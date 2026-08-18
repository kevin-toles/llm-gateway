"""Session Manager - Service layer for session lifecycle management.

WBS 2.5.2: Session Manager Implementation
- WBS 2.5.2.1: SessionManager class with CRUD operations
- WBS 2.5.2.2: Context management methods
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.core.config import get_settings
from src.models.domain import Message, Session
from src.sessions.store import SessionStore


class SessionError(Exception):
    """Base exception for session operations."""


class SessionNotFoundError(SessionError):
    """Raised when a session cannot be found."""


class SessionManager:
    """Service layer for session lifecycle management.

    Provides high-level operations for creating, retrieving, updating,
    and deleting sessions. Uses SessionStore for persistence.

    Args:
        store: SessionStore instance for persistence operations.
        ttl_seconds: Session time-to-live in seconds. Defaults to settings value.
    """

    def __init__(self, store: SessionStore, ttl_seconds: int | None = None) -> None:
        """Initialize SessionManager with store and TTL configuration."""
        self._store = store
        settings = get_settings()
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds

    async def create(self, context: dict[str, Any] | None = None) -> Session:
        """Create a new session.

        Args:
            context: Optional initial context dictionary.

        Returns:
            Newly created Session object.
        """
        now = datetime.now(timezone.utc)
        session = Session(
            id=str(uuid4()),
            messages=[],
            context=context if context is not None else {},
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )
        await self._store.save(session)
        return session

    async def get(self, session_id: str) -> Session:
        """Retrieve a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            The Session object.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self._store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        return session

    async def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: The session identifier.

        Note:
            This operation is idempotent - deleting a non-existent session
            does not raise an error.
        """
        await self._store.delete(session_id)

    async def add_message(self, session_id: str, message: Message) -> None:
        """Add a message to a session's history.

        Args:
            session_id: The session identifier.
            message: The Message to add.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self.get(session_id)
        session.messages.append(message)
        await self._store.save(session)

    async def update_context(self, session_id: str, context: dict[str, Any]) -> None:
        """Update a session's context.

        Merges the provided context with existing context. Existing keys
        are overwritten by new values.

        Args:
            session_id: The session identifier.
            context: Dictionary of context values to merge.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self.get(session_id)
        session.context.update(context)
        await self._store.save(session)

    async def get_history(self, session_id: str) -> list[Message]:
        """Get message history for a session.

        Args:
            session_id: The session identifier.

        Returns:
            List of Message objects.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self.get(session_id)
        return session.messages

    async def clear_history(self, session_id: str) -> None:
        """Clear message history for a session.

        Preserves the session and its context, only clears messages.

        Args:
            session_id: The session identifier.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self.get(session_id)
        session.messages = []
        await self._store.save(session)
