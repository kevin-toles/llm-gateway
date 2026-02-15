"""
Semantic Search Client - WBS 2.7.1.2

This module provides a client for the semantic-search microservice.

Reference Documents:
- ARCHITECTURE.md: Line 52 - semantic_search.py "Proxy to semantic-search-service"
- ARCHITECTURE.md: Line 232 - semantic-search-service dependency
- ARCHITECTURE.md: Line 277 - semantic_search_url configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service

Pattern: Client adapter for microservice communication
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults
"""

from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from src.clients.http import create_http_client, HTTPClientError


# =============================================================================
# Custom Exceptions - WBS 2.7.1.2.6
# =============================================================================


class SemanticSearchError(HTTPClientError):
    """Exception for semantic search service errors."""

    pass


class ChunkNotFoundError(SemanticSearchError):
    """Exception when a chunk is not found."""

    pass


# =============================================================================
# Response Models - WBS 2.7.1.2.3-5
# =============================================================================


class SearchResult(BaseModel):
    """A single search result from semantic search.

    Attributes:
        chunk_id: Unique identifier for the chunk
        content: Text content of the chunk
        score: Relevance score (0-1)
        metadata: Additional metadata about the chunk
    """

    chunk_id: str = Field(..., description="Chunk identifier")
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class SearchResults(BaseModel):
    """Search results from semantic search service.

    Attributes:
        results: List of search results
        total: Total number of matching results
        query: The original query
    """

    results: list[SearchResult] = Field(default_factory=list, description="Search results")
    total: int = Field(default=0, description="Total results")
    query: str = Field(default="", description="Original query")


class Chunk(BaseModel):
    """A document chunk from the semantic search service.

    Attributes:
        chunk_id: Unique identifier for the chunk
        content: Full text content of the chunk
        metadata: Additional metadata about the chunk
    """

    chunk_id: str = Field(..., description="Chunk identifier")
    content: str = Field(..., description="Chunk content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


# =============================================================================
# WBS 2.7.1.2.2: SemanticSearchClient Class
# =============================================================================


class SemanticSearchClient:
    """
    Client for the semantic-search microservice.

    WBS 2.7.1.2.2: Implement SemanticSearchClient class.

    This client provides methods to:
    - Search for relevant chunks (WBS 2.7.1.2.3)
    - Generate embeddings (WBS 2.7.1.2.4)
    - Retrieve specific chunks (WBS 2.7.1.2.5)

    Pattern: Client adapter for microservice communication
    Reference: ARCHITECTURE.md Line 232 - semantic-search-service dependency

    Example:
        >>> client = SemanticSearchClient(base_url="http://localhost:8081")
        >>> results = await client.search("What is machine learning?")
        >>> for result in results.results:
        ...     print(result.content)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Initialize SemanticSearchClient.

        Args:
            base_url: Base URL for semantic-search-service
            http_client: Optional pre-configured HTTP client (for testing)
            timeout_seconds: Request timeout in seconds
        """
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = create_http_client(
                base_url=base_url or "http://localhost:8081",
                timeout_seconds=timeout_seconds,
            )
            self._owns_client = True

    async def close(self) -> None:
        """Close the HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "SemanticSearchClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # WBS 2.7.1.2.3: Search Method
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> SearchResults:
        """
        Search for relevant chunks.

        WBS 2.7.1.2.3: Implement async search(query: str, ...) -> SearchResults.

        Args:
            query: Search query string
            limit: Maximum number of results to return
            filters: Optional filters to apply (e.g., {"source": "doc.md"})

        Returns:
            SearchResults containing matching chunks

        Raises:
            SemanticSearchError: If the service is unavailable or returns an error
        """
        try:
            payload = {
                "query": query,
                "limit": limit,
            }
            if filters:
                payload["filters"] = filters

            response = await self._client.post("/search", json=payload)
            response.raise_for_status()

            data = response.json()
            return SearchResults(
                results=[SearchResult(**r) for r in data.get("results", [])],
                total=data.get("total", 0),
                query=data.get("query", query),
            )

        except httpx.ConnectError as e:
            raise SemanticSearchError(f"Semantic search service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise SemanticSearchError(f"Semantic search request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise SemanticSearchError(f"Semantic search error: {e}") from e
        except Exception as e:
            raise SemanticSearchError(f"Semantic search failed: {e}") from e

    # =========================================================================
    # WBS 2.7.1.2.4: Embed Method
    # =========================================================================

    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for texts.

        WBS 2.7.1.2.4: Implement async embed(texts: list[str]) -> list[list[float]].

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            SemanticSearchError: If the service is unavailable or returns an error
        """
        try:
            payload = {"texts": texts}

            response = await self._client.post("/embed", json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get("embeddings", [])

        except httpx.ConnectError as e:
            raise SemanticSearchError(f"Semantic search service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise SemanticSearchError(f"Embed request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise SemanticSearchError(f"Embed error: {e}") from e
        except Exception as e:
            raise SemanticSearchError(f"Embed failed: {e}") from e

    # =========================================================================
    # WBS 2.7.1.2.5: Get Chunk Method
    # =========================================================================

    async def get_chunk(
        self,
        chunk_id: str,
    ) -> Chunk:
        """
        Retrieve a specific chunk by ID.

        WBS 2.7.1.2.5: Implement async get_chunk(chunk_id: str) -> Chunk.

        Args:
            chunk_id: Unique identifier of the chunk

        Returns:
            Chunk object with full content

        Raises:
            ChunkNotFoundError: If the chunk does not exist
            SemanticSearchError: If the service is unavailable or returns an error
        """
        try:
            response = await self._client.get(f"/chunks/{chunk_id}")
            response.raise_for_status()

            data = response.json()
            return Chunk(
                chunk_id=data.get("chunk_id", chunk_id),
                content=data.get("content", ""),
                metadata=data.get("metadata", {}),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ChunkNotFoundError(f"Chunk not found: {chunk_id}") from e
            raise SemanticSearchError(f"Get chunk error: {e}") from e
        except httpx.ConnectError as e:
            raise SemanticSearchError(f"Semantic search service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise SemanticSearchError(f"Get chunk request timed out: {e}") from e
        except Exception as e:
            raise SemanticSearchError(f"Get chunk failed: {e}") from e
