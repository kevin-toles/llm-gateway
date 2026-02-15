"""
Session Store - WBS 2.5.1.1 Redis Store Implementation

This module provides Redis-based session storage for the LLM Gateway.

Reference Documents:
- ARCHITECTURE.md: "Uses Redis for distributed session storage"
- GUIDELINES pp. 2153: "production systems often require external state stores (Redis)"
- GUIDELINES pp. 949: Repository pattern - "hides the boring details of data access"
- GUIDELINES pp. 2309: Redis caching patterns with connection pooling

WBS Items:
- 2.5.1.1.1: Create src/sessions/__init__.py
- 2.5.1.1.2: Create src/sessions/store.py
- 2.5.1.1.3: Implement SessionStore class
- 2.5.1.1.4: Inject Redis client dependency
- 2.5.1.1.5: Implement async save(session: Session)
- 2.5.1.1.6: Serialize session to JSON
- 2.5.1.1.7: Store with TTL from settings
- 2.5.1.1.8: Implement async get(session_id: str) -> Session | None
- 2.5.1.1.9: Implement async delete(session_id: str) -> bool
- 2.5.1.1.10: Implement async exists(session_id: str) -> bool
- 2.5.1.1.16: REFACTOR: add connection error handling

Pattern: Repository pattern (Percival & Gregory pp. 86)
Pattern: Dependency injection for Redis client (Sinha pp. 89-90)
"""

from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis

from src.core.config import get_settings
from src.models.domain import Session


# =============================================================================
# WBS 2.5.1.1.16: Session Store Error
# =============================================================================


class SessionStoreError(Exception):
    """
    Exception raised for session store errors.

    WBS 2.5.1.1.16: Connection error handling.

    Raised when Redis operations fail due to connection issues,
    serialization errors, or other storage-related problems.

    Pattern: Custom exception for domain-specific errors
    """

    pass


# =============================================================================
# WBS 2.5.1.1.3: SessionStore Class
# =============================================================================


class SessionStore:
    """
    Redis-based session storage.

    WBS 2.5.1.1.3: Implement SessionStore class.

    Provides async CRUD operations for Session objects using Redis
    as the backing store. Sessions are stored as JSON with TTL
    based on session expiration time.

    Pattern: Repository pattern (Percival & Gregory pp. 86)
    Pattern: Dependency injection for Redis client (Sinha pp. 89-90)
    Reference: ARCHITECTURE.md - "Uses Redis for distributed session storage"

    Attributes:
        _redis: The Redis client instance.
        _key_prefix: Prefix for Redis keys.
        _default_ttl_seconds: Default TTL when session has no expiry.

    Example:
        >>> import redis.asyncio as redis
        >>> client = redis.from_url("redis://localhost:6379")
        >>> store = SessionStore(redis_client=client)
        >>> await store.save(session)
        >>> retrieved = await store.get(session.id)
    """

    def __init__(
        self,
        redis_client: Redis,
        key_prefix: str = "sessions:",
        default_ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Initialize SessionStore with Redis client.

        WBS 2.5.1.1.4: Inject Redis client dependency.

        Args:
            redis_client: Async Redis client instance.
            key_prefix: Prefix for all session keys in Redis.
            default_ttl_seconds: Default TTL when session has no expiry.
                                 Defaults to settings.session_ttl_seconds.
        """
        self._redis: Redis = redis_client
        self._key_prefix: str = key_prefix

        if default_ttl_seconds is None:
            settings = get_settings()
            self._default_ttl_seconds: int = settings.session_ttl_seconds
        else:
            self._default_ttl_seconds = default_ttl_seconds

    def _make_key(self, session_id: str) -> str:
        """
        Generate Redis key for a session ID.

        Args:
            session_id: The session's unique identifier.

        Returns:
            Full Redis key with prefix.
        """
        return f"{self._key_prefix}{session_id}"

    def _calculate_ttl(self, session: Session) -> int:
        """
        Calculate TTL for a session based on its expires_at.

        WBS 2.5.1.1.7: Store with TTL from settings.

        Args:
            session: The session to calculate TTL for.

        Returns:
            TTL in seconds (minimum 1 second).
        """
        now = datetime.now(timezone.utc)
        ttl_delta = session.expires_at - now
        ttl_seconds = int(ttl_delta.total_seconds())

        # Ensure minimum TTL of 1 second
        return max(ttl_seconds, 1)

    async def save(self, session: Session) -> None:
        """
        Save a session to Redis.

        WBS 2.5.1.1.5: Implement async save(session: Session).
        WBS 2.5.1.1.6: Serialize session to JSON.
        WBS 2.5.1.1.7: Store with TTL from settings.

        Serializes the session to JSON and stores it with a TTL
        based on the session's expires_at timestamp.

        Args:
            session: The session to save.

        Raises:
            SessionStoreError: If the save operation fails.
        """
        try:
            key = self._make_key(session.id)
            ttl = self._calculate_ttl(session)

            # Serialize session to JSON
            json_data = session.model_dump_json()

            # Store with TTL
            await self._redis.setex(key, ttl, json_data)

        except Exception as e:
            raise SessionStoreError(f"Failed to save session {session.id}: {e}") from e

    async def get(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session from Redis.

        WBS 2.5.1.1.8: Implement async get(session_id: str) -> Session | None.
        Issue 38: Added application-level expiration check.

        This method includes two layers of expiration handling:
        1. Redis TTL: Keys auto-expire based on session.expires_at
        2. Application check: Defensive check for sessions where expires_at
           has passed but Redis TTL hasn't evicted the key yet (race condition)

        Args:
            session_id: The session's unique identifier.

        Returns:
            The Session if found and not expired, None otherwise.

        Raises:
            SessionStoreError: If the get operation fails.
        """
        try:
            key = self._make_key(session_id)
            json_data = await self._redis.get(key)

            if json_data is None:
                return None

            # Deserialize from JSON
            session = Session.model_validate_json(json_data)

            # Issue 38: Application-level expiration check
            # Defensive check in case Redis TTL hasn't evicted the key yet
            now = datetime.now(timezone.utc)
            if session.expires_at < now:
                # Session has logically expired, clean up and return None
                await self._redis.delete(key)
                return None

            return session

        except SessionStoreError:
            raise
        except Exception as e:
            raise SessionStoreError(
                f"Failed to get session {session_id}: {e}"
            ) from e

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session from Redis.

        WBS 2.5.1.1.9: Implement async delete(session_id: str) -> bool.

        Args:
            session_id: The session's unique identifier.

        Returns:
            True if the session was deleted, False if it didn't exist.

        Raises:
            SessionStoreError: If the delete operation fails.
        """
        try:
            key = self._make_key(session_id)
            deleted_count = await self._redis.delete(key)

            return deleted_count > 0

        except Exception as e:
            raise SessionStoreError(
                f"Failed to delete session {session_id}: {e}"
            ) from e

    async def exists(self, session_id: str) -> bool:
        """
        Check if a session exists in Redis.

        WBS 2.5.1.1.10: Implement async exists(session_id: str) -> bool.

        Args:
            session_id: The session's unique identifier.

        Returns:
            True if the session exists, False otherwise.

        Raises:
            SessionStoreError: If the exists check fails.
        """
        try:
            key = self._make_key(session_id)
            return await self._redis.exists(key) > 0

        except Exception as e:
            raise SessionStoreError(
                f"Failed to check session existence {session_id}: {e}"
            ) from e
