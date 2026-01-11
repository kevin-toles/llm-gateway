"""
Gemini Provider - Google Generative AI Adapter

This module implements the Google Gemini provider adapter, including
tool handling for transformation between OpenAI and Gemini formats.

Reference Documents:
- ARCHITECTURE.md: providers/*.py pattern
- GUIDELINES pp. 215: Provider abstraction for model swapping
- GUIDELINES pp. 793-795: Repository pattern and ABC patterns
- GUIDELINES pp. 1510-1590: Tool patterns and agent architectures
- GUIDELINES pp. 2229: Model API patterns
- Google Generative AI API Docs: https://ai.google.dev/api

Design Patterns:
- Ports and Adapters: GeminiProvider implements LLMProvider interface
- Adapter: Transforms OpenAI-style requests to Gemini format
- Retry with Exponential Backoff: Handles transient errors
"""

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

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
# Supported Models
# =============================================================================

SUPPORTED_MODELS = [
    # Gemini 2.5 (Latest - January 2026)
    "gemini-2.5-pro",
    "gemini-2.5-pro-preview-05-06",
    "gemini-2.5-flash",
    # Gemini 2.0
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-2.0-pro",
    # Gemini 1.5
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash-8b",
    # Gemini 1.0 (Legacy)
    "gemini-1.0-pro",
    "gemini-pro",
]

# Default API base URL
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


# =============================================================================
# Gemini Tool Handler
# =============================================================================


class GeminiToolHandler:
    """
    Handler for transforming tools between OpenAI and Gemini formats.

    This class provides methods to:
    - Transform OpenAI tool definitions to Gemini format
    - Parse Gemini function call responses to OpenAI format
    - Format tool results for Gemini API

    Pattern: Adapter pattern for format transformation
    Reference: GUIDELINES pp. 1510-1590 - Tool inventories as service registries

    Example:
        >>> handler = GeminiToolHandler()
        >>> gemini_tools = handler.transform_tools(openai_tools)
        >>> tool_calls = handler.parse_function_calls(gemini_response)
    """

    def transform_tool_definition(self, openai_tool: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single OpenAI tool definition to Gemini format.

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
            Gemini format function declaration:
                {
                    "name": str,
                    "description": Optional[str],
                    "parameters": dict
                }
        """
        function_def = openai_tool.get("function", {})

        gemini_func: dict[str, Any] = {
            "name": function_def.get("name", ""),
        }

        # Handle optional description
        description = function_def.get("description")
        if description:
            gemini_func["description"] = description

        # Transform parameters (Gemini uses same JSON Schema format)
        parameters = function_def.get("parameters")
        if parameters:
            gemini_func["parameters"] = parameters

        return gemini_func

    def transform_tools(self, openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Transform a list of OpenAI tools to Gemini function declarations.

        Args:
            openai_tools: List of OpenAI format tool definitions.

        Returns:
            Gemini tools format:
                [{"function_declarations": [...]}]
        """
        function_declarations = [
            self.transform_tool_definition(tool) for tool in openai_tools
        ]
        return [{"function_declarations": function_declarations}]

    def parse_function_calls(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Parse Gemini function call responses to OpenAI tool_calls format.

        Args:
            candidates: Gemini response candidates with functionCall parts.

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
        """
        tool_calls: list[dict[str, Any]] = []

        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "functionCall" in part:
                    func_call = part["functionCall"]
                    tool_call = {
                        "id": f"call_{uuid.uuid4().hex[:24]}",
                        "type": "function",
                        "function": {
                            "name": func_call.get("name", ""),
                            "arguments": json.dumps(func_call.get("args", {})),
                        },
                    }
                    tool_calls.append(tool_call)

        return tool_calls

    def extract_text_content(self, candidates: list[dict[str, Any]]) -> str:
        """
        Extract text content from Gemini candidates.

        Args:
            candidates: Gemini response candidates.

        Returns:
            Concatenated text content from text parts.
        """
        text_parts: list[str] = []

        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            for part in parts:
                if "text" in part:
                    text_parts.append(part["text"])

        return "".join(text_parts)


# =============================================================================
# Gemini Provider
# =============================================================================


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider adapter.

    This class implements the LLMProvider interface for Google's Gemini models.
    It handles chat completions (streaming and non-streaming) with retry
    logic for transient errors.

    Pattern: Ports and Adapters (Hexagonal Architecture)
    Pattern: Retry with Exponential Backoff
    Reference: GUIDELINES pp. 215 - Provider abstraction for model swapping

    Args:
        api_key: Google AI API key (GEMINI_API_KEY).
        max_retries: Maximum retry attempts for transient errors.
        retry_delay: Initial delay between retries (exponential backoff).
        api_base: Base URL for Gemini API (default: generativelanguage.googleapis.com).

    Example:
        >>> provider = GeminiProvider(api_key="AIza...")
        >>> response = await provider.complete(request)
        >>> print(response.choices[0].message.content)
    """

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        api_base: str | None = None,
    ) -> None:
        """
        Initialize Gemini provider.

        Args:
            api_key: Google AI API key. Falls back to GEMINI_API_KEY env var.
            max_retries: Maximum retry attempts (default: 3).
            retry_delay: Initial retry delay in seconds (default: 1.0).
            api_base: API base URL (default: Google's API).
        """
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self._api_key:
            logger.warning("No Gemini API key provided. Set GEMINI_API_KEY env var.")

        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._api_base = api_base or GEMINI_API_BASE
        self._tool_handler = GeminiToolHandler()
        self._client = httpx.AsyncClient(timeout=120.0)

    async def __aenter__(self) -> "GeminiProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self._client.aclose()

    # =========================================================================
    # Model Support Methods
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
        # Check exact match
        if model_lower in [m.lower() for m in SUPPORTED_MODELS]:
            return True
        # Check prefix match for gemini models
        return model_lower.startswith("gemini-")

    def get_supported_models(self) -> list[str]:
        """
        Get the list of supported model identifiers.

        Returns:
            List of supported model identifiers.
        """
        return SUPPORTED_MODELS.copy()

    # =========================================================================
    # complete() method
    # =========================================================================

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).

        Args:
            request: The chat completion request.

        Returns:
            ChatCompletionResponse with completion results.

        Raises:
            ProviderError: On API errors.
            RateLimitError: On rate limit errors.
            AuthenticationError: On auth errors.
        """
        # Build request payload
        payload = self._build_request_payload(request)

        # Build URL
        url = f"{self._api_base}/models/{request.model}:generateContent?key={self._api_key}"

        # Execute with retry
        response_data = await self._execute_with_retry(url, payload)

        # Transform response to our model
        return self._transform_response(response_data, request.model)

    # =========================================================================
    # stream() method
    # =========================================================================

    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.

        Args:
            request: The chat completion request.

        Yields:
            ChatCompletionChunk objects as they arrive.

        Raises:
            ProviderError: On API errors.
            RateLimitError: On rate limit errors.
            AuthenticationError: On auth errors.
        """
        # Build request payload
        payload = self._build_request_payload(request)

        # Build streaming URL
        url = f"{self._api_base}/models/{request.model}:streamGenerateContent?key={self._api_key}&alt=sse"

        response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        try:
            async for chunk in self._stream_response(url, payload, response_id, request.model, created):
                yield chunk
        except httpx.HTTPStatusError as e:
            self._handle_error(e)
        except Exception as e:
            self._handle_error(e)

    async def _stream_response(
        self,
        url: str,
        payload: dict[str, Any],
        response_id: str,
        model: str,
        created: int,
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Internal streaming implementation.

        Extracted to reduce cognitive complexity of stream().
        """
        async with self._client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                self._handle_error_response(response.status_code, error_text.decode())

            async for line in response.aiter_lines():
                chunk = self._process_stream_line(line, response_id, model, created)
                if chunk is None:
                    continue
                if chunk == "DONE":
                    yield self._create_final_chunk(response_id, model, created)
                    break
                yield chunk

    def _process_stream_line(
        self,
        line: str,
        response_id: str,
        model: str,
        created: int,
    ) -> ChatCompletionChunk | str | None:
        """
        Process a single SSE line from the stream.

        Returns:
            ChatCompletionChunk if content found, "DONE" if done, None to skip.
        """
        if not line or not line.startswith("data: "):
            return None

        data_str = line[6:]  # Remove "data: " prefix
        if data_str.strip() == "[DONE]":
            return "DONE"

        try:
            chunk_data = json.loads(data_str)
            text = self._extract_streaming_text(chunk_data)
            if text:
                return self._create_content_chunk(response_id, model, created, text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse streaming chunk: {data_str[:100]}")

        return None

    def _create_content_chunk(
        self,
        response_id: str,
        model: str,
        created: int,
        content: str,
    ) -> ChatCompletionChunk:
        """Create a content chunk for streaming."""
        return ChatCompletionChunk(
            id=response_id,
            model=model,
            created=created,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(role="assistant", content=content),
                    finish_reason=None,
                )
            ],
        )

    def _create_final_chunk(
        self,
        response_id: str,
        model: str,
        created: int,
    ) -> ChatCompletionChunk:
        """Create the final chunk with finish_reason."""
        return ChatCompletionChunk(
            id=response_id,
            model=model,
            created=created,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(),
                    finish_reason="stop",
                )
            ],
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_request_payload(self, request: ChatCompletionRequest) -> dict[str, Any]:
        """
        Build payload for Gemini API call from request.

        Args:
            request: The chat completion request.

        Returns:
            Dict payload for the API call.
        """
        # Transform messages to Gemini format
        contents = self._transform_messages(request.messages)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {},
        }

        # Add generation config
        gen_config = payload["generationConfig"]

        if request.max_tokens:
            gen_config["maxOutputTokens"] = request.max_tokens

        if request.temperature is not None:
            gen_config["temperature"] = request.temperature

        if request.top_p is not None:
            gen_config["topP"] = request.top_p

        # Remove empty generationConfig
        if not gen_config:
            del payload["generationConfig"]

        # Transform tools if present
        if request.tools:
            payload["tools"] = self._tool_handler.transform_tools(
                [t.model_dump() for t in request.tools]
            )

        return payload

    def _transform_messages(
        self, messages: list[Any]
    ) -> list[dict[str, Any]]:
        """
        Transform OpenAI-format messages to Gemini format.

        OpenAI format:
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]

        Gemini format:
            [{"role": "user", "parts": [{"text": "Hello"}]},
             {"role": "model", "parts": [{"text": "Hi"}]}]

        Args:
            messages: List of OpenAI-format messages.

        Returns:
            List of Gemini-format contents.
        """
        contents: list[dict[str, Any]] = []
        system_instruction: str | None = None

        for msg in messages:
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
            role = msg_dict.get("role", "user")
            content = msg_dict.get("content", "")

            # Handle system messages
            if role == "system":
                system_instruction = content
                continue

            # Handle tool messages
            if role == "tool":
                contents.append(self._transform_tool_message(msg_dict, content))
                continue

            # Transform regular message
            transformed = self._transform_regular_message(msg_dict, role, content)
            if transformed:
                contents.append(transformed)

        # Prepend system instruction if present
        self._prepend_system_instruction(contents, system_instruction)

        return contents

    def _transform_tool_message(
        self, msg_dict: dict[str, Any], content: str
    ) -> dict[str, Any]:
        """Transform a tool response message to Gemini format."""
        tool_call_id = msg_dict.get("tool_call_id", "")
        return {
            "role": "user",
            "parts": [{
                "functionResponse": {
                    "name": tool_call_id,
                    "response": {"result": content}
                }
            }]
        }

    def _transform_regular_message(
        self, msg_dict: dict[str, Any], role: str, content: Any
    ) -> dict[str, Any] | None:
        """Transform a regular user/assistant message to Gemini format."""
        gemini_role = "model" if role == "assistant" else "user"
        parts = self._build_content_parts(content)

        # Handle tool calls in assistant messages
        tool_calls = msg_dict.get("tool_calls")
        if tool_calls:
            parts.extend(self._transform_tool_calls(tool_calls))

        if parts:
            return {"role": gemini_role, "parts": parts}
        return None

    def _build_content_parts(self, content: Any) -> list[dict[str, Any]]:
        """Build content parts from message content."""
        parts: list[dict[str, Any]] = []

        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for item in content:
                part = self._transform_content_item(item)
                if part:
                    parts.append(part)

        return parts

    def _transform_content_item(self, item: Any) -> dict[str, Any] | None:
        """Transform a single content item (text or image)."""
        if not isinstance(item, dict):
            return None

        if item.get("type") == "text":
            return {"text": item.get("text", "")}

        if item.get("type") == "image_url":
            return self._transform_image_item(item)

        return None

    def _transform_image_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Transform an image URL item to Gemini format."""
        image_url = item.get("image_url", {})
        url = image_url.get("url", "")
        if url.startswith("data:"):
            return {"inlineData": self._parse_data_url(url)}
        logger.warning("External image URLs may not be supported")
        return None

    def _transform_tool_calls(
        self, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Transform tool calls to Gemini functionCall format."""
        parts = []
        for tc in tool_calls:
            func = tc.get("function", {})
            parts.append({
                "functionCall": {
                    "name": func.get("name", ""),
                    "args": json.loads(func.get("arguments", "{}"))
                }
            })
        return parts

    def _prepend_system_instruction(
        self, contents: list[dict[str, Any]], system_instruction: str | None
    ) -> None:
        """Prepend system instruction to contents if present."""
        if not system_instruction or not contents:
            return

        # For older models, prepend to first user message
        if contents[0]["role"] == "user":
            contents[0]["parts"].insert(0, {"text": f"System: {system_instruction}\n\n"})
        else:
            contents.insert(0, {
                "role": "user",
                "parts": [{"text": f"System: {system_instruction}"}]
            })

    def _parse_data_url(self, data_url: str) -> dict[str, str]:
        """
        Parse a data URL into Gemini inlineData format.

        Args:
            data_url: Data URL like "data:image/png;base64,..."

        Returns:
            Dict with mimeType and data fields.
        """
        # Format: data:mime/type;base64,data
        if ";base64," in data_url:
            meta, data = data_url.split(";base64,", 1)
            mime_type = meta.replace("data:", "")
            return {"mimeType": mime_type, "data": data}
        return {"mimeType": "application/octet-stream", "data": ""}

    def _transform_response(
        self, response_data: dict[str, Any], model: str
    ) -> ChatCompletionResponse:
        """
        Transform Gemini response to ChatCompletionResponse.

        Args:
            response_data: Raw Gemini API response.
            model: The model name used.

        Returns:
            ChatCompletionResponse in OpenAI format.
        """
        response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        candidates = response_data.get("candidates", [])

        # Extract text content
        content = self._tool_handler.extract_text_content(candidates)

        # Extract tool calls if present
        tool_calls = self._tool_handler.parse_function_calls(candidates)

        # Determine finish reason
        finish_reason = "stop"
        if candidates:
            gemini_finish = candidates[0].get("finishReason", "STOP")
            finish_reason = self._map_finish_reason(gemini_finish)

        # Build choice message
        choice_message = ChoiceMessage(
            role="assistant",
            content=content if content else None,
        )

        # Add tool calls if present
        if tool_calls:
            choice_message = ChoiceMessage(
                role="assistant",
                content=content if content else None,
                tool_calls=tool_calls,
            )
            finish_reason = "tool_calls"

        # Extract usage metadata
        usage_metadata = response_data.get("usageMetadata", {})
        usage = Usage(
            prompt_tokens=usage_metadata.get("promptTokenCount", 0),
            completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
            total_tokens=usage_metadata.get("totalTokenCount", 0),
        )

        return ChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=created,
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=choice_message,
                    finish_reason=finish_reason,
                )
            ],
            usage=usage,
        )

    def _map_finish_reason(self, gemini_reason: str) -> str:
        """
        Map Gemini finish reason to OpenAI format.

        Args:
            gemini_reason: Gemini's finishReason value.

        Returns:
            OpenAI-compatible finish_reason.
        """
        mapping = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
            "OTHER": "stop",
        }
        return mapping.get(gemini_reason, "stop")

    def _extract_streaming_text(self, chunk_data: dict[str, Any]) -> str:
        """
        Extract text from a streaming chunk.

        Args:
            chunk_data: Parsed JSON chunk from SSE stream.

        Returns:
            Text content from the chunk.
        """
        candidates = chunk_data.get("candidates", [])
        return self._tool_handler.extract_text_content(candidates)

    # =========================================================================
    # Retry Logic with Exponential Backoff
    # =========================================================================

    async def _execute_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute HTTP request with retry logic and exponential backoff.

        Args:
            url: The API URL.
            payload: The request payload.

        Returns:
            The response data as dict.

        Raises:
            RateLimitError: When retries exhausted on rate limit.
            AuthenticationError: Immediately on auth errors (no retry).
            ProviderError: On other errors after retry exhaustion.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    return response.json()

                # Handle error responses
                error_text = response.text
                self._handle_error_response(response.status_code, error_text)

            except (AuthenticationError, RateLimitError):
                raise
            except ProviderError as e:
                last_error = e
                # Wait before retry (exponential backoff)
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = ProviderError(str(e), provider="gemini")
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)

        # Exhausted retries
        raise ProviderError(
            f"Request failed after {self._max_retries} attempts: {last_error}",
            provider="gemini",
        )

    def _handle_error_response(self, status_code: int, error_text: str) -> None:
        """
        Handle HTTP error responses from Gemini API.

        Args:
            status_code: HTTP status code.
            error_text: Error response body.

        Raises:
            AuthenticationError: For 401/403 errors.
            RateLimitError: For 429 errors.
            ProviderError: For other errors.
        """
        if status_code in (401, 403):
            raise AuthenticationError(
                f"Authentication failed: {error_text}",
                provider="gemini",
            )

        if status_code == 429:
            raise RateLimitError(f"Rate limit exceeded: {error_text}")

        raise ProviderError(
            f"Gemini API error ({status_code}): {error_text}",
            provider="gemini",
        )

    def _handle_error(self, e: Exception) -> None:
        """
        Handle and re-raise errors with appropriate types.

        Args:
            e: The exception to handle.

        Raises:
            AuthenticationError: For auth errors.
            RateLimitError: For rate limit errors.
            ProviderError: For other errors.
        """
        error_str = str(e).lower()

        if "401" in error_str or "403" in error_str or "api key" in error_str:
            raise AuthenticationError(str(e), provider="gemini") from e

        if "429" in error_str or "rate limit" in error_str:
            raise RateLimitError(str(e)) from e

        raise ProviderError(str(e), provider="gemini") from e
