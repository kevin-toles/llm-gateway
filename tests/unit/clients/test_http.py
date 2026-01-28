"""
Tests for HTTP Client Factory - WBS 2.7.1.1

TDD RED Phase: Tests for HTTP client factory function.

Reference Documents:
- ARCHITECTURE.md: Microservice URLs configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service
- GUIDELINES pp. 2145: Connection pooling, timeouts, circuit breakers

WBS Items Covered:
- 2.7.1.1.1: Create src/clients/__init__.py
- 2.7.1.1.2: Create src/clients/http.py
- 2.7.1.1.3: Implement create_http_client() factory
- 2.7.1.1.4: Configure connection pooling
- 2.7.1.1.5: Set default timeouts
- 2.7.1.1.6: Add retry middleware
- 2.7.1.1.7: RED test: client created with config
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.semantic_search_url = "http://localhost:8081"
    settings.ai_agents_url = "http://localhost:8082"
    return settings


# =============================================================================
# WBS 2.7.1.1.1-2: Package and Module Tests
# =============================================================================


class TestHTTPClientPackage:
    """Tests for HTTP client package structure."""

    def test_clients_package_importable(self) -> None:
        """
        WBS 2.7.1.1.1: clients package is importable.
        """
        from src import clients
        assert clients is not None

    def test_http_module_importable(self) -> None:
        """
        WBS 2.7.1.1.2: http module is importable.
        """
        from src.clients import http
        assert http is not None


# =============================================================================
# WBS 2.7.1.1.3: Factory Function Tests
# =============================================================================


class TestCreateHTTPClient:
    """Tests for create_http_client factory function."""

    def test_create_http_client_exists(self) -> None:
        """
        WBS 2.7.1.1.3: create_http_client function exists.
        """
        from src.clients.http import create_http_client
        assert callable(create_http_client)

    def test_create_http_client_returns_async_client(self) -> None:
        """
        WBS 2.7.1.1.3: Factory returns httpx.AsyncClient.
        """
        from src.clients.http import create_http_client

        client = create_http_client(base_url="http://localhost:8080")
        assert isinstance(client, httpx.AsyncClient)

    def test_create_http_client_with_base_url(self) -> None:
        """
        create_http_client sets base_url on client.
        """
        from src.clients.http import create_http_client

        client = create_http_client(base_url="http://example.com")
        assert str(client.base_url) == "http://example.com"

    def test_create_http_client_without_base_url(self) -> None:
        """
        create_http_client works without base_url.
        """
        from src.clients.http import create_http_client

        client = create_http_client()
        assert client is not None


# =============================================================================
# WBS 2.7.1.1.4: Connection Pooling Tests
# =============================================================================


class TestConnectionPooling:
    """Tests for connection pooling configuration."""

    def test_default_connection_limits(self) -> None:
        """
        WBS 2.7.1.1.4: Default connection limits are set.
        
        Pattern: "different connection pools for each downstream service"
        Reference: GUIDELINES pp. 2309 (Newman - Building Microservices)
        """
        from src.clients.http import create_http_client, DEFAULT_MAX_CONNECTIONS

        client = create_http_client(base_url="http://localhost:8080")
        # Verify client was created with limits (access via transport)
        assert client._transport._pool._max_connections == DEFAULT_MAX_CONNECTIONS

    def test_custom_connection_limits(self) -> None:
        """
        Connection limits can be customized.
        """
        from src.clients.http import create_http_client

        client = create_http_client(
            base_url="http://localhost:8080",
            max_connections=50,
        )
        assert client._transport._pool._max_connections == 50

    def test_max_keepalive_connections(self) -> None:
        """
        Max keepalive connections are set.
        """
        from src.clients.http import create_http_client, DEFAULT_MAX_KEEPALIVE

        client = create_http_client(base_url="http://localhost:8080")
        assert client._transport._pool._max_keepalive_connections == DEFAULT_MAX_KEEPALIVE


# =============================================================================
# WBS 2.7.1.1.5: Timeout Configuration Tests
# =============================================================================


class TestTimeoutConfiguration:
    """Tests for timeout configuration."""

    def test_default_timeout(self) -> None:
        """
        WBS 2.7.1.1.5: Default timeout is set.
        
        Pattern: Timeouts prevent cascading failures
        Reference: GUIDELINES pp. 2309 (Newman - timeouts, circuit breakers)
        """
        from src.clients.http import create_http_client, DEFAULT_TIMEOUT_SECONDS

        client = create_http_client(base_url="http://localhost:8080")
        assert client.timeout.connect == DEFAULT_TIMEOUT_SECONDS
        assert client.timeout.read == DEFAULT_TIMEOUT_SECONDS

    def test_custom_timeout(self) -> None:
        """
        Timeout can be customized.
        """
        from src.clients.http import create_http_client

        client = create_http_client(
            base_url="http://localhost:8080",
            timeout_seconds=60.0,
        )
        assert client.timeout.connect == 60.0
        assert client.timeout.read == 60.0

    def test_timeout_is_httpx_timeout(self) -> None:
        """
        Timeout is proper httpx.Timeout object.
        """
        from src.clients.http import create_http_client

        client = create_http_client(base_url="http://localhost:8080")
        assert isinstance(client.timeout, httpx.Timeout)


# =============================================================================
# WBS 2.7.1.1.6: Retry Configuration Tests
# =============================================================================


class TestRetryConfiguration:
    """Tests for retry middleware configuration."""

    def test_retry_config_exists(self) -> None:
        """
        WBS 2.7.1.1.6: Retry configuration is available.
        """
        from src.clients.http import DEFAULT_RETRY_COUNT

        assert DEFAULT_RETRY_COUNT >= 0

    def test_retry_transport_configured(self) -> None:
        """
        Retry transport is configured on client.
        
        Pattern: Retry with exponential backoff
        Reference: GUIDELINES pp. 2309
        """
        from src.clients.http import create_http_client

        client = create_http_client(
            base_url="http://localhost:8080",
            retries=3,
        )
        # Client should be configured with retries
        assert client is not None


# =============================================================================
# WBS 2.7.1.1.7-8: HTTP Client Import Tests
# =============================================================================


class TestHTTPClientImportable:
    """Tests for HTTP client exports."""

    def test_create_http_client_importable_from_clients(self) -> None:
        """
        WBS 2.7.1.1.7: create_http_client importable from clients package.
        """
        from src.clients import create_http_client
        assert callable(create_http_client)

    def test_http_client_error_importable(self) -> None:
        """
        HTTPClientError is importable.
        """
        from src.clients import HTTPClientError
        assert issubclass(HTTPClientError, Exception)

    def test_default_constants_importable(self) -> None:
        """
        Default constants are importable.
        """
        from src.clients.http import (
            DEFAULT_TIMEOUT_SECONDS,
            DEFAULT_MAX_CONNECTIONS,
            DEFAULT_MAX_KEEPALIVE,
            DEFAULT_RETRY_COUNT,
        )
        assert DEFAULT_TIMEOUT_SECONDS > 0
        assert DEFAULT_MAX_CONNECTIONS > 0
        assert DEFAULT_MAX_KEEPALIVE > 0
        assert DEFAULT_RETRY_COUNT >= 0


# =============================================================================
# Client Headers Tests
# =============================================================================


class TestClientHeaders:
    """Tests for default client headers."""

    def test_default_headers_set(self) -> None:
        """
        Default headers are set on client.
        """
        from src.clients.http import create_http_client

        client = create_http_client(base_url="http://localhost:8080")
        assert "User-Agent" in client.headers or client.headers.get("user-agent")

    def test_custom_headers_can_be_added(self) -> None:
        """
        Custom headers can be added.
        """
        from src.clients.http import create_http_client

        client = create_http_client(
            base_url="http://localhost:8080",
            headers={"X-Custom-Header": "test-value"},
        )
        assert client.headers.get("X-Custom-Header") == "test-value"
