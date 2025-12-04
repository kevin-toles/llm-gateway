"""
Tests for ChatService - WBS 2.6.1 Chat Service Implementation

TDD RED Phase: These tests should fail until ChatService is implemented.

Reference Documents:
- ARCHITECTURE.md: Lines 61-65 - services/chat.py "Chat completion business logic"
- GUIDELINES pp. 211: Service layers for orchestrating foundation models
- GUIDELINES pp. 1544: Agent tool orchestration patterns
- GUIDELINES pp. 1489: Command pattern for tool invocation
- CODING_PATTERNS_ANALYSIS: Async-first, dependency injection

WBS Items Covered:
- 2.6.1.1.2: Create src/services/chat.py
- 2.6.1.1.3: Implement ChatService class
- 2.6.1.1.4: Inject ProviderRouter, ToolExecutor, SessionManager
- 2.6.1.1.5: Implement async complete()
- 2.6.1.1.6-14: Provider routing, session history, tool execution
- 2.6.1.1.15: RED test: complete without tools returns response
- 2.6.1.1.16: RED test: complete with tools executes and continues
- 2.6.1.1.17: RED test: session history included in request
- 2.6.1.2.1-10: Tool call loop tests
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

# Test imports
from src.models.requests import ChatCompletionRequest, Message
from src.models.responses import (
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    Usage,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock()
    provider.complete = AsyncMock()
    provider.stream = AsyncMock()
    provider.supports_model = MagicMock(return_value=True)
    provider.get_supported_models = MagicMock(return_value=["test-model"])
    return provider


@pytest.fixture
def mock_router(mock_provider):
    """Create a mock provider router."""
    from src.providers.router import ProviderRouter

    router = MagicMock(spec=ProviderRouter)
    router.get_provider = MagicMock(return_value=mock_provider)
    return router


@pytest.fixture
def mock_executor():
    """Create a mock tool executor."""
    from src.tools.executor import ToolExecutor

    executor = MagicMock(spec=ToolExecutor)
    executor.execute = AsyncMock()
    executor.execute_batch = AsyncMock()
    return executor


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    from src.sessions.manager import SessionManager

    manager = MagicMock(spec=SessionManager)
    manager.get = AsyncMock()
    manager.add_message = AsyncMock()
    manager.get_history = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def chat_service(mock_router, mock_executor, mock_session_manager):
    """Create ChatService with mocked dependencies."""
    from src.services.chat import ChatService

    return ChatService(
        router=mock_router,
        executor=mock_executor,
        session_manager=mock_session_manager,
    )


@pytest.fixture
def sample_request():
    """Create a sample chat completion request."""
    return ChatCompletionRequest(
        model="test-model",
        messages=[Message(role="user", content="Hello, world!")],
    )


@pytest.fixture
def sample_response():
    """Create a sample chat completion response."""
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(datetime.now(timezone.utc).timestamp()),
        model="test-model",
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content="Hello! How can I help?"),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture
def tool_call_response():
    """Create a response with tool calls."""
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(datetime.now(timezone.utc).timestamp()),
        model="test-model",
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "San Francisco"}',
                            },
                        }
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )


# =============================================================================
# WBS 2.6.1.1.2-3: ChatService Class Tests
# =============================================================================


class TestChatServiceClass:
    """Tests for ChatService class structure."""

    def test_chat_service_can_be_instantiated(
        self, mock_router, mock_executor, mock_session_manager
    ) -> None:
        """
        WBS 2.6.1.1.3: ChatService class exists and can be instantiated.
        """
        from src.services.chat import ChatService

        service = ChatService(
            router=mock_router,
            executor=mock_executor,
            session_manager=mock_session_manager,
        )

        assert isinstance(service, ChatService)

    def test_chat_service_requires_router(
        self, mock_executor, mock_session_manager
    ) -> None:
        """
        WBS 2.6.1.1.4: ChatService requires ProviderRouter dependency.
        """
        from src.services.chat import ChatService

        with pytest.raises(TypeError):
            ChatService(executor=mock_executor, session_manager=mock_session_manager)

    def test_chat_service_requires_executor(
        self, mock_router, mock_session_manager
    ) -> None:
        """
        WBS 2.6.1.1.4: ChatService requires ToolExecutor dependency.
        """
        from src.services.chat import ChatService

        with pytest.raises(TypeError):
            ChatService(router=mock_router, session_manager=mock_session_manager)

    def test_chat_service_session_manager_optional(
        self, mock_router, mock_executor
    ) -> None:
        """
        SessionManager is optional (sessions not always needed).
        """
        from src.services.chat import ChatService

        service = ChatService(
            router=mock_router,
            executor=mock_executor,
            session_manager=None,
        )

        assert service._session_manager is None


# =============================================================================
# WBS 2.6.1.1.5-9: Basic Complete Tests
# =============================================================================


class TestChatServiceComplete:
    """Tests for ChatService.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_returns_response(
        self, chat_service, mock_provider, sample_request, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.5: complete() returns ChatCompletionResponse.
        WBS 2.6.1.1.15: RED test: complete without tools returns response.
        """
        mock_provider.complete.return_value = sample_response

        result = await chat_service.complete(sample_request)

        assert isinstance(result, ChatCompletionResponse)
        assert result.id == sample_response.id
        assert len(result.choices) == 1
        assert result.choices[0].message.content == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_complete_routes_to_provider(
        self, chat_service, mock_router, mock_provider, sample_request, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.6: complete() gets provider from router based on model.
        """
        mock_provider.complete.return_value = sample_response

        await chat_service.complete(sample_request)

        mock_router.get_provider.assert_called_once_with("test-model")
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_calls_provider_with_request(
        self, chat_service, mock_provider, sample_request, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.9: complete() calls provider.complete() with request.
        """
        mock_provider.complete.return_value = sample_response

        await chat_service.complete(sample_request)

        # Verify provider was called with request containing messages
        call_args = mock_provider.complete.call_args
        passed_request = call_args[0][0]
        assert len(passed_request.messages) >= 1


# =============================================================================
# WBS 2.6.1.1.7-8, 2.6.1.1.13, 2.6.1.1.17: Session History Tests
# =============================================================================


class TestChatServiceSession:
    """Tests for session history integration."""

    @pytest.mark.asyncio
    async def test_complete_loads_session_history(
        self, chat_service, mock_session_manager, mock_provider, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.7: complete() loads session history if session_id provided.
        WBS 2.6.1.1.17: RED test: session history included in request.
        """
        from src.models.domain import Message as DomainMessage

        # Setup session with history
        history = [
            DomainMessage(role="user", content="Previous question"),
            DomainMessage(role="assistant", content="Previous answer"),
        ]
        mock_session_manager.get_history.return_value = history
        mock_provider.complete.return_value = sample_response

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="New question")],
            session_id="session_123",
        )

        await chat_service.complete(request)

        mock_session_manager.get_history.assert_called_once_with("session_123")

    @pytest.mark.asyncio
    async def test_complete_prepends_history_to_messages(
        self, chat_service, mock_session_manager, mock_provider, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.8: complete() appends history to messages.
        """
        from src.models.domain import Message as DomainMessage

        history = [
            DomainMessage(role="user", content="Previous question"),
            DomainMessage(role="assistant", content="Previous answer"),
        ]
        mock_session_manager.get_history.return_value = history
        mock_provider.complete.return_value = sample_response

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="New question")],
            session_id="session_123",
        )

        await chat_service.complete(request)

        # Verify provider received request with history prepended
        call_args = mock_provider.complete.call_args
        passed_request = call_args[0][0]
        # History (2 messages) + new message (1) = 3 total
        assert len(passed_request.messages) == 3
        assert passed_request.messages[0].content == "Previous question"
        assert passed_request.messages[1].content == "Previous answer"
        assert passed_request.messages[2].content == "New question"

    @pytest.mark.asyncio
    async def test_complete_saves_messages_to_session(
        self, chat_service, mock_session_manager, mock_provider, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.13: complete() saves messages to session if session_id provided.
        """
        mock_session_manager.get_history.return_value = []
        mock_provider.complete.return_value = sample_response

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            session_id="session_123",
        )

        await chat_service.complete(request)

        # Should save user message and assistant response
        assert mock_session_manager.add_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_complete_without_session_skips_history(
        self, chat_service, mock_session_manager, mock_provider, sample_response
    ) -> None:
        """
        No session_id means no session operations.
        """
        mock_provider.complete.return_value = sample_response

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            # No session_id
        )

        await chat_service.complete(request)

        mock_session_manager.get_history.assert_not_called()
        mock_session_manager.add_message.assert_not_called()


# =============================================================================
# WBS 2.6.1.1.10-12, 2.6.1.1.16: Tool Execution Tests
# =============================================================================


class TestChatServiceToolExecution:
    """Tests for tool call handling."""

    @pytest.mark.asyncio
    async def test_complete_handles_tool_calls(
        self, chat_service, mock_provider, mock_executor, tool_call_response, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.10: complete() handles tool_calls in response.
        WBS 2.6.1.1.16: RED test: complete with tools executes and continues.
        """
        from src.models.domain import ToolResult

        # First call returns tool_calls, second returns final response
        mock_provider.complete.side_effect = [tool_call_response, sample_response]
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="Sunny, 72°F", is_error=False)
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="What's the weather?")],
        )

        await chat_service.complete(request)

        # Verify tool execution was called
        mock_executor.execute_batch.assert_called_once()
        # Verify provider was called twice (initial + after tool results)
        assert mock_provider.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_complete_executes_tools_via_executor(
        self, chat_service, mock_provider, mock_executor, tool_call_response, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.11: complete() executes tools via executor.
        """
        from src.models.domain import ToolCall, ToolResult

        mock_provider.complete.side_effect = [tool_call_response, sample_response]
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="Sunny", is_error=False)
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="What's the weather?")],
        )

        await chat_service.complete(request)

        # Verify execute_batch was called with ToolCall objects
        call_args = mock_executor.execute_batch.call_args
        tool_calls = call_args[0][0]
        assert len(tool_calls) == 1
        assert isinstance(tool_calls[0], ToolCall)
        assert tool_calls[0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_complete_continues_after_tool_execution(
        self, chat_service, mock_provider, mock_executor, tool_call_response, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.12: complete() continues conversation if tools executed.
        """
        from src.models.domain import ToolResult

        mock_provider.complete.side_effect = [tool_call_response, sample_response]
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="Sunny, 72°F", is_error=False)
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="What's the weather?")],
        )

        await chat_service.complete(request)

        # Second call should include tool results
        second_call = mock_provider.complete.call_args_list[1]
        second_request = second_call[0][0]
        
        # Should have: original messages + assistant tool_call + tool result
        assert len(second_request.messages) >= 3

    @pytest.mark.asyncio
    async def test_complete_returns_final_response(
        self, chat_service, mock_provider, mock_executor, tool_call_response, sample_response
    ) -> None:
        """
        WBS 2.6.1.1.14: complete() returns final response.
        """
        from src.models.domain import ToolResult

        mock_provider.complete.side_effect = [tool_call_response, sample_response]
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="Sunny", is_error=False)
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="What's the weather?")],
        )

        result = await chat_service.complete(request)

        # Final response should be the one without tool_calls
        assert result.choices[0].finish_reason == "stop"
        assert result.choices[0].message.content == "Hello! How can I help?"


# =============================================================================
# WBS 2.6.1.2: Tool Call Loop Tests
# =============================================================================


class TestChatServiceToolLoop:
    """Tests for tool call loop handling."""

    @pytest.mark.asyncio
    async def test_tool_loop_handles_multiple_iterations(
        self, chat_service, mock_provider, mock_executor
    ) -> None:
        """
        WBS 2.6.1.2.8: RED test: tool loop handles multiple iterations.
        """
        from src.models.domain import ToolResult

        # Create multiple tool call responses
        tool_response_1 = ChatCompletionResponse(
            id="resp1",
            created=int(datetime.now(timezone.utc).timestamp()),
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "step1", "arguments": "{}"},
                            }
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )

        tool_response_2 = ChatCompletionResponse(
            id="resp2",
            created=int(datetime.now(timezone.utc).timestamp()),
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            {
                                "id": "call_2",
                                "type": "function",
                                "function": {"name": "step2", "arguments": "{}"},
                            }
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        )

        final_response = ChatCompletionResponse(
            id="resp3",
            created=int(datetime.now(timezone.utc).timestamp()),
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content="Done!"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        )

        mock_provider.complete.side_effect = [tool_response_1, tool_response_2, final_response]
        mock_executor.execute_batch.side_effect = [
            [ToolResult(tool_call_id="call_1", content="result1", is_error=False)],
            [ToolResult(tool_call_id="call_2", content="result2", is_error=False)],
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Multi-step task")],
        )

        result = await chat_service.complete(request)

        # Should have called provider 3 times
        assert mock_provider.complete.call_count == 3
        # Should have executed tools twice
        assert mock_executor.execute_batch.call_count == 2
        # Final result should be "Done!"
        assert result.choices[0].message.content == "Done!"

    @pytest.mark.asyncio
    async def test_tool_loop_respects_max_iterations(
        self, chat_service, mock_provider, mock_executor
    ) -> None:
        """
        WBS 2.6.1.2.9: RED test: tool loop respects max iterations.
        """
        from src.models.domain import ToolResult

        # Create an infinite loop of tool calls
        tool_response = ChatCompletionResponse(
            id="resp1",
            created=int(datetime.now(timezone.utc).timestamp()),
            model="test-model",
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            {
                                "id": "call_infinite",
                                "type": "function",
                                "function": {"name": "infinite", "arguments": "{}"},
                            }
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )

        # Always return tool calls (would loop forever without limit)
        mock_provider.complete.return_value = tool_response
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_infinite", content="continue", is_error=False)
        ]

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Infinite task")],
        )

        # Should not hang - max iterations should be enforced
        await chat_service.complete(request)

        # Should have stopped after max iterations (default: 10)
        assert mock_provider.complete.call_count <= 11  # 1 initial + up to 10 iterations


# =============================================================================
# WBS 2.6.1.1.19: Refactor Tests
# =============================================================================


class TestChatServiceToolCallHandler:
    """Tests for extracted _handle_tool_calls method."""

    @pytest.mark.asyncio
    async def test_handle_tool_calls_extracts_calls(
        self, chat_service, mock_executor, tool_call_response
    ) -> None:
        """
        WBS 2.6.1.2.2: _handle_tool_calls extracts tool_calls from response.
        """
        from src.models.domain import ToolCall, ToolResult
        from src.services.chat import ChatService

        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="result", is_error=False)
        ]

        # Access the private method for testing
        tool_calls = chat_service._extract_tool_calls(tool_call_response)

        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_weather"
        assert tool_calls[0].id == "call_abc123"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestChatServiceErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_complete_raises_on_no_provider(
        self, mock_router, mock_executor, mock_session_manager, sample_request
    ) -> None:
        """
        complete() raises error when no provider is available.
        """
        from src.services.chat import ChatService, ChatServiceError
        from src.providers.router import NoProviderError

        mock_router.get_provider.side_effect = NoProviderError("No provider")

        service = ChatService(
            router=mock_router,
            executor=mock_executor,
            session_manager=mock_session_manager,
        )

        with pytest.raises(ChatServiceError):
            await service.complete(sample_request)

    @pytest.mark.asyncio
    async def test_complete_raises_on_session_not_found(
        self, chat_service, mock_session_manager, mock_provider
    ) -> None:
        """
        complete() raises error when session not found.
        """
        from src.services.chat import ChatServiceError
        from src.sessions.manager import SessionNotFoundError

        mock_session_manager.get_history.side_effect = SessionNotFoundError("Not found")

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            session_id="invalid_session",
        )

        with pytest.raises(ChatServiceError):
            await chat_service.complete(request)


# =============================================================================
# Import Tests
# =============================================================================


class TestChatServiceSessionToolCalls:
    """Tests for session history with tool calls.
    
    Issue 28 Fix: Ensure tool call and tool result messages are saved to session.
    """

    @pytest.mark.asyncio
    async def test_save_to_session_includes_tool_call_messages(
        self, mock_router, mock_executor, mock_session_manager, mock_provider, tool_call_response, sample_response
    ) -> None:
        """
        Issue 28 Fix: _save_to_session should save tool call and tool result messages.
        
        When tool calls are executed, the accumulated messages (including assistant
        tool_calls and tool results) should be saved to session, not just the
        original request messages.
        
        RED: This test should fail because current implementation only saves
        request.messages, not the accumulated messages with tool calls.
        """
        from src.services.chat import ChatService
        from src.models.domain import ToolResult

        # Setup: First call returns tool_calls, second returns final response
        mock_provider.complete.side_effect = [tool_call_response, sample_response]
        mock_executor.execute_batch.return_value = [
            ToolResult(tool_call_id="call_abc123", content="Sunny, 72°F", is_error=False)
        ]

        service = ChatService(
            router=mock_router,
            executor=mock_executor,
            session_manager=mock_session_manager,
        )

        request = ChatCompletionRequest(
            model="test-model",
            messages=[Message(role="user", content="What's the weather?")],
            session_id="test_session_123",  # Enable session persistence
        )

        await service.complete(request)

        # Verify add_message was called
        assert mock_session_manager.add_message.call_count >= 3, (
            "Expected at least 3 add_message calls: "
            "user message, assistant tool_call, tool result, final assistant"
        )
        
        # Extract all saved messages
        saved_messages = [
            call.args[1] for call in mock_session_manager.add_message.call_args_list
        ]
        saved_roles = [msg.role for msg in saved_messages]
        
        # Should have: user -> assistant (with tool_calls) -> tool -> assistant (final)
        assert "tool" in saved_roles, (
            f"Tool result message not saved to session. Saved roles: {saved_roles}"
        )
        
        # Verify assistant message with tool_calls was saved
        assistant_messages = [msg for msg in saved_messages if msg.role == "assistant"]
        tool_call_message = next(
            (msg for msg in assistant_messages if msg.tool_calls), None
        )
        assert tool_call_message is not None, (
            "Assistant message with tool_calls not saved to session"
        )


class TestChatServiceImportable:
    """Tests for module importability."""

    def test_chat_service_importable_from_services(self) -> None:
        """ChatService is importable from src.services."""
        from src.services import ChatService

        assert callable(ChatService)

    def test_chat_service_importable_from_chat(self) -> None:
        """ChatService is importable from src.services.chat."""
        from src.services.chat import ChatService

        assert callable(ChatService)

    def test_chat_service_error_importable(self) -> None:
        """ChatServiceError is importable from src.services.chat."""
        from src.services.chat import ChatServiceError

        assert issubclass(ChatServiceError, Exception)
