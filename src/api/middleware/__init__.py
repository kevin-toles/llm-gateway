"""
API Middleware Package - WBS 2.2.5

This package contains middleware components for the LLM Gateway API.

Reference Documents:
- ARCHITECTURE.md lines 26-30: Middleware structure
- GUIDELINES: Sinha pp. 89-91 (FastAPI middleware patterns)

Middleware Components:
- logging: Request/response logging with header redaction
- rate_limit: Token bucket/sliding window rate limiting
- auth: API key validation (optional)
"""

from src.api.middleware.logging import RequestLoggingMiddleware, redact_sensitive_headers
from src.api.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimiter,
    InMemoryRateLimiter,
    RateLimitResult,
)

__all__ = [
    # Logging
    "RequestLoggingMiddleware",
    "redact_sensitive_headers",
    # Rate Limiting
    "RateLimitMiddleware",
    "RateLimiter",
    "InMemoryRateLimiter",
    "RateLimitResult",
]
