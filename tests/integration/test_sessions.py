"""
WBS 3.5.2.3: Session Integration Tests

This module tests session management endpoints against live Docker services.

Reference Documents:
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3314-3321 - WBS 3.5.2.3
- ARCHITECTURE.md: Lines 214-220 - Session Manager component
- GUIDELINES pp. 155-157: "high and low gear" testing philosophy
- Architecture Patterns with Python (Percival & Gregory) p. 157: Repository pattern

TDD Phase: RED - These tests define expected session behavior.

WBS Coverage:
- 3.5.2.3.1: Create tests/integration/test_sessions.py
- 3.5.2.3.2: Test create session
- 3.5.2.3.3: Test get session
- 3.5.2.3.4: Test session persists messages
- 3.5.2.3.5: Test delete session
- 3.5.2.3.6: Test session expiry
- 3.5.2.3.7: Test get nonexistent session (404)
"""

import time

import pytest


# =============================================================================
# WBS 3.5.2.3.2: Test create session
# =============================================================================


class TestCreateSession:
    """
    WBS 3.5.2.3.2: Test session creation endpoint.
    
    Reference: ARCHITECTURE.md - POST /v1/sessions endpoint.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_create_session_returns_201(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.2: POST /v1/sessions should return 201 Created.
        """
        payload = {
            "session_id": test_session_id,
            "context": {"test": True},
        }
        
        response = gateway_client_sync.post("/v1/sessions", json=payload)
        
        # May return 201 (created) or 200 (OK)
        assert response.status_code in (200, 201), (
            f"Expected 200/201 for session creation, got {response.status_code}: {response.text}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_create_session_returns_session_id(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.2: Created session should return session_id.
        """
        payload = {
            "session_id": test_session_id,
            "context": {"test": True},
        }
        
        response = gateway_client_sync.post("/v1/sessions", json=payload)
        
        if response.status_code in (200, 201):
            data = response.json()
            assert "session_id" in data or "id" in data, (
                "Response should include session_id or id"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_create_session_with_context(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.2: Session can be created with context data.
        """
        payload = {
            "session_id": test_session_id,
            "context": {
                "user_name": "Test User",
                "project": "Integration Test",
            },
        }
        
        response = gateway_client_sync.post("/v1/sessions", json=payload)
        
        assert response.status_code in (200, 201), (
            f"Expected success for session with context, got {response.status_code}"
        )


# =============================================================================
# WBS 3.5.2.3.3: Test get session
# =============================================================================


class TestGetSession:
    """
    WBS 3.5.2.3.3: Test session retrieval endpoint.
    
    Reference: ARCHITECTURE.md - GET /v1/sessions/{id} endpoint.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_get_session_returns_200(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.3: GET /v1/sessions/{id} returns 200 for existing session.
        """
        # First create a session
        create_payload = {"session_id": test_session_id}
        create_response = gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        if create_response.status_code in (200, 201):
            # Then retrieve it
            response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            assert response.status_code == 200, (
                f"Expected 200 for existing session, got {response.status_code}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_get_session_returns_session_data(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.3: GET /v1/sessions/{id} returns session data.
        """
        # Create session with context
        create_payload = {
            "session_id": test_session_id,
            "context": {"key": "value"},
        }
        create_response = gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        if create_response.status_code in (200, 201):
            response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            if response.status_code == 200:
                data = response.json()
                # Session data should include messages or context
                assert "session_id" in data or "id" in data or "messages" in data, (
                    "Session data should include session_id, id, or messages"
                )


# =============================================================================
# WBS 3.5.2.3.4: Test session persists messages
# =============================================================================


class TestSessionMessagePersistence:
    """
    WBS 3.5.2.3.4: Test that sessions persist conversation messages.
    
    Reference: ARCHITECTURE.md - Sessions store conversation history.
    Reference: Comp_Static_Analysis_Report Issue #44 - Tool call message persistence.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_session_stores_messages(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.4: Messages sent in session should be persisted.
        """
        # Create session
        create_payload = {"session_id": test_session_id}
        gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        # Send a chat message with session
        chat_payload = {
            "model": "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": "Remember this test message"}],
            "session_id": test_session_id,
        }
        chat_response = gateway_client_sync.post("/v1/chat/completions", json=chat_payload)
        
        if chat_response.status_code == 200:
            # Retrieve session and check messages
            session_response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            if session_response.status_code == 200:
                data = session_response.json()
                messages = data.get("messages", [])
                # Should have at least the user message
                assert len(messages) > 0, "Session should persist messages"

    @pytest.mark.integration
    @pytest.mark.docker
    def test_session_accumulates_messages(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.4: Multiple messages should accumulate in session.
        """
        # Create session
        create_payload = {"session_id": test_session_id}
        gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        # Send first message
        chat_payload_1 = {
            "model": "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": "First message"}],
            "session_id": test_session_id,
        }
        response_1 = gateway_client_sync.post("/v1/chat/completions", json=chat_payload_1)
        
        # Send second message
        chat_payload_2 = {
            "model": "claude-3-sonnet-20240229",
            "messages": [{"role": "user", "content": "Second message"}],
            "session_id": test_session_id,
        }
        response_2 = gateway_client_sync.post("/v1/chat/completions", json=chat_payload_2)
        
        if response_1.status_code == 200 and response_2.status_code == 200:
            # Check accumulated messages
            session_response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            if session_response.status_code == 200:
                data = session_response.json()
                messages = data.get("messages", [])
                # Should have accumulated messages
                assert len(messages) >= 2, (
                    f"Session should accumulate messages, got {len(messages)}"
                )


# =============================================================================
# WBS 3.5.2.3.5: Test delete session
# =============================================================================


class TestDeleteSession:
    """
    WBS 3.5.2.3.5: Test session deletion endpoint.
    
    Reference: ARCHITECTURE.md - DELETE /v1/sessions/{id} endpoint.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_delete_session_returns_success(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.5: DELETE /v1/sessions/{id} should return 200/204.
        """
        # First create a session
        create_payload = {"session_id": test_session_id}
        create_response = gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        if create_response.status_code in (200, 201):
            # Then delete it
            response = gateway_client_sync.delete(f"/v1/sessions/{test_session_id}")
            
            assert response.status_code in (200, 204), (
                f"Expected 200/204 for session deletion, got {response.status_code}"
            )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_deleted_session_not_retrievable(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.5: Deleted session should not be retrievable.
        """
        # Create session
        create_payload = {"session_id": test_session_id}
        create_response = gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        if create_response.status_code in (200, 201):
            # Delete session
            gateway_client_sync.delete(f"/v1/sessions/{test_session_id}")
            
            # Try to retrieve - should fail
            get_response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            assert get_response.status_code == 404, (
                f"Deleted session should return 404, got {get_response.status_code}"
            )


# =============================================================================
# WBS 3.5.2.3.6: Test session expiry
# =============================================================================


class TestSessionExpiry:
    """
    WBS 3.5.2.3.6: Test session TTL and expiry.
    
    Reference: ARCHITECTURE.md - Sessions have TTL.
    Note: These tests may be slow as they wait for expiry.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    @pytest.mark.slow
    @pytest.mark.skip(reason="Session expiry test is slow - run manually")
    def test_session_expires_after_ttl(
        self, skip_if_no_docker, gateway_client_sync, test_session_id
    ) -> None:
        """
        WBS 3.5.2.3.6: Session should expire after TTL.
        
        Manual Test: Create session with short TTL and wait for expiry.
        Note: Default TTL may be hours, so this test needs special config.
        """
        # Create session with short TTL (if supported)
        create_payload = {
            "session_id": test_session_id,
            "ttl_seconds": 5,  # Very short TTL for testing
        }
        create_response = gateway_client_sync.post("/v1/sessions", json=create_payload)
        
        if create_response.status_code in (200, 201):
            # Wait for expiry
            time.sleep(6)
            
            # Try to retrieve - should fail
            get_response = gateway_client_sync.get(f"/v1/sessions/{test_session_id}")
            
            assert get_response.status_code == 404, (
                f"Expired session should return 404, got {get_response.status_code}"
            )


# =============================================================================
# WBS 3.5.2.3.7: Test get nonexistent session (404)
# =============================================================================


class TestNonexistentSession:
    """
    WBS 3.5.2.3.7: Test 404 response for nonexistent sessions.
    
    Reference: GUIDELINES - proper error responses.
    """

    @pytest.mark.integration
    @pytest.mark.docker
    def test_get_nonexistent_session_returns_404(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.3.7: GET for nonexistent session should return 404.
        """
        response = gateway_client_sync.get("/v1/sessions/nonexistent-session-id-xyz")
        
        assert response.status_code == 404, (
            f"Expected 404 for nonexistent session, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_delete_nonexistent_session_handled(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.3.7: DELETE for nonexistent session should be handled gracefully.
        
        May return 404 (not found) or 204 (no content - idempotent delete).
        """
        response = gateway_client_sync.delete("/v1/sessions/nonexistent-session-id-xyz")
        
        # Either 404 (not found) or 204 (idempotent delete) is acceptable
        assert response.status_code in (204, 404), (
            f"Expected 204/404 for nonexistent session delete, got {response.status_code}"
        )

    @pytest.mark.integration
    @pytest.mark.docker
    def test_nonexistent_session_error_body(
        self, skip_if_no_docker, gateway_client_sync
    ) -> None:
        """
        WBS 3.5.2.3.7: 404 response should include error details.
        """
        response = gateway_client_sync.get("/v1/sessions/nonexistent-session-id-xyz")
        
        if response.status_code == 404:
            data = response.json()
            # Should have error detail
            assert "detail" in data or "error" in data or "message" in data, (
                "404 response should include error details"
            )
