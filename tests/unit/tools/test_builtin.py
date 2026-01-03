"""
Test Suite for Built-in Tools - WBS 2.4.3 Built-in Tools

TDD RED Phase: Tests written before implementation.

Reference Documents:
- ARCHITECTURE.md Lines 50-53: builtin/semantic_search.py, chunk_retrieval.py
- ARCHITECTURE.md Line 232: semantic-search-service dependency
- GUIDELINES pp. 1391-1440: RAG patterns, async retrieval pipelines

Test Categories:
1. TestSemanticSearchTool - search_corpus tool (2.4.3.1)
2. TestChunkRetrievalTool - get_chunk tool (2.4.3.2)
3. TestBuiltinToolsImports - Import verification
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings with semantic_search_url."""
    settings = MagicMock()
    settings.semantic_search_url = "http://localhost:8081"
    return settings


@pytest.fixture
def mock_search_response() -> dict:
    """Mock response from semantic-search-service /v1/search endpoint."""
    return {
        "results": [
            {
                "chunk_id": "chunk_001",
                "content": "Python is a high-level programming language.",
                "score": 0.95,
                "metadata": {"source": "docs/python.md", "page": 1},
            },
            {
                "chunk_id": "chunk_002",
                "content": "Python supports multiple programming paradigms.",
                "score": 0.87,
                "metadata": {"source": "docs/python.md", "page": 2},
            },
        ],
        "total": 2,
    }


@pytest.fixture
def mock_chunk_response() -> dict:
    """Mock response from semantic-search-service /v1/chunks/{id} endpoint."""
    return {
        "chunk_id": "chunk_001",
        "content": "Python is a high-level programming language.",
        "metadata": {"source": "docs/python.md", "page": 1, "created_at": "2025-01-01"},
    }


# =============================================================================
# WBS 2.4.3.1: TestSemanticSearchTool
# =============================================================================


class TestSemanticSearchTool:
    """Tests for semantic search tool - WBS 2.4.3.1."""

    def test_search_corpus_function_exists(self) -> None:
        """WBS 2.4.3.1.3: search_corpus function is importable."""
        from src.tools.builtin.semantic_search import search_corpus

        assert callable(search_corpus)

    def test_search_corpus_tool_definition_exists(self) -> None:
        """WBS 2.4.3.1: search_corpus has a tool definition."""
        from src.tools.builtin.semantic_search import SEARCH_CORPUS_DEFINITION

        assert SEARCH_CORPUS_DEFINITION is not None
        assert SEARCH_CORPUS_DEFINITION.name == "search_corpus"

    def test_search_corpus_definition_has_parameters(self) -> None:
        """WBS 2.4.3.1.4: Definition includes query, top_k, collection parameters."""
        from src.tools.builtin.semantic_search import SEARCH_CORPUS_DEFINITION

        params = SEARCH_CORPUS_DEFINITION.parameters
        props = params.get("properties", {})

        assert "query" in props
        assert "top_k" in props
        assert "collection" in props

    @pytest.mark.asyncio
    async def test_search_corpus_returns_results(
        self, mock_settings: MagicMock, mock_search_response: dict
    ) -> None:
        """WBS 2.4.3.1.6,8: search_corpus returns structured results."""
        from src.tools.builtin.semantic_search import search_corpus

        with patch(
            "src.tools.builtin.semantic_search.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.semantic_search.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_corpus(
                {"query": "Python programming", "top_k": 5, "collection": "default"}
            )

            assert "results" in result
            assert len(result["results"]) == 2
            assert result["results"][0]["chunk_id"] == "chunk_001"

    @pytest.mark.asyncio
    async def test_search_corpus_calls_correct_endpoint(
        self, mock_settings: MagicMock, mock_search_response: dict
    ) -> None:
        """WBS 2.4.3.1.5: search_corpus calls /v1/search endpoint."""
        from src.tools.builtin.semantic_search import search_corpus

        with patch(
            "src.tools.builtin.semantic_search.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.semantic_search.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await search_corpus(
                {"query": "test", "top_k": 10, "collection": "docs"}
            )

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "/v1/search" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_search_corpus_uses_default_top_k(
        self, mock_settings: MagicMock, mock_search_response: dict
    ) -> None:
        """search_corpus uses default top_k when not provided."""
        from src.tools.builtin.semantic_search import search_corpus

        with patch(
            "src.tools.builtin.semantic_search.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.semantic_search.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Only query, no top_k
            result = await search_corpus({"query": "test"})

            assert "results" in result

    @pytest.mark.asyncio
    async def test_search_corpus_handles_service_error(
        self, mock_settings: MagicMock
    ) -> None:
        """WBS 2.4.3.1.7,9: search_corpus handles service unavailable errors."""
        from src.tools.builtin.semantic_search import search_corpus, SearchServiceError

        with patch(
            "src.tools.builtin.semantic_search.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.semantic_search.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SearchServiceError) as exc_info:
                await search_corpus({"query": "test"})

            assert "unavailable" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_corpus_handles_http_error(
        self, mock_settings: MagicMock
    ) -> None:
        """search_corpus handles HTTP error responses."""
        from src.tools.builtin.semantic_search import search_corpus, SearchServiceError
        import httpx

        with patch(
            "src.tools.builtin.semantic_search.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.semantic_search.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SearchServiceError):
                await search_corpus({"query": "test"})


# =============================================================================
# WBS 2.4.3.2: TestChunkRetrievalTool
# =============================================================================


class TestChunkRetrievalTool:
    """Tests for chunk retrieval tool - WBS 2.4.3.2."""

    def test_get_chunk_function_exists(self) -> None:
        """WBS 2.4.3.2.2: get_chunk function is importable."""
        from src.tools.builtin.chunk_retrieval import get_chunk

        assert callable(get_chunk)

    def test_get_chunk_tool_definition_exists(self) -> None:
        """WBS 2.4.3.2: get_chunk has a tool definition."""
        from src.tools.builtin.chunk_retrieval import GET_CHUNK_DEFINITION

        assert GET_CHUNK_DEFINITION is not None
        assert GET_CHUNK_DEFINITION.name == "get_chunk"

    def test_get_chunk_definition_has_chunk_id_parameter(self) -> None:
        """WBS 2.4.3.2.3: Definition includes chunk_id parameter."""
        from src.tools.builtin.chunk_retrieval import GET_CHUNK_DEFINITION

        params = GET_CHUNK_DEFINITION.parameters
        props = params.get("properties", {})

        assert "chunk_id" in props
        assert params.get("required") == ["chunk_id"]

    @pytest.mark.asyncio
    async def test_get_chunk_returns_chunk_data(
        self, mock_settings: MagicMock, mock_chunk_response: dict
    ) -> None:
        """WBS 2.4.3.2.5,7: get_chunk returns chunk text and metadata."""
        from src.tools.builtin.chunk_retrieval import get_chunk

        with patch(
            "src.tools.builtin.chunk_retrieval.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.chunk_retrieval.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_chunk_response
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await get_chunk({"chunk_id": "chunk_001"})

            assert result["chunk_id"] == "chunk_001"
            assert "content" in result
            assert "metadata" in result

    @pytest.mark.asyncio
    async def test_get_chunk_calls_correct_endpoint(
        self, mock_settings: MagicMock, mock_chunk_response: dict
    ) -> None:
        """WBS 2.4.3.2.4: get_chunk calls /v1/chunks/{id} endpoint."""
        from src.tools.builtin.chunk_retrieval import get_chunk

        with patch(
            "src.tools.builtin.chunk_retrieval.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.chunk_retrieval.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_chunk_response
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await get_chunk({"chunk_id": "chunk_001"})

            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert "/v1/chunks/chunk_001" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_chunk_handles_not_found(
        self, mock_settings: MagicMock
    ) -> None:
        """WBS 2.4.3.2.6,8: get_chunk handles not found errors."""
        from src.tools.builtin.chunk_retrieval import get_chunk, ChunkNotFoundError
        import httpx

        with patch(
            "src.tools.builtin.chunk_retrieval.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.chunk_retrieval.httpx.AsyncClient"
        ) as mock_client_class:
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

            with pytest.raises(ChunkNotFoundError) as exc_info:
                await get_chunk({"chunk_id": "nonexistent"})

            assert "nonexistent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_chunk_handles_service_error(
        self, mock_settings: MagicMock
    ) -> None:
        """get_chunk handles service unavailable errors."""
        from src.tools.builtin.chunk_retrieval import get_chunk, ChunkServiceError

        with patch(
            "src.tools.builtin.chunk_retrieval.get_settings", return_value=mock_settings
        ), patch(
            "src.tools.builtin.chunk_retrieval.httpx.AsyncClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(ChunkServiceError):
                await get_chunk({"chunk_id": "chunk_001"})


# =============================================================================
# WBS 2.4.3.3: TestToolRegistration
# =============================================================================


class TestToolRegistration:
    """Tests for tool registration - WBS 2.4.3.3."""

    def test_builtin_tools_package_importable(self) -> None:
        """WBS 2.4.3.1.1: builtin package is importable."""
        from src.tools import builtin

        assert builtin is not None

    def test_register_builtin_tools_function_exists(self) -> None:
        """WBS 2.4.3.3.4: register_builtin_tools function exists."""
        from src.tools.builtin import register_builtin_tools

        assert callable(register_builtin_tools)

    def test_register_builtin_tools_registers_search(self) -> None:
        """WBS 2.4.3.3.5: Built-in search tool is registered."""
        from src.tools.builtin import register_builtin_tools
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()
        register_builtin_tools(registry)

        assert registry.has("search_corpus")

    def test_register_builtin_tools_registers_chunk_retrieval(self) -> None:
        """WBS 2.4.3.3.5: Built-in chunk retrieval tool is registered."""
        from src.tools.builtin import register_builtin_tools
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()
        register_builtin_tools(registry)

        assert registry.has("get_chunk")

    def test_registered_tools_have_definitions(self) -> None:
        """Registered tools have proper definitions."""
        from src.tools.builtin import register_builtin_tools
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()
        register_builtin_tools(registry)

        search_tool = registry.get("search_corpus")
        chunk_tool = registry.get("get_chunk")

        assert search_tool.definition.name == "search_corpus"
        assert chunk_tool.definition.name == "get_chunk"


# =============================================================================
# TestBuiltinToolsImports - Import verification
# =============================================================================


class TestBuiltinToolsImports:
    """Tests to verify built-in tools are importable from expected locations."""

    def test_semantic_search_importable(self) -> None:
        """semantic_search module is importable."""
        from src.tools.builtin import semantic_search

        assert semantic_search is not None

    def test_chunk_retrieval_importable(self) -> None:
        """chunk_retrieval module is importable."""
        from src.tools.builtin import chunk_retrieval

        assert chunk_retrieval is not None

    def test_search_corpus_importable_from_builtin(self) -> None:
        """search_corpus is importable from builtin package."""
        from src.tools.builtin import search_corpus

        assert callable(search_corpus)

    def test_get_chunk_importable_from_builtin(self) -> None:
        """get_chunk is importable from builtin package."""
        from src.tools.builtin import get_chunk

        assert callable(get_chunk)


# =============================================================================
# SonarQube Code Quality Fixes - Batch 6 (Issues 47-48)
# =============================================================================


class TestSonarQubeCodeQualityFixesBatch6:
    """
    TDD RED Phase: Tests for SonarQube code smell fixes.
    
    Issue 47: chunk_retrieval.py:165 - f-string without placeholders
    Issue 48: semantic_search.py:187 - f-string without placeholders
    Rule: python:S3457 - Add replacement fields or use a normal string
    
    Reference: CODING_PATTERNS_ANALYSIS.md - NEW pattern for empty f-strings
    """

    def test_chunk_retrieval_error_messages_no_empty_fstrings(self) -> None:
        """
        Issue 47 (S3457): ChunkServiceError messages should not use empty f-strings.
        
        An f-string without any replacement fields should be a regular string.
        This test inspects the source code to verify no f"..." without {}.
        """
        import ast
        import inspect
        from src.tools.builtin import chunk_retrieval
        
        source = inspect.getsource(chunk_retrieval)
        tree = ast.parse(source)
        
        # Find all f-strings (JoinedStr nodes)
        fstrings_without_placeholders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                # An f-string with only Constant values has no placeholders
                has_placeholder = any(
                    isinstance(value, (ast.FormattedValue,))
                    for value in node.values
                )
                if not has_placeholder:
                    # Extract the line number for error message
                    fstrings_without_placeholders.append(node.lineno)
        
        assert len(fstrings_without_placeholders) == 0, (
            f"Found f-strings without placeholders at lines: {fstrings_without_placeholders}. "
            "Remove 'f' prefix from strings that don't use interpolation."
        )

    def test_semantic_search_error_messages_no_empty_fstrings(self) -> None:
        """
        Issue 48 (S3457): SearchServiceError messages should not use empty f-strings.
        
        An f-string without any replacement fields should be a regular string.
        This test inspects the source code to verify no f"..." without {}.
        """
        import ast
        import inspect
        from src.tools.builtin import semantic_search
        
        source = inspect.getsource(semantic_search)
        tree = ast.parse(source)
        
        # Find all f-strings (JoinedStr nodes)
        fstrings_without_placeholders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                # An f-string with only Constant values has no placeholders
                has_placeholder = any(
                    isinstance(value, (ast.FormattedValue,))
                    for value in node.values
                )
                if not has_placeholder:
                    fstrings_without_placeholders.append(node.lineno)
        
        assert len(fstrings_without_placeholders) == 0, (
            f"Found f-strings without placeholders at lines: {fstrings_without_placeholders}. "
            "Remove 'f' prefix from strings that don't use interpolation."
        )

