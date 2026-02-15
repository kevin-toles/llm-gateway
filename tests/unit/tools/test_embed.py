"""
Tests for Embed Tool - WBS-CPA6 Gateway Tool Invocation

TDD RED Phase: Tests for embed tool that proxies to semantic-search-service.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA6 Gateway Tool Invocation
- semantic-search-service/src/api/embeddings.py: /v1/embeddings endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

WBS Items Covered:
- CPA6.1: Write failing tests for embed tool
- CPA6.2: Implement embed tool for external clients

Communication Pattern:
- EXTERNAL (MCP, external LLMs): Gateway (:8080) -> embed tool -> semantic-search

Anti-Patterns Avoided (per CODING_PATTERNS_ANALYSIS.md):
- S3457: No empty f-strings
- S7503: No async without await
- AP-1: Tool names as constants
- AP-2: Tool methods <15 CC
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx


# =============================================================================
# WBS-CPA6.1: Embed Tool Module Structure Tests
# =============================================================================


class TestEmbedModuleStructure:
    """Tests for embed tool module structure."""

    def test_embed_module_importable(self) -> None:
        """
        WBS-CPA6.1: embed module is importable.
        """
        from src.tools.builtin import embed
        assert embed is not None

    def test_embed_function_exists(self) -> None:
        """
        WBS-CPA6.1: embed function exists and is callable.
        """
        from src.tools.builtin.embed import embed
        assert callable(embed)

    def test_embed_definition_exists(self) -> None:
        """
        WBS-CPA6.1: EMBED_DEFINITION exists with correct structure.
        """
        from src.tools.builtin.embed import EMBED_DEFINITION
        
        assert EMBED_DEFINITION.name == "embed"
        assert "embedding" in EMBED_DEFINITION.description.lower()
        assert EMBED_DEFINITION.parameters is not None

    def test_embed_definition_has_texts_parameter(self) -> None:
        """
        WBS-CPA6.1: EMBED_DEFINITION has required 'texts' parameter.
        """
        from src.tools.builtin.embed import EMBED_DEFINITION
        
        properties = EMBED_DEFINITION.parameters.get("properties", {})
        assert "texts" in properties
        assert properties["texts"]["type"] == "array"

    def test_embed_definition_has_model_parameter(self) -> None:
        """
        WBS-CPA6.1: EMBED_DEFINITION has optional 'model' parameter.
        """
        from src.tools.builtin.embed import EMBED_DEFINITION
        
        properties = EMBED_DEFINITION.parameters.get("properties", {})
        assert "model" in properties
        assert properties["model"]["type"] == "string"

    def test_tool_name_constant_exists(self) -> None:
        """
        WBS-CPA6.1: TOOL_NAME_EMBED constant exists (AP-1 compliance).
        """
        from src.tools.builtin.embed import TOOL_NAME_EMBED
        assert TOOL_NAME_EMBED == "embed"

    def test_service_error_class_exists(self) -> None:
        """
        WBS-CPA6.1: EmbedServiceError exception class exists.
        """
        from src.tools.builtin.embed import EmbedServiceError
        assert issubclass(EmbedServiceError, Exception)


# =============================================================================
# WBS-CPA6.2: Embed Tool Execution Tests
# =============================================================================


class TestEmbedFunction:
    """Tests for embed tool function execution."""

    @pytest.mark.asyncio
    async def test_embed_basic_single_text(self) -> None:
        """
        WBS-CPA6.2: embed accepts single text and returns embedding.
        """
        from src.tools.builtin.embed import embed
        
        mock_response = {
            "embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]],
            "model": "all-MiniLM-L6-v2",
            "dimensions": 5,
            "processing_time_ms": 12.3,
        }
        
        with patch("src.tools.builtin.embed._do_embed_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await embed({
                "texts": ["Hello world"],
            })
            
            assert "embeddings" in result
            assert len(result["embeddings"]) == 1
            assert len(result["embeddings"][0]) == 5

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self) -> None:
        """
        WBS-CPA6.2: embed accepts multiple texts and returns embeddings.
        """
        from src.tools.builtin.embed import embed
        
        mock_response = {
            "embeddings": [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9],
            ],
            "model": "all-MiniLM-L6-v2",
            "dimensions": 3,
            "processing_time_ms": 25.0,
        }
        
        with patch("src.tools.builtin.embed._do_embed_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await embed({
                "texts": ["Text one", "Text two", "Text three"],
            })
            
            assert len(result["embeddings"]) == 3

    @pytest.mark.asyncio
    async def test_embed_with_model_parameter(self) -> None:
        """
        WBS-CPA6.2: embed accepts optional model parameter.
        """
        from src.tools.builtin.embed import embed
        
        mock_response = {
            "embeddings": [[0.1, 0.2]],
            "model": "text-embedding-3-small",
            "dimensions": 2,
        }
        
        with patch("src.tools.builtin.embed._do_embed_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await embed({
                "texts": ["Test"],
                "model": "text-embedding-3-small",
            })
            
            assert result["model"] == "text-embedding-3-small"
            # Verify model was passed in request
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert call_args[0][0]["model"] == "text-embedding-3-small"


# =============================================================================
# WBS-CPA6.2: Embed Tool Error Handling Tests
# =============================================================================


class TestEmbedErrorHandling:
    """Tests for embed tool error handling."""

    @pytest.mark.asyncio
    async def test_embed_service_unavailable(self) -> None:
        """
        WBS-CPA6.2: embed raises EmbedServiceError when service unavailable.
        """
        from src.tools.builtin.embed import embed, EmbedServiceError
        
        with patch("src.tools.builtin.embed.get_embed_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = httpx.RequestError("Connection refused")
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(EmbedServiceError) as exc_info:
                await embed({"texts": ["test"]})
            
            assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_circuit_breaker_open(self) -> None:
        """
        WBS-CPA6.2: embed handles circuit breaker in open state.
        """
        from src.tools.builtin.embed import embed, EmbedServiceError
        from src.clients.circuit_breaker import CircuitOpenError
        
        with patch("src.tools.builtin.embed.get_embed_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = CircuitOpenError("Circuit is open")
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(EmbedServiceError) as exc_info:
                await embed({"texts": ["test"]})
            
            assert "circuit" in str(exc_info.value).lower() or "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_embed_http_error(self) -> None:
        """
        WBS-CPA6.2: embed handles HTTP errors from semantic-search-service.
        """
        from src.tools.builtin.embed import embed, EmbedServiceError
        
        with patch("src.tools.builtin.embed.get_embed_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_resp = httpx.Response(500, content=b"Internal Server Error")
            mock_cb_instance.call.side_effect = httpx.HTTPStatusError(
                "Server Error", request=httpx.Request("POST", "http://test"), response=mock_resp
            )
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(EmbedServiceError) as exc_info:
                await embed({"texts": ["test"]})
            
            error_msg = str(exc_info.value).lower()
            assert "error" in error_msg or "failed" in error_msg

    @pytest.mark.asyncio
    async def test_embed_empty_texts_list(self) -> None:
        """
        WBS-CPA6.2: embed handles empty texts list gracefully.
        """
        from src.tools.builtin.embed import embed
        
        mock_response = {
            "embeddings": [],
            "model": "all-MiniLM-L6-v2",
            "dimensions": 384,
        }
        
        with patch("src.tools.builtin.embed._do_embed_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await embed({"texts": []})
            
            assert result["embeddings"] == []


# =============================================================================
# WBS-CPA6.2: Embed Tool Circuit Breaker Tests
# =============================================================================


class TestEmbedCircuitBreaker:
    """Tests for embed tool circuit breaker functionality."""

    def test_circuit_breaker_getter_exists(self) -> None:
        """
        WBS-CPA6.2: get_embed_circuit_breaker function exists.
        """
        from src.tools.builtin.embed import get_embed_circuit_breaker
        assert callable(get_embed_circuit_breaker)

    def test_circuit_breaker_singleton(self) -> None:
        """
        WBS-CPA6.2: Circuit breaker is a singleton.
        """
        from src.tools.builtin.embed import get_embed_circuit_breaker
        
        # Reset for test
        import src.tools.builtin.embed as embed_module
        embed_module._embed_circuit_breaker = None
        
        cb1 = get_embed_circuit_breaker()
        cb2 = get_embed_circuit_breaker()
        
        assert cb1 is cb2

    def test_circuit_breaker_named(self) -> None:
        """
        WBS-CPA6.2: Circuit breaker has correct service name.
        """
        from src.tools.builtin.embed import get_embed_circuit_breaker
        
        # Reset for test
        import src.tools.builtin.embed as embed_module
        embed_module._embed_circuit_breaker = None
        
        cb = get_embed_circuit_breaker()
        
        assert cb.name == "semantic-search-embed"


# =============================================================================
# WBS-CPA6.3: Embed Tool Registration Tests
# =============================================================================


class TestEmbedRegistration:
    """Tests for embed tool registration with ToolRegistry."""

    def test_embed_exported_from_builtin(self) -> None:
        """
        WBS-CPA6.3: embed is exported from src.tools.builtin.
        """
        from src.tools.builtin import embed
        from src.tools.builtin import EMBED_DEFINITION
        from src.tools.builtin import EmbedServiceError
        
        assert callable(embed)
        assert EMBED_DEFINITION is not None
        assert EmbedServiceError is not None

    def test_embed_registered_in_builtin_tools(self) -> None:
        """
        WBS-CPA6.3: embed is registered via register_builtin_tools.
        """
        from src.tools.builtin import register_builtin_tools
        from src.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        register_builtin_tools(registry)
        
        # Verify embed tool is registered
        tool = registry.get("embed")
        assert tool is not None
        assert tool.definition.name == "embed"
        assert callable(tool.handler)

    def test_embed_in_all_exports(self) -> None:
        """
        WBS-CPA6.3: embed exports are in __all__.
        """
        from src.tools import builtin
        
        assert "embed" in builtin.__all__
        assert "EMBED_DEFINITION" in builtin.__all__
        assert "EmbedServiceError" in builtin.__all__
