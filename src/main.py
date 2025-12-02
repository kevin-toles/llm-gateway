"""
LLM Gateway - Main Application Entry Point

This module provides the FastAPI application for the LLM Gateway service.
The gateway acts as a unified interface to multiple LLM providers.
"""

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers - WBS 2.2.1, 2.2.2
from src.api.routes.health import router as health_router
from src.api.routes.chat import router as chat_router

# Application metadata
APP_NAME = "LLM Gateway"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Unified gateway for LLM provider access"

# Environment configuration
ENV = os.getenv("LLM_GATEWAY_ENV", "development")
LOG_LEVEL = os.getenv("LLM_GATEWAY_LOG_LEVEL", "INFO")

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

# Include routers - WBS 2.2.1, 2.2.2
app.include_router(health_router)
app.include_router(chat_router)


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


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event() -> None:
    """Application startup tasks."""
    print(f"🚀 {APP_NAME} v{APP_VERSION} starting in {ENV} mode")
    print(f"📊 Log level: {LOG_LEVEL}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Application shutdown tasks."""
    print(f"👋 {APP_NAME} shutting down")
