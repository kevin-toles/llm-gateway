"""
Tests for CMS Client - WBS-CMS11.5: CMSClient Implementation

TDD RED Phase: These tests define expected behavior for CMS client.

Reference Documents:
- WBS_CONTEXT_MANAGEMENT_SERVICE.md: CMS11 Acceptance Criteria
- Context_Management_Service_Architecture.md: API Contract

Acceptance Criteria Covered:
- AC-11.1: Gateway routes Tier 2+ requests to CMS
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# =============================================================================
# TestCMSClientInit
# =============================================================================

class TestCMSClientInit:
    """Test CMSClient initialization."""
    
    def test_init_with_base_url(self):
        """CMSClient should accept base URL."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086")
        assert client.base_url == "http://localhost:8086"
    
    def test_init_with_timeout(self):
        """CMSClient should accept custom timeout."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086", timeout_seconds=10.0)
        assert client.timeout_seconds == pytest.approx(10.0)
    
    def test_init_default_timeout(self):
        """CMSClient should have default timeout of 5 seconds."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086")
        assert client.timeout_seconds == pytest.approx(5.0)


# =============================================================================
# TestCMSClientHealthCheck
# =============================================================================

class TestCMSClientHealthCheck:
    """Test CMSClient health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self):
        """Health check returns True when CMS is healthy."""
        from src.clients.cms_client import CMSClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            is_healthy = await client.health_check()
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_connection_error(self):
        """Health check returns False on connection error."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            is_healthy = await client.health_check()
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_timeout(self):
        """Health check returns False on timeout."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            is_healthy = await client.health_check()
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_500(self):
        """Health check returns False on 500 status."""
        from src.clients.cms_client import CMSClient
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            is_healthy = await client.health_check()
        
        assert is_healthy is False


# =============================================================================
# TestCMSClientProcess
# =============================================================================

class TestCMSClientProcess:
    """Test CMSClient process method (calls /v1/context/process)."""
    
    @pytest.mark.asyncio
    async def test_process_returns_result(self):
        """Process returns optimization result."""
        from src.clients.cms_client import CMSClient, CMSProcessResult
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "optimized_text": "compressed text",
            "original_tokens": 100,
            "optimized_tokens": 70,
            "compression_ratio": 0.30,
            "strategies_applied": ["prose_to_bullets", "symbols"],
        }
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            result = await client.process(
                text="original text",
                model="qwen3-8b",
            )
        
        assert isinstance(result, CMSProcessResult)
        assert result.optimized_text == "compressed text"
        assert result.compression_ratio == pytest.approx(0.30)
    
    @pytest.mark.asyncio
    async def test_process_sends_correct_payload(self):
        """Process sends correct request payload."""
        from src.clients.cms_client import CMSClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "optimized_text": "text",
            "original_tokens": 100,
            "optimized_tokens": 100,
            "compression_ratio": 0.0,
        }
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            await client.process(
                text="original text",
                model="qwen3-8b",
                conversation_id="conv-123",
            )
        
        # Verify call was made with correct payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/v1/context/process"
        payload = call_args[1]["json"]
        assert payload["text"] == "original text"
        assert payload["model"] == "qwen3-8b"
        assert payload["conversation_id"] == "conv-123"
    
    @pytest.mark.asyncio
    async def test_process_raises_on_error(self):
        """Process raises CMSError on API error."""
        from src.clients.cms_client import CMSClient, CMSError
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(CMSError) as exc_info:
                await client.process(text="text", model="model")
            
            assert exc_info.value.status_code == 500
    
    @pytest.mark.asyncio
    async def test_process_with_optimization_config(self):
        """Process accepts optimization config."""
        from src.clients.cms_client import CMSClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "optimized_text": "text",
            "original_tokens": 100,
            "optimized_tokens": 80,
            "compression_ratio": 0.20,
        }
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            await client.process(
                text="original text",
                model="qwen3-8b",
                optimization_config={
                    "enabled_strategies": ["prose_to_bullets"],
                },
            )
        
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert "optimization_config" in payload
        assert payload["optimization_config"]["enabled_strategies"] == ["prose_to_bullets"]


# =============================================================================
# TestCMSClientValidate
# =============================================================================

class TestCMSClientValidate:
    """Test CMSClient validate method (token counting)."""
    
    @pytest.mark.asyncio
    async def test_validate_returns_token_metrics(self):
        """Validate returns token count and metrics."""
        from src.clients.cms_client import CMSClient, CMSValidateResult
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token_count": 150,
            "context_limit": 8192,
            "utilization": 0.018,
        }
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            result = await client.validate(
                text="some text",
                model="qwen3-8b",
            )
        
        assert isinstance(result, CMSValidateResult)
        assert result.token_count == 150
        assert result.context_limit == 8192


# =============================================================================
# TestCMSClientChunk
# =============================================================================

class TestCMSClientChunk:
    """Test CMSClient chunk method."""
    
    @pytest.mark.asyncio
    async def test_chunk_returns_chunks(self):
        """Chunk returns list of chunks."""
        from src.clients.cms_client import CMSClient, CMSChunk
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "chunks": [
                {"chunk_id": "c1", "sequence": 0, "content": "chunk 1", "token_count": 100},
                {"chunk_id": "c2", "sequence": 1, "content": "chunk 2", "token_count": 100},
            ],
            "total_chunks": 2,
        }
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            chunks = await client.chunk(
                text="long text...",
                model="qwen3-8b",
            )
        
        assert len(chunks) == 2
        assert all(isinstance(c, CMSChunk) for c in chunks)


# =============================================================================
# TestCMSClientContextManager
# =============================================================================

class TestCMSClientContextManager:
    """Test CMSClient as async context manager."""
    
    @pytest.mark.asyncio
    async def test_client_as_context_manager(self):
        """CMSClient should work as async context manager."""
        from src.clients.cms_client import CMSClient
        
        async with CMSClient(base_url="http://localhost:8086") as client:
            assert client is not None
    
    @pytest.mark.asyncio
    async def test_client_closes_on_exit(self):
        """CMSClient should close HTTP client on exit."""
        from src.clients.cms_client import CMSClient
        
        client = CMSClient(base_url="http://localhost:8086")
        
        with patch.object(client, "_client") as mock_http:
            mock_http.aclose = AsyncMock()
            await client.close()
            mock_http.aclose.assert_called_once()


# =============================================================================
# TestCMSClientDependencyInjection
# =============================================================================

class TestCMSClientDependencyInjection:
    """Test CMSClient dependency injection pattern."""
    
    def test_get_cms_client_returns_singleton(self):
        """get_cms_client returns singleton instance."""
        from src.clients.cms_client import get_cms_client, _reset_cms_client
        
        _reset_cms_client()  # Reset for test
        
        client1 = get_cms_client()
        client2 = get_cms_client()
        
        assert client1 is client2
    
    def test_set_cms_client_for_testing(self):
        """set_cms_client allows injection for testing."""
        from src.clients.cms_client import get_cms_client, set_cms_client, _reset_cms_client
        
        _reset_cms_client()
        
        mock_client = MagicMock()
        set_cms_client(mock_client)
        
        assert get_cms_client() is mock_client
        
        _reset_cms_client()  # Cleanup
