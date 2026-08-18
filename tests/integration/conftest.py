"""
WBS 3.5.1: Integration Test Infrastructure

This module provides fixtures and utilities for integration tests that run
against real Docker services via docker-compose.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3270-3340 - WBS 3.5.1
- GUIDELINES pp. 155-157: "high and low gear" testing philosophy
- docker-compose.yml: Service configurations and ports

WBS Coverage:
- 3.5.1.1.2: Create tests/integration/conftest.py
- 3.5.1.1.3: Add fixtures for service URLs
- 3.5.1.1.4: Add fixtures for test data
- 3.5.1.1.5: Add setup/teardown for test isolation
- 3.5.1.2.1-6: Service fixtures and helpers
"""

import asyncio
import os
import time
from typing import AsyncIterator, Iterator

import httpx
import pytest
import redis.asyncio as aioredis


# =============================================================================
# WBS 3.5.1.1.3: Service URL Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def redis_url() -> str:
    """
    WBS 3.5.1.1.3: Redis service URL fixture.
    
    Returns URL from environment or default docker-compose URL.
    """
    return os.getenv("INTEGRATION_REDIS_URL", "redis://localhost:6379")


@pytest.fixture(scope="session")
def gateway_url() -> str:
    """
    WBS 3.5.1.1.3: LLM Gateway service URL fixture.
    
    Returns URL from environment or default docker-compose URL.
    """
    return os.getenv("INTEGRATION_GATEWAY_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def semantic_search_url() -> str:
    """
    WBS 3.5.1.1.3: Semantic Search service URL fixture.
    
    Returns URL from environment or default docker-compose URL.
    """
    return os.getenv("INTEGRATION_SEMANTIC_SEARCH_URL", "http://localhost:8081")


@pytest.fixture(scope="session")
def ai_agents_url() -> str:
    """
    WBS 3.5.1.1.3: AI Agents service URL fixture.
    
    Returns URL from environment or default docker-compose URL.
    """
    return os.getenv("INTEGRATION_AI_AGENTS_URL", "http://localhost:8082")


# =============================================================================
# WBS 3.5.1.2.1: wait_for_service() Helper Function
# =============================================================================


async def wait_for_service(
    url: str,
    timeout: float = 30.0,
    interval: float = 1.0,
    health_path: str = "/health",
) -> bool:
    """
    WBS 3.5.1.2.1: Wait for a service to become healthy.
    
    Polls the service health endpoint until it responds with 200 OK
    or the timeout is reached.
    
    Args:
        url: Base URL of the service (e.g., "http://localhost:8080")
        timeout: Maximum time to wait in seconds (default: 30)
        interval: Time between retries in seconds (default: 1)
        health_path: Path to health endpoint (default: "/health")
        
    Returns:
        True if service became healthy, False otherwise
        
    Example:
        >>> async with httpx.AsyncClient() as client:
        ...     healthy = await wait_for_service("http://localhost:8080")
        ...     if healthy:
        ...         print("Service is ready!")
    """
    health_url = f"{url.rstrip('/')}{health_path}"
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                response = await client.get(health_url, timeout=5.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(interval)
    
    return False


def wait_for_service_sync(
    url: str,
    timeout: float = 30.0,
    interval: float = 1.0,
    health_path: str = "/health",
) -> bool:
    """
    WBS 3.5.1.2.1: Synchronous version of wait_for_service.
    
    Useful for pytest fixtures that don't support async.
    
    Args:
        url: Base URL of the service
        timeout: Maximum time to wait in seconds
        interval: Time between retries in seconds
        health_path: Path to health endpoint
        
    Returns:
        True if service became healthy, False otherwise
    """
    health_url = f"{url.rstrip('/')}{health_path}"
    start_time = time.time()
    
    with httpx.Client() as client:
        while time.time() - start_time < timeout:
            try:
                response = client.get(health_url, timeout=5.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(interval)
    
    return False


async def wait_for_redis(url: str, timeout: float = 30.0, interval: float = 1.0) -> bool:
    """
    WBS 3.5.1.2.1: Wait for Redis to become available.
    
    Args:
        url: Redis URL (e.g., "redis://localhost:6379")
        timeout: Maximum time to wait in seconds
        interval: Time between retries in seconds
        
    Returns:
        True if Redis is available, False otherwise
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            client = aioredis.from_url(url, decode_responses=True)
            result = await client.ping()
            await client.aclose()
            if result:
                return True
        except (ConnectionError, OSError):
            pass
        await asyncio.sleep(interval)
    
    return False


# =============================================================================
# WBS 3.5.1.2.2-5: Service Client Fixtures
# =============================================================================


@pytest.fixture
async def gateway_client(gateway_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """
    WBS 3.5.1.2.2: Async HTTP client for LLM Gateway service.
    
    Creates an httpx.AsyncClient configured to talk to the gateway.
    Client is closed automatically after the test.
    
    Args:
        gateway_url: Gateway URL from fixture
        
    Yields:
        httpx.AsyncClient configured for gateway
    """
    async with httpx.AsyncClient(base_url=gateway_url, timeout=30.0) as client:
        yield client


@pytest.fixture
async def semantic_search_client(
    semantic_search_url: str,
) -> AsyncIterator[httpx.AsyncClient]:
    """
    WBS 3.5.1.2.3: Async HTTP client for Semantic Search service.
    
    Args:
        semantic_search_url: Semantic Search URL from fixture
        
    Yields:
        httpx.AsyncClient configured for semantic-search
    """
    async with httpx.AsyncClient(base_url=semantic_search_url, timeout=30.0) as client:
        yield client


@pytest.fixture
async def ai_agents_client(ai_agents_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """
    WBS 3.5.1.2.4: Async HTTP client for AI Agents service.
    
    Args:
        ai_agents_url: AI Agents URL from fixture
        
    Yields:
        httpx.AsyncClient configured for ai-agents
    """
    async with httpx.AsyncClient(base_url=ai_agents_url, timeout=30.0) as client:
        yield client


@pytest.fixture
async def redis_client(redis_url: str) -> AsyncIterator[aioredis.Redis]:
    """
    WBS 3.5.1.2.5: Async Redis client for test data.
    
    Creates a Redis client connected to the test Redis instance.
    Client is closed automatically after the test.
    
    Args:
        redis_url: Redis URL from fixture
        
    Yields:
        aioredis.Redis client
    """
    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# =============================================================================
# WBS 3.5.1.2.6: Cleanup Fixtures
# =============================================================================


@pytest.fixture
async def clean_redis(redis_client: aioredis.Redis) -> AsyncIterator[aioredis.Redis]:
    """
    WBS 3.5.1.2.6: Cleanup fixture that flushes Redis between tests.
    
    Flushes the Redis database before and after each test to ensure
    test isolation.
    
    Args:
        redis_client: Redis client from fixture
        
    Yields:
        The same Redis client, with cleanup before/after
    """
    # Cleanup before test
    await redis_client.flushdb()
    
    yield redis_client
    
    # Cleanup after test
    await redis_client.flushdb()


@pytest.fixture
def test_session_id() -> str:
    """
    WBS 3.5.1.1.4: Generate a unique session ID for test isolation.
    
    Each test gets a unique session ID to avoid conflicts.
    
    Returns:
        Unique session ID string
    """
    import uuid
    return f"test-session-{uuid.uuid4().hex[:8]}"


# =============================================================================
# WBS 3.5.1.1.4: Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_chat_payload() -> dict:
    """
    WBS 3.5.1.1.4: Sample chat completion request payload.
    
    Returns a basic chat request that can be sent to the gateway.
    """
    return {
        "model": "claude-3-sonnet-20240229",
        "messages": [{"role": "user", "content": "Hello, world!"}],
    }


@pytest.fixture
def sample_tool_payload() -> dict:
    """
    WBS 3.5.1.1.4: Sample chat request with tools.
    
    Returns a chat request with tool definitions for testing
    tool execution flows.
    """
    return {
        "model": "claude-3-sonnet-20240229",
        "messages": [{"role": "user", "content": "Search for information about AI."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_corpus",
                    "description": "Search the document corpus",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            }
                        },
                        "required": ["query"],
                    },
                },
            }
        ],
    }


@pytest.fixture
def sample_session_payload(test_session_id: str) -> dict:
    """
    WBS 3.5.1.1.4: Sample session creation payload.
    
    Returns a session request using the test session ID.
    """
    return {
        "session_id": test_session_id,
        "messages": [{"role": "user", "content": "Start a conversation"}],
        "context": {"test": True},
    }


# =============================================================================
# WBS 3.5.1.1.5: Setup/Teardown for Test Isolation
# =============================================================================


@pytest.fixture(scope="session")
def docker_services_available() -> bool:
    """
    WBS 3.5.1.1.5: Check if Docker services are available.
    
    Returns True if the integration test services are running,
    False otherwise. Tests can use this to skip when services
    are not available.
    
    Returns:
        True if services are up, False otherwise
    """
    gateway_url = os.getenv("INTEGRATION_GATEWAY_URL", "http://localhost:8080")
    
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{gateway_url}/health")
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture
def skip_if_no_docker(docker_services_available: bool) -> None:
    """
    WBS 3.5.1.1.5: Skip test if Docker services are not available.
    
    Use this fixture in tests that require live Docker services.
    
    Example:
        def test_something(skip_if_no_docker, gateway_client):
            # This test will be skipped if Docker isn't running
            pass
    """
    if not docker_services_available:
        pytest.skip("Docker services not available - run with docker-compose up")


# =============================================================================
# Synchronous Client Fixtures (for non-async tests)
# =============================================================================


@pytest.fixture
def gateway_client_sync(gateway_url: str) -> Iterator[httpx.Client]:
    """
    Synchronous HTTP client for LLM Gateway service.
    
    For use in synchronous test functions.
    
    Args:
        gateway_url: Gateway URL from fixture
        
    Yields:
        httpx.Client configured for gateway
    """
    with httpx.Client(base_url=gateway_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def semantic_search_client_sync(semantic_search_url: str) -> Iterator[httpx.Client]:
    """
    Synchronous HTTP client for Semantic Search service.
    
    Args:
        semantic_search_url: Semantic Search URL from fixture
        
    Yields:
        httpx.Client configured for semantic-search
    """
    with httpx.Client(base_url=semantic_search_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def ai_agents_client_sync(ai_agents_url: str) -> Iterator[httpx.Client]:
    """
    Synchronous HTTP client for AI Agents service.
    
    Args:
        ai_agents_url: AI Agents URL from fixture
        
    Yields:
        httpx.Client configured for ai-agents
    """
    with httpx.Client(base_url=ai_agents_url, timeout=30.0) as client:
        yield client
