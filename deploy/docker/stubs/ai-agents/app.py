"""
AI Agents Service - Stub Application
=====================================
Provides minimal health and agent endpoints for docker-compose integration testing.
Replace with actual ai-agents service when available.

Reference: ai-agents/docs/ARCHITECTURE.md - Agent endpoints
WBS: 3.4.1.1.4
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any

app = FastAPI(
    title="ai-agents (stub)",
    description="Stub service for docker-compose integration testing",
    version="0.0.1-stub",
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    version: str


class AgentRequest(BaseModel):
    """Agent request model."""

    code: str
    language: str = "python"
    context: str = ""
    format: str = "markdown"


class AgentResponse(BaseModel):
    """Agent response model (stub)."""

    status: str
    result: dict[str, Any]
    message: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        service="ai-agents",
        version="0.0.1-stub",
    )


@app.get("/health/ready", response_model=HealthResponse)
async def ready():
    """Readiness probe endpoint."""
    return HealthResponse(
        status="ready",
        service="ai-agents",
        version="0.0.1-stub",
    )


@app.post("/v1/agents/code-review/run", response_model=AgentResponse)
async def code_review(request: AgentRequest):
    """
    Stub code review endpoint.
    
    Reference: ai-agents/docs/ARCHITECTURE.md - POST /v1/agents/code-review
    """
    return AgentResponse(
        status="success",
        result={
            "findings": [],
            "summary": "Stub service - no actual code review performed",
            "score": 100,
        },
        message="Stub service response",
    )


@app.post("/v1/agents/architecture/run", response_model=AgentResponse)
async def architecture_analysis(request: AgentRequest):
    """
    Stub architecture analysis endpoint.
    
    Reference: ai-agents/docs/ARCHITECTURE.md - POST /v1/agents/architecture
    """
    return AgentResponse(
        status="success",
        result={
            "patterns": [],
            "concerns": [],
            "recommendations": [],
            "summary": "Stub service - no actual architecture analysis performed",
        },
        message="Stub service response",
    )


@app.post("/v1/agents/doc-generate/run", response_model=AgentResponse)
async def doc_generate(request: AgentRequest):
    """
    Stub documentation generation endpoint.
    
    Reference: ai-agents/docs/ARCHITECTURE.md - POST /v1/agents/doc-generate
    """
    return AgentResponse(
        status="success",
        result={
            "documentation": "# Stub Documentation\n\nNo actual documentation generated.",
            "format": request.format,
        },
        message="Stub service response",
    )
