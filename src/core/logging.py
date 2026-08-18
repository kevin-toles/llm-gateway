"""Structured logging module for llm-gateway service.

WBS-LOG0: Structured Logging Implementation

This module provides:
- AC-LOG0.1: JSONFormatter with timestamp, level, service, correlation_id, module, message
- AC-LOG0.2: RotatingFileHandler writing to /var/log/llm-gateway/app.log
- AC-LOG0.3: CorrelationIdFilter for X-Request-ID propagation
- AC-LOG0.4: Log level configurable via LLM_GATEWAY_LOG_LEVEL env var
"""

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


# Context variable for correlation ID propagation (AC-LOG0.3)
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current request context."""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID from context."""
    _correlation_id.set(None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter with standard fields (AC-LOG0.1)."""
    
    def __init__(self, service_name: str = "llm-gateway", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, "correlation_id", "-")
        
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "correlation_id": correlation_id,
            "module": record.module,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation ID to log records (AC-LOG0.3)."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id if correlation_id else "-"
        return True


def get_log_level_from_env(service_prefix: str = "LLM_GATEWAY") -> int:
    """Get log level from LLM_GATEWAY_LOG_LEVEL env var (AC-LOG0.4)."""
    env_var = f"{service_prefix}_LOG_LEVEL"
    level_str = os.environ.get(env_var, "INFO").upper()
    level = getattr(logging, level_str, None)
    return level if isinstance(level, int) else logging.INFO


def _get_default_log_path() -> str:
    """Get platform-appropriate default log file path.
    
    Returns:
        macOS: ~/Library/Logs/ai-platform/llm-gateway/app.log
        Linux: /var/log/llm-gateway/app.log
    """
    if sys.platform == "darwin":
        from pathlib import Path
        home = Path.home()
        return str(home / "Library" / "Logs" / "ai-platform" / "llm-gateway" / "app.log")
    return "/var/log/llm-gateway/app.log"


def create_file_handler(
    log_file_path: str = "/var/log/llm-gateway/app.log",
    service_name: str = "llm-gateway",
    max_bytes: int = 10_485_760,
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
    handler.addFilter(CorrelationIdFilter())
    return handler


def setup_structured_logging(
    service_name: str = "llm-gateway",
    log_file_path: str | None = None,
    log_level: int | None = None,
    enable_file_logging: bool | None = None,
) -> logging.Logger:
    """Set up structured logging with optional file handler.
    
    Args:
        service_name: Service name for log identification.
        log_file_path: Path for log file. Defaults from env or platform-appropriate location.
        log_level: Log level. Defaults from LLM_GATEWAY_LOG_LEVEL env var.
        enable_file_logging: Enable file logging. Defaults from LLM_GATEWAY_ENABLE_FILE_LOGGING env var.
    """
    if log_level is None:
        log_level = get_log_level_from_env()
    
    logger = logging.getLogger(service_name)
    logger.setLevel(log_level)
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter(service_name=service_name))
    console_handler.addFilter(CorrelationIdFilter())
    logger.addHandler(console_handler)
    
    # Determine if file logging is enabled
    if enable_file_logging is None:
        enable_file_logging = os.environ.get("LLM_GATEWAY_ENABLE_FILE_LOGGING", "true").lower() in ("true", "1", "yes")
    
    # File handler
    if enable_file_logging:
        if log_file_path is None:
            log_file_path = os.environ.get("LLM_GATEWAY_LOG_FILE_PATH") or _get_default_log_path()
        try:
            file_handler = create_file_handler(log_file_path, service_name)
            file_handler.setLevel(log_level)
            logger.addHandler(file_handler)
        except OSError as e:
            logger.warning(f"Cannot write to {log_file_path}, file logging disabled: {e}")
    
    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name or "llm-gateway")
