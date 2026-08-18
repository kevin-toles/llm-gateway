"""
Circuit Breaker State Machine - WBS-CPA3

This module implements the circuit breaker state machine pattern per
textbook specifications from *Building Reactive Microservices in Java* (Escoffier).

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3
- Building Reactive Microservices in Java (Escoffier) Ch.6, pp.54-62
- Release It! (Nygard): Stability patterns
- Microservices Anti-Patterns and Pitfalls (Richards) Ch.3, pp.19-28

State Machine:
    CLOSED: Normal operation, all requests pass through
    OPEN: Circuit tripped, requests fail fast with CircuitBreakerError
    HALF_OPEN: Recovery testing, limited requests pass through

Anti-Pattern Compliance:
- AP-5: Exception uses CircuitBreakerError prefix
- AP-6: State protected by asyncio.Lock() for thread safety
"""

import asyncio
import os
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TypeVar

from src.resilience.metrics import record_circuit_state_transition

T = TypeVar("T")


# =============================================================================
# Constants (AP-1 Compliance: No duplicated string literals)
# =============================================================================

ENV_FAILURE_THRESHOLD = "LLM_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD"
ENV_RESET_TIMEOUT = "LLM_GATEWAY_CIRCUIT_BREAKER_RESET_TIMEOUT"

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RESET_TIMEOUT_SECONDS = 30.0


# =============================================================================
# State Enum
# =============================================================================


class CircuitBreakerState(Enum):
    """
    State of a circuit breaker.

    Per *Building Reactive Microservices in Java* [^10]:
    "A circuit breaker is a three-state automaton that manages an interaction.
    It starts in a closed state, switches to open after N failures,
    and goes to half-open after cooldown to probe recovery."

    States:
        CLOSED: Normal operation, all requests pass through
        OPEN: Circuit is tripped, requests fail immediately
        HALF_OPEN: Recovery testing, limited requests pass through
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# =============================================================================
# Exception Class (AP-5 Compliance: CircuitBreakerError prefix)
# =============================================================================


class CircuitBreakerError(Exception):
    """
    Exception raised when a circuit breaker is open.

    AP-5 Compliance: Uses {Service}Error prefix pattern.

    This indicates that the downstream service is considered unhealthy
    and requests should fail fast rather than waiting for timeout.

    Attributes:
        circuit_name: Name of the circuit breaker that is open
        message: Additional context message
    """

    def __init__(self, circuit_name: str, message: str = "Circuit is open") -> None:
        self.circuit_name = circuit_name
        self.message = message
        super().__init__(f"CircuitBreakerError[{circuit_name}]: {message}")


# =============================================================================
# Circuit Breaker State Machine
# =============================================================================


class CircuitBreakerStateMachine:
    """
    Circuit breaker state machine for protecting against cascading failures.

    WBS-CPA3: Implements CLOSED → OPEN → HALF_OPEN state transitions.

    The state machine monitors failures to downstream services.
    When failures exceed a threshold, it "trips" and fails fast,
    preventing resource exhaustion while the service recovers.

    Per *Building Reactive Microservices in Java* (Escoffier):
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: After reset timeout, allow test request

    Thread Safety (AP-6):
        All state mutations are protected by asyncio.Lock() to prevent
        race conditions in concurrent async contexts.

    Example:
        >>> sm = CircuitBreakerStateMachine(name="semantic-search")
        >>> result = await sm.execute(some_async_func, arg1, kwarg1=value)

    Attributes:
        name: Identifier for this circuit breaker
        failure_threshold: Number of consecutive failures before opening
        reset_timeout_seconds: Seconds to wait before attempting recovery
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        reset_timeout_seconds: float = DEFAULT_RESET_TIMEOUT_SECONDS,
    ) -> None:
        """
        Initialize CircuitBreakerStateMachine.

        Args:
            name: Name for identification and metrics
            failure_threshold: Number of consecutive failures before opening
            reset_timeout_seconds: Seconds to wait before attempting recovery
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout_seconds = reset_timeout_seconds

        # State tracking
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

        # AP-6 Compliance: Thread-safe state transitions
        self._lock = asyncio.Lock()

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def from_env(
        cls,
        name: str,
        failure_threshold: Optional[int] = None,
        reset_timeout_seconds: Optional[float] = None,
    ) -> "CircuitBreakerStateMachine":
        """
        Create CircuitBreakerStateMachine with configuration from environment.

        AC-CPA3.2: Failure threshold configurable via environment.

        Environment Variables:
            LLM_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD: Number of failures
            LLM_GATEWAY_CIRCUIT_BREAKER_RESET_TIMEOUT: Reset timeout in seconds

        Args:
            name: Name for identification
            failure_threshold: Override failure threshold (else use env/default)
            reset_timeout_seconds: Override reset timeout (else use env/default)

        Returns:
            Configured CircuitBreakerStateMachine instance
        """
        env_threshold = os.environ.get(ENV_FAILURE_THRESHOLD)
        env_timeout = os.environ.get(ENV_RESET_TIMEOUT)

        resolved_threshold = failure_threshold
        if resolved_threshold is None:
            if env_threshold:
                resolved_threshold = int(env_threshold)
            else:
                resolved_threshold = DEFAULT_FAILURE_THRESHOLD

        resolved_timeout = reset_timeout_seconds
        if resolved_timeout is None:
            if env_timeout:
                resolved_timeout = float(env_timeout)
            else:
                resolved_timeout = DEFAULT_RESET_TIMEOUT_SECONDS

        return cls(
            name=name,
            failure_threshold=resolved_threshold,
            reset_timeout_seconds=resolved_timeout,
        )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Name of this circuit breaker."""
        return self._name

    @property
    def failure_threshold(self) -> int:
        """Number of failures required to open the circuit."""
        return self._failure_threshold

    @property
    def reset_timeout_seconds(self) -> float:
        """Seconds to wait before attempting recovery."""
        return self._reset_timeout_seconds

    @property
    def state(self) -> CircuitBreakerState:
        """
        Current state of the circuit breaker.

        Note: This returns cached state. For thread-safe state checks
        that may trigger transitions, use get_state() async method.
        """
        return self._state

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self._failure_count

    # =========================================================================
    # State Management (Thread-Safe)
    # =========================================================================

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False

        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._reset_timeout_seconds

    async def get_state(self) -> CircuitBreakerState:
        """
        Get current state with atomic OPEN → HALF_OPEN transition check.

        AP-6 Compliance: Uses asyncio.Lock() for thread safety.

        This method safely transitions from OPEN → HALF_OPEN when the
        reset timeout has elapsed, using a lock to prevent race conditions.

        Returns:
            Current CircuitBreakerState after any transitions
        """
        async with self._lock:
            if (
                self._state == CircuitBreakerState.OPEN
                and self._should_attempt_recovery()
            ):
                old_state = self._state
                self._state = CircuitBreakerState.HALF_OPEN
                record_circuit_state_transition(
                    self._name,
                    self._state.value,
                    old_state.value,
                )
            return self._state

    async def record_failure(self) -> None:
        """
        Record a failure.

        Thread-safe method that increments failure count and transitions
        to OPEN state when threshold exceeded or during HALF_OPEN.

        AC-CPA3.1: Implements CLOSED → OPEN transition on threshold.
        AC-CPA3.1: Implements HALF_OPEN → OPEN transition on failure.
        """
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            # Transition to OPEN if threshold exceeded or in HALF_OPEN
            if (
                self._failure_count >= self._failure_threshold
                or self._state == CircuitBreakerState.HALF_OPEN
            ):
                old_state = self._state
                self._state = CircuitBreakerState.OPEN
                record_circuit_state_transition(
                    self._name,
                    self._state.value,
                    old_state.value,
                )

    async def record_success(self) -> None:
        """
        Record a success.

        Thread-safe method that resets failure count and transitions
        to CLOSED state if currently in HALF_OPEN.

        AC-CPA3.1: Implements HALF_OPEN → CLOSED transition on success.
        """
        async with self._lock:
            self._failure_count = 0

            if self._state == CircuitBreakerState.HALF_OPEN:
                old_state = self._state
                self._state = CircuitBreakerState.CLOSED
                record_circuit_state_transition(
                    self._name,
                    self._state.value,
                    old_state.value,
                )

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute an async function through the circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerError: If the circuit is open
            Exception: Any exception raised by the wrapped function
        """
        # Check state with atomic transition
        current_state = await self.get_state()

        if current_state == CircuitBreakerState.OPEN:
            raise CircuitBreakerError(
                self._name,
                f"Circuit is open - failing fast (threshold={self._failure_threshold})",
            )

        try:
            result = await func(*args, **kwargs)
            await self.record_success()
            return result
        except Exception:
            await self.record_failure()
            raise
