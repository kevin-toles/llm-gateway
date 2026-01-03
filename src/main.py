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

# Import routers - WBS 2.1.1.1.4, 2.2.1, 2.2.2, 2.2.3, 2.2.4, 2.2.5
from src.api.routes.health import router as health_router
from src.api.routes.chat import router as chat_router
from src.api.routes.sessions import router as sessions_router
from src.api.routes.tools import router as tools_router
from src.api.routes.models import router as models_router

# Application metadata
APP_NAME = "LLM Gateway"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Unified gateway for LLM provider access"

# Environment configuration
ENV = os.getenv("LLM_GATEWAY_ENV", "development")
LOG_LEVEL = os.getenv("LLM_GATEWAY_LOG_LEVEL", "INFO")
CORS_ORIGINS = os.getenv("LLM_GATEWAY_CORS_ORIGINS", "")


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
    print(f"🚀 {APP_NAME} v{APP_VERSION} starting in {ENV} mode")
    print(f"📊 Log level: {LOG_LEVEL}")
    
    # Initialize app state - WBS 2.1.1.2.7
    app.state.initialized = True
    app.state.environment = ENV
    
    # NOTE: WBS 2.1.1.2.2 - Redis connection pool initialization
    # Implementation deferred to Stage 3: Integration (WBS 3.x)
    # When Redis is integrated: app.state.redis_pool = await create_redis_pool()
    
    # NOTE: WBS 2.1.1.2.3 - Provider client registry initialization
    # Implementation deferred to Stage 3: Integration (WBS 3.x)
    # When providers are integrated: app.state.provider_registry = ProviderRegistry()
    
    yield
    
    # =========================================================================
    # SHUTDOWN - WBS 2.1.1.2.4
    # =========================================================================
    print(f"👋 {APP_NAME} shutting down")
    
    # Clean up resources - WBS 2.1.1.2.8
    app.state.initialized = False
    
    # NOTE: WBS 2.1.1.2.5 - Redis connection cleanup
    # Implementation deferred to Stage 3: Integration (WBS 3.x)
    # When Redis is integrated:
    # if hasattr(app.state, "redis_pool"):
    #     await app.state.redis_pool.close()
    
    # NOTE: WBS 2.1.1.2.6 - Provider client shutdown
    # Implementation deferred to Stage 3: Integration (WBS 3.x)
    # When providers are integrated:
    # if hasattr(app.state, "provider_registry"):
    #     await app.state.provider_registry.shutdown()


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

# Include routers - WBS 2.1.1.1.4
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(tools_router)
app.include_router(models_router)


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
