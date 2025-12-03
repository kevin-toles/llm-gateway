"""
Tests for Circuit Breaker - WBS 2.7.2.1

TDD RED Phase: Tests for CircuitBreaker class.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 2817-2826 - Circuit Breaker WBS
- Newman (Building Microservices): Circuit breaker pattern
- Nygard (Release It!): Stability patterns

WBS Items Covered:
- 2.7.2.1.1: Implement circuit breaker pattern
- 2.7.2.1.2: Configure failure threshold
- 2.7.2.1.3: Configure recovery timeout
- 2.7.2.1.4: Track failure rate per service
- 2.7.2.1.5: Open circuit when threshold exceeded
- 2.7.2.1.6: Half-open for recovery testing
- 2.7.2.1.7: RED test: circuit opens after failures
- 2.7.2.1.8: RED test: circuit recovers after timeout
- 2.7.2.1.9: GREEN: implement and pass tests
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker with test-friendly settings."""
    from src.clients.circuit_breaker import CircuitBreaker

    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout_seconds=1.0,
        name="test-service",
    )


@pytest.fixture
def fast_circuit_breaker():
    """Create a circuit breaker with very short recovery for testing."""
    from src.clients.circuit_breaker import CircuitBreaker

    return CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_seconds=0.1,
        name="fast-test",
    )


# =============================================================================
# WBS 2.7.2.1.1: Package and Class Tests
# =============================================================================


class TestCircuitBreakerClass:
    """Tests for CircuitBreaker class structure."""

    def test_circuit_breaker_module_importable(self) -> None:
        """
        WBS 2.7.2.1.1: circuit_breaker module is importable.
        """
        from src.clients import circuit_breaker
        assert circuit_breaker is not None

    def test_circuit_breaker_class_exists(self) -> None:
        """
        WBS 2.7.2.1.1: CircuitBreaker class exists.
        """
        from src.clients.circuit_breaker import CircuitBreaker
        assert CircuitBreaker is not None

    def test_circuit_state_enum_exists(self) -> None:
        """
        CircuitState enum exists with CLOSED, OPEN, HALF_OPEN.
        """
        from src.clients.circuit_breaker import CircuitState

        assert CircuitState.CLOSED is not None
        assert CircuitState.OPEN is not None
        assert CircuitState.HALF_OPEN is not None


# =============================================================================
# WBS 2.7.2.1.2-3: Configuration Tests
# =============================================================================


class TestCircuitBreakerConfiguration:
    """Tests for circuit breaker configuration."""

    def test_failure_threshold_configurable(self) -> None:
        """
        WBS 2.7.2.1.2: Failure threshold is configurable.
        """
        from src.clients.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5)
        assert cb.failure_threshold == 5

    def test_recovery_timeout_configurable(self) -> None:
        """
        WBS 2.7.2.1.3: Recovery timeout is configurable.
        """
        from src.clients.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(recovery_timeout_seconds=30.0)
        assert cb.recovery_timeout_seconds == 30.0

    def test_default_failure_threshold(self) -> None:
        """
        Default failure threshold is reasonable.
        """
        from src.clients.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.failure_threshold >= 3

    def test_default_recovery_timeout(self) -> None:
        """
        Default recovery timeout is reasonable.
        """
        from src.clients.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.recovery_timeout_seconds >= 10.0

    def test_circuit_breaker_accepts_name(self) -> None:
        """
        Circuit breaker can be named for identification.
        """
        from src.clients.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="semantic-search")
        assert cb.name == "semantic-search"


# =============================================================================
# WBS 2.7.2.1.4: Failure Tracking Tests
# =============================================================================


class TestCircuitBreakerFailureTracking:
    """Tests for failure rate tracking."""

    def test_initial_state_is_closed(self, circuit_breaker) -> None:
        """
        WBS 2.7.2.1.4: Initial state is CLOSED.
        """
        from src.clients.circuit_breaker import CircuitState

        assert circuit_breaker.state == CircuitState.CLOSED

    def test_failure_count_starts_at_zero(self, circuit_breaker) -> None:
        """
        Failure count starts at zero.
        """
        assert circuit_breaker.failure_count == 0

    def test_record_failure_increments_count(self, circuit_breaker) -> None:
        """
        Recording a failure increments the count.
        """
        circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 1

    def test_record_success_resets_count(self, circuit_breaker) -> None:
        """
        Recording a success resets failure count.
        """
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()
        assert circuit_breaker.failure_count == 0

    def test_failure_count_tracks_consecutive_failures(self, circuit_breaker) -> None:
        """
        Failure count tracks consecutive failures.
        """
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.failure_count == 2


# =============================================================================
# WBS 2.7.2.1.5: Circuit Opens Tests
# =============================================================================


class TestCircuitBreakerOpens:
    """Tests for circuit opening on failures."""

    def test_circuit_opens_after_threshold_failures(self, circuit_breaker) -> None:
        """
        WBS 2.7.2.1.5 & 2.7.2.1.7: Circuit opens after threshold exceeded.
        """
        from src.clients.circuit_breaker import CircuitState

        # Record failures up to threshold
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

    def test_circuit_stays_closed_below_threshold(self, circuit_breaker) -> None:
        """
        Circuit stays closed when below threshold.
        """
        from src.clients.circuit_breaker import CircuitState

        # Record one less than threshold
        for _ in range(circuit_breaker.failure_threshold - 1):
            circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.CLOSED

    def test_is_open_returns_true_when_open(self, circuit_breaker) -> None:
        """
        is_open property returns True when circuit is open.
        """
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure()

        assert circuit_breaker.is_open is True

    def test_is_open_returns_false_when_closed(self, circuit_breaker) -> None:
        """
        is_open property returns False when circuit is closed.
        """
        assert circuit_breaker.is_open is False


# =============================================================================
# WBS 2.7.2.1.6: Half-Open Recovery Tests
# =============================================================================


class TestCircuitBreakerHalfOpen:
    """Tests for half-open recovery state."""

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(
        self, fast_circuit_breaker
    ) -> None:
        """
        WBS 2.7.2.1.6 & 2.7.2.1.8: Circuit goes to HALF_OPEN after recovery timeout.
        """
        from src.clients.circuit_breaker import CircuitState

        # Open the circuit
        for _ in range(fast_circuit_breaker.failure_threshold):
            fast_circuit_breaker.record_failure()

        assert fast_circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(fast_circuit_breaker.recovery_timeout_seconds + 0.05)

        # Check state - should be HALF_OPEN
        assert fast_circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes_circuit(
        self, fast_circuit_breaker
    ) -> None:
        """
        Success during half-open transitions to CLOSED.
        """
        from src.clients.circuit_breaker import CircuitState

        # Open the circuit
        for _ in range(fast_circuit_breaker.failure_threshold):
            fast_circuit_breaker.record_failure()

        # Wait for half-open
        await asyncio.sleep(fast_circuit_breaker.recovery_timeout_seconds + 0.05)
        assert fast_circuit_breaker.state == CircuitState.HALF_OPEN

        # Record success
        fast_circuit_breaker.record_success()
        assert fast_circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(
        self, fast_circuit_breaker
    ) -> None:
        """
        Failure during half-open transitions back to OPEN.
        """
        from src.clients.circuit_breaker import CircuitState

        # Open the circuit
        for _ in range(fast_circuit_breaker.failure_threshold):
            fast_circuit_breaker.record_failure()

        # Wait for half-open
        await asyncio.sleep(fast_circuit_breaker.recovery_timeout_seconds + 0.05)
        assert fast_circuit_breaker.state == CircuitState.HALF_OPEN

        # Record failure
        fast_circuit_breaker.record_failure()
        assert fast_circuit_breaker.state == CircuitState.OPEN


# =============================================================================
# WBS 2.7.2.1.7-8: Context Manager / Decorator Tests
# =============================================================================


class TestCircuitBreakerUsage:
    """Tests for using circuit breaker with async functions."""

    @pytest.mark.asyncio
    async def test_call_succeeds_when_closed(self, circuit_breaker) -> None:
        """
        Calls succeed when circuit is closed.
        """
        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_raises_when_open(self, circuit_breaker) -> None:
        """
        Calls raise CircuitOpenError when circuit is open.
        """
        from src.clients.circuit_breaker import CircuitOpenError

        # Open the circuit
        for _ in range(circuit_breaker.failure_threshold):
            circuit_breaker.record_failure()

        async def success_func():
            return "success"

        with pytest.raises(CircuitOpenError):
            await circuit_breaker.call(success_func)

    @pytest.mark.asyncio
    async def test_call_records_failure_on_exception(self, circuit_breaker) -> None:
        """
        Exceptions during call are recorded as failures.
        """
        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await circuit_breaker.call(failing_func)

        assert circuit_breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_call_records_success_on_completion(self, circuit_breaker) -> None:
        """
        Successful calls are recorded.
        """
        # Add some failures first
        circuit_breaker.record_failure()

        async def success_func():
            return "success"

        await circuit_breaker.call(success_func)

        # Failure count should be reset
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_passes_arguments(self, circuit_breaker) -> None:
        """
        Arguments are passed through to the wrapped function.
        """
        async def echo_func(value: str, multiplier: int = 1):
            return value * multiplier

        result = await circuit_breaker.call(echo_func, "test", multiplier=2)
        assert result == "testtest"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestCircuitBreakerErrors:
    """Tests for circuit breaker error types."""

    def test_circuit_open_error_exists(self) -> None:
        """
        CircuitOpenError is defined.
        """
        from src.clients.circuit_breaker import CircuitOpenError
        assert CircuitOpenError is not None

    def test_circuit_open_error_is_exception(self) -> None:
        """
        CircuitOpenError is an Exception.
        """
        from src.clients.circuit_breaker import CircuitOpenError
        assert issubclass(CircuitOpenError, Exception)

    def test_circuit_open_error_includes_circuit_name(self, circuit_breaker) -> None:
        """
        CircuitOpenError includes circuit name.
        """
        from src.clients.circuit_breaker import CircuitOpenError

        error = CircuitOpenError(circuit_breaker.name)
        assert circuit_breaker.name in str(error)


# =============================================================================
# Import Tests
# =============================================================================


class TestCircuitBreakerImportable:
    """Tests for exports."""

    def test_circuit_breaker_importable_from_clients(self) -> None:
        """
        CircuitBreaker importable from src.clients.
        """
        from src.clients import CircuitBreaker
        assert CircuitBreaker is not None

    def test_circuit_state_importable(self) -> None:
        """
        CircuitState importable from src.clients.
        """
        from src.clients import CircuitState
        assert CircuitState is not None

    def test_circuit_open_error_importable(self) -> None:
        """
        CircuitOpenError importable from src.clients.
        """
        from src.clients import CircuitOpenError
        assert CircuitOpenError is not None
