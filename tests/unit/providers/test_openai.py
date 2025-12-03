"""
Tests for OpenAI Provider - WBS 2.3.3

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 42 - openai.py "OpenAI GPT adapter"
- GUIDELINES pp. 2229: Model API patterns
- GUIDELINES pp. 2309: Circuit breaker and resilience patterns
- GUIDELINES pp. 1224: Retry logic with decorators

Test Categories:
- WBS 2.3.3.1: OpenAI Adapter Implementation
  - 2.3.3.1.3: OpenAIProvider class
  - 2.3.3.1.5: complete() method
  - 2.3.3.1.7: stream() method  
  - 2.3.3.1.9: supports_model() method
  - 2.3.3.1.11: Retry logic with exponential backoff
- WBS 2.3.3.2: OpenAI Tool Handling
  - 2.3.3.2.1: Tool definition passthrough
  - 2.3.3.2.2: tool_calls parsing
  - 2.3.3.2.3: Tool message formatting
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator
import time

from src.models.requests import ChatCompletionRequest, Message
from src.models.responses import (
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    ChunkDelta,
    Usage,
)


# =============================================================================
# WBS 2.3.3.1.3: OpenAIProvider class tests
# =============================================================================


class TestOpenAIProviderClass:
    """Tests for OpenAIProvider class structure."""

    def test_openai_provider_inherits_from_llm_provider(self) -> None:
        """
        WBS 2.3.3.1.3: OpenAIProvider extends LLMProvider ABC.
        """
        from src.providers.openai import OpenAIProvider
        from src.providers.base import LLMProvider

        assert issubclass(OpenAIProvider, LLMProvider)

    def test_openai_provider_requires_api_key(self) -> None:
        """
        WBS 2.3.3.1.4: OpenAIProvider requires api_key parameter.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert provider is not None

    def test_openai_provider_accepts_optional_base_url(self) -> None:
        """
        WBS 2.3.3.1.4: OpenAIProvider accepts optional base_url.
        
        This enables Azure OpenAI or other OpenAI-compatible endpoints.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_key="test-key",
            base_url="https://custom.endpoint.com"
        )
        assert provider is not None

    def test_openai_provider_accepts_retry_config(self) -> None:
        """
        WBS 2.3.3.1.11: OpenAIProvider accepts retry configuration.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_key="test-key",
            max_retries=5,
            retry_delay=0.5,
        )
        assert provider is not None


# =============================================================================
# WBS 2.3.3.1.9: supports_model() tests
# =============================================================================


class TestOpenAIProviderSupportsModel:
    """Tests for supports_model method."""

    def test_supports_gpt_4_models(self) -> None:
        """
        WBS 2.3.3.1.9: supports_model returns True for gpt-4 variants.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.supports_model("gpt-4") is True
        assert provider.supports_model("gpt-4-turbo") is True
        assert provider.supports_model("gpt-4-turbo-preview") is True
        assert provider.supports_model("gpt-4o") is True
        assert provider.supports_model("gpt-4o-mini") is True

    def test_supports_gpt_3_5_turbo_models(self) -> None:
        """
        WBS 2.3.3.1.9: supports_model returns True for gpt-3.5-turbo variants.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.supports_model("gpt-3.5-turbo") is True
        assert provider.supports_model("gpt-3.5-turbo-16k") is True

    def test_does_not_support_claude_models(self) -> None:
        """
        WBS 2.3.3.1.9: supports_model returns False for Claude models.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.supports_model("claude-3-opus") is False
        assert provider.supports_model("claude-3-sonnet") is False

    def test_does_not_support_unknown_models(self) -> None:
        """
        WBS 2.3.3.1.9: supports_model returns False for unknown models.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")

        assert provider.supports_model("unknown-model") is False
        assert provider.supports_model("llama-2") is False


# =============================================================================
# WBS 2.3.3.1.10: get_supported_models() tests
# =============================================================================


class TestOpenAIProviderGetSupportedModels:
    """Tests for get_supported_models method."""

    def test_get_supported_models_returns_list(self) -> None:
        """
        WBS 2.3.3.1.10: get_supported_models returns list of strings.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        models = provider.get_supported_models()

        assert isinstance(models, list)
        assert all(isinstance(m, str) for m in models)

    def test_get_supported_models_includes_gpt_4(self) -> None:
        """
        WBS 2.3.3.1.10: Model list includes GPT-4 variants.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        models = provider.get_supported_models()

        assert "gpt-4" in models
        assert "gpt-4-turbo" in models
        assert "gpt-4o" in models

    def test_get_supported_models_includes_gpt_35(self) -> None:
        """
        WBS 2.3.3.1.10: Model list includes GPT-3.5-turbo.
        """
        from src.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        models = provider.get_supported_models()

        assert "gpt-3.5-turbo" in models


# =============================================================================
# WBS 2.3.3.1.5: complete() method tests
# =============================================================================


class TestOpenAIProviderComplete:
    """Tests for complete method (non-streaming)."""

    @pytest.fixture
    def mock_openai_client(self) -> MagicMock:
        """Create a mock OpenAI client."""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample chat completion request."""
        return ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello, how are you?")],
        )

    @pytest.fixture
    def mock_openai_response(self) -> MagicMock:
        """Create a mock OpenAI API response."""
        response = MagicMock()
        response.id = "chatcmpl-123"
        response.created = 1677652288
        response.model = "gpt-4"
        response.choices = [
            MagicMock(
                index=0,
                message=MagicMock(
                    role="assistant",
                    content="I'm doing well, thank you!",
                    tool_calls=None,
                ),
                finish_reason="stop",
                logprobs=None,
            )
        ]
        response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
        )
        response.system_fingerprint = "fp_abc123"
        return response

    @pytest.mark.asyncio
    async def test_complete_returns_chat_completion_response(
        self,
        sample_request: ChatCompletionRequest,
        mock_openai_response: MagicMock,
    ) -> None:
        """
        WBS 2.3.3.1.5: complete() returns ChatCompletionResponse.
        """
        from src.providers.openai import OpenAIProvider

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            response = await provider.complete(sample_request)

            assert isinstance(response, ChatCompletionResponse)
            assert response.id == "chatcmpl-123"
            assert response.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_complete_maps_choices_correctly(
        self,
        sample_request: ChatCompletionRequest,
        mock_openai_response: MagicMock,
    ) -> None:
        """
        WBS 2.3.3.1.5: complete() maps choices from OpenAI response.
        """
        from src.providers.openai import OpenAIProvider

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            response = await provider.complete(sample_request)

            assert len(response.choices) == 1
            assert response.choices[0].index == 0
            assert response.choices[0].message.content == "I'm doing well, thank you!"
            assert response.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_maps_usage_correctly(
        self,
        sample_request: ChatCompletionRequest,
        mock_openai_response: MagicMock,
    ) -> None:
        """
        WBS 2.3.3.1.5: complete() maps usage statistics.
        """
        from src.providers.openai import OpenAIProvider

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            response = await provider.complete(sample_request)

            assert response.usage.prompt_tokens == 10
            assert response.usage.completion_tokens == 8
            assert response.usage.total_tokens == 18

    @pytest.mark.asyncio
    async def test_complete_passes_optional_parameters(
        self,
        mock_openai_response: MagicMock,
    ) -> None:
        """
        WBS 2.3.3.1.5: complete() passes temperature, max_tokens, etc.
        """
        from src.providers.openai import OpenAIProvider

        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello")],
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
        )

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_openai_response
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            await provider.complete(request)

            # Verify the call was made with correct parameters
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 100
            assert call_kwargs["top_p"] == 0.9


# =============================================================================
# WBS 2.3.3.1.7: stream() method tests
# =============================================================================


class TestOpenAIProviderStream:
    """Tests for stream method (streaming)."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample streaming request."""
        return ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

    @pytest.fixture
    def mock_stream_chunks(self) -> list[MagicMock]:
        """Create mock stream chunks."""
        chunks = []

        # First chunk with role
        chunk1 = MagicMock()
        chunk1.id = "chatcmpl-123"
        chunk1.created = 1677652288
        chunk1.model = "gpt-4"
        chunk1.choices = [
            MagicMock(
                index=0,
                delta=MagicMock(role="assistant", content=None, tool_calls=None),
                finish_reason=None,
                logprobs=None,
            )
        ]
        chunk1.system_fingerprint = "fp_abc123"
        chunks.append(chunk1)

        # Content chunks
        for content in ["Hello", " there", "!"]:
            chunk = MagicMock()
            chunk.id = "chatcmpl-123"
            chunk.created = 1677652288
            chunk.model = "gpt-4"
            chunk.choices = [
                MagicMock(
                    index=0,
                    delta=MagicMock(role=None, content=content, tool_calls=None),
                    finish_reason=None,
                    logprobs=None,
                )
            ]
            chunk.system_fingerprint = "fp_abc123"
            chunks.append(chunk)

        # Final chunk with finish_reason
        final_chunk = MagicMock()
        final_chunk.id = "chatcmpl-123"
        final_chunk.created = 1677652288
        final_chunk.model = "gpt-4"
        final_chunk.choices = [
            MagicMock(
                index=0,
                delta=MagicMock(role=None, content=None, tool_calls=None),
                finish_reason="stop",
                logprobs=None,
            )
        ]
        final_chunk.system_fingerprint = "fp_abc123"
        chunks.append(final_chunk)

        return chunks

    @pytest.mark.asyncio
    async def test_stream_yields_chat_completion_chunks(
        self,
        sample_request: ChatCompletionRequest,
        mock_stream_chunks: list[MagicMock],
    ) -> None:
        """
        WBS 2.3.3.1.7: stream() yields ChatCompletionChunk objects.
        """
        from src.providers.openai import OpenAIProvider

        async def mock_stream():
            for chunk in mock_stream_chunks:
                yield chunk

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=mock_stream()
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")

            chunks_received = []
            async for chunk in provider.stream(sample_request):
                chunks_received.append(chunk)
                assert isinstance(chunk, ChatCompletionChunk)

            assert len(chunks_received) == 5

    @pytest.mark.asyncio
    async def test_stream_preserves_chunk_id(
        self,
        sample_request: ChatCompletionRequest,
        mock_stream_chunks: list[MagicMock],
    ) -> None:
        """
        WBS 2.3.3.1.7: All chunks have same response ID.
        """
        from src.providers.openai import OpenAIProvider

        async def mock_stream():
            for chunk in mock_stream_chunks:
                yield chunk

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=mock_stream()
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")

            async for chunk in provider.stream(sample_request):
                assert chunk.id == "chatcmpl-123"

    @pytest.mark.asyncio
    async def test_stream_maps_delta_content(
        self,
        sample_request: ChatCompletionRequest,
        mock_stream_chunks: list[MagicMock],
    ) -> None:
        """
        WBS 2.3.3.1.7: stream() maps delta content correctly.
        """
        from src.providers.openai import OpenAIProvider

        async def mock_stream():
            for chunk in mock_stream_chunks:
                yield chunk

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = MagicMock(
                return_value=mock_stream()
            )
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")

            content_parts = []
            async for chunk in provider.stream(sample_request):
                if chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)

            assert content_parts == ["Hello", " there", "!"]


# =============================================================================
# WBS 2.3.3.1.11: Retry logic tests
# =============================================================================


class TestOpenAIProviderRetry:
    """Tests for retry logic with exponential backoff."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample request."""
        return ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello")],
        )

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.1.11: Retries on rate limit (429) errors.
        """
        from src.providers.openai import OpenAIProvider, RateLimitError

        call_count = 0
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1677652288
        mock_response.model = "gpt-4"
        mock_response.choices = [
            MagicMock(
                index=0,
                message=MagicMock(role="assistant", content="Success!", tool_calls=None),
                finish_reason="stop",
                logprobs=None,
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=5, completion_tokens=5, total_tokens=10
        )
        mock_response.system_fingerprint = None

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limit exceeded")
            return mock_response

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = mock_create
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key", max_retries=3, retry_delay=0.01)
            response = await provider.complete(sample_request)

            assert call_count == 3
            assert response.choices[0].message.content == "Success!"

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.1.11: Raises error when retries exhausted.
        """
        from src.providers.openai import OpenAIProvider, RateLimitError

        async def mock_create(**kwargs):
            raise RateLimitError("Rate limit exceeded")

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = mock_create
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key", max_retries=2, retry_delay=0.01)

            with pytest.raises(RateLimitError):
                await provider.complete(sample_request)

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.1.11: Does not retry on authentication errors.
        """
        from src.providers.openai import OpenAIProvider, AuthenticationError

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Invalid API key")

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = mock_create
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key", max_retries=3, retry_delay=0.01)

            with pytest.raises(AuthenticationError):
                await provider.complete(sample_request)

            # Should only be called once - no retries
            assert call_count == 1


# =============================================================================
# WBS 2.3.3.2: OpenAI Tool Handling tests
# =============================================================================


class TestOpenAIToolHandler:
    """Tests for OpenAI tool handling."""

    def test_tool_handler_class_exists(self) -> None:
        """
        WBS 2.3.3.2: OpenAIToolHandler class exists.
        """
        from src.providers.openai import OpenAIToolHandler

        handler = OpenAIToolHandler()
        assert handler is not None

    def test_validate_tool_definition_passthrough(self) -> None:
        """
        WBS 2.3.3.2.1: Tool definitions pass through unchanged.
        
        Since request models are already in OpenAI format, 
        tool handling is minimal validation/passthrough.
        """
        from src.providers.openai import OpenAIToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"],
                },
            },
        }

        handler = OpenAIToolHandler()
        validated_tool = handler.validate_tool_definition(openai_tool)

        assert validated_tool == openai_tool

    def test_parse_tool_calls_from_response(self) -> None:
        """
        WBS 2.3.3.2.2: Parse tool_calls from OpenAI response.
        """
        from src.providers.openai import OpenAIToolHandler

        tool_calls = [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco"}',
                },
            }
        ]

        handler = OpenAIToolHandler()
        parsed = handler.parse_tool_calls(tool_calls)

        assert len(parsed) == 1
        assert parsed[0]["id"] == "call_abc123"
        assert parsed[0]["function"]["name"] == "get_weather"

    def test_format_tool_message_for_request(self) -> None:
        """
        WBS 2.3.3.2.3: Format tool result message.
        """
        from src.providers.openai import OpenAIToolHandler

        handler = OpenAIToolHandler()
        message = handler.format_tool_result(
            tool_call_id="call_abc123",
            content='{"temperature": 72, "unit": "F"}',
        )

        assert message["role"] == "tool"
        assert message["tool_call_id"] == "call_abc123"
        assert message["content"] == '{"temperature": 72, "unit": "F"}'


# =============================================================================
# WBS 2.3.3.1.12: Error handling tests
# =============================================================================


class TestOpenAIProviderErrors:
    """Tests for error handling."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample request."""
        return ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello")],
        )

    @pytest.mark.asyncio
    async def test_raises_provider_error_on_api_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.1.12: Raises ProviderError on API errors.
        """
        from src.providers.openai import OpenAIProvider, ProviderError

        async def mock_create(**kwargs):
            raise Exception("API Error: Internal server error")

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = mock_create
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key", max_retries=1, retry_delay=0.01)

            with pytest.raises(ProviderError):
                await provider.complete(sample_request)

    def test_provider_error_is_importable(self) -> None:
        """
        WBS 2.3.3.1.12: ProviderError is importable.
        """
        from src.providers.openai import ProviderError

        error = ProviderError("Test error")
        assert str(error) == "Test error"

    def test_rate_limit_error_is_importable(self) -> None:
        """
        WBS 2.3.3.1.11: RateLimitError is importable.
        """
        from src.providers.openai import RateLimitError

        error = RateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"

    def test_authentication_error_is_importable(self) -> None:
        """
        WBS 2.3.3.1.11: AuthenticationError is importable.
        """
        from src.providers.openai import AuthenticationError

        error = AuthenticationError("Invalid API key")
        assert str(error) == "Invalid API key"


# =============================================================================
# Integration with tool calls in complete()
# =============================================================================


class TestOpenAIProviderToolCalls:
    """Tests for tool call handling in complete()."""

    @pytest.fixture
    def sample_request_with_tools(self) -> ChatCompletionRequest:
        """Create a request with tools."""
        from src.models.requests import Tool, FunctionDefinition

        return ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="What's the weather in SF?")],
            tools=[
                Tool(
                    type="function",
                    function=FunctionDefinition(
                        name="get_weather",
                        description="Get weather",
                        parameters={
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    ),
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_complete_handles_tool_call_response(
        self,
        sample_request_with_tools: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.2.2: complete() handles tool_calls in response.
        """
        from src.providers.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1677652288
        mock_response.model = "gpt-4"
        mock_response.choices = [
            MagicMock(
                index=0,
                message=MagicMock(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        MagicMock(
                            id="call_abc123",
                            type="function",
                            function=MagicMock(
                                name="get_weather",
                                arguments='{"location": "San Francisco"}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
                logprobs=None,
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=20, completion_tokens=15, total_tokens=35
        )
        mock_response.system_fingerprint = None

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            response = await provider.complete(sample_request_with_tools)

            assert response.choices[0].finish_reason == "tool_calls"
            assert response.choices[0].message.tool_calls is not None
            assert len(response.choices[0].message.tool_calls) == 1
            assert response.choices[0].message.tool_calls[0]["id"] == "call_abc123"

    @pytest.mark.asyncio
    async def test_complete_passes_tools_to_api(
        self,
        sample_request_with_tools: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.3.2.1: complete() passes tools to OpenAI API.
        """
        from src.providers.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.created = 1677652288
        mock_response.model = "gpt-4"
        mock_response.choices = [
            MagicMock(
                index=0,
                message=MagicMock(role="assistant", content="Response", tool_calls=None),
                finish_reason="stop",
                logprobs=None,
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )
        mock_response.system_fingerprint = None

        with patch("src.providers.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            provider = OpenAIProvider(api_key="test-key")
            await provider.complete(sample_request_with_tools)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert "tools" in call_kwargs
            assert len(call_kwargs["tools"]) == 1
            assert call_kwargs["tools"][0]["function"]["name"] == "get_weather"

