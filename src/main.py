"""
LLM Gateway - Main Application Entry Point

This module provides the FastAPI application for the LLM Gateway service.
The gateway acts as a unified interface to multiple LLM providers.
"""

import os
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Application metadata
APP_NAME = "LLM Gateway"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Unified gateway for LLM provider access"

# Environment configuration
ENV = os.getenv("LLM_GATEWAY_ENV", "development")
LOG_LEVEL = os.getenv("LLM_GATEWAY_LOG_LEVEL", "INFO")
REDIS_URL = os.getenv("LLM_GATEWAY_REDIS_URL", "")

# Initialize FastAPI application
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs" if ENV != "production" else None,
    redoc_url="/redoc" if ENV != "production" else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ENV == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    environment: str
    version: str
    timestamp: str
    checks: dict[str, Any]


class ReadinessResponse(BaseModel):
    """Readiness check response model."""
    ready: bool
    checks: dict[str, bool]


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the current health status of the service including
    environment information and component health checks.
    """
    checks = {
        "api": True,
        "redis": await check_redis_health(),
    }
    
    return HealthResponse(
        status="healthy" if all(checks.values()) else "degraded",
        environment=ENV,
        version=APP_VERSION,
        timestamp=datetime.utcnow().isoformat() + "Z",
        checks=checks,
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Indicates whether the service is ready to accept traffic.
    Used by Kubernetes readiness probes.
    """
    checks = {
        "api": True,
        "redis": await check_redis_health(),
    }
    
    return ReadinessResponse(
        ready=all(checks.values()),
        checks=checks,
    )


@app.get("/live", tags=["Health"])
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.
    
    Simple check to verify the service is running.
    Used by Kubernetes liveness probes.
    """
    return {"status": "alive"}


# =============================================================================
# Helper Functions
# =============================================================================

async def check_redis_health() -> bool:
    """Check Redis connectivity."""
    if not REDIS_URL:
        # Redis not configured, consider it healthy (optional dependency)
        return True
    
    try:
        import redis.asyncio as redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        await client.close()
        return True
    except Exception:
        return False


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", tags=["Info"])
async def root() -> dict[str, str]:
    """Root endpoint returning basic service information."""
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs" if ENV != "production" else "disabled",
    }


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup tasks."""
    print(f"🚀 {APP_NAME} v{APP_VERSION} starting in {ENV} mode")
    print(f"📊 Log level: {LOG_LEVEL}")
    if REDIS_URL:
        print(f"🔗 Redis configured: {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks."""
    print(f"👋 {APP_NAME} shutting down")
