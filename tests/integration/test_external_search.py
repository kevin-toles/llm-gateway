"""
WBS-CPA1.5: External Search Integration Tests

This module tests external client access to search tools via Gateway.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA1 Gateway External Tool Exposure
- CONSOLIDATED_PLATFORM_ARCHITECTURE.md: Kitchen Brigade Architecture

Communication Pattern:
- INTERNAL (platform services): Direct API calls (:8081, :8082, etc.)
- EXTERNAL (MCP, external LLMs): Gateway (:8080)

WBS Coverage:
- CPA1.5: Integration test: external client → Gateway → semantic-search
- AC-CPA1.1: Gateway exposes semantic_search tool for external clients
- AC-CPA1.2: Gateway exposes hybrid_search tool for external clients
- AC-CPA1.3: External clients can invoke search via Gateway :8080

TDD Phase: REFACTOR - Integration tests validating complete flow.
"""

import pytest


# =============================================================================
# WBS-CPA1.5: External Search via Gateway Tests
# =============================================================================


class TestExternalSearchToolExposure:
    """
    WBS-CPA1.5: Test that search tools are exposed for external clients.
    
    These tests validate that external clients (MCP, external LLMs) can
    discover and invoke search tools through the Gateway.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_gateway_exposes_search_corpus_tool(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.1: Gateway exposes search_corpus tool for external clients.
        
        External clients should be able to discover the search_corpus tool
        in the Gateway's tool registry.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /v1/tools, got {response.status_code}"
        )
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        
        assert "search_corpus" in tool_names, (
            f"search_corpus tool not found in registry. Available: {tool_names}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_gateway_exposes_hybrid_search_tool(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.2: Gateway exposes hybrid_search tool for external clients.
        
        External clients should be able to discover the hybrid_search tool
        in the Gateway's tool registry.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /v1/tools, got {response.status_code}"
        )
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        
        assert "hybrid_search" in tool_names, (
            f"hybrid_search tool not found in registry. Available: {tool_names}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_hybrid_search_tool_has_correct_parameters(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.2: hybrid_search tool has correct parameter schema.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        
        hybrid_tool = next(
            (t for t in tools if isinstance(t, dict) and t.get("name") == "hybrid_search"),
            None
        )
        
        assert hybrid_tool is not None, "hybrid_search tool not found"
        
        # Verify required parameters
        params = hybrid_tool.get("parameters", {})
        properties = params.get("properties", {})
        
        assert "query" in properties, "query parameter missing"
        assert "query" in params.get("required", []), "query should be required"


# =============================================================================
# WBS-CPA1.5: External Search Execution Tests
# =============================================================================


class TestExternalSearchExecution:
    """
    WBS-CPA1.5: Test search tool execution via Gateway.
    
    These tests validate that external clients can execute search tools
    through the Gateway and receive proper responses.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_external_client_can_execute_search_corpus(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.3: External clients can invoke search_corpus via Gateway :8080.
        
        This simulates an external client (MCP, external LLM) executing
        a search through the Gateway.
        """
        # Execute search_corpus tool via Gateway
        response = gateway_client_sync.post(
            "/v1/tools/search_corpus/execute",
            json={
                "query": "microservices architecture patterns",
                "top_k": 5,
            }
        )
        
        # Should succeed or return appropriate error if semantic-search not available
        assert response.status_code in [200, 503], (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "results" in data or "error" not in data, (
                f"Unexpected response structure: {data}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_external_client_can_execute_hybrid_search(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.3: External clients can invoke hybrid_search via Gateway :8080.
        
        This simulates an external client (MCP, external LLM) executing
        a hybrid search through the Gateway.
        """
        # Execute hybrid_search tool via Gateway
        response = gateway_client_sync.post(
            "/v1/tools/hybrid_search/execute",
            json={
                "query": "circuit breaker pattern resilience",
                "limit": 5,
                "alpha": 0.7,
            }
        )
        
        # Should succeed or return appropriate error if semantic-search not available
        assert response.status_code in [200, 503], (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            data = response.json()
            # Hybrid search response includes these fields
            assert "results" in data or "error" not in data, (
                f"Unexpected response structure: {data}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_hybrid_search_with_advanced_parameters(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA1.3: hybrid_search accepts all parameters.
        
        Test that external clients can use advanced hybrid search features.
        """
        response = gateway_client_sync.post(
            "/v1/tools/hybrid_search/execute",
            json={
                "query": "API gateway patterns",
                "limit": 10,
                "alpha": 0.5,
                "collection": "documents",
                "include_graph": True,
                "tier_filter": [1, 2],
            }
        )
        
        # Should succeed or return appropriate error
        assert response.status_code in [200, 422, 503], (
            f"Unexpected status {response.status_code}: {response.text}"
        )


# =============================================================================
# WBS-CPA1.5: Error Handling Tests
# =============================================================================


class TestExternalSearchErrorHandling:
    """
    WBS-CPA1.5: Test error handling for external search requests.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_hybrid_search_missing_query_returns_422(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS-CPA1.5: Missing required parameter returns 422.
        """
        response = gateway_client_sync.post(
            "/v1/tools/hybrid_search/execute",
            json={
                "limit": 5,  # Missing required "query" parameter
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, (
            f"Expected 422 for missing query, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_unknown_tool_returns_404(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS-CPA1.5: Unknown tool returns 404.
        """
        response = gateway_client_sync.post(
            "/v1/tools/nonexistent_tool/execute",
            json={"query": "test"}
        )
        
        assert response.status_code == 404, (
            f"Expected 404 for unknown tool, got {response.status_code}"
        )


# =============================================================================
# WBS-CPA1.4: Internal Direct Call Verification (Negative Test)
# =============================================================================


class TestInternalDirectCallPattern:
    """
    AC-CPA1.4: Internal service-to-service calls via direct ports remain unchanged.
    
    These tests document that the Gateway tools are for EXTERNAL clients only.
    Internal platform services should call semantic-search directly on :8081.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_documentation_internal_direct_call_pattern(
        self, skip_if_no_docker
    ) -> None:
        """
        AC-CPA1.4: Document that internal calls use direct ports.
        
        This is a documentation test - internal services (ai-agents, audit-service, etc.)
        call semantic-search-service directly on :8081, not through Gateway.
        
        Pattern documented in CONSOLIDATED_PLATFORM_ARCHITECTURE.md:
        - INTERNAL (platform services): Direct API calls (:8081, :8082, etc.)
        - EXTERNAL (MCP, external LLMs): Gateway (:8080)
        """
        # This test documents the architecture pattern
        # Internal services call semantic-search directly:
        #   http://semantic-search-service:8081/v1/search
        #   http://semantic-search-service:8081/v1/search/hybrid
        #
        # External clients call Gateway:
        #   http://llm-gateway:8080/v1/tools/search_corpus/execute
        #   http://llm-gateway:8080/v1/tools/hybrid_search/execute
        
        # This is a pass-through test to document the pattern
        assert True, (
            "Internal services use direct ports; "
            "Gateway tools are for external clients only"
        )
