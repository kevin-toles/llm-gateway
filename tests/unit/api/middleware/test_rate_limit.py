"""
Tests for Rate Limiting Middleware - WBS 2.2.5.2

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- ARCHITECTURE.md line 29: rate_limit.py - Request rate limiting
- ARCHITECTURE.md line 221: Rate limiting per client
- GUIDELINES: Token bucket algorithm for rate limiting
- ANTI_PATTERN_ANALYSIS: §3.1 No bare except clauses

WBS Items Covered:
- 2.2.5.2.2: Implement token bucket or sliding window algorithm
- 2.2.5.2.3: Use Redis for distributed rate limiting (stub for unit tests)
- 2.2.5.2.4: Configure limits from settings
- 2.2.5.2.5: Return 429 when limit exceeded
- 2.2.5.2.6: Add X-RateLimit-* headers to responses
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

# RED Phase: These imports will fail until implementation
from src.api.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimiter,
    InMemoryRateLimiter,
)


class TestRateLimitMiddleware:
    """Test suite for rate limiting middleware - WBS 2.2.5.2"""

    # =========================================================================
    # WBS 2.2.5.2.1: Middleware Structure
    # =========================================================================

    def test_rate_limit_middleware_exists(self):
        """
        WBS 2.2.5.2.1: RateLimitMiddleware class must exist.
        """
        assert callable(RateLimitMiddleware)

    def test_rate_limiter_interface_exists(self):
        """
        WBS 2.2.5.2.2: RateLimiter abstract interface must exist.

        Pattern: Strategy pattern for algorithm selection
        """
        assert callable(RateLimiter)

    # =========================================================================
    # WBS 2.2.5.2.7: Requests Within Limit Succeed
    # =========================================================================

    def test_requests_within_limit_return_200(self, client: TestClient):
        """
        WBS 2.2.5.2.7: Requests within rate limit should succeed.
        """
        response = client.get("/test")
        assert response.status_code == 200

    def test_first_request_always_succeeds(self, client: TestClient):
        """
        WBS 2.2.5.2.7: First request should always succeed.
        """
        response = client.get("/test")
        assert response.status_code == 200

    # =========================================================================
    # WBS 2.2.5.2.8: Requests Exceeding Limit Return 429
    # =========================================================================

    def test_requests_exceeding_limit_return_429(self, client_low_limit: TestClient):
        """
        WBS 2.2.5.2.8: Requests exceeding limit should return 429.

        Pattern: Token bucket rate limiting
        """
        # Make requests until limit is exceeded (limit is 2)
        client_low_limit.get("/test")  # 1st request
        client_low_limit.get("/test")  # 2nd request
        response = client_low_limit.get("/test")  # 3rd request - should be limited

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_429_response_has_error_detail(self, client_low_limit: TestClient):
        """
        WBS 2.2.5.2.5: 429 response should include error detail.
        """
        # Exhaust the limit
        for _ in range(3):
            response = client_low_limit.get("/test")

        data = response.json()
        assert "detail" in data
        assert "rate limit" in data["detail"].lower()

    # =========================================================================
    # WBS 2.2.5.2.6: X-RateLimit-* Headers
    # =========================================================================

    def test_response_includes_rate_limit_headers(self, client: TestClient):
        """
        WBS 2.2.5.2.6: Response must include X-RateLimit-* headers.
        """
        response = client.get("/test")

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_remaining_decrements(self, client: TestClient):
        """
        WBS 2.2.5.2.6: X-RateLimit-Remaining should decrement.
        """
        response1 = client.get("/test")
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        response2 = client.get("/test")
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        assert remaining2 < remaining1

    def test_429_includes_retry_after_header(self, client_low_limit: TestClient):
        """
        WBS 2.2.5.2.6: 429 response should include Retry-After header.
        """
        # Exhaust the limit
        for _ in range(3):
            response = client_low_limit.get("/test")

        assert response.status_code == 429
        assert "Retry-After" in response.headers

    # =========================================================================
    # WBS 2.2.5.2.4: Configure Limits from Settings
    # =========================================================================

    def test_rate_limit_configurable(self):
        """
        WBS 2.2.5.2.4: Rate limit should be configurable.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=100, burst=20)
        assert limiter.requests_per_minute == 100
        assert limiter.burst == 20


class TestInMemoryRateLimiter:
    """Test suite for in-memory rate limiter - WBS 2.2.5.2"""

    def test_in_memory_limiter_exists(self):
        """
        WBS 2.2.5.2.2: InMemoryRateLimiter implementation must exist.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        assert isinstance(limiter, RateLimiter)

    @pytest.mark.asyncio
    async def test_limiter_allows_within_limit(self):
        """
        WBS 2.2.5.2.7: Limiter should allow requests within limit.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        result = await limiter.is_allowed("test-client")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_limiter_blocks_exceeding_limit(self):
        """
        WBS 2.2.5.2.8: Limiter should block requests exceeding limit.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=2)

        # Exhaust burst limit
        await limiter.is_allowed("test-client")
        await limiter.is_allowed("test-client")
        result = await limiter.is_allowed("test-client")

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_limiter_returns_remaining_tokens(self):
        """
        WBS 2.2.5.2.6: Limiter should return remaining tokens.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        result = await limiter.is_allowed("test-client")

        assert result.remaining >= 0
        assert result.limit > 0

    @pytest.mark.asyncio
    async def test_limiter_returns_reset_time(self):
        """
        WBS 2.2.5.2.6: Limiter should return reset time.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        result = await limiter.is_allowed("test-client")

        assert result.reset_at > 0

    @pytest.mark.asyncio
    async def test_limiter_tracks_clients_separately(self):
        """
        WBS 2.2.5.2.3: Limiter should track clients separately.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=2)

        # Exhaust client1's limit
        await limiter.is_allowed("client1")
        await limiter.is_allowed("client1")
        result1 = await limiter.is_allowed("client1")

        # Client2 should still have quota
        result2 = await limiter.is_allowed("client2")

        assert result1.allowed is False
        assert result2.allowed is True

    @pytest.mark.asyncio
    async def test_concurrent_requests_maintain_accurate_token_count(self):
        """
        WBS 2.2.5.2.9: Concurrent requests must not cause race conditions.
        
        Tests that concurrent access to the token bucket maintains accurate
        token counts without read-modify-write race conditions.
        
        Pattern: asyncio.Lock for per-client synchronization
        Reference: GUIDELINES - concurrency patterns, Newman bulkhead pattern
        """
        import asyncio
        
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        
        # Run 20 concurrent requests for the same client
        # With burst=10, only 10 should succeed
        async def make_request():
            return await limiter.is_allowed("race-test-client")
        
        tasks = [make_request() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        allowed_count = sum(1 for r in results if r.allowed)
        blocked_count = sum(1 for r in results if not r.allowed)
        
        # Exactly 10 should be allowed (burst size)
        # Without proper locking, race conditions could allow more
        assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"
        assert blocked_count == 10, f"Expected 10 blocked, got {blocked_count}"

    @pytest.mark.asyncio
    async def test_limiter_has_per_client_lock(self):
        """
        WBS 2.2.5.2.9: Limiter should use per-client locks.
        
        Verifies that the rate limiter uses locking mechanism for thread safety.
        """
        limiter = InMemoryRateLimiter(requests_per_minute=60, burst=10)
        
        # The limiter should have a locks dictionary
        assert hasattr(limiter, '_locks'), "Rate limiter should have _locks attribute"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with rate limit middleware (high limit).
    """
    from src.api.middleware.rate_limit import RateLimitMiddleware, InMemoryRateLimiter

    app = FastAPI()

    # High limit for normal tests
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=100)
    app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

    @app.get("/test")
    def test_route():
        return {"message": "test"}

    return TestClient(app)


@pytest.fixture
def client_low_limit():
    """
    Create test client with rate limit middleware (low limit for 429 testing).
    """
    from src.api.middleware.rate_limit import RateLimitMiddleware, InMemoryRateLimiter

    app = FastAPI()

    # Low limit to easily test 429 behavior
    limiter = InMemoryRateLimiter(requests_per_minute=60, burst=2)
    app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

    @app.get("/test")
    def test_route():
        return {"message": "test"}

    return TestClient(app)
