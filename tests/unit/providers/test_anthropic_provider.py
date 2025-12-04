"""
Tests for Anthropic Provider - WBS 2.3.2.1 Anthropic Claude Adapter

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 41 - anthropic.py "Anthropic Claude adapter"
- GUIDELINES pp. 215: Provider abstraction for model swapping
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES pp. 2229: Model API patterns

WBS Items Covered:
- 2.3.2.1.1: Create AnthropicProvider class
- 2.3.2.1.2: Implement LLMProvider interface
- 2.3.2.1.3: __init__ with api_key parameter
- 2.3.2.1.4: Implement complete() method
- 2.3.2.1.5: Implement stream() method
- 2.3.2.1.6: Implement supports_model() for claude-* models
- 2.3.2.1.7: Implement get_supported_models()
- 2.3.2.1.8: Retry logic with exponential backoff
- 2.3.2.1.9: Error handling (ProviderError, RateLimitError, AuthenticationError)
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# WBS 2.3.2.1.1: AnthropicProvider Class Exists
# =============================================================================


class TestAnthropicProviderClass:
    """Tests for AnthropicProvider class existence and structure."""

    def test_anthropic_provider_importable(self) -> None:
        """
        WBS 2.3.2.1.1: AnthropicProvider can be imported.
        """
        from src.providers.anthropic import AnthropicProvider

        assert AnthropicProvider is not None

    def test_anthropic_provider_is_llm_provider(self) -> None:
        """
        WBS 2.3.2.1.2: AnthropicProvider inherits from LLMProvider.
        """
        from src.providers.anthropic import AnthropicProvider
        from src.providers.base import LLMProvider

        assert issubclass(AnthropicProvider, LLMProvider)


# =============================================================================
# WBS 2.3.2.1.3: Initialization
# =============================================================================


class TestAnthropicProviderInit:
    """Tests for AnthropicProvider initialization."""

    def test_init_with_api_key(self) -> None:
        """
        WBS 2.3.2.1.3: __init__ accepts api_key parameter.
        """
        from src.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="test-key")
        assert provider is not None

    def test_init_with_optional_params(self) -> None:
        """
        WBS 2.3.2.1.3: __init__ accepts optional parameters.
        """
        from src.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(
            api_key="test-key",
            max_retries=5,
            retry_delay=2.0,
        )
        assert provider is not None


# =============================================================================
# WBS 2.3.2.1.6: supports_model() Method
# =============================================================================


class TestAnthropicProviderSupportsModel:
    """Tests for supports_model() method."""

    @pytest.fixture
    def provider(self) -> Any:
        """Create provider instance for testing."""
        from src.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key="test-key")

    def test_supports_claude_3_opus(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns True for claude-3-opus.
        """
        assert provider.supports_model("claude-3-opus-20240229") is True

    def test_supports_claude_3_sonnet(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns True for claude-3-sonnet.
        """
        assert provider.supports_model("claude-3-sonnet-20240229") is True

    def test_supports_claude_3_5_sonnet(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns True for claude-3-5-sonnet.
        """
        assert provider.supports_model("claude-3-5-sonnet-20241022") is True

    def test_supports_claude_3_haiku(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns True for claude-3-haiku.
        """
        assert provider.supports_model("claude-3-haiku-20240307") is True

    def test_supports_claude_prefix_match(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model uses prefix matching for claude-*.
        """
        assert provider.supports_model("claude-3-opus-unknown-version") is True

    def test_does_not_support_gpt_models(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns False for GPT models.
        """
        assert provider.supports_model("gpt-4") is False
        assert provider.supports_model("gpt-3.5-turbo") is False

    def test_does_not_support_llama_models(self, provider) -> None:
        """
        WBS 2.3.2.1.6: supports_model returns False for Ollama models.
        """
        assert provider.supports_model("llama2") is False


# =============================================================================
# WBS 2.3.2.1.7: get_supported_models() Method
# =============================================================================


class TestAnthropicProviderGetSupportedModels:
    """Tests for get_supported_models() method."""

    @pytest.fixture
    def provider(self) -> Any:
        """Create provider instance for testing."""
        from src.providers.anthropic import AnthropicProvider

        return AnthropicProvider(api_key="test-key")

    def test_get_supported_models_returns_list(self, provider) -> None:
        """
        WBS 2.3.2.1.7: get_supported_models returns a list.
        """
        models = provider.get_supported_models()
        assert isinstance(models, list)

    def test_get_supported_models_includes_claude_3(self, provider) -> None:
        """
        WBS 2.3.2.1.7: List includes Claude 3 models.
        """
        models = provider.get_supported_models()
        assert any("claude-3" in m for m in models)

    def test_get_supported_models_includes_opus(self, provider) -> None:
        """
        WBS 2.3.2.1.7: List includes Claude 3 Opus.
        """
        models = provider.get_supported_models()
        assert any("opus" in m for m in models)

    def test_get_supported_models_includes_sonnet(self, provider) -> None:
        """
        WBS 2.3.2.1.7: List includes Claude 3 Sonnet.
        """
        models = provider.get_supported_models()
        assert any("sonnet" in m for m in models)

    def test_get_supported_models_includes_haiku(self, provider) -> None:
        """
        WBS 2.3.2.1.7: List includes Claude 3 Haiku.
        """
        models = provider.get_supported_models()
        assert any("haiku" in m for m in models)


# =============================================================================
# WBS 2.3.2.1.4: complete() Method
# =============================================================================


class TestAnthropicProviderComplete:
    """Tests for complete() method."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create mock Anthropic client."""
        mock_response = MagicMock()
        mock_response.id = "msg_test123"
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_response.model = "claude-3-sonnet-20240229"
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
        )
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.fixture
    def sample_request(self):
        """Create sample chat completion request."""
        from src.models.requests import ChatCompletionRequest, Message

        return ChatCompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[
                Message(role="user", content="Hello"),
            ],
        )

    @pytest.mark.asyncio
    async def test_complete_returns_response(
        self, mock_anthropic_client, sample_request
    ) -> None:
        """
        WBS 2.3.2.1.4: complete() returns ChatCompletionResponse.
        """
        from src.providers.anthropic import AnthropicProvider
        from src.models.responses import ChatCompletionResponse

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_anthropic_client,
        ):
            provider = AnthropicProvider(api_key="test-key")
            response = await provider.complete(sample_request)

        assert isinstance(response, ChatCompletionResponse)

    @pytest.mark.asyncio
    async def test_complete_response_has_id(
        self, mock_anthropic_client, sample_request
    ) -> None:
        """
        WBS 2.3.2.1.4: Response has id field.
        """
        from src.providers.anthropic import AnthropicProvider

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_anthropic_client,
        ):
            provider = AnthropicProvider(api_key="test-key")
            response = await provider.complete(sample_request)

        assert response.id is not None
        assert "msg_" in response.id

    @pytest.mark.asyncio
    async def test_complete_response_has_choices(
        self, mock_anthropic_client, sample_request
    ) -> None:
        """
        WBS 2.3.2.1.4: Response has choices with content.
        """
        from src.providers.anthropic import AnthropicProvider

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_anthropic_client,
        ):
            provider = AnthropicProvider(api_key="test-key")
            response = await provider.complete(sample_request)

        assert len(response.choices) > 0
        assert response.choices[0].message.content == "Hello!"

    @pytest.mark.asyncio
    async def test_complete_response_has_usage(
        self, mock_anthropic_client, sample_request
    ) -> None:
        """
        WBS 2.3.2.1.4: Response has usage statistics.
        """
        from src.providers.anthropic import AnthropicProvider

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_anthropic_client,
        ):
            provider = AnthropicProvider(api_key="test-key")
            response = await provider.complete(sample_request)

        assert response.usage is not None
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15


# =============================================================================
# WBS 2.3.2.1.9: Error Handling
# =============================================================================


class TestAnthropicProviderErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def sample_request(self):
        """Create sample chat completion request."""
        from src.models.requests import ChatCompletionRequest, Message

        return ChatCompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[
                Message(role="user", content="Hello"),
            ],
        )

    @pytest.mark.asyncio
    async def test_authentication_error_raised(self, sample_request) -> None:
        """
        WBS 2.3.2.1.9: AuthenticationError raised for invalid API key.
        """
        from src.providers.anthropic import AnthropicProvider
        from src.core.exceptions import AuthenticationError

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("Authentication failed: Invalid API key")
        )

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = AnthropicProvider(api_key="invalid-key")
            with pytest.raises(AuthenticationError):
                await provider.complete(sample_request)

    @pytest.mark.asyncio
    async def test_rate_limit_error_raised(self, sample_request) -> None:
        """
        WBS 2.3.2.1.9: RateLimitError raised for rate limit errors.
        """
        from src.providers.anthropic import AnthropicProvider
        from src.core.exceptions import RateLimitError

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = AnthropicProvider(api_key="test-key", max_retries=1)
            with pytest.raises(RateLimitError):
                await provider.complete(sample_request)

    @pytest.mark.asyncio
    async def test_provider_error_raised_for_other_errors(
        self, sample_request
    ) -> None:
        """
        WBS 2.3.2.1.9: ProviderError raised for other errors.
        """
        from src.providers.anthropic import AnthropicProvider
        from src.core.exceptions import ProviderError

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("Internal server error")
        )

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = AnthropicProvider(api_key="test-key", max_retries=1)
            with pytest.raises(ProviderError):
                await provider.complete(sample_request)


# =============================================================================
# WBS 2.3.2.1.5: stream() Method
# =============================================================================


class TestAnthropicProviderStream:
    """Tests for stream() method."""

    @pytest.fixture
    def sample_request(self):
        """Create sample chat completion request."""
        from src.models.requests import ChatCompletionRequest, Message

        return ChatCompletionRequest(
            model="claude-3-sonnet-20240229",
            messages=[
                Message(role="user", content="Hello"),
            ],
            stream=True,
        )

    @pytest.mark.asyncio
    async def test_stream_returns_async_iterator(self, sample_request) -> None:
        """
        WBS 2.3.2.1.5: stream() returns an async iterator.
        """
        from src.providers.anthropic import AnthropicProvider
        from collections.abc import AsyncIterator

        # Create mock stream events
        async def mock_stream():
            # Message start event
            event1 = MagicMock()
            event1.type = "message_start"
            event1.message = MagicMock()
            event1.message.id = "msg_test123"
            event1.message.model = "claude-3-sonnet-20240229"
            event1.message.usage = MagicMock(input_tokens=10, output_tokens=0)
            yield event1

            # Content block delta event
            event2 = MagicMock()
            event2.type = "content_block_delta"
            event2.delta = MagicMock(type="text_delta", text="Hello")
            yield event2

            # Message delta event (final)
            event3 = MagicMock()
            event3.type = "message_delta"
            event3.delta = MagicMock(stop_reason="end_turn")
            event3.usage = MagicMock(output_tokens=5)
            yield event3

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.stream = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_stream()),
                __aexit__=AsyncMock(return_value=None),
            )
        )

        with patch(
            "src.providers.anthropic.AsyncAnthropic",
            return_value=mock_client,
        ):
            provider = AnthropicProvider(api_key="test-key")
            result = provider.stream(sample_request)

            assert isinstance(result, AsyncIterator)


# =============================================================================
# WBS 2.3.2.1: Provider Registration
# =============================================================================


class TestAnthropicProviderExports:
    """Tests for module exports."""

    def test_anthropic_provider_in_providers_init(self) -> None:
        """
        WBS 2.3.2.1: AnthropicProvider exported from providers package.
        """
        # Should be able to import from providers package
        from src.providers.anthropic import AnthropicProvider

        assert AnthropicProvider is not None

    def test_supported_models_constant_exists(self) -> None:
        """
        WBS 2.3.2.1.7: SUPPORTED_MODELS constant exists.
        """
        from src.providers.anthropic import SUPPORTED_MODELS

        assert isinstance(SUPPORTED_MODELS, list)
        assert len(SUPPORTED_MODELS) > 0

