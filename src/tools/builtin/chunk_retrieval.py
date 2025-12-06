"""
Chunk Retrieval Tool - WBS 2.4.3.2 Chunk Retrieval Tool

This module implements the get_chunk tool that retrieves individual document
chunks from the semantic-search-service.

Reference Documents:
- ARCHITECTURE.md Line 53: chunk_retrieval.py "Document chunk retrieval"
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1440: Async retrieval pipelines
- WBS 3.2.3: Error handling and resilience with circuit breaker

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience (Newman pp. 357-358)
"""

import logging
from typing import Any

import httpx

from src.clients.circuit_breaker import CircuitOpenError
from src.core.config import get_settings
from src.models.domain import ToolDefinition
# WBS 3.2.3.1.5: Share circuit breaker with semantic_search.py
from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker

logger = logging.getLogger(__name__)


# =============================================================================
# WBS 3.2.3.1.5: Shared circuit breaker getter (alias for consistency)
# =============================================================================


def get_chunk_circuit_breaker():
    """
    Get the circuit breaker for chunk retrieval.
    
    WBS 3.2.3.1.5: Uses the same circuit breaker as search_corpus
    since both use the semantic-search-service.
    """
    return get_semantic_search_circuit_breaker()


# =============================================================================
# Exceptions
# =============================================================================


class ChunkNotFoundError(Exception):
    """Raised when a requested chunk is not found."""

    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id
        super().__init__(f"Chunk not found: {chunk_id}")


class ChunkServiceError(Exception):
    """Raised when the chunk retrieval service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 2.4.3.2: Tool Definition
# =============================================================================


GET_CHUNK_DEFINITION = ToolDefinition(
    name="get_chunk",
    description="Retrieve a specific document chunk by its ID. "
    "Returns the chunk content and associated metadata.",
    parameters={
        "type": "object",
        "properties": {
            "chunk_id": {
                "type": "string",
                "description": "The unique identifier of the chunk to retrieve.",
            },
        },
        "required": ["chunk_id"],
    },
)


# =============================================================================
# WBS 2.4.3.2.2: get_chunk Tool Function
# WBS 3.2.3: Integrated with circuit breaker and configurable timeout
# =============================================================================


async def _do_get_chunk(
    base_url: str,
    chunk_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP chunk retrieval.
    
    Separated for circuit breaker wrapping.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(
            f"{base_url}/v1/chunks/{chunk_id}",
        )
        response.raise_for_status()
        return response.json()


async def get_chunk(args: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve a document chunk by ID.

    WBS 2.4.3.2.2: Implement get_chunk tool function.
    WBS 2.4.3.2.3: Accept chunk_id parameter.
    WBS 2.4.3.2.4: Call semantic-search-service to retrieve chunk.
    WBS 2.4.3.2.5: Return chunk text and metadata.
    WBS 2.4.3.2.6: Handle not found errors.
    WBS 3.2.3.1: Circuit breaker integration for resilience.
    WBS 3.2.3.2: Configurable timeout from settings.

    Args:
        args: Dictionary containing:
            - chunk_id (str): The unique identifier of the chunk.

    Returns:
        Dictionary containing:
            - chunk_id: The chunk's unique identifier.
            - content: The chunk's text content.
            - metadata: Associated metadata (source, page, etc.).

    Raises:
        ChunkNotFoundError: If the chunk is not found.
        ChunkServiceError: If the service is unavailable.
        CircuitOpenError: If the circuit breaker is open (service failing).
    """
    settings = get_settings()
    base_url = settings.semantic_search_url
    timeout_seconds = settings.semantic_search_timeout_seconds
    circuit_breaker = get_chunk_circuit_breaker()

    chunk_id = args.get("chunk_id", "")

    if not chunk_id:
        raise ChunkNotFoundError("empty")

    logger.debug(f"Retrieving chunk: {chunk_id}")

    try:
        # WBS 3.2.3.1: Use circuit breaker for resilience
        result = await circuit_breaker.call(
            _do_get_chunk,
            base_url,
            chunk_id,
            timeout_seconds,
        )
        return result

    except CircuitOpenError as e:
        logger.warning(f"Circuit breaker open for semantic-search-service: {e}")
        raise ChunkServiceError(
            f"Chunk service circuit open - failing fast"
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Chunk service timeout after {timeout_seconds}s: {e}")
        raise ChunkServiceError(
            f"Chunk service timeout after {timeout_seconds} seconds"
        ) from e

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"Chunk not found: {chunk_id}")
            raise ChunkNotFoundError(chunk_id) from e

        logger.error(f"Chunk service HTTP error: {e.response.status_code}")
        raise ChunkServiceError(
            f"Chunk service error: HTTP {e.response.status_code}"
        ) from e

    except httpx.RequestError as e:
        logger.error(f"Chunk service connection error: {e}")
        raise ChunkServiceError(
            f"Chunk service unavailable: {e}"
        ) from e

    except Exception as e:
        logger.error(f"Chunk service unexpected error: {e}")
        raise ChunkServiceError(
            f"Chunk service error: {e}"
        ) from e
