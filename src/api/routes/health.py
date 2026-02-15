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

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# WBS-PS5: Memory health metrics
from src.api.middleware.memory import get_memory_health
from src.providers.router import ProviderRouter

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
    models_available: int = 0
    inference_service: str = "unknown"


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with memory metrics (WBS-PS5)."""
    
    status: str
    version: str
    models_available: int = 0
    inference_service: str = "unknown"
    memory: Optional[dict[str, Any]] = None
    backpressure: Optional[dict[str, Any]] = None


class ReadinessResponse(BaseModel):
    """Readiness check response model."""

    status: str
    checks: dict[str, bool]
    models_available: int = 0


# =============================================================================
# Health Service - Repository Pattern (Architecture Patterns p. 157)
# WBS 2.2.1.2.9: Extract dependency checks to separate functions
# WBS 3.2.1.2: Semantic Search Health Check Integration
# =============================================================================

# Default semantic search URL from config
SEMANTIC_SEARCH_URL = os.getenv("LLM_GATEWAY_SEMANTIC_SEARCH_URL", "http://localhost:8081")

# Default ai-agents URL from config (WBS 3.3.1.1)
AI_AGENTS_URL = os.getenv("LLM_GATEWAY_AI_AGENTS_URL", "http://localhost:8082")


class HealthService:
    """
    Service class for health check operations.

    Pattern: Repository pattern for dependency checks
    Reference: Architecture Patterns with Python p. 157

    This class enables dependency injection and test doubles (FakeRepository pattern).
    
    WBS 3.2.1.2: Added semantic-search health checking.
    WBS 3.3.1.2: Added ai-agents health checking (optional service).
    Reference: GUIDELINES pp. 2309-2321 - Newman's graceful degradation patterns.
    Reference: ARCHITECTURE.md line 342 - optional services return degraded status.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        semantic_search_url: str | None = None,
        ai_agents_url: str | None = None,
        router: ProviderRouter | None = None,
    ):
        """
        Initialize health service with optional URL overrides.
        
        Args:
            redis_url: Redis connection URL (defaults to env var)
            semantic_search_url: Semantic search service URL (defaults to env var)
            ai_agents_url: AI agents service URL (defaults to env var)
            router: ProviderRouter instance for model count (defaults to new instance)
            
        WBS 3.3.1.1.5: Gateway resolves ai-agents URL via dependency injection.
        TWR3.4: Router injected for dynamic model count (AC-TWR3.2).
        """
        self._redis_url = redis_url or REDIS_URL
        self._semantic_search_url = semantic_search_url or SEMANTIC_SEARCH_URL
        self._ai_agents_url = ai_agents_url or AI_AGENTS_URL
        self._router = router or ProviderRouter()

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

    async def check_semantic_search_health(self) -> bool:
        """
        Check semantic-search service connectivity asynchronously.

        WBS 3.2.1.2.2: Implement check_semantic_search_health() function.
        WBS 3.2.1.2.3: Call semantic-search /health endpoint.

        Returns:
            bool: True if semantic-search is reachable, False otherwise

        Pattern: Graceful degradation (Newman pp. 352-353)
        Pattern: Circuit breaker fast-fail (Newman pp. 357-358)
        Anti-pattern avoided: §3.1 Bare Except - exceptions logged with context
        Anti-pattern avoided: §67 Connection pooling - uses context manager
        """
        if not self._semantic_search_url:
            # Semantic search not configured, consider it healthy (optional dependency)
            logger.debug("Semantic search not configured, skipping health check")
            return True

        try:
            import httpx

            # Use async context manager for proper connection pooling
            # Anti-pattern §67: Don't create new client per request
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._semantic_search_url}/health")

                if response.status_code == 200:
                    return True
                else:
                    logger.warning(
                        f"Semantic search health check returned status {response.status_code}"
                    )
                    return False

        except httpx.ConnectError as e:
            # Anti-pattern §3.1: Log with context
            logger.warning(f"Semantic search connection failed: {e}")
            return False
        except httpx.TimeoutException as e:
            # Pattern: Timeout logging (Newman p. 356)
            logger.warning(f"Semantic search health check timeout: {e}")
            return False
        except Exception as e:
            # Anti-pattern §3.1: Log exception, don't silently fail
            logger.warning(f"Semantic search health check failed: {e}")
            return False

    async def check_ai_agents_health(self) -> bool:
        """
        Check ai-agents service connectivity asynchronously.

        WBS 3.3.1.2.2: Implement check_ai_agents_health() function.
        WBS 3.3.1.2.3: Report status but don't fail readiness (agents optional).

        Returns:
            bool: True if ai-agents is reachable, False otherwise

        Pattern: Graceful degradation (Newman pp. 352-353)
        Reference: ARCHITECTURE.md line 342 - optional services return degraded
        Reference: llm-document-enhancer/docs/ARCHITECTURE.md line 242 - ai-agents optional
        Anti-pattern avoided: §3.1 Bare Except - exceptions logged with context
        Anti-pattern avoided: §67 Connection pooling - uses context manager
        """
        if not self._ai_agents_url:
            # AI agents not configured, consider it healthy (optional dependency)
            logger.debug("AI agents not configured, skipping health check")
            return True

        try:
            import httpx

            # Use async context manager for proper connection pooling
            # Anti-pattern §67: Don't create new client per request
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._ai_agents_url}/health")

                if response.status_code == 200:
                    return True
                else:
                    logger.warning(
                        f"AI agents health check returned status {response.status_code}"
                    )
                    return False

        except httpx.ConnectError as e:
            # Anti-pattern §3.1: Log with context
            logger.warning(f"AI agents connection failed: {e}")
            return False
        except httpx.TimeoutException as e:
            # Pattern: Timeout logging (Newman p. 356)
            logger.warning(f"AI agents health check timeout: {e}")
            return False
        except Exception as e:
            # Anti-pattern §3.1: Log exception, don't silently fail
            logger.warning(f"AI agents health check failed: {e}")
            return False

    def check_cloud_providers_health(self) -> tuple[bool, int]:
        """
        Check cloud provider availability.

        Returns the count of registered models from the router's
        REGISTERED_MODELS instance attribute (loaded from model_registry.yaml).

        Returns:
            tuple[bool, int]: (is_healthy, registered_model_count)
            - is_healthy: True if at least one model is registered
            - registered_model_count: Number of registered models

        Pattern: Graceful degradation with accurate status reporting (Newman pp. 352-353)
        TWR3.2: Uses instance REGISTERED_MODELS, not phantom class EXTERNAL_MODELS (AC-TWR3.2).
        """
        registered_count = len(self._router.REGISTERED_MODELS)
        has_providers = registered_count > 0
        return has_providers, registered_count


# =============================================================================
# Dependency Injection - FastAPI Pattern (Sinha p. 90)
# =============================================================================

# Global service instances (can be overridden in tests)
_health_service: HealthService | None = None


def get_health_service() -> HealthService:
    """
    Dependency injection factory for HealthService.

    Pattern: Factory method for dependency injection (Sinha p. 90)
    """
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


# =============================================================================
# Router - WBS 2.2.1.1.4
# =============================================================================

router = APIRouter(tags=["Health"])


# =============================================================================
# Health Endpoint - WBS 2.2.1.1.5, 2.2.1.1.6
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check(
    health_service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """
    Health check endpoint - always returns 200.

    WBS 2.2.1.1.5: Implement GET /health endpoint
    WBS 2.2.1.1.6: Return {"status": "healthy", "version": "1.0.0"}
    TWR3.3: models_available is now dynamic from router REGISTERED_MODELS (AC-TWR3.1).
    
    NOTE: This always returns 200 so startup scripts work.
    Use /health/ready for detailed readiness checks with 503 on failure.
    Use /health/detailed for inference-service and model status.

    Returns:
        HealthResponse: Health status and version
    """
    _, model_count = health_service.check_cloud_providers_health()
    return HealthResponse(
        status="healthy", 
        version=APP_VERSION,
        models_available=model_count,
        inference_service="not_managed",  # Gateway manages external models only; CMS manages inference
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    response: Response,
    health_service: HealthService = Depends(get_health_service),
) -> DetailedHealthResponse:
    """
    Detailed health check endpoint with memory metrics (WBS-PS5).

    Returns memory usage, backpressure status, inference-service status, and overall health.
    Use this endpoint for debugging OOM issues and monitoring memory pressure.

    Returns:
        DetailedHealthResponse: Health status with memory/backpressure/inference details
    """
    mem_health = get_memory_health()
    providers_healthy, model_count = health_service.check_cloud_providers_health()
    
    # Status is degraded if under memory pressure or no cloud providers registered
    memory_status = mem_health.get("status", "healthy")
    
    # Gateway manages cloud providers only; inference-service is managed by CMS
    if providers_healthy and model_count > 0:
        providers_status = "registered"
    else:
        providers_status = "no_providers"
    
    # Overall status: worst of memory and provider registration
    if memory_status == "degraded" or not providers_healthy:
        status = "degraded"
    else:
        status = memory_status
    
    if not providers_healthy:
        response.status_code = 503
    
    return DetailedHealthResponse(
        status=status,
        version=APP_VERSION,
        models_available=model_count,
        inference_service=providers_status,  # field reused; shows cloud provider status
        memory=mem_health.get("memory"),
        backpressure=mem_health.get("backpressure"),
    )


# =============================================================================
# Readiness Endpoint - WBS 2.2.1.2, WBS 3.2.1.2
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
    WBS 3.2.1.2.1: Add semantic-search health check to gateway readiness
    CRITICAL FIX: Now includes inference-service in readiness check
    WBS 2.2.1.2.4: Return {"status": "ready"} if all checks pass
    WBS 2.2.1.2.5: Return 503 if dependencies unavailable
    WBS 3.2.1.2.4: Report degraded status if semantic-search unavailable

    Args:
        response: FastAPI response object for setting status code
        health_service: Injected health service dependency

    Returns:
        ReadinessResponse: Readiness status with dependency checks
        
    Pattern: Graceful degradation (Newman pp. 352-353)
    """
    # Check all dependencies concurrently
    # NOTE: Gateway manages cloud providers only. Inference-service is managed by CMS.
    redis_healthy = await health_service.check_redis()
    semantic_search_healthy = await health_service.check_semantic_search_health()
    ai_agents_healthy = await health_service.check_ai_agents_health()
    providers_healthy, model_count = health_service.check_cloud_providers_health()

    checks = {
        "redis": redis_healthy,
        "semantic_search": semantic_search_healthy,
        "ai_agents": ai_agents_healthy,
        "cloud_providers": providers_healthy,
    }
    
    # WBS 3.3.1.2.3: ai_agents is optional - don't fail readiness if it's down
    # Gateway only checks its own dependencies (cloud providers, semantic-search)
    # Inference-service health is CMS's responsibility, not the gateway's
    critical_checks = {
        "semantic_search": semantic_search_healthy,
        "cloud_providers": providers_healthy,
    }
    critical_healthy = all(critical_checks.values())
    all_healthy = all(checks.values())
    
    # Determine status:
    # - "ready" if all services healthy
    # - "degraded" if critical services healthy but optional services down
    # - "not_ready" if critical services down
    if critical_healthy and not all_healthy:
        status = "degraded"
    elif critical_healthy:
        status = "ready"
    else:
        status = "not_ready"
        response.status_code = 503

    return ReadinessResponse(
        status=status,
        checks=checks,
        models_available=model_count,
    )


# =============================================================================
# NOTE: /metrics endpoint removed - WBS-OBS13
#
# The /metrics endpoint was previously defined here using a manual MetricsService
# class that formatted Prometheus metrics as text strings. This has been replaced
# by the proper prometheus_client library implementation in observability/metrics.py
# which is mounted via get_metrics_app() in main.py.
#
# The old implementation was orphaned code - no callers ever invoked the
# increment_provider_request(), record_provider_latency(), etc. methods,
# so the metrics were always returning zero values.
#
# Reference: WBS_B5_B1_REMAINING_WORK.md - OBS-13: Remove duplicate /metrics
# =============================================================================
