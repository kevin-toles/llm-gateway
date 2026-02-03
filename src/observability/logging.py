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
- AC-LOG0.2: RotatingFileHandler for persistent logs
"""

import contextvars
import json
import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Generator, Optional, TextIO

import structlog
from structlog.types import EventDict, Processor


# =============================================================================
# WBS 2.8.1.1.16: Configuration State Flag (Issue 16)
# =============================================================================

_configured: bool = False
_file_logging_configured: bool = False


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
# AC-LOG0.2: File Logging Support
# =============================================================================


def _get_default_log_path() -> str:
    """Get platform-appropriate default log file path.
    
    Returns:
        macOS: ~/Library/Logs/ai-platform/llm-gateway/app.log
        Linux: /var/log/llm-gateway/app.log
    """
    if sys.platform == "darwin":
        home = Path.home()
        return str(home / "Library" / "Logs" / "ai-platform" / "llm-gateway" / "app.log")
    return "/var/log/llm-gateway/app.log"


class JSONFormatter(logging.Formatter):
    """JSON log formatter for file output (AC-LOG0.1)."""
    
    def __init__(self, service_name: str = "llm-gateway", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = get_correlation_id()
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "correlation_id": correlation_id if correlation_id else "-",
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


def _create_file_handler(
    log_file_path: str,
    service_name: str = "llm-gateway",
    max_bytes: int = 10_485_760,  # 10 MB
    backup_count: int = 5,
) -> RotatingFileHandler:
    """Create a rotating file handler for JSON logs (AC-LOG0.2)."""
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(JSONFormatter(service_name=service_name))
    return handler


def _setup_file_logging(log_level: int) -> None:
    """Set up file logging if enabled and not already configured."""
    global _file_logging_configured
    
    if _file_logging_configured:
        return
    
    enable_file_logging = os.environ.get("LLM_GATEWAY_ENABLE_FILE_LOGGING", "true").lower() in ("true", "1", "yes")
    
    if not enable_file_logging:
        _file_logging_configured = True
        return
    
    log_file_path = os.environ.get("LLM_GATEWAY_LOG_FILE_PATH") or _get_default_log_path()
    
    try:
        file_handler = _create_file_handler(log_file_path, "llm-gateway")
        file_handler.setLevel(log_level)
        # Add to root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        _file_logging_configured = True
    except (PermissionError, OSError) as e:
        print(f'{{"timestamp": "{datetime.now(timezone.utc).isoformat()}", "level": "WARNING", "service": "llm-gateway", "message": "File logging disabled: {e}"}}', file=sys.stderr)
        _file_logging_configured = True


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
    AC-LOG0.2: Uses stdlib integration for file logging support.
    
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
    
    log_level = _level_to_int(level)
    
    # Set up file logging first (AC-LOG0.2) - adds handler to root logger
    _setup_file_logging(log_level)
    
    # Configure stdlib logging with console handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Add console handler if not already present
    has_console = any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    if not has_console:
        console_handler = logging.StreamHandler(stream or sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(JSONFormatter(service_name="llm-gateway"))
        root_logger.addHandler(console_handler)
    
    # Configure structlog to use stdlib logging
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        add_correlation_id,
        rename_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    # Configure structlog to pass through to stdlib
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    _configured = True


def reset_logging() -> None:
    """
    Reset logging configuration state.
    
    WBS 2.8.1.1.16: Test utility to reset singleton state.
    
    WARNING: This should only be used in tests.
    """
    global _configured, _file_logging_configured
    _configured = False
    _file_logging_configured = False


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
