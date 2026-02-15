#!/bin/bash
# LLM Gateway Rebuild with Gemini Support
# Double-click this file to rebuild and restart the gateway

cd "$(dirname "$0")"

echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║     REBUILDING LLM GATEWAY WITH GEMINI SUPPORT                        ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""

# Stop existing container
echo "━━━ Stopping existing container... ━━━"
docker stop llm-gateway-standalone 2>/dev/null || true
docker rm llm-gateway-standalone 2>/dev/null || true

# Rebuild
echo ""
echo "━━━ Rebuilding Docker image... ━━━"
docker-compose build --no-cache

# Check for GEMINI_API_KEY
if [ -z "$GEMINI_API_KEY" ]; then
    echo ""
    echo "⚠️  GEMINI_API_KEY not set in environment"
    echo "   Set it in your shell: export GEMINI_API_KEY='your-key'"
    echo "   Or add to .env file"
fi

# Start
echo ""
echo "━━━ Starting LLM Gateway... ━━━"
docker-compose up -d

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "✅ LLM Gateway rebuilt and started!"
echo "   Health check: http://localhost:8080/health"
echo "   Gemini endpoint: POST http://localhost:8080/v1/chat/completions"
echo "═══════════════════════════════════════════════════════════════════════"

# Keep terminal open
read -p "Press Enter to close..."
