"""
Tests for Chat Router - WBS 2.2.2 Chat Completions Endpoint

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- GUIDELINES: FastAPI Pydantic validators (Sinha pp. 193-195)
- GUIDELINES: Dependency injection patterns (Sinha pp. 89-91)
- GUIDELINES: Tool/function calling (AI Engineering pp. 1463-1587)
- ANTI_PATTERN_ANALYSIS: §1.1 Optional types with explicit None
- ANTI_PATTERN_ANALYSIS: §4.1 Cognitive complexity - extract to services
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# RED Phase: These imports will fail until implementation
from src.api.routes.chat import router as chat_router
from src.api.routes.chat import ChatService


class TestChatRouter:
    """Test suite for chat router setup - WBS 2.2.2.1"""

    # =========================================================================
    # WBS 2.2.2.1.1: Router Structure
    # =========================================================================

    def test_chat_router_is_fastapi_router(self):
        """
        WBS 2.2.2.1.1: Chat router must be a FastAPI APIRouter instance.

        Pattern: Router separation (Sinha p. 89)
        """
        from fastapi import APIRouter

        assert isinstance(chat_router, APIRouter)

    def test_chat_router_has_correct_prefix(self):
        """
        WBS 2.2.2.1.2: Chat router must use /v1/chat prefix.

        Pattern: API versioning (Buelta p. 126)
        """
        assert chat_router.prefix == "/v1/chat"

    def test_chat_router_has_correct_tags(self):
        """
        WBS 2.2.2.1.3: Chat router must have 'Chat' tag for OpenAPI docs.
        """
        assert "Chat" in chat_router.tags


class TestChatCompletionsEndpoint:
    """Test suite for chat completions endpoint - WBS 2.2.2.3"""

    # =========================================================================
    # WBS 2.2.2.3.1: POST /v1/chat/completions basic functionality
    # =========================================================================

    def test_chat_completions_returns_200(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.3.1: POST /v1/chat/completions returns 200 for valid request.

        Pattern: REST constraints (Buelta p. 93)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_chat_completions_returns_expected_schema(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.3.2: Response must include id, object, created, model, choices, usage.

        Pattern: OpenAI API compatibility
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=payload)
        data = response.json()

        assert "id" in data
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data

    def test_chat_completions_choices_have_correct_structure(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.3.3: Each choice must have index, message, finish_reason.

        Pattern: OpenAI API compatibility
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=payload)
        data = response.json()

        assert len(data["choices"]) >= 1
        choice = data["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice
        assert "role" in choice["message"]
        assert "content" in choice["message"]

    def test_chat_completions_usage_has_correct_structure(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.3.4: Usage must include prompt_tokens, completion_tokens, total_tokens.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=payload)
        data = response.json()

        usage = data["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage

    # =========================================================================
    # WBS 2.2.2.3.5: Request Validation
    # =========================================================================

    def test_chat_completions_requires_model(self, client: TestClient):
        """
        WBS 2.2.2.3.5: Request must include 'model' field.

        Pattern: Pydantic validation (Sinha pp. 193-195)
        """
        payload = {"messages": [{"role": "user", "content": "Hello"}]}
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422  # Validation error

    def test_chat_completions_requires_messages(self, client: TestClient):
        """
        WBS 2.2.2.3.6: Request must include 'messages' field.
        """
        payload = {"model": "gpt-4"}
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422

    def test_chat_completions_requires_non_empty_messages(self, client: TestClient):
        """
        WBS 2.2.2.3.7: Messages array must not be empty.

        Pattern: Field validators (Sinha p. 195)
        """
        payload = {"model": "gpt-4", "messages": []}
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422

    def test_chat_completions_validates_message_role(self, client: TestClient):
        """
        WBS 2.2.2.3.8: Message role must be valid (system, user, assistant, tool).
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "invalid_role", "content": "Hello"}],
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422


class TestChatCompletionsOptionalParams:
    """Test suite for optional parameters - WBS 2.2.2.2"""

    # =========================================================================
    # WBS 2.2.2.2.1: Optional Parameters
    # Pattern: Optional types with explicit None (ANTI_PATTERN §1.1)
    # =========================================================================

    def test_chat_completions_accepts_session_id(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.2.9: Request may include 'session_id' parameter.

        Pattern: Session management (ARCHITECTURE.md - Session Manager)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "session_id": "sess-12345",
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_session_id_field_exists_in_request_model(self):
        """
        WBS 2.2.2.2.9: ChatCompletionRequest must have session_id field.

        Pattern: Optional types with explicit None (ANTI_PATTERN §1.1)
        """
        from src.models.requests import ChatCompletionRequest

        # Create request with session_id
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            session_id="sess-12345",
        )
        assert hasattr(request, "session_id")
        assert request.session_id == "sess-12345"

    def test_session_id_is_optional(self):
        """
        WBS 2.2.2.2.9: session_id should be optional with None default.

        Pattern: Optional types with explicit None (ANTI_PATTERN §1.1)
        """
        from src.models.requests import ChatCompletionRequest

        # Create request without session_id
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert request.session_id is None

    def test_chat_completions_accepts_temperature(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.2.1: Request may include 'temperature' parameter.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_chat_completions_accepts_max_tokens(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.2.2: Request may include 'max_tokens' parameter.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_chat_completions_accepts_tools(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.2.3: Request may include 'tools' parameter for function calling.

        Pattern: Tool/function calling (AI Engineering pp. 1463-1587)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                }
            ],
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_chat_completions_accepts_tool_choice(
        self, client: TestClient, mock_chat_service: MagicMock
    ):
        """
        WBS 2.2.2.2.4: Request may include 'tool_choice' parameter.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "test_fn",
                        "description": "Test",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "tool_choice": "auto",
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200

    def test_chat_completions_validates_temperature_range(self, client: TestClient):
        """
        WBS 2.2.2.2.5: Temperature must be between 0 and 2.

        Pattern: Field validators (Sinha p. 195)
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 3.0,  # Invalid: > 2.0
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422

    def test_chat_completions_validates_max_tokens_positive(self, client: TestClient):
        """
        WBS 2.2.2.2.6: max_tokens must be positive integer.
        """
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": -1,  # Invalid
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422


class TestChatService:
    """
    Test suite for ChatService - WBS 2.2.2.3.9 Service Layer Extraction

    Pattern: Cognitive complexity reduction (ANTI_PATTERN §4.1)
    Pattern: Dependency injection (Sinha pp. 89-91)
    """

    def test_chat_service_exists(self):
        """
        WBS 2.2.2.3.9: ChatService class must exist for business logic extraction.
        """
        from src.api.routes.chat import ChatService

        service = ChatService()
        assert isinstance(service, ChatService)

    @pytest.mark.asyncio
    async def test_chat_service_create_completion_returns_response(self):
        """
        WBS 2.2.2.3.10: ChatService.create_completion must return ChatCompletionResponse.
        """
        from src.api.routes.chat import ChatService
        from src.models.requests import ChatCompletionRequest
        from src.models.responses import ChatCompletionResponse

        service = ChatService()
        request = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )
        response = await service.create_completion(request)
        assert isinstance(response, ChatCompletionResponse)

    def test_get_chat_service_returns_service(self):
        """
        WBS 2.2.2.3.11: get_chat_service dependency must return ChatService.

        Pattern: Dependency injection factory (Sinha p. 90)
        """
        from src.api.routes.chat import get_chat_service

        service = get_chat_service()
        assert isinstance(service, ChatService)


class TestProviderErrorHandling:
    """
    Test suite for provider error handling - WBS 2.2.2.3.9

    Pattern: Service mesh error translation (Newman pp. 273-275)
    Pattern: Specific exceptions with context (ANTI_PATTERN §3.1)

    Reference: "Service meshes and API gateways should translate internal
    service failures into appropriate HTTP status codes... 502 Bad Gateway
    indicates the upstream service failed."
    """

    def test_provider_error_returns_502(self, client: TestClient):
        """
        WBS 2.2.2.3.9: Provider error must return 502 Bad Gateway.

        Pattern: Error translation (Newman pp. 273-275)
        """
        from src.core.exceptions import ProviderError

        # Mock ChatService to raise ProviderError
        with patch(
            "src.api.routes.chat.ChatService.create_completion",
            side_effect=ProviderError(
                message="Provider API unavailable",
                provider="anthropic",
                status_code=503,
            ),
        ):
            payload = {
                "model": "claude-3-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
            }
            response = client.post("/v1/chat/completions", json=payload)

            assert response.status_code == 502
            data = response.json()
            assert "error" in data

    def test_provider_error_includes_error_details(self, client: TestClient):
        """
        WBS 2.2.2.3.9: 502 response must include error details.

        Pattern: Error context (ANTI_PATTERN §3.1)
        """
        from src.core.exceptions import ProviderError

        with patch(
            "src.api.routes.chat.ChatService.create_completion",
            side_effect=ProviderError(
                message="Rate limit exceeded",
                provider="openai",
                status_code=429,
            ),
        ):
            payload = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            }
            response = client.post("/v1/chat/completions", json=payload)

            assert response.status_code == 502
            data = response.json()
            assert "error" in data
            assert "message" in data["error"]
            assert "code" in data["error"]

    def test_provider_error_logs_exception(self, client: TestClient):
        """
        WBS 2.2.2.3.9: Provider errors must be logged for debugging.

        Pattern: Exception logging (ANTI_PATTERN §3.1)
        """
        from src.core.exceptions import ProviderError

        with patch(
            "src.api.routes.chat.ChatService.create_completion",
            side_effect=ProviderError(
                message="Connection timeout",
                provider="ollama",
            ),
        ):
            with patch("src.api.routes.chat.logger") as mock_logger:
                payload = {
                    "model": "llama2",
                    "messages": [{"role": "user", "content": "Hello"}],
                }
                response = client.post("/v1/chat/completions", json=payload)

                assert response.status_code == 502
                # Verify error was logged
                mock_logger.error.assert_called()


class TestRequestResponseModels:
    """
    Test suite for Pydantic models - WBS 2.2.2.2

    Pattern: Pydantic validation (Sinha pp. 193-195)
    """

    def test_chat_completion_request_model_exists(self):
        """WBS 2.2.2.2.7: ChatCompletionRequest model must exist and be a Pydantic model."""
        from src.models.requests import ChatCompletionRequest
        from pydantic import BaseModel

        assert issubclass(ChatCompletionRequest, BaseModel)

    def test_chat_completion_response_model_exists(self):
        """WBS 2.2.2.2.8: ChatCompletionResponse model must exist and be a Pydantic model."""
        from src.models.responses import ChatCompletionResponse
        from pydantic import BaseModel

        assert issubclass(ChatCompletionResponse, BaseModel)

    def test_message_model_exists(self):
        """WBS 2.2.2.2.9: Message model must exist and be a Pydantic model."""
        from src.models.requests import Message
        from pydantic import BaseModel

        assert issubclass(Message, BaseModel)

    def test_choice_model_exists(self):
        """WBS 2.2.2.2.10: Choice model must exist and be a Pydantic model."""
        from src.models.responses import Choice
        from pydantic import BaseModel

        assert issubclass(Choice, BaseModel)

    def test_usage_model_exists(self):
        """WBS 2.2.2.2.11: Usage model must exist and be a Pydantic model."""
        from src.models.responses import Usage
        from pydantic import BaseModel

        assert issubclass(Usage, BaseModel)


# =============================================================================
# Fixtures - Following Repository Pattern for Test Doubles
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with chat router mounted.

    Pattern: FakeRepository (Architecture Patterns p. 157)
    """
    from fastapi import FastAPI
    from src.api.routes.chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router)

    return TestClient(app)


@pytest.fixture
def mock_chat_service():
    """
    Mock ChatService for testing endpoint without LLM calls.

    Pattern: Test doubles (Architecture Patterns p. 157)
    """
    from src.models.responses import (
        ChatCompletionResponse,
        Choice,
        ChoiceMessage,
        Usage,
    )
    import time

    mock_response = ChatCompletionResponse(
        id="chatcmpl-test123",
        object="chat.completion",
        created=int(time.time()),
        model="gpt-4",
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Hello! How can I help?"),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    )

    with patch("src.api.routes.chat.ChatService.create_completion") as mock:
        mock.return_value = mock_response
        yield mock
