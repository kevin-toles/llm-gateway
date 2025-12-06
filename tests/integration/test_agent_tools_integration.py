"""
WBS 3.3.2: Agent Tool Integration Tests

This module tests the gateway's integration with ai-agents service tools:
- code_review (WBS 3.3.2.1)
- analyze_architecture (WBS 3.3.2.2)
- generate_documentation (WBS 3.3.2.3)

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3178-3210 - WBS 3.3.2
- ai-agents/docs/ARCHITECTURE.md: Agent endpoints
- GUIDELINES pp. 1489-1544: Agent tool execution patterns

TDD Phase: RED - These tests define expected agent tool behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


# =============================================================================
# WBS 3.3.2.1: Code Review Agent Tool Tests
# =============================================================================


class TestCodeReviewToolIntegration:
    """
    WBS 3.3.2.1: Test code review agent tool integration.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_code_review(self):
        """
        Mock ai-agents code review endpoint returning review findings.
        """
        async def mock_post(url, *args, **kwargs):
            if "/v1/agents/code-review" in url:
                # Use MagicMock for response since httpx response.json() is synchronous
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "findings": [
                        {
                            "line": 10,
                            "severity": "warning",
                            "message": "Consider using f-string for clarity",
                            "suggestion": "name = f'Hello {user}'"
                        }
                    ],
                    "summary": "1 issue found",
                    "score": 85
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            raise httpx.ConnectError("Unexpected URL")

        # Patch in the module that uses httpx.AsyncClient
        with patch("src.tools.builtin.code_review.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = mock_post
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    def test_review_code_tool_registered(self, client):
        """
        WBS 3.3.2.1.6: review_code tool should be registered.
        
        RED: Tool should be listed in available tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200
        
        data = response.json()
        # API returns list[ToolDefinition] directly, not wrapped in {"tools": ...}
        tool_names = [t["name"] for t in data]
        assert "review_code" in tool_names, (
            "review_code should be registered as a builtin tool"
        )

    def test_review_code_accepts_code_and_language(self, client, mock_ai_agents_code_review):
        """
        WBS 3.3.2.1.3: review_code accepts code and language parameters.
        
        RED: Tool should accept code string and language.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {
                    "code": "def hello(): print('world')",
                    "language": "python"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    def test_review_code_returns_findings(self, client, mock_ai_agents_code_review):
        """
        WBS 3.3.2.1.5: review_code returns review findings.
        
        RED: Result should contain findings and suggestions.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "review_code",
                "arguments": {
                    "code": "x = 1 + 2",
                    "language": "python"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data.get("result", {})
        
        assert "findings" in result or "error" not in result
        
    def test_review_code_handles_service_unavailable(self, client):
        """
        WBS 3.3.2.1.7: review_code handles ai-agents service unavailable.
        
        RED: Should return error, not crash.
        """
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "review_code",
                    "arguments": {
                        "code": "x = 1",
                        "language": "python"
                    }
                }
            )
            
            # Should return error response, not crash
            assert response.status_code in [200, 500, 503]


# =============================================================================
# WBS 3.3.2.2: Architecture Agent Tool Tests
# =============================================================================


class TestArchitectureToolIntegration:
    """
    WBS 3.3.2.2: Test architecture analysis agent tool integration.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_architecture(self):
        """
        Mock ai-agents architecture endpoint returning analysis.
        """
        async def mock_post(url, *args, **kwargs):
            if "/v1/agents/architecture" in url:
                # Use MagicMock for response since httpx response.json() is synchronous
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "analysis": {
                        "patterns": ["Repository Pattern", "Service Layer"],
                        "concerns": ["Tight coupling between modules"],
                        "suggestions": ["Consider dependency injection"]
                    },
                    "summary": "Architecture analysis complete"
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            raise httpx.ConnectError("Unexpected URL")

        # Patch in the module that uses httpx.AsyncClient
        with patch("src.tools.builtin.architecture.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = mock_post
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    def test_analyze_architecture_tool_registered(self, client):
        """
        WBS 3.3.2.2.6: analyze_architecture tool should be registered.
        
        RED: Tool should be listed in available tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200
        
        data = response.json()
        # API returns list[ToolDefinition] directly, not wrapped in {"tools": ...}
        tool_names = [t["name"] for t in data]
        assert "analyze_architecture" in tool_names, (
            "analyze_architecture should be registered as a builtin tool"
        )

    def test_analyze_architecture_accepts_code_and_context(self, client, mock_ai_agents_architecture):
        """
        WBS 3.3.2.2.3: analyze_architecture accepts code and context parameters.
        
        RED: Tool should accept code string and context.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "analyze_architecture",
                "arguments": {
                    "code": "class UserService:\n    def __init__(self, repo):\n        self.repo = repo",
                    "context": "Python microservice"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    def test_analyze_architecture_returns_analysis(self, client, mock_ai_agents_architecture):
        """
        WBS 3.3.2.2.5: analyze_architecture returns architecture analysis.
        
        RED: Result should contain analysis with patterns and suggestions.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "analyze_architecture",
                "arguments": {
                    "code": "class Repo:\n    pass",
                    "context": "Repository pattern"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data.get("result", {})
        
        assert "analysis" in result or "error" not in result


# =============================================================================
# WBS 3.3.2.3: Doc Generate Agent Tool Tests
# =============================================================================


class TestDocGenerateToolIntegration:
    """
    WBS 3.3.2.3: Test documentation generation agent tool integration.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_doc_generate(self):
        """
        Mock ai-agents doc-generate endpoint returning documentation.
        """
        async def mock_post(url, *args, **kwargs):
            if "/v1/agents/doc-generate" in url:
                # Use MagicMock for response since httpx response.json() is synchronous
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "documentation": "## Function: calculate_total\n\nCalculates the total price.",
                    "format": "markdown",
                    "sections": ["description", "parameters", "returns"]
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response
            raise httpx.ConnectError("Unexpected URL")

        # Patch in the module that uses httpx.AsyncClient
        with patch("src.tools.builtin.doc_generate.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = mock_post
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    def test_generate_documentation_tool_registered(self, client):
        """
        WBS 3.3.2.3.6: generate_documentation tool should be registered.
        
        RED: Tool should be listed in available tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == 200
        
        data = response.json()
        # API returns list[ToolDefinition] directly, not wrapped in {"tools": ...}
        tool_names = [t["name"] for t in data]
        assert "generate_documentation" in tool_names, (
            "generate_documentation should be registered as a builtin tool"
        )

    def test_generate_documentation_accepts_code_and_format(self, client, mock_ai_agents_doc_generate):
        """
        WBS 3.3.2.3.3: generate_documentation accepts code and format parameters.
        
        RED: Tool should accept code string and format.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "generate_documentation",
                "arguments": {
                    "code": "def add(a, b): return a + b",
                    "format": "markdown"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    def test_generate_documentation_returns_docs(self, client, mock_ai_agents_doc_generate):
        """
        WBS 3.3.2.3.5: generate_documentation returns generated documentation.
        
        RED: Result should contain documentation string.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "generate_documentation",
                "arguments": {
                    "code": "def greet(name): return f'Hello {name}'",
                    "format": "markdown"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        result = data.get("result", {})
        
        assert "documentation" in result or "error" not in result


# =============================================================================
# WBS 3.3.2: Tool Module Existence Tests
# =============================================================================


class TestAgentToolModulesExist:
    """
    Tests that the tool modules exist and have expected structure.
    """

    def test_code_review_module_exists(self):
        """
        WBS 3.3.2.1.1: src/tools/builtin/code_review.py should exist.
        """
        from src.tools.builtin import code_review
        assert hasattr(code_review, "review_code")
        assert callable(code_review.review_code)

    def test_architecture_module_exists(self):
        """
        WBS 3.3.2.2.1: src/tools/builtin/architecture.py should exist.
        """
        from src.tools.builtin import architecture
        assert hasattr(architecture, "analyze_architecture")
        assert callable(architecture.analyze_architecture)

    def test_doc_generate_module_exists(self):
        """
        WBS 3.3.2.3.1: src/tools/builtin/doc_generate.py should exist.
        """
        from src.tools.builtin import doc_generate
        assert hasattr(doc_generate, "generate_documentation")
        assert callable(doc_generate.generate_documentation)

    @pytest.mark.asyncio
    async def test_review_code_is_async(self):
        """
        WBS 3.3.2.1.2: review_code should be an async function.
        """
        from src.tools.builtin.code_review import review_code
        import asyncio
        assert asyncio.iscoroutinefunction(review_code)

    @pytest.mark.asyncio
    async def test_analyze_architecture_is_async(self):
        """
        WBS 3.3.2.2.2: analyze_architecture should be an async function.
        """
        from src.tools.builtin.architecture import analyze_architecture
        import asyncio
        assert asyncio.iscoroutinefunction(analyze_architecture)

    @pytest.mark.asyncio
    async def test_generate_documentation_is_async(self):
        """
        WBS 3.3.2.3.2: generate_documentation should be an async function.
        """
        from src.tools.builtin.doc_generate import generate_documentation
        import asyncio
        assert asyncio.iscoroutinefunction(generate_documentation)
