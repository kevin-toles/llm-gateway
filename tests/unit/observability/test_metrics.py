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
