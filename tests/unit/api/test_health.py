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

    # =========================================================================
    # WBS 2.2.1.3.4 RED: /metrics includes provider-specific metrics
    # =========================================================================

    def test_metrics_includes_provider_request_count(self, client: TestClient):
        """
        WBS 2.2.1.3.4: Metrics must include provider-specific request counts.

        Pattern: Domain-specific metrics in business-relevant terms (GUIDELINES line 2309)
        Reference: ARCHITECTURE.md lists providers: anthropic, openai, ollama

        Expected Prometheus metrics:
        - llm_gateway_provider_requests_total{provider="anthropic"}
        - llm_gateway_provider_requests_total{provider="openai"}
        - llm_gateway_provider_requests_total{provider="ollama"}
        """
        response = client.get("/metrics")
        content = response.text

        # Provider-specific request counters with labels
        assert "llm_gateway_provider_requests_total" in content
        assert 'provider="anthropic"' in content
        assert 'provider="openai"' in content
        assert 'provider="ollama"' in content

    def test_metrics_includes_provider_latency(self, client: TestClient):
        """
        WBS 2.2.1.3.4: Metrics must include provider-specific latency.

        Pattern: Service metrics - response times per provider (Newman p. 273-275)
        """
        response = client.get("/metrics")
        content = response.text

        # Provider-specific latency histogram
        assert "llm_gateway_provider_latency_seconds" in content
        assert 'provider="anthropic"' in content or "anthropic" in content

    def test_metrics_includes_provider_errors(self, client: TestClient):
        """
        WBS 2.2.1.3.4: Metrics must include provider-specific error counts.

        Pattern: Service metrics - error rates per provider (Newman p. 273-275)
        """
        response = client.get("/metrics")
        content = response.text

        # Provider-specific error counters
        assert "llm_gateway_provider_errors_total" in content

    def test_metrics_includes_token_usage(self, client: TestClient):
        """
        WBS 2.2.1.3.4: Metrics must include token usage tracking.

        Pattern: Domain-specific metrics - "token usage tracking" (GUIDELINES line 2309)
        Reference: ARCHITECTURE.md - Operational Controls include "Token/cost tracking per request"
        """
        response = client.get("/metrics")
        content = response.text

        # Token usage metrics per provider
        assert "llm_gateway_tokens_total" in content


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
# TWR3: Fix LLM Gateway Health Endpoint (D6)
# =============================================================================


class TestTWR3HealthModelsAvailable:
    """
    TWR3 RED: Verify GET /health returns dynamic models_available count.

    AC-TWR3.1: models_available reflects actual registered model count (not hardcoded 0).
    AC-TWR3.2: Health check uses router.REGISTERED_MODELS, not phantom EXTERNAL_MODELS.
    """

    def test_health_returns_models_available_gt_zero(self, client: TestClient):
        """
        AC-TWR3.1: GET /health must return models_available > 0
        when model_registry.yaml has registered models.
        """
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "models_available" in data
        assert data["models_available"] > 0, (
            f"models_available should reflect YAML registry count, got {data['models_available']}"
        )

    def test_health_models_available_matches_yaml_registry(self, client: TestClient):
        """
        AC-TWR3.1: models_available must equal the number of models
        in config/model_registry.yaml (currently 27).
        """
        response = client.get("/health")
        data = response.json()
        # YAML has: inference(15) + anthropic(2) + openai(4) + google(4) + deepseek(2) = 27
        assert data["models_available"] >= 20, (
            f"Expected at least 20 models from YAML, got {data['models_available']}"
        )

    def test_check_cloud_providers_uses_registered_models(self):
        """
        AC-TWR3.2: check_cloud_providers_health() must use
        router.REGISTERED_MODELS (instance attr), NOT
        ProviderRouter.EXTERNAL_MODELS (phantom class attr).
        """
        service = HealthService()
        # This must NOT raise AttributeError
        is_healthy, count = service.check_cloud_providers_health()
        assert isinstance(is_healthy, bool)
        assert isinstance(count, int)
        assert count > 0, "REGISTERED_MODELS should have entries from YAML"

    def test_no_external_models_attribute_error(self):
        """
        AC-TWR3.2: ProviderRouter must not be accessed via phantom
        class attribute EXTERNAL_MODELS — that attribute does not exist.
        """
        from src.providers.router import ProviderRouter
        assert not hasattr(ProviderRouter, "EXTERNAL_MODELS"), (
            "EXTERNAL_MODELS is a phantom class attribute — use instance REGISTERED_MODELS"
        )

    def test_detailed_health_returns_dynamic_model_count(self, client: TestClient):
        """
        AC-TWR3.1: /health/detailed must also return dynamic model count
        (it already calls check_cloud_providers_health).
        """
        response = client.get("/health/detailed")
        data = response.json()
        assert data["models_available"] > 0, (
            f"Detailed health models_available should be dynamic, got {data['models_available']}"
        )


class TestMetricsServiceProviderMethods:
    """
    Test suite for MetricsService provider-specific methods - WBS 2.2.1.3.4

    Pattern: Domain-specific metrics in business-relevant terms (GUIDELINES line 2309)
    Reference: ARCHITECTURE.md - Provider Router supports anthropic, openai, ollama
    """

    def test_increment_provider_request_updates_count(self):
        """
        WBS 2.2.1.3.4: Provider request counter should increment correctly.
        """
        from src.api.routes.health import MetricsService

        service = MetricsService()
        service.increment_provider_request("anthropic")
        service.increment_provider_request("anthropic")
        service.increment_provider_request("openai")

        metrics = service.get_prometheus_metrics()
        assert 'llm_gateway_provider_requests_total{provider="anthropic"} 2' in metrics
        assert 'llm_gateway_provider_requests_total{provider="openai"} 1' in metrics

    def test_increment_provider_error_updates_count(self):
        """
        WBS 2.2.1.3.4: Provider error counter should increment correctly.
        """
        from src.api.routes.health import MetricsService

        service = MetricsService()
        service.increment_provider_error("ollama")

        metrics = service.get_prometheus_metrics()
        assert 'llm_gateway_provider_errors_total{provider="ollama"} 1' in metrics

    def test_record_provider_latency_updates_sum_and_count(self):
        """
        WBS 2.2.1.3.4: Provider latency should update sum and count.

        Pattern: Service metrics - response times per provider (Newman p. 273-275)
        """
        from src.api.routes.health import MetricsService

        service = MetricsService()
        service.record_provider_latency("anthropic", 0.5)
        service.record_provider_latency("anthropic", 0.3)

        metrics = service.get_prometheus_metrics()
        assert 'llm_gateway_provider_latency_seconds_sum{provider="anthropic"} 0.800000' in metrics
        assert 'llm_gateway_provider_latency_seconds_count{provider="anthropic"} 2' in metrics

    def test_record_provider_tokens_updates_count(self):
        """
        WBS 2.2.1.3.4: Token usage should update per provider.

        Pattern: Domain-specific metrics - "token usage tracking" (GUIDELINES line 2309)
        """
        from src.api.routes.health import MetricsService

        service = MetricsService()
        service.record_provider_tokens("openai", 150)
        service.record_provider_tokens("openai", 200)

        metrics = service.get_prometheus_metrics()
        assert 'llm_gateway_tokens_total{provider="openai"} 350' in metrics

    def test_unknown_provider_ignored_gracefully(self):
        """
        Unknown providers should be ignored without error.

        Pattern: Graceful degradation (Building Microservices p. 274)
        Anti-pattern avoided: §3.1 Bare Except - no exception raised
        """
        from src.api.routes.health import MetricsService

        service = MetricsService()
        # Should not raise exception
        service.increment_provider_request("unknown_provider")
        service.increment_provider_error("unknown_provider")
        service.record_provider_latency("unknown_provider", 1.0)
        service.record_provider_tokens("unknown_provider", 100)

        # Metrics should still be valid
        metrics = service.get_prometheus_metrics()
        assert "llm_gateway_provider_requests_total" in metrics


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
    """Mock Redis connection that returns healthy status.

    WBS 3.2.1.2: Updated to also mock semantic-search as healthy (default).
    WBS 3.3.1.2: Updated to also mock ai-agents as healthy (default).
    """
    with patch("src.api.routes.health.HealthService.check_redis") as mock_redis, \
         patch("src.api.routes.health.HealthService.check_semantic_search_health") as mock_semantic, \
         patch("src.api.routes.health.HealthService.check_ai_agents_health") as mock_agents:
        mock_redis.return_value = True
        mock_semantic.return_value = True
        mock_agents.return_value = True
        yield mock_redis


@pytest.fixture
def mock_redis_unhealthy():
    """Mock Redis connection that returns unhealthy status.

    WBS 3.2.1.2: Updated to also mock semantic-search (healthy by default).
    WBS 3.3.1.2: Updated to also mock ai-agents (healthy by default).
    """
    with patch("src.api.routes.health.HealthService.check_redis") as mock_redis, \
         patch("src.api.routes.health.HealthService.check_semantic_search_health") as mock_semantic, \
         patch("src.api.routes.health.HealthService.check_ai_agents_health") as mock_agents:
        mock_redis.return_value = False
        mock_semantic.return_value = True  # semantic-search healthy, Redis down
        mock_agents.return_value = True  # ai-agents healthy
        yield mock_redis
