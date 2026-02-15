"""
Tests for Fallback Chain - WBS-CPA3

TDD RED Phase: Tests for FallbackChain class.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3, AC-CPA3.3
- Building Microservices (Newman): Cascading failure prevention
- Microservices Patterns (Richardson): Fallback patterns

This module tests:
- CPA3.3: Fallback chain with ordered backends
- CPA3.4: FallbackChain integrates with circuit breakers
- Integration with local cache as final fallback
"""

import asyncio
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_backend_config():
    """Configuration for mock backends."""
    return {
        "semantic-search": {"url": "http://localhost:8081", "timeout": 30.0},
        "code-orchestrator": {"url": "http://localhost:8083", "timeout": 30.0},
    }


@pytest.fixture
def fallback_chain():
    """Create a fallback chain with test backends."""
    from src.resilience.fallback_chain import FallbackChain, FallbackBackend

    backends = [
        FallbackBackend(
            name="semantic-search",
            url="http://localhost:8081",
            timeout=30.0,
        ),
        FallbackBackend(
            name="code-orchestrator",
            url="http://localhost:8083",
            timeout=30.0,
        ),
    ]

    return FallbackChain(
        name="search-chain",
        backends=backends,
        enable_local_cache=True,
    )


@pytest.fixture
def fallback_chain_no_cache():
    """Create a fallback chain without local cache."""
    from src.resilience.fallback_chain import FallbackChain, FallbackBackend

    backends = [
        FallbackBackend(
            name="semantic-search",
            url="http://localhost:8081",
            timeout=30.0,
        ),
    ]

    return FallbackChain(
        name="no-cache-chain",
        backends=backends,
        enable_local_cache=False,
    )


# =============================================================================
# FallbackChain Class Tests
# =============================================================================


class TestFallbackChainClass:
    """Tests for FallbackChain class structure."""

    def test_module_importable(self) -> None:
        """FallbackChain module is importable."""
        from src.resilience import fallback_chain
        assert fallback_chain is not None

    def test_class_exists(self) -> None:
        """FallbackChain class exists."""
        from src.resilience.fallback_chain import FallbackChain
        assert callable(FallbackChain)

    def test_backend_class_exists(self) -> None:
        """FallbackBackend class exists."""
        from src.resilience.fallback_chain import FallbackBackend
        assert callable(FallbackBackend)

    def test_error_class_exists(self) -> None:
        """FallbackChainError exception class exists with proper prefix (AP-5)."""
        from src.resilience.fallback_chain import FallbackChainError

        error = FallbackChainError("search-chain", "All backends failed")
        assert isinstance(error, Exception)
        assert "search-chain" in str(error)


class TestFallbackBackend:
    """Tests for FallbackBackend dataclass."""

    def test_backend_has_required_fields(self) -> None:
        """FallbackBackend has name, url, timeout fields."""
        from src.resilience.fallback_chain import FallbackBackend

        backend = FallbackBackend(
            name="test-backend",
            url="http://localhost:8000",
            timeout=30.0,
        )

        assert backend.name == "test-backend"
        assert backend.url == "http://localhost:8000"
        assert backend.timeout == 30.0

    def test_backend_has_circuit_breaker_config(self) -> None:
        """FallbackBackend can configure circuit breaker settings."""
        from src.resilience.fallback_chain import FallbackBackend

        backend = FallbackBackend(
            name="test-backend",
            url="http://localhost:8000",
            timeout=30.0,
            failure_threshold=5,
            reset_timeout_seconds=30.0,
        )

        assert backend.failure_threshold == 5
        assert backend.reset_timeout_seconds == 30.0


# =============================================================================
# FallbackChain Configuration Tests
# =============================================================================


class TestFallbackChainConfiguration:
    """Tests for FallbackChain configuration."""

    def test_chain_stores_backends_in_order(self, fallback_chain) -> None:
        """Backends are stored in execution order."""
        assert len(fallback_chain.backends) == 2
        assert fallback_chain.backends[0].name == "semantic-search"
        assert fallback_chain.backends[1].name == "code-orchestrator"

    def test_chain_has_name(self, fallback_chain) -> None:
        """Chain has a name for identification."""
        assert fallback_chain.name == "search-chain"

    def test_chain_local_cache_enabled_by_default(self, fallback_chain) -> None:
        """Local cache is enabled by default as final fallback."""
        assert fallback_chain.enable_local_cache is True

    def test_chain_local_cache_can_be_disabled(self, fallback_chain_no_cache) -> None:
        """Local cache can be disabled."""
        assert fallback_chain_no_cache.enable_local_cache is False

    def test_chain_creates_circuit_breaker_per_backend(self, fallback_chain) -> None:
        """Each backend gets its own circuit breaker."""
        assert len(fallback_chain._circuit_breakers) == 2
        assert "semantic-search" in fallback_chain._circuit_breakers
        assert "code-orchestrator" in fallback_chain._circuit_breakers


# =============================================================================
# AC-CPA3.3: Fallback Chain Execution Tests
# =============================================================================


class TestFallbackChainExecution:
    """Tests for fallback chain execution (AC-CPA3.3)."""

    @pytest.mark.asyncio
    async def test_execute_calls_first_backend(self, fallback_chain) -> None:
        """
        Execute calls the first backend in the chain.
        """
        with patch.object(
            fallback_chain,
            "_call_backend",
            new_callable=AsyncMock,
            return_value={"result": "success"},
        ) as mock_call:
            result = await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            assert result == {"result": "success"}
            # Should call first backend
            mock_call.assert_called_once()
            call_args = mock_call.call_args
            assert call_args[0][0].name == "semantic-search"

    @pytest.mark.asyncio
    async def test_execute_falls_back_on_failure(self, fallback_chain) -> None:
        """
        AC-CPA3.3: Falls back to next backend when first fails.
        """
        call_count = 0
        backends_called = []

        async def mock_call_backend(backend, operation, payload):
            nonlocal call_count
            call_count += 1
            backends_called.append(backend.name)

            if backend.name == "semantic-search":
                raise ConnectionError("Service unavailable")
            return {"result": "from-code-orchestrator"}

        with patch.object(
            fallback_chain,
            "_call_backend",
            side_effect=mock_call_backend,
        ):
            result = await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            assert result == {"result": "from-code-orchestrator"}
            assert backends_called == ["semantic-search", "code-orchestrator"]

    @pytest.mark.asyncio
    async def test_execute_falls_back_to_cache(self, fallback_chain) -> None:
        """
        AC-CPA3.3: Falls back to local cache when all backends fail.
        """
        # Pre-populate cache
        cache_key = fallback_chain._get_cache_key("search", {"query": "test"})
        fallback_chain._local_cache[cache_key] = {"cached": "result"}

        async def mock_call_backend(backend, operation, payload):
            raise ConnectionError("Service unavailable")

        with patch.object(
            fallback_chain,
            "_call_backend",
            side_effect=mock_call_backend,
        ):
            result = await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            assert result == {"cached": "result"}

    @pytest.mark.asyncio
    async def test_execute_raises_when_all_fail_and_no_cache(
        self, fallback_chain_no_cache
    ) -> None:
        """
        Raises FallbackChainError when all backends fail and cache disabled.
        """
        from src.resilience.fallback_chain import FallbackChainError

        async def mock_call_backend(backend, operation, payload):
            raise ConnectionError("Service unavailable")

        with patch.object(
            fallback_chain_no_cache,
            "_call_backend",
            side_effect=mock_call_backend,
        ):
            with pytest.raises(FallbackChainError) as exc_info:
                await fallback_chain_no_cache.execute(
                    operation="search",
                    payload={"query": "test"},
                )

            assert "no-cache-chain" in str(exc_info.value)
            assert "All backends failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_updates_cache_on_success(self, fallback_chain) -> None:
        """
        Updates local cache when backend succeeds.
        """
        with patch.object(
            fallback_chain,
            "_call_backend",
            new_callable=AsyncMock,
            return_value={"result": "fresh"},
        ):
            await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            cache_key = fallback_chain._get_cache_key("search", {"query": "test"})
            assert fallback_chain._local_cache.get(cache_key) == {"result": "fresh"}


# =============================================================================
# Circuit Breaker Integration Tests
# =============================================================================


class TestFallbackChainCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_skips_backend_with_open_circuit(self, fallback_chain) -> None:
        """
        Skips backends with open circuit breakers.
        """
        # Open the circuit for semantic-search
        cb = fallback_chain._circuit_breakers["semantic-search"]
        for _ in range(cb.failure_threshold):
            await cb.record_failure()

        backends_called = []

        async def mock_call_backend(backend, operation, payload):
            backends_called.append(backend.name)
            return {"result": f"from-{backend.name}"}

        with patch.object(
            fallback_chain,
            "_call_backend",
            side_effect=mock_call_backend,
        ):
            result = await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            # Should skip semantic-search (circuit open) and call code-orchestrator
            assert backends_called == ["code-orchestrator"]
            assert result == {"result": "from-code-orchestrator"}

    @pytest.mark.asyncio
    async def test_records_failure_on_backend_error(self, fallback_chain) -> None:
        """
        Records failure in circuit breaker when backend fails.
        """
        cb = fallback_chain._circuit_breakers["semantic-search"]
        initial_failures = cb.failure_count

        async def mock_call_backend(backend, operation, payload):
            if backend.name == "semantic-search":
                raise ConnectionError("Service unavailable")
            return {"result": "fallback"}

        with patch.object(
            fallback_chain,
            "_call_backend",
            side_effect=mock_call_backend,
        ):
            await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            assert cb.failure_count > initial_failures

    @pytest.mark.asyncio
    async def test_records_success_on_backend_success(self, fallback_chain) -> None:
        """
        Records success in circuit breaker when backend succeeds.
        """
        cb = fallback_chain._circuit_breakers["semantic-search"]

        # Add some failures first
        await cb.record_failure()
        assert cb.failure_count == 1

        with patch.object(
            fallback_chain,
            "_call_backend",
            new_callable=AsyncMock,
            return_value={"result": "success"},
        ):
            await fallback_chain.execute(
                operation="search",
                payload={"query": "test"},
            )

            # Failure count should be reset
            assert cb.failure_count == 0


# =============================================================================
# Metrics Tests
# =============================================================================


class TestFallbackChainMetrics:
    """Tests for fallback chain metrics."""

    @pytest.mark.asyncio
    async def test_records_fallback_attempt_metric(self, fallback_chain) -> None:
        """
        Records metric when attempting a backend.
        """
        with patch(
            "src.resilience.fallback_chain.record_fallback_attempt"
        ) as mock_metric:
            with patch.object(
                fallback_chain,
                "_call_backend",
                new_callable=AsyncMock,
                return_value={"result": "success"},
            ):
                await fallback_chain.execute(
                    operation="search",
                    payload={"query": "test"},
                )

                mock_metric.assert_called()

    @pytest.mark.asyncio
    async def test_records_fallback_success_metric(self, fallback_chain) -> None:
        """
        Records metric when backend succeeds.
        """
        with patch(
            "src.resilience.fallback_chain.record_fallback_success"
        ) as mock_metric:
            with patch.object(
                fallback_chain,
                "_call_backend",
                new_callable=AsyncMock,
                return_value={"result": "success"},
            ):
                await fallback_chain.execute(
                    operation="search",
                    payload={"query": "test"},
                )

                mock_metric.assert_called_with("search-chain", "semantic-search")


# =============================================================================
# Cache Key Generation Tests
# =============================================================================


class TestFallbackChainCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_is_deterministic(self, fallback_chain) -> None:
        """
        Same operation and payload produce same cache key.
        """
        key1 = fallback_chain._get_cache_key("search", {"query": "test"})
        key2 = fallback_chain._get_cache_key("search", {"query": "test"})
        assert key1 == key2

    def test_cache_key_differs_for_different_operations(self, fallback_chain) -> None:
        """
        Different operations produce different cache keys.
        """
        key1 = fallback_chain._get_cache_key("search", {"query": "test"})
        key2 = fallback_chain._get_cache_key("embed", {"query": "test"})
        assert key1 != key2

    def test_cache_key_differs_for_different_payloads(self, fallback_chain) -> None:
        """
        Different payloads produce different cache keys.
        """
        key1 = fallback_chain._get_cache_key("search", {"query": "test1"})
        key2 = fallback_chain._get_cache_key("search", {"query": "test2"})
        assert key1 != key2


# =============================================================================
# Factory Method Tests
# =============================================================================


class TestFallbackChainFactory:
    """Tests for FallbackChain factory methods."""

    def test_from_config_creates_chain(self) -> None:
        """
        from_config creates FallbackChain from configuration dict.
        """
        from src.resilience.fallback_chain import FallbackChain

        config = {
            "name": "search-fallback",
            "backends": [
                {"name": "semantic-search", "url": "http://localhost:8081"},
                {"name": "code-orchestrator", "url": "http://localhost:8083"},
            ],
            "enable_local_cache": True,
        }

        chain = FallbackChain.from_config(config)

        assert chain.name == "search-fallback"
        assert len(chain.backends) == 2
        assert chain.enable_local_cache is True

    def test_create_search_chain_factory(self) -> None:
        """
        create_search_chain creates pre-configured search fallback chain.
        """
        from src.resilience.fallback_chain import FallbackChain

        chain = FallbackChain.create_search_chain()

        assert chain.name == "search-fallback"
        assert any(b.name == "semantic-search" for b in chain.backends)
