# ==============================================================================
# LLM Gateway - Production Dockerfile
# ==============================================================================
# Multi-stage build for optimized production image
# See docs/DEPLOYMENT_IMPLEMENTATION_PLAN.md Section 1.2.1 for implementation
# ==============================================================================

# ==============================================================================
# Stage 1: Builder
# ==============================================================================
FROM python:3.11-slim-bookworm AS builder

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ==============================================================================
# Stage 2: Production Runtime
# ==============================================================================
FROM python:3.11-slim-bookworm AS production

# Labels (OCI standard)
LABEL org.opencontainers.image.title="llm-gateway" \
      org.opencontainers.image.description="LLM Gateway Microservice - Unified API for LLM interactions" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="kevin-toles" \
      org.opencontainers.image.source="https://github.com/kevin-toles/llm-gateway"

# Security: Run as non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Runtime environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH" \
    # Application defaults (override via Kubernetes ConfigMap)
    LLM_GATEWAY_PORT=8080 \
    LLM_GATEWAY_LOG_LEVEL=INFO \
    LLM_GATEWAY_WORKERS=4

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# ==============================================================================
# Stage 3: Application Setup
# ==============================================================================

# Set working directory
WORKDIR /app

# Copy application code with correct ownership
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup scripts/ ./scripts/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Switch to non-root user
USER appuser

# ==============================================================================
# Stage 4: Container Configuration
# ==============================================================================

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${LLM_GATEWAY_PORT}/health || exit 1

# Expose port (documentation)
EXPOSE 8080

# Entrypoint
ENTRYPOINT ["scripts/entrypoint.sh"]

# Issue 34 Fix (Comp_Static_Analysis_Report_20251203.md):
# Use shell form CMD to allow environment variable expansion.
# Previous exec form ["uvicorn", ..., "--port", "8080"] ignored LLM_GATEWAY_PORT env var.
CMD uvicorn src.main:app --host 0.0.0.0 --port ${LLM_GATEWAY_PORT:-8080} --workers ${LLM_GATEWAY_WORKERS:-4}
