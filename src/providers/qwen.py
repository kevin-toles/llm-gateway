"""
Qwen Provider - Qwen DashScope API Adapter (Alibaba Cloud)

This module implements the Qwen provider adapter for Alibaba Cloud's
DashScope API. The DashScope API is OpenAI-compatible, making integration
straightforward.

Reference Documents:
- ARCHITECTURE.md: Provider pattern
- https://help.aliyun.com/zh/model-studio/getting-started/models
- Qwen models: qwen-turbo, qwen-plus, qwen-max

Design Patterns:
- Ports and Adapters: QwenProvider implements LLMProvider interface
- Retry with Exponential Backoff: For rate limit and transient errors
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from src.core.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
)
from src.models.requests import ChatCompletionRequest
from src.models.responses import (
    ChatCompletionChunk,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    ChunkDelta,
    Usage,
)
from src.providers.base import LLMProvider

# =============================================================================
# Qwen Configuration
# =============================================================================

QWEN_BASE_URL = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
PROVIDER_NAME = "qwen"

SUPPORTED_MODELS = [
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-turbo-1101",
    "qwen-plus-1127",
]


class QwenProvider(LLMProvider):
    """
    Qwen provider adapter for Alibaba Cloud DashScope API.

    This class implements the LLMProvider interface for Qwen models via
    the DashScope API, which is OpenAI-compatible.

    Supported models:
    - qwen-turbo: Fast, cost-effective for simple tasks
    - qwen-plus: Balanced performance and cost
    - qwen-max: Highest quality, best for complex reasoning

    Args:
        api_key: Qwen DashScope API key.
        max_retries: Maximum retry attempts for transient errors.
        retry_delay: Initial delay between retries (exponential backoff).
    """

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize Qwen provider.

        Args:
            api_key: Qwen DashScope API key.
            max_retries: Maximum retry attempts (default: 3).
            retry_delay: Initial retry delay in seconds (default: 1.0).
        """
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Initialize OpenAI-compatible client pointing to DashScope
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=QWEN_BASE_URL,
        )

    def get_supported_models(self) -> list[str]:
        """Return list of supported Qwen models."""
        return list(SUPPORTED_MODELS)

    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model."""
        model_lower = model.lower()
        return any(
            model_lower == m or model_lower.startswith(m)
            for m in SUPPORTED_MODELS
        )

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """
        Execute a chat completion request.

        Args:
            request: The chat completion request.

        Returns:
            ChatCompletionResponse with the model's response.

        Raises:
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limited by DashScope.
            ProviderError: For other API errors.
        """
        return await self._complete_with_retry(request)

    async def _complete_with_retry(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute completion with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                return await self._do_complete(request)
            except RateLimitError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except ProviderError:
                raise
            except Exception as e:
                last_error = ProviderError(
                    message=f"Qwen API error: {e}",
                    provider=PROVIDER_NAME,
                )
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise last_error or ProviderError(
            message="Unknown error during completion",
            provider=PROVIDER_NAME,
        )

    async def _do_complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute the actual completion request."""
        try:
            params = self._build_request_params(request)
            response = await self._client.chat.completions.create(**params)
            return self._build_completion_response(response)

        except Exception as e:
            self._raise_appropriate_error(e)

    def _build_request_params(
        self, request: ChatCompletionRequest, stream: bool = False
    ) -> dict[str, Any]:
        """Build request parameters for the API call."""
        params: dict[str, Any] = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
        }
        if stream:
            params["stream"] = True
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            params["top_p"] = request.top_p
        return params

    def _build_completion_response(
        self,
        response: Any,
    ) -> ChatCompletionResponse:
        """Build ChatCompletionResponse from API response."""
        choice = response.choices[0]
        created = getattr(response, "created", None)
        if created is None:
            import time
            created = int(time.time())
        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            created=created,
            choices=[
                Choice(
                    index=choice.index,
                    message=ChoiceMessage(
                        role=choice.message.role,
                        content=choice.message.content or "",
                    ),
                    finish_reason=choice.finish_reason or "stop",
                )
            ],
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            ),
        )

    def _raise_appropriate_error(self, error: Exception) -> None:
        """Raise appropriate error type based on the exception."""
        error_str = str(error).lower()

        if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str or "401" in error_str or "invalid api_key" in error_str:
            raise AuthenticationError(str(error), provider=PROVIDER_NAME) from error

        if "rate limit" in error_str or "429" in error_str or "too many requests" in error_str:
            raise RateLimitError(str(error)) from error

        raise ProviderError(str(error), provider=PROVIDER_NAME) from error

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Stream a chat completion response.

        Args:
            request: The chat completion request.

        Yields:
            ChatCompletionChunk objects as they arrive.
        """
        async for chunk in self._stream_with_retry(request):
            yield chunk

    async def _stream_with_retry(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Execute streaming completion with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                params = self._build_request_params(request, stream=True)
                stream_response = await self._client.chat.completions.create(**params)

                async for chunk in stream_response:
                    yield self._transform_chunk(chunk)

                return  # Stream completed successfully
            except RateLimitError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except ProviderError:
                raise
            except Exception as e:
                self._raise_appropriate_error(e)

        if last_error:
            raise last_error

    def _transform_chunk(self, chunk: Any) -> ChatCompletionChunk:
        """Transform an API streaming chunk to our format."""
        delta = chunk.choices[0].delta if chunk.choices else None
        return ChatCompletionChunk(
            id=chunk.id,
            model=chunk.model,
            choices=[
                ChunkChoice(
                    index=chunk.choices[0].index if chunk.choices else 0,
                    delta=ChunkDelta(
                        role=delta.role if delta else None,
                        content=delta.content if delta else None,
                    ),
                    finish_reason=chunk.choices[0].finish_reason if chunk.choices else None,
                )
            ],
        )
