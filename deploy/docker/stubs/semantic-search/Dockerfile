# ==============================================================================
# Semantic Search Service - Stub for Local Development
# ==============================================================================
# This stub provides health endpoints for docker-compose integration testing.
# Replace with actual semantic-search-service build when available.
# Reference: docs/ARCHITECTURE.md - Service Discovery Patterns
# WBS: 3.4.1.1.3
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
EXPOSE 8081

# Health check matching ARCHITECTURE.md pattern
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
