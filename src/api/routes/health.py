"""
Health Router - WBS 2.2.1 Health Endpoints

This module implements the health check endpoints following microservices best practices.

Reference Documents:
- Building Microservices (Newman) pp. 273-275: Service metrics and synthetic monitoring
- Building Python Microservices with FastAPI (Sinha) pp. 89-91: Dependency injection patterns
- Architecture Patterns with Python (Percival & Gregory) p. 157: Repository pattern for testing

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses - exceptions logged with context
- ANTI_PATTERN_ANALYSIS §4.1: Cognitive complexity < 15 per function
- ANTI_PATTERN_ANALYSIS §5.1: No unused parameters
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Response, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Environment configuration
REDIS_URL = os.getenv("LLM_GATEWAY_REDIS_URL", "")
APP_VERSION = os.getenv("LLM_GATEWAY_VERSION", "1.0.0")

# =============================================================================
# Response Models - Following Pydantic patterns (Sinha pp. 193-195)
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response model."""

    status: str
    checks: dict[str, bool]


# =============================================================================
# Health Service - Repository Pattern (Architecture Patterns p. 157)
# WBS 2.2.1.2.9: Extract dependency checks to separate functions
# =============================================================================


class HealthService:
    """
    Service class for health check operations.

    Pattern: Repository pattern for dependency checks
    Reference: Architecture Patterns with Python p. 157

    This class enables dependency injection and test doubles (FakeRepository pattern).
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize health service with optional Redis URL override."""
        self._redis_url = redis_url or REDIS_URL

    async def check_redis(self) -> bool:
        """
        Check Redis connectivity asynchronously.

        WBS 2.2.1.2.2: Check Redis connectivity

        Returns:
            bool: True if Redis is reachable, False otherwise

        Pattern: Graceful degradation (Building Microservices p. 274)
        Anti-pattern avoided: §3.1 Bare Except - exceptions logged with context
        """
        if not self._redis_url:
            # Redis not configured, consider it healthy (optional dependency)
            logger.debug("Redis not configured, skipping health check")
            return True

        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            await client.aclose()
            return True
        except ImportError:
            logger.warning("redis package not installed, cannot check Redis health")
            return True  # Optional dependency
        except Exception as e:
            # Anti-pattern §3.1: Log exception, don't silently fail
            logger.warning(f"Redis health check failed: {e}")
            return False

    def check_redis_sync(self) -> bool:
        """
        Synchronous Redis health check for testing.

        Returns:
            bool: True if Redis is reachable, False otherwise
        """
        if not self._redis_url:
            return True

        try:
            import redis

            client = redis.from_url(self._redis_url, decode_responses=True)
            client.ping()
            client.close()
            return True
        except ImportError:
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False


# =============================================================================
# Metrics Service - Prometheus Format (Building Microservices p. 273)
# =============================================================================


class MetricsService:
    """
    Service class for Prometheus metrics.

    Pattern: Service metrics exposure (Building Microservices p. 273-275)
    """

    def __init__(self):
        """Initialize metrics counters."""
        self._request_count = 0
        self._error_count = 0
        self._total_duration_seconds = 0.0

    def get_prometheus_metrics(self) -> str:
        """
        Generate Prometheus-format metrics.

        WBS 2.2.1.3.2: Expose Prometheus metrics format
        WBS 2.2.1.3.3: Include request count, latency, error rate

        Returns:
            str: Prometheus text format metrics
        """
        lines = [
            "# HELP llm_gateway_requests_total Total number of requests",
            "# TYPE llm_gateway_requests_total counter",
            f"llm_gateway_requests_total {self._request_count}",
            "",
            "# HELP llm_gateway_request_duration_seconds Request latency in seconds",
            "# TYPE llm_gateway_request_duration_seconds histogram",
            f"llm_gateway_request_duration_seconds_sum {self._total_duration_seconds:.6f}",
            f"llm_gateway_request_duration_seconds_count {self._request_count}",
            "",
            "# HELP llm_gateway_errors_total Total number of errors",
            "# TYPE llm_gateway_errors_total counter",
            f"llm_gateway_errors_total {self._error_count}",
        ]
        return "\n".join(lines)

    def increment_request_count(self) -> None:
        """Increment request counter."""
        self._request_count += 1

    def increment_error_count(self) -> None:
        """Increment error counter."""
        self._error_count += 1

    def record_duration(self, duration_seconds: float) -> None:
        """Record request duration."""
        self._total_duration_seconds += duration_seconds


# =============================================================================
# Dependency Injection - FastAPI Pattern (Sinha p. 90)
# =============================================================================

# Global service instances (can be overridden in tests)
_health_service: Optional[HealthService] = None
_metrics_service: Optional[MetricsService] = None


def get_health_service() -> HealthService:
    """
    Dependency injection factory for HealthService.

    Pattern: Factory method for dependency injection (Sinha p. 90)
    """
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


def get_metrics_service() -> MetricsService:
    """
    Dependency injection factory for MetricsService.
    """
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


# =============================================================================
# Router - WBS 2.2.1.1.4
# =============================================================================

router = APIRouter(tags=["Health"])


# =============================================================================
# Health Endpoint - WBS 2.2.1.1.5, 2.2.1.1.6
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    WBS 2.2.1.1.5: Implement GET /health endpoint
    WBS 2.2.1.1.6: Return {"status": "healthy", "version": "1.0.0"}

    Returns:
        HealthResponse: Health status and version
    """
    return HealthResponse(status="healthy", version=APP_VERSION)


# =============================================================================
# Readiness Endpoint - WBS 2.2.1.2
# =============================================================================


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(
    response: Response,
    health_service: HealthService = Depends(get_health_service),
) -> ReadinessResponse:
    """
    Readiness check endpoint.

    WBS 2.2.1.2.1: Implement GET /health/ready endpoint
    WBS 2.2.1.2.2: Check Redis connectivity
    WBS 2.2.1.2.4: Return {"status": "ready"} if all checks pass
    WBS 2.2.1.2.5: Return 503 if dependencies unavailable

    Args:
        response: FastAPI response object for setting status code
        health_service: Injected health service dependency

    Returns:
        ReadinessResponse: Readiness status with dependency checks
    """
    redis_healthy = await health_service.check_redis()

    checks = {"redis": redis_healthy}
    all_healthy = all(checks.values())

    if not all_healthy:
        response.status_code = 503

    return ReadinessResponse(
        status="ready" if all_healthy else "not_ready",
        checks=checks,
    )


# =============================================================================
# Metrics Endpoint - WBS 2.2.1.3
# =============================================================================


@router.get("/metrics")
async def metrics(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> PlainTextResponse:
    """
    Prometheus metrics endpoint.

    WBS 2.2.1.3.1: Implement GET /metrics endpoint
    WBS 2.2.1.3.2: Expose Prometheus metrics format
    WBS 2.2.1.3.3: Include request count, latency, error rate

    Args:
        metrics_service: Injected metrics service dependency

    Returns:
        PlainTextResponse: Prometheus text format metrics
    """
    content = metrics_service.get_prometheus_metrics()
    return PlainTextResponse(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
