# ==============================================================================
# AI Agents Service - Stub for Local Development
# ==============================================================================
# This stub provides health endpoints for docker-compose integration testing.
# Replace with actual ai-agents build when available.
# Reference: docs/ARCHITECTURE.md - Service Discovery Patterns
# Reference: ai-agents/docs/ARCHITECTURE.md - Agent endpoints
# WBS: 3.4.1.1.4
# ==============================================================================

FROM python:3.11-slim-bookworm

# Prevent bytecode and buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install FastAPI and uvicorn
RUN pip install --no-cache-dir fastapi uvicorn

# Create app directory
WORKDIR /app

# Copy stub application
COPY app.py .

# Non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser
USER appuser

# Expose port
EXPOSE 8082

# Health check matching ai-agents/docs/ARCHITECTURE.md pattern
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8082"]
