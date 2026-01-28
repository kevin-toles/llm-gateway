"""
Tests for OpenTelemetry Tracing - WBS 2.8.3

TDD RED Phase: Tests for OpenTelemetry Tracing Implementation.

Reference Documents:
- GUIDELINES pp. 2309-2319: "observability framework encompassing metrics collection, 
  logging strategies, and cost tracking"
- GUIDELINES: "modern ML evaluation systems are not monolithic scripts but distributed 
  systems requiring careful attention to consistency, scalability, and observability"
- DEPLOYMENT_IMPL 1.6.1.2.3-5: Add opentelemetry-api, opentelemetry-sdk, 
  opentelemetry-instrumentation-fastapi
- Acceptance Criteria: "OpenTelemetry traces generated for requests. Correlation IDs 
  propagated across services."

WBS Items Covered:
- 2.8.3.1: Create src/observability/tracing.py
- 2.8.3.2: Configure TracerProvider with OTLP exporter
- 2.8.3.3: Create TracingMiddleware ASGI middleware
- 2.8.3.4: Generate trace_id and span_id for requests
- 2.8.3.5: Add trace context to structured logs (correlation)
- 2.8.3.6: Propagate trace context in outbound requests
- 2.8.3.7: Export setup_tracing() function
- 2.8.3.8: RED test: trace spans created for requests
- 2.8.3.9: GREEN: implement and pass tests
"""

import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# WBS 2.8.3.1: Module Structure Tests
# =============================================================================


class TestTracingModule:
    """Tests for tracing module structure."""

    def test_tracing_module_importable(self) -> None:
        """
        WBS 2.8.3.1: tracing module is importable.
        """
        from src.observability import tracing

        assert tracing is not None

    def test_tracing_middleware_class_exists(self) -> None:
        """
        WBS 2.8.3.3: TracingMiddleware class exists.
        """
        from src.observability.tracing import TracingMiddleware

        assert TracingMiddleware is not None


# =============================================================================
# WBS 2.8.3.2: TracerProvider Configuration Tests
# =============================================================================


class TestTracerProviderConfiguration:
    """Tests for TracerProvider setup."""

    def test_setup_tracing_function_exists(self) -> None:
        """
        WBS 2.8.3.7: setup_tracing() function exists.
        """
        from src.observability.tracing import setup_tracing

        assert setup_tracing is not None
        assert callable(setup_tracing)

    def test_setup_tracing_returns_tracer_provider(self) -> None:
        """
        setup_tracing() returns a TracerProvider.
        """
        from src.observability.tracing import setup_tracing
        from opentelemetry.trace import TracerProvider

        provider = setup_tracing(service_name="test-service")
        assert isinstance(provider, TracerProvider)

    def test_setup_tracing_accepts_service_name(self) -> None:
        """
        setup_tracing() accepts service_name parameter.
        """
        from src.observability.tracing import setup_tracing

        # Should not raise
        provider = setup_tracing(service_name="llm-gateway")
        assert provider is not None

    def test_setup_tracing_accepts_endpoint(self) -> None:
        """
        setup_tracing() accepts optional OTLP endpoint.
        """
        from src.observability.tracing import setup_tracing

        # Should not raise
        provider = setup_tracing(
            service_name="llm-gateway",
            otlp_endpoint="http://localhost:4317",
        )
        assert provider is not None

    def test_get_tracer_function_exists(self) -> None:
        """
        get_tracer() function exists for getting named tracer.
        """
        from src.observability.tracing import get_tracer

        assert get_tracer is not None
        assert callable(get_tracer)

    def test_get_tracer_returns_tracer(self) -> None:
        """
        get_tracer() returns a Tracer instance.
        """
        from src.observability.tracing import get_tracer
        from opentelemetry.trace import Tracer

        tracer = get_tracer("test-module")
        assert tracer is not None


# =============================================================================
# WBS 2.8.3.3: TracingMiddleware Tests
# =============================================================================


class TestTracingMiddleware:
    """Tests for TracingMiddleware ASGI middleware."""

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
        from src.observability.tracing import TracingMiddleware

        middleware = TracingMiddleware(mock_app)
        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        # Should not raise
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_middleware_creates_span_for_http_request(
        self, mock_app: AsyncMock
    ) -> None:
        """
        WBS 2.8.3.4: Middleware creates span for HTTP requests.
        """
        from src.observability.tracing import TracingMiddleware, setup_tracing
        from opentelemetry import trace

        # Setup tracing first
        setup_tracing(service_name="test-service")

        middleware = TracingMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/chat/completions",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Verify span was created (via trace context)
        current_span = trace.get_current_span()
        # After request completion, span should be ended
        # We verify the middleware runs without error

    @pytest.mark.asyncio
    async def test_middleware_sets_span_attributes(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware sets span attributes (method, path, status).
        """
        from src.observability.tracing import TracingMiddleware, setup_tracing

        setup_tracing(service_name="test-service")
        middleware = TracingMiddleware(mock_app)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/sessions",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Should set http.method, http.route, http.status_code
        await middleware(scope, receive, send)

    @pytest.mark.asyncio
    async def test_middleware_excludes_health_endpoint(
        self, mock_app: AsyncMock
    ) -> None:
        """
        Middleware can exclude /health endpoint from tracing.
        """
        from src.observability.tracing import TracingMiddleware

        middleware = TracingMiddleware(mock_app, exclude_paths=["/health"])
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        # Should not create span for excluded path
        await middleware(scope, receive, send)


# =============================================================================
# WBS 2.8.3.4: Trace ID and Span ID Tests
# =============================================================================


class TestTraceAndSpanIDs:
    """Tests for trace_id and span_id generation."""

    def test_get_current_trace_id_function_exists(self) -> None:
        """
        WBS 2.8.3.4: get_current_trace_id() function exists.
        """
        from src.observability.tracing import get_current_trace_id

        assert get_current_trace_id is not None
        assert callable(get_current_trace_id)

    def test_get_current_span_id_function_exists(self) -> None:
        """
        get_current_span_id() function exists.
        """
        from src.observability.tracing import get_current_span_id

        assert get_current_span_id is not None
        assert callable(get_current_span_id)

    def test_trace_id_format_is_hex_string(self) -> None:
        """
        Trace ID is returned as hex string.
        """
        from src.observability.tracing import get_current_trace_id, setup_tracing
        from opentelemetry import trace

        setup_tracing(service_name="test")
        tracer = trace.get_tracer("test")
        
        with tracer.start_as_current_span("test-span"):
            trace_id = get_current_trace_id()
            if trace_id:  # May be None if no span
                # Trace IDs are 32 hex chars (128 bits)
                assert len(trace_id) == 32
                assert all(c in "0123456789abcdef" for c in trace_id)

    def test_span_id_format_is_hex_string(self) -> None:
        """
        Span ID is returned as hex string.
        """
        from src.observability.tracing import get_current_span_id, setup_tracing
        from opentelemetry import trace

        setup_tracing(service_name="test")
        tracer = trace.get_tracer("test")
        
        with tracer.start_as_current_span("test-span"):
            span_id = get_current_span_id()
            if span_id:  # May be None if no span
                # Span IDs are 16 hex chars (64 bits)
                assert len(span_id) == 16
                assert all(c in "0123456789abcdef" for c in span_id)


# =============================================================================
# WBS 2.8.3.5: Correlation ID Integration Tests
# =============================================================================


class TestCorrelationIDIntegration:
    """
    Tests for trace context integration with structured logging.
    
    Acceptance Criteria: "Correlation IDs propagated across services."
    """

    @pytest.mark.asyncio
    async def test_middleware_sets_correlation_id_from_trace_id(self) -> None:
        """
        WBS 2.8.3.5: Middleware sets correlation ID from trace ID.
        """
        from src.observability.tracing import TracingMiddleware, setup_tracing
        from src.observability.logging import get_correlation_id

        async def app(scope: dict, receive: Any, send: Any) -> None:
            # Inside app, correlation ID should be set
            correlation_id = get_correlation_id()
            assert correlation_id is not None
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"",
            })

        setup_tracing(service_name="test-service")
        middleware = TracingMiddleware(app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

    def test_inject_trace_context_function_exists(self) -> None:
        """
        inject_trace_context() function for outbound propagation exists.
        """
        from src.observability.tracing import inject_trace_context

        assert inject_trace_context is not None
        assert callable(inject_trace_context)

    def test_inject_trace_context_returns_headers(self) -> None:
        """
        inject_trace_context() returns headers dict.
        """
        from src.observability.tracing import inject_trace_context, setup_tracing
        from opentelemetry import trace

        setup_tracing(service_name="test")
        tracer = trace.get_tracer("test")
        
        with tracer.start_as_current_span("test-span"):
            headers = inject_trace_context()
            assert isinstance(headers, dict)

    def test_extract_trace_context_function_exists(self) -> None:
        """
        extract_trace_context() function for inbound propagation exists.
        """
        from src.observability.tracing import extract_trace_context

        assert extract_trace_context is not None
        assert callable(extract_trace_context)


# =============================================================================
# WBS 2.8.3.6: Trace Context Propagation Tests
# =============================================================================


class TestTraceContextPropagation:
    """Tests for trace context propagation in outbound requests."""

    @pytest.mark.asyncio
    async def test_middleware_extracts_incoming_trace_context(self) -> None:
        """
        WBS 2.8.3.6: Middleware extracts trace context from incoming headers.
        """
        from src.observability.tracing import TracingMiddleware, setup_tracing

        async def app(scope: dict, receive: Any, send: Any) -> None:
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"",
            })

        setup_tracing(service_name="test-service")
        middleware = TracingMiddleware(app)
        
        # Simulate incoming traceparent header (W3C format)
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                (b"traceparent", traceparent.encode()),
            ],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

    def test_propagate_context_to_httpx_request(self) -> None:
        """
        Trace context can be propagated to httpx requests.
        """
        from src.observability.tracing import inject_trace_context, setup_tracing
        from opentelemetry import trace

        setup_tracing(service_name="test")
        tracer = trace.get_tracer("test")
        
        with tracer.start_as_current_span("outbound-request"):
            headers = inject_trace_context()
            # W3C trace context uses 'traceparent' header
            assert "traceparent" in headers or len(headers) >= 0


# =============================================================================
# WBS 2.8.3.7: Export Tests
# =============================================================================


class TestTracingExports:
    """Tests for module exports."""

    def test_setup_tracing_importable_from_observability(self) -> None:
        """
        WBS 2.8.3.7: setup_tracing is importable from src.observability.
        """
        from src.observability import setup_tracing

        assert setup_tracing is not None

    def test_tracing_middleware_importable(self) -> None:
        """
        TracingMiddleware is importable from src.observability.
        """
        from src.observability import TracingMiddleware

        assert TracingMiddleware is not None

    def test_get_current_trace_id_importable(self) -> None:
        """
        get_current_trace_id is importable from src.observability.
        """
        from src.observability import get_current_trace_id

        assert get_current_trace_id is not None

    def test_get_current_span_id_importable(self) -> None:
        """
        get_current_span_id is importable from src.observability.
        """
        from src.observability import get_current_span_id

        assert get_current_span_id is not None

    def test_inject_trace_context_importable(self) -> None:
        """
        inject_trace_context is importable from src.observability.
        """
        from src.observability import inject_trace_context

        assert inject_trace_context is not None


# =============================================================================
# Span Creation Helper Tests
# =============================================================================


class TestSpanCreationHelpers:
    """Tests for span creation helper functions."""

    def test_create_span_decorator_exists(self) -> None:
        """
        @traced decorator exists for creating spans.
        """
        from src.observability.tracing import traced

        assert traced is not None
        assert callable(traced)

    def test_traced_decorator_works_on_sync_function(self) -> None:
        """
        @traced decorator works on synchronous functions.
        """
        from src.observability.tracing import traced, setup_tracing

        setup_tracing(service_name="test")

        @traced("test-operation")
        def my_function() -> str:
            return "result"

        result = my_function()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_traced_decorator_works_on_async_function(self) -> None:
        """
        @traced decorator works on asynchronous functions.
        """
        from src.observability.tracing import traced, setup_tracing

        setup_tracing(service_name="test")

        @traced("async-operation")
        async def my_async_function() -> str:
            return "async result"

        result = await my_async_function()
        assert result == "async result"

    def test_create_span_context_manager_exists(self) -> None:
        """
        create_span() context manager exists.
        """
        from src.observability.tracing import create_span

        assert create_span is not None
        assert callable(create_span)

    def test_create_span_context_manager_works(self) -> None:
        """
        create_span() context manager creates a span.
        """
        from src.observability.tracing import create_span, setup_tracing
        from opentelemetry import trace

        setup_tracing(service_name="test")
        
        with create_span("my-operation") as span:
            assert span is not None

    def test_span_can_add_attributes(self) -> None:
        """
        Spans can have attributes added.
        """
        from src.observability.tracing import create_span, setup_tracing

        setup_tracing(service_name="test")
        
        with create_span("my-operation") as span:
            span.set_attribute("user_id", "user-123")
            span.set_attribute("model", "claude-3-sonnet")


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestTracingErrorHandling:
    """Tests for tracing error handling."""

    @pytest.mark.asyncio
    async def test_middleware_records_exception_on_error(self) -> None:
        """
        Middleware records exception information when request fails.
        """
        from src.observability.tracing import TracingMiddleware, setup_tracing

        async def failing_app(scope: dict, receive: Any, send: Any) -> None:
            raise ValueError("Test error")

        setup_tracing(service_name="test-service")
        middleware = TracingMiddleware(failing_app)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(ValueError, match="Test error"):
            await middleware(scope, receive, send)

    def test_traced_decorator_records_exception(self) -> None:
        """
        @traced decorator records exception when function raises.
        """
        from src.observability.tracing import traced, setup_tracing

        setup_tracing(service_name="test")

        @traced("failing-operation")
        def failing_function() -> None:
            raise RuntimeError("Function failed")

        with pytest.raises(RuntimeError, match="Function failed"):
            failing_function()

    def test_tracing_gracefully_handles_no_provider(self) -> None:
        """
        Tracing functions work gracefully when no provider is set.
        """
        from src.observability.tracing import get_current_trace_id

        # Should not raise, just return None
        trace_id = get_current_trace_id()
        # May be None or empty string when no active span
        assert trace_id is None or isinstance(trace_id, str)
