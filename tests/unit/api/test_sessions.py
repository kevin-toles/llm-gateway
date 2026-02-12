"""
Tests for Sessions Router - WBS 2.2.3 Sessions Endpoints

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- ARCHITECTURE.md: Lines 195-197 - POST, GET, DELETE /v1/sessions
- GUIDELINES: Sinha pp. 89-91 (DI patterns), pp. 193-195 (Pydantic)
- ANTI_PATTERN_ANALYSIS: §1.1 Optional types, §4.1 Extract to service class

Decision Log:
- WBS 2.2.3.3.7 PUT: DEFERRED - Not in ARCHITECTURE.md specification
"""

import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

# These imports will FAIL until we implement the router - this is the RED phase
# WBS 2.2.3.1.3: Import from src/api/routes/sessions.py
from src.api.routes.sessions import router as sessions_router
from src.api.routes.sessions import SessionService


# =============================================================================
# WBS 2.2.3.1 Sessions Router Setup
# =============================================================================


class TestSessionsRouterSetup:
    """Test suite for sessions router setup - WBS 2.2.3.1"""

    def test_sessions_router_is_fastapi_router(self):
        """
        WBS 2.2.3.1.3: Sessions router must be a FastAPI APIRouter instance.

        Pattern: Router separation (Sinha pp. 89-91)
        """
        from fastapi import APIRouter

        assert isinstance(sessions_router, APIRouter)

    def test_sessions_router_has_correct_prefix(self, client: TestClient):
        """
        WBS 2.2.3.1.3: Router must have prefix /v1/sessions.

        Reference: ARCHITECTURE.md line 23 - sessions.py # /v1/sessions/*
        """
        # POST to /v1/sessions should work (not 404 for path)
        response = client.post("/v1/sessions", json={})
        # May fail validation, but should not be 404
        assert response.status_code != 404

    def test_sessions_router_has_sessions_tag(self):
        """
        WBS 2.2.3.1.3: Router must have "Sessions" tag for OpenAPI.

        Pattern: API documentation grouping (Sinha p. 89)
        """
        assert "Sessions" in sessions_router.tags


# =============================================================================
# WBS 2.2.3.2 Session Models
# =============================================================================


class TestSessionModels:
    """Test suite for session models - WBS 2.2.3.2"""

    def test_session_response_model_has_required_fields(self):
        """
        WBS 2.2.3.2.2: SessionResponse must include id, messages, context, timestamps.

        Pattern: Pydantic models (Sinha pp. 193-195)
        """
        from src.models.responses import SessionResponse

        # Check model fields exist
        fields = SessionResponse.model_fields
        assert "id" in fields
        assert "messages" in fields
        assert "context" in fields
        assert "created_at" in fields
        assert "expires_at" in fields

    def test_session_response_model_id_is_required(self):
        """
        WBS 2.2.3.2.2: Session ID is required in response.
        """
        from src.models.responses import SessionResponse
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SessionResponse(messages=[], context={})

    def test_session_create_request_model_exists(self):
        """
        WBS 2.2.3.2.1: SessionCreateRequest model must exist.

        Pattern: Pydantic validation (Sinha pp. 193-195)
        """
        from src.models.requests import SessionCreateRequest

        # Should be importable
        assert SessionCreateRequest is not None

    def test_session_create_request_has_optional_ttl(self):
        """
        WBS 2.2.3.2.1: TTL field should be optional with default.

        Pattern: Optional[T] with None (ANTI_PATTERN §1.1)
        """
        from src.models.requests import SessionCreateRequest

        # Create without ttl - should use default
        request = SessionCreateRequest()
        assert request.ttl_seconds is None or isinstance(request.ttl_seconds, int)

    def test_session_create_request_has_optional_context(self):
        """
        WBS 2.2.3.2.1: Context field should be optional.

        Pattern: Optional[T] with None (ANTI_PATTERN §1.1)
        """
        from src.models.requests import SessionCreateRequest

        fields = SessionCreateRequest.model_fields
        assert "context" in fields
        # Should allow None
        request = SessionCreateRequest()
        assert request.context is None or isinstance(request.context, dict)


# =============================================================================
# WBS 2.2.3.3.1 POST /v1/sessions - Create Session
# =============================================================================


class TestCreateSession:
    """Test suite for POST /v1/sessions - WBS 2.2.3.3.1"""

    def test_create_session_returns_201(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.1: POST /v1/sessions should return 201 Created.

        Reference: ARCHITECTURE.md line 195 - POST /v1/sessions
        """
        response = client.post("/v1/sessions", json={})
        assert response.status_code == 201

    def test_create_session_returns_session_response(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.1: Response must include session ID and timestamps.
        """
        response = client.post("/v1/sessions", json={})
        data = response.json()

        assert "id" in data
        assert "created_at" in data
        assert "expires_at" in data

    def test_create_session_generates_unique_id(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.1: Each session must have a unique ID.
        """
        response = client.post("/v1/sessions", json={})
        data = response.json()

        assert data["id"] is not None
        assert len(data["id"]) > 0

    def test_create_session_accepts_custom_ttl(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.1: Should accept custom TTL in request.

        Reference: Settings.session_ttl_seconds default is 3600
        """
        response = client.post("/v1/sessions", json={"ttl_seconds": 7200})
        assert response.status_code == 201

    def test_create_session_accepts_initial_context(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.1: Should accept initial context in request.
        """
        context = {"user_id": "test-user", "preferences": {"language": "en"}}
        response = client.post("/v1/sessions", json={"context": context})
        assert response.status_code == 201


# =============================================================================
# WBS 2.2.3.3.2 GET /v1/sessions/{id} - Retrieve Session
# =============================================================================


class TestGetSession:
    """Test suite for GET /v1/sessions/{id} - WBS 2.2.3.3.2"""

    def test_get_session_returns_200(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.2: GET /v1/sessions/{id} should return 200 OK.

        Reference: ARCHITECTURE.md line 196 - GET /v1/sessions/{id}
        """
        response = client.get("/v1/sessions/test-session-id")
        assert response.status_code == 200

    def test_get_session_returns_session_data(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.2: Response must include session state.
        """
        response = client.get("/v1/sessions/test-session-id")
        data = response.json()

        assert "id" in data
        assert "messages" in data
        assert "context" in data
        assert "created_at" in data
        assert "expires_at" in data

    def test_get_session_returns_correct_id(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.2: Returned session ID must match requested ID.
        """
        session_id = "test-session-123"
        mock_session_service.get_session.return_value = {
            "id": session_id,
            "messages": [],
            "context": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.now(timezone.utc).isoformat(),
        }

        response = client.get(f"/v1/sessions/{session_id}")
        data = response.json()

        assert data["id"] == session_id


# =============================================================================
# WBS 2.2.3.3.3 GET Nonexistent Session - 404 Not Found
# =============================================================================


class TestGetNonexistentSession:
    """Test suite for GET nonexistent session - WBS 2.2.3.3.3"""

    def test_get_nonexistent_session_returns_404(
        self, client: TestClient, mock_session_service_not_found: MagicMock
    ):
        """
        WBS 2.2.3.3.3: GET nonexistent session should return 404 Not Found.

        Pattern: Graceful error handling (GUIDELINES)
        """
        response = client.get("/v1/sessions/nonexistent-id")
        assert response.status_code == 404

    def test_get_nonexistent_session_returns_error_detail(
        self, client: TestClient, mock_session_service_not_found: MagicMock
    ):
        """
        WBS 2.2.3.3.3: 404 response must include error details.

        Reference: ErrorCode.SESSION_ERROR from exceptions.py
        """
        response = client.get("/v1/sessions/nonexistent-id")
        data = response.json()

        assert "detail" in data or "error" in data

    def test_get_nonexistent_session_includes_session_id_in_error(
        self, client: TestClient, mock_session_service_not_found: MagicMock
    ):
        """
        WBS 2.2.3.3.3: Error should reference the session ID.

        Pattern: Contextual error messages (ANTI_PATTERN §3.1)
        """
        session_id = "nonexistent-session-456"
        response = client.get(f"/v1/sessions/{session_id}")
        data = response.json()

        # Error message should contain the session ID for debugging
        error_text = str(data)
        assert session_id in error_text or "not found" in error_text.lower()


# =============================================================================
# WBS 2.2.3.3.5 DELETE /v1/sessions/{id} - Delete Session
# =============================================================================


class TestDeleteSession:
    """Test suite for DELETE /v1/sessions/{id} - WBS 2.2.3.3.5"""

    def test_delete_session_returns_204(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.5: DELETE /v1/sessions/{id} should return 204 No Content.

        Reference: ARCHITECTURE.md line 197 - DELETE /v1/sessions/{id}
        """
        response = client.delete("/v1/sessions/test-session-id")
        assert response.status_code == 204

    def test_delete_session_returns_empty_body(
        self, client: TestClient, mock_session_service: MagicMock
    ):
        """
        WBS 2.2.3.3.5: 204 response should have no body.

        Pattern: REST semantics - 204 No Content
        """
        response = client.delete("/v1/sessions/test-session-id")
        assert response.content == b"" or response.text == ""

    def test_delete_nonexistent_session_returns_404(
        self, client: TestClient, mock_session_service_not_found: MagicMock
    ):
        """
        WBS 2.2.3.3.5: DELETE nonexistent session should return 404.
        """
        response = client.delete("/v1/sessions/nonexistent-id")
        assert response.status_code == 404


# =============================================================================
# WBS 2.2.3.1 SessionService - Service Layer
# =============================================================================


class TestSessionService:
    """
    Test suite for SessionService - WBS 2.2.3.1 Service Layer

    Pattern: Repository pattern for session operations (ANTI_PATTERN §4.1)
    """

    def test_session_service_exists(self):
        """
        WBS 2.2.3.1: SessionService class must exist.

        Pattern: Extract operations to service class (ANTI_PATTERN §4.1)
        """
        assert SessionService is not None

    def test_session_service_has_create_method(self):
        """
        WBS 2.2.3.3.1: SessionService must have create_session method.
        """
        service = SessionService()
        assert hasattr(service, "create_session")
        assert callable(getattr(service, "create_session"))

    def test_session_service_has_get_method(self):
        """
        WBS 2.2.3.3.2: SessionService must have get_session method.
        """
        service = SessionService()
        assert hasattr(service, "get_session")
        assert callable(getattr(service, "get_session"))

    def test_session_service_has_delete_method(self):
        """
        WBS 2.2.3.3.5: SessionService must have delete_session method.
        """
        service = SessionService()
        assert hasattr(service, "delete_session")
        assert callable(getattr(service, "delete_session"))

    @pytest.mark.asyncio
    async def test_session_service_create_returns_session_dict(self):
        """
        WBS 2.2.3.3.1: create_session must return session data.
        """
        service = SessionService()
        result = await service.create_session()

        assert isinstance(result, dict)
        assert "id" in result

    @pytest.mark.asyncio
    async def test_session_service_get_raises_for_nonexistent(self):
        """
        WBS 2.2.3.3.3: get_session must raise SessionError for nonexistent.

        Pattern: Specific exceptions (GUIDELINES)
        """
        from src.core.exceptions import SessionError

        service = SessionService()

        with pytest.raises(SessionError):
            await service.get_session("nonexistent-id")


# =============================================================================
# Fixtures - Following Repository Pattern for Test Doubles
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with sessions router mounted.

    Pattern: FakeRepository (Architecture Patterns with Python p. 157)
    """
    app = FastAPI()
    app.include_router(sessions_router)

    return TestClient(app)


@pytest.fixture
def mock_session_service():
    """Mock SessionService that returns valid session data."""
    with patch("src.api.routes.sessions.get_session_service") as mock_factory:
        mock_instance = MagicMock()

        # Configure create_session mock
        mock_instance.create_session = AsyncMock(
            return_value={
                "id": "test-session-id",
                "messages": [],
                "context": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Configure get_session mock
        mock_instance.get_session = AsyncMock(
            return_value={
                "id": "test-session-id",
                "messages": [],
                "context": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Configure delete_session mock
        mock_instance.delete_session = AsyncMock(return_value=None)

        mock_factory.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_session_service_not_found():
    """Mock SessionService that raises SessionError for not found."""
    from src.core.exceptions import SessionError

    with patch("src.api.routes.sessions.get_session_service") as mock_factory:
        mock_instance = MagicMock()

        # Configure get_session to raise SessionError
        mock_instance.get_session = AsyncMock(
            side_effect=SessionError("Session not found", session_id="nonexistent-id")
        )

        # Configure delete_session to raise SessionError
        mock_instance.delete_session = AsyncMock(
            side_effect=SessionError("Session not found", session_id="nonexistent-id")
        )

        mock_factory.return_value = mock_instance
        yield mock_instance
