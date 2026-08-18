#!/bin/bash
# ==============================================================================
# LLM Gateway - Dockerfile Test Script (TDD)
# ==============================================================================
# WBS 1.2.1.5 - Docker Image Validation Tests
# Run with: ./tests/docker/test_dockerfile.sh
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

IMAGE_NAME="llm-gateway"
IMAGE_TAG="test"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
MAX_IMAGE_SIZE_MB=500

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# ==============================================================================
# Test Helper Functions
# ==============================================================================

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

# ==============================================================================
# Test 1.2.1.5.1: Verify image builds successfully
# ==============================================================================
test_image_builds() {
    log_test "Testing image builds successfully..."
    
    if docker build -t "${FULL_IMAGE}" . > /dev/null 2>&1; then
        log_pass "Image builds successfully"
        return 0
    else
        log_fail "Image failed to build"
        return 1
    fi
}

# ==============================================================================
# Test 1.2.1.5.2: Verify /health endpoint responds
# ==============================================================================
test_health_endpoint() {
    log_test "Testing /health endpoint responds..."
    
    # Start container in background
    CONTAINER_ID=$(docker run -d --rm -p 8080:8080 "${FULL_IMAGE}" 2>/dev/null || echo "")
    
    if [ -z "$CONTAINER_ID" ]; then
        log_fail "Failed to start container"
        return 1
    fi
    
    # Wait for container to be ready
    sleep 5
    
    # Test health endpoint
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null || echo "000")
    
    # Cleanup
    docker stop "$CONTAINER_ID" > /dev/null 2>&1 || true
    
    if [ "$HTTP_CODE" = "200" ]; then
        log_pass "/health endpoint returns 200"
        return 0
    else
        # Note: This will fail until we implement src/main.py - expected in TDD RED phase
        log_fail "/health endpoint returned $HTTP_CODE (expected 200)"
        return 1
    fi
}

# ==============================================================================
# Test 1.2.1.5.3: Verify non-root user
# ==============================================================================
test_nonroot_user() {
    log_test "Testing container runs as non-root user..."
    
    USER=$(docker run --rm "${FULL_IMAGE}" whoami 2>/dev/null || echo "error")
    
    if [ "$USER" = "appuser" ]; then
        log_pass "Container runs as 'appuser' (non-root)"
        return 0
    else
        log_fail "Container runs as '$USER' (expected 'appuser')"
        return 1
    fi
}

# ==============================================================================
# Test 1.2.1.5.4: Verify image size < 500MB
# ==============================================================================
test_image_size() {
    log_test "Testing image size < ${MAX_IMAGE_SIZE_MB}MB..."
    
    # Get image size in bytes
    SIZE_BYTES=$(docker image inspect "${FULL_IMAGE}" --format='{{.Size}}' 2>/dev/null || echo "0")
    SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
    
    if [ "$SIZE_MB" -lt "$MAX_IMAGE_SIZE_MB" ]; then
        log_pass "Image size is ${SIZE_MB}MB (< ${MAX_IMAGE_SIZE_MB}MB)"
        return 0
    else
        log_fail "Image size is ${SIZE_MB}MB (expected < ${MAX_IMAGE_SIZE_MB}MB)"
        return 1
    fi
}

# ==============================================================================
# Test: Verify Python and dependencies available
# ==============================================================================
test_python_available() {
    log_test "Testing Python is available..."
    
    PYTHON_VERSION=$(docker run --rm "${FULL_IMAGE}" python --version 2>/dev/null || echo "error")
    
    if [[ "$PYTHON_VERSION" == *"Python 3.11"* ]]; then
        log_pass "Python 3.11 is available: $PYTHON_VERSION"
        return 0
    else
        log_fail "Python not available or wrong version: $PYTHON_VERSION"
        return 1
    fi
}

# ==============================================================================
# Test: Verify entrypoint script exists and is executable
# ==============================================================================
test_entrypoint_exists() {
    log_test "Testing entrypoint script exists and is executable..."
    
    RESULT=$(docker run --rm "${FULL_IMAGE}" test -x /app/scripts/entrypoint.sh && echo "ok" || echo "fail")
    
    if [ "$RESULT" = "ok" ]; then
        log_pass "Entrypoint script is executable"
        return 0
    else
        log_fail "Entrypoint script not found or not executable"
        return 1
    fi
}

# ==============================================================================
# Main Test Runner
# ==============================================================================
main() {
    echo "=============================================="
    echo "LLM Gateway - Dockerfile Tests"
    echo "=============================================="
    echo ""
    
    # Check Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}ERROR: Docker daemon is not running${NC}"
        exit 1
    fi
    
    # Run tests
    test_image_builds || true
    test_nonroot_user || true
    test_image_size || true
    test_python_available || true
    test_entrypoint_exists || true
    # test_health_endpoint || true  # Uncomment when src/main.py is implemented
    
    echo ""
    echo "=============================================="
    echo "Test Results"
    echo "=============================================="
    echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
    echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
    echo ""
    
    if [ "$TESTS_FAILED" -gt 0 ]; then
        echo -e "${YELLOW}Note: Some tests may fail until Stage 2 (Implementation) is complete${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
}

main "$@"
