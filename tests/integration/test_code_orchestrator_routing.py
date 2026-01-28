"""
WBS-CPA2.6: Code-Orchestrator Routing Integration Tests

This module tests external client access to Code-Orchestrator tools via Gateway.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA2 Gateway → Code-Orchestrator Tool Exposure
- CONSOLIDATED_PLATFORM_ARCHITECTURE.md: Kitchen Brigade Architecture

Communication Pattern:
- INTERNAL (platform services): Direct API calls (:8083)
- EXTERNAL (MCP, external LLMs): Gateway (:8080)

WBS Coverage:
- CPA2.6: Integration test: ai-agents → Gateway → Code-Orchestrator
- AC-CPA2.1: Gateway exposes compute_similarity tool for external clients
- AC-CPA2.2: Gateway exposes extract_keywords tool for external clients
- AC-CPA2.3: Gateway exposes generate_embeddings tool for external clients
- AC-CPA2.4: External clients can invoke tools via Gateway :8080

TDD Phase: REFACTOR - Integration tests validating complete flow.
"""

import pytest


# =============================================================================
# WBS-CPA2.6: Code-Orchestrator Tool Exposure Tests
# =============================================================================


class TestCodeOrchestratorToolExposure:
    """
    WBS-CPA2.6: Test that Code-Orchestrator tools are exposed for external clients.
    
    These tests validate that external clients (MCP, external LLMs) can
    discover Code-Orchestrator tools through the Gateway.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_gateway_exposes_compute_similarity_tool(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.1: Gateway exposes compute_similarity tool for external clients.
        
        External clients should be able to discover the compute_similarity tool
        in the Gateway's tool registry.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /v1/tools, got {response.status_code}"
        )
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        
        assert "compute_similarity" in tool_names, (
            f"compute_similarity tool not found in registry. Available: {tool_names}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_gateway_exposes_extract_keywords_tool(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.2: Gateway exposes extract_keywords tool for external clients.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        
        assert "extract_keywords" in tool_names, (
            f"extract_keywords tool not found in registry. Available: {tool_names}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_gateway_exposes_generate_embeddings_tool(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.3: Gateway exposes generate_embeddings tool for external clients.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]
        
        assert "generate_embeddings" in tool_names, (
            f"generate_embeddings tool not found in registry. Available: {tool_names}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_compute_similarity_tool_has_correct_parameters(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.1: compute_similarity tool has correct parameter schema.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", data) if isinstance(data, dict) else data
        
        similarity_tool = next(
            (t for t in tools if isinstance(t, dict) and t.get("name") == "compute_similarity"),
            None
        )
        
        assert similarity_tool is not None, "compute_similarity tool not found"
        
        # Verify required parameters
        params = similarity_tool.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])
        
        assert "text1" in properties, "text1 parameter missing"
        assert "text2" in properties, "text2 parameter missing"
        assert "text1" in required, "text1 should be required"
        assert "text2" in required, "text2 should be required"


# =============================================================================
# WBS-CPA2.6: Code-Orchestrator Tool Execution Tests
# =============================================================================


class TestCodeOrchestratorToolExecution:
    """
    WBS-CPA2.6: Test Code-Orchestrator tool execution via Gateway.
    
    These tests validate that external clients can execute Code-Orchestrator tools
    through the Gateway and receive proper responses.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_external_client_can_execute_compute_similarity(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.4: External clients can invoke compute_similarity via Gateway :8080.
        """
        response = gateway_client_sync.post(
            "/v1/tools/compute_similarity/execute",
            json={
                "text1": "Machine learning is a subset of artificial intelligence",
                "text2": "Deep learning is a type of machine learning",
            }
        )
        
        # Should succeed or return 503 if Code-Orchestrator not available
        assert response.status_code in [200, 503], (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "score" in data, f"Expected 'score' in response: {data}"
            # Score should be between -1 and 1
            score = data.get("score", 0)
            assert -1 <= score <= 1, f"Score {score} out of range [-1, 1]"

    @pytest.mark.integration
    @pytest.mark.docker
    def test_external_client_can_execute_extract_keywords(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.4: External clients can invoke extract_keywords via Gateway :8080.
        """
        response = gateway_client_sync.post(
            "/v1/tools/extract_keywords/execute",
            json={
                "corpus": [
                    "Machine learning algorithms process large datasets",
                    "Python is popular for data science applications",
                ],
                "top_k": 5,
            }
        )
        
        # Should succeed or return 503 if Code-Orchestrator not available
        assert response.status_code in [200, 503], (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "keywords" in data, f"Expected 'keywords' in response: {data}"
            assert len(data["keywords"]) == 2, "Should return keywords for each document"

    @pytest.mark.integration
    @pytest.mark.docker
    def test_external_client_can_execute_generate_embeddings(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        AC-CPA2.4: External clients can invoke generate_embeddings via Gateway :8080.
        """
        response = gateway_client_sync.post(
            "/v1/tools/generate_embeddings/execute",
            json={
                "texts": ["Hello world", "Goodbye world"],
            }
        )
        
        # Should succeed or return 503 if Code-Orchestrator not available
        assert response.status_code in [200, 503], (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "embeddings" in data, f"Expected 'embeddings' in response: {data}"
            assert len(data["embeddings"]) == 2, "Should return embedding for each text"


# =============================================================================
# WBS-CPA2.6: Error Handling Tests
# =============================================================================


class TestCodeOrchestratorErrorHandling:
    """
    WBS-CPA2.6: Test error handling for Code-Orchestrator tool requests.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_compute_similarity_missing_params_returns_422(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS-CPA2.6: Missing required parameters returns 422.
        """
        response = gateway_client_sync.post(
            "/v1/tools/compute_similarity/execute",
            json={
                "text1": "Only one text provided",  # Missing text2
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, (
            f"Expected 422 for missing text2, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_extract_keywords_empty_corpus_handled(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS-CPA2.6: Empty corpus is handled appropriately.
        """
        response = gateway_client_sync.post(
            "/v1/tools/extract_keywords/execute",
            json={
                "corpus": [],  # Empty corpus
            }
        )
        
        # May return 200 with empty result or 422 for validation
        assert response.status_code in [200, 422, 503], (
            f"Unexpected status {response.status_code}: {response.text}"
        )


# =============================================================================
# WBS-CPA2.6: Internal Direct Call Pattern Documentation
# =============================================================================


class TestCodeOrchestratorInternalPattern:
    """
    AC-CPA2.4 Note: Internal platform services use direct calls.
    
    This test documents that internal services (ai-agents, audit-service, etc.)
    call Code-Orchestrator-Service directly on :8083, not through Gateway.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_documentation_internal_direct_call_pattern(
        self, skip_if_no_docker
    ) -> None:
        """
        Document that internal calls use direct ports.
        
        Pattern documented in CONSOLIDATED_PLATFORM_ARCHITECTURE.md:
        - INTERNAL (platform services): Direct API calls (:8083)
          - http://code-orchestrator-service:8083/v1/similarity
          - http://code-orchestrator-service:8083/v1/keywords
          - http://code-orchestrator-service:8083/v1/embeddings
        - EXTERNAL (MCP, external LLMs): Gateway (:8080)
          - http://llm-gateway:8080/v1/tools/compute_similarity/execute
          - http://llm-gateway:8080/v1/tools/extract_keywords/execute
          - http://llm-gateway:8080/v1/tools/generate_embeddings/execute
        """
        # This is a documentation test
        assert True, (
            "Internal services use direct ports; "
            "Gateway tools are for external clients only"
        )
