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
    echo "Redis URL configured: ${LLM_GATEWAY_REDIS_URL%%@*}@***" # Mask password in logs
    echo "Waiting for Redis to be available..."
    
    # Issue 23 Fix (Comp_Static_Analysis_Report_20251203.md):
    # Robust Redis URL parsing that handles:
    # - redis://host:port
    # - redis://:password@host:port
    # - redis://user:password@host:port
    # - redis://host:port/db
    # - IPv6: redis://[::1]:6379
    
    # Remove scheme
    REDIS_URL_NO_SCHEME="${LLM_GATEWAY_REDIS_URL#redis://}"
    REDIS_URL_NO_SCHEME="${REDIS_URL_NO_SCHEME#rediss://}"
    
    # Remove database suffix (e.g., /0)
    REDIS_URL_NO_DB="${REDIS_URL_NO_SCHEME%%/*}"
    
    # Remove auth (everything before @)
    if echo "$REDIS_URL_NO_DB" | grep -q '@'; then
        REDIS_HOST_PORT="${REDIS_URL_NO_DB##*@}"
    else
        REDIS_HOST_PORT="$REDIS_URL_NO_DB"
    fi
    
    # Handle IPv6 addresses (e.g., [::1]:6379)
    if echo "$REDIS_HOST_PORT" | grep -q '^\['; then
        # IPv6: extract host from brackets and port after ]
        REDIS_HOST=$(echo "$REDIS_HOST_PORT" | sed -n 's/^\[\([^]]*\)\].*/\1/p')
        REDIS_PORT=$(echo "$REDIS_HOST_PORT" | sed -n 's/^\[[^]]*\]:\([0-9]*\)/\1/p')
    else
        # IPv4 or hostname: split on last colon
        REDIS_HOST="${REDIS_HOST_PORT%:*}"
        REDIS_PORT="${REDIS_HOST_PORT##*:}"
    fi
    
    # Default port if not specified
    if [ "$REDIS_HOST" = "$REDIS_PORT" ] || [ -z "$REDIS_PORT" ]; then
        REDIS_PORT=6379
    fi
    
    # Validate parsed values
    if [ -z "$REDIS_HOST" ]; then
        echo "ERROR: Could not parse Redis host from URL"
        exit 1
    fi
    
    echo "Parsed Redis connection: host=${REDIS_HOST}, port=${REDIS_PORT}"
    
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
