"""
Tests for Circuit Breaker State Machine - WBS-CPA3

TDD RED Phase: Tests for CircuitBreakerStateMachine class.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3, AC-CPA3.1, AC-CPA3.2, AC-CPA3.4
- Building Reactive Microservices in Java (Escoffier) Ch.6: Circuit breaker pattern
- Release It! (Nygard): Stability patterns

This module tests:
- CPA3.1: CLOSED → OPEN → HALF_OPEN state transitions
- CPA3.2: Configurable failure threshold from environment
- CPA3.4: asyncio.Lock() for thread-safe state transitions
- CPA3.5: Prometheus metrics on state transitions
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def state_machine():
    """Create a state machine with test-friendly settings."""
    from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

    return CircuitBreakerStateMachine(
        name="test-service",
        failure_threshold=3,
        reset_timeout_seconds=1.0,
    )


@pytest.fixture
def fast_state_machine():
    """Create a state machine with very short reset timeout for testing."""
    from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

    return CircuitBreakerStateMachine(
        name="fast-test",
        failure_threshold=2,
        reset_timeout_seconds=0.1,
    )


# =============================================================================
# CPA3.1: State Machine Tests
# =============================================================================


class TestCircuitBreakerStateMachineClass:
    """Tests for CircuitBreakerStateMachine class structure."""

    def test_module_importable(self) -> None:
        """CircuitBreakerStateMachine module is importable."""
        from src.resilience import circuit_breaker_state_machine
        assert circuit_breaker_state_machine is not None

    def test_class_exists(self) -> None:
        """CircuitBreakerStateMachine class exists."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine
        assert callable(CircuitBreakerStateMachine)

    def test_state_enum_exists(self) -> None:
        """CircuitBreakerState enum exists with CLOSED, OPEN, HALF_OPEN."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        assert CircuitBreakerState.CLOSED is not None
        assert CircuitBreakerState.OPEN is not None
        assert CircuitBreakerState.HALF_OPEN is not None

    def test_error_class_exists(self) -> None:
        """CircuitBreakerError exception class exists with proper prefix (AP-5)."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerError

        error = CircuitBreakerError("test-circuit", "Circuit is open")
        assert isinstance(error, Exception)
        assert "test-circuit" in str(error)


class TestCircuitBreakerStateTransitions:
    """Tests for state machine transitions (AC-CPA3.1)."""

    def test_initial_state_is_closed(self, state_machine) -> None:
        """Initial state is CLOSED."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        assert state_machine.state == CircuitBreakerState.CLOSED

    def test_failure_count_starts_at_zero(self, state_machine) -> None:
        """Failure count starts at zero."""
        assert state_machine.failure_count == 0

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(self, state_machine) -> None:
        """Recording a failure increments the failure count."""
        await state_machine.record_failure()
        assert state_machine.failure_count == 1

    @pytest.mark.asyncio
    async def test_record_success_resets_count(self, state_machine) -> None:
        """Recording a success resets failure count to zero."""
        await state_machine.record_failure()
        await state_machine.record_failure()
        await state_machine.record_success()
        assert state_machine.failure_count == 0

    @pytest.mark.asyncio
    async def test_transitions_closed_to_open_after_threshold(
        self, state_machine
    ) -> None:
        """
        CLOSED → OPEN: Circuit opens after threshold failures exceeded.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Record failures up to threshold
        for _ in range(state_machine.failure_threshold):
            await state_machine.record_failure()

        assert state_machine.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_stays_closed_below_threshold(self, state_machine) -> None:
        """Circuit stays CLOSED when below threshold."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Record one less than threshold
        for _ in range(state_machine.failure_threshold - 1):
            await state_machine.record_failure()

        assert state_machine.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_transitions_open_to_half_open_after_timeout(
        self, fast_state_machine
    ) -> None:
        """
        OPEN → HALF_OPEN: Circuit transitions after reset timeout.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Open the circuit
        for _ in range(fast_state_machine.failure_threshold):
            await fast_state_machine.record_failure()

        assert fast_state_machine.state == CircuitBreakerState.OPEN

        # Wait for reset timeout
        await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)

        # Should transition to HALF_OPEN
        current_state = await fast_state_machine.get_state()
        assert current_state == CircuitBreakerState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_transitions_half_open_to_closed_on_success(
        self, fast_state_machine
    ) -> None:
        """
        HALF_OPEN → CLOSED: Success during half-open closes the circuit.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Open the circuit
        for _ in range(fast_state_machine.failure_threshold):
            await fast_state_machine.record_failure()

        # Wait for half-open
        await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)
        await fast_state_machine.get_state()  # Trigger transition

        # Record success
        await fast_state_machine.record_success()
        assert fast_state_machine.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_transitions_half_open_to_open_on_failure(
        self, fast_state_machine
    ) -> None:
        """
        HALF_OPEN → OPEN: Failure during half-open reopens the circuit.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Open the circuit
        for _ in range(fast_state_machine.failure_threshold):
            await fast_state_machine.record_failure()

        # Wait for half-open
        await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)
        await fast_state_machine.get_state()  # Trigger transition

        # Record failure
        await fast_state_machine.record_failure()
        assert fast_state_machine.state == CircuitBreakerState.OPEN


# =============================================================================
# CPA3.2: Configuration from Environment Tests
# =============================================================================


class TestCircuitBreakerConfiguration:
    """Tests for configuration from environment (AC-CPA3.2)."""

    def test_failure_threshold_configurable(self) -> None:
        """Failure threshold is configurable via constructor."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        sm = CircuitBreakerStateMachine(name="test", failure_threshold=10)
        assert sm.failure_threshold == 10

    def test_reset_timeout_configurable(self) -> None:
        """Reset timeout is configurable via constructor."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        sm = CircuitBreakerStateMachine(name="test", reset_timeout_seconds=60.0)
        assert sm.reset_timeout_seconds == 60.0

    def test_default_failure_threshold(self) -> None:
        """Default failure threshold is reasonable (5)."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        sm = CircuitBreakerStateMachine(name="test")
        assert sm.failure_threshold == 5

    def test_default_reset_timeout(self) -> None:
        """Default reset timeout is reasonable (30 seconds)."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        sm = CircuitBreakerStateMachine(name="test")
        assert sm.reset_timeout_seconds == 30.0

    def test_failure_threshold_from_env(self) -> None:
        """
        AC-CPA3.2: Failure threshold can be configured from environment.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        with patch.dict(
            "os.environ",
            {"LLM_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD": "7"},
        ):
            sm = CircuitBreakerStateMachine.from_env(name="test")
            assert sm.failure_threshold == 7

    def test_reset_timeout_from_env(self) -> None:
        """Reset timeout can be configured from environment."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine

        with patch.dict(
            "os.environ",
            {"LLM_GATEWAY_CIRCUIT_BREAKER_RESET_TIMEOUT": "45"},
        ):
            sm = CircuitBreakerStateMachine.from_env(name="test")
            assert sm.reset_timeout_seconds == 45.0


# =============================================================================
# CPA3.4: Thread-Safe State Transitions Tests
# =============================================================================


class TestCircuitBreakerThreadSafety:
    """Tests for thread-safe state transitions (AC-CPA3.4)."""

    def test_has_asyncio_lock(self, state_machine) -> None:
        """State machine has asyncio.Lock for thread safety (AP-6)."""
        assert hasattr(state_machine, "_lock")
        assert isinstance(state_machine._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_concurrent_failures_are_safe(self, state_machine) -> None:
        """
        AC-CPA3.4: Concurrent failure recordings are thread-safe.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Record many failures concurrently
        tasks = [state_machine.record_failure() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Should be in OPEN state (threshold exceeded)
        assert state_machine.state == CircuitBreakerState.OPEN
        # Failure count should be consistent
        assert state_machine.failure_count >= state_machine.failure_threshold

    @pytest.mark.asyncio
    async def test_concurrent_state_checks_are_safe(self, fast_state_machine) -> None:
        """
        AC-CPA3.4: Concurrent state checks during transition are thread-safe.
        """
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerState

        # Open the circuit
        for _ in range(fast_state_machine.failure_threshold):
            await fast_state_machine.record_failure()

        # Wait for timeout
        await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)

        # Check state concurrently - all should see HALF_OPEN
        tasks = [fast_state_machine.get_state() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should see HALF_OPEN
        assert all(s == CircuitBreakerState.HALF_OPEN for s in results)


# =============================================================================
# CPA3.5: Metrics Tests
# =============================================================================


class TestCircuitBreakerMetrics:
    """Tests for Prometheus metrics on state transitions (AC-CPA3.5)."""

    @pytest.mark.asyncio
    async def test_emits_metric_on_transition_to_open(self, state_machine) -> None:
        """
        AC-CPA3.5: Metric emitted when transitioning to OPEN.
        """
        with patch(
            "src.resilience.circuit_breaker_state_machine.record_circuit_state_transition"
        ) as mock_metric:
            # Trigger threshold failures
            for _ in range(state_machine.failure_threshold):
                await state_machine.record_failure()

            # Should have recorded transition to OPEN
            mock_metric.assert_called()
            calls = [c for c in mock_metric.call_args_list if c.args[1] == "open"]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_emits_metric_on_transition_to_half_open(
        self, fast_state_machine
    ) -> None:
        """
        AC-CPA3.5: Metric emitted when transitioning to HALF_OPEN.
        """
        with patch(
            "src.resilience.circuit_breaker_state_machine.record_circuit_state_transition"
        ) as mock_metric:
            # Open the circuit
            for _ in range(fast_state_machine.failure_threshold):
                await fast_state_machine.record_failure()

            # Wait for timeout
            await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)

            # Trigger state check
            await fast_state_machine.get_state()

            # Should have recorded transition to HALF_OPEN
            calls = [c for c in mock_metric.call_args_list if c.args[1] == "half_open"]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_emits_metric_on_transition_to_closed(
        self, fast_state_machine
    ) -> None:
        """
        AC-CPA3.5: Metric emitted when transitioning to CLOSED.
        """
        with patch(
            "src.resilience.circuit_breaker_state_machine.record_circuit_state_transition"
        ) as mock_metric:
            # Open and wait for half-open
            for _ in range(fast_state_machine.failure_threshold):
                await fast_state_machine.record_failure()

            await asyncio.sleep(fast_state_machine.reset_timeout_seconds + 0.05)
            await fast_state_machine.get_state()

            # Record success to close
            await fast_state_machine.record_success()

            # Should have recorded transition to CLOSED
            calls = [c for c in mock_metric.call_args_list if c.args[1] == "closed"]
            assert len(calls) >= 1


# =============================================================================
# Execute Method Tests
# =============================================================================


class TestCircuitBreakerExecute:
    """Tests for execute method that wraps calls."""

    @pytest.mark.asyncio
    async def test_execute_passes_through_when_closed(self, state_machine) -> None:
        """Execute passes through when circuit is closed."""
        mock_func = AsyncMock(return_value="success")

        result = await state_machine.execute(mock_func)

        assert result == "success"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_raises_when_open(self, state_machine) -> None:
        """Execute raises CircuitBreakerError when circuit is open."""
        from src.resilience.circuit_breaker_state_machine import CircuitBreakerError

        # Open the circuit
        for _ in range(state_machine.failure_threshold):
            await state_machine.record_failure()

        mock_func = AsyncMock()

        with pytest.raises(CircuitBreakerError):
            await state_machine.execute(mock_func)

        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_records_success(self, state_machine) -> None:
        """Execute records success when function succeeds."""
        mock_func = AsyncMock(return_value="success")

        await state_machine.execute(mock_func)

        assert state_machine.failure_count == 0

    @pytest.mark.asyncio
    async def test_execute_records_failure(self, state_machine) -> None:
        """Execute records failure when function raises."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))

        with pytest.raises(ValueError):
            await state_machine.execute(mock_func)

        assert state_machine.failure_count == 1

    @pytest.mark.asyncio
    async def test_execute_passes_args_and_kwargs(self, state_machine) -> None:
        """Execute passes arguments to wrapped function."""
        mock_func = AsyncMock(return_value="result")

        await state_machine.execute(mock_func, "arg1", "arg2", kwarg1="value1")

        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")
