"""
Resilience Metrics - WBS-CPA3

This module provides Prometheus metrics for circuit breaker and fallback chain
resilience patterns.

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3, AC-CPA3.5
- GUIDELINES pp. 2309-2319: Prometheus for metrics collection

Metrics Provided:
- Circuit breaker state transitions (counter)
- Fallback chain attempts (counter)
- Fallback chain successes (counter)

Anti-Pattern Compliance:
- AP-1: Metric names as constants
"""

from prometheus_client import Counter, Gauge

# =============================================================================
# Constants (AP-1 Compliance: No duplicated string literals)
# =============================================================================

METRIC_CIRCUIT_TRANSITIONS = "llm_gateway_circuit_breaker_state_transitions_total"
METRIC_FALLBACK_ATTEMPTS = "llm_gateway_fallback_chain_attempts_total"
METRIC_FALLBACK_SUCCESSES = "llm_gateway_fallback_chain_successes_total"
METRIC_CIRCUIT_STATE = "llm_gateway_circuit_breaker_state"


# =============================================================================
# CPA3.6: Circuit Breaker State Transition Metrics
# =============================================================================

CIRCUIT_STATE_TRANSITIONS = Counter(
    name=METRIC_CIRCUIT_TRANSITIONS,
    documentation="Total number of circuit breaker state transitions",
    labelnames=["circuit_name", "to_state", "from_state"],
)

CIRCUIT_STATE_GAUGE = Gauge(
    name=METRIC_CIRCUIT_STATE,
    documentation="Current state of circuit breaker (0=closed, 1=half_open, 2=open)",
    labelnames=["circuit_name"],
)

# State to numeric mapping for gauge
_STATE_TO_NUMERIC = {
    "closed": 0,
    "half_open": 1,
    "open": 2,
}


def record_circuit_state_transition(
    circuit_name: str,
    to_state: str,
    from_state: str,
) -> None:
    """
    Record a circuit breaker state transition.

    AC-CPA3.5: Metrics emitted on state transitions.

    Args:
        circuit_name: Name of the circuit breaker
        to_state: State transitioning to (closed, open, half_open)
        from_state: State transitioning from (closed, open, half_open)
    """
    CIRCUIT_STATE_TRANSITIONS.labels(
        circuit_name=circuit_name,
        to_state=to_state,
        from_state=from_state,
    ).inc()

    # Update gauge to current state
    CIRCUIT_STATE_GAUGE.labels(circuit_name=circuit_name).set(
        _STATE_TO_NUMERIC.get(to_state, 0)
    )


# =============================================================================
# Fallback Chain Metrics
# =============================================================================

FALLBACK_ATTEMPTS = Counter(
    name=METRIC_FALLBACK_ATTEMPTS,
    documentation="Total number of fallback chain backend attempts",
    labelnames=["chain_name", "backend_name", "operation"],
)

FALLBACK_SUCCESSES = Counter(
    name=METRIC_FALLBACK_SUCCESSES,
    documentation="Total number of successful fallback chain backend calls",
    labelnames=["chain_name", "backend_name"],
)


def record_fallback_attempt(
    chain_name: str,
    backend_name: str,
    operation: str,
) -> None:
    """
    Record a fallback chain backend attempt.

    Args:
        chain_name: Name of the fallback chain
        backend_name: Name of the backend being attempted
        operation: Operation being performed (search, embed, etc.)
    """
    FALLBACK_ATTEMPTS.labels(
        chain_name=chain_name,
        backend_name=backend_name,
        operation=operation,
    ).inc()


def record_fallback_success(
    chain_name: str,
    backend_name: str,
) -> None:
    """
    Record a successful fallback chain backend call.

    Args:
        chain_name: Name of the fallback chain
        backend_name: Name of the successful backend
    """
    FALLBACK_SUCCESSES.labels(
        chain_name=chain_name,
        backend_name=backend_name,
    ).inc()
