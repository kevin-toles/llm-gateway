#!/bin/bash
# Rebuild and restart the container with new code
set -e
cd "$(dirname "$0")"
echo "🔄 Rebuilding llm-gateway..."
docker-compose -f docker-compose.dev.yml up -d --build
echo "✅ Done."
