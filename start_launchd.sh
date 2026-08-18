#!/bin/bash
# Launchd startup script for llm-gateway.
# Sources .env so API keys are not embedded in the plist.
# Reclaims port 8080 if a stale process holds it (prevents crash loop).
/usr/sbin/lsof -ti:8080 | xargs kill -9 2>/dev/null || true
sleep 1
set -a
# shellcheck disable=SC1091
source "$(dirname "$0")/.env" 2>/dev/null || true
set +a
cd "$(dirname "$0")"
exec .venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8080
