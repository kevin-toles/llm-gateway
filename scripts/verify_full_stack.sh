#!/bin/bash
# ==============================================================================
# Full Stack Docker Compose Verification Script
# ==============================================================================
# WBS: 3.4.1.2 Service Health Verification
# WBS: 3.4.1.3 Service Communication Verification
# Reference: docs/DEPLOYMENT_IMPLEMENTATION_PLAN.md
# Reference: docs/ARCHITECTURE.md lines 300-330 - Health Check Integration
# ==============================================================================
#
# Usage:
#   ./scripts/verify_full_stack.sh
#
# Prerequisites:
#   - Docker daemon running
#   - docker-compose up -d completed
# ==============================================================================

set -e

echo "=============================================="
echo "LLM Gateway Full Stack Verification"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function
check_service() {
    local service=$1
    local url=$2
    local expected=$3
    
    echo -n "  Checking $service at $url... "
    
    response=$(curl -sf "$url" 2>/dev/null) || {
        echo -e "${RED}FAILED${NC}"
        return 1
    }
    
    if echo "$response" | grep -q "$expected"; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}UNEXPECTED RESPONSE${NC}"
        return 1
    fi
}

echo ""
echo "WBS 3.4.1.2: Service Health Verification"
echo "----------------------------------------------"

# WBS 3.4.1.2.1: Wait for services to be healthy
echo "Waiting for services to be healthy..."
docker-compose ps --format table 2>/dev/null || {
    echo -e "${RED}Error: Docker Compose services not running${NC}"
    echo "Run: docker-compose up -d"
    exit 1
}

# WBS 3.4.1.2.2: Verify Redis
echo ""
echo "Checking Redis..."
docker exec llm-gateway-redis redis-cli ping | grep -q "PONG" && \
    echo -e "  Redis: ${GREEN}PONG${NC}" || \
    echo -e "  Redis: ${RED}FAILED${NC}"

# WBS 3.4.1.2.3: Verify semantic-search
echo ""
echo "Checking semantic-search..."
check_service "health" "http://localhost:8081/health" "healthy"
check_service "ready" "http://localhost:8081/health/ready" "ready"

# WBS 3.4.1.2.4: Verify ai-agents
echo ""
echo "Checking ai-agents..."
check_service "health" "http://localhost:8082/health" "healthy"
check_service "ready" "http://localhost:8082/health/ready" "ready"

# WBS 3.4.1.2.5: Verify llm-gateway
echo ""
echo "Checking llm-gateway..."
check_service "health" "http://localhost:8080/health" "healthy"

# WBS 3.4.1.2.6: Verify llm-gateway readiness
check_service "ready" "http://localhost:8080/health/ready" "ready"

echo ""
echo "WBS 3.4.1.3: Service Communication Verification"
echo "----------------------------------------------"

# WBS 3.4.1.3.1: From gateway container, curl semantic-search
echo ""
echo "Checking inter-service communication..."
echo -n "  llm-gateway -> semantic-search: "
docker exec llm-gateway curl -sf http://semantic-search:8081/health 2>/dev/null | grep -q "healthy" && \
    echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAILED${NC}"

# WBS 3.4.1.3.2: From gateway container, curl ai-agents
echo -n "  llm-gateway -> ai-agents: "
docker exec llm-gateway curl -sf http://ai-agents:8082/health 2>/dev/null | grep -q "healthy" && \
    echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAILED${NC}"

# WBS 3.4.1.3.3: From gateway container, verify Redis connection
echo -n "  llm-gateway -> redis: "
docker exec llm-gateway curl -sf http://localhost:8080/health/ready 2>/dev/null | grep -q "redis" && \
    echo -e "${GREEN}OK${NC}" || echo -e "${YELLOW}CHECK MANUALLY${NC}"

# WBS 3.4.1.3.4: Test tool execution (requires actual implementation)
echo ""
echo "Tool execution tests (stub services):"
echo -n "  search_corpus tool: "
curl -sf -X POST http://localhost:8081/v1/search -H "Content-Type: application/json" \
    -d '{"query": "test"}' 2>/dev/null | grep -q "Stub" && \
    echo -e "${GREEN}STUB RESPONDING${NC}" || echo -e "${YELLOW}N/A${NC}"

echo -n "  code_review tool: "
curl -sf -X POST http://localhost:8082/v1/agents/code-review/run \
    -H "Content-Type: application/json" \
    -d '{"code": "print(1)", "language": "python"}' 2>/dev/null | grep -q "Stub" && \
    echo -e "${GREEN}STUB RESPONDING${NC}" || echo -e "${YELLOW}N/A${NC}"

echo ""
echo "=============================================="
echo "Verification Complete"
echo "=============================================="
echo ""
echo "WBS 3.4.1.2.7: Startup Sequence Documentation"
echo "----------------------------------------------"
echo "Service startup order (via depends_on):"
echo "  1. redis (no dependencies)"
echo "  2. semantic-search (no dependencies)"
echo "  3. ai-agents (depends on: semantic-search)"
echo "  4. llm-gateway (depends on: redis, semantic-search, ai-agents)"
echo ""
echo "Estimated startup time: ~30-60 seconds"
echo "Health check intervals: 10s (redis/search/agents), 30s (gateway)"
