"""
Sessions Router - WBS 2.2.3 Sessions Endpoints

This module implements session management endpoints for conversation continuity.

Reference Documents:
- ARCHITECTURE.md: Lines 195-197 - POST, GET, DELETE /v1/sessions
- ARCHITECTURE.md: Lines 215-219 - Session Manager specification
- GUIDELINES: Sinha pp. 89-91 (DI patterns), pp. 193-195 (Pydantic)
- ANTI_PATTERN_ANALYSIS: §1.1 Optional types, §4.1 Extract to service class

Decision Log:
- WBS 2.2.3.3.7 PUT: DEFERRED - Not in ARCHITECTURE.md specification
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from src.core.config import get_settings
from src.core.exceptions import SessionError
from src.models.requests import SessionCreateRequest
from src.models.responses import SessionResponse


# =============================================================================
# WBS 2.2.3.1.3: Router Setup
# Pattern: Router separation (Sinha pp. 89-91)
# =============================================================================

router = APIRouter(
    prefix="/v1/sessions",
    tags=["Sessions"],
)


# =============================================================================
# WBS 2.2.3.1: SessionService - Service Layer
# Pattern: Extract operations to service class (ANTI_PATTERN §4.1)
# =============================================================================


class SessionService:
    """
    Service class for session operations.

    WBS 2.2.3.1: Encapsulates session lifecycle management.

    Pattern: Repository pattern (ANTI_PATTERN §4.1)
    Reference: ARCHITECTURE.md lines 215-219 - Session Manager

    Note: This is a stub implementation using in-memory storage.
    Methods are async to maintain interface compatibility with
    future Redis integration (WBS 2.3 Sessions Module).
    The async signature allows drop-in replacement without
    changing the router endpoints.
    """

    def __init__(self) -> None:
        """Initialize the session service."""
        self._settings = get_settings()
        # In-memory store for stub implementation
        # WBS 2.3: Replace with Redis session storage
        self._sessions: dict[str, dict[str, Any]] = {}

    async def create_session(  # NOSONAR - async for Redis compatibility (WBS 2.3)
        self,
        ttl_seconds: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Create a new session.

        WBS 2.2.3.3.1: POST /v1/sessions

        Args:
            ttl_seconds: Session TTL (default from settings)
            context: Optional initial context

        Returns:
            Session data dictionary
        """
        session_id = str(uuid.uuid4())
        ttl = ttl_seconds or self._settings.session_ttl_seconds
        now = datetime.now(timezone.utc)

        session_data = {
            "id": session_id,
            "messages": [],
            "context": context or {},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
        }

        # Store session (stub - in-memory)
        self._sessions[session_id] = session_data

        return session_data

    async def get_session(self, session_id: str) -> dict[str, Any]:  # NOSONAR - async for Redis
        """
        Retrieve a session by ID.

        WBS 2.2.3.3.2: GET /v1/sessions/{id}
        WBS 2.2.3.3.3: Raises SessionError if not found

        Args:
            session_id: The session ID to retrieve

        Returns:
            Session data dictionary

        Raises:
            SessionError: If session not found
        """
        if session_id not in self._sessions:
            raise SessionError(
                message=f"Session not found: {session_id}",
                session_id=session_id,
            )

        return self._sessions[session_id]

    async def delete_session(self, session_id: str) -> None:  # NOSONAR - async for Redis
        """
        Delete a session by ID.

        WBS 2.2.3.3.5: DELETE /v1/sessions/{id}

        Args:
            session_id: The session ID to delete

        Raises:
            SessionError: If session not found
        """
        if session_id not in self._sessions:
            raise SessionError(
                message=f"Session not found: {session_id}",
                session_id=session_id,
            )

        del self._sessions[session_id]


# =============================================================================
# Singleton service instance
# Pattern: Dependency injection preparation (Sinha pp. 89-91)
# =============================================================================

_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """
    Get or create the session service singleton.

    Pattern: Factory function for DI (Sinha p. 90)
    """
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


# =============================================================================
# WBS 2.2.3.3.1: POST /v1/sessions - Create Session
# Reference: ARCHITECTURE.md line 195
# =============================================================================


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionResponse,
    summary="Create a new session",
    description="Create a new session for conversation continuity.",
)
async def create_session(
    request: SessionCreateRequest,
) -> SessionResponse:
    """
    Create a new session.

    WBS 2.2.3.3.1: POST /v1/sessions returns 201 Created.

    Args:
        request: Session creation request with optional TTL and context

    Returns:
        SessionResponse with session ID and timestamps
    """
    service = get_session_service()
    session_data = await service.create_session(
        ttl_seconds=request.ttl_seconds,
        context=request.context,
    )

    return SessionResponse(**session_data)


# =============================================================================
# WBS 2.2.3.3.2: GET /v1/sessions/{id} - Retrieve Session
# WBS 2.2.3.3.3: Returns 404 if not found
# Reference: ARCHITECTURE.md line 196
# =============================================================================


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session state",
    description="Retrieve the current state of a session.",
)
async def get_session(session_id: str) -> SessionResponse:
    """
    Retrieve a session by ID.

    WBS 2.2.3.3.2: GET /v1/sessions/{id} returns 200 OK.
    WBS 2.2.3.3.3: Returns 404 if session not found.

    Args:
        session_id: The session ID to retrieve

    Returns:
        SessionResponse with session state

    Raises:
        HTTPException: 404 if session not found
    """
    service = get_session_service()

    try:
        session_data = await service.get_session(session_id)
        return SessionResponse(**session_data)
    except SessionError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {e.session_id}",
        ) from e


# =============================================================================
# WBS 2.2.3.3.5: DELETE /v1/sessions/{id} - Delete Session
# Reference: ARCHITECTURE.md line 197
# =============================================================================


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete session",
    description="Delete a session and its conversation history.",
)
async def delete_session(session_id: str) -> Response:
    """
    Delete a session by ID.

    WBS 2.2.3.3.5: DELETE /v1/sessions/{id} returns 204 No Content.

    Args:
        session_id: The session ID to delete

    Returns:
        Empty response with 204 status

    Raises:
        HTTPException: 404 if session not found
    """
    service = get_session_service()

    try:
        await service.delete_session(session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SessionError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {e.session_id}",
        ) from e
