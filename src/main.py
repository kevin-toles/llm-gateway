"""
LLM Gateway - Main Application Entry Point

This module provides the FastAPI application for the LLM Gateway service.
The gateway acts as a unified interface to multiple LLM providers.

WBS 2.1.1: Application Entry Point
- 2.1.1.1: Configure FastAPI application
- 2.1.1.2: Application lifespan events
"""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import middleware - WBS-PS5: Memory tracking and backpressure
from src.api.middleware.memory import MemoryMiddleware, memory_tracker

# WBS-OBS1-4: Import observability components
from src.observability import (
    setup_tracing,
    TracingMiddleware,
    MetricsMiddleware,
    get_metrics_app,
    get_logger,
)
from src.core.config import get_settings

# Import routers - WBS 2.1.1.1.4, 2.2.1, 2.2.2, 2.2.3, 2.2.4, 2.2.5
from src.api.routes.health import router as health_router
from src.api.routes.chat import router as chat_router
from src.api.routes.sessions import router as sessions_router
from src.api.routes.tools import router as tools_router
from src.api.routes.models import router as models_router
from src.api.routes.responses import router as responses_router

# Application metadata
APP_NAME = "LLM Gateway"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Unified gateway for LLM provider access"

# Environment configuration
ENV = os.getenv("LLM_GATEWAY_ENV", "development")
LOG_LEVEL = os.getenv("LLM_GATEWAY_LOG_LEVEL", "INFO")
CORS_ORIGINS = os.getenv("LLM_GATEWAY_CORS_ORIGINS", "")

# Path constants to avoid duplicate literals
METRICS_PATH = "/metrics"


def get_cors_origins() -> list[str]:
    """
    Get CORS allowed origins based on environment.
    
    Issue 35 Fix (Comp_Static_Analysis_Report_20251203.md):
    Configure allowed origins via environment variable instead of hardcoding empty list.
    
    - Development: Allow all origins (["*"])
    - Staging/Production: Use LLM_GATEWAY_CORS_ORIGINS env var (comma-separated)
    - If not configured in production: Empty list (blocks all cross-origin requests)
    
    Example:
        export LLM_GATEWAY_CORS_ORIGINS="https://app.example.com,https://admin.example.com"
    
    Returns:
        List of allowed origin strings.
    """
    if ENV == "development":
        return ["*"]
    
    if CORS_ORIGINS:
        # Parse comma-separated origins and strip whitespace
        return [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]
    
    return []


# =============================================================================
# Lifespan Context Manager - WBS 2.1.1.1.3
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup/shutdown events.
    
    WBS 2.1.1.2.1: Implement startup event handler
    WBS 2.1.1.2.4: Implement shutdown event handler
    
    Uses the modern lifespan pattern instead of deprecated @app.on_event.
    Reference: Sinha (FastAPI) pp. 89-91 - Lifespan patterns
    """
    # =========================================================================
    # STARTUP - WBS 2.1.1.2.1
    # =========================================================================
    logger = get_logger(__name__)
    settings = get_settings()
    
    logger.info(f"{APP_NAME} v{APP_VERSION} starting in {ENV} mode")
    logger.info(f"Log level: {LOG_LEVEL}")
    
    # WBS-OBS1: Initialize OpenTelemetry tracing
    if settings.tracing_enabled:
        tracer_provider = setup_tracing(
            service_name=settings.service_name,
            otlp_endpoint=settings.otlp_endpoint,
        )
        app.state.tracer_provider = tracer_provider
        logger.info(
            "OpenTelemetry tracing initialized",
            extra={"otlp_endpoint": settings.otlp_endpoint or "console"}
        )
    
    # Initialize app state - WBS 2.1.1.2.7
    app.state.initialized = True
    app.state.environment = ENV
    
    # TWR4 (D7): Provider registry initialization — WBS 2.1.1.2.3
    # Creates ProviderRouter with providers loaded from API keys in settings.
    # REGISTERED_MODELS loaded from config/model_registry.yaml.
    from src.providers.router import create_provider_router
    app.state.provider_registry = create_provider_router(settings)
    logger.info(
        f"Provider registry initialized: "
        f"{len(app.state.provider_registry.REGISTERED_MODELS)} registered models, "
        f"{len(app.state.provider_registry.providers)} active providers"
    )
    
    # TWR4 (D7): Redis connection pool initialization — WBS 2.1.1.2.2
    # Graceful fallback: Redis is optional; app runs without it.
    try:
        import redis.asyncio as aioredis
        app.state.redis_pool = aioredis.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,
        )
        await app.state.redis_pool.ping()
        logger.info(f"Redis pool initialized: {settings.redis_url}")
    except Exception as e:
        logger.warning(f"Redis unavailable, proceeding without caching: {e}")
        app.state.redis_pool = None
    
    yield
    
    # =========================================================================
    # SHUTDOWN - WBS 2.1.1.2.4
    # =========================================================================
    logger.info(f"{APP_NAME} shutting down")
    
    # Clean up resources - WBS 2.1.1.2.8
    app.state.initialized = False
    
    # TWR4 (D7): Redis connection cleanup — WBS 2.1.1.2.5
    if hasattr(app.state, "redis_pool") and app.state.redis_pool is not None:
        try:
            await app.state.redis_pool.aclose()
            logger.info("Redis pool closed")
        except Exception as e:
            logger.warning(f"Error closing Redis pool: {e}")
    app.state.redis_pool = None
    
    # TWR4 (D7): Provider registry cleanup — WBS 2.1.1.2.6
    if hasattr(app.state, "provider_registry"):
        app.state.provider_registry = None
        logger.info("Provider registry released")


# Initialize FastAPI application with lifespan - WBS 2.1.1.1.1
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs" if ENV != "production" else None,
    redoc_url="/redoc" if ENV != "production" else None,
    lifespan=lifespan,
)

# Configure CORS - WBS 2.1.1.1.5
# Issue 35 Fix: Use get_cors_origins() for configurable allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WBS-OBS2: Add TracingMiddleware for OpenTelemetry distributed tracing
# Excluded paths: /health, /metrics (internal endpoints)
app.add_middleware(
    TracingMiddleware,
    exclude_paths=["/health", METRICS_PATH, "/"],
)

# WBS-OBS3: Add MetricsMiddleware for Prometheus metrics
# Records RED metrics (Rate, Errors, Duration) for all routes
app.add_middleware(
    MetricsMiddleware,
    exclude_paths=[METRICS_PATH],
)

# WBS-PS5: Memory tracking and backpressure middleware
# Prevents OOM by rejecting requests when memory exceeds threshold
# or when concurrent request limit is reached
app.add_middleware(MemoryMiddleware)

# Include routers - WBS 2.1.1.1.4
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(tools_router)
app.include_router(models_router)
app.include_router(responses_router)

# WBS-OBS4: Mount /metrics endpoint for Prometheus scraping
# Returns Prometheus text format metrics at http://localhost:8080/metrics
app.mount(METRICS_PATH, get_metrics_app())


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", tags=["Info"])
async def root() -> dict[str, Any]:
    """Root endpoint returning basic service information."""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs" if ENV != "production" else "disabled",
    }
