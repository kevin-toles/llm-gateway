"""
Tests for Ollama Provider - WBS 2.3.4

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 43 - ollama.py "Ollama local adapter"
- GUIDELINES pp. 2309: Timeout configuration and connection pooling
- GUIDELINES pp. 1004: Self-hosted model patterns
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Test Categories:
- WBS 2.3.4.1: Ollama Adapter Implementation
  - 2.3.4.1.2: OllamaProvider class
  - 2.3.4.1.4: complete() method
  - 2.3.4.1.8: stream() method  
  - 2.3.4.1.9: supports_model() dynamically
  - 2.3.4.1.10: list_available_models() method
  - 2.3.4.1.11: complete returns valid response (mocked)
  - 2.3.4.1.12: handles connection errors gracefully

Ollama API Reference:
- Base URL: http://localhost:11434
- Chat endpoint: POST /api/chat
- Models endpoint: GET /api/tags
- Format: Similar to OpenAI but with different field names
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator
import json

from src.models.requests import ChatCompletionRequest, Message
from src.models.responses import (
    ChatCompletionResponse,
    ChatCompletionChunk,
)


# =============================================================================
# WBS 2.3.4.1.2: OllamaProvider class tests
# =============================================================================


class TestOllamaProviderClass:
    """Tests for OllamaProvider class structure."""

    def test_ollama_provider_inherits_from_llm_provider(self) -> None:
        """
        WBS 2.3.4.1.2: OllamaProvider extends LLMProvider ABC.
        """
        from src.providers.ollama import OllamaProvider
        from src.providers.base import LLMProvider

        assert issubclass(OllamaProvider, LLMProvider)

    def test_ollama_provider_accepts_base_url(self) -> None:
        """
        WBS 2.3.4.1.3: OllamaProvider accepts base_url parameter.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434")
        assert provider is not None

    def test_ollama_provider_uses_default_url(self) -> None:
        """
        WBS 2.3.4.1.3: OllamaProvider uses default localhost URL.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        assert provider._base_url == "http://localhost:11434"

    def test_ollama_provider_accepts_timeout_config(self) -> None:
        """
        WBS 2.3.4.1.3: OllamaProvider accepts timeout configuration.
        
        Pattern: Timeout configuration (GUIDELINES pp. 2309)
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider(
            base_url="http://localhost:11434",
            timeout=60.0,
        )
        assert provider is not None


# =============================================================================
# WBS 2.3.4.1.9: supports_model() tests
# =============================================================================


class TestOllamaProviderSupportsModel:
    """Tests for supports_model method."""

    def test_supports_model_returns_true_for_available_model(self) -> None:
        """
        WBS 2.3.4.1.9: supports_model returns True for available models.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        # Set available models directly for testing
        provider._available_models = ["llama2", "mistral", "codellama"]

        assert provider.supports_model("llama2") is True
        assert provider.supports_model("mistral") is True

    def test_supports_model_returns_false_for_unavailable_model(self) -> None:
        """
        WBS 2.3.4.1.9: supports_model returns False for unavailable models.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        provider._available_models = ["llama2"]

        assert provider.supports_model("gpt-4") is False
        assert provider.supports_model("claude-3") is False

    def test_supports_model_with_empty_available_list(self) -> None:
        """
        WBS 2.3.4.1.9: supports_model handles empty model list.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        provider._available_models = []

        assert provider.supports_model("llama2") is False


# =============================================================================
# WBS 2.3.4.1.10: list_available_models() tests
# =============================================================================


class TestOllamaProviderListModels:
    """Tests for list_available_models method."""

    @pytest.mark.asyncio
    async def test_list_available_models_returns_list(self) -> None:
        """
        WBS 2.3.4.1.10: list_available_models returns list of strings.
        """
        from src.providers.ollama import OllamaProvider

        mock_response = {
            "models": [
                {"name": "llama2:latest", "size": 3826793677},
                {"name": "mistral:latest", "size": 4109865159},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            models = await provider.list_available_models()

            assert isinstance(models, list)
            assert "llama2:latest" in models
            assert "mistral:latest" in models

    @pytest.mark.asyncio
    async def test_list_available_models_handles_empty_response(self) -> None:
        """
        WBS 2.3.4.1.10: list_available_models handles empty model list.
        """
        from src.providers.ollama import OllamaProvider

        mock_response = {"models": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            models = await provider.list_available_models()

            assert models == []


# =============================================================================
# WBS 2.3.4.1.10: get_supported_models() tests
# =============================================================================


class TestOllamaProviderGetSupportedModels:
    """Tests for get_supported_models method (sync wrapper)."""

    def test_get_supported_models_returns_cached_list(self) -> None:
        """
        WBS 2.3.4.1.10: get_supported_models returns cached available models.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        provider._available_models = ["llama2", "mistral"]

        models = provider.get_supported_models()

        assert isinstance(models, list)
        assert "llama2" in models
        assert "mistral" in models

    def test_get_supported_models_returns_empty_if_not_fetched(self) -> None:
        """
        WBS 2.3.4.1.10: get_supported_models returns empty if not fetched.
        """
        from src.providers.ollama import OllamaProvider

        provider = OllamaProvider()

        models = provider.get_supported_models()

        assert models == []


# =============================================================================
# WBS 2.3.4.1.4-7: complete() method tests
# =============================================================================


class TestOllamaProviderComplete:
    """Tests for complete method (non-streaming)."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample chat completion request."""
        return ChatCompletionRequest(
            model="llama2",
            messages=[Message(role="user", content="Hello, how are you?")],
        )

    @pytest.fixture
    def mock_ollama_response(self) -> dict:
        """Create a mock Ollama API response."""
        return {
            "model": "llama2",
            "created_at": "2024-01-15T10:30:00Z",
            "message": {
                "role": "assistant",
                "content": "I'm doing well, thank you for asking!",
            },
            "done": True,
            "total_duration": 5000000000,
            "load_duration": 1000000000,
            "prompt_eval_count": 10,
            "prompt_eval_duration": 500000000,
            "eval_count": 15,
            "eval_duration": 3500000000,
        }

    @pytest.mark.asyncio
    async def test_complete_returns_chat_completion_response(
        self,
        sample_request: ChatCompletionRequest,
        mock_ollama_response: dict,
    ) -> None:
        """
        WBS 2.3.4.1.11: complete() returns ChatCompletionResponse.
        """
        from src.providers.ollama import OllamaProvider

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_ollama_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            response = await provider.complete(sample_request)

            assert isinstance(response, ChatCompletionResponse)
            assert response.model == "llama2"

    @pytest.mark.asyncio
    async def test_complete_maps_message_correctly(
        self,
        sample_request: ChatCompletionRequest,
        mock_ollama_response: dict,
    ) -> None:
        """
        WBS 2.3.4.1.7: complete() transforms response to internal format.
        """
        from src.providers.ollama import OllamaProvider

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_ollama_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            response = await provider.complete(sample_request)

            assert len(response.choices) == 1
            assert response.choices[0].message.role == "assistant"
            assert response.choices[0].message.content == "I'm doing well, thank you for asking!"

    @pytest.mark.asyncio
    async def test_complete_maps_usage_statistics(
        self,
        sample_request: ChatCompletionRequest,
        mock_ollama_response: dict,
    ) -> None:
        """
        WBS 2.3.4.1.7: complete() maps usage statistics.
        """
        from src.providers.ollama import OllamaProvider

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_ollama_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            response = await provider.complete(sample_request)

            # Ollama provides prompt_eval_count and eval_count
            assert response.usage.prompt_tokens == 10
            assert response.usage.completion_tokens == 15
            assert response.usage.total_tokens == 25

    @pytest.mark.asyncio
    async def test_complete_transforms_request_to_ollama_format(
        self,
        mock_ollama_response: dict,
    ) -> None:
        """
        WBS 2.3.4.1.5: complete() transforms request to Ollama format.
        """
        from src.providers.ollama import OllamaProvider

        request = ChatCompletionRequest(
            model="llama2",
            messages=[
                Message(role="system", content="You are helpful."),
                Message(role="user", content="Hello"),
            ],
            temperature=0.7,
            max_tokens=100,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_ollama_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            await provider.complete(request)

            # Verify the call was made with Ollama format
            call_kwargs = mock_client.post.call_args
            request_body = call_kwargs.kwargs.get("json", {})

            assert request_body["model"] == "llama2"
            assert len(request_body["messages"]) == 2
            assert request_body["options"]["temperature"] == 0.7
            assert request_body["options"]["num_predict"] == 100  # Ollama uses num_predict


# =============================================================================
# WBS 2.3.4.1.8: stream() method tests
# =============================================================================


class TestOllamaProviderStream:
    """Tests for stream method (streaming)."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample streaming request."""
        return ChatCompletionRequest(
            model="llama2",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

    @pytest.mark.asyncio
    async def test_stream_yields_chat_completion_chunks(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.4.1.8: stream() yields ChatCompletionChunk objects.
        """
        from src.providers.ollama import OllamaProvider

        # Mock streaming response lines (NDJSON format)
        stream_lines = [
            b'{"model":"llama2","created_at":"2024-01-15T10:30:00Z","message":{"role":"assistant","content":"Hello"},"done":false}\n',
            b'{"model":"llama2","created_at":"2024-01-15T10:30:00Z","message":{"role":"assistant","content":" there"},"done":false}\n',
            b'{"model":"llama2","created_at":"2024-01-15T10:30:00Z","message":{"role":"assistant","content":"!"},"done":true,"total_duration":1000000000,"prompt_eval_count":5,"eval_count":3}\n',
        ]

        async def mock_iter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.aiter_lines = mock_iter_lines
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response_obj),
                __aexit__=AsyncMock(return_value=None),
            ))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()

            chunks_received = []
            async for chunk in provider.stream(sample_request):
                chunks_received.append(chunk)
                assert isinstance(chunk, ChatCompletionChunk)

            assert len(chunks_received) == 3

    @pytest.mark.asyncio
    async def test_stream_maps_delta_content(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.4.1.8: stream() maps delta content correctly.
        """
        from src.providers.ollama import OllamaProvider

        stream_lines = [
            b'{"model":"llama2","created_at":"2024-01-15T10:30:00Z","message":{"role":"assistant","content":"Hi"},"done":false}\n',
            b'{"model":"llama2","created_at":"2024-01-15T10:30:00Z","message":{"role":"assistant","content":"!"},"done":true}\n',
        ]

        async def mock_iter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.aiter_lines = mock_iter_lines
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.stream = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response_obj),
                __aexit__=AsyncMock(return_value=None),
            ))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()

            content_parts = []
            async for chunk in provider.stream(sample_request):
                if chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)

            assert content_parts == ["Hi", "!"]


# =============================================================================
# WBS 2.3.4.1.12: Connection error handling tests
# =============================================================================


class TestOllamaProviderConnectionErrors:
    """Tests for connection error handling."""

    @pytest.fixture
    def sample_request(self) -> ChatCompletionRequest:
        """Create a sample request."""
        return ChatCompletionRequest(
            model="llama2",
            messages=[Message(role="user", content="Hello")],
        )

    @pytest.mark.asyncio
    async def test_handles_connection_refused_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.4.1.12: Handles connection errors gracefully.
        """
        from src.providers.ollama import OllamaProvider, OllamaConnectionError
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.complete(sample_request)

            assert "Connection refused" in str(exc_info.value) or "connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_timeout_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.4.1.12: Handles timeout errors gracefully.
        
        Pattern: Timeout configuration (GUIDELINES pp. 2309)
        """
        from src.providers.ollama import OllamaProvider, OllamaTimeoutError
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()

            with pytest.raises(OllamaTimeoutError) as exc_info:
                await provider.complete(sample_request)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_http_error(
        self,
        sample_request: ChatCompletionRequest,
    ) -> None:
        """
        WBS 2.3.4.1.12: Handles HTTP errors gracefully.
        """
        from src.providers.ollama import OllamaProvider, OllamaProviderError
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=mock_response,
                )
            )
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()

            with pytest.raises(OllamaProviderError):
                await provider.complete(sample_request)


# =============================================================================
# Error classes import tests
# =============================================================================


class TestOllamaProviderErrorClasses:
    """Tests for error class imports."""

    def test_provider_error_is_importable(self) -> None:
        """
        WBS 2.3.4.1.12: ProviderError is importable from core.exceptions.
        """
        from src.core.exceptions import ProviderError

        error = ProviderError("Test error", provider="ollama")
        assert "Test error" in str(error)

    def test_connection_error_is_importable(self) -> None:
        """
        WBS 2.3.4.1.12: OllamaConnectionError is importable.
        """
        from src.providers.ollama import OllamaConnectionError

        error = OllamaConnectionError("Connection failed")
        assert str(error) == "Connection failed"

    def test_timeout_error_is_importable(self) -> None:
        """
        WBS 2.3.4.1.12: OllamaTimeoutError is importable.
        """
        from src.providers.ollama import OllamaTimeoutError

        error = OllamaTimeoutError("Request timed out")
        assert str(error) == "Request timed out"


# =============================================================================
# Model refresh tests
# =============================================================================


class TestOllamaProviderModelRefresh:
    """Tests for model refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_models_updates_available_list(self) -> None:
        """
        WBS 2.3.4.1.10: refresh_models updates available models.
        """
        from src.providers.ollama import OllamaProvider

        mock_response = {
            "models": [
                {"name": "llama2:latest"},
                {"name": "codellama:latest"},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            provider = OllamaProvider()
            await provider.refresh_models()

            assert provider.supports_model("llama2:latest") is True
            assert provider.supports_model("codellama:latest") is True

