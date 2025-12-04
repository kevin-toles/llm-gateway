"""
Ollama Provider - WBS 2.3.4 Ollama Local Adapter

This module implements the Ollama local model provider adapter.
Ollama runs locally and provides access to open-source LLMs like Llama, Mistral, etc.

Reference Documents:
- ARCHITECTURE.md: Line 43 - ollama.py "Ollama local adapter"
- GUIDELINES pp. 2309: Timeout configuration and connection pooling
- GUIDELINES pp. 1004: Self-hosted model patterns
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS: Exception names must not shadow builtins

Design Patterns:
- Ports and Adapters: OllamaProvider implements LLMProvider interface
- HTTP Client: Uses httpx for async HTTP requests to local Ollama API
- Adapter Pattern: Transforms Ollama responses to our response models

Ollama API Reference:
- Base URL: http://localhost:11434 (default)
- Chat endpoint: POST /api/chat
- Models endpoint: GET /api/tags
"""

import json
import time
import uuid
from typing import Any, AsyncIterator, Optional

import httpx

from src.models.requests import ChatCompletionRequest
from src.models.responses import (
    ChatCompletionResponse,
    ChatCompletionChunk,
    Choice,
    ChoiceMessage,
    ChunkChoice,
    ChunkDelta,
    Usage,
)
from src.providers.base import LLMProvider


# =============================================================================
# WBS 2.3.4.1.12: Custom Exception Classes
# NOTE: Named with Ollama prefix to avoid shadowing Python builtins
# See CODING_PATTERNS_ANALYSIS.md §7.1: Exception Shadowing Anti-Pattern
# =============================================================================


class OllamaProviderError(Exception):
    """
    Base exception for Ollama provider errors.
    
    WBS 2.3.4.1.12: Custom exception for provider-specific errors.
    """
    pass


class OllamaConnectionError(OllamaProviderError):
    """
    Exception raised when connection to Ollama fails.
    
    WBS 2.3.4.1.12: Connection error for local service unavailability.
    
    NOTE: Named OllamaConnectionError to avoid shadowing Python's
    builtin ConnectionError exception.
    """
    pass


class OllamaTimeoutError(OllamaProviderError):
    """
    Exception raised when request times out.
    
    WBS 2.3.4.1.12: Timeout error for slow responses.
    Pattern: Timeout configuration (GUIDELINES pp. 2309)
    
    NOTE: Named OllamaTimeoutError to avoid shadowing Python's
    builtin TimeoutError exception.
    """
    pass


# =============================================================================
# WBS 2.3.4.1: Ollama Provider
# =============================================================================


class OllamaProvider(LLMProvider):
    """
    Ollama local model provider adapter.
    
    WBS 2.3.4.1: Ollama Adapter Implementation.
    
    This class implements the LLMProvider interface for Ollama's local models.
    It communicates with a local Ollama instance via HTTP to provide chat
    completions with models like Llama, Mistral, CodeLlama, etc.
    
    Pattern: Ports and Adapters (Hexagonal Architecture)
    Pattern: HTTP Client with timeout (GUIDELINES pp. 2309)
    
    Args:
        base_url: URL of the Ollama instance (default: http://localhost:11434).
        timeout: Request timeout in seconds (default: 120.0 for long generations).
        
    Example:
        >>> provider = OllamaProvider()
        >>> await provider.refresh_models()  # Fetch available models
        >>> response = await provider.complete(request)
        >>> print(response.choices[0].message.content)
    """

    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 120.0  # Long timeout for local model inference

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize Ollama provider.
        
        WBS 2.3.4.1.3: Initialize HTTP client for Ollama API.
        
        Args:
            base_url: URL of Ollama instance (default: http://localhost:11434).
            timeout: Request timeout in seconds (default: 120.0).
            
        Pattern: Optional[T] with None defaults (ANTI_PATTERN §1.1)
        """
        self._base_url = base_url or self.DEFAULT_URL
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._available_models: list[str] = []

    # =========================================================================
    # WBS 2.3.4.1.4-7: complete() method
    # =========================================================================

    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Generate a chat completion response (non-streaming).
        
        WBS 2.3.4.1.4: Implement complete() method.
        
        Args:
            request: The chat completion request.
            
        Returns:
            ChatCompletionResponse with completion results.
            
        Raises:
            OllamaConnectionError: When Ollama is not reachable.
            OllamaTimeoutError: When request times out.
            OllamaProviderError: On other API errors.
        """
        # Build Ollama request format
        ollama_request = self._build_ollama_request(request)
        ollama_request["stream"] = False
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=ollama_request,
                )
                response.raise_for_status()
                data = response.json()
                
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Request to Ollama timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise OllamaProviderError(f"Ollama API error: {e}") from e
        
        # Transform response
        return self._transform_response(data, request.model)

    # =========================================================================
    # WBS 2.3.4.1.8: stream() method
    # =========================================================================

    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Generate a streaming chat completion response.
        
        WBS 2.3.4.1.8: Implement stream() method.
        
        Args:
            request: The chat completion request.
            
        Yields:
            ChatCompletionChunk objects as they arrive.
            
        Raises:
            OllamaConnectionError: When Ollama is not reachable.
            OllamaTimeoutError: When request times out.
            OllamaProviderError: On other API errors.
        """
        # Build Ollama request format
        ollama_request = self._build_ollama_request(request)
        ollama_request["stream"] = True
        
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/api/chat",
                    json=ollama_request,
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        
                        chunk = self._transform_chunk(
                            data, request.model, response_id, created
                        )
                        yield chunk
                        
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e
        except httpx.TimeoutException as e:
            raise OllamaTimeoutError(f"Request to Ollama timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise OllamaProviderError(f"Ollama API error: {e}") from e

    # =========================================================================
    # WBS 2.3.4.1.9: supports_model() method
    # =========================================================================

    def supports_model(self, model: str) -> bool:
        """
        Check if this provider supports the specified model.
        
        WBS 2.3.4.1.9: Implement supports_model() dynamically.
        
        Args:
            model: The model identifier.
            
        Returns:
            True if model is in available models list, False otherwise.
            
        Note:
            This checks against the cached available models list.
            Call refresh_models() to update the list from Ollama.
        """
        return model in self._available_models

    # =========================================================================
    # WBS 2.3.4.1.10: get_supported_models() method
    # =========================================================================

    def get_supported_models(self) -> list[str]:
        """
        Get the list of supported model identifiers.
        
        WBS 2.3.4.1.10: Implement get_supported_models().
        
        Returns:
            List of available model identifiers from cache.
            
        Note:
            Returns empty list if refresh_models() hasn't been called.
            Call refresh_models() to fetch from Ollama.
        """
        return self._available_models.copy()

    # =========================================================================
    # WBS 2.3.4.1.10: list_available_models() method
    # =========================================================================

    async def list_available_models(self) -> list[str]:
        """
        Fetch and return available models from Ollama.
        
        WBS 2.3.4.1.10: Implement list_available_models().
        
        Returns:
            List of model names available in the local Ollama instance.
            
        Raises:
            OllamaConnectionError: When Ollama is not reachable.
            ProviderError: On other API errors.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Ollama API error: {e}") from e
        
        models = data.get("models", [])
        return [m.get("name", "") for m in models if m.get("name")]

    async def refresh_models(self) -> None:
        """
        Refresh the cached list of available models.
        
        WBS 2.3.4.1.10: Model discovery from Ollama.
        
        Raises:
            OllamaConnectionError: When Ollama is not reachable.
            ProviderError: On other API errors.
        """
        self._available_models = await self.list_available_models()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_ollama_request(
        self, request: ChatCompletionRequest
    ) -> dict[str, Any]:
        """
        Build Ollama API request from ChatCompletionRequest.
        
        WBS 2.3.4.1.5: Transform request to Ollama format.
        
        Args:
            request: The chat completion request.
            
        Returns:
            Dict formatted for Ollama /api/chat endpoint.
        """
        # Convert messages to Ollama format
        messages = []
        for msg in request.messages:
            ollama_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content or "",
            }
            messages.append(ollama_msg)
        
        ollama_request: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        
        # Build options dict for Ollama-specific parameters
        options: dict[str, Any] = {}
        
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens  # Ollama uses num_predict
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.stop is not None:
            # Ollama expects stop as a list
            if isinstance(request.stop, str):
                options["stop"] = [request.stop]
            else:
                options["stop"] = request.stop
        if request.seed is not None:
            options["seed"] = request.seed
        if request.presence_penalty is not None:
            options["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            # Ollama's repeat_penalty must be >= 0
            # Convert from frequency_penalty (-2.0 to 2.0) to repeat_penalty (0.0+)
            repeat_penalty = 1.0 + request.frequency_penalty
            options["repeat_penalty"] = max(0.0, repeat_penalty)
        
        if options:
            ollama_request["options"] = options
        
        return ollama_request

    def _transform_response(
        self, data: dict[str, Any], model: str
    ) -> ChatCompletionResponse:
        """
        Transform Ollama response to ChatCompletionResponse.
        
        WBS 2.3.4.1.7: Transform response to internal format.
        
        Args:
            data: The Ollama API response data.
            model: The model identifier.
            
        Returns:
            ChatCompletionResponse model.
        """
        message_data = data.get("message", {})
        
        # Build choice
        choice = Choice(
            index=0,
            message=ChoiceMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", ""),
                tool_calls=None,  # Ollama doesn't support tool calls (yet)
            ),
            finish_reason="stop" if data.get("done", False) else None,
            logprobs=None,
        )
        
        # Build usage from Ollama's token counts
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        
        # Generate response ID
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        
        return ChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=created,
            model=model,
            choices=[choice],
            usage=usage,
            system_fingerprint=None,
        )

    def _transform_chunk(
        self,
        data: dict[str, Any],
        model: str,
        response_id: str,
        created: int,
    ) -> ChatCompletionChunk:
        """
        Transform Ollama stream chunk to ChatCompletionChunk.
        
        Args:
            data: The Ollama stream chunk data.
            model: The model identifier.
            response_id: The response ID (same for all chunks).
            created: The creation timestamp.
            
        Returns:
            ChatCompletionChunk model.
        """
        message_data = data.get("message", {})
        is_done = data.get("done", False)
        
        # Build delta
        delta = ChunkDelta(
            role=message_data.get("role") if not is_done else None,
            content=message_data.get("content"),
            tool_calls=None,
        )
        
        # Build chunk choice
        chunk_choice = ChunkChoice(
            index=0,
            delta=delta,
            finish_reason="stop" if is_done else None,
            logprobs=None,
        )
        
        return ChatCompletionChunk(
            id=response_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[chunk_choice],
            system_fingerprint=None,
        )

