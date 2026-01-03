"""
WBS 3.3.1: AI Agents Integration Tests

This module tests gateway configuration and health check integration
for the ai-agents microservice.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3141-3155 - WBS 3.3.1
- ARCHITECTURE.md: Line 342 - Graceful degradation for optional services
- llm-document-enhancer/docs/ARCHITECTURE.md: Line 242 - ai-agents is optional

TDD Phase: RED - These tests define expected ai-agents integration behavior.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


# =============================================================================
# WBS 3.3.1.1: Gateway Configuration for AI Agents Tests
# =============================================================================


class TestAIAgentsGatewayConfiguration:
    """
    WBS 3.3.1.1: Test gateway configuration for ai-agents service.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_ai_agents_url_in_settings(self):
        """
        WBS 3.3.1.1.1: Verify ai_agents_url exists in Settings.
        
        Settings should have ai_agents_url field with sensible default.
        """
        from src.core.config import get_settings

        settings = get_settings()
        assert hasattr(settings, "ai_agents_url"), (
            "Settings should have ai_agents_url field"
        )
        assert settings.ai_agents_url, "ai_agents_url should have a value"
        assert "8082" in settings.ai_agents_url, (
            "Default ai_agents_url should use port 8082 per ARCHITECTURE.md"
        )

    def test_ai_agents_url_configurable_via_env(self):
        """
        WBS 3.3.1.1.1: ai_agents_url should be configurable via environment.
        
        Environment variable LLM_GATEWAY_AI_AGENTS_URL should override default.
        """
        import os
        from importlib import reload

        # Save original
        original = os.environ.get("LLM_GATEWAY_AI_AGENTS_URL")
        
        try:
            # Set test value
            os.environ["LLM_GATEWAY_AI_AGENTS_URL"] = "http://test-ai-agents:9999"
            
            # Need to reimport to pick up new env var
            import src.core.config as config_module
            
            # Clear the cached settings
            config_module.get_settings.cache_clear()
            
            settings = config_module.get_settings()
            assert settings.ai_agents_url == "http://test-ai-agents:9999"
        finally:
            # Restore
            if original is None:
                os.environ.pop("LLM_GATEWAY_AI_AGENTS_URL", None)
            else:
                os.environ["LLM_GATEWAY_AI_AGENTS_URL"] = original
            
            # Clear cache again
            import src.core.config as config_module
            config_module.get_settings.cache_clear()

    def test_ai_agents_url_follows_naming_convention(self):
        """
        WBS 3.3.1.1.4: Service discovery pattern documentation.
        
        The URL field should follow the same naming convention as other services.
        Pattern: <service>_url
        """
        from src.core.config import get_settings

        settings = get_settings()
        
        # All service URLs should follow consistent naming
        assert hasattr(settings, "semantic_search_url")
        assert hasattr(settings, "ai_agents_url")
        assert hasattr(settings, "ollama_url")
        
        # All should have http scheme
        assert settings.ai_agents_url.startswith("http")


# =============================================================================
# WBS 3.3.1.2: Health Check Integration Tests
# =============================================================================


class TestAIAgentsHealthCheckIntegration:
    """
    WBS 3.3.1.2: Test health check integration for ai-agents service.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_ai_agents_healthy(self):
        """
        Mock ai-agents service returning healthy status.
        """
        async def mock_get(*args, **kwargs):
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            return mock_response
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = mock_get
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    @pytest.fixture
    def mock_ai_agents_unavailable(self):
        """
        Mock ai-agents service being unavailable.
        """
        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = mock_get
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            yield mock_client

    @pytest.mark.asyncio
    async def test_check_ai_agents_health_function_exists(self):
        """
        WBS 3.3.1.2.2: check_ai_agents_health() function should exist.
        
        RED: This test will fail until we implement the function.
        """
        from src.api.routes.health import HealthService

        service = HealthService()
        assert hasattr(service, "check_ai_agents_health"), (
            "HealthService should have check_ai_agents_health method"
        )
        assert callable(service.check_ai_agents_health)

    @pytest.mark.asyncio
    async def test_check_ai_agents_health_returns_bool(self):
        """
        WBS 3.3.1.2.2: check_ai_agents_health() should return boolean.
        """
        from src.api.routes.health import HealthService

        service = HealthService(ai_agents_url="http://localhost:8082")
        result = await service.check_ai_agents_health()
        assert isinstance(result, bool)

    def test_readiness_includes_ai_agents_status(self, client):
        """
        WBS 3.3.1.2.1: Readiness endpoint should include ai_agents check.
        
        The /health/ready response should have ai_agents in checks dict.
        """
        response = client.get("/health/ready")
        data = response.json()
        
        assert "checks" in data
        assert "ai_agents" in data["checks"], (
            "Readiness checks should include ai_agents status"
        )

    def test_ai_agents_unavailable_does_not_fail_readiness(self, client):
        """
        WBS 3.3.1.2.3: AI agents being down should NOT fail readiness.
        
        ai-agents is an optional service. Gateway should remain ready
        even if ai-agents is unavailable - this differs from semantic-search.
        
        Pattern: Graceful degradation (Newman pp. 352-353)
        Reference: ARCHITECTURE.md line 342 - optional services return degraded
        """
        # Mock all HTTP calls to ai-agents to fail
        with patch("src.api.routes.health.HealthService.check_ai_agents_health") as mock:
            mock.return_value = False
            
            # Also mock other health checks to be healthy
            with patch("src.api.routes.health.HealthService.check_redis") as mock_redis:
                mock_redis.return_value = True
                with patch("src.api.routes.health.HealthService.check_semantic_search_health") as mock_ss:
                    mock_ss.return_value = True
                    
                    response = client.get("/health/ready")
                    
                    # Should NOT be 503 - ai-agents is optional
                    assert response.status_code == 200, (
                        "ai-agents unavailability should not cause 503"
                    )
                    
                    data = response.json()
                    # Status should be ready or degraded, not not_ready
                    assert data["status"] in ["ready", "degraded"], (
                        "Status should be ready or degraded when optional service down"
                    )
                    assert data["checks"]["ai_agents"] is False

    def test_ai_agents_healthy_included_in_checks(self, client):
        """
        WBS 3.3.1.2.4: When ai-agents is healthy, should report True.
        """
        with patch("src.api.routes.health.HealthService.check_ai_agents_health") as mock:
            mock.return_value = True
            with patch("src.api.routes.health.HealthService.check_redis") as mock_redis:
                mock_redis.return_value = True
                with patch("src.api.routes.health.HealthService.check_semantic_search_health") as mock_ss:
                    mock_ss.return_value = True
                    
                    response = client.get("/health/ready")
                    data = response.json()
                    
                    assert data["checks"]["ai_agents"] is True

    @pytest.mark.asyncio
    async def test_ai_agents_health_timeout_handling(self):
        """
        WBS 3.3.1.2.2: Health check should handle timeouts gracefully.
        
        If ai-agents takes too long, should return False not raise exception.
        Pattern: Timeout handling (Newman p. 356)
        """
        from src.api.routes.health import HealthService

        # Create service pointing to non-existent host
        service = HealthService(ai_agents_url="http://nonexistent.local:9999")
        
        # Should return False, not raise
        result = await service.check_ai_agents_health()
        assert result is False


# =============================================================================
# WBS 3.3.1.1.5: Integration Test - Gateway Resolves AI Agents URL
# =============================================================================


class TestGatewayAIAgentsURLResolution:
    """
    WBS 3.3.1.1.5: Integration tests for URL resolution.
    """

    def test_settings_loads_ai_agents_url_from_pydantic(self):
        """
        Verify Settings class properly loads ai_agents_url.
        """
        from src.core.config import Settings

        # Create settings instance directly
        settings = Settings()
        assert settings.ai_agents_url == "http://localhost:8082"

    def test_health_service_uses_configured_url(self):
        """
        HealthService should use ai_agents_url from configuration.
        """
        from src.api.routes.health import HealthService

        # Default should be localhost:8082
        service = HealthService()
        assert "8082" in service._ai_agents_url or service._ai_agents_url is None

    def test_health_service_accepts_custom_url(self):
        """
        HealthService should accept custom ai_agents_url in constructor.
        
        Pattern: Dependency injection (Sinha p. 90)
        """
        from src.api.routes.health import HealthService

        custom_url = "http://custom-ai-agents:9000"
        service = HealthService(ai_agents_url=custom_url)
        assert service._ai_agents_url == custom_url
