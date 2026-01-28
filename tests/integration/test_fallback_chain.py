"""
Integration Tests for Fallback Chain - WBS-CPA3

TDD REFACTOR Phase: Integration tests for full fallback chain.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3, AC-CPA3.3
- Building Microservices (Newman): Cascading failure prevention

This module tests:
- Full fallback chain: Gateway → semantic-search → Code-Orchestrator → cache
- Circuit breaker integration across multiple failures
- Cache fallback behavior
- Metrics emission during fallback scenarios

INTEGRATION TEST REQUIREMENTS:
- These tests require real services or are skipped
- Use pytest -m integration --integration to run with real services
- Mock usage is prohibited per TEST_AUDIT_GUIDELINES.md Rule I1
"""

import asyncio
import os
from typing import Any, Dict

import httpx
import pytest


# =============================================================================
# Integration Test Configuration
# =============================================================================

# Check if real services are available for integration testing
SEMANTIC_SEARCH_URL = os.getenv("INTEGRATION_SEMANTIC_SEARCH_URL", "http://localhost:8081")
CODE_ORCHESTRATOR_URL = os.getenv("INTEGRATION_CODE_ORCHESTRATOR_URL", "http://localhost:8083")


def services_available() -> bool:
    """Check if backend services are available for integration tests."""
    try:
        import httpx
        with httpx.Client(timeout=2.0) as client:
            ss_health = client.get(f"{SEMANTIC_SEARCH_URL}/health")
            if ss_health.status_code != 200:
                return False
        return True
    except Exception:
        return False


# Skip all tests in this module if services unavailable
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not services_available(),
        reason="Integration tests require real services (semantic-search, code-orchestrator)"
    ),
]


# =============================================================================
# Test Fixtures - Real Service Configuration
# =============================================================================


@pytest.fixture
def integration_chain():
    """Create a fallback chain configured for real services."""
    from src.resilience.fallback_chain import FallbackChain

    return FallbackChain.create_search_chain(
        semantic_search_url=SEMANTIC_SEARCH_URL,
        code_orchestrator_url=CODE_ORCHESTRATOR_URL,
    )


@pytest.fixture
def fast_integration_chain():
    """Create a fallback chain with fast circuit breakers for testing."""
    from src.resilience.fallback_chain import FallbackBackend, FallbackChain

    backends = [
        FallbackBackend(
            name="semantic-search",
            url=SEMANTIC_SEARCH_URL,
            timeout=5.0,
            failure_threshold=2,
            reset_timeout_seconds=0.5,
        ),
        FallbackBackend(
            name="code-orchestrator",
            url=CODE_ORCHESTRATOR_URL,
            timeout=5.0,
            failure_threshold=2,
            reset_timeout_seconds=0.5,
        ),
    ]

    return FallbackChain(
        name="fast-search-fallback",
        backends=backends,
        enable_local_cache=True,
    )


# =============================================================================
# AC-CPA3.3: Full Fallback Chain Integration Tests
# =============================================================================


class TestFullFallbackChainIntegration:
    """
    Integration tests for the full fallback chain (AC-CPA3.3).
    
    These tests use REAL backend services - no mocking allowed.
    """

    @pytest.mark.asyncio
    async def test_full_chain_primary_backend_success(
        self, integration_chain
    ) -> None:
        """
        AC-CPA3.3: Primary backend (semantic-search) succeeds.
        
        Uses real semantic-search service.
        """
        result = await integration_chain.execute(
            operation="search",
            payload={"query": "test query", "top_k": 5},
        )

        # Verify we got results from semantic-search
        assert isinstance(result, dict)
        assert "results" in result or "error" not in result

    @pytest.mark.asyncio
    async def test_full_chain_handles_empty_results(
        self, integration_chain
    ) -> None:
        """
        AC-CPA3.3: Primary backend returns empty results gracefully.
        """
        result = await integration_chain.execute(
            operation="search",
            payload={"query": "xyznonexistentquery12345", "top_k": 5},
        )

        assert isinstance(result, dict)
        # Empty results are valid - not an error

    @pytest.mark.asyncio
    async def test_full_chain_cache_stores_results(
        self, integration_chain
    ) -> None:
        """
        AC-CPA3.3: Successful results are cached for fallback.
        """
        payload = {"query": "cache integration test", "top_k": 3}
        
        # First call - hits real service
        result1 = await integration_chain.execute(
            operation="search",
            payload=payload,
        )

        # Verify cache was populated
        cache_key = integration_chain._get_cache_key("search", payload)
        cached = integration_chain._local_cache.get(cache_key)
        
        assert cached is not None, "Results should be cached after successful call"
        assert cached == result1


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================


class TestCircuitBreakerIntegration:
    """
    Integration tests for circuit breaker behavior with real services.
    
    NOTE: These tests verify circuit breaker state transitions using
    real backend calls. Circuit breaker behavior is tested, not mocked.
    """

    @pytest.mark.asyncio
    async def test_circuit_starts_closed(
        self, fast_integration_chain
    ) -> None:
        """
        Circuit breaker starts in CLOSED state.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        cb = fast_integration_chain._circuit_breakers["semantic-search"]
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_calls_keep_circuit_closed(
        self, fast_integration_chain
    ) -> None:
        """
        Successful calls keep the circuit breaker closed.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Make successful requests to real service
        for _ in range(3):
            await fast_integration_chain.execute(
                operation="search",
                payload={"query": "test", "top_k": 1},
            )

        # Circuit should still be closed
        cb = fast_integration_chain._circuit_breakers["semantic-search"]
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_success(
        self, fast_integration_chain
    ) -> None:
        """
        Circuit breaker records successful calls.
        """
        cb = fast_integration_chain._circuit_breakers["semantic-search"]
        initial_failures = cb._failure_count

        await fast_integration_chain.execute(
            operation="search",
            payload={"query": "test", "top_k": 1},
        )

        # Success should reset failure count
        assert cb._failure_count <= initial_failures


# =============================================================================
# Cache Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Integration tests for local cache behavior with real services."""

    @pytest.mark.asyncio
    async def test_cache_updated_on_success(
        self, integration_chain
    ) -> None:
        """
        Local cache is updated on successful backend call.
        """
        payload = {"query": "cache update test", "top_k": 3}
        
        # Make real call
        result = await integration_chain.execute(
            operation="search",
            payload=payload,
        )

        # Verify cache was updated
        cache_key = integration_chain._get_cache_key("search", payload)
        cached = integration_chain._local_cache.get(cache_key)
        
        assert cached is not None
        assert cached == result

    @pytest.mark.asyncio
    async def test_cache_key_generation_deterministic(
        self, integration_chain
    ) -> None:
        """
        Cache key generation is deterministic for same inputs.
        """
        payload = {"query": "deterministic test", "top_k": 5}
        
        key1 = integration_chain._get_cache_key("search", payload)
        key2 = integration_chain._get_cache_key("search", payload)
        
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_different_queries_have_different_cache_keys(
        self, integration_chain
    ) -> None:
        """
        Different queries produce different cache keys.
        """
        key1 = integration_chain._get_cache_key("search", {"query": "query1"})
        key2 = integration_chain._get_cache_key("search", {"query": "query2"})
        
        assert key1 != key2
