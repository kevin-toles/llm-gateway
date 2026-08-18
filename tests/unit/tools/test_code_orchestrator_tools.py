"""
Tests for Code-Orchestrator Tools - WBS-CPA2 Code-Orchestrator Tool Exposure

TDD RED Phase: Tests for Code-Orchestrator tools that proxy to Code-Orchestrator-Service.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA2 Gateway → Code-Orchestrator Tool Exposure
- Code-Orchestrator-Service/src/api/similarity.py: /v1/similarity, /v1/embeddings endpoints
- Code-Orchestrator-Service/src/api/keywords.py: /v1/keywords endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

WBS Items Covered:
- CPA2.1: Write failing tests for Code-Orchestrator tools
- CPA2.2: Implement compute_similarity tool
- CPA2.3: Implement extract_keywords tool
- CPA2.4: Implement generate_embeddings tool

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
# WBS-CPA2.2: Compute Similarity Tool Tests
# =============================================================================


class TestComputeSimilarityModuleStructure:
    """Tests for compute_similarity module structure."""

    def test_compute_similarity_module_importable(self) -> None:
        """
        WBS-CPA2.2: compute_similarity module is importable.
        """
        from src.tools.builtin import code_orchestrator_tools
        assert code_orchestrator_tools is not None

    def test_compute_similarity_function_exists(self) -> None:
        """
        WBS-CPA2.2: compute_similarity function exists.
        """
        from src.tools.builtin.code_orchestrator_tools import compute_similarity
        assert callable(compute_similarity)

    def test_compute_similarity_definition_exists(self) -> None:
        """
        WBS-CPA2.2: COMPUTE_SIMILARITY_DEFINITION exists with correct structure.
        """
        from src.tools.builtin.code_orchestrator_tools import COMPUTE_SIMILARITY_DEFINITION
        
        assert COMPUTE_SIMILARITY_DEFINITION.name == "compute_similarity"
        assert "similarity" in COMPUTE_SIMILARITY_DEFINITION.description.lower()
        assert COMPUTE_SIMILARITY_DEFINITION.parameters is not None
        assert "text1" in COMPUTE_SIMILARITY_DEFINITION.parameters.get("properties", {})
        assert "text2" in COMPUTE_SIMILARITY_DEFINITION.parameters.get("properties", {})


class TestComputeSimilarityFunction:
    """Tests for compute_similarity tool function."""

    @pytest.mark.asyncio
    async def test_compute_similarity_basic(self) -> None:
        """
        WBS-CPA2.2: compute_similarity accepts text1 and text2.
        """
        from src.tools.builtin.code_orchestrator_tools import compute_similarity
        
        mock_response = {
            "score": 0.85,
            "model": "all-MiniLM-L6-v2",
            "processing_time_ms": 15.5,
        }
        
        with patch("src.tools.builtin.code_orchestrator_tools._do_code_orchestrator_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await compute_similarity({
                "text1": "Machine learning is great",
                "text2": "Deep learning is powerful",
            })
            
            assert "score" in result
            assert result["score"] == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_compute_similarity_error_handling(self) -> None:
        """
        WBS-CPA2.2: compute_similarity handles service errors.
        """
        from src.tools.builtin.code_orchestrator_tools import (
            compute_similarity,
            CodeOrchestratorServiceError,
        )
        
        with patch("src.tools.builtin.code_orchestrator_tools.get_code_orchestrator_circuit_breaker") as mock_cb:
            mock_cb_instance = AsyncMock()
            mock_cb_instance.call.side_effect = httpx.RequestError("Connection refused")
            mock_cb.return_value = mock_cb_instance
            
            with pytest.raises(CodeOrchestratorServiceError) as exc_info:
                await compute_similarity({
                    "text1": "test1",
                    "text2": "test2",
                })
            
            assert "unavailable" in str(exc_info.value).lower()


# =============================================================================
# WBS-CPA2.3: Extract Keywords Tool Tests
# =============================================================================


class TestExtractKeywordsModuleStructure:
    """Tests for extract_keywords module structure."""

    def test_extract_keywords_function_exists(self) -> None:
        """
        WBS-CPA2.3: extract_keywords function exists.
        """
        from src.tools.builtin.code_orchestrator_tools import extract_keywords
        assert callable(extract_keywords)

    def test_extract_keywords_definition_exists(self) -> None:
        """
        WBS-CPA2.3: EXTRACT_KEYWORDS_DEFINITION exists with correct structure.
        """
        from src.tools.builtin.code_orchestrator_tools import EXTRACT_KEYWORDS_DEFINITION
        
        assert EXTRACT_KEYWORDS_DEFINITION.name == "extract_keywords"
        assert "keyword" in EXTRACT_KEYWORDS_DEFINITION.description.lower()
        assert EXTRACT_KEYWORDS_DEFINITION.parameters is not None
        assert "corpus" in EXTRACT_KEYWORDS_DEFINITION.parameters.get("properties", {})


class TestExtractKeywordsFunction:
    """Tests for extract_keywords tool function."""

    @pytest.mark.asyncio
    async def test_extract_keywords_basic(self) -> None:
        """
        WBS-CPA2.3: extract_keywords accepts corpus and returns keywords.
        """
        from src.tools.builtin.code_orchestrator_tools import extract_keywords
        
        mock_response = {
            "keywords": [["machine", "learning"], ["python", "data"]],
            "processing_time_ms": 12.5,
        }
        
        with patch("src.tools.builtin.code_orchestrator_tools._do_code_orchestrator_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await extract_keywords({
                "corpus": ["Machine learning is great", "Python for data science"],
            })
            
            assert "keywords" in result
            assert len(result["keywords"]) == 2

    @pytest.mark.asyncio
    async def test_extract_keywords_with_top_k(self) -> None:
        """
        WBS-CPA2.3: extract_keywords accepts optional top_k parameter.
        """
        from src.tools.builtin.code_orchestrator_tools import extract_keywords
        
        mock_response = {
            "keywords": [["ml"]],
            "processing_time_ms": 10.0,
        }
        
        with patch("src.tools.builtin.code_orchestrator_tools._do_code_orchestrator_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            await extract_keywords({
                "corpus": ["Machine learning"],
                "top_k": 5,
            })
            
            # Verify top_k was passed
            call_args = mock_req.call_args
            payload = call_args[0][1]  # Second positional arg is payload
            assert payload.get("top_k") == 5


# =============================================================================
# WBS-CPA2.4: Generate Embeddings Tool Tests
# =============================================================================


class TestGenerateEmbeddingsModuleStructure:
    """Tests for generate_embeddings module structure."""

    def test_generate_embeddings_function_exists(self) -> None:
        """
        WBS-CPA2.4: generate_embeddings function exists.
        """
        from src.tools.builtin.code_orchestrator_tools import generate_embeddings
        assert callable(generate_embeddings)

    def test_generate_embeddings_definition_exists(self) -> None:
        """
        WBS-CPA2.4: GENERATE_EMBEDDINGS_DEFINITION exists with correct structure.
        """
        from src.tools.builtin.code_orchestrator_tools import GENERATE_EMBEDDINGS_DEFINITION
        
        assert GENERATE_EMBEDDINGS_DEFINITION.name == "generate_embeddings"
        assert "embedding" in GENERATE_EMBEDDINGS_DEFINITION.description.lower()
        assert GENERATE_EMBEDDINGS_DEFINITION.parameters is not None
        assert "texts" in GENERATE_EMBEDDINGS_DEFINITION.parameters.get("properties", {})


class TestGenerateEmbeddingsFunction:
    """Tests for generate_embeddings tool function."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_basic(self) -> None:
        """
        WBS-CPA2.4: generate_embeddings accepts texts and returns embeddings.
        """
        from src.tools.builtin.code_orchestrator_tools import generate_embeddings
        
        mock_response = {
            "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            "model": "all-MiniLM-L6-v2",
            "processing_time_ms": 25.0,
        }
        
        with patch("src.tools.builtin.code_orchestrator_tools._do_code_orchestrator_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await generate_embeddings({
                "texts": ["Hello world", "Goodbye world"],
            })
            
            assert "embeddings" in result
            assert len(result["embeddings"]) == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings_single_text(self) -> None:
        """
        WBS-CPA2.4: generate_embeddings handles single text.
        """
        from src.tools.builtin.code_orchestrator_tools import generate_embeddings
        
        mock_response = {
            "embeddings": [[0.1, 0.2, 0.3]],
            "model": "all-MiniLM-L6-v2",
            "processing_time_ms": 10.0,
        }
        
        with patch("src.tools.builtin.code_orchestrator_tools._do_code_orchestrator_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            
            result = await generate_embeddings({
                "texts": ["Single text"],
            })
            
            assert len(result["embeddings"]) == 1


# =============================================================================
# WBS-CPA2: Circuit Breaker Tests
# =============================================================================


class TestCodeOrchestratorCircuitBreaker:
    """Tests for Code-Orchestrator circuit breaker integration."""

    def test_circuit_breaker_singleton(self) -> None:
        """
        WBS-CPA2: Circuit breaker is singleton per service.
        """
        from src.tools.builtin.code_orchestrator_tools import get_code_orchestrator_circuit_breaker
        
        # Reset the singleton for test
        import src.tools.builtin.code_orchestrator_tools as module
        module._code_orchestrator_circuit_breaker = None
        
        cb1 = get_code_orchestrator_circuit_breaker()
        cb2 = get_code_orchestrator_circuit_breaker()
        
        assert cb1 is cb2

    def test_circuit_breaker_name(self) -> None:
        """
        WBS-CPA2: Circuit breaker has correct name.
        """
        from src.tools.builtin.code_orchestrator_tools import get_code_orchestrator_circuit_breaker
        
        # Reset the singleton for test
        import src.tools.builtin.code_orchestrator_tools as module
        module._code_orchestrator_circuit_breaker = None
        
        cb = get_code_orchestrator_circuit_breaker()
        
        assert cb.name == "code-orchestrator-service"


# =============================================================================
# WBS-CPA2.5: Registration Tests
# =============================================================================


class TestCodeOrchestratorToolsRegistration:
    """Tests for Code-Orchestrator tools registration."""

    def test_tools_in_builtin_exports(self) -> None:
        """
        WBS-CPA2.5: Code-Orchestrator tools are exported from builtin package.
        """
        from src.tools.builtin import (
            compute_similarity,
            extract_keywords,
            generate_embeddings,
            COMPUTE_SIMILARITY_DEFINITION,
            EXTRACT_KEYWORDS_DEFINITION,
            GENERATE_EMBEDDINGS_DEFINITION,
        )
        
        assert callable(compute_similarity)
        assert callable(extract_keywords)
        assert callable(generate_embeddings)
        assert COMPUTE_SIMILARITY_DEFINITION is not None
        assert EXTRACT_KEYWORDS_DEFINITION is not None
        assert GENERATE_EMBEDDINGS_DEFINITION is not None

    def test_tools_registered_in_registry(self) -> None:
        """
        WBS-CPA2.5: Code-Orchestrator tools are registered by register_builtin_tools.
        """
        from src.tools.registry import ToolRegistry
        from src.tools.builtin import register_builtin_tools
        
        registry = ToolRegistry()
        register_builtin_tools(registry)
        
        # All three tools should be registered
        compute_tool = registry.get("compute_similarity")
        keywords_tool = registry.get("extract_keywords")
        embeddings_tool = registry.get("generate_embeddings")
        
        assert compute_tool is not None
        assert keywords_tool is not None
        assert embeddings_tool is not None


# =============================================================================
# WBS-CPA2: Error Class Tests
# =============================================================================


class TestCodeOrchestratorServiceError:
    """Tests for CodeOrchestratorServiceError exception."""

    def test_error_class_exists(self) -> None:
        """
        WBS-CPA2: CodeOrchestratorServiceError exception class exists.
        """
        from src.tools.builtin.code_orchestrator_tools import CodeOrchestratorServiceError
        
        assert issubclass(CodeOrchestratorServiceError, Exception)

    def test_error_message(self) -> None:
        """
        WBS-CPA2: Error includes message.
        """
        from src.tools.builtin.code_orchestrator_tools import CodeOrchestratorServiceError
        
        error = CodeOrchestratorServiceError("Test error message")
        assert "Test error message" in str(error)
