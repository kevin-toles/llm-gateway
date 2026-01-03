"""
DeepSeek Provider - WBS 2.3.6 DeepSeek Adapter

This module implements the DeepSeek provider adapter for the Reasoner model.
DeepSeek's API is OpenAI-compatible, making integration straightforward.

Reference Documents:
- ARCHITECTURE.md: Provider pattern
- https://api-docs.deepseek.com/

Design Patterns:
- Ports and Adapters: DeepSeekProvider implements LLMProvider interface
- Retry with Exponential Backoff: For rate limit and transient errors
"""

import asyncio
import time
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
# DeepSeek Configuration
# =============================================================================

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
PROVIDER_NAME = "deepseek"

SUPPORTED_MODELS = [
    # Reasoner model - best for complex reasoning tasks
    "deepseek-reasoner",
    # Chat model - general purpose
    "deepseek-chat",
    # Coder model - code generation
    "deepseek-coder",
]


class DeepSeekProvider(LLMProvider):
    """
    DeepSeek provider adapter.

    This class implements the LLMProvider interface for DeepSeek's models.
    DeepSeek uses an OpenAI-compatible API, so we can use the OpenAI client.

    The deepseek-reasoner model is particularly good at:
    - Complex reasoning tasks
    - Breaking down problems step-by-step
    - Arbitrating between different viewpoints

    Args:
        api_key: DeepSeek API key.
        max_retries: Maximum retry attempts for transient errors.
        retry_delay: Initial delay between retries (exponential backoff).

    Example:
        >>> provider = DeepSeekProvider(api_key="sk-...")
        >>> response = await provider.complete(request)
        >>> print(response.choices[0].message.content)
    """

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize DeepSeek provider.

        Args:
            api_key: DeepSeek API key.
            max_retries: Maximum retry attempts (default: 3).
            retry_delay: Initial retry delay in seconds (default: 1.0).
        """
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Initialize OpenAI-compatible client pointing to DeepSeek
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

    def get_supported_models(self) -> list[str]:
        """Return list of supported DeepSeek models."""
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
            RateLimitError: If rate limited by DeepSeek.
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
            except (AuthenticationError, ProviderError):
                raise
            except Exception as e:
                last_error = ProviderError(
                    message=f"DeepSeek API error: {e}",
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
            # Build request parameters
            params: dict[str, Any] = {
                "model": request.model,
                "messages": [m.model_dump() for m in request.messages],
            }

            # Add optional parameters
            if request.temperature is not None:
                params["temperature"] = request.temperature
            if request.max_tokens is not None:
                params["max_tokens"] = request.max_tokens
            if request.top_p is not None:
                params["top_p"] = request.top_p
            if request.stop is not None:
                params["stop"] = request.stop

            # Make the API call
            response = await self._client.chat.completions.create(**params)

            # Convert to our response format
            # Note: deepseek-reasoner returns content in 'reasoning_content' field
            choices = []
            for choice in response.choices:
                content = choice.message.content or ""
                # For reasoner model, check reasoning_content if content is empty
                if not content and hasattr(choice.message, "reasoning_content"):
                    content = getattr(choice.message, "reasoning_content", "") or ""
                
                choices.append(
                    Choice(
                        index=choice.index,
                        message=ChoiceMessage(
                            role=choice.message.role,
                            content=content,
                        ),
                        finish_reason=choice.finish_reason,
                    )
                )

            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )

            # Get created timestamp from response or use current time
            created = getattr(response, "created", None) or int(time.time())

            return ChatCompletionResponse(
                id=response.id,
                model=response.model,
                created=created,
                choices=choices,
                usage=usage,
            )

        except Exception as e:
            error_str = str(e).lower()
            if "authentication" in error_str or "api key" in error_str or "401" in error_str:
                raise AuthenticationError(
                    message=f"DeepSeek authentication failed: {e}",
                    provider=PROVIDER_NAME,
                )
            elif "rate" in error_str or "429" in error_str:
                raise RateLimitError(
                    message=f"DeepSeek rate limit exceeded: {e}",
                )
            else:
                raise ProviderError(
                    message=f"DeepSeek API error: {e}",
                    provider=PROVIDER_NAME,
                )

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Stream a chat completion request.

        Args:
            request: The chat completion request.

        Yields:
            ChatCompletionChunk objects as they arrive.
        """
        try:
            params: dict[str, Any] = {
                "model": request.model,
                "messages": [m.model_dump() for m in request.messages],
                "stream": True,
            }

            if request.temperature is not None:
                params["temperature"] = request.temperature
            if request.max_tokens is not None:
                params["max_tokens"] = request.max_tokens
            if request.top_p is not None:
                params["top_p"] = request.top_p
            if request.stop is not None:
                params["stop"] = request.stop

            stream = await self._client.chat.completions.create(**params)

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                yield ChatCompletionChunk(
                    id=chunk.id,
                    model=chunk.model,
                    choices=[
                        ChunkChoice(
                            index=0,
                            delta=ChunkDelta(
                                role=getattr(delta, "role", None),
                                content=getattr(delta, "content", None),
                            ),
                            finish_reason=chunk.choices[0].finish_reason,
                        )
                    ],
                )

        except Exception as e:
            error_str = str(e).lower()
            if "authentication" in error_str or "api key" in error_str:
                raise AuthenticationError(
                    message=f"DeepSeek authentication failed: {e}",
                    provider=PROVIDER_NAME,
                )
            elif "rate" in error_str or "429" in error_str:
                raise RateLimitError(
                    message=f"DeepSeek rate limit exceeded: {e}",
                )
            else:
                raise ProviderError(
                    message=f"DeepSeek streaming error: {e}",
                    provider=PROVIDER_NAME,
                )
