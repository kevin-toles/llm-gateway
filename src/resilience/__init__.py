"""
Resilience patterns for LLM Gateway.

WBS-CPA3: Circuit Breaker Fallback Chains

This module provides resilience patterns including:
- CircuitBreakerStateMachine: State machine for circuit breaker pattern
- FallbackChain: Ordered backend fallback with circuit breakers
- Prometheus metrics for state transitions

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA3
- Building Reactive Microservices in Java (Escoffier): Circuit breaker pattern
- Microservices Patterns (Richardson): API Gateway resilience
"""

from src.resilience.circuit_breaker_state_machine import (
    CircuitBreakerError,
    CircuitBreakerStateMachine,
    CircuitBreakerState,
)
from src.resilience.fallback_chain import (
    FallbackChain,
    FallbackChainError,
    FallbackBackend,
)
from src.resilience.metrics import (
    record_circuit_state_transition,
    record_fallback_attempt,
    record_fallback_success,
)

__all__ = [
    # Circuit Breaker
    "CircuitBreakerStateMachine",
    "CircuitBreakerState",
    "CircuitBreakerError",
    # Fallback Chain
    "FallbackChain",
    "FallbackChainError",
    "FallbackBackend",
    # Metrics
    "record_circuit_state_transition",
    "record_fallback_attempt",
    "record_fallback_success",
]
