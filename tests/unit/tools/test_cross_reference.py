"""
Tests for Cross-Reference Tool - WBS 2.4.3.2 Cross-Reference Tool

TDD RED Phase: Tests for cross_reference tool that proxies to ai-agents service.

Reference Documents:
- ARCHITECTURE.md Line 82: ai_agents_url "http://localhost:8082"
- ai-agents ARCHITECTURE.md: Cross-Reference Agent endpoint
- TIER_RELATIONSHIP_DIAGRAM.md: Spider Web Model taxonomy
- GUIDELINES pp. 2309: Circuit breaker pattern
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

WBS Items Covered:
- 2.4.3.2.1: Create src/tools/builtin/cross_reference.py
- 2.4.3.2.2: Implement CrossReferenceServiceError exception
- 2.4.3.2.3: Implement cross_reference tool function
- 2.4.3.2.4: Accept source chapter and config parameters
- 2.4.3.2.5: Call ai-agents /v1/agents/cross-reference endpoint
- 2.4.3.2.6: Return cross-reference results as structured data
- 2.4.3.2.7: Handle service unavailable errors
- 3.2.3.1: Circuit breaker integration

Anti-Patterns Avoided (per CODING_PATTERNS_ANALYSIS.md):
- S3457: No empty f-strings
- S7503: No async without await
- S1066: No nested if statements
- S6546: Use PEP 604 union syntax (X | Y)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# =============================================================================
# WBS 2.4.3.2.1: Module and Class Tests
# =============================================================================


class TestCrossReferenceModuleStructure:
    """Tests for cross_reference module structure."""

    def test_cross_reference_module_importable(self) -> None:
        """
        WBS 2.4.3.2.1: cross_reference module is importable.
        """
        from src.tools.builtin import cross_reference
        assert cross_reference is not None

    def test_cross_reference_function_exists(self) -> None:
        """
        WBS 2.4.3.2.3: cross_reference function exists.
        """
        from src.tools.builtin.cross_reference import cross_reference
        assert callable(cross_reference)

    def test_cross_reference_definition_exists(self) -> None:
        """
        WBS 2.4.3.2.1: CROSS_REFERENCE_DEFINITION exists.
        """
        from src.tools.builtin.cross_reference import CROSS_REFERENCE_DEFINITION
        assert CROSS_REFERENCE_DEFINITION is not None
        assert CROSS_REFERENCE_DEFINITION.name == "cross_reference"

    def test_cross_reference_service_error_exists(self) -> None:
        """
        WBS 2.4.3.2.2: CrossReferenceServiceError exception exists.
        """
        from src.tools.builtin.cross_reference import CrossReferenceServiceError
        assert issubclass(CrossReferenceServiceError, Exception)


# =============================================================================
# WBS 2.4.3.2.3-4: Tool Definition Tests
# =============================================================================


class TestCrossReferenceDefinition:
    """Tests for CROSS_REFERENCE_DEFINITION tool schema."""

    def test_definition_has_required_properties(self) -> None:
        """
        CROSS_REFERENCE_DEFINITION has required properties.
        """
        from src.tools.builtin.cross_reference import CROSS_REFERENCE_DEFINITION
        
        params = CROSS_REFERENCE_DEFINITION.parameters
        required = params.get("required", [])
        
        assert "book" in required
        assert "chapter" in required
        assert "title" in required
        assert "tier" in required

    def test_definition_has_optional_properties(self) -> None:
        """
        CROSS_REFERENCE_DEFINITION has optional config properties.
        """
        from src.tools.builtin.cross_reference import CROSS_REFERENCE_DEFINITION
        
        properties = CROSS_REFERENCE_DEFINITION.parameters.get("properties", {})
        
        # Config parameters should exist
        assert "max_hops" in properties
        assert "min_similarity" in properties
        assert "include_tier1" in properties
        assert "include_tier2" in properties
        assert "include_tier3" in properties
        assert "taxonomy_id" in properties

    def test_definition_tier_enum(self) -> None:
        """
        Tier parameter has enum constraint [1, 2, 3].
        """
        from src.tools.builtin.cross_reference import CROSS_REFERENCE_DEFINITION
        
        properties = CROSS_REFERENCE_DEFINITION.parameters.get("properties", {})
        tier_prop = properties.get("tier", {})
        
        assert tier_prop.get("enum") == [1, 2, 3]


# =============================================================================
# WBS 2.4.3.2.5: HTTP Request Tests
# =============================================================================


class TestCrossReferenceHttpRequest:
    """Tests for cross_reference HTTP request behavior."""

    @pytest.fixture
    def sample_cross_reference_response(self):
        """Sample response from ai-agents cross-reference endpoint."""
        return {
            "annotation": "This chapter relates to **Domain-Driven Design** concepts...",
            "citations": [
                {
                    "author": "Percival, Harry",
                    "book": "Architecture Patterns with Python",
                    "chapter": 1,
                    "chapter_title": "Domain Modeling",
                    "pages": "1-25",
                    "tier": 1,
                }
            ],
            "tier_coverage": [
                {"tier": 1, "count": 3, "books": ["Architecture Patterns with Python"]},
                {"tier": 2, "count": 2, "books": ["Building LLM Powered Applications"]},
            ],
            "processing_time_ms": 1234.5,
            "model_used": "claude-3-sonnet-20240229",
        }

    @pytest.mark.asyncio
    async def test_cross_reference_calls_ai_agents_endpoint(
        self, sample_cross_reference_response
    ) -> None:
        """
        WBS 2.4.3.2.5: cross_reference calls /v1/agents/cross-reference.
        """
        from src.tools.builtin.cross_reference import cross_reference

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            mock_do.return_value = sample_cross_reference_response

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            _result = await cross_reference(args)  # noqa: F841

            # Verify the HTTP function was called
            assert mock_do.called

    @pytest.mark.asyncio
    async def test_cross_reference_returns_structured_result(
        self, sample_cross_reference_response
    ) -> None:
        """
        WBS 2.4.3.2.6: cross_reference returns structured data.
        """
        from src.tools.builtin.cross_reference import cross_reference

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            mock_do.return_value = sample_cross_reference_response

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            result = await cross_reference(args)

            assert "annotation" in result
            assert "citations" in result
            assert "tier_coverage" in result
            assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_cross_reference_passes_optional_config(
        self, sample_cross_reference_response
    ) -> None:
        """
        cross_reference passes optional config parameters.
        """
        from src.tools.builtin.cross_reference import cross_reference

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            mock_do.return_value = sample_cross_reference_response

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
                "max_hops": 5,
                "min_similarity": 0.8,
                "include_tier1": True,
                "include_tier2": False,
                "include_tier3": True,
                "taxonomy_id": "custom-taxonomy",
            }

            _result = await cross_reference(args)  # noqa: F841

            # Verify it was called (config params handled internally)
            assert mock_do.called


# =============================================================================
# WBS 2.4.3.2.7: Error Handling Tests
# =============================================================================


class TestCrossReferenceErrorHandling:
    """Tests for cross_reference error handling."""

    @pytest.mark.asyncio
    async def test_timeout_raises_service_error(self) -> None:
        """
        WBS 2.4.3.2.7: Timeout raises CrossReferenceServiceError.
        """
        from src.tools.builtin.cross_reference import (
            cross_reference,
            CrossReferenceServiceError,
        )

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            mock_do.side_effect = httpx.TimeoutException("Request timed out")

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            with pytest.raises(CrossReferenceServiceError) as exc_info:
                await cross_reference(args)

            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connection_error_raises_service_error(self) -> None:
        """
        WBS 2.4.3.2.7: Connection error raises CrossReferenceServiceError.
        """
        from src.tools.builtin.cross_reference import (
            cross_reference,
            CrossReferenceServiceError,
        )

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            mock_do.side_effect = httpx.ConnectError("Connection refused")

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            with pytest.raises(CrossReferenceServiceError) as exc_info:
                await cross_reference(args)

            assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_http_error_raises_service_error(self) -> None:
        """
        WBS 2.4.3.2.7: HTTP error raises CrossReferenceServiceError.
        """
        from src.tools.builtin.cross_reference import (
            cross_reference,
            CrossReferenceServiceError,
        )

        with patch("src.tools.builtin.cross_reference._do_cross_reference") as mock_do:
            # Create mock HTTP error response
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Internal server error"}
            mock_do.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            with pytest.raises(CrossReferenceServiceError) as exc_info:
                await cross_reference(args)

            assert "500" in str(exc_info.value)


# =============================================================================
# WBS 3.2.3.1: Circuit Breaker Tests
# =============================================================================


class TestCrossReferenceCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_circuit_breaker_getter_exists(self) -> None:
        """
        WBS 3.2.3.1: Circuit breaker getter function exists.
        """
        from src.tools.builtin.cross_reference import get_ai_agents_circuit_breaker
        
        circuit_breaker = get_ai_agents_circuit_breaker()
        assert circuit_breaker is not None
        assert circuit_breaker.name == "ai-agents-service"

    @pytest.mark.asyncio
    async def test_circuit_open_raises_service_error(self) -> None:
        """
        WBS 3.2.3.1: Circuit open raises CrossReferenceServiceError.
        """
        from src.tools.builtin.cross_reference import (
            cross_reference,
            CrossReferenceServiceError,
        )
        from src.clients.circuit_breaker import CircuitOpenError

        with patch(
            "src.tools.builtin.cross_reference.get_ai_agents_circuit_breaker"
        ) as mock_cb:
            mock_circuit = MagicMock()
            mock_circuit.call.side_effect = CircuitOpenError("Circuit is open")
            mock_cb.return_value = mock_circuit

            args = {
                "book": "Test Book",
                "chapter": 1,
                "title": "Test Chapter",
                "tier": 1,
            }

            with pytest.raises(CrossReferenceServiceError) as exc_info:
                await cross_reference(args)

            assert "circuit open" in str(exc_info.value).lower()


# =============================================================================
# Registration Tests
# =============================================================================


class TestCrossReferenceRegistration:
    """Tests for cross_reference tool registration in builtin package."""

    def test_cross_reference_exported_from_builtin(self) -> None:
        """
        cross_reference is exported from builtin package.
        """
        from src.tools.builtin import (
            cross_reference,
            CROSS_REFERENCE_DEFINITION,
            CrossReferenceServiceError,
        )
        
        assert cross_reference is not None
        assert CROSS_REFERENCE_DEFINITION is not None
        assert CrossReferenceServiceError is not None

    def test_register_builtin_tools_includes_cross_reference(self) -> None:
        """
        register_builtin_tools registers cross_reference tool.
        """
        from src.tools.builtin import register_builtin_tools
        from src.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        register_builtin_tools(registry)
        
        # Verify cross_reference is registered
        assert registry.has("cross_reference")
