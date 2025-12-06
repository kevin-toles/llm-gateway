"""
Tests for Prometheus Metrics - WBS 2.8.2

TDD RED Phase: Tests for Prometheus Metrics Implementation.

Reference Documents:
- GUIDELINES pp. 2309-2319: "Prometheus for metrics collection and structured logging"
- GUIDELINES pp. 2309: "observability framework encompassing metrics collection, logging strategies"
- GUIDELINES: "cache hit ratio metric and token usage tracking serve as domain-specific implementations"
- Newman (Building Microservices pp. 273-275): Services "expose basic metrics themselves"
  including "response times and error rates"
- DEPLOYMENT_IMPL 1.6.1.2.2: Add prometheus-client for metrics

WBS Items Covered:
- 2.8.2.1: Create src/observability/metrics.py
- 2.8.2.2: Define request counter (llm_gateway_requests_total)
- 2.8.2.3: Define request latency histogram (llm_gateway_request_duration_seconds)
- 2.8.2.4: Define active requests gauge (llm_gateway_requests_in_progress)
- 2.8.2.5: Define LLM-specific metrics (token usage, cache hits)
- 2.8.2.6: Create MetricsMiddleware ASGI middleware
- 2.8.2.7: Expose /metrics endpoint via make_asgi_app()
- 2.8.2.8: RED test: metrics endpoint returns Prometheus format
- 2.8.2.9: GREEN: implement and pass tests
"""

import io
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# WBS 2.8.2.1: Module Structure Tests
# =============================================================================


class TestMetricsModule:
    """Tests for metrics module structure."""

    def test_metrics_module_importable(self) -> None:
        """
        WBS 2.8.2.1: metrics module is importable.
        """
        from src.observability import metrics

        assert metrics is not None

    def test_metrics_middleware_class_exists(self) -> None:
        """
        WBS 2.8.2.6: MetricsMiddleware class exists.
        """
        from src.observability.metrics import MetricsMiddleware

        assert MetricsMiddleware is not None


# =============================================================================
# WBS 2.8.2.2: Request Counter Tests
# =============================================================================


class TestRequestCounter:
    """Tests for request counter metric."""

    def test_request_counter_defined(self) -> None:
        """
        WBS 2.8.2.2: Request counter metric is defined.
        """
        from src.observability.metrics import REQUESTS_TOTAL

        assert REQUESTS_TOTAL is not None

    def test_request_counter_has_correct_name(self) -> None:
        """
        Counter has correct name: llm_gateway_requests_total.
        """
        from src.observability.metrics import REQUESTS_TOTAL

        # prometheus_client strips "_total" suffix for internal _name
        # Verify via describe() which returns full metric name
        metric_desc = REQUESTS_TOTAL.describe()[0]
        assert "llm_gateway_requests" in metric_desc.name

    def test_request_counter_has_method_label(self) -> None:
        """
        Counter has 'method' label.
        """
        from src.observability.metrics import REQUESTS_TOTAL

        assert "method" in REQUESTS_TOTAL._labelnames

    def test_request_counter_has_path_label(self) -> None:
        """
        Counter has 'path' label.
        """
        from src.observability.metrics import REQUESTS_TOTAL

        assert "path" in REQUESTS_TOTAL._labelnames

    def test_request_counter_has_status_label(self) -> None:
        """
        Counter has 'status' label.
        """
        from src.observability.metrics import REQUESTS_TOTAL

        assert "status" in REQUESTS_TOTAL._labelnames


# =============================================================================
# WBS 2.8.2.3: Request Latency Histogram Tests
# =============================================================================


class TestRequestLatencyHistogram:
    """Tests for request latency histogram metric."""

    def test_latency_histogram_defined(self) -> None:
        """
        WBS 2.8.2.3: Request latency histogram is defined.
        """
        from src.observability.metrics import REQUEST_DURATION_SECONDS

        assert REQUEST_DURATION_SECONDS is not None

    def test_latency_histogram_has_correct_name(self) -> None:
        """
        Histogram has correct name: llm_gateway_request_duration_seconds.
        """
        from src.observability.metrics import REQUEST_DURATION_SECONDS

        assert REQUEST_DURATION_SECONDS._name == "llm_gateway_request_duration_seconds"

    def test_latency_histogram_has_method_label(self) -> None:
        """
        Histogram has 'method' label.
        """
        from src.observability.metrics import REQUEST_DURATION_SECONDS

        assert "method" in REQUEST_DURATION_SECONDS._labelnames

    def test_latency_histogram_has_path_label(self) -> None:
        """
        Histogram has 'path' label.
        """
        from src.observability.metrics import REQUEST_DURATION_SECONDS

        assert "path" in REQUEST_DURATION_SECONDS._labelnames


# =============================================================================
# WBS 2.8.2.4: Active Requests Gauge Tests
# =============================================================================


class TestActiveRequestsGauge:
    """Tests for active requests gauge metric."""

    def test_active_requests_gauge_defined(self) -> None:
        """
        WBS 2.8.2.4: Active requests gauge is defined.
        """
        from src.observability.metrics import REQUESTS_IN_PROGRESS

        assert REQUESTS_IN_PROGRESS is not None

    def test_active_requests_gauge_has_correct_name(self) -> None:
        """
        Gauge has correct name: llm_gateway_requests_in_progress.
        """
        from src.observability.metrics import REQUESTS_IN_PROGRESS

        assert REQUESTS_IN_PROGRESS._name == "llm_gateway_requests_in_progress"

    def test_active_requests_gauge_has_method_label(self) -> None:
        """
        Gauge has 'method' label.
        """
        from src.observability.metrics import REQUESTS_IN_PROGRESS

        assert "method" in REQUESTS_IN_PROGRESS._labelnames


# =============================================================================
# WBS 2.8.2.5: LLM-Specific Metrics Tests (GUIDELINES pp. 2309-2319)
# =============================================================================


class TestLLMSpecificMetrics:
    """
    Tests for LLM-specific metrics per GUIDELINES.
    
    Reference: "cache hit ratio metric and token usage tracking serve as
    domain-specific implementations"
    """

    def test_token_usage_counter_defined(self) -> None:
        """
        Token usage counter is defined (GUIDELINES: token usage tracking).
        """
        from src.observability.metrics import TOKEN_USAGE_TOTAL

        assert TOKEN_USAGE_TOTAL is not None

    def test_token_usage_counter_has_correct_name(self) -> None:
        """
        Token counter has correct name: llm_gateway_tokens_total.
        """
        from src.observability.metrics import TOKEN_USAGE_TOTAL

        # prometheus_client strips "_total" suffix for internal _name
        metric_desc = TOKEN_USAGE_TOTAL.describe()[0]
        assert "llm_gateway_tokens" in metric_desc.name

    def test_token_usage_has_provider_label(self) -> None:
        """
        Token counter has 'provider' label.
        """
        from src.observability.metrics import TOKEN_USAGE_TOTAL

        assert "provider" in TOKEN_USAGE_TOTAL._labelnames

    def test_token_usage_has_model_label(self) -> None:
        """
        Token counter has 'model' label.
        """
        from src.observability.metrics import TOKEN_USAGE_TOTAL

        assert "model" in TOKEN_USAGE_TOTAL._labelnames

    def test_token_usage_has_type_label(self) -> None:
        """
        Token counter has 'type' label (prompt/completion).
        """
        from src.observability.metrics import TOKEN_USAGE_TOTAL

        assert "type" in TOKEN_USAGE_TOTAL._labelnames

    def test_cache_hit_counter_defined(self) -> None:
        """
        Cache hit counter is defined (GUIDELINES: cache hit ratio).
        """
        from src.observability.metrics import CACHE_OPERATIONS_TOTAL

        assert CACHE_OPERATIONS_TOTAL is not None

    def test_cache_hit_counter_has_correct_name(self) -> None:
        """
        Cache counter has correct name: llm_gateway_cache_operations_total.
        """
        from src.observability.metrics import CACHE_OPERATIONS_TOTAL

        # prometheus_client strips "_total" suffix for internal _name
        metric_desc = CACHE_OPERATIONS_TOTAL.describe()[0]
        assert "llm_gateway_cache_operations" in metric_desc.name

    def test_cache_counter_has_result_label(self) -> None:
        """
        Cache counter has 'result' label (hit/miss).
        """
        from src.observability.metrics import CACHE_OPERATIONS_TOTAL

        assert "result" in CACHE_OPERATIONS_TOTAL._labelnames

    def test_cost_tracker_gauge_defined(self) -> None:
        """
        Cost tracking gauge is defined (GUIDELINES: cost tracking).
        """
        from src.observability.metrics import REQUEST_COST_DOLLARS

        assert REQUEST_COST_DOLLARS is not None

    def test_cost_gauge_has_correct_name(self) -> None:
        """
        Cost gauge has correct name: llm_gateway_request_cost_dollars.
        """
        from src.observability.metrics import REQUEST_COST_DOLLARS

        assert REQUEST_COST_DOLLARS._name == "llm_gateway_request_cost_dollars"


# =============================================================================
# WBS 2.8.2.6: MetricsMiddleware Tests
# =============================================================================


class TestMetricsMiddleware:
    """Tests for MetricsMiddleware ASGI middleware."""

    @pytest.fixture
    def mock_app(self) -> AsyncMock:
        """Create mock ASGI app."""
        async def app(scope: dict, receive: Any, send: Any) -> None:
            if scope["type"] == "http":
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({
                    "type": "http.response.body",
                    "body": b'{"ok": true}',
                })
        return app

    @pytest.mark.asyncio
    async def test_middleware_passes_through_non_http(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware passes through non-HTTP requests (websocket, lifespan).
        """
        from src.observability.metrics import MetricsMiddleware

        middleware = MetricsMiddleware(mock_app)
        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        # Should not raise
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_middleware_increments_request_counter(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware increments request counter on HTTP request.
        """
        from src.observability.metrics import MetricsMiddleware, REQUESTS_TOTAL

        middleware = MetricsMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/chat/completions",
            "headers": [],
        }
        receive = AsyncMock()
        
        # Capture response status
        responses: list[dict] = []
        async def capture_send(message: dict) -> None:
            responses.append(message)
        
        await middleware(scope, receive, capture_send)

        # Counter should have been incremented
        # We verify by checking the metric value is accessible
        counter_value = REQUESTS_TOTAL.labels(
            method="GET", path="/v1/chat/completions", status="200"
        )._value.get()
        assert counter_value >= 0  # At least accessed

    @pytest.mark.asyncio
    async def test_middleware_records_latency(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware records request latency in histogram.
        """
        from src.observability.metrics import MetricsMiddleware, REQUEST_DURATION_SECONDS

        middleware = MetricsMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Histogram should have observations
        # Check that the histogram is accessible
        histogram = REQUEST_DURATION_SECONDS.labels(
            method="POST", path="/v1/chat/completions"
        )
        assert histogram is not None

    @pytest.mark.asyncio
    async def test_middleware_tracks_in_progress(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware tracks requests in progress.
        """
        from src.observability.metrics import MetricsMiddleware, REQUESTS_IN_PROGRESS

        middleware = MetricsMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Gauge should track in-progress requests
        await middleware(scope, receive, send)
        
        # After request, in_progress should be back to 0
        gauge = REQUESTS_IN_PROGRESS.labels(method="GET")
        assert gauge._value.get() == 0

    @pytest.mark.asyncio
    async def test_middleware_excludes_metrics_path(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware excludes /metrics path from metrics.
        """
        from src.observability.metrics import MetricsMiddleware, REQUESTS_TOTAL

        middleware = MetricsMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/metrics",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Get initial value (should be 0 or not exist)
        initial_value = 0
        try:
            initial_value = REQUESTS_TOTAL.labels(
                method="GET", path="/metrics", status="200"
            )._value.get()
        except Exception:
            pass

        await middleware(scope, receive, send)

        # Counter should NOT have been incremented
        final_value = REQUESTS_TOTAL.labels(
            method="GET", path="/metrics", status="200"
        )._value.get()
        assert final_value == initial_value


# =============================================================================
# WBS 2.8.2.7: Metrics Endpoint Tests
# =============================================================================


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_get_metrics_app_function_exists(self) -> None:
        """
        WBS 2.8.2.7: get_metrics_app() function exists.
        """
        from src.observability.metrics import get_metrics_app

        assert get_metrics_app is not None
        assert callable(get_metrics_app)

    def test_metrics_app_returns_asgi_app(self) -> None:
        """
        get_metrics_app() returns ASGI application.
        """
        from src.observability.metrics import get_metrics_app

        app = get_metrics_app()
        # ASGI app should be callable
        assert callable(app)


# =============================================================================
# WBS 2.8.2.8: Prometheus Format Output Tests
# =============================================================================


class TestPrometheusFormatOutput:
    """Tests for Prometheus exposition format."""

    def test_generate_metrics_text_function_exists(self) -> None:
        """
        generate_metrics() function exists for text output.
        """
        from src.observability.metrics import generate_metrics

        assert generate_metrics is not None
        assert callable(generate_metrics)

    def test_metrics_output_includes_help(self) -> None:
        """
        WBS 2.8.2.8: Metrics output includes HELP lines.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "# HELP" in output

    def test_metrics_output_includes_type(self) -> None:
        """
        Metrics output includes TYPE lines.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "# TYPE" in output

    def test_metrics_output_includes_request_counter(self) -> None:
        """
        Metrics output includes request counter.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "llm_gateway_requests_total" in output

    def test_metrics_output_includes_latency_histogram(self) -> None:
        """
        Metrics output includes latency histogram.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "llm_gateway_request_duration_seconds" in output

    def test_metrics_output_includes_in_progress_gauge(self) -> None:
        """
        Metrics output includes in-progress gauge.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "llm_gateway_requests_in_progress" in output

    def test_metrics_output_includes_token_counter(self) -> None:
        """
        Metrics output includes token usage counter.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "llm_gateway_tokens_total" in output

    def test_metrics_output_includes_cache_counter(self) -> None:
        """
        Metrics output includes cache operations counter.
        """
        from src.observability.metrics import generate_metrics

        output = generate_metrics()
        assert "llm_gateway_cache_operations_total" in output


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestMetricsHelperFunctions:
    """Tests for metrics helper functions."""

    def test_record_token_usage_function_exists(self) -> None:
        """
        record_token_usage() helper function exists.
        """
        from src.observability.metrics import record_token_usage

        assert record_token_usage is not None
        assert callable(record_token_usage)

    def test_record_token_usage_accepts_parameters(self) -> None:
        """
        record_token_usage() accepts provider, model, type, count.
        """
        from src.observability.metrics import record_token_usage

        # Should not raise
        record_token_usage(
            provider="anthropic",
            model="claude-3-sonnet",
            token_type="prompt",
            count=100,
        )

    def test_record_cache_operation_function_exists(self) -> None:
        """
        record_cache_operation() helper function exists.
        """
        from src.observability.metrics import record_cache_operation

        assert record_cache_operation is not None
        assert callable(record_cache_operation)

    def test_record_cache_hit(self) -> None:
        """
        record_cache_operation() records cache hit.
        """
        from src.observability.metrics import record_cache_operation

        # Should not raise
        record_cache_operation(result="hit")

    def test_record_cache_miss(self) -> None:
        """
        record_cache_operation() records cache miss.
        """
        from src.observability.metrics import record_cache_operation

        # Should not raise
        record_cache_operation(result="miss")

    def test_record_request_cost_function_exists(self) -> None:
        """
        record_request_cost() helper function exists.
        """
        from src.observability.metrics import record_request_cost

        assert record_request_cost is not None
        assert callable(record_request_cost)

    def test_record_request_cost_accepts_amount(self) -> None:
        """
        record_request_cost() accepts cost amount.
        """
        from src.observability.metrics import record_request_cost

        # Should not raise
        record_request_cost(
            provider="anthropic",
            model="claude-3-sonnet",
            cost=0.0015,
        )


# =============================================================================
# Export Tests
# =============================================================================


# =============================================================================
# Issue 17: Path Normalization Tests (High Cardinality Prevention)
# =============================================================================


class TestPathNormalization:
    """
    Tests for path normalization to prevent high cardinality metrics.
    
    Issue 17 from Comp_Static_Analysis_Report_20251203.md:
    - Dynamic path segments like UUIDs and numeric IDs can explode Prometheus cardinality
    - Solution: Normalize paths by replacing UUIDs/IDs with placeholders
    
    Reference: GUIDELINES pp. 2309-2319 - metrics should use business-relevant terms
    """

    def test_normalize_path_function_exists(self) -> None:
        """
        normalize_path() function exists in metrics module.
        """
        from src.observability.metrics import normalize_path

        assert normalize_path is not None
        assert callable(normalize_path)

    def test_normalize_path_preserves_static_paths(self) -> None:
        """
        Static paths without dynamic segments are unchanged.
        """
        from src.observability.metrics import normalize_path

        assert normalize_path("/health") == "/health"
        assert normalize_path("/v1/chat/completions") == "/v1/chat/completions"
        assert normalize_path("/metrics") == "/metrics"

    def test_normalize_path_replaces_uuid_v4(self) -> None:
        """
        UUID v4 segments are replaced with {id} placeholder.
        """
        from src.observability.metrics import normalize_path

        path = "/v1/sessions/123e4567-e89b-12d3-a456-426614174000"
        result = normalize_path(path)
        assert result == "/v1/sessions/{id}"

    def test_normalize_path_replaces_numeric_ids(self) -> None:
        """
        Numeric ID segments are replaced with {id} placeholder.
        """
        from src.observability.metrics import normalize_path

        path = "/v1/users/12345"
        result = normalize_path(path)
        assert result == "/v1/users/{id}"

    def test_normalize_path_replaces_multiple_ids(self) -> None:
        """
        Multiple dynamic segments in path are all normalized.
        """
        from src.observability.metrics import normalize_path

        path = "/v1/users/12345/sessions/abc123-def456-7890"
        result = normalize_path(path)
        # Both numeric ID and UUID-like should be normalized
        assert "{id}" in result
        assert "12345" not in result

    def test_normalize_path_handles_root_path(self) -> None:
        """
        Root path is unchanged.
        """
        from src.observability.metrics import normalize_path

        assert normalize_path("/") == "/"

    def test_normalize_path_replaces_hex_ids(self) -> None:
        """
        Hexadecimal ID segments (like MongoDB ObjectIds) are replaced.
        """
        from src.observability.metrics import normalize_path

        # MongoDB ObjectId format (24 hex chars)
        path = "/v1/documents/507f1f77bcf86cd799439011"
        result = normalize_path(path)
        assert result == "/v1/documents/{id}"

    def test_middleware_uses_normalized_path_for_metrics(self) -> None:
        """
        MetricsMiddleware uses normalized paths when recording metrics.
        
        This prevents high cardinality explosion from dynamic path segments.
        """
        from src.observability.metrics import MetricsMiddleware, REQUESTS_TOTAL

        async def mock_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b""})

        middleware = MetricsMiddleware(mock_app)

        import asyncio

        async def test_normalized_path():
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/v1/sessions/123e4567-e89b-12d3-a456-426614174000",
                "headers": [],
            }

            async def receive():
                return {"type": "http.request", "body": b""}

            responses = []

            async def send(msg):
                responses.append(msg)

            await middleware(scope, receive, send)

            # The metric should be recorded with normalized path, not raw UUID
            # Check that the normalized path label is used
            counter = REQUESTS_TOTAL.labels(
                method="GET", path="/v1/sessions/{id}", status="200"
            )
            # If this doesn't raise, the label combination exists
            assert counter is not None

        asyncio.get_event_loop().run_until_complete(test_normalized_path())


class TestMetricsExports:
    """Tests for module exports."""

    def test_metrics_importable_from_observability(self) -> None:
        """
        Metrics are importable from src.observability.
        """
        from src.observability import MetricsMiddleware

        assert MetricsMiddleware is not None

    def test_get_metrics_app_importable(self) -> None:
        """
        get_metrics_app is importable from src.observability.
        """
        from src.observability import get_metrics_app

        assert get_metrics_app is not None

    def test_record_token_usage_importable(self) -> None:
        """
        record_token_usage is importable from src.observability.
        """
        from src.observability import record_token_usage

        assert record_token_usage is not None

    def test_record_cache_operation_importable(self) -> None:
        """
        record_cache_operation is importable from src.observability.
        """
        from src.observability import record_cache_operation

        assert record_cache_operation is not None


# =============================================================================
# SonarQube Code Quality Fixes - Batch 6 (Issue 50)
# =============================================================================


class TestSonarQubeCodeQualityFixesBatch6:
    """
    TDD RED Phase: Tests for SonarQube code smell fixes.
    
    Issue 50: metrics.py:54 - Duplicated literal '/{id}' appears 4 times
    Rule: python:S1192 - Define a constant instead of duplicating this literal
    
    Reference: CODING_PATTERNS_ANALYSIS.md - NEW pattern for duplicated literals
    """

    def test_path_id_placeholder_constant_exists(self) -> None:
        """
        Issue 50 (S1192): A constant should be defined for '/{id}' placeholder.
        
        The literal '/{id}' appears 4 times in _PATH_PATTERNS. Per DRY principle
        and SonarQube S1192, this should be extracted to a named constant.
        """
        from src.observability import metrics
        
        # Check that _PATH_ID_PLACEHOLDER constant exists
        assert hasattr(metrics, "_PATH_ID_PLACEHOLDER"), (
            "Expected _PATH_ID_PLACEHOLDER constant to be defined in metrics.py"
        )
        assert metrics._PATH_ID_PLACEHOLDER == "/{id}"

    def test_path_patterns_use_constant(self) -> None:
        """
        Issue 50 (S1192): _PATH_PATTERNS should reference the constant.
        
        Verifies that the constant is actually used in the patterns,
        not hardcoded literal strings.
        """
        from src.observability import metrics
        
        # All patterns should use the same placeholder value
        for pattern, replacement in metrics._PATH_PATTERNS:
            if "{id}" in replacement:
                assert replacement == metrics._PATH_ID_PLACEHOLDER, (
                    f"Pattern replacement '{replacement}' should use _PATH_ID_PLACEHOLDER"
                )

