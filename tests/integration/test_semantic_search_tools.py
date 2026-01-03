"""
Integration Tests for Semantic Search Tools - WBS 3.2.2

Tests the search_corpus and get_chunk tools through the gateway API.

Reference Documents:
- ARCHITECTURE.md Lines 50-53: builtin/semantic_search.py, chunk_retrieval.py
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391-1440: RAG patterns, async retrieval pipelines

WBS Items Covered:
- 3.2.2.1.3: Call search_corpus tool through gateway
- 3.2.2.1.4: Verify search results returned correctly
- 3.2.2.1.5: Test with various query types
- 3.2.2.1.6: Test with different top_k values
- 3.2.2.1.7: Write integration test: search returns relevant results
- 3.2.2.1.8: Write integration test: empty results handled
- 3.2.2.2.1: Call get_chunk tool through gateway
- 3.2.2.2.2: Verify chunk text and metadata returned
- 3.2.2.2.3: Test with valid chunk IDs
- 3.2.2.2.4: Test with invalid chunk IDs (404 handling)
- 3.2.2.2.5: Write integration test: chunk retrieval works
- 3.2.2.2.6: Write integration test: not found handled gracefully

TDD RED Phase: Tests written before wiring tools to API.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def app_with_tools():
    """
    Create FastAPI app with tools router and builtin tools registered.

    Pattern: Integration test fixture (Percival p. 157)
    """
    from src.api.routes.tools import router as tools_router

    app = FastAPI()
    app.include_router(tools_router)
    return app


@pytest.fixture
def client(app_with_tools):
    """Create test client for integration tests."""
    return TestClient(app_with_tools)


@pytest.fixture
def mock_search_response():
    """Mock response from semantic-search-service /v1/search."""
    return {
        "results": [
            {
                "chunk_id": "chunk_001",
                "content": "Python is a high-level programming language known for its readability.",
                "score": 0.95,
                "metadata": {"source": "python_intro.md", "page": 1},
            },
            {
                "chunk_id": "chunk_002",
                "content": "Python supports multiple programming paradigms including OOP.",
                "score": 0.87,
                "metadata": {"source": "python_intro.md", "page": 2},
            },
            {
                "chunk_id": "chunk_003",
                "content": "The Python interpreter is available for major operating systems.",
                "score": 0.82,
                "metadata": {"source": "python_setup.md", "page": 1},
            },
        ],
        "total": 3,
    }


@pytest.fixture
def mock_empty_search_response():
    """Mock empty search response."""
    return {
        "results": [],
        "total": 0,
    }


@pytest.fixture
def mock_chunk_response():
    """Mock response from semantic-search-service /v1/chunks/{id}."""
    return {
        "chunk_id": "chunk_001",
        "content": "Python is a high-level programming language known for its readability.",
        "metadata": {
            "source": "python_intro.md",
            "page": 1,
            "created_at": "2025-01-01T00:00:00Z",
        },
    }


# =============================================================================
# WBS 3.2.2.1: Search Corpus Tool Integration Tests
# =============================================================================


class TestSearchCorpusToolIntegration:
    """
    Integration tests for search_corpus tool through gateway API.

    WBS 3.2.2.1: Search Corpus Tool Testing
    """

    def test_search_corpus_tool_registered(self, client):
        """
        WBS 3.2.2.1.3: search_corpus tool should be available through gateway.

        RED: Expects tool to be registered and listed in /v1/tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200

        data = response.json()
        # Response is a list of tool definitions
        tools = data.get("tools", []) if isinstance(data, dict) else data
        tool_names = [tool["name"] for tool in tools]

        assert "search_corpus" in tool_names, "search_corpus should be registered"

    @pytest.mark.asyncio
    async def test_search_corpus_returns_results(
        self, client, mock_search_response
    ):
        """
        WBS 3.2.2.1.4, 3.2.2.1.7: search_corpus returns relevant results.

        RED: Tool should proxy to semantic-search and return results.
        """
        with patch("src.tools.builtin.semantic_search.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "search_corpus",
                    "arguments": {"query": "Python programming"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["result"]["total"] == 3
            assert len(data["result"]["results"]) == 3

    @pytest.mark.asyncio
    async def test_search_corpus_with_different_queries(
        self, client, mock_search_response
    ):
        """
        WBS 3.2.2.1.5: Test with various query types.

        Tests: short query, long query, technical terms.
        """
        with patch("src.tools.builtin.semantic_search.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            queries = [
                "Python",  # Short query
                "How do I implement a decorator in Python?",  # Long query
                "asyncio event loop",  # Technical terms
            ]

            for query in queries:
                response = client.post(
                    "/v1/tools/execute",
                    json={"name": "search_corpus", "arguments": {"query": query}},
                )
                assert response.status_code == 200, f"Failed for query: {query}"

    @pytest.mark.asyncio
    async def test_search_corpus_with_different_top_k(
        self, client, mock_search_response
    ):
        """
        WBS 3.2.2.1.6: Test with different top_k values.

        Tests: default (10), small (3), large (50).
        """
        with patch("src.tools.builtin.semantic_search.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            top_k_values = [3, 10, 50]

            for top_k in top_k_values:
                response = client.post(
                    "/v1/tools/execute",
                    json={
                        "name": "search_corpus",
                        "arguments": {"query": "test", "top_k": top_k},
                    },
                )
                assert response.status_code == 200, f"Failed for top_k: {top_k}"

                # Verify top_k was passed to service
                call_args = mock_client.post.call_args
                assert call_args[1]["json"]["top_k"] == top_k

    @pytest.mark.asyncio
    async def test_search_corpus_empty_results(
        self, client, mock_empty_search_response
    ):
        """
        WBS 3.2.2.1.8: Empty results handled gracefully.

        RED: Should return success=True with empty results list.
        """
        with patch("src.tools.builtin.semantic_search.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_empty_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "search_corpus",
                    "arguments": {"query": "nonexistent topic xyz123"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["result"]["total"] == 0
            assert data["result"]["results"] == []

    def test_search_corpus_service_unavailable(self, client):
        """
        WBS 3.2.2.1: Handle service unavailability gracefully.

        Pattern: Graceful degradation (Newman pp. 352-353)
        """
        with patch("src.tools.builtin.semantic_search.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "search_corpus",
                    "arguments": {"query": "test"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "unavailable" in data["error"].lower() or "error" in data["error"].lower()


# =============================================================================
# WBS 3.2.2.2: Chunk Retrieval Tool Integration Tests
# =============================================================================


class TestChunkRetrievalToolIntegration:
    """
    Integration tests for get_chunk tool through gateway API.

    WBS 3.2.2.2: Chunk Retrieval Tool Testing
    """

    def test_get_chunk_tool_registered(self, client):
        """
        WBS 3.2.2.2.1: get_chunk tool should be available through gateway.

        RED: Expects tool to be registered and listed in /v1/tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200

        data = response.json()
        # Response is a list of tool definitions
        tools = data.get("tools", []) if isinstance(data, dict) else data
        tool_names = [tool["name"] for tool in tools]

        assert "get_chunk" in tool_names, "get_chunk should be registered"

    @pytest.mark.asyncio
    async def test_get_chunk_returns_content_and_metadata(
        self, client, mock_chunk_response
    ):
        """
        WBS 3.2.2.2.2, 3.2.2.2.5: get_chunk returns chunk text and metadata.

        RED: Tool should proxy to semantic-search and return chunk data.
        """
        with patch("src.tools.builtin.chunk_retrieval.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_chunk_response
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "get_chunk",
                    "arguments": {"chunk_id": "chunk_001"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["result"]["chunk_id"] == "chunk_001"
            assert "content" in data["result"]
            assert "metadata" in data["result"]
            assert data["result"]["metadata"]["source"] == "python_intro.md"

    @pytest.mark.asyncio
    async def test_get_chunk_with_valid_ids(
        self, client, mock_chunk_response
    ):
        """
        WBS 3.2.2.2.3: Test with valid chunk IDs.

        Tests various valid ID formats.
        """
        with patch("src.tools.builtin.chunk_retrieval.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_chunk_response
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            chunk_ids = [
                "chunk_001",
                "doc-12345",
                "uuid-a1b2c3d4",
            ]

            for chunk_id in chunk_ids:
                # Update mock response for each ID
                mock_chunk_response["chunk_id"] = chunk_id

                response = client.post(
                    "/v1/tools/execute",
                    json={"name": "get_chunk", "arguments": {"chunk_id": chunk_id}},
                )
                assert response.status_code == 200, f"Failed for chunk_id: {chunk_id}"

    @pytest.mark.asyncio
    async def test_get_chunk_not_found(self, client):
        """
        WBS 3.2.2.2.4, 3.2.2.2.6: Invalid chunk IDs return not found error.

        RED: Should return success=False with error message.
        """
        import httpx

        with patch("src.tools.builtin.chunk_retrieval.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "get_chunk",
                    "arguments": {"chunk_id": "nonexistent_chunk"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "not found" in data["error"].lower() or "nonexistent" in data["error"].lower()

    def test_get_chunk_service_unavailable(self, client):
        """
        WBS 3.2.2.2: Handle service unavailability gracefully.

        Pattern: Graceful degradation (Newman pp. 352-353)
        """
        with patch("src.tools.builtin.chunk_retrieval.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "get_chunk",
                    "arguments": {"chunk_id": "chunk_001"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data


# =============================================================================
# WBS 3.2.2: Tool Execute Endpoint Integration
# =============================================================================


class TestToolExecuteEndpointIntegration:
    """
    Integration tests for /v1/tools/execute endpoint with semantic tools.

    WBS 3.2.2: Verify tools are properly wired to API.
    """

    def test_execute_endpoint_exists(self, client):
        """Execute endpoint should exist and accept POST."""
        response = client.post(
            "/v1/tools/execute",
            json={"name": "echo", "arguments": {"message": "test"}},
        )
        # Should not be 404 or 405
        assert response.status_code != 404
        assert response.status_code != 405

    def test_execute_unknown_tool_returns_error(self, client):
        """Unknown tool should return 404 error."""
        response = client.post(
            "/v1/tools/execute",
            json={"name": "unknown_tool", "arguments": {}},
        )

        # API returns 404 for unknown tools (HTTPException pattern)
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_execute_missing_required_argument(self, client):
        """Missing required argument should return validation error."""
        response = client.post(
            "/v1/tools/execute",
            json={"name": "search_corpus", "arguments": {}},  # Missing 'query'
        )

        # Either 422 (validation) or 200 with error
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is False


# =============================================================================
# Fixtures for pytest
# =============================================================================


@pytest.fixture(autouse=True)
def reset_tool_executor():
    """Reset tool executor between tests."""
    from src.api.routes import tools as tools_module

    tools_module._tool_executor = None
    yield
    tools_module._tool_executor = None
