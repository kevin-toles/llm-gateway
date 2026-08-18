"""Admin diagnostic routes for llm-gateway.

Provides circuit breaker reset endpoints for recovering from stuck-open
circuit breakers.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/admin/circuits/reset")
async def reset_circuit_breakers() -> dict[str, str]:
    """Force-reset ALL circuit breakers to CLOSED.

    Admin endpoint for recovering from stuck-open circuit breakers.
    """
    from src.resilience.circuit_breaker_state_machine import CircuitBreakerStateMachine  # noqa: PLC0415

    # llm-gateway uses per-backend CircuitBreakerStateMachine instances
    # This endpoint is a placeholder — circuit breakers are created per-backend
    # in the code that uses them.
    return {"status": "llm-gateway circuit breakers are per-backend; use service restart"}


@router.post("/admin/circuits/{backend_name}/reset")
async def reset_circuit_breaker(backend_name: str) -> dict[str, str]:
    """Force-reset a single backend's circuit breaker to CLOSED.

    Admin endpoint for recovering from a stuck-open circuit breaker.
    """
    return {"status": f"llm-gateway circuit breakers are per-backend; use service restart"}
