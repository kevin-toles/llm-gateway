"""
Semantic Search Tool - WBS 2.4.3.1 Semantic Search Tool

This module implements the search_corpus tool that proxies search requests
to the semantic-search-service.

Reference Documents:
- ARCHITECTURE.md Line 52: semantic_search.py "Proxy to semantic-search-service"
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391: RAG systems and retrieval patterns
- GUIDELINES pp. 1440: Async retrieval pipelines
- WBS 3.2.3: Error handling and resilience with circuit breaker

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience (Newman pp. 357-358)
"""

import logging
from typing import Any, Optional

import httpx

from src.clients.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# WBS 3.2.3.1: Shared Circuit Breaker for Semantic Search Service
# Pattern: Singleton circuit breaker per downstream service
# =============================================================================

_semantic_search_circuit_breaker: Optional[CircuitBreaker] = None


def get_semantic_search_circuit_breaker() -> CircuitBreaker:
    """
    Get the shared circuit breaker for semantic-search-service.
    
    WBS 3.2.3.1.5: Shared circuit breaker for all semantic search operations.
    
    Returns:
        CircuitBreaker instance configured from settings.
    """
    global _semantic_search_circuit_breaker
    if _semantic_search_circuit_breaker is None:
        settings = get_settings()
        _semantic_search_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
            name="semantic-search-service",
        )
    return _semantic_search_circuit_breaker


# =============================================================================
# Exceptions
# =============================================================================


class SearchServiceError(Exception):
    """Raised when the semantic search service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 2.4.3.1: Tool Definition
# =============================================================================


SEARCH_CORPUS_DEFINITION = ToolDefinition(
    name="search_corpus",
    description="Search the document corpus for relevant content using semantic similarity. "
    "Returns the most relevant chunks matching the query.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant documents.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10).",
                "default": 10,
            },
            "collection": {
                "type": "string",
                "description": "The document collection to search (default: 'default').",
                "default": "default",
            },
        },
        "required": ["query"],
    },
)


# =============================================================================
# WBS 2.4.3.1.3: search_corpus Tool Function
# WBS 3.2.3: Integrated with circuit breaker and configurable timeout
# =============================================================================


async def _do_search(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP search request.
    
    Separated for circuit breaker wrapping.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/v1/search",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def search_corpus(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search the document corpus for relevant content.

    WBS 2.4.3.1.3: Implement search_corpus tool function.
    WBS 2.4.3.1.4: Accept query, top_k, collection parameters.
    WBS 2.4.3.1.5: Call semantic-search-service /v1/search endpoint.
    WBS 2.4.3.1.6: Return search results as structured data.
    WBS 2.4.3.1.7: Handle service unavailable errors.
    WBS 3.2.3.1: Circuit breaker integration for resilience.
    WBS 3.2.3.2: Configurable timeout from settings.

    Args:
        args: Dictionary containing:
            - query (str): The search query.
            - top_k (int, optional): Max results to return (default: 10).
            - collection (str, optional): Collection to search (default: 'default').

    Returns:
        Dictionary containing search results with:
            - results: List of matching chunks with chunk_id, content, score, metadata.
            - total: Total number of results.

    Raises:
        SearchServiceError: If the semantic search service is unavailable.
        CircuitOpenError: If the circuit breaker is open (service failing).
    """
    settings = get_settings()
    base_url = settings.semantic_search_url
    timeout_seconds = settings.semantic_search_timeout_seconds
    circuit_breaker = get_semantic_search_circuit_breaker()

    # Extract parameters with defaults
    query = args.get("query", "")
    top_k = args.get("top_k", 10)
    collection = args.get("collection", "default")

    # Build request payload
    payload = {
        "query": query,
        "top_k": top_k,
        "collection": collection,
    }

    logger.debug(f"Searching corpus: query='{query[:50]}...', top_k={top_k}")

    try:
        # WBS 3.2.3.1: Use circuit breaker for resilience
        result = await circuit_breaker.call(
            _do_search,
            base_url,
            payload,
            timeout_seconds,
        )
        return result

    except CircuitOpenError as e:
        logger.warning(f"Circuit breaker open for semantic-search-service: {e}")
        raise SearchServiceError(
            f"Semantic search service circuit open - failing fast"
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Search service timeout after {timeout_seconds}s: {e}")
        raise SearchServiceError(
            f"Search service timeout after {timeout_seconds} seconds"
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error(f"Search service HTTP error: {e.response.status_code}")
        raise SearchServiceError(
            f"Search service error: HTTP {e.response.status_code}"
        ) from e

    except httpx.RequestError as e:
        logger.error(f"Search service connection error: {e}")
        raise SearchServiceError(
            f"Search service unavailable: {e}"
        ) from e

    except Exception as e:
        logger.error(f"Search service unexpected error: {e}")
        raise SearchServiceError(
            f"Search service error: {e}"
        ) from e
