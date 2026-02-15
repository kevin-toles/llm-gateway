"""
Response Cache Service - WBS 2.6.3.1

This module provides caching functionality for LLM API responses.

Reference Documents:
- ARCHITECTURE.md: Service layer patterns
- GUIDELINES: Async patterns, dependency injection
- CODING_PATTERNS_ANALYSIS.md: Pydantic patterns, error handling

Pattern: Repository pattern with Redis storage
Anti-Pattern §1.3 Avoided: Uses Pydantic models for data structures
"""

import hashlib
import json
from typing import Optional

from redis.asyncio import Redis

from src.models.requests import ChatCompletionRequest
from src.models.responses import ChatCompletionResponse


# =============================================================================
# Custom Exceptions - WBS 2.6.3.1.9
# =============================================================================


class CacheError(Exception):
    """Base exception for cache errors."""

    pass


# =============================================================================
# Default Configuration
# =============================================================================


DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hour


# =============================================================================
# ResponseCache Service - WBS 2.6.3.1.2
# =============================================================================


class ResponseCache:
    """
    Service for caching LLM API responses.

    Pattern: Repository pattern with Redis storage
    Reference: ARCHITECTURE.md service layer patterns

    Attributes:
        redis: Redis client for persistence
        ttl_seconds: Cache TTL in seconds
    """

    # Redis key prefix
    KEY_PREFIX = "cache:response:"

    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Initialize ResponseCache.

        WBS 2.6.3.1.3: Inject Redis client.

        Args:
            redis_client: Redis client for persistence
            ttl_seconds: Cache TTL in seconds (defaults to DEFAULT_CACHE_TTL_SECONDS)
        """
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds or DEFAULT_CACHE_TTL_SECONDS

    @property
    def ttl_seconds(self) -> int:
        """Get cache TTL in seconds."""
        return self._ttl_seconds

    def _generate_cache_key(self, request: ChatCompletionRequest) -> str:
        """
        Generate a cache key from a request.

        WBS 2.6.3.1.4: Cache key generation from request hash.

        The key is based on:
        - Model name
        - Messages content
        - Temperature
        - Max tokens
        - Other relevant parameters

        Args:
            request: Chat completion request

        Returns:
            Cache key string
        """
        # Build a deterministic representation of the request
        key_parts = {
            "model": request.model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
        }

        # Create hash of the key parts
        key_json = json.dumps(key_parts, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:32]

        return f"{self.KEY_PREFIX}{request.model}:{key_hash}"

    def _should_cache(self, request: ChatCompletionRequest) -> bool:
        """
        Determine if a request should be cached.

        WBS 2.6.3.1.8: Skip caching for tool_use requests.

        Tool calls are not cached because:
        - They may have side effects
        - Results depend on external state
        - Tool outputs vary even for identical inputs

        Streaming requests are also not cached because:
        - They return incremental responses
        - Caching would defeat the purpose of streaming

        Args:
            request: Chat completion request

        Returns:
            True if the request should be cached
        """
        # Skip caching for tool requests
        if request.tools:
            return False

        # Skip caching for streaming requests
        if request.stream:
            return False

        return True

    async def get(
        self,
        request: ChatCompletionRequest,
    ) -> Optional[ChatCompletionResponse]:
        """
        Get a cached response for a request.

        WBS 2.6.3.1.5: async get(request) -> ChatCompletionResponse | None.

        Args:
            request: Chat completion request

        Returns:
            Cached response or None if not found
        """
        try:
            # Check if request should be cached
            if not self._should_cache(request):
                return None

            cache_key = self._generate_cache_key(request)
            data = await self._redis.get(cache_key)

            if not data:
                return None

            # Deserialize response
            response_dict = json.loads(data)
            return ChatCompletionResponse.model_validate(response_dict)

        except Exception as e:
            raise CacheError(f"Failed to get cached response: {e}") from e

    async def set(
        self,
        request: ChatCompletionRequest,
        response: ChatCompletionResponse,
    ) -> bool:
        """
        Cache a response for a request.

        WBS 2.6.3.1.6: async set(request, response).
        WBS 2.6.3.1.7: Configure TTL from settings.

        Args:
            request: Chat completion request
            response: Chat completion response

        Returns:
            True if cached successfully
        """
        try:
            # Check if request should be cached
            if not self._should_cache(request):
                return False

            cache_key = self._generate_cache_key(request)

            # Serialize response
            response_json = response.model_dump_json()

            # Store with TTL
            await self._redis.set(
                cache_key,
                response_json,
                ex=self._ttl_seconds,
            )

            return True

        except Exception as e:
            raise CacheError(f"Failed to cache response: {e}") from e

    async def invalidate(
        self,
        request: ChatCompletionRequest,
    ) -> bool:
        """
        Invalidate a cached response.

        Args:
            request: Chat completion request

        Returns:
            True if invalidated successfully
        """
        try:
            cache_key = self._generate_cache_key(request)
            result = await self._redis.delete(cache_key)
            return result > 0

        except Exception as e:
            raise CacheError(f"Failed to invalidate cache: {e}") from e

    async def clear_all(self) -> int:
        """
        Clear all cached responses.

        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.KEY_PREFIX}*"
            deleted = 0

            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += await self._redis.delete(*keys)
                if cursor == 0:
                    break

            return deleted

        except Exception as e:
            raise CacheError(f"Failed to clear cache: {e}") from e
