"""
Tests for Hybrid Search Tool - WBS-CPA1.3 Hybrid Search Tool

TDD RED Phase: Tests for hybrid_search tool that proxies to semantic-search-service.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA1 Gateway External Tool Exposure
- semantic-search-service/src/api/routes.py: /v1/search/hybrid endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

WBS Items Covered:
- CPA1.3: Write tests for Gateway `hybrid_search` tool
- CPA1.4: Implement `hybrid_search` tool in Gateway

Anti-Patterns Avoided (per CODING_PATTERNS_ANALYSIS.md):
- S3457: No empty f-strings
- S7503: No async without await
- S1066: No nested if statements
- AP-1: Tool names as constants
- AP-2: Tool methods <15 CC
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx


# =============================================================================
# WBS-CPA1.3: Module and Class Tests
# =============================================================================


class TestHybridSearchModuleStructure:
    """Tests for hybrid_search module structure."""

    def test_hybrid_search_module_importable(self) -> None:
        """
        WBS-CPA1.3: hybrid_search module is importable.
        """
        from src.tools.builtin import hybrid_search
        assert hybrid_search is not None

    def test_hybrid_search_function_exists(self) -> None:
        """
        WBS-CPA1.3: hybrid_search function exists.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        assert callable(hybrid_search)

    def test_hybrid_search_definition_exists(self) -> None:
        """
        WBS-CPA1.3: HYBRID_SEARCH_DEFINITION exists with correct structure.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        assert HYBRID_SEARCH_DEFINITION.name == "hybrid_search"
        assert "hybrid" in HYBRID_SEARCH_DEFINITION.description.lower()
        assert HYBRID_SEARCH_DEFINITION.parameters is not None
        assert "query" in HYBRID_SEARCH_DEFINITION.parameters.get("properties", {})

    def test_hybrid_search_error_class_exists(self) -> None:
        """
        WBS-CPA1.3: HybridSearchServiceError exception class exists.
        """
        from src.tools.builtin.hybrid_search import HybridSearchServiceError
        
        assert issubclass(HybridSearchServiceError, Exception)


# =============================================================================
# WBS-CPA1.3: Tool Definition Tests
# =============================================================================


class TestHybridSearchDefinition:
    """Tests for HYBRID_SEARCH_DEFINITION."""

    def test_definition_has_required_parameters(self) -> None:
        """
        WBS-CPA1.3: Definition includes required parameters.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        params = HYBRID_SEARCH_DEFINITION.parameters
        properties = params.get("properties", {})
        required = params.get("required", [])
        
        # Required parameter
        assert "query" in required
        
        # Optional parameters
        assert "limit" in properties
        assert "alpha" in properties
        assert "collection" in properties
        assert "include_graph" in properties

    def test_definition_parameter_defaults(self) -> None:
        """
        WBS-CPA1.3: Parameters have appropriate defaults.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        properties = HYBRID_SEARCH_DEFINITION.parameters.get("properties", {})
        
        assert properties["limit"].get("default") == 10
        assert properties["alpha"].get("default") == pytest.approx(0.7)
        assert properties["collection"].get("default") == "documents"
        assert properties["include_graph"].get("default") is True


# =============================================================================
# WBS-CPA1.4: Hybrid Search Function Tests
# =============================================================================


class TestHybridSearchFunction:
    """Tests for hybrid_search tool function."""

    @pytest.mark.asyncio
    async def test_hybrid_search_basic_query(self) -> None:
        """
        WBS-CPA1.4: hybrid_search accepts query and returns results.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [
                {
                    "id": "doc-001",
                    "score": 0.95,
                    "vector_score": 0.9,
                    "graph_score": 0.8,
                    "payload": {"title": "Test Document", "content": "Test content"},
                }
            ],
            "total": 1,
            "query": "test query",
            "alpha": 0.7,
            "latency_ms": 50.5,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await hybrid_search({"query": "test query"})
            
            assert result["total"] == 1
            assert len(result["results"]) == 1
            assert result["results"][0]["id"] == "doc-001"

    @pytest.mark.asyncio
    async def test_hybrid_search_with_all_parameters(self) -> None:
        """
        WBS-CPA1.4: hybrid_search accepts all optional parameters.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [],
            "total": 0,
            "query": "advanced query",
            "alpha": 0.5,
            "latency_ms": 30.0,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({
                "query": "advanced query",
                "limit": 20,
                "alpha": 0.5,
                "collection": "textbooks",
                "include_graph": False,
            })
            
            # Verify parameters passed to internal function
            call_args = mock_search.call_args
            payload = call_args[0][1]  # Second positional arg is payload
            
            assert payload["query"] == "advanced query"
            assert payload["limit"] == 20
            assert payload["alpha"] == pytest.approx(0.5)
            assert payload["collection"] == "textbooks"
            assert payload["include_graph"] is False

    @pytest.mark.asyncio
    async def test_hybrid_search_default_parameters(self) -> None:
        """
        WBS-CPA1.4: hybrid_search uses correct defaults.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [],
            "total": 0,
            "query": "test",
            "alpha": 0.7,
            "latency_ms": 25.0,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({"query": "test"})
            
            call_args = mock_search.call_args
            payload = call_args[0][1]
            
            assert payload["limit"] == 10
            assert payload["alpha"] == pytest.approx(0.7)
            assert payload["collection"] == "documents"
            assert payload["include_graph"] is True


# =============================================================================
# WBS-CPA1.4: Error Handling Tests
# =============================================================================


class TestHybridSearchErrorHandling:
    """Tests for hybrid_search error handling."""

    @pytest.mark.asyncio
    async def test_hybrid_search_timeout_error(self) -> None:
        """
        WBS-CPA1.4: hybrid_search handles timeout gracefully.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = httpx.TimeoutException("Connection timed out")
            
            with patch("src.tools.builtin.hybrid_search.get_hybrid_search_circuit_breaker") as mock_cb:
                mock_cb_instance = AsyncMock()
                mock_cb_instance.call.side_effect = httpx.TimeoutException("Connection timed out")
                mock_cb.return_value = mock_cb_instance
                
                with pytest.raises(HybridSearchServiceError) as exc_info:
                    await hybrid_search({"query": "test"})
                
                assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_hybrid_search_http_error(self) -> None:
        """
        WBS-CPA1.4: hybrid_search handles HTTP errors.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        
        mock_response = httpx.Response(500, request=httpx.Request("POST", "http://test"))
        
        with patch("src.tools.builtin.hybrid_search.get_hybrid_search_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = httpx.HTTPStatusError(
                "Internal Server Error", request=mock_response.request, response=mock_response
            )
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(HybridSearchServiceError) as exc_info:
                await hybrid_search({"query": "test"})
            
            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_hybrid_search_connection_error(self) -> None:
        """
        WBS-CPA1.4: hybrid_search handles connection errors.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        
        with patch("src.tools.builtin.hybrid_search.get_hybrid_search_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = httpx.RequestError("Connection refused")
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(HybridSearchServiceError) as exc_info:
                await hybrid_search({"query": "test"})
            
            assert "unavailable" in str(exc_info.value).lower()


# =============================================================================
# WBS-CPA1.4: Circuit Breaker Tests
# =============================================================================


class TestHybridSearchCircuitBreaker:
    """Tests for hybrid_search circuit breaker integration."""

    def test_circuit_breaker_singleton(self) -> None:
        """
        WBS-CPA1.4: Circuit breaker is singleton per service.
        """
        from src.tools.builtin.hybrid_search import get_hybrid_search_circuit_breaker
        
        # Reset the singleton for test
        import src.tools.builtin.hybrid_search as module
        module._hybrid_search_circuit_breaker = None
        
        cb1 = get_hybrid_search_circuit_breaker()
        cb2 = get_hybrid_search_circuit_breaker()
        
        assert cb1 is cb2

    def test_circuit_breaker_name(self) -> None:
        """
        WBS-CPA1.4: Circuit breaker has correct name.
        """
        from src.tools.builtin.hybrid_search import get_hybrid_search_circuit_breaker
        
        # Reset the singleton for test
        import src.tools.builtin.hybrid_search as module
        module._hybrid_search_circuit_breaker = None
        
        cb = get_hybrid_search_circuit_breaker()
        
        assert cb.name == "semantic-search-hybrid"

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_error(self) -> None:
        """
        WBS-CPA1.4: Circuit open raises HybridSearchServiceError.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        from src.clients.circuit_breaker import CircuitOpenError
        
        with patch("src.tools.builtin.hybrid_search.get_hybrid_search_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = CircuitOpenError("Circuit is open")
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(HybridSearchServiceError) as exc_info:
                await hybrid_search({"query": "test"})
            
            assert "circuit" in str(exc_info.value).lower()


# =============================================================================
# WBS-CPA1.3: Registration Tests
# =============================================================================


class TestHybridSearchRegistration:
    """Tests for hybrid_search tool registration."""

    def test_hybrid_search_in_builtin_exports(self) -> None:
        """
        WBS-CPA1.3: hybrid_search is exported from builtin package.
        """
        from src.tools.builtin import hybrid_search, HYBRID_SEARCH_DEFINITION
        
        assert callable(hybrid_search)
        assert HYBRID_SEARCH_DEFINITION is not None

    def test_hybrid_search_registered_in_registry(self) -> None:
        """
        WBS-CPA1.3: hybrid_search is registered by register_builtin_tools.
        """
        from src.tools.registry import ToolRegistry
        from src.tools.builtin import register_builtin_tools
        
        registry = ToolRegistry()
        register_builtin_tools(registry)
        
        # Should not raise ToolNotFoundError
        tool = registry.get("hybrid_search")
        assert tool is not None
        assert tool.definition.name == "hybrid_search"
