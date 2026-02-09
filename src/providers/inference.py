"""Inference Service Provider - Routes to local inference-service.

This provider proxies requests to the local inference-service which hosts
GGUF models running on Metal GPU (qwen2.5-7b, deepseek-r1-7b, phi-4, etc.).

This is the DEFAULT provider for local models. OpenRouter is only used
when explicitly requested by the user.

When CMS (Context Management Service) is enabled, requests are routed
through the CMS proxy endpoint which intercepts traffic, checks context
windows, optimizes/chunks if needed, and forwards to inference-service.

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
    """Provider that proxies to local inference-service via CMS when enabled.
    
    When CMS is enabled (default), requests route through the CMS proxy:
        Client → Gateway → CMS (/v1/proxy/chat/completions) → inference-service
    CMS intercepts the request, checks context windows, optimizes/chunks
    if needed, and forwards to inference-service transparently.
    
    When CMS is disabled or unavailable, requests go directly:
        Client → Gateway → inference-service (/v1/chat/completions)
    
    Model discovery always talks to inference-service directly regardless
    of CMS state.
    
    Example:
        >>> provider = InferenceServiceProvider(cms_url="http://localhost:8086", cms_enabled=True)
        >>> response = await provider.complete(request)  # routes through CMS proxy
    """
    
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 120.0,
        cms_url: str | None = None,
        cms_enabled: bool = False,
    ) -> None:
        """Initialize the inference service provider.
        
        Args:
            base_url: URL of the inference service. If None, auto-resolved via ai_platform_common.
            timeout: Request timeout in seconds
            cms_url: URL of the CMS proxy. If None, CMS routing is disabled.
            cms_enabled: Whether to route through CMS proxy.
        """
        self._base_url = (base_url or _get_default_inference_url()).rstrip("/")
        self._timeout = timeout
        self._cms_url = cms_url.rstrip("/") if cms_url else None
        self._cms_enabled = cms_enabled and self._cms_url is not None
        self._client: httpx.AsyncClient | None = None
        self._proxy_client: httpx.AsyncClient | None = None
        self._discovered_models: list[str] | None = None
        
        # Synchronously discover models at init time (always direct to inference)
        self._discover_models_sync()
        
        mode = "CMS proxy" if self._cms_enabled else "direct"
        target = self._cms_url if self._cms_enabled else self._base_url
        logger.info(
            "InferenceServiceProvider initialized (mode=%s, target=%s, inference=%s, models=%d)",
            mode, target, self._base_url, len(self._discovered_models or []),
        )
    
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
        """Get or create the HTTP client for direct inference-service calls."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client
    
    async def _get_proxy_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for CMS proxy calls."""
        if self._proxy_client is None:
            self._proxy_client = httpx.AsyncClient(
                base_url=self._cms_url,
                timeout=self._timeout,
            )
        return self._proxy_client
    
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
        """Send completion request, routing through CMS proxy when enabled.
        
        When CMS is enabled:
            POST → CMS /v1/proxy/chat/completions
            CMS intercepts, checks context window, optimizes, forwards to inference
        When CMS is disabled:
            POST → inference-service /v1/chat/completions
        
        Args:
            request: The chat completion request
            
        Returns:
            ChatCompletionResponse from inference service (via CMS or direct)
        """
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
        
        # Route through CMS proxy or direct to inference
        if self._cms_enabled:
            client = await self._get_proxy_client()
            endpoint = "/v1/proxy/chat/completions"
            logger.debug("Inference request via CMS proxy: model=%s", request.model)
        else:
            client = await self._get_client()
            endpoint = "/v1/chat/completions"
            logger.debug("Inference request direct: model=%s", request.model)
        
        # Loop detection: tell CMS this request came from gateway
        # so DualRouter won't fallback to gateway (which would loop).
        # Pattern ref: Envoy x-envoy-max-retries, Kong X-Kong-Proxy-Latency
        proxy_headers = {"X-CMS-Origin": "gateway"} if self._cms_enabled else {}
        
        response = await client.post(endpoint, json=payload, headers=proxy_headers)
        response.raise_for_status()
        
        result = response.json()
        logger.debug("Inference response received (via %s)", "CMS" if self._cms_enabled else "direct")
        
        # Convert to ChatCompletionResponse
        return ChatCompletionResponse(**result)
    
    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk]:
        """Stream completion response, routing through CMS proxy when enabled.
        
        Args:
            request: The chat completion request
            
        Yields:
            ChatCompletionChunk for each streamed piece
        """
        payload = {
            "model": request.model,
            "messages": [m.model_dump() for m in request.messages],
            "stream": True,
        }
        
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        
        # Route through CMS proxy or direct to inference
        if self._cms_enabled:
            client = await self._get_proxy_client()
            endpoint = "/v1/proxy/chat/completions"
        else:
            client = await self._get_client()
            endpoint = "/v1/chat/completions"
        
        # Loop detection header for streaming (same as non-streaming)
        proxy_headers = {"X-CMS-Origin": "gateway"} if self._cms_enabled else {}
        
        async with client.stream(
            "POST",
            endpoint,
            json=payload,
            headers=proxy_headers,
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
        """Close HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._proxy_client:
            await self._proxy_client.aclose()
            self._proxy_client = None

