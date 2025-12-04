"""
Structured Logging Module - WBS 2.8.1.1

This module provides structured JSON logging with correlation ID support.

Reference Documents:
- GUIDELINES pp. 2309-2319: "Prometheus for metrics collection and structured logging"
- GUIDELINES pp. 2319: Newman "log when timeouts occur, look at what happens"
- CODING_PATTERNS: logging.debug/warning/error with context

Pattern: Structured logging for observability
Pattern: Singleton configuration (configure once at startup)
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults

WBS Items:
- 2.8.1.1.2: Create src/observability/logging.py
- 2.8.1.1.3: Configure structlog with JSON formatter
- 2.8.1.1.4: Add timestamp, level, logger name processors
- 2.8.1.1.5: Add correlation ID processor
- 2.8.1.1.6: Configure based on LOG_LEVEL setting
- 2.8.1.1.7: Export get_logger() function
- 2.8.1.1.16: Singleton configuration pattern (Issue 16)
"""

import contextvars
import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional, TextIO

import structlog
from structlog.types import EventDict, Processor


# =============================================================================
# WBS 2.8.1.1.16: Configuration State Flag (Issue 16)
# =============================================================================

_configured: bool = False


# =============================================================================
# Correlation ID Context - WBS 2.8.1.1.5
# =============================================================================

_correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.

    Args:
        correlation_id: Unique identifier for request tracing
    """
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID.

    Returns:
        Correlation ID if set, None otherwise
    """
    return _correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID for the current context."""
    _correlation_id_var.set(None)


@contextmanager
def correlation_id_context(correlation_id: str) -> Generator[None, None, None]:
    """
    Context manager for setting correlation ID.

    Args:
        correlation_id: Unique identifier for request tracing

    Yields:
        None

    Example:
        >>> with correlation_id_context("req-12345"):
        ...     logger.info("processing request")
    """
    token = _correlation_id_var.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id_var.reset(token)


# =============================================================================
# Custom Processors - WBS 2.8.1.1.4-5
# =============================================================================


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Add correlation ID to log event if set.

    WBS 2.8.1.1.5: Add correlation ID processor.
    """
    correlation_id = get_correlation_id()
    if correlation_id is not None:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_timestamp(
    logger: logging.Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Add ISO 8601 timestamp to log event.

    WBS 2.8.1.1.4: Add timestamp processor.
    
    Args:
        logger: The logger instance (unused but required by structlog interface)
        _method_name: The log method name (unused but required by structlog interface)
        event_dict: The event dictionary to process
    """
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_logger_name(
    logger: logging.Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Add logger name to log event.

    WBS 2.8.1.1.4: Add logger name processor.
    
    Args:
        logger: The logger instance
        _method_name: The log method name (unused but required by structlog interface)
        event_dict: The event dictionary to process
    """
    # Logger name is stored as _logger in bound logger
    if hasattr(logger, "name"):
        event_dict["logger"] = logger.name
    return event_dict


def rename_level(
    logger: logging.Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Rename log_level to level for cleaner output.
    
    Args:
        logger: The logger instance (unused but required by structlog interface)
        _method_name: The log method name (unused but required by structlog interface)
        event_dict: The event dictionary to process
    """
    if "log_level" in event_dict:
        event_dict["level"] = event_dict.pop("log_level")
    return event_dict


# =============================================================================
# WBS 2.8.1.1.16: Singleton Configuration (Issue 16)
# =============================================================================


def configure_logging(
    level: str = "INFO",
    stream: Optional[TextIO] = None,
    force: bool = False,
) -> None:
    """
    Configure structlog for the application.
    
    WBS 2.8.1.1.16: Singleton configuration function.
    
    This should be called once at application startup. Subsequent calls
    are no-ops to avoid reconfiguration overhead, unless force=True.
    
    Args:
        level: Default log level (DEBUG, INFO, WARNING, ERROR)
        stream: Output stream (default: sys.stdout)
        force: Force reconfiguration (for testing only)
    
    Example:
        >>> # In application startup (e.g., main.py)
        >>> configure_logging(level="DEBUG")
        >>> logger = get_logger("my_module")
    """
    global _configured
    
    if _configured and not force:
        return
    
    # Configure processors
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        add_timestamp,
        add_correlation_id,
        rename_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog once
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            _level_to_int(level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,  # Allow different loggers per call
    )
    
    _configured = True


def reset_logging() -> None:
    """
    Reset logging configuration state.
    
    WBS 2.8.1.1.16: Test utility to reset singleton state.
    
    WARNING: This should only be used in tests.
    """
    global _configured
    _configured = False


# =============================================================================
# WBS 2.8.1.1.7: Logger Factory
# =============================================================================


def get_logger(
    name: str,
    stream: Optional[TextIO] = None,
    level: str = "INFO",
) -> structlog.BoundLogger:
    """
    Get a configured structured logger.

    WBS 2.8.1.1.7: Export get_logger() function.
    WBS 2.8.1.1.16: Uses singleton configuration pattern.

    Args:
        name: Logger name (typically module name)
        stream: Output stream (default: sys.stdout) - used for initial config
        level: Log level (DEBUG, INFO, WARNING, ERROR) - used for initial config

    Returns:
        Configured structlog BoundLogger

    Example:
        >>> logger = get_logger("my_module")
        >>> logger.info("user logged in", user_id="123")
    """
    # Auto-configure if not already configured (for convenience)
    # Pass through stream and level for initial configuration
    configure_logging(level=level, stream=stream)

    # Create logger with name bound as context
    return structlog.get_logger().bind(logger=name)


def _level_to_int(level: str) -> int:
    """Convert level string to logging int."""
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(level.upper(), logging.INFO)
