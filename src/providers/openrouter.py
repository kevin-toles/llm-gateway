"""
OpenRouter Provider - OpenRouter API Adapter

This module implements the OpenRouter provider adapter, which provides
access to multiple LLM models through a unified OpenAI-compatible API.

OpenRouter is used as a **stub/POC** for future local LLM servers.
When local LLMs are deployed on dedicated hardware, they will expose
OpenAI-compatible APIs and route through llm-gateway the same way.

Reference Documents:
- INTER_AI_ORCHESTRATION.md: OpenRouter as POC for local LLMs
- OpenRouter API: https://openrouter.ai/docs

Design Pattern:
- OpenRouter uses OpenAI-compatible API format
- Minimal adaptation needed - reuses OpenAI request/response patterns
"""

import asyncio
import logging
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

logger = logging.getLogger(__name__)

# =============================================================================
# Supported Models via OpenRouter
# =============================================================================

SUPPORTED_MODELS = [
    # Qwen models (primary for POC)
    "qwen/qwen3-coder",
    "qwen/qwen-2.5-coder-32b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    # Llama models
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-8b-instruct",
    # Mistral models
    "mistralai/mistral-large-2411",
    "mistralai/codestral-2501",
    # DeepSeek models
    "deepseek/deepseek-chat",
    "deepseek/deepseek-coder",
]


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter provider implementation.
    
    Uses OpenAI-compatible API to access various LLM models through OpenRouter.
    This serves as a POC/stub for future local LLM integration.
    
    When local LLM servers are deployed:
    1. They will expose OpenAI-compatible endpoints
    2. They will be accessed through llm-gateway
    3. The pattern established here will be reused
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        max_retries: int = 3,
        timeout: float = 120.0,
    ) -> None:
        """Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (OPENROUTER_API_KEY from env).
            base_url: OpenRouter API base URL.
            max_retries: Maximum number of retry attempts.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._max_retries = max_retries
        self._timeout = timeout
        
        # Initialize AsyncOpenAI client with OpenRouter base URL
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        logger.info(f"Initialized OpenRouterProvider with base_url={base_url}")

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.

        Args:
            model: The model identifier.

        Returns:
            True if supported, False otherwise.
        """
        model_lower = model.lower()
        return any(model_lower.startswith(m.lower()) for m in SUPPORTED_MODELS)

    def get_supported_models(self) -> list[str]:
        """
        Get the list of supported model identifiers.

        Returns:
            List of supported model identifiers.
        """
        return SUPPORTED_MODELS.copy()

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).
        
        Args:
            request: The chat completion request.
            
        Returns:
            ChatCompletionResponse with the model's response.
            
        Raises:
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limited by OpenRouter.
            ProviderError: For other API errors.
        """
        try:
            # Build request parameters
            params = self._build_request_params(request)
            
            # Make API call
            response = await self._client.chat.completions.create(**params)
            
            # Transform to our response format
            return self._transform_response(response, request.model)
            
        except Exception as e:
            raise self._handle_error(e) from e

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate streaming chat completion chunks.
        
        Args:
            request: The chat completion request.
            
        Yields:
            ChatCompletionChunk objects as they arrive.
            
        Raises:
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limited.
            ProviderError: For other API errors.
        """
        try:
            # Build request parameters with streaming enabled
            params = self._build_request_params(request)
            params["stream"] = True
            
            # Create streaming response
            stream = await self._client.chat.completions.create(**params)
            
            async for chunk in stream:
                yield self._transform_chunk(chunk, request.model)
                
        except Exception as e:
            raise self._handle_error(e) from e

    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model.
        
        Args:
            model: The model identifier to check.
            
        Returns:
            True if the model is supported, False otherwise.
        """
        # Support models in our list or any model with openrouter prefix
        return model in SUPPORTED_MODELS or model.startswith("openrouter/")

    def get_supported_models(self) -> list[str]:
        """Get list of supported model identifiers.
        
        Returns:
            List of model names this provider supports.
        """
        return SUPPORTED_MODELS.copy()

    def _build_request_params(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """Build OpenAI-format request parameters.
        
        Args:
            request: Our ChatCompletionRequest.
            
        Returns:
            Dictionary of parameters for OpenAI API.
        """
        # Convert messages to dict format
        messages = [msg.model_dump() for msg in request.messages]
        
        params: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        
        # Optional parameters - set sensible default for max_tokens to avoid credit issues
        if request.temperature is not None:
            params["temperature"] = request.temperature
        # Default max_tokens to 4096 for OpenRouter to avoid hitting credit limits
        params["max_tokens"] = request.max_tokens if request.max_tokens is not None else 4096
        if request.top_p is not None:
            params["top_p"] = request.top_p
        if request.stop is not None:
            params["stop"] = request.stop
        if request.tools is not None:
            params["tools"] = [tool.model_dump() for tool in request.tools]
        if request.tool_choice is not None:
            params["tool_choice"] = request.tool_choice
            
        return params

    def _transform_response(
        self,
        response: Any,
        model: str,
    ) -> ChatCompletionResponse:
        """Transform OpenAI response to our format.
        
        Args:
            response: OpenAI API response object.
            model: The model that was used.
            
        Returns:
            ChatCompletionResponse in our format.
        """
        choices = []
        for choice in response.choices:
            # Handle tool calls if present
            tool_calls = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]
            
            choices.append(
                Choice(
                    index=choice.index,
                    message=ChoiceMessage(
                        role=choice.message.role,
                        content=choice.message.content or "",
                        tool_calls=tool_calls,
                    ),
                    finish_reason=choice.finish_reason,
                )
            )
        
        # Build usage info
        usage = None
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        
        return ChatCompletionResponse(
            id=response.id,
            object="chat.completion",
            created=response.created,
            model=model,
            choices=choices,
            usage=usage,
        )

    def _transform_chunk(
        self,
        chunk: Any,
        model: str,
    ) -> ChatCompletionChunk:
        """Transform streaming chunk to our format.
        
        Args:
            chunk: OpenAI streaming chunk.
            model: The model being used.
            
        Returns:
            ChatCompletionChunk in our format.
        """
        choices = []
        for choice in chunk.choices:
            delta_content = None
            delta_role = None
            delta_tool_calls = None
            
            if hasattr(choice, "delta"):
                if hasattr(choice.delta, "content"):
                    delta_content = choice.delta.content
                if hasattr(choice.delta, "role"):
                    delta_role = choice.delta.role
                if hasattr(choice.delta, "tool_calls") and choice.delta.tool_calls:
                    delta_tool_calls = [
                        {
                            "id": tc.id if hasattr(tc, "id") else None,
                            "type": tc.type if hasattr(tc, "type") else None,
                            "function": {
                                "name": tc.function.name if hasattr(tc.function, "name") else None,
                                "arguments": tc.function.arguments if hasattr(tc.function, "arguments") else None,
                            },
                        }
                        for tc in choice.delta.tool_calls
                    ]
            
            choices.append(
                ChunkChoice(
                    index=choice.index,
                    delta=ChunkDelta(
                        role=delta_role,
                        content=delta_content,
                        tool_calls=delta_tool_calls,
                    ),
                    finish_reason=choice.finish_reason,
                )
            )
        
        return ChatCompletionChunk(
            id=chunk.id,
            object="chat.completion.chunk",
            created=chunk.created,
            model=model,
            choices=choices,
        )

    def _handle_error(self, error: Exception) -> Exception:
        """Convert OpenAI errors to our exception types.
        
        Args:
            error: The original exception.
            
        Returns:
            Appropriate exception type for our system.
        """
        error_str = str(error).lower()
        
        if "authentication" in error_str or "api key" in error_str or "401" in error_str:
            return AuthenticationError(f"OpenRouter authentication failed: {error}")
        elif "rate limit" in error_str or "429" in error_str:
            return RateLimitError(f"OpenRouter rate limited: {error}")
        else:
            return ProviderError(message=f"OpenRouter error: {error}", provider="openrouter")
