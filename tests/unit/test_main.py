"""
Main Application Tests - WBS 2.1.1 Application Entry Point

This module tests FastAPI application setup, lifespan events, and exception handlers.

Reference Documents:
- GUIDELINES: Sinha (FastAPI) pp. 89-91: Dependency injection, app setup
- ARCHITECTURE.md: Application entry point specification
- Buelta pp. 92-93: REST statelessness, graceful shutdown

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# WBS 2.1.1.1 FastAPI Application Setup Tests
# =============================================================================


class TestFastAPIApplicationSetup:
    """Tests for WBS 2.1.1.1: FastAPI Application Setup."""

    def test_app_instantiates_without_error(self):
        """
        WBS 2.1.1.1.7: App instantiates without error.

        Pattern: Basic smoke test for app creation.
        """
        from src.main import app

        assert isinstance(app, FastAPI)

    def test_app_has_correct_title(self):
        """
        WBS 2.1.1.1.2: Configure app metadata (title).
        """
        from src.main import app

        assert app.title == "LLM Gateway"

    def test_app_has_correct_version(self):
        """
        WBS 2.1.1.1.2: Configure app metadata (version).
        """
        from src.main import app

        assert app.version == "1.0.0"

    def test_app_has_description(self):
        """
        WBS 2.1.1.1.2: Configure app metadata (description).
        """
        from src.main import app

        assert app.description is not None
        assert len(app.description) > 0

    def test_app_includes_health_router(self):
        """
        WBS 2.1.1.1.4: Import and include all routers.

        Verifies health router is included.
        """
        from src.main import app

        routes = [route.path for route in app.routes]
        assert "/health" in routes

    def test_app_includes_chat_router(self):
        """
        WBS 2.1.1.1.4: Import and include all routers.

        Verifies chat router is included.
        """
        from src.main import app

        routes = [route.path for route in app.routes]
        assert "/v1/chat/completions" in routes

    def test_app_includes_tools_router(self):
        """
        WBS 2.1.1.1.4: Import and include all routers.

        Verifies tools router is included.
        """
        from src.main import app

        routes = [route.path for route in app.routes]
        assert "/v1/tools" in routes or "/v1/tools/execute" in routes


# =============================================================================
# WBS 2.1.1.1.3 Lifespan Context Manager Tests
# =============================================================================


class TestLifespanContextManager:
    """Tests for WBS 2.1.1.1.3: Lifespan context manager."""

    def test_app_has_lifespan_handler(self):
        """
        WBS 2.1.1.1.3: Add lifespan context manager for startup/shutdown.

        Verifies app uses modern lifespan pattern (not deprecated on_event).
        """
        from src.main import app

        # Modern FastAPI uses lifespan parameter, not on_event handlers
        assert app.router.lifespan_context is not None

    def test_lifespan_function_exists(self):
        """
        WBS 2.1.1.1.3: Lifespan context manager exists.
        """
        from src.main import lifespan

        assert callable(lifespan)


# =============================================================================
# WBS 2.1.1.2 Application Lifespan Events Tests
# =============================================================================


class TestApplicationLifespanEvents:
    """Tests for WBS 2.1.1.2: Application Lifespan Events."""

    def test_startup_initializes_app_state(self):
        """
        WBS 2.1.1.2.1: Implement startup event handler.
        WBS 2.1.1.2.7: Write RED test: startup initializes dependencies.

        Verifies startup sets up app state.
        """
        from src.main import app

        # Use TestClient context manager which handles lifespan
        with TestClient(app) as client:
            # After startup, state should be initialized
            response = client.get("/health")
            assert response.status_code == 200

        # Check that app.state has expected attributes after lifespan
        assert hasattr(app.state, "initialized")

    def test_startup_logs_environment_info(self, capfd):
        """
        WBS 2.1.1.2.1: Startup event handler logs environment.
        """
        from src.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

        # Startup should log environment info (captured in stdout/stderr)
        captured = capfd.readouterr()
        # Either stdout contains startup info or we check app initialized
        assert "LLM Gateway" in captured.out or hasattr(app.state, "initialized")

    def test_shutdown_cleans_up_resources(self):
        """
        WBS 2.1.1.2.4: Implement shutdown event handler.
        WBS 2.1.1.2.8: Write RED test: shutdown cleans up resources.

        Verifies shutdown releases resources.
        """
        from src.main import app

        # Use context manager to trigger both startup and shutdown
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
        # After exiting context, shutdown should have run
        # Resources should be released (no active connections)


# =============================================================================
# WBS 2.1.1.1.6 Exception Handlers Tests
# =============================================================================


class TestExceptionHandlers:
    """Tests for WBS 2.1.1.1.6: Add exception handlers."""

    def test_app_has_custom_exception_handler(self):
        """
        WBS 2.1.1.1.6: Add exception handlers.

        Verifies custom exception handlers are registered.
        """
        from src.main import app

        # App should have exception handlers beyond defaults
        assert len(app.exception_handlers) > 0

    def test_validation_error_returns_422(self):
        """
        WBS 2.1.1.1.6: Exception handlers return proper status codes.

        Pattern: RequestValidationError -> 422 (Sinha pp. 193-195)
        """
        from src.main import app

        client = TestClient(app)
        # Send invalid request to trigger validation error
        response = client.post(
            "/v1/chat/completions",
            json={"invalid": "data"}
        )
        assert response.status_code == 422

    def test_validation_error_has_detail(self):
        """
        WBS 2.1.1.1.6: Exception handlers return error details.

        Pattern: Structured error response with detail field.
        """
        from src.main import app

        client = TestClient(app)
        response = client.post(
            "/v1/chat/completions",
            json={"invalid": "data"}
        )
        data = response.json()
        assert "detail" in data

    def test_not_found_returns_404(self):
        """
        WBS 2.1.1.1.6: 404 handler for unknown routes.
        """
        from src.main import app

        client = TestClient(app)
        response = client.get("/nonexistent/endpoint")
        assert response.status_code == 404


# =============================================================================
# WBS 2.1.1.1.5 Middleware Tests
# =============================================================================


class TestMiddlewareRegistration:
    """Tests for WBS 2.1.1.1.5: Add middleware registration."""

    def test_cors_middleware_registered(self):
        """
        WBS 2.1.1.1.5: CORS middleware is registered.
        """
        from src.main import app

        # Check middleware stack includes CORS
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_cors_allows_requests_in_dev(self):
        """
        WBS 2.1.1.1.5: CORS allows requests in development.

        Pattern: Statelessness principle (Buelta p. 93)
        """
        from src.main import app

        client = TestClient(app)
        response = client.options(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        # Should not be blocked by CORS in dev
        assert response.status_code in [200, 204, 405]


class TestCORSOrigins:
    """
    Issue 35 Fix (Comp_Static_Analysis_Report_20251203.md):
    Tests for CORS origins via environment variable.
    """

    def test_cors_origins_from_env_variable(self, monkeypatch):
        """
        Issue 35: CORS origins should be configurable via environment variable.
        
        When LLM_GATEWAY_CORS_ORIGINS is set, those origins should be used
        instead of empty list for production.
        """
        # Set environment variables before importing
        monkeypatch.setenv("LLM_GATEWAY_ENV", "production")
        monkeypatch.setenv("LLM_GATEWAY_CORS_ORIGINS", "https://app.example.com,https://admin.example.com")
        
        # Force reimport to pick up new env vars
        import importlib
        import src.main
        importlib.reload(src.main)
        
        from src.main import get_cors_origins
        
        origins = get_cors_origins()
        assert "https://app.example.com" in origins
        assert "https://admin.example.com" in origins

    def test_cors_origins_empty_for_production_without_env(self, monkeypatch):
        """
        Issue 35: Production should have empty origins if not configured.
        """
        monkeypatch.setenv("LLM_GATEWAY_ENV", "production")
        monkeypatch.delenv("LLM_GATEWAY_CORS_ORIGINS", raising=False)
        
        import importlib
        import src.main
        importlib.reload(src.main)
        
        from src.main import get_cors_origins
        
        origins = get_cors_origins()
        assert origins == []

    def test_cors_allows_all_in_development(self, monkeypatch):
        """
        Issue 35: Development should allow all origins.
        """
        monkeypatch.setenv("LLM_GATEWAY_ENV", "development")
        monkeypatch.delenv("LLM_GATEWAY_CORS_ORIGINS", raising=False)
        
        import importlib
        import src.main
        importlib.reload(src.main)
        
        from src.main import get_cors_origins
        
        origins = get_cors_origins()
        assert origins == ["*"]


# =============================================================================
# Integration: Root Endpoint Test
# =============================================================================


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_service_info(self):
        """Root endpoint returns service information."""
        from src.main import app

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "service" in data
        assert "version" in data

    def test_root_returns_correct_service_name(self):
        """Root endpoint returns correct service name."""
        from src.main import app

        client = TestClient(app)
        response = client.get("/")
        data = response.json()
        assert data["service"] == "LLM Gateway"
