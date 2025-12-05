"""
Semantic Search Tool - WBS 2.4.3.1 Semantic Search Tool

This module implements the search_corpus tool that proxies search requests
to the semantic-search-service.

Reference Documents:
- ARCHITECTURE.md Line 52: semantic_search.py "Proxy to semantic-search-service"
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391: RAG systems and retrieval patterns
- GUIDELINES pp. 1440: Async retrieval pipelines

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
"""

import logging
from typing import Any

import httpx

from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


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
# =============================================================================


async def search_corpus(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search the document corpus for relevant content.

    WBS 2.4.3.1.3: Implement search_corpus tool function.
    WBS 2.4.3.1.4: Accept query, top_k, collection parameters.
    WBS 2.4.3.1.5: Call semantic-search-service /v1/search endpoint.
    WBS 2.4.3.1.6: Return search results as structured data.
    WBS 2.4.3.1.7: Handle service unavailable errors.

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
    """
    settings = get_settings()
    base_url = settings.semantic_search_url

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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/v1/search",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

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
