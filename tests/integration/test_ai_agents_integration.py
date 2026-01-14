"""
WBS 3.3.1: AI Agents Integration Tests

This module tests gateway configuration and health check integration
for the ai-agents microservice.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3141-3155 - WBS 3.3.1
- ARCHITECTURE.md: Line 342 - Graceful degradation for optional services
- llm-document-enhancer/docs/ARCHITECTURE.md: Line 242 - ai-agents is optional

INTEGRATION TEST COMPLIANCE:
- Configuration tests: No mocks needed
- Health check tests: Use real services where available, skip otherwise
- Pattern: Dependency injection for testability (not mocking HTTP)
"""

import os

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


# =============================================================================
# Integration Test Configuration
# =============================================================================

AI_AGENTS_URL = os.getenv("INTEGRATION_AI_AGENTS_URL", "http://localhost:8082")


def ai_agents_available() -> bool:
    """Check if ai-agents service is available."""
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{AI_AGENTS_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


# =============================================================================
# WBS 3.3.1.1: Gateway Configuration for AI Agents Tests (No Mocks Needed)
# =============================================================================


class TestAIAgentsGatewayConfiguration:
    """
    WBS 3.3.1.1: Test gateway configuration for ai-agents service.
    
    These tests verify configuration - no mocks needed.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_ai_agents_url_in_settings(self):
        """
        WBS 3.3.1.1.1: Verify ai_agents_url exists in Settings.
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
        """
        import os
        from importlib import reload

        original = os.environ.get("LLM_GATEWAY_AI_AGENTS_URL")
        
        try:
            os.environ["LLM_GATEWAY_AI_AGENTS_URL"] = "http://test-ai-agents:9999"
            
            import src.core.config as config_module
            config_module.get_settings.cache_clear()
            
            settings = config_module.get_settings()
            assert settings.ai_agents_url == "http://test-ai-agents:9999"
        finally:
            if original is None:
                os.environ.pop("LLM_GATEWAY_AI_AGENTS_URL", None)
            else:
                os.environ["LLM_GATEWAY_AI_AGENTS_URL"] = original
            
            import src.core.config as config_module
            config_module.get_settings.cache_clear()

    def test_ai_agents_url_follows_naming_convention(self):
        """
        WBS 3.3.1.1.4: Service discovery pattern documentation.
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
    
    Tests use real services where available, dependency injection otherwise.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_check_ai_agents_health_function_exists(self):
        """
        WBS 3.3.1.2.2: check_ai_agents_health() function should exist.
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

        service = HealthService(ai_agents_url=AI_AGENTS_URL)
        result = await service.check_ai_agents_health()
        assert isinstance(result, bool)

    def test_readiness_includes_ai_agents_status(self, client):
        """
        WBS 3.3.1.2.1: Readiness endpoint should include ai_agents check.
        """
        response = client.get("/health/ready")
        data = response.json()
        
        assert "checks" in data
        assert "ai_agents" in data["checks"], (
            "Readiness checks should include ai_agents status"
        )

    @pytest.mark.skipif(
        not ai_agents_available(),
        reason="AI Agents service not available"
    )
    def test_readiness_shows_healthy_when_service_up(self, client):
        """
        WBS 3.3.1.2.4: When ai-agents is healthy, should report True.
        
        Uses real ai-agents service.
        """
        response = client.get("/health/ready")
        data = response.json()
        
        # With real service available, should be True
        assert data["checks"]["ai_agents"] is True

    @pytest.mark.skipif(
        ai_agents_available(),
        reason="Test only runs when AI Agents service is unavailable"
    )
    def test_readiness_shows_false_when_service_down(self, client):
        """
        WBS 3.3.1.2.3: When ai-agents is down, should report False but not fail.
        
        ai-agents is an optional service - gateway should remain ready.
        """
        response = client.get("/health/ready")
        data = response.json()
        
        # Should NOT be 503 - ai-agents is optional
        assert response.status_code == 200, (
            "ai-agents unavailability should not cause 503"
        )
        
        # Status should be ready or degraded, not not_ready
        assert data["status"] in ["ready", "degraded"], (
            "Status should be ready or degraded when optional service down"
        )

    @pytest.mark.asyncio
    async def test_ai_agents_health_timeout_handling(self):
        """
        WBS 3.3.1.2.2: Health check should handle timeouts gracefully.
        
        If ai-agents takes too long, should return False not raise exception.
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
    
    Configuration tests - no mocks needed.
    """

    def test_settings_loads_ai_agents_url_from_pydantic(self):
        """
        Verify Settings class properly loads ai_agents_url.
        """
        from src.core.config import Settings

        settings = Settings()
        assert settings.ai_agents_url == "http://localhost:8082"

    def test_health_service_uses_configured_url(self):
        """
        HealthService should use ai_agents_url from configuration.
        """
        from src.api.routes.health import HealthService

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
