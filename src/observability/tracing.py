"""
OpenTelemetry Tracing Module - WBS 2.8.3

This module provides distributed tracing via OpenTelemetry.

Reference Documents:
- GUIDELINES pp. 2309-2319: "observability framework encompassing metrics collection, 
  logging strategies, and cost tracking"
- GUIDELINES: "modern ML evaluation systems are not monolithic scripts but distributed 
  systems requiring careful attention to consistency, scalability, and observability"
- DEPLOYMENT_IMPL 1.6.1.2.3-5: Add opentelemetry-api, opentelemetry-sdk, 
  opentelemetry-instrumentation-fastapi
- Acceptance Criteria: "OpenTelemetry traces generated for requests. Correlation IDs 
  propagated across services."

Pattern: Distributed tracing for observability
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults

WBS Items:
- 2.8.3.1: Create src/observability/tracing.py
- 2.8.3.2: Configure TracerProvider with OTLP exporter
- 2.8.3.3: Create TracingMiddleware ASGI middleware
- 2.8.3.4: Generate trace_id and span_id for requests
- 2.8.3.5: Add trace context to structured logs (correlation)
- 2.8.3.6: Propagate trace context in outbound requests
- 2.8.3.7: Export setup_tracing() function
"""

import functools
import inspect
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer

from src.observability.logging import set_correlation_id, clear_correlation_id

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Global tracer provider reference
_tracer_provider: Optional[TracerProvider] = None


# =============================================================================
# WBS 2.8.3.2: TracerProvider Configuration
# =============================================================================


def setup_tracing(
    service_name: str = "llm-gateway",
    otlp_endpoint: Optional[str] = None,
) -> TracerProvider:
    """
    Configure OpenTelemetry TracerProvider.

    WBS 2.8.3.2: Configure TracerProvider with OTLP exporter.
    WBS 2.8.3.7: Export setup_tracing() function.

    Args:
        service_name: Name of the service for resource identification
        otlp_endpoint: Optional OTLP exporter endpoint (http://localhost:4317)

    Returns:
        Configured TracerProvider
    """
    global _tracer_provider

    # Create resource with service name
    resource = Resource.create({SERVICE_NAME: service_name})

    # Create provider
    provider = TracerProvider(resource=resource)

    # Configure exporter
    if otlp_endpoint:
        # Use OTLP exporter if endpoint provided
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        except ImportError:
            # Fall back to console if OTLP not available
            exporter = ConsoleSpanExporter()
    else:
        # Use console exporter for development/testing
        exporter = ConsoleSpanExporter()

    # Add batch processor for efficiency
    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global provider
    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    return provider


def get_tracer(name: str = __name__) -> Tracer:
    """
    Get a named tracer instance.

    Args:
        name: Name for the tracer (typically module name)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


# =============================================================================
# WBS 2.8.3.4: Trace ID and Span ID Functions
# =============================================================================


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID as hex string.

    WBS 2.8.3.4: Generate trace_id and span_id for requests.

    Returns:
        32-character hex string or None if no active span
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    
    if span_context.trace_id == 0:
        return None
    
    return format(span_context.trace_id, "032x")


def get_current_span_id() -> Optional[str]:
    """
    Get the current span ID as hex string.

    Returns:
        16-character hex string or None if no active span
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    
    if span_context.span_id == 0:
        return None
    
    return format(span_context.span_id, "016x")


# =============================================================================
# WBS 2.8.3.5-6: Context Propagation
# =============================================================================


def inject_trace_context(headers: Optional[dict[str, str]] = None) -> dict[str, str]:
    """
    Inject trace context into headers for outbound requests.

    WBS 2.8.3.6: Propagate trace context in outbound requests.

    Args:
        headers: Existing headers dict to inject into (optional)

    Returns:
        Headers dict with trace context injected
    """
    carrier = headers if headers is not None else {}
    inject(carrier)
    return carrier


def extract_trace_context(headers: dict[str, Any]) -> Context:
    """
    Extract trace context from incoming headers.

    Args:
        headers: Headers dict (e.g., from ASGI scope)

    Returns:
        Context with extracted trace information
    """
    return extract(headers)


def _headers_to_dict(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """Convert ASGI headers to dict for propagation."""
    return {
        key.decode("utf-8").lower(): value.decode("utf-8")
        for key, value in headers
    }


# =============================================================================
# WBS 2.8.3.3: TracingMiddleware
# =============================================================================


class TracingMiddleware:
    """
    ASGI middleware for OpenTelemetry tracing.

    WBS 2.8.3.3: Create TracingMiddleware ASGI middleware.

    This middleware:
    - Creates spans for HTTP requests
    - Sets span attributes (method, path, status)
    - Integrates with correlation ID logging
    - Extracts/propagates trace context
    """

    def __init__(
        self,
        app: Callable[..., Any],
        exclude_paths: Optional[list[str]] = None,
        tracer_name: str = "llm_gateway.http",
    ) -> None:
        """
        Initialize TracingMiddleware.

        Args:
            app: ASGI application to wrap
            exclude_paths: Paths to exclude from tracing
            tracer_name: Name for the tracer
        """
        self.app = app
        self.exclude_paths = exclude_paths or []
        self.tracer = get_tracer(tracer_name)

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
        path = scope.get("path", "/")

        # Skip excluded paths
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        # Extract context from incoming headers
        headers = scope.get("headers", [])
        headers_dict = _headers_to_dict(headers)
        parent_context = extract_trace_context(headers_dict)

        # Create span name
        span_name = f"{method} {path}"
        status_code = 500  # Default if not captured

        # Wrapper to capture status code
        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        # Start span with parent context
        with self.tracer.start_as_current_span(
            span_name,
            context=parent_context,
            kind=SpanKind.SERVER,
        ) as span:
            # WBS 2.8.3.5: Set correlation ID from trace ID
            trace_id = get_current_trace_id()
            if trace_id:
                set_correlation_id(trace_id)

            # Set span attributes
            span.set_attribute("http.method", method)
            span.set_attribute("http.route", path)
            span.set_attribute("http.url", path)

            try:
                await self.app(scope, receive, send_wrapper)
                span.set_attribute("http.status_code", status_code)
                
                if status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR))
                else:
                    span.set_status(Status(StatusCode.OK))
                    
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                clear_correlation_id()


# =============================================================================
# Span Creation Helpers
# =============================================================================


@contextmanager
def create_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
) -> Generator[Span, None, None]:
    """
    Context manager for creating a span.

    Args:
        name: Span name
        attributes: Optional span attributes

    Yields:
        Active span
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def traced(name: str) -> Callable[[F], F]:
    """
    Decorator for creating spans around functions.

    Args:
        name: Span name

    Returns:
        Decorator function

    Example:
        >>> @traced("process-request")
        ... def process_request(data):
        ...     return data
    """
    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                with tracer.start_as_current_span(name) as span:
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                with tracer.start_as_current_span(name) as span:
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            return sync_wrapper  # type: ignore
    return decorator
