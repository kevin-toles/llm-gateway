"""
Tests for Health Router - WBS 2.2.1 Health Endpoints

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- GUIDELINES: Service metrics pattern (Building Microservices pp. 273-275)
- GUIDELINES: FastAPI dependency injection (Sinha pp. 89-91)
- ANTI_PATTERN_ANALYSIS: §4.1 Extract dependency checks to separate functions
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

# These imports will FAIL until we implement the router - this is the RED phase
# WBS 2.2.1.1.3: Import from src/api/routes/health.py
from src.api.routes.health import router as health_router
from src.api.routes.health import HealthService


class TestHealthRouter:
    """Test suite for health router endpoints - WBS 2.2.1.1"""
    
    # =========================================================================
    # WBS 2.2.1.1.7 RED: /health returns 200
    # =========================================================================
    
    def test_health_endpoint_returns_200(self, client: TestClient):
        """
        WBS 2.2.1.1.7: GET /health should return 200 status code.
        
        Pattern: Architecture Patterns with Python - high gear testing
        """
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_endpoint_returns_expected_schema(self, client: TestClient):
        """
        WBS 2.2.1.1.6: Response must include status, version fields.
        
        Expected: {"status": "healthy", "version": "1.0.0", ...}
        """
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["version"] == "1.0.0"
    
    def test_health_router_is_fastapi_router(self):
        """
        WBS 2.2.1.1.4: Health router must be a FastAPI APIRouter instance.
        
        Pattern: Router separation (Building Python Microservices with FastAPI p. 89)
        """
        from fastapi import APIRouter
        assert isinstance(health_router, APIRouter)


class TestReadinessEndpoint:
    """Test suite for readiness endpoint - WBS 2.2.1.2"""
    
    # =========================================================================
    # WBS 2.2.1.2.6 RED: /health/ready returns 200 when Redis up
    # =========================================================================
    
    def test_readiness_returns_200_when_redis_available(
        self, client: TestClient, mock_redis_healthy: AsyncMock
    ):
        """
        WBS 2.2.1.2.6: GET /health/ready returns 200 when Redis is up.
        
        Pattern: Dependency injection for testability (Sinha p. 90)
        """
        response = client.get("/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
    
    # =========================================================================
    # WBS 2.2.1.2.7 RED: /health/ready returns 503 when Redis down
    # =========================================================================
    
    def test_readiness_returns_503_when_redis_unavailable(
        self, client: TestClient, mock_redis_unhealthy: AsyncMock
    ):
        """
        WBS 2.2.1.2.7: GET /health/ready returns 503 when Redis is down.
        
        Pattern: Graceful degradation (Building Microservices p. 274)
        """
        response = client.get("/health/ready")
        assert response.status_code == 503
        
        data = response.json()
        assert data["status"] == "not_ready"
    
    def test_readiness_checks_redis_connectivity(
        self, client: TestClient, mock_redis_healthy: AsyncMock
    ):
        """
        WBS 2.2.1.2.2: Readiness must check Redis connectivity.
        
        Pattern: Service health checks (Building Microservices p. 273)
        """
        response = client.get("/health/ready")
        data = response.json()
        
        assert "checks" in data
        assert "redis" in data["checks"]
        assert data["checks"]["redis"] is True


class TestMetricsEndpoint:
    """Test suite for metrics endpoint - WBS 2.2.1.3"""
    
    # =========================================================================
    # WBS 2.2.1.3.5 RED: /metrics returns valid Prometheus format
    # =========================================================================
    
    def test_metrics_endpoint_returns_prometheus_format(self, client: TestClient):
        """
        WBS 2.2.1.3.5: GET /metrics returns valid Prometheus format.
        
        Pattern: Expose basic metrics (Building Microservices p. 273)
        """
        response = client.get("/metrics")
        assert response.status_code == 200
        
        # Prometheus format uses text/plain with specific content type
        assert "text/plain" in response.headers.get("content-type", "")
    
    def test_metrics_includes_request_count(self, client: TestClient):
        """
        WBS 2.2.1.3.3: Metrics must include request count.
        
        Pattern: Service metrics (Building Microservices p. 273-275)
        """
        response = client.get("/metrics")
        content = response.text
        
        # Prometheus metric naming convention
        assert "llm_gateway_requests_total" in content
    
    def test_metrics_includes_latency(self, client: TestClient):
        """
        WBS 2.2.1.3.3: Metrics must include latency histogram.
        """
        response = client.get("/metrics")
        content = response.text
        
        assert "llm_gateway_request_duration_seconds" in content
    
    def test_metrics_includes_error_rate(self, client: TestClient):
        """
        WBS 2.2.1.3.3: Metrics must include error rate.
        """
        response = client.get("/metrics")
        content = response.text
        
        assert "llm_gateway_errors_total" in content


class TestHealthService:
    """
    Test suite for HealthService - WBS 2.2.1.2.9 REFACTOR target
    
    Pattern: Repository pattern for dependency checks (Architecture Patterns p. 157)
    """
    
    def test_health_service_check_redis_returns_bool(self):
        """
        WBS 2.2.1.2.9: Dependency checks must be extracted to separate functions.
        
        Pattern: Single Responsibility (ANTI_PATTERN_ANALYSIS §4.1)
        """
        service = HealthService()
        # Should return bool, not raise exception
        result = service.check_redis_sync()
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_health_service_async_redis_check(self):
        """
        Test async Redis health check method.
        """
        service = HealthService()
        result = await service.check_redis()
        assert isinstance(result, bool)


# =============================================================================
# Fixtures - Following Repository Pattern for Test Doubles
# =============================================================================

@pytest.fixture
def client():
    """
    Create test client with health router mounted.
    
    Pattern: FakeRepository (Architecture Patterns with Python p. 157)
    """
    from fastapi import FastAPI
    from src.api.routes.health import router as health_router
    
    app = FastAPI()
    app.include_router(health_router)
    
    return TestClient(app)


@pytest.fixture
def mock_redis_healthy():
    """Mock Redis connection that returns healthy status."""
    with patch("src.api.routes.health.HealthService.check_redis") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_redis_unhealthy():
    """Mock Redis connection that returns unhealthy status."""
    with patch("src.api.routes.health.HealthService.check_redis") as mock:
        mock.return_value = False
        yield mock
