"""Inference Service Provider - Routes to local inference-service:8085.

This provider proxies requests to the local inference-service which hosts
GGUF models running on Metal GPU (qwen2.5-7b, deepseek-r1-7b, phi-4, etc.).

This is the DEFAULT provider for local models. OpenRouter is only used
when explicitly requested by the user.
"""

import logging
from typing import Any, AsyncIterator

import httpx

from src.providers.base import LLMProvider
from src.models.requests import ChatCompletionRequest
from src.models.responses import ChatCompletionResponse, ChatCompletionChunk

logger = logging.getLogger(__name__)

# Default inference service URL
DEFAULT_INFERENCE_URL = "http://localhost:8085"

# Models typically available in inference-service
LOCAL_MODELS = [
    "qwen2.5-7b",
    "deepseek-r1-7b",
    "phi-4",
    "phi-3-medium-128k",
    "llama-3.2-3b",
]


class InferenceServiceProvider(LLMProvider):
    """Provider that proxies to local inference-service.
    
    This provider routes requests to inference-service:8085 which hosts
    local GGUF models running on Metal GPU acceleration.
    
    Supported models (loaded in inference-service):
    - qwen2.5-7b
    - deepseek-r1-7b  
    - phi-4
    - phi-3-medium-128k
    - llama-3.2-3b
    
    Example:
        >>> provider = InferenceServiceProvider()
        >>> response = await provider.complete(request)
    """
    
    def __init__(
        self,
        base_url: str = DEFAULT_INFERENCE_URL,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the inference service provider.
        
        Args:
            base_url: URL of the inference service (default: http://localhost:8085)
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        logger.info(f"InferenceServiceProvider initialized (base_url={base_url})")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client
    
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the specified model.
        
        Supports any model that starts with known local model prefixes.
        """
        model_lower = model.lower()
        # Check exact matches first
        if model_lower in [m.lower() for m in LOCAL_MODELS]:
            return True
        # Check prefixes for local models
        local_prefixes = ["qwen", "deepseek-r1", "phi-", "phi3", "phi4", "llama-3"]
        return any(model_lower.startswith(prefix) for prefix in local_prefixes)
    
    def get_supported_models(self) -> list[str]:
        """Return list of supported model names."""
        return LOCAL_MODELS.copy()
    
    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Send completion request to inference service.
        
        Args:
            request: The chat completion request
            
        Returns:
            ChatCompletionResponse from inference service
        """
        client = await self._get_client()
        
        # Convert request to dict for JSON payload
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
        }
        
        # Add optional parameters if present
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop is not None:
            payload["stop"] = request.stop
        
        logger.debug(f"Inference request: model={request.model}")
        
        response = await client.post(
            "/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Inference response received")
        
        # Convert to ChatCompletionResponse
        return ChatCompletionResponse(**result)
    
    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream completion response from inference service.
        
        Args:
            request: The chat completion request
            
        Yields:
            ChatCompletionChunk for each streamed piece
        """
        client = await self._get_client()
        
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": True,
        }
        
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        import json
                        chunk_data = json.loads(data)
                        yield ChatCompletionChunk(**chunk_data)
                    except Exception:
                        continue
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

