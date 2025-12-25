"""
WBS 3.5.2.1: Health Endpoint Integration Tests

This module tests the health endpoints against live Docker services.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3297-3302 - WBS 3.5.2.1
- ARCHITECTURE.md: Lines 196-215 - Health endpoint documentation
- GUIDELINES pp. 155-157: "high and low gear" testing philosophy
- Building Microservices (Newman) pp. 273-275: Service metrics and synthetic monitoring

TDD Phase: RED - These tests define expected health endpoint behavior against live services.

WBS Coverage:
- 3.5.2.1.1: Create tests/integration/test_health.py
- 3.5.2.1.2: Test /health returns 200
- 3.5.2.1.3: Test /health/ready returns 200 when all deps up
- 3.5.2.1.4: Test /health/ready returns 503 when Redis down
- 3.5.2.1.5: Test /metrics returns Prometheus format
"""

import pytest


# =============================================================================
# WBS 3.5.2.1.2: Test /health returns 200
# =============================================================================


class TestHealthEndpoint:
    """
    WBS 3.5.2.1.2: Test basic health check endpoint.
    
    Pattern: Synthetic monitoring (Newman pp. 273-275)
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_health_returns_200(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.2: /health endpoint should return 200 OK.
        
        RED: Test expects health endpoint to return 200 when gateway is running.
        """
        response = gateway_client_sync.get("/health")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /health, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_health_returns_expected_schema(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.2: /health should return expected JSON schema.
        
        Schema: {"status": "healthy", "version": "<version>"}
        Reference: ARCHITECTURE.md health endpoint documentation.
        """
        response = gateway_client_sync.get("/health")
        data = response.json()
        
        assert "status" in data, "Health response should have 'status' field"
        assert "version" in data, "Health response should have 'version' field"
        assert data["status"] == "healthy", (
            f"Expected status 'healthy', got '{data['status']}'"
        )


# =============================================================================
# WBS 3.5.2.1.3: Test /health/ready returns 200 when all deps up
# =============================================================================


class TestReadyEndpoint:
    """
    WBS 3.5.2.1.3: Test readiness check endpoint.
    
    Pattern: Readiness probes for Kubernetes (Newman pp. 274)
    Reference: ARCHITECTURE.md Lines 282-304 - Graceful Degradation
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_ready_returns_200_when_healthy(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.3: /health/ready returns 200 when all dependencies are up.
        
        RED: Test expects ready endpoint to return 200 with full-stack profile.
        """
        response = gateway_client_sync.get("/health/ready")
        
        # With full-stack profile, all deps should be healthy
        assert response.status_code == 200, (
            f"Expected 200 OK from /health/ready, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_ready_returns_checks_schema(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.3: /health/ready returns checks for each dependency.
        
        Schema: {"status": "ready", "checks": {"redis": true, ...}}
        Reference: ARCHITECTURE.md health check integration.
        """
        response = gateway_client_sync.get("/health/ready")
        data = response.json()
        
        assert "status" in data, "Ready response should have 'status' field"
        assert "checks" in data, "Ready response should have 'checks' field"
        assert isinstance(data["checks"], dict), "'checks' should be a dict"

    @pytest.mark.integration
    @pytest.mark.docker
    def test_ready_checks_redis(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.3: /health/ready includes Redis check.
        
        Reference: ARCHITECTURE.md - Redis is required dependency.
        """
        response = gateway_client_sync.get("/health/ready")
        data = response.json()
        
        assert "redis" in data.get("checks", {}), (
            "Ready response should include 'redis' check"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_ready_checks_semantic_search(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.3: /health/ready includes semantic-search check.
        
        Reference: ARCHITECTURE.md - semantic-search is optional dependency.
        """
        response = gateway_client_sync.get("/health/ready")
        data = response.json()
        
        # semantic_search should be in checks (may be true or false)
        assert "semantic_search" in data.get("checks", {}), (
            "Ready response should include 'semantic_search' check"
        )


# =============================================================================
# WBS 3.5.2.1.4: Test /health/ready returns 503 when Redis down
# =============================================================================


class TestReadyEndpointDegraded:
    """
    WBS 3.5.2.1.4: Test readiness when dependencies are down.
    
    Pattern: Graceful degradation (Newman pp. 352-353)
    Reference: ARCHITECTURE.md Lines 340-345 - Degraded status handling.
    
    Note: These tests require ability to simulate Redis being down,
    which may require special test configuration or mocking.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    @pytest.mark.skip(reason="Requires Redis down simulation - manual verification")
    def test_ready_returns_503_when_redis_down(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.4: /health/ready returns 503 when Redis unavailable.
        
        RED: Test expects 503 Service Unavailable when Redis is down.
        This test is skipped by default as it requires Redis to be stopped.
        
        Manual Test Steps:
        1. docker-compose stop redis
        2. Run: pytest tests/integration/test_health.py::TestReadyEndpointDegraded -v
        3. docker-compose start redis
        """
        response = gateway_client_sync.get("/health/ready")
        
        assert response.status_code == 503, (
            f"Expected 503 when Redis down, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    @pytest.mark.skip(reason="Requires Redis down simulation - manual verification")
    def test_ready_returns_not_ready_status_when_redis_down(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.4: /health/ready response shows not_ready status.
        
        Reference: ARCHITECTURE.md - Service unavailable returns 503 with not_ready.
        """
        response = gateway_client_sync.get("/health/ready")
        data = response.json()
        
        assert data.get("status") == "not_ready", (
            f"Expected status 'not_ready', got '{data.get('status')}'"
        )
        assert data.get("checks", {}).get("redis") is False, (
            "Redis check should be False when Redis is down"
        )


# =============================================================================
# WBS 3.5.2.1.5: Test /metrics returns Prometheus format
# =============================================================================


class TestMetricsEndpoint:
    """
    WBS 3.5.2.1.5: Test Prometheus metrics endpoint.
    
    Pattern: Service metrics exposure (Newman pp. 273-275)
    Reference: GUIDELINES line 2309 - "domain-specific metrics in business-relevant terms"
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_metrics_returns_200(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.5: /metrics endpoint should return 200 OK.
        """
        response = gateway_client_sync.get("/metrics")
        
        assert response.status_code == 200, (
            f"Expected 200 OK from /metrics, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_metrics_returns_prometheus_format(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.5: /metrics returns Prometheus text format.
        
        Prometheus format example:
        # HELP llm_gateway_requests_total Total requests
        # TYPE llm_gateway_requests_total counter
        llm_gateway_requests_total 0
        """
        response = gateway_client_sync.get("/metrics")
        content = response.text
        
        # Prometheus format indicators
        assert "# HELP" in content or "# TYPE" in content or "llm_gateway" in content, (
            "Metrics response should be in Prometheus format with HELP/TYPE comments"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_metrics_content_type(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.5: /metrics should return text/plain content type.
        
        Prometheus scraper expects text/plain or text/plain; version=0.0.4
        """
        response = gateway_client_sync.get("/metrics")
        content_type = response.headers.get("content-type", "")
        
        assert "text/plain" in content_type, (
            f"Expected text/plain content type, got '{content_type}'"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_metrics_includes_request_count(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.5: /metrics includes request count metric.
        
        Reference: GUIDELINES - request count is basic metric.
        """
        response = gateway_client_sync.get("/metrics")
        content = response.text
        
        # Check for request-related metric
        assert "requests" in content.lower(), (
            "Metrics should include request count metric"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_metrics_includes_error_count(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.1.5: /metrics includes error count metric.
        
        Reference: Newman pp. 273 - error rates are key metrics.
        """
        response = gateway_client_sync.get("/metrics")
        content = response.text
        
        # Check for error-related metric
        assert "error" in content.lower(), (
            "Metrics should include error count metric"
        )
