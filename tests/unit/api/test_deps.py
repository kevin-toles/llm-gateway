"""
Tests for API Dependencies - WBS 2.2.6

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- ARCHITECTURE.md line 31: deps.py - FastAPI dependencies
- GUIDELINES: Sinha pp. 89-91 (Dependency injection patterns)
- ANTI_PATTERN_ANALYSIS: §4.1 Extract to service class

WBS Items Covered:
- 2.2.6.1.1: Create src/api/deps.py
- 2.2.6.1.2: Implement get_settings dependency
- 2.2.6.1.3: Implement get_redis dependency
- 2.2.6.1.4: Implement get_chat_service dependency
- 2.2.6.1.5: Implement get_session_manager dependency
- 2.2.6.1.6: Implement get_tool_executor dependency
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# RED Phase: These imports will fail until implementation
from src.api.deps import (
    get_settings,
    get_redis,
    get_chat_service,
    get_session_manager,
    get_tool_executor,
)


class TestDependencyModule:
    """Test suite for API dependencies module - WBS 2.2.6.1"""

    # =========================================================================
    # WBS 2.2.6.1.1: deps.py Module
    # =========================================================================

    def test_deps_module_exists(self):
        """
        WBS 2.2.6.1.1: src/api/deps.py module must exist.
        """
        import src.api.deps

        assert src.api.deps is not None


class TestGetSettings:
    """Test suite for get_settings dependency - WBS 2.2.6.1.2"""

    def test_get_settings_returns_settings_instance(self):
        """
        WBS 2.2.6.1.2: get_settings must return Settings instance.

        Pattern: Singleton pattern for configuration (Sinha p. 90)
        """
        from src.core.config import Settings

        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_callable_dependency(self):
        """
        WBS 2.2.6.1.2: get_settings must be usable as FastAPI dependency.
        """
        assert callable(get_settings)

    def test_get_settings_returns_same_instance(self):
        """
        WBS 2.2.6.1.2: get_settings should return cached instance.

        Pattern: Singleton with @lru_cache
        """
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestGetRedis:
    """Test suite for get_redis dependency - WBS 2.2.6.1.3"""

    def test_get_redis_is_callable(self):
        """
        WBS 2.2.6.1.3: get_redis must be callable.
        """
        assert callable(get_redis)

    @pytest.mark.asyncio
    async def test_get_redis_returns_redis_client(self):
        """
        WBS 2.2.6.1.3: get_redis must return Redis client or None.

        Note: Returns None when Redis is unavailable (graceful degradation)
        """
        result = await get_redis()
        # May return client or None depending on Redis availability
        assert result is None or hasattr(result, "ping")


class TestGetChatService:
    """Test suite for get_chat_service dependency - WBS 2.2.6.1.4"""

    def test_get_chat_service_is_callable(self):
        """
        WBS 2.2.6.1.4: get_chat_service must be callable.
        """
        assert callable(get_chat_service)

    def test_get_chat_service_returns_chat_service(self):
        """
        WBS 2.2.6.1.4: get_chat_service must return ChatService instance.

        Pattern: Factory function for DI (Sinha p. 90)
        """
        from src.api.routes.chat import ChatService

        service = get_chat_service()
        assert isinstance(service, ChatService)


class TestGetSessionManager:
    """Test suite for get_session_manager dependency - WBS 2.2.6.1.5"""

    def test_get_session_manager_is_callable(self):
        """
        WBS 2.2.6.1.5: get_session_manager must be callable.
        """
        assert callable(get_session_manager)

    def test_get_session_manager_returns_session_service(self):
        """
        WBS 2.2.6.1.5: get_session_manager must return SessionService instance.

        Pattern: Factory function for DI (Sinha p. 90)
        """
        from src.api.routes.sessions import SessionService

        service = get_session_manager()
        assert isinstance(service, SessionService)


class TestGetToolExecutor:
    """Test suite for get_tool_executor dependency - WBS 2.2.6.1.6"""

    def test_get_tool_executor_is_callable(self):
        """
        WBS 2.2.6.1.6: get_tool_executor must be callable.
        """
        assert callable(get_tool_executor)

    def test_get_tool_executor_returns_tool_executor_service(self):
        """
        WBS 2.2.6.1.6: get_tool_executor must return ToolExecutorService.

        Pattern: Factory function for DI (Sinha p. 90)
        """
        from src.api.routes.tools import ToolExecutorService

        service = get_tool_executor()
        assert isinstance(service, ToolExecutorService)


class TestDependencyInjectionInRoutes:
    """Integration tests for dependency injection in routes."""

    def test_dependencies_can_be_used_in_fastapi(self, client: TestClient):
        """
        WBS 2.2.6.1.7: Dependencies must work with FastAPI Depends().

        Pattern: Dependency injection (Sinha pp. 89-91)
        """
        response = client.get("/test-deps")
        assert response.status_code == 200

        data = response.json()
        assert "settings_available" in data
        assert data["settings_available"] is True


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with routes that use dependencies.

    Pattern: Integration testing for DI
    """
    from src.api.deps import get_settings

    app = FastAPI()

    @app.get("/test-deps")
    def test_route(settings=Depends(get_settings)):
        return {
            "settings_available": settings is not None,
            "service_name": settings.service_name,
        }

    return TestClient(app)
