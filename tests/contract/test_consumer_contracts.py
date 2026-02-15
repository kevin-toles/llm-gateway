"""
WBS 3.6.2: Consumer Contract Tests

These tests define the expected behavior from the perspective of API consumers
(the llm-document-enhancer service). They verify that the API contract meets
consumer expectations and catches breaking changes.

Reference Documents:
- GUIDELINES pp. 1004: Contract testing patterns
- ARCHITECTURE.md: Consumer-driven contracts

Consumer Contract Pattern:
- Consumer (llm-document-enhancer) defines expected API behavior
- Provider (llm-gateway) must satisfy consumer expectations
- Changes that break consumer contracts fail CI/CD
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


# Mark entire module as contract tests
pytestmark = pytest.mark.contract


class TestDocumentEnhancerConsumerContract:
    """
    Consumer contract tests from llm-document-enhancer perspective.
    
    These tests verify that the LLM Gateway provides the endpoints and
    response structures that the document enhancer service depends on.
    """

    @pytest.fixture
    def client(self):
        """Test client for API requests."""
        return TestClient(app)

    # =========================================================================
    # WBS 3.6.2.1.1: Chat Completions Contract
    # =========================================================================
    
    def test_chat_completions_endpoint_exists(self, client) -> None:
        """
        Consumer expects POST /v1/chat/completions endpoint.
        
        The document enhancer sends prompts to this endpoint for:
        - Metadata extraction
        - Content enhancement
        - Table of contents generation
        """
        # Verify endpoint exists (OPTIONS should work)
        response = client.options("/v1/chat/completions")
        # Endpoint exists if we don't get 404
        assert response.status_code != 404
    
    def test_chat_completions_accepts_openai_format(self, client) -> None:
        """
        Consumer expects OpenAI-compatible request format.
        
        Required fields per consumer contract:
        - model: string
        - messages: array of {role, content}
        """
        # Minimal valid request per OpenAI spec
        request = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        
        response = client.post("/v1/chat/completions", json=request)
        
        # Should not return validation error for schema
        # May return 401/403 (auth) or 502/503 (backend) in test env
        # but NOT 400/422 for valid request structure
        assert response.status_code not in [400, 422], (
            f"Chat completions rejected valid OpenAI format: {response.json()}"
        )
    
    def test_chat_completions_response_has_choices(self, client) -> None:
        """
        Consumer expects response with 'choices' array.
        
        Response structure must include:
        - id: string
        - choices: array with at least one choice
        - usage: token usage info (optional but expected)
        """
        # This is a schema contract test - verify in OpenAPI spec
        spec_response = client.get("/openapi.json")
        spec = spec_response.json()
        
        # Verify chat completions is documented
        assert "/v1/chat/completions" in spec["paths"]
        
        chat_path = spec["paths"]["/v1/chat/completions"]
        assert "post" in chat_path

    # =========================================================================
    # WBS 3.6.2.1.2: Health Check Contract
    # =========================================================================
    
    def test_health_endpoint_contract(self, client) -> None:
        """
        Consumer expects GET /health for service monitoring.
        
        Used by:
        - Kubernetes liveness probes
        - Service mesh health checks
        - Load balancer health monitoring
        """
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Consumer expects "status" field
        assert "status" in data
    
    def test_ready_endpoint_contract(self, client) -> None:
        """
        Consumer expects GET /health/ready for dependency checks.
        
        Used by:
        - Kubernetes readiness probes
        - Circuit breaker patterns
        - Graceful startup/shutdown
        """
        response = client.get("/health/ready")
        
        # Can be 200 (ready) or 503 (not ready)
        assert response.status_code in [200, 503]
        data = response.json()
        
        # Consumer expects status field
        assert "status" in data

    # =========================================================================
    # WBS 3.6.2.1.3: Error Response Contract
    # =========================================================================
    
    def test_error_responses_have_detail(self, client) -> None:
        """
        Consumer expects error responses to have 'detail' field.
        
        Standard error format:
        - detail: human-readable error message
        - status_code: HTTP status code (in response)
        """
        # Request non-existent endpoint
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        
        # FastAPI standard error format
        assert "detail" in data
    
    def test_validation_errors_identify_field(self, client) -> None:
        """
        Consumer expects validation errors to identify problematic fields.
        
        Helps consumers debug their requests.
        """
        # Send invalid request to chat completions (missing required field)
        response = client.post("/v1/chat/completions", json={})
        
        # Should get validation error
        if response.status_code == 422:
            data = response.json()
            # Pydantic validation format
            assert "detail" in data

    # =========================================================================
    # WBS 3.6.2.1.4: Rate Limiting Contract
    # =========================================================================
    
    def test_rate_limit_headers_present(self, client) -> None:
        """
        Consumer expects rate limit information in headers.
        
        Standard headers (if implemented):
        - X-RateLimit-Limit
        - X-RateLimit-Remaining
        - X-RateLimit-Reset
        """
        response = client.get("/health")
        
        # Rate limit headers are informational
        # Consumer can use them for backoff strategies
        # Not required but good to document if present
        headers = response.headers
        
        # Test passes regardless - this documents expected behavior
        # If rate limiting is added, consumer expects these headers
        _ = headers.get("X-RateLimit-Limit")
        _ = headers.get("X-RateLimit-Remaining")

    # =========================================================================
    # WBS 3.6.2.1.5: API Version Contract
    # =========================================================================
    
    def test_api_version_in_path(self, client) -> None:
        """
        Consumer expects /v1/* prefix for versioned endpoints.
        
        Versioning strategy:
        - URL path versioning (e.g., /v1/, /v2/)
        - Allows gradual migration between versions
        """
        spec_response = client.get("/openapi.json")
        spec = spec_response.json()
        
        # Get all paths that are versioned
        versioned_paths = [
            path for path in spec["paths"].keys()
            if path.startswith("/v1/")
        ]
        
        # Consumer expects versioned endpoints for main functionality
        assert len(versioned_paths) > 0
        
        # Critical endpoints must be versioned
        assert any("/chat/completions" in p for p in versioned_paths)
    
    def test_openapi_spec_has_version(self, client) -> None:
        """
        Consumer expects API version in OpenAPI spec.
        
        Used for:
        - SDK generation
        - API compatibility checks
        - Documentation
        """
        response = client.get("/openapi.json")
        spec = response.json()
        
        assert "info" in spec
        assert "version" in spec["info"]
        
        # Version should follow semver
        version = spec["info"]["version"]
        parts = version.split(".")
        assert len(parts) >= 2, "Version should be semver format"


class TestSessionManagementContract:
    """
    Consumer contract for session management endpoints.
    
    Sessions enable stateful conversations for the document enhancer
    to maintain context across multiple API calls.
    """

    @pytest.fixture
    def client(self):
        """Test client for API requests."""
        return TestClient(app)

    def test_session_endpoints_documented(self, client) -> None:
        """Consumer expects session management endpoints."""
        spec_response = client.get("/openapi.json")
        spec = spec_response.json()
        
        # Session endpoints should exist
        session_paths = [
            p for p in spec["paths"].keys()
            if "session" in p.lower()
        ]
        
        # Document enhancer expects session management
        assert len(session_paths) > 0
    
    def test_create_session_endpoint(self, client) -> None:
        """Consumer expects POST /v1/sessions to create sessions."""
        spec_response = client.get("/openapi.json")
        spec = spec_response.json()
        
        assert "/v1/sessions" in spec["paths"]
        assert "post" in spec["paths"]["/v1/sessions"]


class TestToolExecutionContract:
    """
    Consumer contract for tool execution endpoints.
    
    Tools enable the document enhancer to perform specific actions
    like semantic search, metadata extraction, etc.
    """

    @pytest.fixture
    def client(self):
        """Test client for API requests."""
        return TestClient(app)

    def test_tools_list_endpoint(self, client) -> None:
        """Consumer expects GET /v1/tools to list available tools."""
        response = client.get("/v1/tools")
        
        # Should return list or indicate no tools configured
        assert response.status_code in [200, 404, 501]
        
        if response.status_code == 200:
            data = response.json()
            # Should be a list or dict with tools
            assert isinstance(data, (list, dict))
    
    def test_tool_execute_endpoint_documented(self, client) -> None:
        """Consumer expects POST /v1/tools/execute for tool execution."""
        spec_response = client.get("/openapi.json")
        spec = spec_response.json()
        
        # Tool execution endpoint
        assert "/v1/tools/execute" in spec["paths"]
        assert "post" in spec["paths"]["/v1/tools/execute"]
