"""
Pytest configuration for comprehensive test suite.

WBS 2.9.1.1.7: Create tests/conftest.py with shared fixtures

Reference Documents:
- GUIDELINES pp. 155-157: "high and low gear" testing philosophy
- GUIDELINES pp. 157: FakeRepository pattern using duck typing
- GUIDELINES pp. 242 (Newman): AI tests require mocks simulating varying response times,
  occasional failures, and context-dependent outputs
- ARCHITECTURE.md: Test structure and dependencies
- CODING_PATTERNS_ANALYSIS: pytest fixtures and patterns

This configuration sets up:
- Test discovery paths
- Shared fixtures following FakeRepository pattern
- Test markers for categorization
- Mock patterns for AI/ML components
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
import fakeredis.aioredis
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Test Markers (WBS 2.9.1.1.7)
# =============================================================================


def pytest_configure(config):
    """
    Register custom markers for test categorization.
    
    Categories follow GUIDELINES "high and low gear" philosophy:
    - unit: Low gear tests for individual components (primitives)
    - integration: High gear tests for service interactions (domain)
    - e2e: End-to-end workflow tests
    - slow: Tests that take a long time to run
    """
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line("markers", "integration: Integration tests for service interactions")
    config.addinivalue_line("markers", "e2e: End-to-end workflow tests")
    config.addinivalue_line("markers", "slow: Tests that take a long time to run")


# =============================================================================
# WBS 2.9.1.2.1: FakeRedis Fixture
# =============================================================================


@pytest.fixture
def fake_redis():
    """
    Create a fake Redis client for testing.
    
    Reference: GUIDELINES pp. 157 - FakeRepository pattern
    "Python's duck typing enables test doubles without complex mocking frameworks"
    
    This fixture uses fakeredis to provide a fully functional Redis-compatible
    interface without requiring a real Redis instance.
    
    Returns:
        FakeRedis: A fake Redis client with decode_responses=True
    """
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# =============================================================================
# WBS 2.9.1.2.4: Test Settings Fixture
# =============================================================================


@pytest.fixture
def test_settings():
    """
    Create test settings with safe defaults.
    
    Reference: ARCHITECTURE.md - Settings class configuration
    
    Provides a Settings instance configured for testing with:
    - In-memory defaults (no real external services)
    - Fake API keys for testing
    - Development environment
    
    Returns:
        Settings: Configured settings for testing
    """
    from src.core.config import Settings
    
    return Settings(
        service_name="llm-gateway-test",
        port=8080,
        environment="development",
        redis_url="redis://localhost:6379",
        redis_pool_size=5,
        semantic_search_url="http://localhost:8081",
        ai_agents_url="http://localhost:8082",
        ollama_url="http://localhost:11434",
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key",
        default_provider="anthropic",
        default_model="claude-3-sonnet-20240229",
        rate_limit_requests_per_minute=60,
        rate_limit_burst=10,
        session_ttl_seconds=3600,
    )


# =============================================================================
# WBS 2.9.1.2.2: MockProviderRouter Fixture
# =============================================================================


@pytest.fixture
def mock_provider():
    """
    Create a mock LLM provider.
    
    Reference: GUIDELINES pp. 242 (Newman)
    "AI gateway tests require mock providers that simulate varying response times,
    occasional failures, and context-dependent outputs"
    
    Returns:
        AsyncMock: A mock provider with complete/stream methods
    """
    provider = AsyncMock()
    provider.complete = AsyncMock()
    provider.stream = AsyncMock()
    provider.supports_model = MagicMock(return_value=True)
    provider.get_supported_models = MagicMock(return_value=["test-model"])
    return provider


@pytest.fixture
def mock_provider_router(mock_provider):
    """
    Create a mock provider router.
    
    Reference: ARCHITECTURE.md - Provider routing logic
    Reference: GUIDELINES pp. 157 - FakeRepository pattern
    
    Uses duck typing to create a mock that matches the ProviderRouter interface
    without complex inheritance.
    
    Args:
        mock_provider: The mock LLM provider fixture
        
    Returns:
        MagicMock: A mock router with get_provider method
    """
    from src.providers.router import ProviderRouter
    
    router = MagicMock(spec=ProviderRouter)
    router.get_provider = MagicMock(return_value=mock_provider)
    router.list_available_models = MagicMock(return_value=[
        {"provider": "test", "model": "test-model"}
    ])
    router.register_provider = MagicMock()
    router.unregister_provider = MagicMock()
    router.get_provider_names = MagicMock(return_value=["test"])
    return router


# =============================================================================
# WBS 2.9.1.2.3: MockSemanticSearchClient Fixture
# =============================================================================


@pytest.fixture
def mock_http_client():
    """
    Create a mock HTTP client for client fixtures.
    
    Returns:
        AsyncMock: A mock httpx.AsyncClient
    """
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def mock_semantic_search_client(mock_http_client):
    """
    Create a mock semantic search client.
    
    Reference: ARCHITECTURE.md - semantic-search-service dependency
    Reference: GUIDELINES pp. 157 - FakeRepository pattern
    
    Args:
        mock_http_client: Mock HTTP client fixture
        
    Returns:
        SemanticSearchClient: Client with mocked HTTP backend
    """
    from src.clients.semantic_search import SemanticSearchClient
    
    return SemanticSearchClient(http_client=mock_http_client)


@pytest.fixture
def mock_ai_agents_client(mock_http_client):
    """
    Create a mock AI agents client.
    
    Reference: ARCHITECTURE.md - ai-agents dependency
    
    Args:
        mock_http_client: Mock HTTP client fixture
        
    Returns:
        AIAgentsClient: Client with mocked HTTP backend
    """
    from src.clients.ai_agents import AIAgentsClient
    
    return AIAgentsClient(http_client=mock_http_client)


# =============================================================================
# Mock Tool Executor Fixture
# =============================================================================


@pytest.fixture
def mock_tool_executor():
    """
    Create a mock tool executor.
    
    Reference: ARCHITECTURE.md - Tool execution orchestration
    
    Returns:
        MagicMock: Mock ToolExecutor with execute/execute_batch methods
    """
    from src.tools.executor import ToolExecutor
    
    executor = MagicMock(spec=ToolExecutor)
    executor.execute = AsyncMock()
    executor.execute_batch = AsyncMock()
    return executor


# =============================================================================
# Mock Session Manager Fixture
# =============================================================================


@pytest.fixture
def mock_session_manager():
    """
    Create a mock session manager.
    
    Reference: ARCHITECTURE.md - Session lifecycle
    
    Returns:
        MagicMock: Mock SessionManager with session operations
    """
    from src.sessions.manager import SessionManager
    
    manager = MagicMock(spec=SessionManager)
    manager.create = AsyncMock()
    manager.get = AsyncMock()
    manager.delete = AsyncMock()
    manager.add_message = AsyncMock()
    manager.get_history = AsyncMock(return_value=[])
    manager.update_context = AsyncMock()
    manager.clear_history = AsyncMock()
    return manager


# =============================================================================
# WBS 2.9.1.2.5: Test Client Fixture
# =============================================================================


@pytest.fixture
def app():
    """
    Create a minimal FastAPI app for testing.
    
    Returns:
        FastAPI: A basic FastAPI application
    """
    return FastAPI(title="Test App")


@pytest.fixture
def test_client(app):
    """
    Create a FastAPI test client.
    
    Reference: GUIDELINES pp. 155-157 - Service-layer tests
    
    Args:
        app: The FastAPI application fixture
        
    Returns:
        TestClient: Synchronous test client for the app
    """
    return TestClient(app)


@pytest.fixture
def full_app_client():
    """
    Create a test client with the full application.
    
    This fixture creates a TestClient for the actual main application,
    useful for integration-level tests.
    
    Returns:
        TestClient: Test client for the full application
    """
    from src.main import app
    
    return TestClient(app)


# =============================================================================
# WBS 2.9.1.2.6: Sample Request/Response Fixtures
# =============================================================================


@pytest.fixture
def sample_chat_request():
    """
    Create a sample chat completion request.
    
    Reference: ARCHITECTURE.md - Request models
    
    Returns:
        ChatCompletionRequest: A basic chat request
    """
    from src.models.requests import ChatCompletionRequest, Message
    
    return ChatCompletionRequest(
        model="test-model",
        messages=[Message(role="user", content="Hello, world!")],
    )


@pytest.fixture
def sample_chat_response():
    """
    Create a sample chat completion response.
    
    Reference: ARCHITECTURE.md - Response models
    
    Returns:
        ChatCompletionResponse: A basic chat response
    """
    from src.models.responses import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        Usage,
    )
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(datetime.now(timezone.utc).timestamp()),
        model="test-model",
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Hello! How can I help?"),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture
def sample_tool_request():
    """
    Create a sample request with tools.
    
    Returns:
        ChatCompletionRequest: A request with tool definitions
    """
    from src.models.requests import ChatCompletionRequest, Message, Tool, FunctionDefinition
    
    return ChatCompletionRequest(
        model="test-model",
        messages=[Message(role="user", content="What's the weather?")],
        tools=[
            Tool(
                type="function",
                function=FunctionDefinition(
                    name="get_weather",
                    description="Get weather for a location",
                    parameters={"type": "object", "properties": {}},
                ),
            )
        ],
    )


@pytest.fixture
def sample_tool_call_response():
    """
    Create a response with tool calls.
    
    Returns:
        ChatCompletionResponse: A response containing tool calls
    """
    from src.models.responses import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        Usage,
    )
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(datetime.now(timezone.utc).timestamp()),
        model="test-model",
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "San Francisco"}',
                            },
                        }
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


@pytest.fixture
def sample_session():
    """
    Create a sample session for testing.
    
    Returns:
        Session: A sample session with messages
    """
    from src.models.domain import Session, Message
    
    now = datetime.now(timezone.utc)
    return Session(
        id=str(uuid.uuid4()),
        messages=[
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ],
        context={"test_key": "test_value"},
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


# =============================================================================
# Semantic Search Response Fixtures
# =============================================================================


@pytest.fixture
def sample_search_response():
    """
    Sample search response from semantic-search-service.
    
    Returns:
        dict: A search response with results
    """
    return {
        "results": [
            {
                "chunk_id": "chunk-001",
                "content": "This is a test chunk about AI.",
                "score": 0.95,
                "metadata": {"source": "test.md", "page": 1},
            },
            {
                "chunk_id": "chunk-002",
                "content": "Another relevant chunk.",
                "score": 0.87,
                "metadata": {"source": "test.md", "page": 2},
            },
        ],
        "total": 2,
        "query": "test query",
    }


@pytest.fixture
def sample_embed_response():
    """
    Sample embedding response.
    
    Returns:
        dict: An embedding response with vectors
    """
    return {
        "embeddings": [
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.2, 0.3, 0.4, 0.5, 0.6],
        ],
        "model": "text-embedding-ada-002",
    }


@pytest.fixture
def sample_chunk_response():
    """
    Sample chunk response.
    
    Returns:
        dict: A chunk retrieval response
    """
    return {
        "chunk_id": "chunk-001",
        "content": "This is the full chunk content.",
        "metadata": {"source": "test.md", "page": 1, "created_at": "2024-01-01"},
    }


# =============================================================================
# Environment Patch Fixtures
# =============================================================================


@pytest.fixture
def mock_env_vars():
    """
    Context manager to mock environment variables for testing.
    
    Yields:
        dict: Mocked environment variables
    """
    import os
    
    test_vars = {
        "LLM_GATEWAY_ENVIRONMENT": "development",
        "LLM_GATEWAY_PORT": "8080",
        "LLM_GATEWAY_ANTHROPIC_API_KEY": "test-key",
        "LLM_GATEWAY_OPENAI_API_KEY": "test-key",
    }
    
    with patch.dict(os.environ, test_vars):
        yield test_vars


# =============================================================================
# Async Event Loop Configuration
# =============================================================================


@pytest.fixture
def event_loop_policy():
    """
    Configure the event loop policy for async tests.
    
    This ensures consistent async behavior across test runs.
    """
    import asyncio
    
    return asyncio.DefaultEventLoopPolicy()
