"""Inference Service Provider - Routes to local inference-service.

This provider proxies requests to the local inference-service which hosts
GGUF models running on Metal GPU (qwen2.5-7b, deepseek-r1-7b, phi-4, etc.).

This is the DEFAULT provider for local models. OpenRouter is only used
when explicitly requested by the user.

URL resolution uses ai_platform_common for infrastructure-aware discovery.
"""

import logging
from typing import Any, AsyncIterator

import httpx

from src.providers.base import LLMProvider
from src.models.requests import ChatCompletionRequest
from src.models.responses import ChatCompletionResponse, ChatCompletionChunk

logger = logging.getLogger(__name__)


def _get_default_inference_url() -> str:
    """Get inference service URL using ai_platform_common if available.
    
    Falls back to localhost:8085 if ai_platform_common is not installed.
    """
    try:
        from ai_platform_common import get_service_url
        return get_service_url("inference-service")
    except ImportError:
        logger.warning("ai_platform_common not installed, using localhost:8085 for inference-service")
        return "http://localhost:8085"


# Fallback models if inference-service is unreachable during init
FALLBACK_MODELS = [
    "qwen2.5-7b",
    "deepseek-r1-7b",
    "phi-4",
    "phi-3-medium-128k",
    "llama-3.2-3b",
]


class InferenceServiceProvider(LLMProvider):
    """Provider that proxies to local inference-service.
    
    This provider routes requests to inference-service which hosts
    local GGUF models running on Metal GPU acceleration.
    
    URL is resolved using ai_platform_common.get_service_url() which
    supports docker/hybrid/native deployment modes.
    
    Models are dynamically discovered from the inference-service /v1/models
    endpoint at initialization time.
    
    Example:
        >>> provider = InferenceServiceProvider()
        >>> response = await provider.complete(request)
    """
    
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the inference service provider.
        
        Args:
            base_url: URL of the inference service. If None, auto-resolved via ai_platform_common.
            timeout: Request timeout in seconds
        """
        self._base_url = (base_url or _get_default_inference_url()).rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._discovered_models: list[str] | None = None
        
        # Synchronously discover models at init time
        self._discover_models_sync()
        logger.info(f"InferenceServiceProvider initialized (base_url={self._base_url}, models={len(self._discovered_models or [])})")
    
    def _discover_models_sync(self) -> None:
        """Synchronously discover available models from inference-service.
        
        Called during __init__ to populate the model list.
        Falls back to FALLBACK_MODELS if service is unreachable.
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/v1/models")
                response.raise_for_status()
                data = response.json()
                self._discovered_models = [m["id"] for m in data.get("data", [])]
                logger.info(f"Discovered {len(self._discovered_models)} models from inference-service at {self._base_url}")
        except Exception as e:
            logger.warning(f"Could not discover models from inference-service ({self._base_url}): {e}. Using fallback list.")
            self._discovered_models = FALLBACK_MODELS.copy()
    
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
        
        Checks against dynamically discovered models from inference-service.
        """
        if self._discovered_models:
            model_lower = model.lower()
            return model_lower in [m.lower() for m in self._discovered_models]
        return False
    
    def get_supported_models(self) -> list[str]:
        """Return list of supported model names from inference-service."""
        return (self._discovered_models or FALLBACK_MODELS).copy()
    
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

