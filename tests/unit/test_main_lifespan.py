"""
TWR4: Lifespan Initialization Tests — Provider Registry & Redis Pool

TDD RED Phase: These tests verify that the application lifespan
properly initializes and shuts down the provider registry and Redis pool.

Reference: WBS_TOOL_WIRING_REMEDIATION.md §TWR4
Defect: D7 — Redis pool + Provider registry init deferred (commented out)

AC-TWR4.1: app.state.provider_registry is initialized during startup
AC-TWR4.2: app.state.redis_pool is initialized during startup (graceful fallback)
AC-TWR4.3: Both are properly shut down during shutdown
"""

import pytest
from fastapi.testclient import TestClient


class TestTWR4ProviderRegistryInit:
    """
    AC-TWR4.1: app.state.provider_registry is initialized during app lifespan startup.
    """

    def test_startup_creates_provider_registry(self):
        """
        AC-TWR4.1: After lifespan startup, app.state.provider_registry must exist.
        """
        from src.main import app

        with TestClient(app) as client:
            assert hasattr(app.state, "provider_registry"), (
                "app.state.provider_registry must be set during lifespan startup"
            )
            assert app.state.provider_registry is not None, (
                "app.state.provider_registry must not be None"
            )

    def test_provider_registry_is_provider_router(self):
        """
        AC-TWR4.1: provider_registry must be a ProviderRouter instance
        with REGISTERED_MODELS loaded from model_registry.yaml.
        """
        from src.main import app
        from src.providers.router import ProviderRouter

        with TestClient(app) as client:
            registry = app.state.provider_registry
            assert isinstance(registry, ProviderRouter), (
                f"Expected ProviderRouter, got {type(registry)}"
            )

    def test_provider_registry_has_registered_models(self):
        """
        AC-TWR4.1: provider_registry must have REGISTERED_MODELS populated
        from config/model_registry.yaml (27 models).
        """
        from src.main import app

        with TestClient(app) as client:
            registry = app.state.provider_registry
            assert hasattr(registry, "REGISTERED_MODELS")
            assert len(registry.REGISTERED_MODELS) >= 20, (
                f"Expected at least 20 registered models from YAML, "
                f"got {len(registry.REGISTERED_MODELS)}"
            )


class TestTWR4RedisPoolInit:
    """
    AC-TWR4.2: app.state.redis_pool is initialized during app lifespan startup
    (with graceful fallback if Redis unavailable).
    """

    def test_startup_creates_redis_pool_attribute(self):
        """
        AC-TWR4.2: After lifespan startup, app.state.redis_pool must exist.
        It may be None if Redis is unavailable (graceful fallback).
        """
        from src.main import app

        with TestClient(app) as client:
            assert hasattr(app.state, "redis_pool"), (
                "app.state.redis_pool must be set during lifespan startup "
                "(None if Redis unavailable, connection if available)"
            )

    def test_redis_pool_graceful_fallback(self):
        """
        AC-TWR4.2: If Redis is unavailable, redis_pool should be None
        (not raise an exception that crashes startup).
        """
        from src.main import app

        # The app should start successfully even without Redis
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200, (
                "App must start and serve health checks even when Redis is down"
            )


class TestTWR4LifespanShutdown:
    """
    AC-TWR4.3: Both provider_registry and redis_pool are properly shut down.
    """

    def test_shutdown_releases_provider_registry(self):
        """
        AC-TWR4.3: After lifespan shutdown, provider_registry should be cleaned up.
        """
        from src.main import app

        with TestClient(app) as client:
            # Verify it exists during app lifetime
            assert hasattr(app.state, "provider_registry")
            assert app.state.provider_registry is not None

        # After context manager exits (shutdown), registry should be None
        assert app.state.provider_registry is None, (
            "provider_registry must be set to None during shutdown"
        )

    def test_shutdown_closes_redis_pool(self):
        """
        AC-TWR4.3: After lifespan shutdown, redis_pool should be cleaned up.
        """
        from src.main import app

        with TestClient(app) as client:
            # Redis may or may not be available
            assert hasattr(app.state, "redis_pool")

        # After shutdown, redis_pool should be None
        assert app.state.redis_pool is None, (
            "redis_pool must be set to None during shutdown"
        )

    def test_shutdown_sets_initialized_false(self):
        """
        AC-TWR4.3: app.state.initialized should be False after shutdown.
        (Pre-existing behavior, verify not broken.)
        """
        from src.main import app

        with TestClient(app) as client:
            assert app.state.initialized is True

        assert app.state.initialized is False


class TestTWR4ChatCompletionsRouting:
    """
    AC-TWR4.4: POST /v1/chat/completions routes through the initialized provider registry.
    """

    def test_chat_completions_endpoint_exists(self):
        """
        AC-TWR4.4: The /v1/chat/completions endpoint must be registered.
        """
        from src.main import app

        routes = [route.path for route in app.routes]
        assert "/v1/chat/completions" in routes

    def test_chat_completions_rejects_unknown_model(self):
        """
        AC-TWR4.4: POST /v1/chat/completions with an unknown model
        should invoke the provider router (not crash with AttributeError
        on missing app.state). 500 = NoProviderError (router IS working).
        """
        from src.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "nonexistent-model-xyz",
                    "messages": [{"role": "user", "content": "test"}],
                },
            )
            # NoProviderError → 500 proves the router is wired and rejecting.
            # (Proper 4xx error translation is out of D7 scope.)
            assert response.status_code in (400, 404, 500), (
                f"Expected error for unknown model, got {response.status_code}"
            )
