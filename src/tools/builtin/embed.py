"""
Embed Tool - WBS-CPA6 Gateway Tool Invocation

This module implements the embed tool that proxies embedding requests
to the semantic-search-service for external clients.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA6 Gateway Tool Invocation
- semantic-search-service/src/api/embeddings.py: /v1/embeddings endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

Communication Pattern:
- EXTERNAL (MCP, external LLMs): Gateway (:8080) -> embed tool -> semantic-search

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience (Newman pp. 357-358)

Anti-Patterns Avoided:
- AP-1: Tool names as constants
- AP-5: {Service}Error prefix for exceptions
"""

import logging
from typing import Any, Optional

import httpx

from src.clients.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (AP-1 compliance: tool names as constants)
# =============================================================================

TOOL_NAME_EMBED = "embed"
ENDPOINT_EMBEDDINGS = "/v1/embeddings"


# =============================================================================
# Circuit Breaker for Semantic-Search Service (Embed)
# Pattern: Singleton circuit breaker per service operation
# =============================================================================

_embed_circuit_breaker: Optional[CircuitBreaker] = None


def get_embed_circuit_breaker() -> CircuitBreaker:
    """
    Get the shared circuit breaker for embed operations.
    
    WBS-CPA6: Separate circuit breaker for embed to isolate from search failures.
    
    Returns:
        CircuitBreaker instance configured from settings.
    """
    global _embed_circuit_breaker
    if _embed_circuit_breaker is None:
        settings = get_settings()
        _embed_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
            name="semantic-search-embed",
        )
    return _embed_circuit_breaker


# =============================================================================
# Exceptions (AP-5 compliance: {Service}Error prefix)
# =============================================================================


class EmbedServiceError(Exception):
    """Raised when the embed service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS-CPA6.2: Embed Tool Definition
# =============================================================================


EMBED_DEFINITION = ToolDefinition(
    name=TOOL_NAME_EMBED,
    description="Generate embedding vectors for texts using semantic-search-service. "
    "Returns dense vectors suitable for semantic similarity calculations, "
    "clustering, or vector database storage. "
    "Use this for external embedding generation via the Gateway.",
    parameters={
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of texts to generate embeddings for.",
            },
            "model": {
                "type": "string",
                "description": "Embedding model to use (default: all-MiniLM-L6-v2).",
                "default": "all-MiniLM-L6-v2",
            },
        },
        "required": ["texts"],
    },
)


# =============================================================================
# Internal HTTP Request Function
# =============================================================================


async def _do_embed_request(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Internal function to perform HTTP request to semantic-search-service.
    
    Separated for circuit breaker wrapping.
    
    Args:
        payload: Request payload with texts and optional model.
        
    Returns:
        Response JSON with embeddings.
    """
    settings = get_settings()
    base_url = settings.semantic_search_url
    timeout = getattr(settings, "tool_timeout_seconds", 30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{base_url}{ENDPOINT_EMBEDDINGS}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# WBS-CPA6.2: Embed Tool Function
# =============================================================================


async def embed(params: dict[str, Any]) -> dict[str, Any]:
    """
    Generate embeddings for texts via semantic-search-service.
    
    WBS-CPA6.2: External clients access this tool via Gateway.
    Routes requests to semantic-search-service /v1/embeddings endpoint.
    
    Args:
        params: Dictionary with:
            - texts (list[str]): Texts to embed (required).
            - model (str): Embedding model (optional, default: all-MiniLM-L6-v2).
    
    Returns:
        Dictionary with:
            - embeddings (list[list[float]]): Embedding vectors.
            - model (str): Model used.
            - dimensions (int): Vector dimensions.
            - processing_time_ms (float): Processing time (optional).
    
    Raises:
        EmbedServiceError: If semantic-search-service is unavailable.
    """
    texts = params.get("texts", [])
    model = params.get("model", "all-MiniLM-L6-v2")
    
    # Build request payload
    payload = {
        "texts": texts,
        "model": model,
    }
    
    circuit_breaker = get_embed_circuit_breaker()
    
    try:
        # Execute with circuit breaker protection
        result = await circuit_breaker.call(_do_embed_request, payload)
        return result
    
    except CircuitOpenError as e:
        logger.warning(f"Embed circuit breaker open: {e}")
        raise EmbedServiceError(
            f"Embed service unavailable (circuit breaker open): {e}"
        ) from e
    
    except httpx.RequestError as e:
        logger.error(f"Embed request failed: {e}")
        raise EmbedServiceError(
            f"Embed service unavailable: {e}"
        ) from e
    
    except httpx.HTTPStatusError as e:
        logger.error(f"Embed HTTP error: {e.response.status_code}")
        raise EmbedServiceError(
            f"Embed service error (HTTP {e.response.status_code}): {e}"
        ) from e
