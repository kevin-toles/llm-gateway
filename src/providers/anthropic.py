"""
Anthropic Provider - WBS 2.3.2 Anthropic Claude Adapter

This module implements the Anthropic Claude provider adapter, including
tool handling for transformation between OpenAI and Anthropic formats.

Reference Documents:
- ARCHITECTURE.md: Line 41 - anthropic.py "Anthropic Claude adapter"
- ARCHITECTURE.md: Lines 209-213 - Tool-Use Orchestrator patterns
- GUIDELINES pp. 215: Provider abstraction for model swapping
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES pp. 1510-1590: Tool patterns and agent architectures
- GUIDELINES pp. 2229: Model API patterns
- Anthropic API Docs: tool_use/tool_result content block format
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Format Differences (OpenAI → Anthropic):
- Tool definition: function.parameters → input_schema
- Tool use response: tool_calls[] → content blocks type="tool_use"
- Tool result: role="tool" → role="user" with type="tool_result"
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

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
# WBS 2.3.2.1.7: Supported Models
# =============================================================================


SUPPORTED_MODELS = [
    # Claude 4 variants
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    # Claude 3.5 variants
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    # Claude 3 variants
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    # Claude 2 variants (legacy)
    "claude-2.1",
    "claude-2.0",
    # Claude Instant (legacy)
    "claude-instant-1.2",
]


# =============================================================================
# WBS 2.3.2.2: Anthropic Tool Handler
# =============================================================================


class AnthropicToolHandler:
    """
    Handler for transforming tools between OpenAI and Anthropic formats.

    WBS 2.3.2.2: Anthropic Tool Handling.

    This class provides methods to:
    - Transform OpenAI tool definitions to Anthropic format (2.3.2.2.1)
    - Parse Anthropic tool_use responses to OpenAI format (2.3.2.2.2)
    - Format tool results for Anthropic API (2.3.2.2.3)

    Pattern: Adapter pattern for format transformation
    Reference: GUIDELINES pp. 1510-1590 - Tool inventories as service registries

    Example:
        >>> handler = AnthropicToolHandler()
        >>> anthropic_tools = handler.transform_tools(openai_tools)
        >>> tool_calls = handler.parse_tool_use_response(content_blocks)
    """

    # =========================================================================
    # WBS 2.3.2.2.1: Tool Definition Transformation
    # =========================================================================

    def transform_tool_definition(self, openai_tool: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single OpenAI tool definition to Anthropic format.

        WBS 2.3.2.2.1: Implement tool definition transformation.

        Args:
            openai_tool: OpenAI format tool definition with structure:
                {
                    "type": "function",
                    "function": {
                        "name": str,
                        "description": Optional[str],
                        "parameters": Optional[dict]
                    }
                }

        Returns:
            Anthropic format tool definition:
                {
                    "name": str,
                    "description": Optional[str],
                    "input_schema": dict
                }

        Pattern: Adapter transformation (GUIDELINES pp. 1510-1590)
        """
        function_def = openai_tool.get("function", {})

        anthropic_tool: dict[str, Any] = {
            "name": function_def.get("name", ""),
            "input_schema": function_def.get("parameters", {"type": "object", "properties": {}}),
        }

        # Handle optional description - Pattern: Optional[T] (ANTI_PATTERN §1.1)
        description = function_def.get("description")
        if description:
            anthropic_tool["description"] = description

        # Ensure input_schema has required structure
        if "type" not in anthropic_tool["input_schema"]:
            anthropic_tool["input_schema"]["type"] = "object"
        if "properties" not in anthropic_tool["input_schema"]:
            anthropic_tool["input_schema"]["properties"] = {}

        return anthropic_tool

    def transform_tools(self, openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Transform a list of OpenAI tools to Anthropic format.

        WBS 2.3.2.2.1: Batch tool transformation.

        Args:
            openai_tools: List of OpenAI format tool definitions.

        Returns:
            List of Anthropic format tool definitions.
        """
        return [self.transform_tool_definition(tool) for tool in openai_tools]

    # =========================================================================
    # WBS 2.3.2.2.2: Tool Use Response Parsing
    # =========================================================================

    def parse_tool_use_response(self, content_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Parse Anthropic tool_use content blocks to OpenAI tool_calls format.

        WBS 2.3.2.2.2: Implement tool_use response parsing.

        Args:
            content_blocks: Anthropic response content array with structure:
                [
                    {"type": "text", "text": str},
                    {
                        "type": "tool_use",
                        "id": str,
                        "name": str,
                        "input": dict
                    }
                ]

        Returns:
            OpenAI format tool_calls array:
                [
                    {
                        "id": str,
                        "type": "function",
                        "function": {
                            "name": str,
                            "arguments": str (JSON)
                        }
                    }
                ]

        Pattern: Content block filtering and transformation
        """
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_call = {
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                }
                tool_calls.append(tool_call)

        return tool_calls

    def extract_text_content(self, content_blocks: list[dict[str, Any]]) -> str:
        """
        Extract text content from Anthropic content blocks.

        WBS 2.3.2.2.2: Extract text alongside tool uses.

        Args:
            content_blocks: Anthropic response content array.

        Returns:
            Concatenated text content from text blocks.
        """
        text_parts: list[str] = []

        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    text_parts.append(text)

        return " ".join(text_parts) if text_parts else ""

    # =========================================================================
    # WBS 2.3.2.2.3: Tool Result Message Formatting
    # =========================================================================

    def format_tool_result(
        self,
        tool_use_id: str,
        content: str,
        is_error: bool = False,
    ) -> dict[str, Any]:
        """
        Format a single tool result content block.

        WBS 2.3.2.2.3: Implement tool_result message formatting.

        Args:
            tool_use_id: The ID from the original tool_use block.
            content: The tool execution result (string or JSON string).
            is_error: Whether the result represents an error.

        Returns:
            Anthropic tool_result content block:
                {
                    "type": "tool_result",
                    "tool_use_id": str,
                    "content": str,
                    "is_error": Optional[bool]
                }

        Pattern: Content block construction for continuation
        """
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
        }

        if is_error:
            result["is_error"] = True

        return result

    def format_tool_result_message(self, openai_tool_message: dict[str, Any]) -> dict[str, Any]:
        """
        Transform OpenAI tool message to Anthropic user message with tool_result.

        WBS 2.3.2.2.3: Transform single tool result message.

        Args:
            openai_tool_message: OpenAI format tool message:
                {
                    "role": "tool",
                    "tool_call_id": str,
                    "content": str
                }

        Returns:
            Anthropic format user message with tool_result:
                {
                    "role": "user",
                    "content": [{"type": "tool_result", ...}]
                }

        Note: Anthropic requires tool results in user messages.
        """
        tool_result = self.format_tool_result(
            tool_use_id=openai_tool_message.get("tool_call_id", ""),
            content=openai_tool_message.get("content", ""),
        )

        return {"role": "user", "content": [tool_result]}

    def format_tool_results(self, openai_tool_messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Transform multiple OpenAI tool messages to single Anthropic message.

        WBS 2.3.2.2.3: Batch tool result formatting.

        Args:
            openai_tool_messages: List of OpenAI format tool messages.

        Returns:
            Single Anthropic user message with multiple tool_result blocks.

        Note: Anthropic expects all tool results in a single user message.
        """
        tool_results: list[dict[str, Any]] = []

        for msg in openai_tool_messages:
            tool_result = self.format_tool_result(
                tool_use_id=msg.get("tool_call_id", ""),
                content=msg.get("content", ""),
            )
            tool_results.append(tool_result)

        return {"role": "user", "content": tool_results}


# =============================================================================
# WBS 2.3.2.1: Anthropic Provider
# =============================================================================


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider adapter.

    WBS 2.3.2.1: Anthropic Adapter Implementation.

    This class implements the LLMProvider interface for Anthropic's Claude models.
    It handles chat completions (streaming and non-streaming) with retry
    logic for transient errors.

    Pattern: Ports and Adapters (Hexagonal Architecture)
    Pattern: Retry with Exponential Backoff (GUIDELINES pp. 2309)
    Reference: GUIDELINES pp. 215 - Provider abstraction for model swapping

    Args:
        api_key: Anthropic API key.
        max_retries: Maximum retry attempts for transient errors.
        retry_delay: Initial delay between retries (exponential backoff).

    Example:
        >>> provider = AnthropicProvider(api_key="sk-ant-...")
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
        Initialize Anthropic provider.

        WBS 2.3.2.1.3: __init__ with api_key parameter.

        Args:
            api_key: Anthropic API key.
            max_retries: Maximum retry attempts (default: 3).
            retry_delay: Initial retry delay in seconds (default: 1.0).
        """
        self._api_key = api_key
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._tool_handler = AnthropicToolHandler()
        self._client = AsyncAnthropic(api_key=api_key)

    # =========================================================================
    # WBS 2.3.2.1.7: Model Support Methods
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
    # WBS 2.3.2.1.4: complete() method
    # =========================================================================

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).

        WBS 2.3.2.1.4: Implement complete() method.

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

        # Execute with retry
        response = await self._execute_with_retry(
            self._client.messages.create,
            **kwargs,
        )

        # Transform response to our model
        return self._transform_response(response)

    # =========================================================================
    # WBS 2.3.2.1.5: stream() method
    # =========================================================================

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.

        WBS 2.3.2.1.5: Implement stream() method.

        Args:
            request: The chat completion request.

        Yields:
            ChatCompletionChunk objects as they arrive.

        Raises:
            ProviderError: On API errors.
            RateLimitError: On rate limit errors.
            AuthenticationError: On auth errors.
        """
        kwargs = self._build_request_kwargs(request)

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                message_id: str | None = None
                model: str | None = None

                async for event in stream:
                    if event.type == "message_start":
                        message_id, model = self._handle_message_start(event)
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield self._handle_content_delta(
                                event,
                                message_id or "unknown",
                                model or request.model,
                            )
                    elif event.type == "message_delta":
                        yield self._handle_message_delta(
                            event,
                            message_id or "unknown",
                            model or request.model,
                        )
        except Exception as e:
            self._handle_error(e)

    # =========================================================================
    # WBS 2.3.2.1.6: supports_model() method
    # =========================================================================

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.

        WBS 2.3.2.1.6: Implement supports_model().

        Args:
            model: The model identifier.

        Returns:
            True if model is supported, False otherwise.
        """
        # Check exact match first
        if model in SUPPORTED_MODELS:
            return True

        # Check prefix match for Claude models
        return model.startswith("claude-")

    # =========================================================================
    # WBS 2.3.2.1.7: get_supported_models() method
    # =========================================================================

    def get_supported_models(self) -> list[str]:
        """
        Get the list of supported model identifiers.

        WBS 2.3.2.1.7: Implement get_supported_models().

        Returns:
            List of supported model identifiers.
        """
        return SUPPORTED_MODELS.copy()

    # =========================================================================
    # WBS 2.3.2.1.8: Retry Logic with Exponential Backoff
    # =========================================================================

    async def _execute_with_retry(
        self,
        func,
        **kwargs,
    ) -> Any:
        """
        Execute a function with retry logic and exponential backoff.

        WBS 2.3.2.1.8: Implement retry logic.

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
                    raise AuthenticationError(str(e), provider="anthropic") from e

                # Rate limit errors: retry with RateLimitError
                if error_type == "rate_limit":
                    last_error = RateLimitError(str(e))
                else:
                    # Other errors: wrap and retry
                    last_error = ProviderError(str(e), provider="anthropic")

                # Wait before retry (exponential backoff)
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        # Exhausted retries
        if isinstance(last_error, RateLimitError):
            raise last_error
        raise ProviderError(
            f"Request failed after {self._max_retries} attempts: {last_error}",
            provider="anthropic",
        )

    # =========================================================================
    # WBS 2.3.2.1.9: Error Handling
    # =========================================================================

    def _classify_error(self, error_str: str) -> str:
        """
        Classify an error string into error type.

        Extracted to reduce cognitive complexity of _execute_with_retry().

        Args:
            error_str: The error message (lowercase).

        Returns:
            Error type: 'auth', 'rate_limit', or 'other'.
        """
        error_lower = error_str.lower()

        # Authentication errors
        if (
            "authentication" in error_lower
            or "api key" in error_lower
            or "unauthorized" in error_lower
            or "invalid_api_key" in error_lower
        ):
            return "auth"

        # Rate limit errors
        if "rate limit" in error_lower or "429" in error_lower:
            return "rate_limit"

        return "other"

    def _handle_error(self, e: Exception) -> None:
        """
        Handle and re-raise errors with appropriate types.

        WBS 2.3.2.1.9: Error handling.

        Args:
            e: The exception to handle.

        Raises:
            AuthenticationError: For auth errors.
            RateLimitError: For rate limit errors.
            ProviderError: For other errors.
        """
        error_type = self._classify_error(str(e))

        if error_type == "auth":
            raise AuthenticationError(str(e), provider="anthropic") from e

        if error_type == "rate_limit":
            raise RateLimitError(str(e)) from e

        raise ProviderError(str(e), provider="anthropic") from e

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_request_kwargs(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """
        Build kwargs for Anthropic API call from request.

        Args:
            request: The chat completion request.

        Returns:
            Dict of kwargs for the API call.
        """
        # Transform messages to Anthropic format
        messages = self._transform_messages(request.messages)

        # Extract system message if present
        system: str | None = None
        if messages and messages[0].get("role") == "system":
            system = messages[0].get("content", "")
            messages = messages[1:]

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
        }

        if system:
            kwargs["system"] = system

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        if request.top_p is not None:
            kwargs["top_p"] = request.top_p

        # Transform tools if present
        if request.tools:
            kwargs["tools"] = self._tool_handler.transform_tools(
                [t.model_dump() for t in request.tools]
            )

        return kwargs

    # =========================================================================
    # Stream Event Handlers - Extracted for Complexity Reduction
    # =========================================================================

    def _handle_message_start(self, event: Any) -> tuple[str, str]:
        """
        Handle message_start event from Anthropic stream.

        Extracted to reduce cognitive complexity of stream().

        Args:
            event: The message_start event.

        Returns:
            Tuple of (message_id, model).
        """
        return event.message.id, event.message.model

    def _handle_content_delta(
        self,
        event: Any,
        message_id: str,
        model: str,
    ) -> ChatCompletionChunk:
        """
        Handle content_block_delta event from Anthropic stream.

        Extracted to reduce cognitive complexity of stream().

        Args:
            event: The content_block_delta event.
            message_id: The message ID from message_start.
            model: The model name.

        Returns:
            ChatCompletionChunk with content delta.
        """
        return ChatCompletionChunk(
            id=message_id,
            model=model,
            created=int(time.time()),
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(
                        role="assistant",
                        content=event.delta.text,
                    ),
                    finish_reason=None,
                )
            ],
        )

    def _handle_message_delta(
        self,
        event: Any,
        message_id: str,
        model: str,
    ) -> ChatCompletionChunk:
        """
        Handle message_delta event from Anthropic stream.

        Extracted to reduce cognitive complexity of stream().

        Args:
            event: The message_delta event.
            message_id: The message ID from message_start.
            model: The model name.

        Returns:
            ChatCompletionChunk with finish_reason.
        """
        finish_reason = None
        if hasattr(event.delta, "stop_reason"):
            stop_reason = event.delta.stop_reason
            finish_reason = "stop" if stop_reason == "end_turn" else stop_reason

        return ChatCompletionChunk(
            id=message_id,
            model=model,
            created=int(time.time()),
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(),
                    finish_reason=finish_reason,
                )
            ],
        )

    # =========================================================================
    # Message Transform Helpers - Extracted for Complexity Reduction
    # =========================================================================

    def _transform_tool_message(self, msg_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a tool message to Anthropic format.

        Extracted to reduce cognitive complexity of _transform_messages().

        Args:
            msg_dict: The tool message dict.

        Returns:
            Anthropic-format tool result message.
        """
        return self._tool_handler.format_tool_result_message(msg_dict)

    def _transform_assistant_tool_message(self, msg_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Transform an assistant message with tool_calls to Anthropic format.

        Extracted to reduce cognitive complexity of _transform_messages().

        Args:
            msg_dict: The assistant message dict with tool_calls.

        Returns:
            Anthropic-format assistant message with tool_use blocks.
        """
        content = msg_dict.get("content", "")
        content_blocks: list[dict[str, Any]] = []

        if content:
            content_blocks.append({"type": "text", "text": content})

        # Add tool use blocks
        for tc in msg_dict["tool_calls"]:
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "input": json.loads(tc.get("function", {}).get("arguments", "{}")),
                }
            )

        return {"role": "assistant", "content": content_blocks}

    def _transform_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        """
        Transform OpenAI-format messages to Anthropic format.

        Args:
            messages: List of messages in OpenAI format.

        Returns:
            List of messages in Anthropic format.
        """
        result: list[dict[str, Any]] = []

        for msg in messages:
            # Handle both Pydantic models and dicts
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg

            role = msg_dict.get("role", "user")
            content = msg_dict.get("content", "")

            # Handle tool messages
            if role == "tool":
                tool_result = self._transform_tool_message(msg_dict)
                self._merge_tool_result(result, tool_result)
            # Handle assistant with tool calls
            elif role == "assistant" and msg_dict.get("tool_calls"):
                result.append(self._transform_assistant_tool_message(msg_dict))
            else:
                result.append({"role": role, "content": content})

        return result

    def _merge_tool_result(
        self,
        result: list[dict[str, Any]],
        tool_result: dict[str, Any],
    ) -> None:
        """
        Merge tool result into result list, combining consecutive user messages.

        Extracted to reduce cognitive complexity of _transform_messages().

        Args:
            result: The result list to append to (mutated in place).
            tool_result: The tool result message to merge.
        """
        # Merge consecutive tool results if last message is also user
        if result and result[-1].get("role") == "user":
            if isinstance(result[-1].get("content"), list):
                result[-1]["content"].extend(tool_result["content"])
            else:
                result[-1] = tool_result
        else:
            result.append(tool_result)

        return result

    def _transform_response(self, response: Any) -> ChatCompletionResponse:
        """
        Transform Anthropic response to our model.

        Args:
            response: Anthropic API response.

        Returns:
            ChatCompletionResponse model.
        """
        # Extract text content
        content = ""
        tool_calls = None

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    }
                )

        # Determine finish reason
        finish_reason = "stop"
        if response.stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif response.stop_reason == "max_tokens":
            finish_reason = "length"

        return ChatCompletionResponse(
            id=response.id,
            model=response.model,
            created=int(time.time()),
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=content if content else None,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
        )
