#!/bin/bash
# ==============================================================================
# LLM Gateway - Start Script
# ==============================================================================
# Convenience script for starting the application
# See docs/DEPLOYMENT_IMPLEMENTATION_PLAN.md for full implementation
# ==============================================================================

set -e

# Placeholder - Full implementation in WBS 1.2

PORT=${LLM_GATEWAY_PORT:-8080}
WORKERS=${LLM_GATEWAY_WORKERS:-4}

echo "Starting LLM Gateway on port ${PORT} with ${WORKERS} workers..."

exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT}" --workers "${WORKERS}"
