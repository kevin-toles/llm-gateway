"""Provider Router - Routes requests to appropriate LLM provider.

This module implements the Strategy pattern for provider selection,
routing requests to the appropriate LLM provider based on model name.

All routing data is loaded from config/model_registry.yaml at startup.
The YAML is the SINGLE source of truth — no hardcoded model dicts.

Reference: Microservices Patterns Ch.27 (API Gateway routing map pattern),
           MLflow gateway/config.py (YAML-driven provider routing)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from src.providers.base import LLMProvider

if TYPE_CHECKING:
    from src.core.config import Settings

logger = logging.getLogger(__name__)

# Path to the canonical model registry
_REGISTRY_PATH = Path(__file__).parent.parent.parent / "config" / "model_registry.yaml"


def _load_model_registry(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical model registry from YAML.

    This is the SINGLE source of truth for model→provider routing.
    No hardcoded dicts — everything comes from this file.

    Pattern: MLflow _load_gateway_config() — YAML → Pydantic validation.
    Anti-pattern avoided: Dual source of truth (PLATFORM_CONSOLIDATED_ISSUES C-9).

    Args:
        path: Override path for testing. Defaults to config/model_registry.yaml.

    Returns:
        Parsed registry dict.

    Raises:
        FileNotFoundError: If registry YAML doesn't exist.
        yaml.YAMLError: If YAML is malformed.
    """
    registry_path = path or _REGISTRY_PATH
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Model registry not found: {registry_path}. "
            "Cannot start gateway without a model registry."
        )
    with open(registry_path) as f:
        config = yaml.safe_load(f)
    logger.info("Loaded model registry from %s", registry_path)
    return config


def _build_registered_models(config: dict[str, Any]) -> dict[str, str]:
    """Build the COMPLETE model→provider allowlist from registry YAML.

    Reads EVERY provider's `models:` list and maps each model to its
    provider name. This is THE bouncer list — if a model isn't here,
    it cannot be contacted. Period.

    Pattern: MLflow gateway/app.py — `if name in self.dynamic_endpoints`
    Pattern: Terraform provider_validation.go — `if _, exists := m[key]`
    Pattern: Kubernetes Gatekeeper — explicit constraint list

    Args:
        config: Parsed model_registry.yaml.

    Returns:
        Dict mapping model name → provider name (ALL providers, ALL models).
    """
    registered: dict[str, str] = {}
    providers = config.get("providers", {})
    for provider_name, provider_config in providers.items():
        for model in provider_config.get("models", []):
            registered[model] = provider_name
    logger.info(
        "Registered %d models from YAML: %s",
        len(registered),
        {v: sum(1 for m in registered if registered[m] == v) for v in set(registered.values())},
    )
    return registered


def _build_prefix_map(config: dict[str, Any]) -> dict[str, str]:
    """Build prefix→provider map from registry YAML.

    Reads ANY provider that has a `prefix` field and maps it
    to that provider name.

    Args:
        config: Parsed model_registry.yaml.

    Returns:
        Dict mapping prefix (e.g. "openrouter/") → provider name.
    """
    prefix_map: dict[str, str] = {}
    providers = config.get("providers", {})
    for provider_name, provider_config in providers.items():
        prefix = provider_config.get("prefix", "")
        if prefix:
            prefix_map[prefix] = provider_name
    logger.info("Built MODEL_PREFIXES from YAML: %s", prefix_map)
    return prefix_map


def _build_aliases(config: dict[str, Any]) -> dict[str, str]:
    """Build alias→model map from registry YAML.

    Aliases are shorthand names like "openai" → "gpt-5.2".

    Args:
        config: Parsed model_registry.yaml.

    Returns:
        Dict mapping alias → default model name.
    """
    aliases = config.get("aliases", {})
    logger.info("Built %d provider aliases from YAML", len(aliases))
    return aliases


class NoProviderError(Exception):
    """Raised when no provider is available for the requested model."""

    pass


class ProviderRouter:
    """Routes requests to appropriate LLM provider based on model name.

    Bouncer pattern: if you're not on the list, you're not getting in.

    All routing data is loaded from config/model_registry.yaml.
    Every provider lists its models. That list IS the registry.
    If a model isn't in a provider's `models:` list, it cannot be contacted.

    Routing: alias → prefix → dict lookup → reject.
    No wildcards. No globs. No fallbacks.

    Reference: MLflow gateway/app.py — `if name in self.dynamic_endpoints`
    Reference: Terraform provider_validation.go — `if _, exists := m[key]`
    Reference: Microservices Patterns Ch.27 — "consults a routing map"
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
        default_provider: str | None = None,
        registry_path: Path | None = None,
    ) -> None:
        """Initialize the provider router.

        Loads routing tables from config/model_registry.yaml.

        Args:
            providers: Dictionary mapping provider names to provider instances.
            default_provider: Name of the default provider (used ONLY if
                              registry YAML specifies a non-null default).
            registry_path: Override path for testing.
        """
        self._providers: dict[str, LLMProvider] = providers or {}
        self._default_provider = default_provider

        # Load routing data from YAML — the SINGLE source of truth
        try:
            config = _load_model_registry(registry_path)
        except FileNotFoundError:
            logger.warning("Model registry YAML not found, using empty routing tables")
            config = {"providers": {}, "routing": [], "aliases": {}}

        self.REGISTERED_MODELS = _build_registered_models(config)
        self.MODEL_PREFIXES = _build_prefix_map(config)
        self.PROVIDER_DEFAULTS = _build_aliases(config)

        # Respect YAML routing_default setting — null means NO default (reject unknown)
        yaml_default = config.get("routing_default")
        if yaml_default is None:
            # YAML says null → no silent fallback
            self._default_provider = None

    @property
    def providers(self) -> dict[str, LLMProvider]:
        """Get the registered providers."""
        return self._providers

    @property
    def default_provider(self) -> str | None:
        """Get the default provider name."""
        return self._default_provider

    def get_provider(self, model: str) -> LLMProvider:
        """Get the appropriate provider for the given model.

        Like a bouncer at a club: if you're not on the list, you're not getting in.

        Routing Priority:
        1. Alias resolution (e.g. "openai" → "gpt-5.2" → re-lookup)
        2. Explicit prefix (e.g. "openrouter/model" → openrouter provider)
        3. Registered model lookup (THE list — built from all providers' models)
        4. REJECT — raise NoProviderError

        Pattern: MLflow gateway/app.py — if name in endpoints → route, else reject
        Pattern: Terraform — if _, exists := m[key]; exists → use, else skip
        """
        if not self._providers:
            raise NoProviderError("No providers registered")

        model_lower = model.lower()

        # 1. Alias? (e.g. "openai" → "gpt-5.2", then re-lookup)
        if model_lower in self.PROVIDER_DEFAULTS:
            actual_model = self.PROVIDER_DEFAULTS[model_lower]
            logger.info(f"Alias '{model}' -> '{actual_model}'")
            return self.get_provider(actual_model)

        # 2. Explicit prefix? (e.g. "openrouter/mixtral" → openrouter)
        for prefix, provider_name in self.MODEL_PREFIXES.items():
            if model_lower.startswith(prefix) and provider_name in self._providers:
                logger.info(f"Routing {model} to {provider_name} (prefix '{prefix}')")
                return self._providers[provider_name]

        # 3. On the list? (exact match in REGISTERED_MODELS)
        provider_name = self.REGISTERED_MODELS.get(model) or self.REGISTERED_MODELS.get(model_lower)
        if provider_name and provider_name in self._providers:
            logger.info(f"Routing {model} to {provider_name} (registered)")
            return self._providers[provider_name]

        # 4. Not on the list = not getting in
        raise NoProviderError(
            f"Model '{model}' is not registered in model_registry.yaml. "
            f"Only registered models can be contacted."
        )

    def resolve_model_alias(self, model: str) -> str:
        """Resolve a model alias to the actual model name.
        
        If the model is an alias (e.g., 'openai', 'chatgpt', 'claude'),
        returns the default model for that provider. Otherwise returns
        the model unchanged.
        
        Args:
            model: The model name or alias.
            
        Returns:
            The resolved model name.
        """
        model_lower = model.lower()
        if model_lower in self.PROVIDER_DEFAULTS:
            resolved = self.PROVIDER_DEFAULTS[model_lower]
            logger.info(f"Resolved alias '{model}' -> '{resolved}'")
            return resolved
        return model

    def list_available_models(self) -> list[str]:
        """List all registered models.

        Returns models from the REGISTERED_MODELS registry
        whose providers are actually loaded.

        Returns:
            List of registered model names.
        """
        return [
            model for model, provider in self.REGISTERED_MODELS.items()
            if provider in self._providers
        ]

    def list_available_models_by_provider(self) -> dict[str, list[str]]:
        """List registered models grouped by provider.

        Returns models from the REGISTERED_MODELS registry, filtered
        to providers that are actually loaded.

        Returns:
            Dictionary mapping provider names to their registered model lists.
        """
        result: dict[str, list[str]] = {}
        for model_name, provider_name in self.REGISTERED_MODELS.items():
            if provider_name in self._providers:
                result.setdefault(provider_name, []).append(model_name)
        return result

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """Register a new provider.

        Args:
            name: The name to register the provider under.
            provider: The provider instance.
        """
        self._providers[name] = provider

    def unregister_provider(self, name: str) -> None:
        """Unregister a provider.

        Args:
            name: The name of the provider to unregister.
        """
        self._providers.pop(name, None)

    def get_provider_names(self) -> list[str]:
        """Get the names of all registered providers.

        Returns:
            List of provider names.
        """
        return list(self._providers.keys())


def _register_inference(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register Inference Service provider for local models.
    
    This is the PRIMARY provider for local LLMs (qwen2.5-7b, deepseek-r1-7b, phi-4).
    
    When CMS is enabled, requests route through CMS proxy which intercepts,
    checks context windows, and forwards to inference-service.
    When CMS is disabled, routes directly to inference-service:8085.
    """
    inference_url = getattr(settings, 'inference_service_url', 'http://localhost:8085')
    cms_url = getattr(settings, 'cms_url', None)
    cms_enabled = getattr(settings, 'cms_enabled', False)
    try:
        from src.providers.inference import InferenceServiceProvider
        providers["inference"] = InferenceServiceProvider(
            base_url=inference_url,
            cms_url=cms_url,
            cms_enabled=cms_enabled,
        )
        mode = "via CMS proxy" if cms_enabled and cms_url else "direct"
        logger.info(f"Inference provider registered ({mode}, inference={inference_url})")
    except Exception as e:
        logger.warning(f"Could not initialize Inference provider: {e}")


def _register_openai(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register OpenAI provider if API key is available."""
    if settings.openai_api_key is None:
        return
    openai_key = settings.openai_api_key.get_secret_value()
    if not openai_key:
        return
    from src.providers.openai import OpenAIProvider
    providers["openai"] = OpenAIProvider(api_key=openai_key)
    logger.info("OpenAI provider registered")


def _register_openrouter(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register OpenRouter provider (external cloud API).
    
    OpenRouter is ONLY used when explicitly requested with 'openrouter/' prefix.
    It is NOT used for local models like qwen2.5-7b - those go to inference-service.
    """
    if settings.openrouter_api_key is None:
        return
    openrouter_key = settings.openrouter_api_key.get_secret_value()
    if not openrouter_key:
        return
    from src.providers.openrouter import OpenRouterProvider
    providers["openrouter"] = OpenRouterProvider(api_key=openrouter_key)
    logger.info("OpenRouter provider registered (use 'openrouter/' prefix to invoke)")


def _register_anthropic(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register Anthropic provider if API key is available."""
    if settings.anthropic_api_key is None:
        return
    anthropic_key = settings.anthropic_api_key.get_secret_value()
    if not anthropic_key:
        return
    try:
        from src.providers.anthropic import AnthropicProvider
        providers["anthropic"] = AnthropicProvider(api_key=anthropic_key)
        logger.info("Anthropic provider registered")
    except Exception as e:
        logger.warning(f"Could not initialize Anthropic provider: {e}")


def _register_deepseek(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register DeepSeek provider if API key is available."""
    if settings.deepseek_api_key is None:
        return
    deepseek_key = settings.deepseek_api_key.get_secret_value()
    if not deepseek_key:
        return
    try:
        from src.providers.deepseek import DeepSeekProvider
        providers["deepseek"] = DeepSeekProvider(api_key=deepseek_key)
        logger.info("DeepSeek provider registered (Reasoner)")
    except Exception as e:
        logger.warning(f"Could not initialize DeepSeek provider: {e}")


def _register_gemini(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register Gemini provider if API key is available."""
    if settings.gemini_api_key is None:
        return
    gemini_key = settings.gemini_api_key.get_secret_value()
    if not gemini_key:
        return
    try:
        from src.providers.gemini import GeminiProvider
        # Register as "google" to match EXTERNAL_MODELS and MODEL_PREFIXES routing
        providers["google"] = GeminiProvider(api_key=gemini_key)
        logger.info("Google/Gemini provider registered")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini provider: {e}")


def _register_llamacpp(settings: "Settings", providers: dict[str, LLMProvider]) -> None:
    """Register LlamaCpp provider if enabled."""
    if not settings.llamacpp_enabled:
        return
    try:
        from src.providers.llamacpp import LlamaCppProvider
        providers["llamacpp"] = LlamaCppProvider(
            models_dir=settings.llamacpp_models_dir,
            n_gpu_layers=settings.llamacpp_gpu_layers,
        )
        logger.info(
            f"LlamaCpp provider registered "
            f"(models_dir={settings.llamacpp_models_dir})"
        )
    except ImportError as e:
        logger.warning(
            f"Could not initialize LlamaCpp provider - "
            f"llama-cpp-python not installed: {e}"
        )
    except Exception as e:
        logger.warning(f"Could not initialize LlamaCpp provider: {e}")


def create_provider_router(settings: "Settings") -> ProviderRouter:
    """Create a provider router from settings.

    Factory function that instantiates providers based on available
    API keys in settings and creates a router with them.

    Provider Routing (EXTERNAL ONLY):
    - openai: GPT models → OpenAI API
    - anthropic: Claude models → Anthropic API  
    - deepseek: DeepSeek cloud API (deepseek-reasoner)
    - gemini: Google Gemini → Google AI API
    - openrouter: ONLY when explicitly requested with 'openrouter/' prefix

    Service Boundary:
    - Local models (inference-service) are NOT registered in the gateway.
    - Local model requests should go to CMS /v1/proxy/chat/completions.
    - See config/model_registry.yaml for the canonical model registry.

    Args:
        settings: Application settings containing API keys and defaults.

    Returns:
        Configured ProviderRouter instance.
    """
    providers: dict[str, LLMProvider] = {}

    # NOTE: Inference provider is NOT registered in the gateway.
    # Local models are managed by CMS (Context Management Service).
    # Gateway only handles external/cloud model routing.
    # See: config/model_registry.yaml for the canonical model registry.
    
    # Cloud providers
    _register_openai(settings, providers)
    _register_anthropic(settings, providers)
    _register_deepseek(settings, providers)
    _register_gemini(settings, providers)
    
    # OpenRouter - only for explicit requests
    _register_openrouter(settings, providers)
    
    # Legacy local providers
    _register_llamacpp(settings, providers)

    provider_names = list(providers.keys())
    logger.info(f"Provider router initialized with: {provider_names}")

    if not providers:
        logger.error(
            "No LLM providers available! Ensure inference-service is running "
            "or set API keys for cloud providers."

        )

    default = settings.default_provider if settings.default_provider in providers else None
    return ProviderRouter(providers=providers, default_provider=default)

