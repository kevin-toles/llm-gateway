#!/bin/bash
# ==============================================================================
# LLM Gateway - Container Entrypoint
# ==============================================================================
# See docs/DEPLOYMENT_IMPLEMENTATION_PLAN.md Section 1.2.3 for implementation
# ==============================================================================

set -e

# ==============================================================================
# Startup Logging
# ==============================================================================
echo "=============================================="
echo "  LLM Gateway - Starting Up"
echo "=============================================="
echo "Environment: ${LLM_GATEWAY_ENV:-production}"
echo "Port: ${LLM_GATEWAY_PORT:-8080}"
echo "Log Level: ${LLM_GATEWAY_LOG_LEVEL:-INFO}"
echo "Workers: ${LLM_GATEWAY_WORKERS:-4}"
echo "=============================================="

# ==============================================================================
# Dependency Wait Logic
# ==============================================================================

# Wait for Redis if configured
if [ -n "$LLM_GATEWAY_REDIS_URL" ]; then
    echo "Redis URL configured: $LLM_GATEWAY_REDIS_URL"
    echo "Waiting for Redis to be available..."
    
    # Extract host and port from Redis URL
    # Format: redis://host:port or redis://host:port/db
    REDIS_HOST=$(echo "$LLM_GATEWAY_REDIS_URL" | sed -e 's|redis://||' -e 's|:.*||')
    REDIS_PORT=$(echo "$LLM_GATEWAY_REDIS_URL" | sed -e 's|redis://[^:]*:||' -e 's|/.*||')
    REDIS_PORT=${REDIS_PORT:-6379}
    
    MAX_RETRIES=${REDIS_WAIT_RETRIES:-30}
    RETRY_INTERVAL=${REDIS_WAIT_INTERVAL:-1}
    
    for i in $(seq 1 $MAX_RETRIES); do
        if nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
            echo "Redis is available at ${REDIS_HOST}:${REDIS_PORT}"
            break
        fi
        
        if [ $i -eq $MAX_RETRIES ]; then
            echo "WARNING: Redis not available after ${MAX_RETRIES} attempts. Continuing anyway..."
        else
            echo "Waiting for Redis... (attempt $i/$MAX_RETRIES)"
            sleep "$RETRY_INTERVAL"
        fi
    done
else
    echo "No Redis URL configured, skipping Redis wait"
fi

echo ""
echo "Starting application..."
echo "=============================================="

# ==============================================================================
# Execute Main Command
# ==============================================================================
# Using exec replaces this script with the main process
# This ensures proper signal handling (SIGTERM, SIGINT, etc.)
exec "$@"
