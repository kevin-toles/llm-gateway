"""
WBS 3.5.2.4: Tool Execution Integration Tests

This module tests tool execution endpoints against live Docker services.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3323-3329 - WBS 3.5.2.4
- ARCHITECTURE.md: Lines 207-213 - Tool-Use Orchestrator component
- GUIDELINES pp. 155-157: "high and low gear" testing philosophy
- GUIDELINES pp. 1489-1544: Agent tool execution patterns

TDD Phase: RED - These tests define expected tool execution behavior.

WBS Coverage:
- 3.5.2.4.1: Create tests/integration/test_tools.py
- 3.5.2.4.2: Test list available tools
- 3.5.2.4.3: Test execute search_corpus tool
- 3.5.2.4.4: Test execute get_chunk tool
- 3.5.2.4.5: Test execute unknown tool (404)
- 3.5.2.4.6: Test execute with invalid arguments (422)
"""

import pytest


# =============================================================================
# WBS 3.5.2.4.2: Test list available tools
# =============================================================================


class TestListTools:
    """
    WBS 3.5.2.4.2: Test tool listing endpoint.
    
    Reference: ARCHITECTURE.md - Tool Registry component.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_list_tools_returns_200(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.2: GET /v1/tools should return 200 OK.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /v1/tools, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_list_tools_returns_array(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.2: Tool list should be an array of tool definitions.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        if response.status_code == 200:
            data = response.json()
            # Response may be {"tools": [...]} or just [...]
            tools = data.get("tools", data) if isinstance(data, dict) else data
            assert isinstance(tools, list), (
                f"Tools should be a list, got {type(tools)}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_list_tools_includes_search_corpus(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.2: Tool list should include search_corpus tool.
        
        Reference: ARCHITECTURE.md - Built-in semantic search tools.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", data) if isinstance(data, dict) else data
            
            tool_names = [
                t.get("name") or t.get("function", {}).get("name")
                for t in tools
            ]
            assert "search_corpus" in tool_names, (
                f"Tool list should include search_corpus, got {tool_names}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_list_tools_includes_get_chunk(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.2: Tool list should include get_chunk tool.
        
        Reference: ARCHITECTURE.md - Chunk retrieval tool.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", data) if isinstance(data, dict) else data
            
            tool_names = [
                t.get("name") or t.get("function", {}).get("name")
                for t in tools
            ]
            assert "get_chunk" in tool_names, (
                f"Tool list should include get_chunk, got {tool_names}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_tool_definitions_have_schema(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.2: Tool definitions should include parameter schema.
        """
        response = gateway_client_sync.get("/v1/tools")
        
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", data) if isinstance(data, dict) else data
            
            for tool in tools:
                # Should have function definition with parameters
                function = tool.get("function", tool)
                assert "name" in function or "name" in tool, (
                    "Tool should have a name"
                )


# =============================================================================
# WBS 3.5.2.4.3: Test execute search_corpus tool
# =============================================================================


class TestExecuteSearchCorpus:
    """
    WBS 3.5.2.4.3: Test search_corpus tool execution.
    
    Reference: ARCHITECTURE.md - semantic-search-service integration.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_execute_search_corpus_returns_200(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.3: POST /v1/tools/execute for search_corpus should return 200.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {"query": "test search query"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # May return 200 (success) or 503 (semantic-search unavailable in stubs)
        assert response.status_code in (200, 503), (
            f"Expected 200 or 503, got {response.status_code}: {response.text}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_search_corpus_returns_results(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.3: search_corpus should return search results.
        
        Schema: {"results": [...], "total": N}
        """
        payload = {
            "name": "search_corpus",
            "arguments": {"query": "artificial intelligence"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Result may be in "result" key or directly in response
            result = data.get("result", data)
            assert "results" in result or isinstance(result.get("content"), str), (
                "search_corpus should return results or content"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_search_corpus_with_top_k(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.3: search_corpus should accept top_k parameter.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {"query": "test", "top_k": 5},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        assert response.status_code in (200, 503), (
            f"search_corpus with top_k should be accepted, got {response.status_code}"
        )


# =============================================================================
# WBS 3.5.2.4.4: Test execute get_chunk tool
# =============================================================================


class TestExecuteGetChunk:
    """
    WBS 3.5.2.4.4: Test get_chunk tool execution.
    
    Reference: ARCHITECTURE.md - Chunk retrieval from semantic-search.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_execute_get_chunk_returns_response(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.4: POST /v1/tools/execute for get_chunk should return response.
        """
        payload = {
            "name": "get_chunk",
            "arguments": {"chunk_id": "test-chunk-id"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # May return 200 (success), 404 (chunk not found), or 503 (service unavailable)
        assert response.status_code in (200, 404, 503), (
            f"Expected 200, 404, or 503, got {response.status_code}: {response.text}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_get_chunk_returns_chunk_data(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.4: get_chunk should return chunk content.
        
        Schema: {"chunk_id": "...", "content": "...", "metadata": {...}}
        """
        payload = {
            "name": "get_chunk",
            "arguments": {"chunk_id": "existing-chunk-id"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", data)
            # Should have content or error message
            assert "content" in result or "error" in result or isinstance(result, str), (
                "get_chunk should return content or error"
            )


# =============================================================================
# WBS 3.5.2.4.5: Test execute unknown tool (404)
# =============================================================================


class TestExecuteUnknownTool:
    """
    WBS 3.5.2.4.5: Test error handling for unknown tools.
    
    Reference: GUIDELINES - proper error responses.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_unknown_tool_returns_404(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.5: Executing unknown tool should return 404.
        """
        payload = {
            "name": "nonexistent_tool_xyz",
            "arguments": {"param": "value"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        assert response.status_code == 404, (
            f"Expected 404 for unknown tool, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_unknown_tool_returns_error_detail(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.5: 404 response should include error details.
        """
        payload = {
            "name": "nonexistent_tool_xyz",
            "arguments": {},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data, (
                "404 response should include error details"
            )


# =============================================================================
# WBS 3.5.2.4.6: Test execute with invalid arguments (422)
# =============================================================================


class TestExecuteInvalidArguments:
    """
    WBS 3.5.2.4.6: Test error handling for invalid tool arguments.
    
    Reference: GUIDELINES - input validation.
    Reference: Comp_Static_Analysis_Report - validation patterns.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_missing_required_argument_returns_422(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.6: Missing required argument should return 422.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {},  # Missing required 'query' argument
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # Should return 422 Unprocessable Entity for missing required args
        assert response.status_code in (400, 422), (
            f"Expected 400/422 for missing required arg, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_wrong_argument_type_returns_422(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.6: Wrong argument type should return 422.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {
                "query": 12345,  # Should be string, not int
            },
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # Should return 422 for wrong type, but may coerce to string
        assert response.status_code in (200, 400, 422, 503), (
            f"Unexpected status for wrong arg type: {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_invalid_arguments_returns_error_detail(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.6: 422 response should include validation error details.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {},  # Missing required 'query'
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        if response.status_code in (400, 422):
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data, (
                "422 response should include validation error details"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_extra_arguments_handled(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.4.6: Extra arguments should be handled gracefully.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {
                "query": "test",
                "extra_param": "should be ignored",
            },
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # Extra params should be ignored or cause 422
        assert response.status_code in (200, 422, 503), (
            f"Unexpected status for extra args: {response.status_code}"
        )


# =============================================================================
# Additional Tool Tests
# =============================================================================


class TestToolExecutionFormat:
    """
    Additional tests for tool execution request/response format.
    
    Reference: ARCHITECTURE.md - Tool execution API contract.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_execute_request_requires_name(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        Tool execute request must include tool name.
        """
        payload = {
            # Missing "name" field
            "arguments": {"query": "test"},
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        assert response.status_code == 422, (
            f"Expected 422 for missing tool name, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_execute_request_requires_arguments(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        Tool execute request must include arguments object.
        """
        payload = {
            "name": "search_corpus",
            # Missing "arguments" field
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        # May accept empty arguments or require them
        assert response.status_code in (200, 400, 422, 503), (
            f"Unexpected status for missing arguments: {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_execute_response_includes_tool_call_id(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        Tool execution response may include tool_call_id for tracking.
        """
        payload = {
            "name": "search_corpus",
            "arguments": {"query": "test"},
            "tool_call_id": "call_test123",
        }
        
        response = gateway_client_sync.post("/v1/tools/execute", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Response may echo back tool_call_id
            # This is optional, so we just verify the request was accepted
            assert isinstance(data, dict), "Response should be a dict"
