"""
Tests for ResponseCache - WBS 2.6.3 Response Cache Service

TDD RED Phase: These tests should fail until ResponseCache is implemented.

Reference Documents:
- ARCHITECTURE.md: Line 64 - cache.py "Response caching"
- ARCHITECTURE.md: Line 222 - "Response caching"
- ARCHITECTURE.md: Line 231 - "Redis | Infrastructure | Session storage, caching"
- GUIDELINES pp. 2153: Redis for external state stores

WBS Items Covered:
- 2.6.3.1.1: Create src/services/cache.py
- 2.6.3.1.2: Implement ResponseCache class
- 2.6.3.1.3: Inject Redis client
- 2.6.3.1.4: Implement cache key generation from request hash
- 2.6.3.1.5: Implement async get()
- 2.6.3.1.6: Implement async set()
- 2.6.3.1.7: Configure TTL from settings
- 2.6.3.1.8: Skip caching for tool_use requests
- 2.6.3.1.9: RED test: cache hit returns response
- 2.6.3.1.10: RED test: cache miss returns None
- 2.6.3.1.11: RED test: cache expires after TTL
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import fakeredis.aioredis
import uuid

from src.models.requests import ChatCompletionRequest, Message, Tool, FunctionDefinition
from src.models.responses import ChatCompletionResponse, Choice, ChoiceMessage, Usage


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def fake_redis():
    """Create a fake Redis client for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def response_cache(fake_redis):
    """Create ResponseCache with fake Redis."""
    from src.services.cache import ResponseCache

    return ResponseCache(redis_client=fake_redis, ttl_seconds=60)


@pytest.fixture
def sample_request():
    """Create a sample chat completion request."""
    return ChatCompletionRequest(
        model="claude-3-5-sonnet-20241022",
        messages=[Message(role="user", content="Hello, world!")],
        temperature=0.7,
    )


@pytest.fixture
def sample_response():
    """Create a sample chat completion response."""
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(datetime.now(timezone.utc).timestamp()),
        model="claude-3-5-sonnet-20241022",
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
def tool_request():
    """Create a request with tools (should not be cached)."""
    return ChatCompletionRequest(
        model="claude-3-5-sonnet-20241022",
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


# =============================================================================
# WBS 2.6.3.1.2-3: ResponseCache Class Tests
# =============================================================================


class TestResponseCacheClass:
    """Tests for ResponseCache class structure."""

    def test_response_cache_can_be_instantiated(self, fake_redis) -> None:
        """
        WBS 2.6.3.1.2: ResponseCache class exists and can be instantiated.
        """
        from src.services.cache import ResponseCache

        cache = ResponseCache(redis_client=fake_redis)

        assert isinstance(cache, ResponseCache)

    def test_response_cache_requires_redis(self) -> None:
        """
        WBS 2.6.3.1.3: ResponseCache requires Redis client dependency.
        """
        from src.services.cache import ResponseCache

        with pytest.raises(TypeError):
            ResponseCache()

    def test_response_cache_accepts_custom_ttl(self, fake_redis) -> None:
        """
        WBS 2.6.3.1.7: Configure TTL from settings.
        """
        from src.services.cache import ResponseCache

        cache = ResponseCache(redis_client=fake_redis, ttl_seconds=300)

        assert cache._ttl_seconds == 300


# =============================================================================
# WBS 2.6.3.1.4: Cache Key Generation Tests
# =============================================================================


class TestResponseCacheKeyGeneration:
    """Tests for cache key generation."""

    def test_generates_consistent_keys(self, response_cache, sample_request) -> None:
        """
        WBS 2.6.3.1.4: Cache key generation is deterministic.
        """
        key1 = response_cache._generate_cache_key(sample_request)
        key2 = response_cache._generate_cache_key(sample_request)

        assert key1 == key2

    def test_different_requests_different_keys(self, response_cache) -> None:
        """
        Different requests generate different keys.
        """
        request1 = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Hello")],
        )
        request2 = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Goodbye")],
        )

        key1 = response_cache._generate_cache_key(request1)
        key2 = response_cache._generate_cache_key(request2)

        assert key1 != key2

    def test_key_includes_model(self, response_cache) -> None:
        """
        Cache key includes model in computation.
        """
        request1 = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Hello")],
        )
        request2 = ChatCompletionRequest(
            model="gpt-4",
            messages=[Message(role="user", content="Hello")],
        )

        key1 = response_cache._generate_cache_key(request1)
        key2 = response_cache._generate_cache_key(request2)

        assert key1 != key2

    def test_key_includes_temperature(self, response_cache) -> None:
        """
        Cache key includes temperature in computation.
        """
        request1 = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Hello")],
            temperature=0.5,
        )
        request2 = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Hello")],
            temperature=1.0,
        )

        key1 = response_cache._generate_cache_key(request1)
        key2 = response_cache._generate_cache_key(request2)

        assert key1 != key2


# =============================================================================
# WBS 2.6.3.1.5: Cache Get Tests
# =============================================================================


class TestResponseCacheGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(
        self, response_cache, sample_request
    ) -> None:
        """
        WBS 2.6.3.1.5: get() returns None on cache miss.
        WBS 2.6.3.1.10: RED test: cache miss returns None.
        """
        result = await response_cache.get(sample_request)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_response(
        self, response_cache, sample_request, sample_response
    ) -> None:
        """
        WBS 2.6.3.1.5: get() returns response on cache hit.
        WBS 2.6.3.1.9: RED test: cache hit returns response.
        """
        # Store response first
        await response_cache.set(sample_request, sample_response)

        # Retrieve it
        result = await response_cache.get(sample_request)

        assert result is not None
        assert isinstance(result, ChatCompletionResponse)
        assert result.choices[0].message.content == "Hello! How can I help?"


# =============================================================================
# WBS 2.6.3.1.6: Cache Set Tests
# =============================================================================


class TestResponseCacheSet:
    """Tests for set method."""

    @pytest.mark.asyncio
    async def test_set_stores_response(
        self, response_cache, sample_request, sample_response
    ) -> None:
        """
        WBS 2.6.3.1.6: set() stores response in cache.
        """
        await response_cache.set(sample_request, sample_response)

        # Verify it can be retrieved
        result = await response_cache.get(sample_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_set_preserves_response_data(
        self, response_cache, sample_request, sample_response
    ) -> None:
        """
        set() preserves all response data.
        """
        await response_cache.set(sample_request, sample_response)

        result = await response_cache.get(sample_request)

        assert result.model == sample_response.model
        assert result.choices[0].message.content == sample_response.choices[0].message.content
        assert result.usage.total_tokens == sample_response.usage.total_tokens


# =============================================================================
# WBS 2.6.3.1.7: TTL Configuration Tests
# =============================================================================


class TestResponseCacheTTL:
    """Tests for TTL behavior."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, fake_redis) -> None:
        """
        WBS 2.6.3.1.7: Cache entries expire after TTL.
        WBS 2.6.3.1.11: RED test: cache expires after TTL.
        """
        from src.services.cache import ResponseCache

        # Use very short TTL for testing
        cache = ResponseCache(redis_client=fake_redis, ttl_seconds=1)

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Test")],
        )
        response = ChatCompletionResponse(
            id="test-id",
            created=int(datetime.now(timezone.utc).timestamp()),
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content="Test response"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )

        await cache.set(request, response)

        # Should exist immediately
        result1 = await cache.get(request)
        assert result1 is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired
        result2 = await cache.get(request)
        assert result2 is None


# =============================================================================
# WBS 2.6.3.1.8: Skip Tool Requests Tests
# =============================================================================


class TestResponseCacheToolRequests:
    """Tests for skipping tool_use requests."""

    @pytest.mark.asyncio
    async def test_skip_caching_tool_requests(
        self, response_cache, tool_request, sample_response
    ) -> None:
        """
        WBS 2.6.3.1.8: Skip caching for tool_use requests.
        """
        # Should not cache (method should be no-op)
        await response_cache.set(tool_request, sample_response)

        # Should return None even after set
        result = await response_cache.get(tool_request)
        assert result is None

    def test_should_cache_returns_false_for_tools(
        self, response_cache, tool_request
    ) -> None:
        """
        _should_cache returns False for requests with tools.
        """
        should_cache = response_cache._should_cache(tool_request)
        assert should_cache is False

    def test_should_cache_returns_true_for_normal(
        self, response_cache, sample_request
    ) -> None:
        """
        _should_cache returns True for normal requests.
        """
        should_cache = response_cache._should_cache(sample_request)
        assert should_cache is True

    @pytest.mark.asyncio
    async def test_skip_caching_stream_requests(self, response_cache, sample_response) -> None:
        """
        Skip caching for streaming requests.
        """
        stream_request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

        await response_cache.set(stream_request, sample_response)

        result = await response_cache.get(stream_request)
        assert result is None


# =============================================================================
# Import Tests
# =============================================================================


class TestResponseCacheImportable:
    """Tests for module importability."""

    def test_response_cache_importable_from_services(self) -> None:
        """ResponseCache is importable from src.services."""
        from src.services import ResponseCache

        assert callable(ResponseCache)

    def test_response_cache_importable_from_cache(self) -> None:
        """ResponseCache is importable from src.services.cache."""
        from src.services.cache import ResponseCache

        assert callable(ResponseCache)
