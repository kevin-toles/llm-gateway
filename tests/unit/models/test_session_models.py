"""
Tests for Session Domain Models - WBS 2.5.1.2

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Session Manager - "Creates sessions with TTL, Stores conversation history"
- GUIDELINES pp. 2153: "production systems often require external state stores (Redis)"
- GUIDELINES pp. 2257: "AI model gateways must manage stateful context windows"
- GUIDELINES pp. 59-65, 276: Domain modeling with Pydantic or @dataclass(frozen=True)
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

WBS Items:
- 2.5.1.2.1: Add Session model to src/models/domain.py
- 2.5.1.2.2: Add id: str (UUID)
- 2.5.1.2.3: Add messages: list[Message] for conversation history
- 2.5.1.2.4: Add context: dict for additional metadata
- 2.5.1.2.5: Add created_at: datetime
- 2.5.1.2.6: Add expires_at: datetime
- 2.5.1.2.7: Add Message model (role, content, tool_calls, tool_results)
- 2.5.1.2.8: Write RED tests for session model serialization
- 2.5.1.2.9: GREEN: implement and pass tests

Pattern: Domain models as value objects (Percival & Gregory pp. 59-65)
Pattern: Pydantic for validation (Sinha pp. 193-195)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


# =============================================================================
# WBS 2.5.1.2.7: Message Model Tests
# =============================================================================


class TestMessageModel:
    """Tests for Message domain model."""

    def test_message_can_be_instantiated(self) -> None:
        """
        WBS 2.5.1.2.7: Message class exists.
        """
        from src.models.domain import Message

        msg = Message(
            role="user",
            content="Hello, assistant!",
        )

        assert msg.role == "user"

    def test_message_has_role(self) -> None:
        """
        WBS 2.5.1.2.7: Message has role field.
        """
        from src.models.domain import Message

        msg = Message(role="assistant", content="Hello!")

        assert msg.role == "assistant"

    def test_message_has_content(self) -> None:
        """
        WBS 2.5.1.2.7: Message has content field.
        """
        from src.models.domain import Message

        msg = Message(role="user", content="What is Python?")

        assert msg.content == "What is Python?"

    def test_message_content_can_be_none(self) -> None:
        """
        WBS 2.5.1.2.7: Message content can be None (for tool_calls messages).
        Pattern: ANTI_PATTERN §1.1 - Optional types with explicit None
        """
        from src.models.domain import Message

        msg = Message(role="assistant", content=None)

        assert msg.content is None

    def test_message_has_tool_calls(self) -> None:
        """
        WBS 2.5.1.2.7: Message has optional tool_calls field.
        """
        from src.models.domain import Message

        tool_calls = [
            {"id": "call_1", "name": "search", "arguments": {"query": "test"}}
        ]

        msg = Message(role="assistant", content=None, tool_calls=tool_calls)

        assert msg.tool_calls == tool_calls

    def test_message_tool_calls_defaults_to_none(self) -> None:
        """
        WBS 2.5.1.2.7: tool_calls defaults to None.
        """
        from src.models.domain import Message

        msg = Message(role="user", content="Hi")

        assert msg.tool_calls is None

    def test_message_has_tool_results(self) -> None:
        """
        WBS 2.5.1.2.7: Message has optional tool_results field.
        """
        from src.models.domain import Message

        tool_results = [
            {"tool_call_id": "call_1", "content": "Search results...", "is_error": False}
        ]

        msg = Message(role="tool", content="Result", tool_results=tool_results)

        assert msg.tool_results == tool_results

    def test_message_tool_results_defaults_to_none(self) -> None:
        """
        WBS 2.5.1.2.7: tool_results defaults to None.
        """
        from src.models.domain import Message

        msg = Message(role="user", content="Hi")

        assert msg.tool_results is None

    def test_message_valid_roles(self) -> None:
        """
        WBS 2.5.1.2.7: Message role should accept standard roles.
        """
        from src.models.domain import Message

        roles = ["user", "assistant", "system", "tool"]

        for role in roles:
            msg = Message(role=role, content="test")
            assert msg.role == role

    def test_message_serialization_to_dict(self) -> None:
        """
        WBS 2.5.1.2.8: Message can be serialized to dict.
        """
        from src.models.domain import Message

        msg = Message(role="user", content="Hello")

        msg_dict = msg.model_dump()

        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Hello"

    def test_message_serialization_excludes_none(self) -> None:
        """
        WBS 2.5.1.2.8: Serialization can exclude None values.
        """
        from src.models.domain import Message

        msg = Message(role="user", content="Hello")

        msg_dict = msg.model_dump(exclude_none=True)

        assert "tool_calls" not in msg_dict
        assert "tool_results" not in msg_dict


# =============================================================================
# WBS 2.5.1.2.1-6: Session Model Tests
# =============================================================================


class TestSessionModel:
    """Tests for Session domain model."""

    def test_session_can_be_instantiated(self) -> None:
        """
        WBS 2.5.1.2.1: Session class exists.
        """
        from src.models.domain import Session

        session = Session(
            id="sess_abc123",
            messages=[],
            context={},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert session.id == "sess_abc123"

    def test_session_has_id(self) -> None:
        """
        WBS 2.5.1.2.2: Session has id field (UUID string).
        """
        from src.models.domain import Session

        session = Session(
            id="550e8400-e29b-41d4-a716-446655440000",
            messages=[],
            context={},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert session.id == "550e8400-e29b-41d4-a716-446655440000"

    def test_session_has_messages_list(self) -> None:
        """
        WBS 2.5.1.2.3: Session has messages list for conversation history.
        """
        from src.models.domain import Session, Message

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ]

        session = Session(
            id="sess_1",
            messages=messages,
            context={},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert len(session.messages) == 2
        assert session.messages[0].content == "Hello"

    def test_session_messages_defaults_to_empty_list(self) -> None:
        """
        WBS 2.5.1.2.3: messages defaults to empty list.
        Pattern: ANTI_PATTERN §1.5 - Avoid mutable defaults
        """
        from src.models.domain import Session

        session = Session(
            id="sess_empty",
            context={},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert session.messages == []

    def test_session_has_context_dict(self) -> None:
        """
        WBS 2.5.1.2.4: Session has context dict for additional metadata.
        """
        from src.models.domain import Session

        context = {
            "user_id": "user_123",
            "model": "claude-3-sonnet",
            "temperature": 0.7,
        }

        session = Session(
            id="sess_ctx",
            messages=[],
            context=context,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert session.context["user_id"] == "user_123"
        assert session.context["model"] == "claude-3-sonnet"

    def test_session_context_defaults_to_empty_dict(self) -> None:
        """
        WBS 2.5.1.2.4: context defaults to empty dict.
        """
        from src.models.domain import Session

        session = Session(
            id="sess_no_ctx",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert session.context == {}

    def test_session_has_created_at(self) -> None:
        """
        WBS 2.5.1.2.5: Session has created_at datetime.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)

        session = Session(
            id="sess_time",
            messages=[],
            context={},
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )

        assert session.created_at == now

    def test_session_has_expires_at(self) -> None:
        """
        WBS 2.5.1.2.6: Session has expires_at datetime.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=2)

        session = Session(
            id="sess_exp",
            messages=[],
            context={},
            created_at=now,
            expires_at=expires,
        )

        assert session.expires_at == expires

    def test_session_is_expired_property(self) -> None:
        """
        WBS 2.5.1.2.6: Session can determine if expired.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)

        session = Session(
            id="sess_old",
            messages=[],
            context={},
            created_at=past - timedelta(hours=1),
            expires_at=past,  # Expired 1 hour ago
        )

        assert session.is_expired is True

    def test_session_is_not_expired(self) -> None:
        """
        WBS 2.5.1.2.6: Session knows when not expired.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)

        session = Session(
            id="sess_fresh",
            messages=[],
            context={},
            created_at=now,
            expires_at=future,
        )

        assert session.is_expired is False


# =============================================================================
# WBS 2.5.1.2.8: Session Serialization Tests
# =============================================================================


class TestSessionSerialization:
    """Tests for Session model serialization (JSON)."""

    def test_session_serialization_to_dict(self) -> None:
        """
        WBS 2.5.1.2.8: Session can be serialized to dict.
        """
        from src.models.domain import Session, Message

        now = datetime.now(timezone.utc)

        session = Session(
            id="sess_ser",
            messages=[Message(role="user", content="Hi")],
            context={"key": "value"},
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )

        session_dict = session.model_dump()

        assert session_dict["id"] == "sess_ser"
        assert len(session_dict["messages"]) == 1
        assert session_dict["context"]["key"] == "value"

    def test_session_serialization_to_json(self) -> None:
        """
        WBS 2.5.1.2.8: Session can be serialized to JSON string.
        """
        from src.models.domain import Session, Message
        import json

        now = datetime.now(timezone.utc)

        session = Session(
            id="sess_json",
            messages=[Message(role="user", content="Hello")],
            context={"model": "gpt-4"},
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )

        json_str = session.model_dump_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["id"] == "sess_json"

    def test_session_deserialization_from_dict(self) -> None:
        """
        WBS 2.5.1.2.8: Session can be deserialized from dict.
        """
        from src.models.domain import Session

        now = datetime.now(timezone.utc)

        data = {
            "id": "sess_deser",
            "messages": [{"role": "user", "content": "Test"}],
            "context": {"temperature": 0.5},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }

        session = Session.model_validate(data)

        assert session.id == "sess_deser"
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"

    def test_session_deserialization_from_json(self) -> None:
        """
        WBS 2.5.1.2.8: Session can be deserialized from JSON string.
        """
        from src.models.domain import Session
        import json

        now = datetime.now(timezone.utc)

        json_str = json.dumps({
            "id": "sess_from_json",
            "messages": [],
            "context": {},
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        })

        session = Session.model_validate_json(json_str)

        assert session.id == "sess_from_json"

    def test_session_roundtrip_serialization(self) -> None:
        """
        WBS 2.5.1.2.8: Session survives serialization roundtrip.
        """
        from src.models.domain import Session, Message

        now = datetime.now(timezone.utc)

        original = Session(
            id="sess_roundtrip",
            messages=[
                Message(role="system", content="You are helpful"),
                Message(role="user", content="Hi"),
                Message(role="assistant", content="Hello!"),
            ],
            context={"user_id": "u_123", "model": "claude"},
            created_at=now,
            expires_at=now + timedelta(seconds=3600),
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = Session.model_validate_json(json_str)

        assert restored.id == original.id
        assert len(restored.messages) == len(original.messages)
        assert restored.context == original.context
        # Datetime comparison (allowing for microsecond precision loss)
        assert abs((restored.created_at - original.created_at).total_seconds()) < 1


# =============================================================================
# Session Validation Tests
# =============================================================================


class TestSessionValidation:
    """Tests for Session model validation."""

    def test_session_id_required(self) -> None:
        """
        WBS 2.5.1.2.2: Session id is required.
        """
        from src.models.domain import Session
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Session(
                messages=[],
                context={},
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

    def test_session_created_at_required(self) -> None:
        """
        WBS 2.5.1.2.5: Session created_at is required.
        """
        from src.models.domain import Session
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Session(
                id="sess_no_created",
                messages=[],
                context={},
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

    def test_session_expires_at_required(self) -> None:
        """
        WBS 2.5.1.2.6: Session expires_at is required.
        """
        from src.models.domain import Session
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Session(
                id="sess_no_expires",
                messages=[],
                context={},
                created_at=datetime.now(timezone.utc),
            )

    def test_message_role_required(self) -> None:
        """
        WBS 2.5.1.2.7: Message role is required.
        """
        from src.models.domain import Message
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Message(content="No role provided")


# =============================================================================
# Session/Message Importability Tests
# =============================================================================


class TestSessionModelsImportable:
    """Tests that session models are importable from expected locations."""

    def test_models_importable_from_domain(self) -> None:
        """Session and Message models are importable from src.models.domain."""
        from src.models.domain import Session, Message

        assert Session is not None
        assert Message is not None
