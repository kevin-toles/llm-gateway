# Docker Troubleshooting Guide

## WBS 1.2.4.4.6 - Known Issues and Solutions

### Issue 1: Docker Daemon Not Running

**Error Message:**
```
Cannot connect to the Docker daemon at unix:///Users/kevintoles/.docker/run/docker.sock. 
Is the docker daemon running?
```

**Solution (macOS):**
1. Open Docker Desktop application
2. Wait for Docker to fully start (whale icon stops animating)
3. Verify with: `docker info`

**Alternative (CLI):**
```bash
# If using Colima instead of Docker Desktop
colima start

# Verify daemon is running
docker ps
```

---

### Issue 2: Deprecated `version` Attribute Warning

**Warning Message:**
```
WARN[0000] docker-compose.yml: the attribute `version` is obsolete, 
it will be ignored, please remove it to avoid potential confusion
```

**Status:** Non-breaking warning. The `version` field is maintained for backward compatibility with older docker-compose versions but is ignored by Compose V2.

**Resolution:** Can optionally remove `version: '3.8'` from compose files, but not required.

---

## Validation Status (WBS 1.2.4.4)

| Task | Status | Notes |
|------|--------|-------|
| 1.2.4.4.1 Validate compose files | ✅ PASS | All 3 files valid |
| 1.2.4.4.2 Full stack startup | ⏸️ PENDING | Requires Docker daemon |
| 1.2.4.4.3 Health endpoint | ⏸️ PENDING | Requires running stack |
| 1.2.4.4.4 Redis connectivity | ⏸️ PENDING | Requires running stack |
| 1.2.4.4.5 Graceful shutdown | ⏸️ PENDING | Requires running stack |
| 1.2.4.4.6 Document issues | ✅ DONE | This file |

---

## Post-Docker Startup Validation Commands

Once Docker daemon is running, execute these commands to complete WBS 1.2.4.4:

```bash
# Navigate to project
cd /Users/kevintoles/POC/llm-gateway

# 1.2.4.4.2 - Start full stack
docker-compose -f deploy/docker/docker-compose.yml up -d

# Wait for services to be healthy
docker-compose -f deploy/docker/docker-compose.yml ps

# 1.2.4.4.3 - Verify health endpoint
curl -s http://localhost:8080/health | jq .

# 1.2.4.4.4 - Verify Redis connectivity
# Issue 26 Fix (Comp_Static_Analysis_Report_20251203.md):
# redis-cli is NOT installed in llm-gateway container, use redis container instead
docker exec llm-gateway-redis redis-cli ping

# Alternative: Check gateway logs for Redis connection
docker logs llm-gateway 2>&1 | grep -i redis

# 1.2.4.4.5 - Test graceful shutdown
docker-compose -f deploy/docker/docker-compose.yml down

# Verify all containers stopped
docker ps -a | grep llm-gateway
```

---

## Environment Setup (Required Before First Run)

The docker-compose.yml references a `.env` file for API keys. Follow these steps:

### Step 1: Create .env File

```bash
# Navigate to the docker compose directory
cd /Users/kevintoles/POC/llm-gateway/deploy/docker

# Copy the example file to create your .env
cp ../../.env.example .env
```

### Step 2: Configure API Keys

Edit the `.env` file with your actual API keys:

```bash
# Open in your editor
nano .env
# Or
code .env
```

Required variables:
```env
# Provider API Keys (at least one required)
LLM_GATEWAY_ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_GATEWAY_OPENAI_API_KEY=sk-your-key-here

# Optional: Override default provider
LLM_GATEWAY_DEFAULT_PROVIDER=anthropic
LLM_GATEWAY_DEFAULT_MODEL=claude-3-sonnet-20240229
```

### Step 3: Verify Setup

```bash
# Ensure .env exists and has content
cat .env | grep -v "^#" | grep -v "^$"
```

> ⚠️ **Security Note:** Never commit `.env` files to git. The `.gitignore` already excludes them.

---

## Development Environment Startup

```bash
# Start with hot-reload (development)
docker-compose -f deploy/docker/docker-compose.yml \
               -f deploy/docker/docker-compose.dev.yml up -d

# View logs
docker-compose -f deploy/docker/docker-compose.yml \
               -f deploy/docker/docker-compose.dev.yml logs -f
```

---

## Test Environment Startup

```bash
# Run tests in isolated environment
docker-compose -f deploy/docker/docker-compose.test.yml run --rm tests

# View test results
cat test-results/junit.xml
```

---

## Consumer Integration (llm-document-enhancer)

### WBS 3.1.3.2 - Document Enhancer Docker Integration

The llm-document-enhancer service connects to the gateway via the shared `llm-network`. There are two deployment modes:

#### Mode 1: Standalone (Gateway included in document-enhancer stack)

```bash
# In llm-document-enhancer directory
cd /Users/kevintoles/POC/llm-document-enhancer

# Start full stack (includes gateway and redis)
docker compose up -d

# Verify all services
docker compose ps
```

#### Mode 2: External Gateway (Gateway already running)

```bash
# First, ensure llm-gateway is running
cd /Users/kevintoles/POC/llm-gateway
docker compose up -d

# Then start document-enhancer with external gateway config
cd /Users/kevintoles/POC/llm-document-enhancer
docker compose -f docker-compose.external.yml up document-enhancer -d
```

### Verifying Document Enhancer Connectivity

```bash
# Check document-enhancer can reach gateway
docker exec llm-document-enhancer curl -s http://llm-gateway:8080/health

# Check environment variables are set
docker exec llm-document-enhancer env | grep DOC_ENHANCER

# Expected output:
# DOC_ENHANCER_GATEWAY_URL=http://llm-gateway:8080
# DOC_ENHANCER_GATEWAY_ENABLED=true
# DOC_ENHANCER_GATEWAY_TIMEOUT=30.0
# DOC_ENHANCER_GATEWAY_SESSION_TTL=3600.0
```

### Network Troubleshooting

```bash
# Verify llm-network exists
docker network ls | grep llm-network

# Inspect network to see connected containers
docker network inspect llm-network

# If network doesn't exist, create it manually
docker network create llm-network

# Then start services
docker compose up -d
```

### Common Consumer Issues

**Issue: Document enhancer can't reach gateway**
```
ConnectionError: Cannot connect to http://llm-gateway:8080
```

**Solutions:**
1. Verify both services are on the same network: `docker network inspect llm-network`
2. Check gateway is healthy: `docker exec llm-gateway curl -s localhost:8080/health`
3. Ensure container names match (gateway should be `llm-gateway`)

**Issue: Gateway URL not set**
```
ValueError: DOC_ENHANCER_GATEWAY_URL must start with http:// or https://
```

**Solution:** Ensure `.env` file exists in llm-document-enhancer directory or environment variables are set in docker-compose.yml.

---

## Common Docker Commands Reference

```bash
# Check container status
docker-compose -f deploy/docker/docker-compose.yml ps

# View container logs
docker-compose -f deploy/docker/docker-compose.yml logs llm-gateway

# Enter running container
docker exec -it llm-gateway /bin/sh

# Rebuild without cache
docker-compose -f deploy/docker/docker-compose.yml build --no-cache

# Remove all volumes (clean slate)
docker-compose -f deploy/docker/docker-compose.yml down -v
```

---

## Port Conflicts

If port 8080 or 6379 is already in use:

```bash
# Find what's using the port
lsof -i :8080
lsof -i :6379

# Kill the process
kill -9 <PID>

# Or modify docker-compose.yml ports
# ports:
#   - "8081:8080"  # Use different host port
```

---

*Document created: December 1, 2025*
*Last updated: December 4, 2025*
*WBS Reference: 1.2.4.4.6, 3.1.3.2*
