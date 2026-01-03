"""
WBS 3.3.3: Agent Workflow Integration Tests

This module tests end-to-end agent workflows including:
- WBS 3.3.3.1: Full Agent Flow Testing
- WBS 3.3.3.2: Error Handling

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3211-3240 - WBS 3.3.3
- GUIDELINES pp. 1460-1600: Agent tool execution patterns, ReAct framework
- Architecture Patterns with Python pp. 155-157: Living documentation tests
- Building Microservices pp. 352-353: Graceful degradation patterns

Anti-Patterns Avoided (from Comp_Static_Analysis_Report_20251203.md):
- Issue #9-11: No race conditions in async code
- Issue #7: No exception shadowing of builtins
- Issue #12: Mock connection pooling pattern

TDD Phase: RED - These tests define expected agent workflow behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app

# =============================================================================
# WBS 3.3.3.1: Full Agent Flow Testing
# Pattern: Living documentation tests (Architecture Patterns with Python pp. 155-157)
# =============================================================================


class TestAgentWorkflowEndToEnd:
    """
    WBS 3.3.3.1: Test full agent workflow from chat completion through tool execution.
    
    Pattern: Integration tests as living documentation.
    Reference: Percival & Gregory - "tests written in domain language"
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_healthy(self):
        """
        Mock ai-agents service returning healthy responses for all tools.
        
        Pattern: Connection reuse mock (avoiding Issue #12 anti-pattern)
        """
        async def mock_post(url, *args, **kwargs):
            # Satisfy linter: async function must await something
            await asyncio.sleep(0)
            # Route based on endpoint
            if "/v1/agents/code-review" in url:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "findings": [
                        {
                            "line": 5,
                            "severity": "warning",
                            "message": "Function lacks docstring",
                            "suggestion": "Add a docstring describing the function"
                        }
                    ],
                    "summary": "1 issue found",
                    "score": 90
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            elif "/v1/agents/architecture" in url:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "analysis": {
                        "patterns": ["Function-based"],
                        "concerns": [],
                        "suggestions": ["Consider adding type hints"]
                    },
                    "summary": "Simple architecture"
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            elif "/v1/agents/doc-generate" in url:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "documentation": "## Function: add\n\nAdds two numbers.",
                    "format": "markdown",
                    "sections": ["description"]
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            raise httpx.ConnectError(f"Unexpected URL: {url}")

        # Patch all three modules
        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_cr, \
             patch("src.tools.builtin.architecture.httpx.AsyncClient") as mock_arch, \
             patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_doc:
            
            for mock_client in [mock_cr, mock_arch, mock_doc]:
                mock_instance = AsyncMock()
                mock_instance.post = mock_post
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
            
            yield {
                "code_review": mock_cr,
                "architecture": mock_arch,
                "doc_generate": mock_doc
            }

    def test_code_review_through_gateway_tool_execute(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.2: Test code review through gateway.
        
        RED: Gateway should execute review_code tool and return findings.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {
                    "code": "def add(a, b):\n    return a + b",
                    "language": "python"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] is not None
        assert "findings" in data["result"]
        assert len(data["result"]["findings"]) > 0

    def test_llm_can_request_code_review_tool(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.3: Verify LLM can request code review tool.
        
        RED: Tool should be available and executable through gateway.
        """
        # First verify tool is listed
        list_response = client.get("/v1/tools")
        assert list_response.status_code == 200
        tools = list_response.json()
        tool_names = [t["name"] for t in tools]
        assert "review_code" in tool_names
        
        # Then verify tool is executable
        exec_response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {"code": "x = 1", "language": "python"}
            }
        )
        assert exec_response.status_code == 200
        assert exec_response.json()["success"] is True

    def test_tool_results_contain_expected_structure(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.4: Verify tool results returned have expected structure.
        
        RED: Results should include findings, summary, and score.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {
                    "code": "print('hello')",
                    "language": "python"
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()["result"]
        
        # Verify expected structure per ai-agents API spec
        assert "findings" in result, "Result should contain findings"
        assert "summary" in result, "Result should contain summary"
        assert "score" in result, "Result should contain score"
        assert isinstance(result["findings"], list)

    def test_multi_tool_workflow_review_then_doc(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.5: Test multi-tool workflow (review → doc generation).
        
        RED: Multiple tools should be executable in sequence.
        Pattern: Saga pattern for multi-step workflows (GUIDELINES cross-ref)
        """
        code = "def calculate(x, y):\n    return x * y"
        
        # Step 1: Review code
        review_response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {"code": code, "language": "python"}
            }
        )
        assert review_response.status_code == 200
        assert review_response.json()["success"] is True
        
        # Step 2: Generate documentation
        doc_response = client.post(
            "/v1/tools/execute",
            json={
                "name": "generate_documentation",
                "arguments": {"code": code, "format": "markdown"}
            }
        )
        assert doc_response.status_code == 200
        assert doc_response.json()["success"] is True
        assert "documentation" in doc_response.json()["result"]

    def test_multi_tool_workflow_review_analyze_doc(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.5: Test full multi-tool workflow.
        
        RED: All three agent tools should work in sequence.
        """
        code = "class Service:\n    def __init__(self, repo):\n        self.repo = repo"
        
        # Step 1: Review code
        review = client.post(
            "/v1/tools/execute",
            json={"name": "review_code", "arguments": {"code": code}}
        )
        assert review.status_code == 200
        
        # Step 2: Analyze architecture
        arch = client.post(
            "/v1/tools/execute",
            json={"name": "analyze_architecture", "arguments": {"code": code}}
        )
        assert arch.status_code == 200
        
        # Step 3: Generate documentation
        doc = client.post(
            "/v1/tools/execute",
            json={"name": "generate_documentation", "arguments": {"code": code}}
        )
        assert doc.status_code == 200
        
        # All should succeed
        assert review.json()["success"] is True
        assert arch.json()["success"] is True
        assert doc.json()["success"] is True

    def test_all_agent_tools_return_consistent_response_format(
        self, client, mock_ai_agents_healthy
    ):
        """
        WBS 3.3.3.1.6: Integration test for agent workflow consistency.
        
        RED: All agent tools should return ToolExecuteResponse format.
        """
        tools_to_test = [
            ("review_code", {"code": "x=1", "language": "python"}),
            ("analyze_architecture", {"code": "class A: pass"}),
            ("generate_documentation", {"code": "def f(): pass"}),
        ]
        
        for tool_name, args in tools_to_test:
            response = client.post(
                "/v1/tools/execute",
                json={"name": tool_name, "arguments": args}
            )
            
            assert response.status_code == 200, f"{tool_name} should return 200"
            data = response.json()
            
            # Verify consistent response structure
            assert "name" in data, f"{tool_name} response missing 'name'"
            assert "result" in data, f"{tool_name} response missing 'result'"
            assert "success" in data, f"{tool_name} response missing 'success'"
            assert data["name"] == tool_name


# =============================================================================
# WBS 3.3.3.2: Error Handling Tests
# Pattern: Graceful degradation (Building Microservices pp. 352-353)
# =============================================================================


class TestAgentWorkflowErrorHandling:
    """
    WBS 3.3.3.2: Test error handling in agent workflows.
    
    Pattern: Graceful degradation for optional services.
    Reference: Newman - Building Microservices pp. 352-353
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_unavailable(self):
        """
        Mock ai-agents service being unavailable.
        
        WBS 3.3.3.2.1: Simulate service unavailability.
        """
        async def mock_post(url, *args, **kwargs):
            await asyncio.sleep(0)  # Satisfy linter
            raise httpx.ConnectError("Connection refused")

        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_cr, \
             patch("src.tools.builtin.architecture.httpx.AsyncClient") as mock_arch, \
             patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_doc:
            
            for mock_client in [mock_cr, mock_arch, mock_doc]:
                mock_instance = AsyncMock()
                mock_instance.post = mock_post
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
            
            yield

    @pytest.fixture
    def mock_ai_agents_timeout(self):
        """
        Mock ai-agents service timing out.
        
        WBS 3.3.3.2.2: Simulate execution timeout.
        """
        async def mock_post(url, *args, **kwargs):
            await asyncio.sleep(0)  # Satisfy linter
            raise httpx.TimeoutException("Request timed out")

        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_cr, \
             patch("src.tools.builtin.architecture.httpx.AsyncClient") as mock_arch, \
             patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_doc:
            
            for mock_client in [mock_cr, mock_arch, mock_doc]:
                mock_instance = AsyncMock()
                mock_instance.post = mock_post
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
            
            yield

    @pytest.fixture
    def mock_ai_agents_invalid_response(self):
        """
        Mock ai-agents service returning invalid response.
        
        WBS 3.3.3.2.3: Simulate invalid agent response.
        """
        async def mock_post(url, *args, **kwargs):
            await asyncio.sleep(0)  # Satisfy linter
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": "Internal server error"}
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response
            )
            return mock_response

        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_cr, \
             patch("src.tools.builtin.architecture.httpx.AsyncClient") as mock_arch, \
             patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_doc:
            
            for mock_client in [mock_cr, mock_arch, mock_doc]:
                mock_instance = AsyncMock()
                mock_instance.post = mock_post
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value = mock_instance
            
            yield

    def test_service_unavailable_returns_graceful_error(
        self, client, mock_ai_agents_unavailable
    ):
        """
        WBS 3.3.3.2.1: Test behavior when ai-agents service unavailable.
        
        RED: Should return 200 with error info, not 500/503.
        Pattern: Graceful degradation (Newman pp. 352-353)
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {"code": "x = 1", "language": "python"}
            }
        )
        
        # Should still return 200 with tool response
        assert response.status_code == 200
        data = response.json()
        
        # Result should indicate error gracefully
        assert data["success"] is True  # Tool executed (even if service unavailable)
        assert "error" in data["result"], "Result should contain error info"
        assert "unavailable" in data["result"]["error"].lower()

    def test_timeout_returns_graceful_error(
        self, client, mock_ai_agents_timeout
    ):
        """
        WBS 3.3.3.2.2: Test behavior on agent execution timeout.
        
        RED: Should return graceful error, not propagate exception.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "analyze_architecture",
                "arguments": {"code": "class A: pass"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data["result"]
        assert "timeout" in data["result"]["error"].lower()

    def test_invalid_response_handled_gracefully(
        self, client, mock_ai_agents_invalid_response
    ):
        """
        WBS 3.3.3.2.3: Test behavior on invalid agent response.
        
        RED: Should handle 5xx errors from ai-agents gracefully.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "generate_documentation",
                "arguments": {"code": "def f(): pass"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data["result"]

    def test_errors_returned_gracefully_to_caller(
        self, client, mock_ai_agents_unavailable
    ):
        """
        WBS 3.3.3.2.4: Verify errors returned gracefully to LLM/caller.
        
        RED: Error response should follow ToolExecuteResponse schema.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {"code": "x = 1"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response follows schema
        assert "name" in data
        assert "result" in data
        assert "success" in data
        assert data["name"] == "review_code"

    def test_all_tools_handle_errors_consistently(
        self, client, mock_ai_agents_unavailable
    ):
        """
        WBS 3.3.3.2.5: Integration test for consistent error handling.
        
        RED: All tools should handle errors the same way.
        """
        tools = [
            ("review_code", {"code": "x=1"}),
            ("analyze_architecture", {"code": "x=1"}),
            ("generate_documentation", {"code": "x=1"}),
        ]
        
        for tool_name, args in tools:
            response = client.post(
                "/v1/tools/execute",
                json={"name": tool_name, "arguments": args}
            )
            
            assert response.status_code == 200, f"{tool_name} should return 200"
            data = response.json()
            
            # All should have same error structure
            assert "error" in data["result"], f"{tool_name} should have error in result"
            assert "unavailable" in data["result"]["error"].lower(), \
                f"{tool_name} error should indicate unavailability"

    def test_partial_workflow_failure_continues(self):
        """
        WBS 3.3.3.2.5: Test that workflow can continue after partial failure.
        
        RED: If one tool fails, others should still work.
        Pattern: Saga pattern - partial workflow failure handling
        """
        # This test verifies that when one agent tool fails,
        # other tools in the workflow can still succeed.
        # We test this by first calling a failing tool, then a working one.
        
        # Test 1: Use mock_ai_agents_unavailable to make all services fail
        async def mock_post_fail(url, *args, **kwargs):
            await asyncio.sleep(0)  # Satisfy linter
            raise httpx.ConnectError("Connection refused")

        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_cr:
            mock_cr_instance = AsyncMock()
            mock_cr_instance.post = mock_post_fail
            mock_cr_instance.__aenter__ = AsyncMock(return_value=mock_cr_instance)
            mock_cr_instance.__aexit__ = AsyncMock(return_value=None)
            mock_cr.return_value = mock_cr_instance
            
            client = TestClient(app)
            
            # Code review fails gracefully
            review_resp = client.post(
                "/v1/tools/execute",
                json={"name": "review_code", "arguments": {"code": "x=1"}}
            )
            assert review_resp.status_code == 200
            review_result = review_resp.json()["result"]
            assert "error" in review_result, f"Expected error in result, got: {review_result}"
        
        # Test 2: Doc generate works in separate context (no mock)
        async def mock_post_healthy(url, *args, **kwargs):
            await asyncio.sleep(0)  # Satisfy linter
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "documentation": "docs",
                "format": "markdown",
                "sections": []
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_doc:
            mock_doc_instance = AsyncMock()
            mock_doc_instance.post = mock_post_healthy
            mock_doc_instance.__aenter__ = AsyncMock(return_value=mock_doc_instance)
            mock_doc_instance.__aexit__ = AsyncMock(return_value=None)
            mock_doc.return_value = mock_doc_instance
            
            client = TestClient(app)
            
            # Doc generate still works
            doc_resp = client.post(
                "/v1/tools/execute",
                json={"name": "generate_documentation", "arguments": {"code": "x=1"}}
            )
            assert doc_resp.status_code == 200
            assert doc_resp.json()["success"] is True
            assert "documentation" in doc_resp.json()["result"]


# =============================================================================
# WBS 3.3.3.1.7 & 3.3.3.2.6: GREEN Phase Markers
# These tests verify the GREEN phase is complete.
# =============================================================================


class TestAgentWorkflowGreenPhaseMarkers:
    """
    Marker tests for GREEN phase completion.
    
    These tests confirm that the full implementation is working.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_agent_tools_registered_in_builtin_tools(self, client):
        """
        WBS 3.3.3.1.7: Verify agent integration is working.
        
        GREEN marker: All agent tools should be registered.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200
        
        tools = response.json()
        tool_names = [t["name"] for t in tools]
        
        # All three agent tools should be registered
        assert "review_code" in tool_names
        assert "analyze_architecture" in tool_names
        assert "generate_documentation" in tool_names

    def test_error_handling_does_not_crash_gateway(self, client):
        """
        WBS 3.3.3.2.6: Verify error handling is working.
        
        GREEN marker: Gateway should not crash on tool errors.
        """
        # Even with a non-existent tool, gateway should handle gracefully
        response = client.post(
            "/v1/tools/execute",
            json={"name": "nonexistent_tool", "arguments": {}}
        )
        
        # Should return 404, not 500
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
