"""
Semantic Search Service - Stub Application
===========================================
Provides minimal health endpoints for docker-compose integration testing.
Replace with actual semantic-search-service when available.

Reference: docs/ARCHITECTURE.md lines 300-330 - Health Check Integration
WBS: 3.4.1.1.3
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="semantic-search-service (stub)",
    description="Stub service for docker-compose integration testing",
    version="0.0.1-stub",
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str


class SearchResponse(BaseModel):
    """Search response model (stub)."""

    chunks: list[dict]
    query: str
    message: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        service="semantic-search-service",
        version="0.0.1-stub",
    )


@app.get("/health/ready", response_model=HealthResponse)
async def ready():
    """Readiness probe endpoint."""
    return HealthResponse(
        status="ready",
        service="semantic-search-service",
        version="0.0.1-stub",
    )


@app.post("/v1/search", response_model=SearchResponse)
async def search(query: str = ""):
    """Stub search endpoint - returns empty results."""
    return SearchResponse(
        chunks=[],
        query=query,
        message="Stub service - no actual search functionality",
    )


@app.get("/v1/chunks/{chunk_id}")
async def get_chunk(chunk_id: str):
    """Stub chunk retrieval endpoint."""
    return {
        "chunk_id": chunk_id,
        "content": "Stub chunk content",
        "metadata": {"source": "stub"},
        "message": "Stub service - no actual chunk storage",
    }
