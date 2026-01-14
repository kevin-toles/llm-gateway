"""Provider Router - Routes requests to appropriate LLM provider.

This module implements the Strategy pattern for provider selection,
routing requests to the appropriate LLM provider based on model name
or falling back to a configured default provider.
"""

import logging
from typing import TYPE_CHECKING

from src.providers.base import LLMProvider

if TYPE_CHECKING:
    from src.core.config import Settings

logger = logging.getLogger(__name__)

# Constants for duplicate literals
MODEL_GPT_5_2 = "gpt-5.2"
MODEL_GEMINI_1_5_PRO = "gemini-1.5-pro"


class NoProviderError(Exception):
    """Raised when no provider is available for the requested model."""

    pass


class ProviderRouter:
    """Routes requests to appropriate LLM provider based on model name.

    The router maintains a registry of providers and routes requests
    based on model name prefixes. If no matching provider is found,
    it falls back to the configured default provider.

    Attributes:
        providers: Dictionary mapping provider names to provider instances.
        default_provider: Name of the default provider to use as fallback.

    Example:
        >>> router = ProviderRouter(
        ...     providers={"anthropic": anthropic_provider, "openai": openai_provider},
        ...     default_provider="anthropic"
        ... )
        >>> provider = router.get_provider("claude-3-5-sonnet-20241022")
        >>> # Returns anthropic_provider
    """

    # ==========================================================================
    # MODEL ROUTING TABLE
    # ==========================================================================
    # Categories:
    #   1. LOCAL (inference-service) - Default for all local GGUF models
    #   2. EXTERNAL_OWNED - Your API keys (OpenAI, Anthropic, Google)
    #   3. EXTERNAL_AGGREGATOR - Explicit prefix only (openrouter/, ollama/)
    #
    # RULE: OpenRouter is NEVER auto-routed. Must use "openrouter/" prefix.
    # RULE: Ollama requires "ollama/" prefix.
    # ==========================================================================
    
    # Exact model matches for local inference-service (checked first)
    LOCAL_MODELS = {
        # Primary/General
        "phi-4", "qwen2.5-7b", "qwen3-8b", "llama-3.2-3b", "gpt-oss-20b",
        # Reasoning
        "deepseek-r1-7b", "phi-3-medium-128k",
        # Code-Specialized
        "codellama-7b-instruct", "codellama-13b", "qwen2.5-coder-7b",
        "qwen3-coder-30b", "starcoder2-7b", "codegemma-7b",
        "deepseek-coder-v2-lite", "granite-8b-code-128k", "granite-20b-code",
    }
    
    # Exact model matches for external owned APIs
    EXTERNAL_MODELS = {
        # Anthropic (your API key) - support both naming conventions
        "claude-opus-4.5": "anthropic",
        "claude-sonnet-4.5": "anthropic",
        "claude-opus-4-5-20250514": "anthropic",    # User's preferred ID
        "claude-sonnet-4-5-20250514": "anthropic",  # User's preferred ID
        "claude-opus-4-20250514": "anthropic",     # Official Anthropic ID
        "claude-sonnet-4-20250514": "anthropic",   # Official Anthropic ID
        # OpenAI (your API key)
        MODEL_GPT_5_2: "openai",
        "gpt-5.2-pro": "openai",
        "gpt-5-mini": "openai",
        "gpt-5-nano": "openai",
        # Google (your API key)
        "gemini-2.0-flash": "google",
        MODEL_GEMINI_1_5_PRO: "google",
        "gemini-1.5-flash": "google",
        "gemini-pro": "google",
        # DeepSeek (your API key) - direct model access
        "deepseek-reasoner": "deepseek",
    }
    
    # Prefix routing for cloud providers (fallback after exact match)
    MODEL_PREFIXES = {
        # External owned - auto-route by prefix
        "claude-": "anthropic",
        "gpt-": "openai",
        "gemini-": "google",
        
        # External aggregators - EXPLICIT PREFIX REQUIRED
        "openrouter/": "openrouter",  # Must use: openrouter/model-name
        "ollama/": "ollama",          # Must use: ollama/model-name
        "deepseek-api/": "deepseek",  # Must use: deepseek-api/model-name
        
        # Legacy support
        "local/": "llamacpp",
        "llamacpp:": "llamacpp",
        "gguf/": "llamacpp",
    }
    
    # Fallback defaults - when user requests just a provider/alias name
    # Maps shorthand names to the recommended default model
    PROVIDER_DEFAULTS = {
        # OpenAI shortcuts
        "openai": MODEL_GPT_5_2,
        "chatgpt": MODEL_GPT_5_2,
        "gpt": MODEL_GPT_5_2,
        # Anthropic shortcuts - use the -5- format users expect
        "anthropic": "claude-opus-4-5-20250514",
        "claude": "claude-opus-4-5-20250514",
        # DeepSeek shortcuts
        "deepseek": "deepseek-api/deepseek-reasoner",
        "reasoner": "deepseek-api/deepseek-reasoner",
        # Google shortcuts
        "google": MODEL_GEMINI_1_5_PRO,
        "gemini": MODEL_GEMINI_1_5_PRO,
    }

    def __init__(
        self,
        providers: dict[str, LLMProvider] | None = None,
        default_provider: str | None = None,
    ) -> None:
        """Initialize the provider router.

        Args:
            providers: Dictionary mapping provider names to provider instances.
            default_provider: Name of the default provider to use as fallback.
        """
        self._providers: dict[str, LLMProvider] = providers or {}
        self._default_provider = default_provider

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

        Routing Priority:
        0. Provider alias defaults (openai, chatgpt, claude, etc.)
        1. Explicit prefix (openrouter/, ollama/) - strips prefix
        2. Exact match in LOCAL_MODELS -> inference provider
        3. Exact match in EXTERNAL_MODELS -> specific provider
        4. Prefix match in MODEL_PREFIXES -> specific provider
        5. Default provider (inference-service)
        """
        if not self._providers:
            raise NoProviderError("No providers registered")

        model_lower = model.lower()
        
        # Try each routing strategy in order
        provider = self._route_by_alias(model, model_lower)
        if provider:
            return provider
            
        provider = self._route_by_explicit_prefix(model, model_lower)
        if provider:
            return provider
            
        provider = self._route_by_local_model(model, model_lower)
        if provider:
            return provider
            
        provider = self._route_by_external_model(model)
        if provider:
            return provider
            
        provider = self._route_by_prefix_match(model, model_lower)
        if provider:
            return provider
            
        provider = self._route_to_default(model)
        if provider:
            return provider

        raise NoProviderError(f"No provider found for model: {model}")

    def _route_by_alias(self, model: str, model_lower: str) -> LLMProvider | None:
        """Route by provider alias (e.g., 'openai' -> 'gpt-5.2')."""
        if model_lower not in self.PROVIDER_DEFAULTS:
            return None
        actual_model = self.PROVIDER_DEFAULTS[model_lower]
        logger.info(f"Alias '{model}' -> default model '{actual_model}'")
        return self.get_provider(actual_model)

    def _route_by_explicit_prefix(self, model: str, model_lower: str) -> LLMProvider | None:
        """Route by explicit aggregator prefix (openrouter/, ollama/, deepseek-api/)."""
        explicit_prefixes = ["openrouter/", "ollama/", "deepseek-api/"]
        for prefix in explicit_prefixes:
            if not model_lower.startswith(prefix):
                continue
            provider_name = self.MODEL_PREFIXES.get(prefix)
            if provider_name and provider_name in self._providers:
                logger.info(f"Routing {model} to {provider_name} (explicit prefix)")
                return self._providers[provider_name]
        return None

    def _route_by_local_model(self, model: str, model_lower: str) -> LLMProvider | None:
        """Route local models to inference-service."""
        if model_lower not in self.LOCAL_MODELS and model not in self.LOCAL_MODELS:
            return None
        if "inference" in self._providers:
            logger.info(f"Routing {model} to inference-service (local model)")
            return self._providers["inference"]
        return None

    def _route_by_external_model(self, model: str) -> LLMProvider | None:
        """Route external models to their specific provider."""
        if model not in self.EXTERNAL_MODELS:
            return None
        provider_name = self.EXTERNAL_MODELS[model]
        if provider_name in self._providers:
            logger.info(f"Routing {model} to {provider_name} (external owned)")
            return self._providers[provider_name]
        return None

    def _route_by_prefix_match(self, model: str, model_lower: str) -> LLMProvider | None:
        """Route by prefix match (claude-, gpt-, gemini-)."""
        for prefix, provider_name in self.MODEL_PREFIXES.items():
            if model_lower.startswith(prefix) and provider_name in self._providers:
                logger.info(f"Routing {model} to {provider_name} (prefix match)")
                return self._providers[provider_name]
        return None

    def _route_to_default(self, model: str) -> LLMProvider | None:
        """Route to default provider (inference-service or configured default)."""
        if "inference" in self._providers:
            logger.warning(f"Unknown model {model}, defaulting to inference-service")
            return self._providers["inference"]
        if self._default_provider and self._default_provider in self._providers:
            logger.warning(f"Unknown model {model}, using default: {self._default_provider}")
            return self._providers[self._default_provider]
        return None

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
        """List all available models from all registered providers.

        Returns:
            List of model names from all providers.
        """
        models: list[str] = []
        for provider_name, provider in self._providers.items():
            models.extend(provider.get_supported_models())
        return models

    def list_available_models_by_provider(self) -> dict[str, list[str]]:
        """List available models grouped by provider.

        Returns:
            Dictionary mapping provider names to their model lists.
        """
        return {
            provider_name: provider.get_supported_models()
            for provider_name, provider in self._providers.items()
        }

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
    Routes to inference-service:8085 running on the local machine.
    """
    inference_url = getattr(settings, 'inference_service_url', 'http://localhost:8085')
    try:
        from src.providers.inference import InferenceServiceProvider
        providers["inference"] = InferenceServiceProvider(base_url=inference_url)
        logger.info(f"Inference provider registered (url={inference_url})")
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

    Provider Routing:
    - inference: LOCAL models (qwen2.5-7b, deepseek-r1-7b, phi-4) → inference-service:8085
    - openai: GPT models → OpenAI API
    - anthropic: Claude models → Anthropic API  
    - deepseek: DeepSeek cloud API (deepseek-chat, deepseek-reasoner)
    - gemini: Google Gemini → Google AI API
    - openrouter: ONLY when explicitly requested with 'openrouter/' prefix

    Args:
        settings: Application settings containing API keys and defaults.

    Returns:
        Configured ProviderRouter instance.
    """
    providers: dict[str, LLMProvider] = {}

    # Register inference provider FIRST - this is the default for local models
    _register_inference(settings, providers)
    
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

