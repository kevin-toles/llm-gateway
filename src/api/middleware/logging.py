"""
Request Logging Middleware - WBS 2.2.5.1

This module implements request/response logging middleware for the API.

Reference Documents:
- ARCHITECTURE.md line 30: logging.py - Request/response logging
- GUIDELINES: Sinha pp. 89-91 (FastAPI middleware patterns)
- ANTI_PATTERN_ANALYSIS: §3.1 No bare except clauses

WBS Items:
- 2.2.5.1.3: Implement request/response logging middleware
- 2.2.5.1.4: Log request method, path, duration
- 2.2.5.1.5: Log response status code
- 2.2.5.1.6: Redact sensitive headers (Authorization, API keys)
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# WBS 2.2.5.1.6: Sensitive Header Redaction
# Pattern: Security - never log credentials
# =============================================================================

# Headers that should be redacted (case-insensitive matching)
SENSITIVE_HEADER_PATTERNS = [
    "authorization",
    "api-key",
    "apikey",
    "x-api-key",
    "api_key",
    "x-auth-token",
    "cookie",
    "set-cookie",
]


def redact_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """
    Redact sensitive headers from a headers dictionary.

    WBS 2.2.5.1.6: Redact sensitive headers (Authorization, API keys).

    Pattern: Security - prevent credential leakage in logs

    Args:
        headers: Dictionary of HTTP headers

    Returns:
        Dictionary with sensitive values replaced with [REDACTED]
    """
    redacted = {}
    for key, value in headers.items():
        key_lower = key.lower()
        # Check if header name matches any sensitive pattern
        is_sensitive = any(
            pattern in key_lower for pattern in SENSITIVE_HEADER_PATTERNS
        )
        redacted[key] = "[REDACTED]" if is_sensitive else value
    return redacted


# =============================================================================
# WBS 2.2.5.1.3: Request Logging Middleware
# Pattern: ASGI middleware (Starlette/FastAPI)
# =============================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.

    WBS 2.2.5.1.3: Implement request/response logging middleware.

    Pattern: BaseHTTPMiddleware for request/response interception

    Features:
    - Logs request method, path, and client IP
    - Logs response status code
    - Calculates and logs request duration
    - Redacts sensitive headers from logs
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Process the request and log details.

        WBS 2.2.5.1.4: Log request method, path, duration.
        WBS 2.2.5.1.5: Log response status code.
        WBS 2.2.5.1.6: Redact sensitive headers.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from the handler
        """
        # Capture start time for duration calculation
        start_time = time.perf_counter()

        # Extract request details
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # Redact sensitive headers for logging
        headers_dict = dict(request.headers)
        redacted_headers = redact_sensitive_headers(headers_dict)

        # Log incoming request at DEBUG level (includes headers)
        logger.debug(
            f"Request: {method} {path} from {client_host} "
            f"headers={redacted_headers}"
        )

        # Process request through the chain
        try:
            response = await call_next(request)
        except Exception as e:
            # WBS ANTI_PATTERN §3.1: Log exception with context
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Request failed: {method} {path} from {client_host} "
                f"error={type(e).__name__}: {e} duration={duration_ms:.2f}ms"
            )
            raise

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log completed request
        # WBS 2.2.5.1.4: Log method, path, duration
        # WBS 2.2.5.1.5: Log status code
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            f"{method} {path} {response.status_code} "
            f"from {client_host} duration={duration_ms:.2f}ms",
        )

        return response
