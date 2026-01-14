"""
Hybrid Search Tool - WBS-CPA1.4 Hybrid Search Tool

This module implements the hybrid_search tool that proxies hybrid search requests
to the semantic-search-service's /v1/search/hybrid endpoint.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA1 Gateway External Tool Exposure
- CONSOLIDATED_PLATFORM_ARCHITECTURE.md: Kitchen Brigade Architecture
- semantic-search-service/src/api/routes.py: /v1/search/hybrid endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience (Newman pp. 357-358)

Communication Pattern:
- INTERNAL (platform services): Direct API calls (:8081)
- EXTERNAL (MCP, external LLMs): Gateway (:8080) -> this tool
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

TOOL_NAME = "hybrid_search"
ENDPOINT_PATH = "/v1/search/hybrid"


# =============================================================================
# Circuit Breaker for Hybrid Search
# Pattern: Singleton circuit breaker per downstream service endpoint
# =============================================================================

_hybrid_search_circuit_breaker: Optional[CircuitBreaker] = None


def get_hybrid_search_circuit_breaker() -> CircuitBreaker:
    """
    Get the shared circuit breaker for semantic-search-service hybrid endpoint.
    
    WBS-CPA1.4: Shared circuit breaker for all hybrid search operations.
    
    Returns:
        CircuitBreaker instance configured from settings.
    """
    global _hybrid_search_circuit_breaker
    if _hybrid_search_circuit_breaker is None:
        settings = get_settings()
        _hybrid_search_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
            name="semantic-search-hybrid",
        )
    return _hybrid_search_circuit_breaker


# =============================================================================
# Exceptions (AP-5 compliance: {Service}Error prefix)
# =============================================================================


class HybridSearchServiceError(Exception):
    """Raised when the hybrid search service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS-CPA1.4: Tool Definition
# =============================================================================


HYBRID_SEARCH_DEFINITION = ToolDefinition(
    name=TOOL_NAME,
    description="Execute a hybrid search combining vector similarity and graph relationships. "
    "Returns results ranked by a weighted combination of semantic similarity (vector) and "
    "structural relationships (graph). Use this for complex queries requiring contextual understanding.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant content.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10).",
                "default": 10,
            },
            "alpha": {
                "type": "number",
                "description": "Weight for vector vs graph score: 0.0 (all graph) to 1.0 (all vector). Default: 0.7.",
                "default": 0.7,
            },
            "collection": {
                "type": "string",
                "description": "The document collection to search (default: 'documents').",
                "default": "documents",
            },
            "include_graph": {
                "type": "boolean",
                "description": "Whether to include graph-based scoring (default: true).",
                "default": True,
            },
            "tier_filter": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Filter to specific taxonomy tiers (1=Architecture, 2=Implementation, 3=Engineering).",
            },
            "focus_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Focus areas for domain-aware filtering (e.g., 'llm_rag', 'microservices').",
            },
        },
        "required": ["query"],
    },
)


# =============================================================================
# WBS-CPA1.4: Internal HTTP Function
# =============================================================================


async def _do_hybrid_search(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP hybrid search request.
    
    Separated for circuit breaker wrapping.
    
    Args:
        base_url: Base URL of semantic-search-service.
        payload: Request payload matching HybridSearchRequest schema.
        timeout_seconds: Request timeout.
        
    Returns:
        Response JSON matching HybridSearchResponse schema.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}{ENDPOINT_PATH}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# WBS-CPA1.4: Hybrid Search Tool Function
# =============================================================================


async def hybrid_search(args: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a hybrid search combining vector similarity and graph relationships.

    WBS-CPA1.4: Implement hybrid_search tool function.
    
    This tool proxies requests from external clients (MCP, external LLMs) through
    the Gateway to the semantic-search-service. Internal platform services call
    semantic-search-service directly.

    Args:
        args: Dictionary containing:
            - query (str): The search query.
            - limit (int, optional): Max results to return (default: 10).
            - alpha (float, optional): Vector vs graph weight (default: 0.7).
            - collection (str, optional): Collection to search (default: 'documents').
            - include_graph (bool, optional): Include graph scoring (default: True).
            - tier_filter (list[int], optional): Filter to taxonomy tiers.
            - focus_areas (list[str], optional): Domain-aware focus areas.

    Returns:
        Dictionary containing hybrid search results with:
            - results: List of matching items with id, score, vector_score, graph_score, payload.
            - total: Total number of results.
            - query: Original query text.
            - alpha: Alpha value used for scoring.
            - latency_ms: Search latency in milliseconds.

    Raises:
        HybridSearchServiceError: If the semantic search service is unavailable.
        CircuitOpenError: If the circuit breaker is open (service failing).
    """
    settings = get_settings()
    base_url = settings.semantic_search_url
    timeout_seconds = settings.semantic_search_timeout_seconds
    circuit_breaker = get_hybrid_search_circuit_breaker()

    # Extract parameters with defaults
    query = args.get("query", "")
    limit = args.get("limit", 10)
    alpha = args.get("alpha", 0.7)
    collection = args.get("collection", "documents")
    include_graph = args.get("include_graph", True)
    tier_filter = args.get("tier_filter")
    focus_areas = args.get("focus_areas")

    # Build request payload - matches HybridSearchRequest schema
    payload: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "alpha": alpha,
        "collection": collection,
        "include_graph": include_graph,
    }
    
    # Add optional parameters if provided
    if tier_filter is not None:
        payload["tier_filter"] = tier_filter
    if focus_areas is not None:
        payload["focus_areas"] = focus_areas

    logger.debug(
        f"Hybrid search: query='{query[:50]}...', "
        f"limit={limit}, alpha={alpha}, include_graph={include_graph}"
    )

    try:
        # Use circuit breaker for resilience
        result = await circuit_breaker.call(
            _do_hybrid_search,
            base_url,
            payload,
            timeout_seconds,
        )
        return result

    except CircuitOpenError as e:
        logger.warning(f"Circuit breaker open for semantic-search hybrid: {e}")
        raise HybridSearchServiceError(
            "Hybrid search service circuit open - failing fast"
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Hybrid search timeout after {timeout_seconds}s: {e}")
        raise HybridSearchServiceError(
            f"Hybrid search timeout after {timeout_seconds} seconds"
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error(f"Hybrid search HTTP error: {e.response.status_code}")
        raise HybridSearchServiceError(
            f"Hybrid search error: HTTP {e.response.status_code}"
        ) from e

    except httpx.RequestError as e:
        logger.error(f"Hybrid search connection error: {e}")
        raise HybridSearchServiceError(
            f"Hybrid search service unavailable: {e}"
        ) from e

    except Exception as e:
        logger.error(f"Hybrid search unexpected error: {e}")
        raise HybridSearchServiceError(
            f"Hybrid search error: {e}"
        ) from e
