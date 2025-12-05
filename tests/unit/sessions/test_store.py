"""
Tests for Session Store - WBS 2.5.1.1

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: "Uses Redis for distributed session storage"
- GUIDELINES pp. 2153: "production systems often require external state stores (Redis)"
- GUIDELINES pp. 949: Repository pattern for data access abstraction
- GUIDELINES pp. 2309: Redis caching patterns

WBS Items:
- 2.5.1.1.3: Implement SessionStore class
- 2.5.1.1.4: Inject Redis client dependency
- 2.5.1.1.5: Implement async save(session: Session)
- 2.5.1.1.6: Serialize session to JSON
- 2.5.1.1.7: Store with TTL from settings
- 2.5.1.1.8: Implement async get(session_id: str) -> Session | None
- 2.5.1.1.9: Implement async delete(session_id: str) -> bool
- 2.5.1.1.10: Implement async exists(session_id: str) -> bool
- 2.5.1.1.11: Write RED test: save and retrieve session
- 2.5.1.1.12: Write RED test: session expires after TTL
- 2.5.1.1.13: Write RED test: delete removes session
- 2.5.1.1.14: Write RED test: get nonexistent returns None
- 2.5.1.1.15: GREEN: implement and pass all tests (use fakeredis)
- 2.5.1.1.16: REFACTOR: add connection error handling

Pattern: Repository pattern (Percival & Gregory pp. 86)
Pattern: FakeRepository for testing (Percival & Gregory pp. 157)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio


# =============================================================================
# Fixtures for fakeredis
# =============================================================================


@pytest_asyncio.fixture
async def fake_redis():
    """
    Provide a fake Redis client for testing.
    
    Pattern: FakeRepository - test doubles without complex mocking
    Reference: Percival & Gregory pp. 157
    """
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.aclose()


@pytest_asyncio.fixture
async def session_store(fake_redis):
    """
    Provide a SessionStore with fake Redis for testing.
    
    WBS 2.5.1.1.4: Inject Redis client dependency.
    """
    from src.sessions.store import SessionStore

    store = SessionStore(redis_client=fake_redis)
    return store


@pytest.fixture
def sample_session():
    """Provide a sample session for testing."""
    from src.models.domain import Session, Message

    now = datetime.now(timezone.utc)
    return Session(
        id="sess_test_123",
        messages=[
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ],
        context={"user_id": "u_456", "model": "claude-3-sonnet"},
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )


# =============================================================================
# WBS 2.5.1.1.3: SessionStore Class Tests
# =============================================================================


class TestSessionStoreClass:
    """Tests for SessionStore class instantiation."""

    @pytest.mark.asyncio
    async def test_session_store_can_be_instantiated(self, fake_redis) -> None:
        """
        WBS 2.5.1.1.3: SessionStore class exists.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis)

        assert store is not None

    @pytest.mark.asyncio
    async def test_session_store_accepts_redis_client(self, fake_redis) -> None:
        """
        WBS 2.5.1.1.4: SessionStore accepts Redis client dependency.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis)

        assert store._redis is fake_redis

    @pytest.mark.asyncio
    async def test_session_store_accepts_custom_ttl(self, fake_redis) -> None:
        """
        WBS 2.5.1.1.7: SessionStore can use custom TTL.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis, default_ttl_seconds=7200)

        assert store._default_ttl_seconds == 7200

    @pytest.mark.asyncio
    async def test_session_store_default_ttl(self, fake_redis) -> None:
        """
        WBS 2.5.1.1.7: SessionStore uses default TTL from settings.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis)

        # Default TTL should match settings (3600 seconds)
        assert store._default_ttl_seconds == 3600

    @pytest.mark.asyncio
    async def test_session_store_key_prefix(self, fake_redis) -> None:
        """
        SessionStore uses key prefix for Redis keys.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis, key_prefix="test_sessions:")

        assert store._key_prefix == "test_sessions:"


# =============================================================================
# WBS 2.5.1.1.5-6: Save Session Tests
# =============================================================================


class TestSessionStoreSave:
    """Tests for SessionStore.save() method."""

    @pytest.mark.asyncio
    async def test_save_session(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.5: save() stores session in Redis.
        WBS 2.5.1.1.11: RED test: save and retrieve session.
        """
        await session_store.save(sample_session)

        # Session should now exist
        exists = await session_store.exists(sample_session.id)
        assert exists is True

    @pytest.mark.asyncio
    async def test_save_session_serializes_to_json(self, session_store, sample_session, fake_redis) -> None:
        """
        WBS 2.5.1.1.6: save() serializes session to JSON.
        """
        await session_store.save(sample_session)

        # Get raw data from Redis
        key = session_store._make_key(sample_session.id)
        raw_data = await fake_redis.get(key)

        # Should be valid JSON
        import json
        data = json.loads(raw_data)
        assert data["id"] == sample_session.id

    @pytest.mark.asyncio
    async def test_save_session_with_ttl(self, session_store, sample_session, fake_redis) -> None:
        """
        WBS 2.5.1.1.7: save() stores with TTL.
        """
        await session_store.save(sample_session)

        # Check TTL is set
        key = session_store._make_key(sample_session.id)
        ttl = await fake_redis.ttl(key)

        # TTL should be positive (session has 1 hour expiry)
        assert ttl > 0

    @pytest.mark.asyncio
    async def test_save_session_updates_existing(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.5: save() updates existing session.
        """
        from src.models.domain import Message

        await session_store.save(sample_session)

        # Update session with new message
        sample_session.messages.append(Message(role="user", content="New message"))
        await session_store.save(sample_session)

        # Retrieved session should have new message
        retrieved = await session_store.get(sample_session.id)
        assert len(retrieved.messages) == 3


# =============================================================================
# WBS 2.5.1.1.8: Get Session Tests
# =============================================================================


class TestSessionStoreGet:
    """Tests for SessionStore.get() method."""

    @pytest.mark.asyncio
    async def test_get_session(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.8: get() retrieves session from Redis.
        WBS 2.5.1.1.11: RED test: save and retrieve session.
        """
        await session_store.save(sample_session)

        retrieved = await session_store.get(sample_session.id)

        assert retrieved is not None
        assert retrieved.id == sample_session.id

    @pytest.mark.asyncio
    async def test_get_session_preserves_messages(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.8: get() preserves message history.
        """
        await session_store.save(sample_session)

        retrieved = await session_store.get(sample_session.id)

        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].role == "user"
        assert retrieved.messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_get_session_preserves_context(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.8: get() preserves context metadata.
        """
        await session_store.save(sample_session)

        retrieved = await session_store.get(sample_session.id)

        assert retrieved.context["user_id"] == "u_456"
        assert retrieved.context["model"] == "claude-3-sonnet"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_none(self, session_store) -> None:
        """
        WBS 2.5.1.1.8: get() returns None for nonexistent session.
        WBS 2.5.1.1.14: RED test: get nonexistent returns None.
        """
        result = await session_store.get("nonexistent_session_id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_expired_session_returns_none(self, session_store, fake_redis) -> None:
        """
        Issue 38: get() returns None for logically expired sessions.
        
        Even if Redis TTL hasn't evicted the key yet, sessions with
        expires_at in the past should return None for defensive coding.
        
        This tests the application-level expiration check that supplements
        Redis TTL behavior.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)
        
        # Create session that will expire immediately
        expired_session = Session(
            id="sess_expired_check",
            messages=[],
            context={},
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(seconds=1),  # Already expired
        )
        
        # Directly save to Redis bypassing TTL calculation (simulates race condition)
        key = f"sessions:{expired_session.id}"
        await fake_redis.set(key, expired_session.model_dump_json())
        
        # Even though key exists in Redis, get() should check expires_at
        result = await session_store.get(expired_session.id)
        
        assert result is None


# =============================================================================
# WBS 2.5.1.1.9: Delete Session Tests
# =============================================================================


class TestSessionStoreDelete:
    """Tests for SessionStore.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_session(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.9: delete() removes session from Redis.
        WBS 2.5.1.1.13: RED test: delete removes session.
        """
        await session_store.save(sample_session)

        result = await session_store.delete(sample_session.id)

        assert result is True
        assert await session_store.exists(sample_session.id) is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_returns_false(self, session_store) -> None:
        """
        WBS 2.5.1.1.9: delete() returns False for nonexistent session.
        """
        result = await session_store.delete("nonexistent_session_id")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_cannot_be_retrieved(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.13: After delete, session cannot be retrieved.
        """
        await session_store.save(sample_session)
        await session_store.delete(sample_session.id)

        result = await session_store.get(sample_session.id)

        assert result is None


# =============================================================================
# WBS 2.5.1.1.10: Exists Method Tests
# =============================================================================


class TestSessionStoreExists:
    """Tests for SessionStore.exists() method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_session(self, session_store, sample_session) -> None:
        """
        WBS 2.5.1.1.10: exists() returns True for existing session.
        """
        await session_store.save(sample_session)

        result = await session_store.exists(sample_session.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_nonexistent_session(self, session_store) -> None:
        """
        WBS 2.5.1.1.10: exists() returns False for nonexistent session.
        """
        result = await session_store.exists("nonexistent_session_id")

        assert result is False


# =============================================================================
# WBS 2.5.1.1.12: TTL and Expiration Tests
# =============================================================================


class TestSessionStoreTTL:
    """Tests for session TTL and expiration behavior."""

    @pytest.mark.asyncio
    async def test_session_ttl_uses_session_expires_at(self, session_store, sample_session, fake_redis) -> None:
        """
        WBS 2.5.1.1.7: TTL is calculated from session.expires_at.
        """
        await session_store.save(sample_session)

        key = session_store._make_key(sample_session.id)
        ttl = await fake_redis.ttl(key)

        # TTL should be approximately 1 hour (3600 seconds), allow some variance
        assert 3500 < ttl <= 3600

    @pytest.mark.asyncio
    async def test_session_ttl_uses_default_for_expired_session(self, session_store, fake_redis) -> None:
        """
        WBS 2.5.1.1.7: Uses minimum TTL for already expired sessions.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)
        expired_session = Session(
            id="sess_expired",
            messages=[],
            context={},
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),  # Already expired
        )

        await session_store.save(expired_session)

        # Should still be saved with a minimum TTL
        exists = await session_store.exists(expired_session.id)
        assert exists is True


# =============================================================================
# WBS 2.5.1.1.16: Connection Error Handling Tests
# =============================================================================


class TestSessionStoreErrorHandling:
    """Tests for SessionStore error handling."""

    @pytest.mark.asyncio
    async def test_session_store_error_class_exists(self) -> None:
        """
        WBS 2.5.1.1.16: SessionStoreError exception class exists.
        """
        from src.sessions.store import SessionStoreError

        error = SessionStoreError("Connection failed")

        assert str(error) == "Connection failed"

    @pytest.mark.asyncio
    async def test_session_store_error_is_exception(self) -> None:
        """
        WBS 2.5.1.1.16: SessionStoreError is an Exception subclass.
        """
        from src.sessions.store import SessionStoreError

        assert issubclass(SessionStoreError, Exception)


# =============================================================================
# Key Generation Tests
# =============================================================================


class TestSessionStoreKeyGeneration:
    """Tests for Redis key generation."""

    @pytest.mark.asyncio
    async def test_make_key_with_default_prefix(self, session_store) -> None:
        """
        Key generation uses prefix.
        """
        key = session_store._make_key("sess_123")

        assert key.startswith("sessions:")
        assert "sess_123" in key

    @pytest.mark.asyncio
    async def test_make_key_with_custom_prefix(self, fake_redis) -> None:
        """
        Key generation uses custom prefix.
        """
        from src.sessions.store import SessionStore

        store = SessionStore(redis_client=fake_redis, key_prefix="custom:")
        key = store._make_key("sess_123")

        assert key == "custom:sess_123"


# =============================================================================
# Importability Tests
# =============================================================================


class TestSessionStoreImportable:
    """Tests that SessionStore is importable from expected locations."""

    def test_session_store_importable_from_sessions(self) -> None:
        """SessionStore is importable from src.sessions."""
        from src.sessions import SessionStore

        assert SessionStore is not None

    def test_session_store_error_importable_from_sessions(self) -> None:
        """SessionStoreError is importable from src.sessions."""
        from src.sessions import SessionStoreError

        assert SessionStoreError is not None

    def test_session_store_importable_from_store(self) -> None:
        """SessionStore is importable from src.sessions.store."""
        from src.sessions.store import SessionStore

        assert SessionStore is not None
