"""
Tests for Hybrid Search Tier Parameters - WBS-TXS5 MCP Gateway Tier Parameter Exposure

TDD RED Phase: Tests for bloom_tier_filter, quality_tier_filter, and bloom_tier_boost parameters.

Reference Documents:
- WBS_TAXONOMY_ENHANCED_SEARCH.md: WBS-TXS5 MCP Gateway Tier Parameter Exposure
- unified-search-service/src/api/models.py: HybridSearchRequest schema
- llm-gateway/src/tools/builtin/hybrid_search.py: Current implementation

WBS Items Covered:
- TXS5.1: Test bloom_tier_filter parameter acceptance
- TXS5.3: Test quality_tier_filter parameter acceptance
- TXS5.5: Test bloom_tier_boost parameter acceptance
- TXS5.7: Test tier parameters included in dispatch payload
- TXS5.9: Test omitting params produces payload without those keys
- TXS5.11: Test bloom_tier_filter=[7] validation error

Anti-Patterns Avoided:
- S3457: No empty f-strings
- S7503: No async without await
- S1066: No nested if statements
"""

import pytest
from unittest.mock import AsyncMock, patch


# =============================================================================
# TXS5.1: RED - Test bloom_tier_filter Parameter
# =============================================================================


class TestBloomTierFilterParameter:
    """Tests for bloom_tier_filter parameter in hybrid_search tool."""

    @pytest.mark.asyncio
    async def test_hybrid_search_accepts_bloom_tier_filter(self) -> None:
        """
        TXS5.1: hybrid_search accepts bloom_tier_filter=[2,3] parameter.
        
        AC-TXS5.1: hybrid_search MCP tool accepts optional bloom_tier_filter
        parameter (list of ints 0-6, for chapters).
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [
                {
                    "id": "ch_123",
                    "score": 0.95,
                    "vector_score": 0.9,
                    "graph_score": 0.8,
                    "bloom_tier_level": 2,
                    "payload": {"title": "Chapter on Design Patterns"},
                }
            ],
            "total": 1,
            "query": "design patterns",
            "alpha": 0.7,
            "latency_ms": 50.5,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await hybrid_search({
                "query": "design patterns",
                "bloom_tier_filter": [2, 3],
            })
            
            assert result["total"] == 1
            assert result["results"][0]["bloom_tier_level"] == 2

    def test_hybrid_search_definition_includes_bloom_tier_filter(self) -> None:
        """
        TXS5.1: HYBRID_SEARCH_DEFINITION includes bloom_tier_filter in schema.
        
        AC-TXS5.1: MCP tool schema must advertise the parameter.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        properties = HYBRID_SEARCH_DEFINITION.parameters.get("properties", {})
        
        assert "bloom_tier_filter" in properties
        assert properties["bloom_tier_filter"]["type"] == "array"
        assert properties["bloom_tier_filter"]["items"]["type"] == "integer"
        assert "chapters" in properties["bloom_tier_filter"]["description"].lower()


# =============================================================================
# TXS5.3: RED - Test quality_tier_filter Parameter
# =============================================================================


class TestQualityTierFilterParameter:
    """Tests for quality_tier_filter parameter in hybrid_search tool."""

    @pytest.mark.asyncio
    async def test_hybrid_search_accepts_quality_tier_filter(self) -> None:
        """
        TXS5.3: hybrid_search accepts quality_tier_filter=[1,2] parameter.
        
        AC-TXS5.2: hybrid_search MCP tool accepts optional quality_tier_filter
        parameter (list of ints 1-3, for code_chunks).
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [
                {
                    "id": "code_456",
                    "score": 0.92,
                    "vector_score": 0.85,
                    "graph_score": 0.75,
                    "tier": 1,
                    "payload": {"repo": "flagship-repo", "path": "src/main.py"},
                }
            ],
            "total": 1,
            "query": "authentication",
            "alpha": 0.7,
            "latency_ms": 45.2,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await hybrid_search({
                "query": "authentication",
                "quality_tier_filter": [1, 2],
            })
            
            assert result["total"] == 1
            assert result["results"][0]["tier"] == 1

    def test_hybrid_search_definition_includes_quality_tier_filter(self) -> None:
        """
        TXS5.3: HYBRID_SEARCH_DEFINITION includes quality_tier_filter in schema.
        
        AC-TXS5.2: MCP tool schema must advertise the parameter.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        properties = HYBRID_SEARCH_DEFINITION.parameters.get("properties", {})
        
        assert "quality_tier_filter" in properties
        assert properties["quality_tier_filter"]["type"] == "array"
        assert properties["quality_tier_filter"]["items"]["type"] == "integer"
        assert "code_chunks" in properties["quality_tier_filter"]["description"].lower()


# =============================================================================
# TXS5.5: RED - Test bloom_tier_boost Parameter
# =============================================================================


class TestBloomTierBoostParameter:
    """Tests for bloom_tier_boost parameter in hybrid_search tool."""

    @pytest.mark.asyncio
    async def test_hybrid_search_accepts_bloom_tier_boost_false(self) -> None:
        """
        TXS5.5: hybrid_search accepts bloom_tier_boost=False parameter.
        
        AC-TXS5.3: hybrid_search MCP tool accepts optional bloom_tier_boost
        parameter (bool, default True).
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {
            "results": [
                {
                    "id": "ch_789",
                    "score": 0.85,
                    "vector_score": 0.85,
                    "graph_score": 0.75,
                    "bloom_tier_level": 3,
                    "tier_boost_applied": None,
                    "payload": {"title": "Advanced Patterns"},
                }
            ],
            "total": 1,
            "query": "advanced patterns",
            "alpha": 0.7,
            "latency_ms": 48.3,
        }
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            result = await hybrid_search({
                "query": "advanced patterns",
                "bloom_tier_boost": False,
            })
            
            assert result["results"][0]["tier_boost_applied"] is None

    def test_hybrid_search_definition_includes_bloom_tier_boost(self) -> None:
        """
        TXS5.5: HYBRID_SEARCH_DEFINITION includes bloom_tier_boost in schema.
        
        AC-TXS5.3: MCP tool schema must advertise the parameter with default=True.
        """
        from src.tools.builtin.hybrid_search import HYBRID_SEARCH_DEFINITION
        
        properties = HYBRID_SEARCH_DEFINITION.parameters.get("properties", {})
        
        assert "bloom_tier_boost" in properties
        assert properties["bloom_tier_boost"]["type"] == "boolean"
        assert properties["bloom_tier_boost"]["default"] is True


# =============================================================================
# TXS5.7: RED - Test Parameters Included in Dispatch Payload
# =============================================================================


class TestTierParametersInPayload:
    """Tests that tier parameters are forwarded to semantic-search-service."""

    @pytest.mark.asyncio
    async def test_bloom_tier_filter_included_in_payload(self) -> None:
        """
        TXS5.7: bloom_tier_filter is included in dispatch payload.
        
        AC-TXS5.4: All three params are forwarded to semantic-search-service
        in the dispatch payload.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {"results": [], "total": 0, "query": "test", "alpha": 0.7, "latency_ms": 10.0}
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({
                "query": "test query",
                "bloom_tier_filter": [2, 3, 4],
            })
            
            # Verify the payload passed to _do_hybrid_search
            call_args = mock_search.call_args
            payload = call_args[0][1]  # Second positional arg is payload
            
            assert "bloom_tier_filter" in payload
            assert payload["bloom_tier_filter"] == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_quality_tier_filter_included_in_payload(self) -> None:
        """
        TXS5.7: quality_tier_filter is included in dispatch payload.
        
        AC-TXS5.4: All three params are forwarded to semantic-search-service.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {"results": [], "total": 0, "query": "test", "alpha": 0.7, "latency_ms": 10.0}
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({
                "query": "test query",
                "quality_tier_filter": [1],
            })
            
            call_args = mock_search.call_args
            payload = call_args[0][1]
            
            assert "quality_tier_filter" in payload
            assert payload["quality_tier_filter"] == [1]

    @pytest.mark.asyncio
    async def test_bloom_tier_boost_included_in_payload(self) -> None:
        """
        TXS5.7: bloom_tier_boost is included in dispatch payload.
        
        AC-TXS5.4: All three params are forwarded to semantic-search-service.
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {"results": [], "total": 0, "query": "test", "alpha": 0.7, "latency_ms": 10.0}
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({
                "query": "test query",
                "bloom_tier_boost": False,
            })
            
            call_args = mock_search.call_args
            payload = call_args[0][1]
            
            assert "bloom_tier_boost" in payload
            assert payload["bloom_tier_boost"] is False


# =============================================================================
# TXS5.9: RED - Test Omitting Parameters
# =============================================================================


class TestOmittingTierParameters:
    """Tests backward compatibility when tier parameters are omitted."""

    @pytest.mark.asyncio
    async def test_omitting_tier_params_excludes_from_payload(self) -> None:
        """
        TXS5.9: Omitting tier params produces payload without those keys.
        
        AC-TXS5.5: Omitting all new params produces identical behavior to
        current (backward compatible).
        """
        from src.tools.builtin.hybrid_search import hybrid_search
        
        mock_response = {"results": [], "total": 0, "query": "test", "alpha": 0.7, "latency_ms": 10.0}
        
        with patch("src.tools.builtin.hybrid_search._do_hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_response
            
            await hybrid_search({
                "query": "test query",
            })
            
            call_args = mock_search.call_args
            payload = call_args[0][1]
            
            # When omitted, tier params should NOT be in payload
            # (to maintain backward compatibility)
            assert "bloom_tier_filter" not in payload
            assert "quality_tier_filter" not in payload
            # bloom_tier_boost defaults to True, so it should be included
            assert "bloom_tier_boost" in payload
            assert payload["bloom_tier_boost"] is True


# =============================================================================
# TXS5.11: RED - Test Validation Errors
# =============================================================================


class TestTierParameterValidation:
    """Tests validation of tier parameter ranges."""

    @pytest.mark.asyncio
    async def test_bloom_tier_filter_invalid_value_raises_error(self) -> None:
        """
        TXS5.11: bloom_tier_filter=[7] raises validation error.
        
        AC-TXS5.6: Invalid bloom_tier_filter values (e.g., [7]) are caught
        at gateway level with proper error message.
        
        WBS-TXS5.13: Gateway-level validation in REFACTOR phase.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        
        with pytest.raises(HybridSearchServiceError) as exc_info:
            await hybrid_search({
                "query": "test query",
                "bloom_tier_filter": [7],  # Invalid: should be 0-6
            })
        
        assert "bloom_tier_filter" in str(exc_info.value).lower()
        assert "0-6" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_quality_tier_filter_invalid_value_raises_error(self) -> None:
        """
        TXS5.11: quality_tier_filter=[0] raises validation error.
        
        AC-TXS5.6: Invalid quality_tier_filter values (should be 1-3).
        
        WBS-TXS5.13: Gateway-level validation in REFACTOR phase.
        """
        from src.tools.builtin.hybrid_search import hybrid_search, HybridSearchServiceError
        
        with pytest.raises(HybridSearchServiceError) as exc_info:
            await hybrid_search({
                "query": "test query",
                "quality_tier_filter": [0],  # Invalid: should be 1-3
            })
        
        assert "quality_tier_filter" in str(exc_info.value).lower()
        assert "1-3" in str(exc_info.value)
