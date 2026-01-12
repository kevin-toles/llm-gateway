"""
Tests for CMS Routing - WBS-CMS11: Gateway Integration

TDD RED Phase: These tests define expected behavior for CMS integration.

Reference Documents:
- WBS_CONTEXT_MANAGEMENT_SERVICE.md: CMS11 Acceptance Criteria
- Architecture Doc → Integration Architecture

Acceptance Criteria Covered:
- AC-11.1: Gateway routes Tier 2+ requests to CMS
- AC-11.2: X-CMS-Mode header protocol implemented
- AC-11.3: X-CMS-Routed response header set
- AC-11.4: Tier 3+ returns 503 when CMS unavailable
- AC-11.5: Fast token estimation in Gateway
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# =============================================================================
# Test Data Constants
# =============================================================================

# Model context limits for tier calculation
MODEL_CONTEXT_LIMITS = {
    "qwen3-8b": 8192,
    "codellama-7b": 16384,
    "deepseek-coder-v2-lite": 131072,
    "llama-3.2-3b": 8192,
    "gpt-4": 8192,  # Default
}


# =============================================================================
# TestTierDetection (AC-11.1)
# =============================================================================

class TestTierDetection:
    """Test tier detection and routing logic."""
    
    def test_tier_1_for_small_request(self):
        """Tier 1: Token utilization < 25% - bypass CMS."""
        from src.api.routes.cms_routing import calculate_tier
        
        # 500 tokens out of 8192 limit = ~6%
        tier = calculate_tier(token_count=500, context_limit=8192)
        assert tier == 1
    
    def test_tier_2_for_medium_request(self):
        """Tier 2: Token utilization 25-50% - validate via CMS."""
        from src.api.routes.cms_routing import calculate_tier
        
        # 3000 tokens out of 8192 limit = ~37%
        tier = calculate_tier(token_count=3000, context_limit=8192)
        assert tier == 2
    
    def test_tier_3_for_large_request(self):
        """Tier 3: Token utilization 50-75% - optimize via CMS."""
        from src.api.routes.cms_routing import calculate_tier
        
        # 5000 tokens out of 8192 limit = ~61%
        tier = calculate_tier(token_count=5000, context_limit=8192)
        assert tier == 3
    
    def test_tier_4_for_critical_request(self):
        """Tier 4: Token utilization > 75% - plan via CMS (chunking)."""
        from src.api.routes.cms_routing import calculate_tier
        
        # 7000 tokens out of 8192 limit = ~85%
        tier = calculate_tier(token_count=7000, context_limit=8192)
        assert tier == 4
    
    def test_tier_boundaries_exact(self):
        """Test exact boundary values."""
        from src.api.routes.cms_routing import calculate_tier
        
        # 25% boundary (2048/8192 = 0.25 exactly)
        assert calculate_tier(token_count=2047, context_limit=8192) == 1  # < 25%
        assert calculate_tier(token_count=2048, context_limit=8192) == 2  # = 25% (in Tier 2)
        
        # 50% boundary (4096/8192 = 0.50 exactly)
        assert calculate_tier(token_count=4095, context_limit=8192) == 2  # < 50%
        assert calculate_tier(token_count=4096, context_limit=8192) == 3  # = 50% (in Tier 3)
        
        # 75% boundary (6144/8192 = 0.75 exactly)
        assert calculate_tier(token_count=6143, context_limit=8192) == 3  # < 75%
        assert calculate_tier(token_count=6144, context_limit=8192) == 4  # = 75% (in Tier 4)
    
    def test_tier_with_zero_tokens(self):
        """Zero tokens should be Tier 1."""
        from src.api.routes.cms_routing import calculate_tier
        
        tier = calculate_tier(token_count=0, context_limit=8192)
        assert tier == 1
    
    def test_tier_exceeds_context(self):
        """Tokens exceeding context should still be Tier 4."""
        from src.api.routes.cms_routing import calculate_tier
        
        tier = calculate_tier(token_count=10000, context_limit=8192)
        assert tier == 4


# =============================================================================
# TestCMSModeHeader (AC-11.2)
# =============================================================================

class TestCMSModeHeader:
    """Test X-CMS-Mode header parsing."""
    
    def test_parse_mode_none(self):
        """X-CMS-Mode: none should bypass CMS."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode("none")
        assert mode == "none"
    
    def test_parse_mode_validate(self):
        """X-CMS-Mode: validate should only validate tokens."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode("validate")
        assert mode == "validate"
    
    def test_parse_mode_optimize(self):
        """X-CMS-Mode: optimize should optimize text."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode("optimize")
        assert mode == "optimize"
    
    def test_parse_mode_plan(self):
        """X-CMS-Mode: plan should do full planning (including chunking)."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode("plan")
        assert mode == "plan"
    
    def test_parse_mode_invalid_defaults_to_auto(self):
        """Invalid mode should default to 'auto'."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode("invalid")
        assert mode == "auto"
    
    def test_parse_mode_missing_defaults_to_auto(self):
        """Missing mode header should default to 'auto'."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        mode = parse_cms_mode(None)
        assert mode == "auto"
    
    def test_parse_mode_case_insensitive(self):
        """Mode parsing should be case-insensitive."""
        from src.api.routes.cms_routing import parse_cms_mode
        
        assert parse_cms_mode("NONE") == "none"
        assert parse_cms_mode("Validate") == "validate"
        assert parse_cms_mode("OPTIMIZE") == "optimize"
        assert parse_cms_mode("Plan") == "plan"


# =============================================================================
# TestCMSModeRouting (AC-11.1, AC-11.2)
# =============================================================================

class TestCMSModeRouting:
    """Test mode affects routing behavior."""
    
    def test_mode_none_bypasses_cms_regardless_of_tier(self):
        """X-CMS-Mode: none should bypass CMS even for Tier 4."""
        from src.api.routes.cms_routing import should_route_to_cms
        
        assert should_route_to_cms(tier=4, mode="none") is False
    
    def test_mode_validate_only_counts_tokens(self):
        """X-CMS-Mode: validate only validates, doesn't optimize."""
        from src.api.routes.cms_routing import get_cms_action
        
        action = get_cms_action(tier=3, mode="validate")
        assert action == "validate"
    
    def test_mode_auto_uses_tier(self):
        """X-CMS-Mode: auto uses tier to determine action."""
        from src.api.routes.cms_routing import get_cms_action
        
        assert get_cms_action(tier=1, mode="auto") == "none"
        assert get_cms_action(tier=2, mode="auto") == "validate"
        assert get_cms_action(tier=3, mode="auto") == "optimize"
        assert get_cms_action(tier=4, mode="auto") == "plan"
    
    def test_mode_override_respects_minimum_tier(self):
        """Explicit mode should be applied even if tier is lower."""
        from src.api.routes.cms_routing import get_cms_action
        
        # User requests optimization on a Tier 1 request
        action = get_cms_action(tier=1, mode="optimize")
        assert action == "optimize"


# =============================================================================
# TestResponseHeaders (AC-11.3)
# =============================================================================

class TestResponseHeaders:
    """Test X-CMS-* response headers."""
    
    def test_build_cms_headers_basic(self):
        """Build response headers with CMS info."""
        from src.api.routes.cms_routing import build_cms_response_headers
        
        headers = build_cms_response_headers(
            routed=True,
            tier=3,
            token_count=5000,
            token_limit=8192,
        )
        
        assert headers["X-CMS-Routed"] == "true"
        assert headers["X-CMS-Tier"] == "3"
        assert headers["X-Token-Count"] == "5000"
        assert headers["X-Token-Limit"] == "8192"
    
    def test_build_cms_headers_with_headroom(self):
        """Headers should include headroom percentage."""
        from src.api.routes.cms_routing import build_cms_response_headers
        
        headers = build_cms_response_headers(
            routed=True,
            tier=2,
            token_count=3000,
            token_limit=8192,
        )
        
        # Headroom = (8192 - 3000) / 8192 * 100 = ~63%
        assert "X-Headroom-Pct" in headers
        headroom = int(headers["X-Headroom-Pct"])
        assert 60 <= headroom <= 65
    
    def test_build_cms_headers_not_routed(self):
        """Headers when CMS was not used."""
        from src.api.routes.cms_routing import build_cms_response_headers
        
        headers = build_cms_response_headers(
            routed=False,
            tier=1,
            token_count=500,
            token_limit=8192,
        )
        
        assert headers["X-CMS-Routed"] == "false"
        assert headers["X-CMS-Tier"] == "1"


# =============================================================================
# TestCMSAvailability (AC-11.4)
# =============================================================================

class TestCMSAvailability:
    """Test CMS availability checks and 503 handling."""
    
    @pytest.mark.asyncio
    async def test_cms_health_check_success(self):
        """CMS health check returns True when healthy."""
        from src.clients.cms_client import CMSClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            client = CMSClient(base_url="http://localhost:8086")
            is_healthy = await client.health_check()
            assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_cms_health_check_failure(self):
        """CMS health check returns False when unhealthy."""
        from src.clients.cms_client import CMSClient
        import httpx
        
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
            client = CMSClient(base_url="http://localhost:8086")
            is_healthy = await client.health_check()
            assert is_healthy is False
    
    def test_tier_3_requires_cms(self):
        """Tier 3+ requests require CMS to be available."""
        from src.api.routes.cms_routing import cms_required_for_tier
        
        assert cms_required_for_tier(tier=1) is False
        assert cms_required_for_tier(tier=2) is False
        assert cms_required_for_tier(tier=3) is True
        assert cms_required_for_tier(tier=4) is True
    
    @pytest.mark.asyncio
    async def test_tier_3_returns_503_when_cms_unavailable(self):
        """Tier 3+ should return 503 when CMS is unavailable."""
        from src.api.routes.cms_routing import handle_cms_unavailable
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            handle_cms_unavailable(tier=3)
        
        assert exc_info.value.status_code == 503
        assert "CMS" in str(exc_info.value.detail)
    
    def test_tier_2_gracefully_degrades(self):
        """Tier 2 should continue without CMS if unavailable."""
        from src.api.routes.cms_routing import cms_required_for_tier
        
        # Tier 2 is not required - validation is optional
        assert cms_required_for_tier(tier=2) is False


# =============================================================================
# TestFastEstimation (AC-11.5)
# =============================================================================

class TestFastEstimation:
    """Test fast token estimation in Gateway."""
    
    def test_estimate_tokens_fast(self):
        """Fast estimation uses character/token ratio."""
        from src.api.routes.cms_routing import estimate_tokens_fast
        
        # ~1000 chars at 4 chars/token ratio = ~250 tokens
        text = "a" * 1000
        estimate = estimate_tokens_fast(text, model="gpt-4")
        
        assert 200 <= estimate <= 300
    
    def test_estimate_tokens_model_specific_ratio(self):
        """Different models may have different ratios."""
        from src.api.routes.cms_routing import estimate_tokens_fast
        
        text = "This is a test message with some words."
        
        # Different models may estimate differently
        est_gpt4 = estimate_tokens_fast(text, model="gpt-4")
        est_qwen = estimate_tokens_fast(text, model="qwen3-8b")
        
        # Both should be reasonable estimates
        assert 5 <= est_gpt4 <= 20
        assert 5 <= est_qwen <= 20
    
    def test_estimate_tokens_empty_string(self):
        """Empty string should return 0 tokens."""
        from src.api.routes.cms_routing import estimate_tokens_fast
        
        estimate = estimate_tokens_fast("", model="gpt-4")
        assert estimate == 0
    
    def test_estimate_tokens_from_messages(self):
        """Estimate tokens from chat messages."""
        from src.api.routes.cms_routing import estimate_tokens_from_messages
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]
        
        estimate = estimate_tokens_from_messages(messages, model="gpt-4")
        
        # Should include message overhead
        assert estimate > 0
    
    def test_estimate_latency_under_1ms(self):
        """Fast estimation should complete in <1ms."""
        import time
        from src.api.routes.cms_routing import estimate_tokens_fast
        
        text = "x" * 10000  # 10KB of text
        
        start = time.perf_counter()
        for _ in range(100):  # 100 iterations
            estimate_tokens_fast(text, model="gpt-4")
        elapsed = time.perf_counter() - start
        
        avg_time_ms = (elapsed / 100) * 1000
        assert avg_time_ms < 1.0


# =============================================================================
# TestGetContextLimit (AC-11.5)
# =============================================================================

class TestGetContextLimit:
    """Test context limit retrieval."""
    
    def test_get_context_limit_known_model(self):
        """Get context limit for known models."""
        from src.api.routes.cms_routing import get_context_limit
        
        assert get_context_limit("qwen3-8b") == 8192
        assert get_context_limit("codellama-7b") == 16384
        assert get_context_limit("deepseek-coder-v2-lite") == 131072
    
    def test_get_context_limit_unknown_model_uses_default(self):
        """Unknown models should use default context limit."""
        from src.api.routes.cms_routing import get_context_limit
        
        limit = get_context_limit("unknown-model")
        assert limit == 8192  # Default


# =============================================================================
# TestIntegrationWithChatEndpoint
# Tests for chat.py CMS integration (WBS-CMS11.8)
# =============================================================================

class TestChatEndpointCMSIntegration:
    """Test CMS integration with /v1/chat/completions endpoint."""
    
    @pytest.fixture
    def mock_cms_client(self):
        """Mock CMS client for testing."""
        client = AsyncMock()
        client.health_check = AsyncMock(return_value=True)
        client.process = AsyncMock(return_value=MagicMock(
            optimized_text="optimized prompt",
            original_tokens=100,
            optimized_tokens=75,
            compression_ratio=0.25,
            strategies_applied=[],
            glossary_version=0,
            chunks=None,
            fidelity_validated=False,
            fidelity_passed=None,
            rolled_back=False,
        ))
        return client
    
    @pytest.fixture
    def mock_chat_service(self):
        """Mock ChatService for testing."""
        service = AsyncMock()
        service.complete = AsyncMock(return_value=MagicMock(
            id="chatcmpl-test123",
            object="chat.completion",
            created=1234567890,
            model="qwen3-8b",
            choices=[MagicMock(
                index=0,
                message=MagicMock(role="assistant", content="Hello! I'm a test response."),
                finish_reason="stop",
            )],
            usage=MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            model_dump=MagicMock(return_value={
                "id": "chatcmpl-test123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "qwen3-8b",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello! I'm a test response."},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }),
        ))
        return service
    
    @pytest.fixture
    def client(self, mock_cms_client, mock_chat_service):
        """Create test client with mocked CMS and ChatService."""
        from fastapi import FastAPI
        from src.api.routes.chat import router as chat_router, get_chat_service
        from src.api.routes.cms_routing import set_cms_client
        
        app = FastAPI()
        app.include_router(chat_router)
        set_cms_client(mock_cms_client)
        
        # Override the chat service dependency
        app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
        
        return TestClient(app)
    
    def test_chat_includes_cms_headers(self, client, mock_cms_client, mock_chat_service):
        """Chat response should include CMS headers."""
        payload = {
            "model": "qwen3-8b",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        
        response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 200
        assert "X-CMS-Tier" in response.headers
        assert "X-Token-Count" in response.headers
    
    def test_tier_1_bypasses_cms(self, client, mock_cms_client, mock_chat_service):
        """Tier 1 requests should bypass CMS."""
        payload = {
            "model": "qwen3-8b",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        
        response = client.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 200
        assert response.headers.get("X-CMS-Routed") == "false"
        mock_cms_client.process.assert_not_called()
    
    def test_explicit_mode_none_bypasses_cms(self, client, mock_cms_client, mock_chat_service):
        """X-CMS-Mode: none should bypass CMS."""
        payload = {
            "model": "qwen3-8b",
            "messages": [{"role": "user", "content": "A" * 5000}],  # Large message
        }
        
        response = client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"X-CMS-Mode": "none"},
        )
        
        assert response.status_code == 200
        assert response.headers.get("X-CMS-Routed") == "false"
        mock_cms_client.process.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_tier_3_calls_cms(self, mock_cms_client):
        """Tier 3 requests should call CMS for optimization."""
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from src.api.routes.chat import router as chat_router, get_chat_service
        from src.api.routes.cms_routing import set_cms_client
        
        # Create mock chat service
        mock_chat_service = AsyncMock()
        mock_chat_service.complete = AsyncMock(return_value=MagicMock(
            model_dump=MagicMock(return_value={
                "id": "chatcmpl-test123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "qwen3-8b",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test response."},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            }),
        ))
        
        app = FastAPI()
        app.include_router(chat_router)
        set_cms_client(mock_cms_client)
        app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "model": "qwen3-8b",
                "messages": [{"role": "user", "content": "A" * 20000}],  # ~5000 tokens
            }
            response = await ac.post("/v1/chat/completions", json=payload)
        
        # Should have called CMS
        assert response.status_code == 200
        assert response.headers.get("X-CMS-Routed") == "true"
    
    @pytest.mark.asyncio
    async def test_tier_4_returns_503_when_cms_down(self):
        """Tier 4 should return 503 when CMS is unavailable."""
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport
        from src.api.routes.chat import router as chat_router, get_chat_service
        from src.api.routes.cms_routing import set_cms_client
        
        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=False)
        
        # Create mock chat service (shouldn't be called due to 503)
        mock_chat_service = AsyncMock()
        
        app = FastAPI()
        app.include_router(chat_router)
        set_cms_client(mock_client)
        app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "model": "qwen3-8b",
                "messages": [{"role": "user", "content": "A" * 30000}],  # ~7500 tokens (Tier 4)
            }
            response = await ac.post("/v1/chat/completions", json=payload)
        
        assert response.status_code == 503
