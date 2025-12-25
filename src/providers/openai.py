"""
OpenAI Provider - WBS 2.3.3 OpenAI GPT Adapter

This module implements the OpenAI GPT provider adapter, including
tool handling (passthrough since our models are already OpenAI format).

Reference Documents:
- ARCHITECTURE.md: Line 42 - openai.py "OpenAI GPT adapter"
- GUIDELINES pp. 2229: Model API patterns
- GUIDELINES pp. 2309: Circuit breaker and resilience patterns
- GUIDELINES pp. 1224: Retry logic with decorators
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.4: Import exceptions from core, don't duplicate

Design Patterns:
- Ports and Adapters: OpenAIProvider implements LLMProvider interface
- Retry with Exponential Backoff: For rate limit and transient errors
- Adapter Pattern: Transforms OpenAI SDK responses to our response models
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
# WBS 2.3.3.1.10: Supported Models
# =============================================================================


SUPPORTED_MODELS = [
    # GPT-5 variants
    "gpt-5.2",
    "gpt-5.2-pro",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    # GPT-4 variants
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    # GPT-3.5 variants
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
]


# =============================================================================
# WBS 2.3.3.2: OpenAI Tool Handler
# =============================================================================


class OpenAIToolHandler:
    """
    Handler for OpenAI tool operations.

    WBS 2.3.3.2: OpenAI Tool Handling.

    Since our request/response models are already in OpenAI format,
    this handler primarily provides validation and passthrough operations.

    Pattern: Adapter pattern (minimal transformation)
    Reference: GUIDELINES pp. 1510-1590 - Tool inventories as service registries
    """

    def validate_tool_definition(self, tool: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and passthrough OpenAI tool definition.

        WBS 2.3.3.2.1: Tool definition validation.

        Args:
            tool: OpenAI format tool definition.

        Returns:
            The same tool definition (passthrough).
        """
        # OpenAI format is native - just passthrough
        return tool

    def parse_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Parse tool_calls from OpenAI response.

        WBS 2.3.3.2.2: Parse tool_calls array.

        Args:
            tool_calls: List of tool calls from OpenAI response.

        Returns:
            Parsed tool calls (passthrough since already in correct format).
        """
        return tool_calls

    def format_tool_result(
        self,
        tool_call_id: str,
        content: str,
    ) -> dict[str, Any]:
        """
        Format tool result message for OpenAI API.

        WBS 2.3.3.2.3: Format tool result message.

        Args:
            tool_call_id: The ID of the tool call being responded to.
            content: The tool execution result.

        Returns:
            OpenAI format tool message.
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }


# =============================================================================
# WBS 2.3.3.1: OpenAI Provider
# =============================================================================


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT provider adapter.

    WBS 2.3.3.1: OpenAI Adapter Implementation.

    This class implements the LLMProvider interface for OpenAI's GPT models.
    It handles chat completions (streaming and non-streaming) with retry
    logic for transient errors.

    Pattern: Ports and Adapters (Hexagonal Architecture)
    Pattern: Retry with Exponential Backoff (GUIDELINES pp. 2309)

    Args:
        api_key: OpenAI API key.
        base_url: Optional custom endpoint URL (for Azure OpenAI or proxies).
        max_retries: Maximum retry attempts for transient errors.
        retry_delay: Initial delay between retries (exponential backoff).

    Example:
        >>> provider = OpenAIProvider(api_key="sk-...")
        >>> response = await provider.complete(request)
        >>> print(response.choices[0].message.content)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize OpenAI provider.

        WBS 2.3.3.1.4: __init__ with api_key, optional base_url.

        Args:
            api_key: OpenAI API key.
            base_url: Optional custom endpoint URL.
            max_retries: Maximum retry attempts (default: 3).
            retry_delay: Initial retry delay in seconds (default: 1.0).
        """
        self._api_key = api_key
        self._base_url = base_url
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._tool_handler = OpenAIToolHandler()

        # Initialize client
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**client_kwargs)

    # =========================================================================
    # WBS 2.3.3.1.10: Model Support Methods
    # =========================================================================

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

    # =========================================================================
    # WBS 2.3.3.1.5: complete() method
    # =========================================================================

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).

        WBS 2.3.3.1.5: Implement complete() method.

        Args:
            request: The chat completion request.

        Returns:
            ChatCompletionResponse with completion results.

        Raises:
            ProviderError: On API errors.
            RateLimitError: On rate limit errors.
            AuthenticationError: On auth errors.
        """
        # Build request kwargs
        kwargs = self._build_request_kwargs(request)
        kwargs["stream"] = False

        # Execute with retry
        response = await self._execute_with_retry(
            self._client.chat.completions.create,
            **kwargs,
        )

        # Transform response to our model
        return self._transform_response(response)

    # =========================================================================
    # WBS 2.3.3.1.7: stream() method
    # =========================================================================

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.

        WBS 2.3.3.1.7: Implement stream() method.
        WBS 2.3.3.1.13: Error handling during streaming iteration.

        Args:
            request: The chat completion request.

        Yields:
            ChatCompletionChunk objects as they arrive.

        Raises:
            ProviderError: On API errors.
            RateLimitError: On rate limit errors.
            AuthenticationError: On auth errors.
        """
        # Build request kwargs
        kwargs = self._build_request_kwargs(request)
        kwargs["stream"] = True

        # Get stream - OpenAI returns an async generator directly (not awaitable)
        stream = self._client.chat.completions.create(**kwargs)

        # Yield transformed chunks with error handling
        try:
            async for chunk in stream:
                yield self._transform_chunk(chunk)
        except Exception as e:
            # WBS 2.3.3.1.13: Handle errors during streaming same as complete()
            error_str = str(e).lower()

            # Check for authentication errors
            if (
                "authentication" in error_str
                or "api key" in error_str
                or "unauthorized" in error_str
                or "401" in error_str
            ):
                raise AuthenticationError(str(e), provider="openai") from e

            # Check for rate limit errors
            if "rate limit" in error_str or "429" in error_str:
                raise RateLimitError(str(e)) from e

            # Other errors - wrap in ProviderError
            raise ProviderError(str(e), provider="openai") from e

    # =========================================================================
    # WBS 2.3.3.1.9: supports_model() method
    # =========================================================================

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.

        WBS 2.3.3.1.9: Implement supports_model().

        Args:
            model: The model identifier.

        Returns:
            True if model is supported, False otherwise.
        """
        # Check exact match first
        if model in SUPPORTED_MODELS:
            return True

        # Check prefix match for versioned models
        return model.startswith(("gpt-5", "gpt-4", "gpt-3.5-turbo"))

    # =========================================================================
    # WBS 2.3.3.1.10: get_supported_models() method
    # =========================================================================

    def get_supported_models(self) -> list[str]:
        """
        Get the list of supported model identifiers.

        WBS 2.3.3.1.10: Implement get_supported_models().

        Returns:
            List of supported model identifiers.
        """
        return SUPPORTED_MODELS.copy()

    # =========================================================================
    # WBS 2.3.3.1.11: Retry Logic with Exponential Backoff
    # =========================================================================

    async def _execute_with_retry(
        self,
        func,
        **kwargs,
    ) -> Any:
        """
        Execute a function with retry logic and exponential backoff.

        WBS 2.3.3.1.11: Implement retry logic.

        Pattern: Exponential backoff (GUIDELINES pp. 2309)

        Args:
            func: The async function to execute.
            **kwargs: Arguments to pass to the function.

        Returns:
            The function result.

        Raises:
            RateLimitError: When retries exhausted on rate limit.
            AuthenticationError: Immediately on auth errors (no retry).
            ProviderError: On other errors after retry exhaustion.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                return await func(**kwargs)
            except Exception as e:
                error_type = self._classify_error(str(e))

                # Auth errors: don't retry
                if error_type == "auth":
                    raise AuthenticationError(str(e), provider="openai") from e

                # Preserve existing RateLimitError or create new one
                if isinstance(e, RateLimitError):
                    last_error = e
                elif error_type == "rate_limit":
                    last_error = RateLimitError(str(e))
                else:
                    last_error = ProviderError(str(e), provider="openai")

                # Wait before retry (exponential backoff)
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        # Exhausted retries
        if isinstance(last_error, RateLimitError):
            raise last_error
        raise ProviderError(
            f"Request failed after {self._max_retries} attempts: {last_error}",
            provider="openai",
        )

    # =========================================================================
    # WBS 2.3.3.1.15: Error Classification Helper
    # Extracted to reduce cognitive complexity of _execute_with_retry()
    # =========================================================================

    def _classify_error(self, error_str: str) -> str:
        """
        Classify an error string into error type.

        Extracted to reduce cognitive complexity of _execute_with_retry().

        Args:
            error_str: The error message.

        Returns:
            Error type: 'auth', 'rate_limit', or 'other'.
        """
        error_lower = error_str.lower()

        # Authentication errors
        if (
            "authentication" in error_lower
            or "api key" in error_lower
            or "unauthorized" in error_lower
        ):
            return "auth"

        # Rate limit errors
        if "rate limit" in error_lower or "429" in error_lower:
            return "rate_limit"

        return "other"

    # =========================================================================
    # WBS 2.3.3.1.16: Message Transformation Helper
    # Extracted to reduce cognitive complexity of _build_request_kwargs()
    # =========================================================================

    def _transform_message(self, msg: Any) -> dict[str, Any]:
        """
        Transform a Message object to dict format for API call.

        Extracted to reduce cognitive complexity of _build_request_kwargs().

        Args:
            msg: The Message object.

        Returns:
            Dict format message.
        """
        msg_dict: dict[str, Any] = {"role": msg.role}

        if msg.content is not None:
            msg_dict["content"] = msg.content
        if msg.name is not None:
            msg_dict["name"] = msg.name
        if msg.tool_calls is not None:
            msg_dict["tool_calls"] = msg.tool_calls
        if msg.tool_call_id is not None:
            msg_dict["tool_call_id"] = msg.tool_call_id

        return msg_dict

    # =========================================================================
    # WBS 2.3.3.1.17: Optional Parameters Helper
    # Extracted to reduce cognitive complexity of _build_request_kwargs()
    # =========================================================================

    def _build_optional_params(
        self, request: ChatCompletionRequest, model: str | None = None
    ) -> dict[str, Any]:
        """
        Build optional parameters dict from request.

        Extracted to reduce cognitive complexity of _build_request_kwargs().

        Args:
            request: The chat completion request.
            model: The model name (for parameter name detection).

        Returns:
            Dict of optional parameters.
        """
        params: dict[str, Any] = {}

        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            # GPT-5.x models use max_completion_tokens instead of max_tokens
            model_name = model or request.model
            if model_name and model_name.startswith("gpt-5"):
                params["max_completion_tokens"] = request.max_tokens
            else:
                params["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            params["top_p"] = request.top_p
        if request.n is not None:
            params["n"] = request.n
        if request.stop is not None:
            params["stop"] = request.stop
        if request.presence_penalty is not None:
            params["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            params["frequency_penalty"] = request.frequency_penalty
        if request.seed is not None:
            params["seed"] = request.seed
        if request.user is not None:
            params["user"] = request.user

        return params

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_request_kwargs(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """
        Build kwargs for OpenAI API call from request.

        Args:
            request: The chat completion request.

        Returns:
            Dict of kwargs for the API call.
        """
        # Convert messages to dict format using helper
        messages = [self._transform_message(msg) for msg in request.messages]

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }

        # Add optional parameters using helper
        kwargs.update(self._build_optional_params(request))

        # Handle tools
        if request.tools:
            kwargs["tools"] = self._build_tools_list(request.tools)
        if request.tool_choice is not None:
            kwargs["tool_choice"] = request.tool_choice

        return kwargs

    def _build_tools_list(self, tools: list[Any]) -> list[dict[str, Any]]:
        """
        Build tools list from request tools.

        Extracted to reduce cognitive complexity of _build_request_kwargs().

        Args:
            tools: List of Tool objects.

        Returns:
            List of tool dicts for API call.
        """
        return [
            {
                "type": tool.type,
                "function": {
                    "name": tool.function.name,
                    **(
                        {"description": tool.function.description}
                        if tool.function.description
                        else {}
                    ),
                    **(
                        {"parameters": tool.function.parameters} if tool.function.parameters else {}
                    ),
                },
            }
            for tool in tools
        ]

    def _transform_response(self, response: Any) -> ChatCompletionResponse:
        """
        Transform OpenAI response to our response model.

        Args:
            response: The OpenAI API response.

        Returns:
            ChatCompletionResponse model.
        """
        choices = []
        for choice in response.choices:
            # Handle tool_calls
            tool_calls = None
            if choice.message.tool_calls:
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
                        content=choice.message.content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=choice.finish_reason,
                    logprobs=choice.logprobs,
                )
            )

        return ChatCompletionResponse(
            id=response.id,
            object="chat.completion",
            created=response.created,
            model=response.model,
            choices=choices,
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            system_fingerprint=response.system_fingerprint,
        )

    def _transform_chunk(self, chunk: Any) -> ChatCompletionChunk:
        """
        Transform OpenAI stream chunk to our chunk model.

        Args:
            chunk: The OpenAI API stream chunk.

        Returns:
            ChatCompletionChunk model.
        """
        choices = []
        for choice in chunk.choices:
            # Handle delta
            delta = choice.delta
            tool_calls = None
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                tool_calls = [
                    {
                        "id": getattr(tc, "id", None),
                        "type": getattr(tc, "type", None),
                        "function": {
                            "name": getattr(tc.function, "name", None) if tc.function else None,
                            "arguments": getattr(tc.function, "arguments", None)
                            if tc.function
                            else None,
                        },
                    }
                    for tc in delta.tool_calls
                ]

            choices.append(
                ChunkChoice(
                    index=choice.index,
                    delta=ChunkDelta(
                        role=getattr(delta, "role", None),
                        content=getattr(delta, "content", None),
                        tool_calls=tool_calls,
                    ),
                    finish_reason=choice.finish_reason,
                    logprobs=getattr(choice, "logprobs", None),
                )
            )

        return ChatCompletionChunk(
            id=chunk.id,
            object="chat.completion.chunk",
            created=chunk.created,
            model=chunk.model,
            choices=choices,
            system_fingerprint=getattr(chunk, "system_fingerprint", None),
        )
