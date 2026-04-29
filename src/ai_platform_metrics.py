"""
Platform-standard Prometheus metrics for llm-gateway — P1-02.

All ai_platform_* metrics follow design doc §2.3.
Never add user_id, session_id, or request_id as label values (§2.7).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

if TYPE_CHECKING:
    from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Platform-standard metrics (all services)  design doc §2.3
# ---------------------------------------------------------------------------

REQUEST_TOTAL = Counter(
    "ai_platform_request_total",
    "Total HTTP requests to this service",
    ["service", "endpoint", "method", "status_code"],
)

REQUEST_DURATION = Histogram(
    "ai_platform_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0],
)

CIRCUIT_BREAKER_STATE = Gauge(
    "ai_platform_circuit_breaker_state",
    "Circuit breaker state: 0=CLOSED, 1=OPEN",
    ["service", "circuit_name"],
)

# ---------------------------------------------------------------------------
# llm-gateway domain metric  design doc §2.3
# ---------------------------------------------------------------------------

LLM_TOKENS_TOTAL = Counter(
    "ai_platform_llm_tokens_total",
    "LLM tokens processed",
    ["service", "model", "direction"],  # direction: "input" | "output"
)


def mount_metrics(app: "FastAPI", service_name: str) -> None:  # noqa: ARG001
    """Mount the Prometheus /metrics ASGI sub-application.

    For llm-gateway the endpoint is already mounted in main.py via
    get_metrics_app(); calling mount_metrics() here would register a
    duplicate mount.  This function is a no-op for this service so that
    callers can be written uniformly across all 6 services.
    """
