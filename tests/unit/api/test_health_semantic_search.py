"""
Tests for Semantic Search Health Integration - WBS 3.2.1

TDD RED Phase: Tests for semantic-search health check in gateway readiness.

Reference Documents:
- ARCHITECTURE.md Line 277: semantic_search_url configuration
- GUIDELINES pp. 2309-2321: Newman's graceful degradation patterns
- Comp_Static_Analysis_Report #24: Stub services for semantic-search

WBS 3.2.1.1: Gateway Configuration for Semantic Search
WBS 3.2.1.2: Health Check Integration

Anti-Patterns Avoided:
- CODING_PATTERNS §67: Use shared httpx.AsyncClient (connection pooling)
- ANTI_PATTERN §3.1: Log exceptions with context
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# WBS 3.2.1.1: Gateway Configuration Tests
# =============================================================================


class TestSemanticSearchConfiguration:
    """Tests for semantic-search URL configuration - WBS 3.2.1.1"""

    def test_semantic_search_url_in_settings(self):
        """
        WBS 3.2.1.1.1: Verify LLM_GATEWAY_SEMANTIC_SEARCH_URL in Settings.
        
        Expected: Settings class has semantic_search_url field.
        """
        from src.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "semantic_search_url")
        assert settings.semantic_search_url == "http://localhost:8081"

    def test_semantic_search_url_env_override(self):
        """
        WBS 3.2.1.1.2: Test URL override via environment variable.
        
        Expected: LLM_GATEWAY_SEMANTIC_SEARCH_URL overrides default.
        """
        import os

        from src.core.config import Settings

        with patch.dict(os.environ, {"LLM_GATEWAY_SEMANTIC_SEARCH_URL": "http://semantic-search:8081"}):
            # Clear cached settings
            from src.core.config import get_settings
            get_settings.cache_clear()

            settings = Settings()
            assert settings.semantic_search_url == "http://semantic-search:8081"

            # Restore cache
            get_settings.cache_clear()

    def test_semantic_search_url_docker_dns_pattern(self):
        """
        WBS 3.2.1.1.3: Test Docker DNS service discovery pattern.
        
        Pattern: Service discovery via Docker network DNS.
        Expected URL format: http://<service-name>:<port>
        """
        import os

        from src.core.config import Settings

        docker_url = "http://semantic-search:8081"

        with patch.dict(os.environ, {"LLM_GATEWAY_SEMANTIC_SEARCH_URL": docker_url}):
            from src.core.config import get_settings
            get_settings.cache_clear()

            settings = Settings()
            assert settings.semantic_search_url == docker_url
            assert "semantic-search" in settings.semantic_search_url

            get_settings.cache_clear()


# =============================================================================
# WBS 3.2.1.2: Health Check Integration Tests
# =============================================================================


class TestSemanticSearchHealthCheck:
    """Tests for semantic-search health check - WBS 3.2.1.2"""

    def test_health_service_has_check_semantic_search_method(self):
        """
        WBS 3.2.1.2.2: HealthService must have check_semantic_search_health().
        
        RED: This test will FAIL until we implement the method.
        """
        from src.api.routes.health import HealthService

        service = HealthService()
        assert hasattr(service, "check_semantic_search_health")
        assert callable(service.check_semantic_search_health)

    @pytest.mark.asyncio
    async def test_check_semantic_search_health_returns_true_when_healthy(self):
        """
        WBS 3.2.1.2.3: check_semantic_search_health() returns True when service is up.
        
        Pattern: Graceful degradation (Newman pp. 352-353)
        """
        from src.api.routes.health import HealthService

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            service = HealthService(semantic_search_url="http://semantic-search:8081")
            result = await service.check_semantic_search_health()

            assert result is True

    @pytest.mark.asyncio
    async def test_check_semantic_search_health_returns_false_when_unhealthy(self):
        """
        WBS 3.2.1.2.3: check_semantic_search_health() returns False when service is down.
        
        Pattern: Circuit breaker fast-fail (Newman pp. 357-358)
        """
        import httpx

        from src.api.routes.health import HealthService

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            service = HealthService(semantic_search_url="http://semantic-search:8081")
            result = await service.check_semantic_search_health()

            assert result is False

    @pytest.mark.asyncio
    async def test_check_semantic_search_health_timeout_returns_false(self):
        """
        WBS 3.2.1.2.3: Timeout results in health check failure.
        
        Pattern: Timeout configuration (Newman p. 356)
        """
        import httpx

        from src.api.routes.health import HealthService

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Request timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            service = HealthService(semantic_search_url="http://semantic-search:8081")
            result = await service.check_semantic_search_health()

            assert result is False


class TestReadinessWithSemanticSearch:
    """Tests for readiness endpoint including semantic-search - WBS 3.2.1.2"""

    def test_readiness_checks_semantic_search(self, client: TestClient):
        """
        WBS 3.2.1.2.1: Readiness check must include semantic-search.
        
        Expected: /health/ready response includes semantic_search in checks.
        """
        from src.api.routes.health import HealthService

        with patch.object(HealthService, "check_redis", new_callable=AsyncMock, return_value=True), \
             patch.object(HealthService, "check_semantic_search_health", new_callable=AsyncMock, return_value=True):

            response = client.get("/health/ready")
            data = response.json()

            assert "checks" in data
            assert "semantic_search" in data["checks"]
            assert data["checks"]["semantic_search"] is True

    def test_readiness_returns_503_when_semantic_search_down(self, client: TestClient):
        """
        WBS 3.2.1.2.5: Readiness returns 503 if semantic-search unavailable.
        
        Pattern: Graceful degradation (Newman pp. 352-353)
        """
        from src.api.routes.health import HealthService

        with patch.object(HealthService, "check_redis", new_callable=AsyncMock, return_value=True), \
             patch.object(HealthService, "check_semantic_search_health", new_callable=AsyncMock, return_value=False):

            response = client.get("/health/ready")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["checks"]["semantic_search"] is False

    def test_readiness_returns_degraded_status(self, client: TestClient):
        """
        WBS 3.2.1.2.4: Report degraded status if semantic-search unavailable.
        
        Pattern: Degraded functionality (Newman pp. 351-353)
        
        Note: "degraded" status means some services are down but core is up.
        """
        from src.api.routes.health import HealthService

        # Redis up, semantic-search down
        with patch.object(HealthService, "check_redis", new_callable=AsyncMock, return_value=True), \
             patch.object(HealthService, "check_semantic_search_health", new_callable=AsyncMock, return_value=False):

            response = client.get("/health/ready")
            data = response.json()

            # When any dependency is down, status should reflect it
            assert data["status"] in ["not_ready", "degraded"]

    def test_readiness_200_when_all_services_healthy(self, client: TestClient):
        """
        WBS 3.2.1.2.6: Readiness returns 200 when all services healthy.
        
        GREEN: All dependency checks pass.
        WBS 3.3.1.2: Updated to also mock ai-agents as healthy.
        """
        from src.api.routes.health import HealthService

        with patch.object(HealthService, "check_redis", new_callable=AsyncMock, return_value=True), \
             patch.object(HealthService, "check_semantic_search_health", new_callable=AsyncMock, return_value=True), \
             patch.object(HealthService, "check_ai_agents_health", new_callable=AsyncMock, return_value=True):

            response = client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"


# =============================================================================
# WBS 3.2.1.1.5: Integration Test - Gateway resolves semantic-search URL
# =============================================================================


class TestSemanticSearchURLResolution:
    """Integration tests for semantic-search URL resolution - WBS 3.2.1.1.5"""

    @pytest.mark.asyncio
    async def test_semantic_search_client_accepts_configured_url(self):
        """
        WBS 3.2.1.1.5: SemanticSearchClient accepts URL from settings.
        
        Expected: Client initializes without error using semantic_search_url from config.
        
        Note: SemanticSearchClient doesn't expose _base_url - it's encapsulated
        in the internal httpx.AsyncClient. We verify the client accepts the URL.
        """
        from src.clients.semantic_search import SemanticSearchClient
        from src.core.config import get_settings

        settings = get_settings()

        # Verify client can be instantiated with configured URL
        client = SemanticSearchClient(base_url=settings.semantic_search_url)

        # Client should have internal _client (httpx.AsyncClient)
        assert hasattr(client, "_client")
        assert client._owns_client is True

        # Cleanup
        await client.close()

    def test_health_service_uses_configured_url(self):
        """
        WBS 3.2.1.1.5: HealthService uses semantic_search_url from settings.
        """
        from src.api.routes.health import HealthService
        from src.core.config import get_settings

        settings = get_settings()
        service = HealthService(semantic_search_url=settings.semantic_search_url)

        assert service._semantic_search_url == settings.semantic_search_url


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """Create FastAPI test client with health router."""
    from fastapi import FastAPI

    from src.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    return TestClient(app)
