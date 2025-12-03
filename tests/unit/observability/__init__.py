"""
Tests for Structured Logging - WBS 2.8.1.1

TDD RED Phase: Tests for Logger Configuration.

Reference Documents:
- GUIDELINES pp. 2309-2319: Prometheus for metrics, structured logging
- GUIDELINES pp. 2319: Newman "log when timeouts occur"
- ARCHITECTURE.md: Line 30 - middleware/logging.py
- CODING_PATTERNS: logging.debug/warning/error with context

WBS Items Covered:
- 2.8.1.1.1: Create src/observability/__init__.py
- 2.8.1.1.2: Create src/observability/logging.py
- 2.8.1.1.3: Configure structlog with JSON formatter
- 2.8.1.1.4: Add timestamp, level, logger name processors
- 2.8.1.1.5: Add correlation ID processor
- 2.8.1.1.6: Configure based on LOG_LEVEL setting
- 2.8.1.1.7: Export get_logger() function
- 2.8.1.1.8: RED test: logger outputs JSON
- 2.8.1.1.9: GREEN: implement and pass test
"""

import io
import json
import sys
from typing import Any
from unittest.mock import patch

import pytest


# =============================================================================
# WBS 2.8.1.1.1-2: Package and Module Tests
# =============================================================================


class TestObservabilityPackage:
    """Tests for observability package structure."""

    def test_observability_package_importable(self) -> None:
        """
        WBS 2.8.1.1.1: observability package is importable.
        """
        from src import observability
        assert observability is not None

    def test_logging_module_importable(self) -> None:
        """
        WBS 2.8.1.1.2: logging module is importable.
        """
        from src.observability import logging as obs_logging
        assert obs_logging is not None


# =============================================================================
# WBS 2.8.1.1.3: JSON Formatter Tests
# =============================================================================


class TestJSONFormatter:
    """Tests for JSON log output."""

    def test_logger_outputs_json(self) -> None:
        """
        WBS 2.8.1.1.8: Logger outputs valid JSON.
        """
        from src.observability.logging import get_logger

        # Capture log output
        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("test message")

        output = captured.getvalue().strip()
        # Should be valid JSON
        log_entry = json.loads(output)
        assert "event" in log_entry
        assert log_entry["event"] == "test message"

    def test_log_entry_is_single_line(self) -> None:
        """
        JSON logs are single-line for easy parsing.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("test message")

        output = captured.getvalue()
        lines = [l for l in output.split("\n") if l.strip()]
        assert len(lines) == 1


# =============================================================================
# WBS 2.8.1.1.4: Timestamp, Level, Logger Name Tests
# =============================================================================


class TestLogProcessors:
    """Tests for log processors."""

    def test_log_includes_timestamp(self) -> None:
        """
        WBS 2.8.1.1.4: Logs include timestamp.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("test message")

        log_entry = json.loads(captured.getvalue().strip())
        assert "timestamp" in log_entry

    def test_log_includes_level(self) -> None:
        """
        WBS 2.8.1.1.4: Logs include log level.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("test message")

        log_entry = json.loads(captured.getvalue().strip())
        assert "level" in log_entry
        assert log_entry["level"] == "info"

    def test_log_includes_logger_name(self) -> None:
        """
        WBS 2.8.1.1.4: Logs include logger name.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("my_module", stream=captured)
        logger.info("test message")

        log_entry = json.loads(captured.getvalue().strip())
        assert "logger" in log_entry
        assert log_entry["logger"] == "my_module"

    def test_warning_level_captured(self) -> None:
        """
        Warning level is correctly captured.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.warning("warning message")

        log_entry = json.loads(captured.getvalue().strip())
        assert log_entry["level"] == "warning"

    def test_error_level_captured(self) -> None:
        """
        Error level is correctly captured.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.error("error message")

        log_entry = json.loads(captured.getvalue().strip())
        assert log_entry["level"] == "error"


# =============================================================================
# WBS 2.8.1.1.5: Correlation ID Tests
# =============================================================================


class TestCorrelationID:
    """Tests for correlation ID processor."""

    def test_log_includes_correlation_id_when_set(self) -> None:
        """
        WBS 2.8.1.1.5: Logs include correlation ID when in context.
        """
        from src.observability.logging import get_logger, set_correlation_id

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)

        set_correlation_id("req-12345")
        logger.info("test message")

        log_entry = json.loads(captured.getvalue().strip())
        assert "correlation_id" in log_entry
        assert log_entry["correlation_id"] == "req-12345"

    def test_log_omits_correlation_id_when_not_set(self) -> None:
        """
        Correlation ID is omitted when not set.
        """
        from src.observability.logging import get_logger, clear_correlation_id

        clear_correlation_id()

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("test message")

        log_entry = json.loads(captured.getvalue().strip())
        # correlation_id should not be present or be None
        assert log_entry.get("correlation_id") is None or "correlation_id" not in log_entry

    def test_correlation_id_context_manager(self) -> None:
        """
        Correlation ID context manager works correctly.
        """
        from src.observability.logging import (
            get_logger,
            correlation_id_context,
            clear_correlation_id,
        )

        clear_correlation_id()
        captured = io.StringIO()
        logger = get_logger("test", stream=captured)

        with correlation_id_context("ctx-abc"):
            logger.info("inside context")

        log_entry = json.loads(captured.getvalue().strip())
        assert log_entry["correlation_id"] == "ctx-abc"


# =============================================================================
# WBS 2.8.1.1.6: LOG_LEVEL Configuration Tests
# =============================================================================


class TestLogLevelConfiguration:
    """Tests for log level configuration."""

    def test_debug_level_logs_when_configured(self) -> None:
        """
        WBS 2.8.1.1.6: Debug logs appear when level is DEBUG.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured, level="DEBUG")
        logger.debug("debug message")

        output = captured.getvalue().strip()
        assert output  # Should have output
        log_entry = json.loads(output)
        assert log_entry["level"] == "debug"

    def test_debug_level_filtered_when_info(self) -> None:
        """
        Debug logs are filtered when level is INFO.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured, level="INFO")
        logger.debug("debug message")

        output = captured.getvalue().strip()
        assert output == ""  # Should be filtered


# =============================================================================
# WBS 2.8.1.1.7: Export Tests
# =============================================================================


class TestLoggerExports:
    """Tests for module exports."""

    def test_get_logger_importable_from_observability(self) -> None:
        """
        WBS 2.8.1.1.7: get_logger is importable from observability.
        """
        from src.observability import get_logger
        assert get_logger is not None

    def test_set_correlation_id_importable(self) -> None:
        """
        set_correlation_id is importable from observability.
        """
        from src.observability import set_correlation_id
        assert set_correlation_id is not None

    def test_clear_correlation_id_importable(self) -> None:
        """
        clear_correlation_id is importable from observability.
        """
        from src.observability import clear_correlation_id
        assert clear_correlation_id is not None

    def test_correlation_id_context_importable(self) -> None:
        """
        correlation_id_context is importable from observability.
        """
        from src.observability import correlation_id_context
        assert correlation_id_context is not None


# =============================================================================
# Additional Tests: Structured Data
# =============================================================================


class TestStructuredData:
    """Tests for structured log data."""

    def test_extra_fields_included_in_log(self) -> None:
        """
        Extra fields passed to logger are included.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("user action", user_id="user-123", action="login")

        log_entry = json.loads(captured.getvalue().strip())
        assert log_entry["user_id"] == "user-123"
        assert log_entry["action"] == "login"

    def test_exception_info_included(self) -> None:
        """
        Exception information is included when logging errors.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)

        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("caught exception")

        log_entry = json.loads(captured.getvalue().strip())
        assert "exception" in log_entry or "exc_info" in log_entry

    def test_nested_data_serialized(self) -> None:
        """
        Nested data structures are properly serialized.
        """
        from src.observability.logging import get_logger

        captured = io.StringIO()
        logger = get_logger("test", stream=captured)
        logger.info("request", request={"method": "POST", "path": "/api/chat"})

        log_entry = json.loads(captured.getvalue().strip())
        assert log_entry["request"]["method"] == "POST"
