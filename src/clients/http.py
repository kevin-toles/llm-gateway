"""
HTTP Client Module - WBS 2.7.1.1 Client Factory

This module provides HTTP client factory functionality with proper
connection pooling, timeouts, and retry configuration.

Reference Documents:
- ARCHITECTURE.md: Microservice URLs configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service (Newman)
- GUIDELINES pp. 2145: Connection pooling, graceful degradation, circuit breakers
- GUIDELINES pp. 2319: Timeout configuration and logging

Pattern: Factory pattern for creating configured HTTP clients
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults
"""

from typing import Optional

import httpx


# =============================================================================
# Custom Exceptions - WBS 2.7.1.1
# =============================================================================


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""

    pass


# =============================================================================
# Default Configuration Constants - WBS 2.7.1.1.4-6
# Pattern: Connection pooling per downstream service (GUIDELINES pp. 2309)
# =============================================================================


DEFAULT_TIMEOUT_SECONDS: float = 30.0
"""Default timeout for HTTP requests in seconds.

Reference: GUIDELINES pp. 2319 - Newman's guidance on timeout configuration.
"""

DEFAULT_MAX_CONNECTIONS: int = 100
"""Maximum number of connections in the pool.

Reference: GUIDELINES pp. 2309 - "different connection pools for each downstream 
service" to prevent resource exhaustion.
"""

DEFAULT_MAX_KEEPALIVE: int = 20
"""Maximum number of keepalive connections.

Pattern: Bulkhead pattern - connection isolation
Reference: GUIDELINES pp. 2313 - Newman Building Microservices pp. 359-360
"""

DEFAULT_RETRY_COUNT: int = 3
"""Default number of retries for failed requests.

Pattern: Retry with exponential backoff
Reference: GUIDELINES pp. 1224 - retry logic for LLM API calls
"""


# =============================================================================
# WBS 2.7.1.1.3: HTTP Client Factory
# =============================================================================


def create_http_client(
    base_url: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    max_connections: Optional[int] = None,
    max_keepalive: Optional[int] = None,
    retries: Optional[int] = None,
    headers: Optional[dict[str, str]] = None,
) -> httpx.AsyncClient:
    """
    Create a configured HTTP client with connection pooling and timeouts.

    WBS 2.7.1.1.3: Implement create_http_client() factory.

    This factory creates an httpx.AsyncClient with:
    - Connection pooling (WBS 2.7.1.1.4)
    - Configurable timeouts (WBS 2.7.1.1.5)
    - Retry support (WBS 2.7.1.1.6)

    Pattern: Factory pattern for HTTP client creation
    Reference: GUIDELINES pp. 2309 - connection pools per downstream service

    Args:
        base_url: Base URL for all requests (e.g., "http://localhost:8081")
        timeout_seconds: Request timeout in seconds (default: 30.0)
        max_connections: Maximum connections in pool (default: 100)
        max_keepalive: Maximum keepalive connections (default: 20)
        retries: Number of retries for failed requests (default: 3)
        headers: Additional headers to include in all requests

    Returns:
        httpx.AsyncClient: Configured async HTTP client

    Example:
        >>> client = create_http_client(
        ...     base_url="http://semantic-search:8081",
        ...     timeout_seconds=60.0,
        ...     retries=3,
        ... )
        >>> async with client:
        ...     response = await client.get("/search")
    """
    # Apply defaults
    timeout = timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS
    max_conn = max_connections if max_connections is not None else DEFAULT_MAX_CONNECTIONS
    max_keep = max_keepalive if max_keepalive is not None else DEFAULT_MAX_KEEPALIVE
    retry_count = retries if retries is not None else DEFAULT_RETRY_COUNT

    # Configure connection limits (WBS 2.7.1.1.4)
    # Pattern: Bulkhead - separate pools prevent resource exhaustion
    limits = httpx.Limits(
        max_connections=max_conn,
        max_keepalive_connections=max_keep,
    )

    # Configure timeout (WBS 2.7.1.1.5)
    # Pattern: Timeouts prevent cascading failures
    timeout_config = httpx.Timeout(
        connect=timeout,
        read=timeout,
        write=timeout,
        pool=timeout,
    )

    # Build default headers
    default_headers = {
        "User-Agent": "llm-gateway/1.0",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)

    # Configure retry transport (WBS 2.7.1.1.6)
    # Note: httpx transport retries are for connection-level retries
    transport = httpx.AsyncHTTPTransport(
        retries=retry_count,
        limits=limits,  # Pass limits to transport
    )

    # Create client
    client = httpx.AsyncClient(
        base_url=base_url or "",
        timeout=timeout_config,
        headers=default_headers,
        transport=transport,
    )

    return client
