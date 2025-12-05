"""
Chunk Retrieval Tool - WBS 2.4.3.2 Chunk Retrieval Tool

This module implements the get_chunk tool that retrieves individual document
chunks from the semantic-search-service.

Reference Documents:
- ARCHITECTURE.md Line 53: chunk_retrieval.py "Document chunk retrieval"
- ARCHITECTURE.md Line 232: semantic-search-service dependency
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
# =============================================================================


async def get_chunk(args: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve a document chunk by ID.

    WBS 2.4.3.2.2: Implement get_chunk tool function.
    WBS 2.4.3.2.3: Accept chunk_id parameter.
    WBS 2.4.3.2.4: Call semantic-search-service to retrieve chunk.
    WBS 2.4.3.2.5: Return chunk text and metadata.
    WBS 2.4.3.2.6: Handle not found errors.

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
    """
    settings = get_settings()
    base_url = settings.semantic_search_url

    chunk_id = args.get("chunk_id", "")

    if not chunk_id:
        raise ChunkNotFoundError("empty")

    logger.debug(f"Retrieving chunk: {chunk_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/v1/chunks/{chunk_id}",
            )
            response.raise_for_status()
            return response.json()

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
