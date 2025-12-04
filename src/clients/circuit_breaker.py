"""
Circuit Breaker - WBS 2.7.2.1

This module implements the circuit breaker pattern for resilience.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 2817-2826 - Circuit Breaker WBS
- Newman (Building Microservices): Circuit breaker pattern for preventing cascading failures
- Nygard (Release It!): Stability patterns

Pattern: Circuit Breaker
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests fail fast
- HALF_OPEN: Testing recovery, limited requests pass through

Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults
"""

import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


# =============================================================================
# Circuit State Enum
# =============================================================================


class CircuitState(Enum):
    """
    State of a circuit breaker.

    States:
        CLOSED: Normal operation, all requests pass through
        OPEN: Circuit is tripped, requests fail immediately
        HALF_OPEN: Recovery testing, limited requests pass through
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# =============================================================================
# Custom Exceptions
# =============================================================================


class CircuitOpenError(Exception):
    """
    Exception raised when a circuit breaker is open.

    This indicates that the downstream service is considered unhealthy
    and requests should fail fast rather than waiting for timeout.
    """

    def __init__(self, circuit_name: str) -> None:
        self.circuit_name = circuit_name
        super().__init__(f"Circuit '{circuit_name}' is open - failing fast")


# =============================================================================
# WBS 2.7.2.1.1: CircuitBreaker Class
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    WBS 2.7.2.1.1: Implement circuit breaker pattern.

    The circuit breaker monitors failures to downstream services.
    When failures exceed a threshold, it "trips" and fails fast,
    preventing resource exhaustion while the service recovers.

    States:
        CLOSED: Normal operation, requests pass through
        OPEN: Failures exceeded threshold, requests fail fast
        HALF_OPEN: After recovery timeout, allow test request

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=30)
        >>> result = await cb.call(some_async_func, arg1, kwarg1=value)

    References:
        - Newman (Building Microservices): Circuit breaker pattern
        - Nygard (Release It!): Stability patterns
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        name: Optional[str] = None,
    ) -> None:
        """
        Initialize CircuitBreaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout_seconds: Seconds to wait before attempting recovery
            name: Optional name for identification (default: "circuit")
        """
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._name = name or "circuit"

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def failure_threshold(self) -> int:
        """Number of failures required to open the circuit."""
        return self._failure_threshold

    @property
    def recovery_timeout_seconds(self) -> float:
        """Seconds to wait before attempting recovery."""
        return self._recovery_timeout_seconds

    @property
    def name(self) -> str:
        """Name of this circuit breaker."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """
        Current state of the circuit breaker.

        This property checks if enough time has passed to transition
        from OPEN to HALF_OPEN.
        """
        if self._state == CircuitState.OPEN and self._should_attempt_recovery():
            self._state = CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self._failure_count

    @property
    def is_open(self) -> bool:
        """Whether the circuit is currently open (failing fast)."""
        return self.state == CircuitState.OPEN

    # =========================================================================
    # State Management
    # =========================================================================

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False

        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._recovery_timeout_seconds

    def _transition_to_open(self) -> None:
        """Transition the circuit to OPEN state."""
        self._state = CircuitState.OPEN

    def record_failure(self) -> None:
        """
        Record a failure.

        WBS 2.7.2.1.4: Track failure rate per service.
        WBS 2.7.2.1.5: Open circuit when threshold exceeded.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        # Open circuit if threshold exceeded or during half-open
        if self._failure_count >= self._failure_threshold or self._state == CircuitState.HALF_OPEN:
            self._transition_to_open()

    def record_success(self) -> None:
        """
        Record a success.

        Resets failure count and closes circuit if in HALF_OPEN.
        """
        self._failure_count = 0

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED

    # =========================================================================
    # Execution
    # =========================================================================

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Call an async function through the circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            CircuitOpenError: If the circuit is open
            Exception: Any exception raised by the wrapped function
        """
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(self._name)

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
