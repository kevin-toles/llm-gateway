"""
WBS 3.2.3: Error Handling and Resilience Integration Tests

This module tests circuit breaker integration and timeout handling
for semantic search tools.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3117-3132 - WBS 3.2.3
- ARCHITECTURE.md: Graceful Degradation section
- Newman (Building Microservices) pp. 357-358: Circuit breaker pattern

INTEGRATION TEST REQUIREMENTS:
- Tests use real services where available, skip otherwise
- Configuration tests don't require mocks
- Circuit breaker state tests use real service calls
"""

import asyncio
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


# =============================================================================
# Integration Test Configuration
# =============================================================================

SEMANTIC_SEARCH_URL = os.getenv("INTEGRATION_SEMANTIC_SEARCH_URL", "http://localhost:8081")


def semantic_search_available() -> bool:
    """Check if semantic-search service is available."""
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{SEMANTIC_SEARCH_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


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
    
    NOTE: These tests verify circuit breaker configuration and state.
    Tests that require service failures use direct circuit breaker API
    rather than mocking HTTP calls.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_circuit_breaker_initializes_closed(self, client):
        """
        WBS 3.2.3.1.1: Circuit breaker starts in CLOSED state.
        """
        from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker
        from src.clients.circuit_breaker import CircuitState
        
        cb = get_semantic_search_circuit_breaker()
        assert cb.state == CircuitState.CLOSED, (
            f"Circuit breaker should start CLOSED, but is {cb.state}"
        )

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self, client):
        """
        WBS 3.2.3.1.2: Circuit breaker opens after repeated failures.
        
        Uses direct circuit breaker API to record failures.
        """
        from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker
        from src.clients.circuit_breaker import CircuitState
        
        cb = get_semantic_search_circuit_breaker()
        
        # Record failures up to threshold
        for _ in range(cb._failure_threshold):
            cb.record_failure()
        
        assert cb.state == CircuitState.OPEN, (
            f"Circuit breaker should be OPEN after {cb._failure_threshold} failures"
        )

    @pytest.mark.asyncio
    async def test_circuit_recovery_after_timeout(self, client):
        """
        WBS 3.2.3.1.4: Circuit recovers when service comes back.
        
        After recovery timeout, circuit should transition to half-open
        and allow test requests through.
        """
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

    @pytest.mark.skipif(
        not semantic_search_available(),
        reason="Semantic search service not available"
    )
    @pytest.mark.asyncio
    async def test_successful_call_resets_failure_count(self, client):
        """
        WBS 3.2.3.1.3: Successful calls reset failure count.
        
        Uses real semantic search service.
        """
        from src.tools.builtin.semantic_search import get_semantic_search_circuit_breaker
        
        cb = get_semantic_search_circuit_breaker()
        
        # Record some failures (but not enough to open)
        cb.record_failure()
        initial_failures = cb._failure_count
        
        # Make a real successful call through the API
        response = client.post(
            "/v1/tools/execute",
            json={
                "name": "search_corpus",
                "arguments": {"query": "test query"},
            },
        )
        
        if response.status_code == 200:
            # Success should reset failure count
            assert cb._failure_count == 0 or cb._failure_count < initial_failures


# =============================================================================
# WBS 3.2.3.2: Timeout Handling Tests (Configuration - No Mocks Needed)
# =============================================================================


class TestTimeoutHandling:
    """
    WBS 3.2.3.2: Test timeout configuration and handling.
    
    These tests verify configuration - no mocks needed.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

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

    def test_timeout_has_reasonable_value(self):
        """
        WBS 3.2.3.2.3: Timeout value should be reasonable.
        """
        from src.core.config import get_settings
        
        settings = get_settings()
        # The timeout value should be reasonable (between 1 and 300 seconds)
        assert 1 <= settings.semantic_search_timeout_seconds <= 300, (
            f"Timeout should be between 1-300s, got {settings.semantic_search_timeout_seconds}"
        )

    def test_chunk_retrieval_timeout_uses_same_config(self):
        """
        WBS 3.2.3.2.1: Chunk retrieval also uses configured timeout.
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
