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

# 1.2.4.4.4 - Verify Redis connectivity from gateway
docker exec llm-gateway redis-cli -h redis -p 6379 ping

# Alternative: Check gateway logs for Redis connection
docker logs llm-gateway 2>&1 | grep -i redis

# 1.2.4.4.5 - Test graceful shutdown
docker-compose -f deploy/docker/docker-compose.yml down

# Verify all containers stopped
docker ps -a | grep llm-gateway
```

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
*WBS Reference: 1.2.4.4.6*
