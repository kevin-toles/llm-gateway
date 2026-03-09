"""
Tests for Request Logging Middleware - WBS 2.2.5.1

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- ARCHITECTURE.md line 30: logging.py - Request/response logging
- GUIDELINES: Sinha pp. 89-91 (FastAPI middleware patterns)
- ANTI_PATTERN_ANALYSIS: §3.1 No bare except clauses

WBS Items Covered:
- 2.2.5.1.3: Implement request/response logging middleware
- 2.2.5.1.4: Log request method, path, duration
- 2.2.5.1.5: Log response status code
- 2.2.5.1.6: Redact sensitive headers (Authorization, API keys)
"""

import logging
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# RED Phase: These imports will fail until implementation
from src.api.middleware.logging import (
    RequestLoggingMiddleware,
    redact_sensitive_headers,
)


class TestRequestLoggingMiddleware:
    """Test suite for request logging middleware - WBS 2.2.5.1"""

    # =========================================================================
    # WBS 2.2.5.1.3: Middleware Implementation
    # =========================================================================

    def test_logging_middleware_exists(self):
        """
        WBS 2.2.5.1.3: RequestLoggingMiddleware class must exist.

        Pattern: ASGI middleware (FastAPI/Starlette)
        """
        assert RequestLoggingMiddleware is not None

    def test_logging_middleware_is_callable(self):
        """
        WBS 2.2.5.1.3: Middleware must be callable (ASGI spec).
        """
        app = FastAPI()
        middleware = RequestLoggingMiddleware(app)
        assert callable(middleware)

    # =========================================================================
    # WBS 2.2.5.1.4: Log Request Method, Path, Duration
    # =========================================================================

    def test_middleware_logs_request_method(self, client: TestClient, caplog):
        """
        WBS 2.2.5.1.4: Middleware must log HTTP method.
        """
        with caplog.at_level(logging.INFO):
            client.get("/test")

        assert any("GET" in record.message for record in caplog.records)

    def test_middleware_logs_request_path(self, client: TestClient, caplog):
        """
        WBS 2.2.5.1.4: Middleware must log request path.
        """
        with caplog.at_level(logging.INFO):
            client.get("/test/path")

        assert any("/test/path" in record.message for record in caplog.records)

    def test_middleware_logs_request_duration(self, client: TestClient, caplog):
        """
        WBS 2.2.5.1.4: Middleware must log request duration.
        """
        with caplog.at_level(logging.INFO):
            client.get("/test")

        # Duration should be in milliseconds format
        assert any(
            "ms" in record.message or "duration" in record.message.lower()
            for record in caplog.records
        )

    # =========================================================================
    # WBS 2.2.5.1.5: Log Response Status Code
    # =========================================================================

    def test_middleware_logs_response_status_200(self, client: TestClient, caplog):
        """
        WBS 2.2.5.1.5: Middleware must log response status code.
        """
        with caplog.at_level(logging.INFO):
            response = client.get("/test")
            assert response.status_code == 200

        assert any("200" in record.message for record in caplog.records)

    def test_middleware_logs_response_status_404(self, client: TestClient, caplog):
        """
        WBS 2.2.5.1.5: Middleware must log 404 status for non-existent routes.
        """
        with caplog.at_level(logging.INFO):
            response = client.get("/nonexistent")
            assert response.status_code == 404

        assert any("404" in record.message for record in caplog.records)

    # =========================================================================
    # WBS 2.2.5.1.6: Redact Sensitive Headers
    # =========================================================================

    def test_redact_authorization_header(self):
        """
        WBS 2.2.5.1.6: Authorization header must be redacted.

        Pattern: Security - never log credentials
        """
        headers = {
            "Authorization": "Bearer secret-token-12345",
            "Content-Type": "application/json",
        }

        redacted = redact_sensitive_headers(headers)

        assert redacted["Authorization"] == "[REDACTED]"
        assert redacted["Content-Type"] == "application/json"

    def test_redact_x_api_key_header(self):
        """
        WBS 2.2.5.1.6: X-API-Key header must be redacted.
        """
        headers = {
            "X-API-Key": "my-secret-api-key",
            "Accept": "application/json",
        }

        redacted = redact_sensitive_headers(headers)

        assert redacted["X-API-Key"] == "[REDACTED]"
        assert redacted["Accept"] == "application/json"

    def test_redact_api_key_header_variations(self):
        """
        WBS 2.2.5.1.6: Various API key header formats must be redacted.
        """
        headers = {
            "x-api-key": "secret1",  # lowercase
            "Api-Key": "secret2",  # different format
            "apikey": "secret3",  # no hyphen
            "X-Custom-Header": "not-secret",
        }

        redacted = redact_sensitive_headers(headers)

        assert redacted["x-api-key"] == "[REDACTED]"
        assert redacted["Api-Key"] == "[REDACTED]"
        assert redacted["apikey"] == "[REDACTED]"
        assert redacted["X-Custom-Header"] == "not-secret"

    def test_middleware_does_not_log_sensitive_headers(
        self, client: TestClient, caplog
    ):
        """
        WBS 2.2.5.1.6: Sensitive headers must not appear in logs.
        """
        with caplog.at_level(logging.DEBUG):
            client.get(
                "/test",
                headers={
                    "Authorization": "Bearer super-secret-token",
                    "X-API-Key": "another-secret",
                },
            )

        # Ensure secrets are NOT in logs
        log_output = " ".join(record.message for record in caplog.records)
        assert "super-secret-token" not in log_output
        assert "another-secret" not in log_output


class TestLoggingMiddlewareIntegration:
    """Integration tests for logging middleware with FastAPI app."""

    def test_middleware_preserves_response(self, client: TestClient):
        """
        Middleware must not alter response content.
        """
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json() == {"message": "test"}

    def test_middleware_handles_post_requests(self, client: TestClient, caplog):
        """
        Middleware must log POST requests correctly.
        """
        with caplog.at_level(logging.INFO):
            response = client.post("/test", json={"data": "value"})
            assert response.status_code == 200

        assert any("POST" in record.message for record in caplog.records)

    def test_middleware_logs_client_ip(self, client: TestClient, caplog):
        """
        Middleware should log client IP address.

        Pattern: Request tracing for debugging
        """
        with caplog.at_level(logging.INFO):
            client.get("/test")

        # TestClient uses "testclient" as host
        assert any(
            "testclient" in record.message.lower() or "127.0.0.1" in record.message
            for record in caplog.records
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with logging middleware applied.

    Pattern: Middleware integration testing
    """
    from src.api.middleware.logging import RequestLoggingMiddleware

    app = FastAPI()

    # Add logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Add test routes
    @app.get("/test")
    def test_route():
        return {"message": "test"}

    @app.post("/test")
    def test_post_route(data: dict = None):
        return {"message": "test", "received": data}

    return TestClient(app)
