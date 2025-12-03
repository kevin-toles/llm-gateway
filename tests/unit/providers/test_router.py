"""
Tests for Provider Router - WBS 2.3.5

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 44 - router.py "Provider routing logic"
- ARCHITECTURE.md: Lines 206-208 - Provider Router description
- GUIDELINES pp. 2255: AI router extends routing patterns
- GUIDELINES pp. 276: Factory pattern with get_*_repo() patterns

Test Categories:
- WBS 2.3.5.1: Router Implementation
  - 2.3.5.1.2: ProviderRouter class
  - 2.3.5.1.4: get_provider() method
  - 2.3.5.1.6: Fall back to default provider
  - 2.3.5.1.7: list_available_models() aggregating all providers
  - 2.3.5.1.8-11: RED/GREEN tests for routing

- WBS 2.3.5.2: Provider Factory
  - 2.3.5.2.1: create_provider_router() factory
  - 2.3.5.2.2: Initialize providers from settings
  - 2.3.5.2.3: Skip providers without API keys
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Optional

from src.providers.base import LLMProvider


# =============================================================================
# Mock Provider for Testing
# =============================================================================


class MockProvider(LLMProvider):
    """Mock provider for testing router."""

    def __init__(self, name: str, models: list[str]) -> None:
        self._name = name
        self._models = models

    async def complete(self, request):
        return MagicMock()

    async def stream(self, request):
        yield MagicMock()

    def supports_model(self, model: str) -> bool:
        return any(model.startswith(m.rstrip("*")) for m in self._models)

    def get_supported_models(self) -> list[str]:
        return self._models.copy()

    @property
    def available_models(self) -> list[str]:
        """Alias for get_supported_models for compatibility."""
        return self._models.copy()


# =============================================================================
# WBS 2.3.5.1.2: ProviderRouter class tests
# =============================================================================


class TestProviderRouterClass:
    """Tests for ProviderRouter class structure."""

    def test_provider_router_can_be_instantiated(self) -> None:
        """
        WBS 2.3.5.1.2: ProviderRouter class exists.
        """
        from src.providers.router import ProviderRouter

        router = ProviderRouter()
        assert router is not None

    def test_provider_router_accepts_providers_dict(self) -> None:
        """
        WBS 2.3.5.1.3: ProviderRouter accepts providers in constructor.
        """
        from src.providers.router import ProviderRouter

        mock_provider = MockProvider("test", ["test-*"])
        router = ProviderRouter(providers={"test": mock_provider})

        assert router is not None

    def test_provider_router_accepts_default_provider(self) -> None:
        """
        WBS 2.3.5.1.6: ProviderRouter accepts default_provider name.
        """
        from src.providers.router import ProviderRouter

        mock_provider = MockProvider("anthropic", ["claude-*"])
        router = ProviderRouter(
            providers={"anthropic": mock_provider},
            default_provider="anthropic",
        )

        assert router is not None


# =============================================================================
# WBS 2.3.5.1.4: get_provider() tests
# =============================================================================


class TestProviderRouterGetProvider:
    """Tests for get_provider method."""

    def test_get_provider_returns_anthropic_for_claude_model(self) -> None:
        """
        WBS 2.3.5.1.8: Router returns correct provider for model.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus", "claude-3-sonnet"])
        openai = MockProvider("openai", ["gpt-4", "gpt-3.5-turbo"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
        )

        provider = router.get_provider("claude-3-opus")
        assert provider is anthropic

    def test_get_provider_returns_openai_for_gpt_model(self) -> None:
        """
        WBS 2.3.5.1.8: Router returns correct provider for GPT models.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        openai = MockProvider("openai", ["gpt-4", "gpt-3.5-turbo"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
        )

        provider = router.get_provider("gpt-4")
        assert provider is openai

    def test_get_provider_returns_ollama_for_llama_model(self) -> None:
        """
        WBS 2.3.5.1.8: Router returns correct provider for Ollama models.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        ollama = MockProvider("ollama", ["llama2", "mistral", "codellama"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "ollama": ollama},
        )

        provider = router.get_provider("llama2")
        assert provider is ollama

    def test_get_provider_uses_prefix_matching(self) -> None:
        """
        WBS 2.3.5.1.5: Router matches based on model name prefix.
        """
        from src.providers.router import ProviderRouter

        openai = MockProvider("openai", ["gpt-4", "gpt-3.5-turbo"])

        router = ProviderRouter(providers={"openai": openai})

        # Should match gpt-4 even with version suffix
        provider = router.get_provider("gpt-4-turbo-preview")
        assert provider is openai


# =============================================================================
# WBS 2.3.5.1.6: Default provider fallback tests
# =============================================================================


class TestProviderRouterDefaultFallback:
    """Tests for default provider fallback."""

    def test_get_provider_falls_back_to_default(self) -> None:
        """
        WBS 2.3.5.1.9: Router falls back to default provider.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        openai = MockProvider("openai", ["gpt-4"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
            default_provider="anthropic",
        )

        # Unknown model should fall back to default
        provider = router.get_provider("unknown-model")
        assert provider is anthropic

    def test_get_provider_uses_first_provider_if_no_default(self) -> None:
        """
        WBS 2.3.5.1.6: Falls back to first provider if no default set.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])

        router = ProviderRouter(providers={"anthropic": anthropic})

        # Should use first provider when no default
        provider = router.get_provider("unknown-model")
        assert provider is anthropic


# =============================================================================
# WBS 2.3.5.1.10: Unknown model error tests
# =============================================================================


class TestProviderRouterErrors:
    """Tests for error handling."""

    def test_get_provider_raises_error_when_no_providers(self) -> None:
        """
        WBS 2.3.5.1.10: Unknown model raises error when no providers.
        """
        from src.providers.router import ProviderRouter, NoProviderError

        router = ProviderRouter(providers={})

        with pytest.raises(NoProviderError):
            router.get_provider("any-model")

    def test_get_provider_raises_error_for_invalid_default(self) -> None:
        """
        WBS 2.3.5.1.10: Error when default provider not found.
        """
        from src.providers.router import ProviderRouter, NoProviderError

        anthropic = MockProvider("anthropic", ["claude-3-opus"])

        router = ProviderRouter(
            providers={"anthropic": anthropic},
            default_provider="nonexistent",
        )

        # Unknown model can't fall back to nonexistent default
        with pytest.raises(NoProviderError):
            router.get_provider("unknown-model")

    def test_no_provider_error_is_importable(self) -> None:
        """
        WBS 2.3.5.1.10: NoProviderError is importable.
        """
        from src.providers.router import NoProviderError

        error = NoProviderError("No provider found")
        assert str(error) == "No provider found"


# =============================================================================
# WBS 2.3.5.1.7: list_available_models() tests
# =============================================================================


class TestProviderRouterListModels:
    """Tests for list_available_models method."""

    def test_list_available_models_aggregates_all_providers(self) -> None:
        """
        WBS 2.3.5.1.7: list_available_models aggregates from all providers.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus", "claude-3-sonnet"])
        openai = MockProvider("openai", ["gpt-4", "gpt-3.5-turbo"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
        )

        models = router.list_available_models()

        assert "claude-3-opus" in models
        assert "claude-3-sonnet" in models
        assert "gpt-4" in models
        assert "gpt-3.5-turbo" in models
        assert len(models) == 4

    def test_list_available_models_returns_empty_for_no_providers(self) -> None:
        """
        WBS 2.3.5.1.7: Returns empty list when no providers.
        """
        from src.providers.router import ProviderRouter

        router = ProviderRouter(providers={})
        models = router.list_available_models()

        assert models == []

    def test_list_available_models_includes_provider_name(self) -> None:
        """
        WBS 2.3.5.1.7: list_available_models_by_provider returns dict.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        openai = MockProvider("openai", ["gpt-4"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
        )

        models_by_provider = router.list_available_models_by_provider()

        assert "anthropic" in models_by_provider
        assert "openai" in models_by_provider
        assert "claude-3-opus" in models_by_provider["anthropic"]
        assert "gpt-4" in models_by_provider["openai"]


# =============================================================================
# WBS 2.3.5.1.12: Configurable registration tests
# =============================================================================


class TestProviderRouterRegistration:
    """Tests for provider registration."""

    def test_register_provider_adds_new_provider(self) -> None:
        """
        WBS 2.3.5.1.12: register_provider adds provider dynamically.
        """
        from src.providers.router import ProviderRouter

        router = ProviderRouter()
        anthropic = MockProvider("anthropic", ["claude-3-opus"])

        router.register_provider("anthropic", anthropic)

        provider = router.get_provider("claude-3-opus")
        assert provider is anthropic

    def test_unregister_provider_removes_provider(self) -> None:
        """
        WBS 2.3.5.1.12: unregister_provider removes provider.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        router = ProviderRouter(providers={"anthropic": anthropic})

        router.unregister_provider("anthropic")

        assert "anthropic" not in router._providers

    def test_get_provider_names_returns_registered_names(self) -> None:
        """
        WBS 2.3.5.1.12: get_provider_names returns list of provider names.
        """
        from src.providers.router import ProviderRouter

        anthropic = MockProvider("anthropic", ["claude-3-opus"])
        openai = MockProvider("openai", ["gpt-4"])

        router = ProviderRouter(
            providers={"anthropic": anthropic, "openai": openai},
        )

        names = router.get_provider_names()

        assert "anthropic" in names
        assert "openai" in names


# =============================================================================
# WBS 2.3.5.2: Provider Factory tests
# =============================================================================


class TestCreateProviderRouter:
    """Tests for create_provider_router factory function."""

    def test_create_provider_router_exists(self) -> None:
        """
        WBS 2.3.5.2.1: create_provider_router function exists.
        """
        from src.providers.router import create_provider_router

        assert callable(create_provider_router)

    def test_create_provider_router_returns_router(self) -> None:
        """
        WBS 2.3.5.2.1: Factory returns ProviderRouter instance.
        """
        from src.providers.router import create_provider_router, ProviderRouter
        from pydantic import SecretStr

        # Mock settings with API keys
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = SecretStr("test-anthropic-key")
        mock_settings.openai_api_key = SecretStr("test-openai-key")
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.default_provider = "anthropic"

        # Create router (will use real providers that exist, skip missing ones)
        router = create_provider_router(mock_settings)

        assert isinstance(router, ProviderRouter)

    def test_create_provider_router_skips_providers_without_keys(self) -> None:
        """
        WBS 2.3.5.2.3: Skips providers without API keys.
        """
        from src.providers.router import create_provider_router
        from pydantic import SecretStr

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None  # No key
        mock_settings.openai_api_key = SecretStr("test-openai-key")
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.default_provider = "openai"

        router = create_provider_router(mock_settings)

        # Anthropic should be skipped due to missing key
        assert "anthropic" not in router.get_provider_names()
        # OpenAI should be present (it's implemented)
        assert "openai" in router.get_provider_names()

    def test_create_provider_router_includes_ollama_by_default(self) -> None:
        """
        WBS 2.3.5.2.2: Ollama is included by default (no API key needed).
        """
        from src.providers.router import create_provider_router

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.default_provider = "ollama"

        router = create_provider_router(mock_settings)

        # Ollama should always be included (it's implemented)
        assert "ollama" in router.get_provider_names()

    def test_create_provider_router_uses_settings_default(self) -> None:
        """
        WBS 2.3.5.2.2: Factory uses default_provider from settings.
        """
        from src.providers.router import create_provider_router
        from pydantic import SecretStr

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = SecretStr("test-key")
        mock_settings.openai_api_key = SecretStr("test-key")
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.default_provider = "openai"

        router = create_provider_router(mock_settings)

        assert router._default_provider == "openai"


# =============================================================================
# WBS 2.3.5.2.4: Logging tests
# =============================================================================


class TestProviderRouterLogging:
    """Tests for router logging."""

    def test_create_provider_router_logs_available_providers(self) -> None:
        """
        WBS 2.3.5.2.4: Factory logs available providers on startup.
        """
        from src.providers.router import create_provider_router
        from pydantic import SecretStr

        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = SecretStr("test-key")
        mock_settings.openai_api_key = None
        mock_settings.ollama_url = "http://localhost:11434"
        mock_settings.default_provider = "anthropic"

        with patch("src.providers.router.logger") as mock_logger:
            router = create_provider_router(mock_settings)

            # Should have logged available providers
            mock_logger.info.assert_called()

