"""
Tests for Session Manager - WBS 2.5.2

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Session Manager - "Creates sessions with TTL, Stores conversation history"
- GUIDELINES pp. 949: Service layer coordinating repository operations
- GUIDELINES pp. 2153: External state stores (Redis)

WBS Items:
- 2.5.2.1.1: Create src/sessions/manager.py
- 2.5.2.1.2: Implement SessionManager class
- 2.5.2.1.3: Inject SessionStore dependency
- 2.5.2.1.4: Implement async create() -> Session
- 2.5.2.1.5: Generate UUID for session ID
- 2.5.2.1.6: Set created_at and expires_at
- 2.5.2.1.7: Save to store and return
- 2.5.2.1.8: Implement async get(session_id: str) -> Session
- 2.5.2.1.9: Raise SessionError if not found
- 2.5.2.1.10: Implement async delete(session_id: str)
- 2.5.2.1.11: Implement async add_message(session_id: str, message: Message)
- 2.5.2.1.12: Load session, append message, save
- 2.5.2.1.13: Write RED test: create returns new session
- 2.5.2.1.14: Write RED test: add_message updates history
- 2.5.2.1.15: Write RED test: get nonexistent raises error
- 2.5.2.1.16: GREEN: implement and pass all tests
- 2.5.2.2.1: Implement async update_context(session_id: str, context: dict)
- 2.5.2.2.2: Implement async get_history(session_id: str) -> list[Message]
- 2.5.2.2.3: Implement async clear_history(session_id: str)

Pattern: Service layer (Percival & Gregory)
Pattern: Dependency injection for SessionStore (Sinha pp. 89-90)
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import pytest
import pytest_asyncio


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def fake_redis():
    """Provide a fake Redis client for testing."""
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.aclose()


@pytest_asyncio.fixture
async def session_store(fake_redis):
    """Provide a SessionStore with fake Redis."""
    from src.sessions.store import SessionStore

    return SessionStore(redis_client=fake_redis)


@pytest_asyncio.fixture
async def session_manager(session_store):
    """
    Provide a SessionManager with SessionStore dependency.
    
    WBS 2.5.2.1.3: Inject SessionStore dependency.
    """
    from src.sessions.manager import SessionManager

    return SessionManager(store=session_store)


# =============================================================================
# WBS 2.5.2.1.2-3: SessionManager Class Tests
# =============================================================================


class TestSessionManagerClass:
    """Tests for SessionManager class instantiation."""

    @pytest.mark.asyncio
    async def test_session_manager_can_be_instantiated(self, session_store) -> None:
        """
        WBS 2.5.2.1.2: SessionManager class exists.
        """
        from src.sessions.manager import SessionManager

        manager = SessionManager(store=session_store)

        assert isinstance(manager, SessionManager)

    @pytest.mark.asyncio
    async def test_session_manager_requires_store(self, session_store) -> None:
        """
        WBS 2.5.2.1.3: SessionManager requires SessionStore dependency.
        """
        from src.sessions.manager import SessionManager

        manager = SessionManager(store=session_store)

        assert manager._store is session_store

    @pytest.mark.asyncio
    async def test_session_manager_accepts_custom_ttl(self, session_store) -> None:
        """
        SessionManager can use custom TTL for sessions.
        """
        from src.sessions.manager import SessionManager

        manager = SessionManager(store=session_store, ttl_seconds=7200)

        assert manager._ttl_seconds == 7200

    @pytest.mark.asyncio
    async def test_session_manager_default_ttl(self, session_store) -> None:
        """
        SessionManager uses default TTL from settings.
        """
        from src.sessions.manager import SessionManager

        manager = SessionManager(store=session_store)

        # Default TTL should match settings (3600 seconds)
        assert manager._ttl_seconds == 3600


# =============================================================================
# WBS 2.5.2.1.4-7, 2.5.2.1.13: Create Session Tests
# =============================================================================


class TestSessionManagerCreate:
    """Tests for SessionManager.create() method."""

    @pytest.mark.asyncio
    async def test_create_returns_session(self, session_manager) -> None:
        """
        WBS 2.5.2.1.4: create() returns a Session.
        WBS 2.5.2.1.13: RED test: create returns new session.
        """
        from src.models.domain import Session

        session = await session_manager.create()

        assert isinstance(session, Session)

    @pytest.mark.asyncio
    async def test_create_generates_uuid(self, session_manager) -> None:
        """
        WBS 2.5.2.1.5: create() generates UUID for session ID.
        """
        session = await session_manager.create()

        # Session ID should be a valid UUID
        parsed_uuid = uuid.UUID(session.id)
        assert str(parsed_uuid) == session.id

    @pytest.mark.asyncio
    async def test_create_sets_created_at(self, session_manager) -> None:
        """
        WBS 2.5.2.1.6: create() sets created_at timestamp.
        """
        before = datetime.now(timezone.utc)
        session = await session_manager.create()
        after = datetime.now(timezone.utc)

        assert before <= session.created_at <= after

    @pytest.mark.asyncio
    async def test_create_sets_expires_at(self, session_manager) -> None:
        """
        WBS 2.5.2.1.6: create() sets expires_at timestamp.
        """
        session = await session_manager.create()

        # expires_at should be in the future
        assert session.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_create_with_initial_context(self, session_manager) -> None:
        """
        create() can accept initial context.
        """
        context = {"user_id": "u_123", "model": "claude-3-sonnet"}

        session = await session_manager.create(context=context)

        assert session.context["user_id"] == "u_123"
        assert session.context["model"] == "claude-3-sonnet"

    @pytest.mark.asyncio
    async def test_create_saves_to_store(self, session_manager) -> None:
        """
        WBS 2.5.2.1.7: create() saves session to store.
        """
        session = await session_manager.create()

        # Session should be retrievable
        retrieved = await session_manager.get(session.id)
        assert retrieved.id == session.id

    @pytest.mark.asyncio
    async def test_create_with_custom_ttl(self, session_store) -> None:
        """
        create() uses manager's configured TTL.
        """
        from src.sessions.manager import SessionManager

        # Create manager with custom TTL
        manager = SessionManager(store=session_store, ttl_seconds=1800)
        session = await manager.create()

        # expires_at should be ~30 minutes from now
        expected_expiry = datetime.now(timezone.utc) + timedelta(seconds=1800)
        delta = abs((session.expires_at - expected_expiry).total_seconds())
        assert delta < 5  # Within 5 seconds

    @pytest.mark.asyncio
    async def test_create_starts_with_empty_messages(self, session_manager) -> None:
        """
        create() starts with empty message history.
        """
        session = await session_manager.create()

        assert session.messages == []


# =============================================================================
# WBS 2.5.2.1.8-9, 2.5.2.1.15: Get Session Tests
# =============================================================================


class TestSessionManagerGet:
    """Tests for SessionManager.get() method."""

    @pytest.mark.asyncio
    async def test_get_returns_session(self, session_manager) -> None:
        """
        WBS 2.5.2.1.8: get() returns the session.
        """
        created = await session_manager.create()

        retrieved = await session_manager.get(created.id)

        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises_error(self, session_manager) -> None:
        """
        WBS 2.5.2.1.9: get() raises SessionNotFoundError if not found.
        WBS 2.5.2.1.15: RED test: get nonexistent raises error.
        """
        from src.sessions.manager import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            await session_manager.get("nonexistent_session_id")

    @pytest.mark.asyncio
    async def test_get_preserves_messages(self, session_manager) -> None:
        """
        get() preserves message history.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        await session_manager.add_message(
            session.id, Message(role="user", content="Hello")
        )

        retrieved = await session_manager.get(session.id)

        assert len(retrieved.messages) == 1
        assert retrieved.messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_get_preserves_context(self, session_manager) -> None:
        """
        get() preserves context metadata.
        """
        context = {"user_id": "u_456"}
        session = await session_manager.create(context=context)

        retrieved = await session_manager.get(session.id)

        assert retrieved.context["user_id"] == "u_456"


# =============================================================================
# WBS 2.5.2.1.10: Delete Session Tests
# =============================================================================


class TestSessionManagerDelete:
    """Tests for SessionManager.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_removes_session(self, session_manager) -> None:
        """
        WBS 2.5.2.1.10: delete() removes session.
        """
        from src.sessions.manager import SessionNotFoundError

        session = await session_manager.create()
        await session_manager.delete(session.id)

        with pytest.raises(SessionNotFoundError):
            await session_manager.get(session.id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_idempotent(self, session_manager) -> None:
        """
        delete() is idempotent for nonexistent sessions.
        """
        # Should not raise
        await session_manager.delete("nonexistent_session_id")


# =============================================================================
# WBS 2.5.2.1.11-12, 2.5.2.1.14: Add Message Tests
# =============================================================================


class TestSessionManagerAddMessage:
    """Tests for SessionManager.add_message() method."""

    @pytest.mark.asyncio
    async def test_add_message_updates_history(self, session_manager) -> None:
        """
        WBS 2.5.2.1.11: add_message() appends message to history.
        WBS 2.5.2.1.14: RED test: add_message updates history.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        message = Message(role="user", content="Hello, assistant!")

        await session_manager.add_message(session.id, message)

        retrieved = await session_manager.get(session.id)
        assert len(retrieved.messages) == 1
        assert retrieved.messages[0].content == "Hello, assistant!"

    @pytest.mark.asyncio
    async def test_add_message_preserves_existing(self, session_manager) -> None:
        """
        WBS 2.5.2.1.12: add_message() preserves existing messages.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        await session_manager.add_message(
            session.id, Message(role="user", content="First")
        )
        await session_manager.add_message(
            session.id, Message(role="assistant", content="Second")
        )

        retrieved = await session_manager.get(session.id)
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].content == "First"
        assert retrieved.messages[1].content == "Second"

    @pytest.mark.asyncio
    async def test_add_message_to_nonexistent_raises_error(self, session_manager) -> None:
        """
        add_message() raises error for nonexistent session.
        """
        from src.models.domain import Message
        from src.sessions.manager import SessionNotFoundError

        message = Message(role="user", content="Hello")

        with pytest.raises(SessionNotFoundError):
            await session_manager.add_message("nonexistent", message)

    @pytest.mark.asyncio
    async def test_add_message_saves_to_store(self, session_manager, session_store) -> None:
        """
        WBS 2.5.2.1.12: add_message() saves updated session to store.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        await session_manager.add_message(
            session.id, Message(role="user", content="Test")
        )

        # Verify directly from store
        stored = await session_store.get(session.id)
        assert len(stored.messages) == 1


# =============================================================================
# WBS 2.5.2.2.1: Update Context Tests
# =============================================================================


class TestSessionManagerUpdateContext:
    """Tests for SessionManager.update_context() method."""

    @pytest.mark.asyncio
    async def test_update_context_sets_values(self, session_manager) -> None:
        """
        WBS 2.5.2.2.1: update_context() sets context values.
        """
        session = await session_manager.create()

        await session_manager.update_context(
            session.id, {"temperature": "0.7", "model": "gpt-4"}
        )

        retrieved = await session_manager.get(session.id)
        assert retrieved.context["temperature"] == "0.7"
        assert retrieved.context["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_update_context_merges_values(self, session_manager) -> None:
        """
        update_context() merges with existing context.
        """
        session = await session_manager.create(context={"user_id": "u_123"})

        await session_manager.update_context(session.id, {"model": "claude"})

        retrieved = await session_manager.get(session.id)
        assert retrieved.context["user_id"] == "u_123"
        assert retrieved.context["model"] == "claude"

    @pytest.mark.asyncio
    async def test_update_context_overwrites_existing_keys(self, session_manager) -> None:
        """
        update_context() overwrites existing keys.
        """
        session = await session_manager.create(context={"model": "gpt-3"})

        await session_manager.update_context(session.id, {"model": "gpt-4"})

        retrieved = await session_manager.get(session.id)
        assert retrieved.context["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_update_context_nonexistent_raises_error(self, session_manager) -> None:
        """
        update_context() raises error for nonexistent session.
        """
        from src.sessions.manager import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            await session_manager.update_context("nonexistent", {"key": "value"})


# =============================================================================
# WBS 2.5.2.2.2: Get History Tests
# =============================================================================


class TestSessionManagerGetHistory:
    """Tests for SessionManager.get_history() method."""

    @pytest.mark.asyncio
    async def test_get_history_returns_messages(self, session_manager) -> None:
        """
        WBS 2.5.2.2.2: get_history() returns message list.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        await session_manager.add_message(
            session.id, Message(role="user", content="Hello")
        )
        await session_manager.add_message(
            session.id, Message(role="assistant", content="Hi there!")
        )

        history = await session_manager.get_history(session.id)

        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_get_history_empty_session(self, session_manager) -> None:
        """
        get_history() returns empty list for new session.
        """
        session = await session_manager.create()

        history = await session_manager.get_history(session.id)

        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_nonexistent_raises_error(self, session_manager) -> None:
        """
        get_history() raises error for nonexistent session.
        """
        from src.sessions.manager import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            await session_manager.get_history("nonexistent")


# =============================================================================
# WBS 2.5.2.2.3: Clear History Tests
# =============================================================================


class TestSessionManagerClearHistory:
    """Tests for SessionManager.clear_history() method."""

    @pytest.mark.asyncio
    async def test_clear_history_removes_messages(self, session_manager) -> None:
        """
        WBS 2.5.2.2.3: clear_history() removes all messages.
        """
        from src.models.domain import Message

        session = await session_manager.create()
        await session_manager.add_message(
            session.id, Message(role="user", content="Hello")
        )
        await session_manager.add_message(
            session.id, Message(role="assistant", content="Hi!")
        )

        await session_manager.clear_history(session.id)

        retrieved = await session_manager.get(session.id)
        assert retrieved.messages == []

    @pytest.mark.asyncio
    async def test_clear_history_preserves_context(self, session_manager) -> None:
        """
        clear_history() preserves context metadata.
        """
        from src.models.domain import Message

        session = await session_manager.create(context={"user_id": "u_123"})
        await session_manager.add_message(
            session.id, Message(role="user", content="Hello")
        )

        await session_manager.clear_history(session.id)

        retrieved = await session_manager.get(session.id)
        assert retrieved.context["user_id"] == "u_123"

    @pytest.mark.asyncio
    async def test_clear_history_nonexistent_raises_error(self, session_manager) -> None:
        """
        clear_history() raises error for nonexistent session.
        """
        from src.sessions.manager import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            await session_manager.clear_history("nonexistent")


# =============================================================================
# Error Class Tests
# =============================================================================


class TestSessionManagerErrors:
    """Tests for SessionManager error classes."""

    def test_session_not_found_error_exists(self) -> None:
        """
        SessionNotFoundError exception class exists.
        """
        from src.sessions.manager import SessionNotFoundError

        error = SessionNotFoundError("sess_123")

        assert "sess_123" in str(error)

    def test_session_not_found_error_is_exception(self) -> None:
        """
        SessionNotFoundError is an Exception subclass.
        """
        from src.sessions.manager import SessionNotFoundError

        assert issubclass(SessionNotFoundError, Exception)

    def test_session_error_exists(self) -> None:
        """
        SessionError base exception class exists.
        """
        from src.sessions.manager import SessionError

        error = SessionError("Something went wrong")

        assert str(error) == "Something went wrong"


# =============================================================================
# Importability Tests
# =============================================================================


class TestSessionManagerImportable:
    """Tests that SessionManager is importable from expected locations."""

    def test_session_manager_importable_from_sessions(self) -> None:
        """SessionManager is importable from src.sessions."""
        from src.sessions import SessionManager

        assert callable(SessionManager)

    def test_session_manager_importable_from_manager(self) -> None:
        """SessionManager is importable from src.sessions.manager."""
        from src.sessions.manager import SessionManager

        assert callable(SessionManager)

    def test_errors_importable_from_sessions(self) -> None:
        """Error classes are importable from src.sessions."""
        from src.sessions import SessionNotFoundError, SessionError

        assert SessionNotFoundError is not None
        assert SessionError is not None
