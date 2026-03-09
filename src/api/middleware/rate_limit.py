"""
Rate Limiting Middleware - WBS 2.2.5.2

This module implements rate limiting middleware using a token bucket algorithm.

Reference Documents:
- ARCHITECTURE.md line 29: rate_limit.py - Request rate limiting
- ARCHITECTURE.md line 221: Rate limiting per client
- GUIDELINES: Token bucket algorithm for rate limiting
- GUIDELINES §2309: Connection pooling and bulkhead patterns for resource isolation
- ANTI_PATTERN_ANALYSIS: §3.1 No bare except clauses

WBS Items:
- 2.2.5.2.2: Implement token bucket or sliding window algorithm
- 2.2.5.2.3: Use Redis for distributed rate limiting (stub provided)
- 2.2.5.2.4: Configure limits from settings
- 2.2.5.2.5: Return 429 when limit exceeded
- 2.2.5.2.6: Add X-RateLimit-* headers to responses
- 2.2.5.2.9: Thread-safe token bucket with per-client locking
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limit Result - WBS 2.2.5.2.6
# =============================================================================


@dataclass
class RateLimitResult:
    """
    Result of a rate limit check.

    WBS 2.2.5.2.6: Contains data for X-RateLimit-* headers.

    Attributes:
        allowed: Whether the request is allowed
        limit: Maximum requests per window
        remaining: Remaining requests in current window
        reset_at: Unix timestamp when the window resets
        retry_after: Seconds to wait before retrying (if blocked)
    """

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: Optional[int] = None


# =============================================================================
# Rate Limiter Interface - WBS 2.2.5.2.2
# Pattern: Strategy pattern for algorithm selection
# =============================================================================


class RateLimiter(ABC):
    """
    Abstract interface for rate limiting algorithms.

    WBS 2.2.5.2.2: Implement token bucket or sliding window algorithm.

    Pattern: Strategy pattern - allows swapping algorithms (token bucket, sliding window)

    Implementations:
    - InMemoryRateLimiter: For single-instance deployments
    - RedisRateLimiter: For distributed deployments (WBS 2.2.5.2.3)
    """

    @abstractmethod
    async def is_allowed(self, client_id: str) -> RateLimitResult:
        """
        Check if a request from client_id is allowed.

        Args:
            client_id: Unique identifier for the client (IP, API key, etc.)

        Returns:
            RateLimitResult with allowed status and rate limit info
        """
        pass


# =============================================================================
# In-Memory Rate Limiter - Token Bucket Implementation
# =============================================================================


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory rate limiter using token bucket algorithm.

    WBS 2.2.5.2.2: Token bucket implementation.
    WBS 2.2.5.2.4: Configure limits from settings.
    WBS 2.2.5.2.9: Thread-safe with per-client asyncio.Lock.

    Pattern: Token bucket algorithm with per-client locking
    - Tokens are added at a fixed rate (requests_per_minute / 60 per second)
    - Each request consumes one token
    - Burst allows temporary spikes above the rate
    - Per-client locks prevent read-modify-write race conditions

    Reference: GUIDELINES §2309 - Newman bulkhead pattern recommends
    "using different connection pools for each downstream service"
    to prevent resource exhaustion. We apply the same principle here
    with per-client locks.

    Note: This implementation is suitable for single-instance deployments.
    For distributed deployments, use RedisRateLimiter.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        """
        Initialize the rate limiter.

        WBS 2.2.5.2.4: Configure limits from settings.

        Args:
            requests_per_minute: Sustained request rate limit
            burst: Maximum burst size (token bucket capacity)
        """
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._refill_rate = requests_per_minute / 60.0  # tokens per second
        self._buckets: dict[str, tuple[float, float]] = {}  # client_id -> (tokens, last_update)
        self._locks: dict[str, asyncio.Lock] = {}  # Per-client locks for thread safety
        self._global_lock = asyncio.Lock()  # Lock for creating new client locks

    def _get_lock(self, client_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific client.
        
        WBS 2.2.5.2.9: Per-client locking for thread safety.
        
        Args:
            client_id: Client identifier
            
        Returns:
            asyncio.Lock for the client
        """
        if client_id not in self._locks:
            self._locks[client_id] = asyncio.Lock()
        return self._locks[client_id]

    async def is_allowed(self, client_id: str) -> RateLimitResult:
        """
        Check if request is allowed using token bucket algorithm.

        WBS 2.2.5.2.7: Allow requests within limit.
        WBS 2.2.5.2.8: Block requests exceeding limit.
        WBS 2.2.5.2.9: Thread-safe with per-client locking.

        Args:
            client_id: Client identifier (IP, API key, etc.)

        Returns:
            RateLimitResult with rate limit status
        """
        # Get or create lock for this client (brief global lock)
        async with self._global_lock:
            lock = self._get_lock(client_id)
        
        # Per-client lock prevents race conditions on bucket access
        async with lock:
            now = time.time()
            window_duration = 60  # 1 minute window

            # Get or create bucket for client
            if client_id in self._buckets:
                tokens, last_update = self._buckets[client_id]
            else:
                tokens = float(self.burst)
                last_update = now

            # Refill tokens based on time elapsed
            elapsed = now - last_update
            tokens = min(self.burst, tokens + elapsed * self._refill_rate)

            # Calculate reset time (when bucket would be full)
            tokens_needed = self.burst - tokens
            if tokens_needed > 0:
                reset_at = int(now + tokens_needed / self._refill_rate)
            else:
                reset_at = int(now + window_duration)

            # Check if request is allowed
            if tokens >= 1:
                # Consume a token
                tokens -= 1
                self._buckets[client_id] = (tokens, now)

                return RateLimitResult(
                    allowed=True,
                    limit=self.requests_per_minute,
                    remaining=int(tokens),
                    reset_at=reset_at,
                )
            else:
                # Rate limited
                retry_after = int((1 - tokens) / self._refill_rate) + 1
                self._buckets[client_id] = (tokens, now)

                return RateLimitResult(
                    allowed=False,
                    limit=self.requests_per_minute,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )


# =============================================================================
# Rate Limit Middleware - WBS 2.2.5.2.1
# =============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting requests.

    WBS 2.2.5.2.1: Rate limiting middleware.
    WBS 2.2.5.2.5: Return 429 when limit exceeded.
    WBS 2.2.5.2.6: Add X-RateLimit-* headers to responses.

    Pattern: BaseHTTPMiddleware for request interception

    Features:
    - Configurable rate limiter (strategy pattern)
    - X-RateLimit-* headers on all responses
    - 429 Too Many Requests when limit exceeded
    - Retry-After header on 429 responses
    """

    def __init__(self, app, rate_limiter: RateLimiter):
        """
        Initialize the middleware.

        Args:
            app: FastAPI/Starlette application
            rate_limiter: RateLimiter implementation to use
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter

    def _get_client_id(self, request: Request) -> str:
        """
        Extract client identifier from request.

        Uses X-Forwarded-For if behind proxy, otherwise client IP.

        Args:
            request: HTTP request

        Returns:
            Client identifier string
        """
        # Check for forwarded header (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain
            return forwarded.split(",")[0].strip()

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request through rate limiter.

        WBS 2.2.5.2.5: Return 429 when limit exceeded.
        WBS 2.2.5.2.6: Add X-RateLimit-* headers.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler

        Returns:
            Response with rate limit headers
        """
        client_id = self._get_client_id(request)

        # Check rate limit
        result = await self.rate_limiter.is_allowed(client_id)

        if not result.allowed:
            # WBS 2.2.5.2.5: Return 429 when limit exceeded
            logger.warning(
                f"Rate limit exceeded for client {client_id}: "
                f"limit={result.limit}, reset_at={result.reset_at}"
            )

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry later."},
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(result.reset_at),
                    "Retry-After": str(result.retry_after or 60),
                },
            )

        # Process request
        response = await call_next(request)

        # WBS 2.2.5.2.6: Add X-RateLimit-* headers to all responses
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)

        return response
