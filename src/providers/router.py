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

    # Model prefix to provider name mapping
    MODEL_PREFIXES = {
        "claude": "anthropic",
        "gpt": "openai",
        "o1": "openai",
        "o3": "openai",
        "llama": "ollama",
        "mistral": "ollama",
        "codellama": "ollama",
        "deepseek": "ollama",
        "qwen": "ollama",
        "gemma": "ollama",
        "phi": "ollama",
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

        Routes based on model name prefix. Falls back to default provider
        if no prefix match is found.

        Args:
            model: The model name to route (e.g., "claude-3-5-sonnet-20241022").

        Returns:
            The LLMProvider instance for the model.

        Raises:
            NoProviderError: If no provider is available.
        """
        if not self._providers:
            raise NoProviderError("No providers registered")

        # Try to match model prefix
        model_lower = model.lower()
        for prefix, provider_name in self.MODEL_PREFIXES.items():
            if model_lower.startswith(prefix):
                if provider_name in self._providers:
                    return self._providers[provider_name]

        # Fall back to default provider
        if self._default_provider:
            if self._default_provider not in self._providers:
                raise NoProviderError(
                    f"Default provider '{self._default_provider}' not registered"
                )
            return self._providers[self._default_provider]

        # Fall back to first registered provider
        return next(iter(self._providers.values()))

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


def create_provider_router(settings: "Settings") -> ProviderRouter:
    """Create a provider router from settings.

    Factory function that instantiates providers based on available
    API keys in settings and creates a router with them.

    Note: This function gracefully handles missing provider implementations.
    Provider classes that haven't been implemented yet (e.g., AnthropicProvider)
    will be skipped with a warning.

    Args:
        settings: Application settings containing API keys and defaults.

    Returns:
        Configured ProviderRouter instance.
    """
    providers: dict[str, LLMProvider] = {}

    # Try to add Anthropic if API key is available
    # SecretStr.get_secret_value() returns the actual string value
    if settings.anthropic_api_key is not None:
        anthropic_key = settings.anthropic_api_key.get_secret_value()
        if anthropic_key:
            try:
                from src.providers.anthropic import AnthropicProvider

                providers["anthropic"] = AnthropicProvider(api_key=anthropic_key)
            except ImportError:
                logger.warning("AnthropicProvider not yet implemented, skipping")

    # Try to add OpenAI if API key is available
    if settings.openai_api_key is not None:
        openai_key = settings.openai_api_key.get_secret_value()
        if openai_key:
            try:
                from src.providers.openai import OpenAIProvider

                providers["openai"] = OpenAIProvider(api_key=openai_key)
            except ImportError:
                logger.warning("OpenAIProvider not yet implemented, skipping")

    # Try to add Ollama (local, no API key needed)
    try:
        from src.providers.ollama import OllamaProvider

        providers["ollama"] = OllamaProvider(base_url=str(settings.ollama_url))
    except ImportError:
        logger.warning("OllamaProvider not yet implemented, skipping")

    # Log available providers
    provider_names = list(providers.keys())
    logger.info(f"Initialized provider router with providers: {provider_names}")

    return ProviderRouter(
        providers=providers,
        default_provider=settings.default_provider,
    )
