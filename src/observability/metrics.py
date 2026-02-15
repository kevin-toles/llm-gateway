"""
Prometheus Metrics Module - WBS 2.8.2

This module provides Prometheus metrics for observability.

Reference Documents:
- GUIDELINES pp. 2309-2319: "Prometheus for metrics collection and structured logging"
- GUIDELINES pp. 2309: "observability framework encompassing metrics collection, 
  logging strategies, and cost tracking"
- GUIDELINES: "cache hit ratio metric and token usage tracking serve as 
  domain-specific implementations"
- Newman (Building Microservices pp. 273-275): Services "expose basic metrics 
  themselves" including "response times and error rates"
- DEPLOYMENT_IMPL 1.6.1.2.2: Add prometheus-client for metrics

Pattern: Metrics collection for observability
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults

WBS Items:
- 2.8.2.1: Create src/observability/metrics.py
- 2.8.2.2: Define request counter (llm_gateway_requests_total)
- 2.8.2.3: Define request latency histogram (llm_gateway_request_duration_seconds)
- 2.8.2.4: Define active requests gauge (llm_gateway_requests_in_progress)
- 2.8.2.5: Define LLM-specific metrics (token usage, cache hits, cost)
- 2.8.2.6: Create MetricsMiddleware ASGI middleware
- 2.8.2.7: Expose /metrics endpoint via make_asgi_app()

Issue 17 Fix (Comp_Static_Analysis_Report_20251203.md):
- Added normalize_path() to prevent high cardinality from dynamic path segments
- Replaces UUIDs, numeric IDs, and hex IDs with {id} placeholder
"""

import re
import time
from typing import Any, Callable, Optional

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    make_asgi_app,
)

# =============================================================================
# Issue 17 Fix: Path Normalization (High Cardinality Prevention)
# =============================================================================

# Issue 50 (python:S1192): Define constant for duplicated '/{id}' literal
# This placeholder is used in all path normalization patterns
_PATH_ID_PLACEHOLDER = "/{id}"

# Regex patterns for dynamic path segments that cause high cardinality
# Order matters: more specific patterns first
_PATH_PATTERNS = [
    # UUID v4: 8-4-4-4-12 hex pattern (e.g., 123e4567-e89b-12d3-a456-426614174000)
    (re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), _PATH_ID_PLACEHOLDER),
    # MongoDB ObjectId: 24 hex chars (e.g., 507f1f77bcf86cd799439011)
    (re.compile(r"/[0-9a-fA-F]{24}(?=/|$)"), _PATH_ID_PLACEHOLDER),
    # Generic hex ID: 8+ hex chars (but not at start to avoid short strings)
    (re.compile(r"/[0-9a-fA-F]{8,}(?=/|$)"), _PATH_ID_PLACEHOLDER),
    # Numeric ID: pure digits (e.g., /users/12345)
    (re.compile(r"/\d+(?=/|$)"), _PATH_ID_PLACEHOLDER),
]


def normalize_path(path: str) -> str:
    """
    Normalize a URL path by replacing dynamic segments with placeholders.
    
    This prevents high cardinality in Prometheus metrics caused by:
    - UUID path parameters (e.g., /sessions/123e4567-e89b-...)
    - Numeric IDs (e.g., /users/12345)
    - Hex IDs like MongoDB ObjectIds (e.g., /docs/507f1f77bcf86cd799439011)
    
    Issue 17 (Comp_Static_Analysis_Report_20251203.md):
    - "path label in metrics can explode cardinality with dynamic segments"
    - "Impact: Prometheus memory exhaustion"
    
    Reference: GUIDELINES pp. 2309-2319 - metrics should use business-relevant terms
    
    Args:
        path: The URL path to normalize (e.g., "/v1/sessions/uuid-here")
    
    Returns:
        Normalized path with dynamic segments replaced (e.g., "/v1/sessions/{id}")
    
    Examples:
        >>> normalize_path("/health")
        '/health'
        >>> normalize_path("/v1/sessions/123e4567-e89b-12d3-a456-426614174000")
        '/v1/sessions/{id}'
        >>> normalize_path("/v1/users/12345")
        '/v1/users/{id}'
    """
    if path == "/":
        return path
    
    normalized = path
    for pattern, replacement in _PATH_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    
    return normalized


# =============================================================================
# WBS 2.8.2.2: Request Counter
# =============================================================================

REQUESTS_TOTAL = Counter(
    name="llm_gateway_requests_total",
    documentation="Total number of HTTP requests",
    labelnames=["method", "path", "status"],
)

# =============================================================================
# WBS 2.8.2.3: Request Latency Histogram
# =============================================================================

REQUEST_DURATION_SECONDS = Histogram(
    name="llm_gateway_request_duration_seconds",
    documentation="HTTP request duration in seconds",
    labelnames=["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# =============================================================================
# WBS 2.8.2.4: Active Requests Gauge
# =============================================================================

REQUESTS_IN_PROGRESS = Gauge(
    name="llm_gateway_requests_in_progress",
    documentation="Number of HTTP requests currently being processed",
    labelnames=["method"],
)

# =============================================================================
# WBS 2.8.2.5: LLM-Specific Metrics (GUIDELINES pp. 2309-2319)
# =============================================================================

# Token usage counter (GUIDELINES: "token usage tracking")
TOKEN_USAGE_TOTAL = Counter(
    name="llm_gateway_tokens_total",
    documentation="Total number of tokens used",
    labelnames=["provider", "model", "type"],
)

# Cache operations counter (GUIDELINES: "cache hit ratio metric")
CACHE_OPERATIONS_TOTAL = Counter(
    name="llm_gateway_cache_operations_total",
    documentation="Total cache operations by result (hit/miss)",
    labelnames=["result"],
)

# Request cost tracking (GUIDELINES: "cost tracking")
REQUEST_COST_DOLLARS = Histogram(
    name="llm_gateway_request_cost_dollars",
    documentation="Request cost in dollars",
    labelnames=["provider", "model"],
    buckets=(0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# =============================================================================
# OBS-14: Provider-Specific Metrics (Migrated from health.py)
# =============================================================================

# Total requests by provider (for provider-level observability)
PROVIDER_REQUESTS_TOTAL = Counter(
    name="llm_gateway_provider_requests_total",
    documentation="Total requests to LLM providers",
    labelnames=["provider"],
)

# Total errors by provider (for provider-level observability)
PROVIDER_ERRORS_TOTAL = Counter(
    name="llm_gateway_provider_errors_total",
    documentation="Total errors from LLM providers",
    labelnames=["provider", "error_type"],
)

# Latency by provider (for SLA monitoring)
PROVIDER_LATENCY_SECONDS = Histogram(
    name="llm_gateway_provider_latency_seconds",
    documentation="LLM provider response latency in seconds",
    labelnames=["provider"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


# =============================================================================
# Helper Functions
# =============================================================================


def record_token_usage(
    provider: str,
    model: str,
    token_type: str,
    count: int,
) -> None:
    """
    Record token usage for an LLM request.

    Args:
        provider: LLM provider (anthropic, openai, etc.)
        model: Model name (claude-3-sonnet, gpt-4, etc.)
        token_type: Type of tokens (prompt, completion)
        count: Number of tokens
    """
    TOKEN_USAGE_TOTAL.labels(
        provider=provider,
        model=model,
        type=token_type,
    ).inc(count)


def record_cache_operation(result: str) -> None:
    """
    Record a cache operation (hit or miss).

    Args:
        result: Cache operation result ("hit" or "miss")
    """
    CACHE_OPERATIONS_TOTAL.labels(result=result).inc()


def record_request_cost(
    provider: str,
    model: str,
    cost: float,
) -> None:
    """
    Record the cost of an LLM request.

    Args:
        provider: LLM provider
        model: Model name
        cost: Cost in dollars
    """
    REQUEST_COST_DOLLARS.labels(
        provider=provider,
        model=model,
    ).observe(cost)


# =============================================================================
# OBS-14: Provider-Specific Helper Functions
# =============================================================================


def record_provider_request(provider: str) -> None:
    """
    Record a request to an LLM provider.

    Args:
        provider: LLM provider name (anthropic, openai, gemini, local)
    """
    PROVIDER_REQUESTS_TOTAL.labels(provider=provider).inc()


def record_provider_error(provider: str, error_type: str = "unknown") -> None:
    """
    Record an error from an LLM provider.

    Args:
        provider: LLM provider name
        error_type: Type of error (timeout, rate_limit, auth, api_error, etc.)
    """
    PROVIDER_ERRORS_TOTAL.labels(provider=provider, error_type=error_type).inc()


def record_provider_latency(provider: str, latency_seconds: float) -> None:
    """
    Record the latency of an LLM provider response.

    Args:
        provider: LLM provider name
        latency_seconds: Response time in seconds
    """
    PROVIDER_LATENCY_SECONDS.labels(provider=provider).observe(latency_seconds)


# =============================================================================
# WBS 2.8.2.6: MetricsMiddleware ASGI Middleware
# =============================================================================


class MetricsMiddleware:
    """
    ASGI middleware for Prometheus metrics collection.

    WBS 2.8.2.6: Create MetricsMiddleware ASGI middleware.

    Reference:
    - Newman (Building Microservices pp. 273-275): Services "expose basic 
      metrics themselves" including "response times and error rates"

    This middleware:
    - Increments request counter per method/path/status
    - Records request latency histogram
    - Tracks in-progress requests gauge
    - Excludes /metrics path from metrics
    """

    def __init__(
        self,
        app: Callable[..., Any],
        exclude_paths: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize MetricsMiddleware.

        Args:
            app: ASGI application to wrap
            exclude_paths: Paths to exclude from metrics (default: ["/metrics"])
        """
        self.app = app
        self.exclude_paths = exclude_paths or ["/metrics"]

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        """
        Process an ASGI request.

        Args:
            scope: ASGI scope dict
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Pass through non-HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        raw_path = scope.get("path", "/")
        
        # Issue 17 Fix: Normalize path to prevent high cardinality
        # Replace UUIDs, numeric IDs, etc. with {id} placeholder
        path = normalize_path(raw_path)

        # Exclude specified paths from metrics
        if raw_path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        # Track in-progress requests
        REQUESTS_IN_PROGRESS.labels(method=method).inc()
        start_time = time.perf_counter()
        status_code = "500"  # Default if not captured

        # Wrapper to capture status code
        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = str(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Record metrics
            duration = time.perf_counter() - start_time

            REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=status_code,
            ).inc()

            REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=path,
            ).observe(duration)

            REQUESTS_IN_PROGRESS.labels(method=method).dec()


# =============================================================================
# WBS 2.8.2.7: Metrics Endpoint
# =============================================================================


def get_metrics_app() -> Callable[..., Any]:
    """
    Get ASGI app for /metrics endpoint.

    WBS 2.8.2.7: Expose /metrics endpoint via make_asgi_app().

    Returns:
        ASGI application that serves Prometheus metrics
    """
    return make_asgi_app()


def generate_metrics() -> str:
    """
    Generate Prometheus metrics text format.

    Returns:
        Prometheus exposition format text
    """
    return generate_latest(REGISTRY).decode("utf-8")
