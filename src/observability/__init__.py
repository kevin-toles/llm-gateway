"""
Observability Package - WBS 2.8 Observability Implementation

This package provides observability infrastructure including:
- Structured JSON logging (WBS 2.8.1)
- Prometheus metrics (WBS 2.8.2)
- OpenTelemetry tracing (WBS 2.8.3)

Reference Documents:
- GUIDELINES pp. 2309-2319: Observability = metrics + logging + cost tracking
- GUIDELINES pp. 2319: Newman "log when timeouts occur"
- ARCHITECTURE.md: Line 30 - middleware/logging.py

WBS Items:
- 2.8.1: Structured Logging
- 2.8.2: Metrics
- 2.8.3: Tracing
"""

from src.observability.logging import (
    clear_correlation_id,
    correlation_id_context,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)

from src.observability.metrics import (
    MetricsMiddleware,
    get_metrics_app,
    generate_metrics,
    record_cache_operation,
    record_request_cost,
    record_token_usage,
    # OBS-14: Provider-specific metrics
    record_provider_request,
    record_provider_error,
    record_provider_latency,
)

from src.observability.tracing import (
    TracingMiddleware,
    create_span,
    extract_trace_context,
    get_current_span_id,
    get_current_trace_id,
    get_tracer,
    inject_trace_context,
    setup_tracing,
    traced,
)

__all__ = [
    # Logging
    "get_logger",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    "correlation_id_context",
    # Metrics
    "MetricsMiddleware",
    "get_metrics_app",
    "generate_metrics",
    "record_token_usage",
    "record_cache_operation",
    "record_request_cost",
    # OBS-14: Provider metrics
    "record_provider_request",
    "record_provider_error",
    "record_provider_latency",
    # Tracing
    "TracingMiddleware",
    "setup_tracing",
    "get_tracer",
    "get_current_trace_id",
    "get_current_span_id",
    "inject_trace_context",
    "extract_trace_context",
    "create_span",
    "traced",
]
