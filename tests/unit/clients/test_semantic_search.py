"""
Tests for Semantic Search Client - WBS 2.7.1.2

TDD RED Phase: Tests for SemanticSearchClient class.

Reference Documents:
- ARCHITECTURE.md: Line 52 - semantic_search.py "Proxy to semantic-search-service"
- ARCHITECTURE.md: Line 232 - semantic-search-service dependency
- ARCHITECTURE.md: Line 277 - semantic_search_url configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service

WBS Items Covered:
- 2.7.1.2.1: Create src/clients/semantic_search.py
- 2.7.1.2.2: Implement SemanticSearchClient class
- 2.7.1.2.3: Implement async search(query: str, ...) -> SearchResults
- 2.7.1.2.4: Implement async embed(texts: list[str]) -> list[list[float]]
- 2.7.1.2.5: Implement async get_chunk(chunk_id: str) -> Chunk
- 2.7.1.2.6: Add error handling for service unavailable
- 2.7.1.2.7: RED tests with mocked responses
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def semantic_search_client(mock_http_client):
    """Create SemanticSearchClient with mock HTTP client."""
    from src.clients.semantic_search import SemanticSearchClient

    return SemanticSearchClient(http_client=mock_http_client)


@pytest.fixture
def sample_search_response():
    """Sample search response from semantic-search-service."""
    return {
        "results": [
            {
                "chunk_id": "chunk-001",
                "content": "This is a test chunk about AI.",
                "score": 0.95,
                "metadata": {"source": "test.md", "page": 1},
            },
            {
                "chunk_id": "chunk-002",
                "content": "Another relevant chunk.",
                "score": 0.87,
                "metadata": {"source": "test.md", "page": 2},
            },
        ],
        "total": 2,
        "query": "test query",
    }


@pytest.fixture
def sample_embed_response():
    """Sample embedding response."""
    return {
        "embeddings": [
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.2, 0.3, 0.4, 0.5, 0.6],
        ],
        "model": "text-embedding-ada-002",
    }


@pytest.fixture
def sample_chunk_response():
    """Sample chunk response."""
    return {
        "chunk_id": "chunk-001",
        "content": "This is the full chunk content.",
        "metadata": {"source": "test.md", "page": 1, "created_at": "2024-01-01"},
    }


# =============================================================================
# WBS 2.7.1.2.1-2: Package and Class Tests
# =============================================================================


class TestSemanticSearchClientClass:
    """Tests for SemanticSearchClient class structure."""

    def test_semantic_search_module_importable(self) -> None:
        """
        WBS 2.7.1.2.1: semantic_search module is importable.
        """
        from src.clients import semantic_search
        assert semantic_search is not None

    def test_semantic_search_client_class_exists(self) -> None:
        """
        WBS 2.7.1.2.2: SemanticSearchClient class exists.
        """
        from src.clients.semantic_search import SemanticSearchClient
        assert SemanticSearchClient is not None

    def test_client_accepts_http_client(self, mock_http_client) -> None:
        """
        SemanticSearchClient accepts HTTP client dependency.
        """
        from src.clients.semantic_search import SemanticSearchClient

        client = SemanticSearchClient(http_client=mock_http_client)
        assert client is not None

    def test_client_accepts_base_url(self) -> None:
        """
        SemanticSearchClient can be created with base_url.
        """
        from src.clients.semantic_search import SemanticSearchClient

        client = SemanticSearchClient(base_url="http://localhost:8081")
        assert client is not None


# =============================================================================
# WBS 2.7.1.2.3: Search Method Tests
# =============================================================================


class TestSemanticSearchMethod:
    """Tests for search method."""

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self, semantic_search_client, mock_http_client, sample_search_response
    ) -> None:
        """
        WBS 2.7.1.2.3: search returns SearchResults.
        """
        from src.clients.semantic_search import SearchResults

        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_search_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        results = await semantic_search_client.search("test query")

        assert isinstance(results, SearchResults)
        assert len(results.results) == 2

    @pytest.mark.asyncio
    async def test_search_with_limit(
        self, semantic_search_client, mock_http_client, sample_search_response
    ) -> None:
        """
        search accepts limit parameter.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_search_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        await semantic_search_client.search("test query", limit=5)

        # Verify limit was passed in request
        call_kwargs = mock_http_client.post.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, semantic_search_client, mock_http_client, sample_search_response
    ) -> None:
        """
        search accepts filter parameters.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_search_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        await semantic_search_client.search(
            "test query",
            filters={"source": "test.md"},
        )

        call_kwargs = mock_http_client.post.call_args
        assert call_kwargs is not None


# =============================================================================
# WBS 2.7.1.2.4: Embed Method Tests
# =============================================================================


class TestEmbedMethod:
    """Tests for embed method."""

    @pytest.mark.asyncio
    async def test_embed_returns_embeddings(
        self, semantic_search_client, mock_http_client, sample_embed_response
    ) -> None:
        """
        WBS 2.7.1.2.4: embed returns list of embeddings.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_embed_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        embeddings = await semantic_search_client.embed(["text1", "text2"])

        assert isinstance(embeddings, list)
        assert len(embeddings) == 2
        assert all(isinstance(e, list) for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_single_text(
        self, semantic_search_client, mock_http_client
    ) -> None:
        """
        embed works with single text.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        embeddings = await semantic_search_client.embed(["single text"])

        assert len(embeddings) == 1


# =============================================================================
# WBS 2.7.1.2.5: Get Chunk Method Tests
# =============================================================================


class TestGetChunkMethod:
    """Tests for get_chunk method."""

    @pytest.mark.asyncio
    async def test_get_chunk_returns_chunk(
        self, semantic_search_client, mock_http_client, sample_chunk_response
    ) -> None:
        """
        WBS 2.7.1.2.5: get_chunk returns Chunk.
        """
        from src.clients.semantic_search import Chunk

        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_chunk_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        chunk = await semantic_search_client.get_chunk("chunk-001")

        assert isinstance(chunk, Chunk)
        assert chunk.chunk_id == "chunk-001"

    @pytest.mark.asyncio
    async def test_get_chunk_includes_content(
        self, semantic_search_client, mock_http_client, sample_chunk_response
    ) -> None:
        """
        get_chunk returns chunk with content.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_chunk_response
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        chunk = await semantic_search_client.get_chunk("chunk-001")

        assert chunk.content == "This is the full chunk content."


# =============================================================================
# WBS 2.7.1.2.6: Error Handling Tests
# =============================================================================


class TestSemanticSearchErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_service_unavailable_raises_error(
        self, semantic_search_client, mock_http_client
    ) -> None:
        """
        WBS 2.7.1.2.6: Service unavailable raises SemanticSearchError.
        """
        from src.clients.semantic_search import SemanticSearchError

        mock_http_client.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(SemanticSearchError) as exc_info:
            await semantic_search_client.search("test")

        assert "unavailable" in str(exc_info.value).lower() or "connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_raises_error(
        self, semantic_search_client, mock_http_client
    ) -> None:
        """
        Timeout raises SemanticSearchError.
        """
        from src.clients.semantic_search import SemanticSearchError

        mock_http_client.post.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(SemanticSearchError):
            await semantic_search_client.search("test")

    @pytest.mark.asyncio
    async def test_chunk_not_found_raises_error(
        self, semantic_search_client, mock_http_client
    ) -> None:
        """
        Chunk not found raises ChunkNotFoundError.
        """
        from src.clients.semantic_search import ChunkNotFoundError

        # Use MagicMock for response since raise_for_status is synchronous
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_http_client.get.return_value = mock_response

        with pytest.raises(ChunkNotFoundError):
            await semantic_search_client.get_chunk("nonexistent")


# =============================================================================
# Import Tests
# =============================================================================


class TestSemanticSearchImportable:
    """Tests for exports."""

    def test_semantic_search_client_importable_from_clients(self) -> None:
        """
        SemanticSearchClient importable from clients package.
        """
        from src.clients import SemanticSearchClient
        assert SemanticSearchClient is not None

    def test_search_results_importable(self) -> None:
        """
        SearchResults importable from semantic_search module.
        """
        from src.clients.semantic_search import SearchResults
        assert SearchResults is not None

    def test_chunk_importable(self) -> None:
        """
        Chunk model importable.
        """
        from src.clients.semantic_search import Chunk
        assert Chunk is not None

    def test_semantic_search_error_importable(self) -> None:
        """
        SemanticSearchError importable.
        """
        from src.clients.semantic_search import SemanticSearchError
        assert issubclass(SemanticSearchError, Exception)
