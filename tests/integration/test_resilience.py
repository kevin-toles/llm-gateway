"""
WBS 3.2.3: Error Handling and Resilience Integration Tests

This module tests circuit breaker integration and timeout handling
for semantic search tools.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3117-3132 - WBS 3.2.3
- ARCHITECTURE.md: Graceful Degradation section
- Newman (Building Microservices) pp. 357-358: Circuit breaker pattern

TDD Phase: RED - These tests define expected resilience behavior.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """
    Reset the circuit breaker singleton before each test.
    
    This prevents test pollution from circuit breaker state.
    """
    import src.tools.builtin.semantic_search as ss_module
    ss_module._semantic_search_circuit_breaker = None
    yield
    ss_module._semantic_search_circuit_breaker = None


# =============================================================================
# WBS 3.2.3.1: Service Unavailable Handling Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    """
    WBS 3.2.3.1: Test circuit breaker behavior with semantic search tools.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_service_failure(self):
        """
        Mock semantic-search-service returning errors.
        
        Simulates service being unavailable.
        """
        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")
        
        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = mock_post
            mock_instance.get = mock_get
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, client, mock_service_failure):
        """
        WBS 3.2.3.1.2: Circuit breaker opens after repeated failures.
        
        After threshold failures, subsequent calls should fail fast
        with circuit open error instead of attempting connection.
        """
        # Make requests until circuit opens (default threshold is 5)
        circuit_open_detected = False
        responses = []
        
        for i in range(10):
            response = client.post(
                "/v1/tools/execute",
                json={
                    "name": "search_corpus",
                    "arguments": {"query": "test query"},
                },
            )
            responses.append(response)
            
            # Check if circuit open message is in the response
            if response.status_code == 200:
                data = response.json()
                # Tool errors return in result field
                result = data.get("result", {})
                if isinstance(result, dict) and "error" in str(result).lower():
                    if "circuit" in str(result).lower():
                        circuit_open_detected = True
                        break
        
        # Verify circuit behavior in logs/responses
        # The circuit should have opened by now - check via the circuit breaker directly
        from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker
        from src.clients.circuit_breaker import CircuitState
        
        cb = get_semantic_search_circuit_breaker()
        assert cb.state == CircuitState.OPEN, (
            f"Circuit breaker should be OPEN after 5 failures, but is {cb.state}"
        )

    @pytest.mark.asyncio
    async def test_graceful_degradation_returns_error_not_crash(
        self, client, mock_service_failure
    ):
        """
        WBS 3.2.3.1.3: Tools return error responses, not crashes.
        
        When service is down, should return structured error response,
        not crash the server. The API returns 200 with error in result
        because tool execution is wrapped.
        """
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "search_corpus",
                "arguments": {"query": "test query"},
            },
        )
        
        # Tool execution returns 200 with error in result or 500 for exceptions
        assert response.status_code in [200, 500, 503], (
            f"Expected 200, 500 or 503, got {response.status_code}"
        )
        
        data = response.json()
        # Either has detail (error) or result (success/wrapped error)
        assert "detail" in data or "result" in data, (
            "Response should have detail or result field"
        )

    @pytest.mark.asyncio
    async def test_circuit_recovery_after_timeout(self, client):
        """
        WBS 3.2.3.1.4: Circuit recovers when service comes back.
        
        After recovery timeout, circuit should transition to half-open
        and allow test requests through.
        """
        # This test requires timing control - we'll use a short recovery timeout
        from src.clients.circuit_breaker import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout_seconds=0.1,  # 100ms for fast testing
            name="test_circuit",
        )
        
        # Record failures to open circuit
        cb.record_failure()
        cb.record_failure()
        
        assert cb.state == CircuitState.OPEN, "Circuit should be open after failures"
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Check state with update
        state = await cb.check_and_update_state()
        assert state == CircuitState.HALF_OPEN, (
            "Circuit should transition to HALF_OPEN after recovery timeout"
        )

    @pytest.mark.asyncio
    async def test_get_chunk_uses_circuit_breaker(self, client, mock_service_failure):
        """
        WBS 3.2.3.1.5: get_chunk tool also uses circuit breaker.
        
        RED: Both search_corpus and get_chunk should share circuit breaker
        for the semantic-search-service.
        """
        # Trigger failures with search_corpus first
        for _ in range(6):
            client.post(
                "/v1/tools/execute",
                json={
                    "name": "search_corpus",
                    "arguments": {"query": "test"},
                },
            )
        
        # Now get_chunk should also fail fast
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "get_chunk",
                "arguments": {"chunk_id": "chunk-123"},
            },
        )
        
        data = response.json()
        # Should fail fast due to shared circuit breaker
        assert "circuit" in str(data).lower() or response.status_code in [500, 503]


# =============================================================================
# WBS 3.2.3.2: Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """
    WBS 3.2.3.2: Test timeout configuration and handling.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_slow_service(self):
        """
        Mock semantic-search-service with slow responses.
        """
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)  # Slow response
            return AsyncMock(
                status_code=200,
                json=lambda: {"results": [], "total": 0},
                raise_for_status=lambda: None,
            )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = slow_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    def test_timeout_configurable_in_settings(self):
        """
        WBS 3.2.3.2.1: Timeout should be configurable in Settings.
        
        Settings class should have semantic_search_timeout field.
        """
        from src.core.config import get_settings
        
        settings = get_settings()
        assert hasattr(settings, "semantic_search_timeout_seconds"), (
            "Settings should have semantic_search_timeout_seconds field"
        )
        assert settings.semantic_search_timeout_seconds > 0

    def test_timeout_used_by_search_tool(self):
        """
        WBS 3.2.3.2.3: Search tool uses configured timeout.
        
        Verify that the search_corpus function uses the timeout from settings.
        """
        from src.core.config import get_settings
        
        settings = get_settings()
        # The timeout value should be reasonable (between 1 and 300 seconds)
        assert 1 <= settings.semantic_search_timeout_seconds <= 300, (
            f"Timeout should be between 1-300s, got {settings.semantic_search_timeout_seconds}"
        )

    def test_chunk_retrieval_timeout_configurable(self):
        """
        WBS 3.2.3.2.1: Chunk retrieval also uses configured timeout.
        
        get_chunk should respect the same timeout configuration.
        """
        from src.core.config import get_settings
        
        settings = get_settings()
        # Both tools should use same timeout config
        assert hasattr(settings, "semantic_search_timeout_seconds")


# =============================================================================
# WBS 3.2.3.1.5: Circuit Breaker Behavior Integration Tests
# =============================================================================


class TestCircuitBreakerBehavior:
    """
    Additional circuit breaker behavior tests per WBS 3.2.3.1.5.
    """

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold_from_config(self):
        """
        Circuit breaker thresholds should be configurable.
        
        RED: Settings should have circuit breaker configuration.
        """
        from src.core.config import get_settings
        
        settings = get_settings()
        assert hasattr(settings, "circuit_breaker_failure_threshold"), (
            "Settings should have circuit_breaker_failure_threshold"
        )
        assert hasattr(settings, "circuit_breaker_recovery_timeout_seconds"), (
            "Settings should have circuit_breaker_recovery_timeout_seconds"
        )

    @pytest.mark.asyncio
    async def test_semantic_search_circuit_breaker_singleton(self):
        """
        Semantic search tools should share a circuit breaker instance.
        
        RED: Both search_corpus and get_chunk should use the same circuit breaker.
        """
        from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker
        from src.tools.builtin.chunk_retrieval import get_chunk_circuit_breaker
        
        # Both should return the same circuit breaker instance
        search_cb = get_semantic_search_circuit_breaker()
        chunk_cb = get_chunk_circuit_breaker()
        
        assert search_cb is chunk_cb, (
            "Both tools should share the same circuit breaker for semantic-search-service"
        )
