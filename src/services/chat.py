"""
Chat Service - WBS 2.6.1 Chat Service Implementation

This module implements the chat completion business logic, orchestrating
provider calls, tool execution, and session management.

Reference Documents:
- ARCHITECTURE.md: Lines 61-65 - services/chat.py "Chat completion business logic"
- GUIDELINES pp. 211: Service layers for orchestrating foundation models
- GUIDELINES pp. 1544: Agent tool orchestration patterns
- GUIDELINES pp. 1489: Command pattern for tool invocation
- GUIDELINES pp. 466: Fail-fast error handling with retry at orchestration level

WBS Items:
- 2.6.1.1.2: Create src/services/chat.py
- 2.6.1.1.3: Implement ChatService class
- 2.6.1.1.4: Inject ProviderRouter, ToolExecutor, SessionManager
- 2.6.1.1.5-14: complete() method implementation
- 2.6.1.2.1-7: Tool call loop handling

Pattern: Service Layer (orchestrates domain operations)
Pattern: Dependency Injection (router, executor, session_manager)
Pattern: Command Executor (tool calls as commands)
"""

import json
import logging
from typing import Optional

from src.models.domain import Message as DomainMessage, ToolCall, ToolResult
from src.models.requests import ChatCompletionRequest, Message
from src.models.responses import ChatCompletionResponse
from src.providers.base import LLMProvider
from src.providers.router import ProviderRouter, NoProviderError
from src.sessions.manager import SessionManager, SessionNotFoundError
from src.tools.executor import ToolExecutor

logger = logging.getLogger(__name__)

# Default maximum tool call iterations to prevent infinite loops
DEFAULT_MAX_TOOL_ITERATIONS = 10


class ChatServiceError(Exception):
    """Base exception for chat service errors."""


class ChatService:
    """
    Service layer for chat completion orchestration.

    WBS 2.6.1.1.3: Implement ChatService class.
    WBS 2.6.1.1.4: Inject ProviderRouter, ToolExecutor, SessionManager.

    Orchestrates the complete chat completion workflow including:
    - Provider routing based on model
    - Session history loading and saving
    - Tool call execution and continuation
    - Response handling

    Pattern: Service Layer (GUIDELINES pp. 211)
    Pattern: Dependency Injection (CODING_PATTERNS_ANALYSIS)
    Pattern: Tool Orchestration (GUIDELINES pp. 1544)

    Attributes:
        _router: Provider router for model-based routing.
        _executor: Tool executor for running tools.
        _session_manager: Session manager for conversation history.
        _max_tool_iterations: Maximum tool call loop iterations.

    Example:
        >>> service = ChatService(
        ...     router=provider_router,
        ...     executor=tool_executor,
        ...     session_manager=session_manager,
        ... )
        >>> response = await service.complete(request)
    """

    def __init__(
        self,
        router: ProviderRouter,
        executor: ToolExecutor,
        session_manager: Optional[SessionManager] = None,
        max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        """
        Initialize ChatService with dependencies.

        WBS 2.6.1.1.4: Inject ProviderRouter, ToolExecutor, SessionManager.

        Args:
            router: Provider router for model-based routing.
            executor: Tool executor for running tools.
            session_manager: Optional session manager for conversation history.
            max_tool_iterations: Maximum tool call iterations (default: 10).
        """
        self._router = router
        self._executor = executor
        self._session_manager = session_manager
        self._max_tool_iterations = max_tool_iterations

    async def complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process a chat completion request.

        WBS 2.6.1.1.5: Implement async complete(request) -> ChatCompletionResponse.
        WBS 2.6.1.1.6: Get provider from router based on model.
        WBS 2.6.1.1.7: Load session history if session_id provided.
        WBS 2.6.1.1.8: Append history to messages.
        WBS 2.6.1.1.9: Call provider.complete().
        WBS 2.6.1.1.10: Handle tool_calls in response.
        WBS 2.6.1.1.11: Execute tools via executor.
        WBS 2.6.1.1.12: Continue conversation if tools executed.
        WBS 2.6.1.1.13: Save messages to session if session_id provided.
        WBS 2.6.1.1.14: Return final response.

        Args:
            request: The chat completion request.

        Returns:
            The chat completion response.

        Raises:
            ChatServiceError: If provider not found or session not found.
        """
        # WBS 2.6.1.1.6: Get provider from router
        try:
            provider = self._router.get_provider(request.model)
        except NoProviderError as e:
            raise ChatServiceError(f"No provider available: {e}") from e

        # WBS 2.6.1.1.7-8: Load and prepend session history
        messages = await self._build_messages_with_history(request)

        # Create a working request with updated messages
        working_request = self._create_working_request(request, messages)

        # WBS 2.6.1.1.9: Initial provider call
        response = await provider.complete(working_request)

        # WBS 2.6.1.1.10-12: Handle tool calls loop
        iteration = 0
        while self._has_tool_calls(response) and iteration < self._max_tool_iterations:
            response, messages = await self._handle_tool_calls(
                provider, response, working_request, messages
            )
            working_request = self._create_working_request(request, messages)
            iteration += 1

        # WBS 2.6.1.1.13: Save messages to session
        await self._save_to_session(request, messages, response)

        # WBS 2.6.1.1.14: Return final response
        return response

    async def _build_messages_with_history(
        self, request: ChatCompletionRequest
    ) -> list[Message]:
        """
        Build message list with session history prepended.

        WBS 2.6.1.1.7: Load session history if session_id provided.
        WBS 2.6.1.1.8: Append history to messages.

        Args:
            request: The original request.

        Returns:
            List of messages with history prepended.

        Raises:
            ChatServiceError: If session not found.
        """
        messages: list[Message] = []

        if request.session_id and self._session_manager:
            try:
                history = await self._session_manager.get_history(request.session_id)
                # Convert domain messages to request messages
                for msg in history:
                    messages.append(
                        Message(
                            role=msg.role,  # type: ignore[arg-type]
                            content=msg.content,
                            tool_calls=msg.tool_calls,
                        )
                    )
            except SessionNotFoundError as e:
                raise ChatServiceError(f"Session not found: {e}") from e

        # Append original request messages
        messages.extend(request.messages)
        return messages

    def _create_working_request(
        self, original: ChatCompletionRequest, messages: list[Message]
    ) -> ChatCompletionRequest:
        """
        Create a working request with updated messages.

        Args:
            original: The original request.
            messages: The updated message list.

        Returns:
            New request with updated messages.
        """
        return ChatCompletionRequest(
            model=original.model,
            messages=messages,
            temperature=original.temperature,
            max_tokens=original.max_tokens,
            top_p=original.top_p,
            n=original.n,
            stream=original.stream,
            stop=original.stop,
            presence_penalty=original.presence_penalty,
            frequency_penalty=original.frequency_penalty,
            tools=original.tools,
            tool_choice=original.tool_choice,
            user=original.user,
            seed=original.seed,
            # Don't pass session_id to provider
        )

    def _has_tool_calls(self, response: ChatCompletionResponse) -> bool:
        """
        Check if response contains tool calls.

        WBS 2.6.1.1.10: Handle tool_calls in response.

        Args:
            response: The chat completion response.

        Returns:
            True if response has tool calls.
        """
        if not response.choices:
            return False
        choice = response.choices[0]
        return (
            choice.finish_reason == "tool_calls"
            and choice.message.tool_calls is not None
            and len(choice.message.tool_calls) > 0
        )

    def _extract_tool_calls(
        self, response: ChatCompletionResponse
    ) -> list[ToolCall]:
        """
        Extract ToolCall objects from response.

        WBS 2.6.1.2.2: Extract tool_calls from response.

        Args:
            response: The chat completion response.

        Returns:
            List of ToolCall objects.
        """
        tool_calls: list[ToolCall] = []

        if not response.choices:
            return tool_calls

        raw_calls = response.choices[0].message.tool_calls
        if not raw_calls:
            return tool_calls

        for raw_call in raw_calls:
            function_info = raw_call.get("function", {})
            arguments_str = function_info.get("arguments", "{}")

            # Parse arguments JSON
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(
                ToolCall(
                    id=raw_call.get("id", ""),
                    name=function_info.get("name", ""),
                    arguments=arguments,
                )
            )

        return tool_calls

    async def _handle_tool_calls(
        self,
        provider: LLMProvider,
        response: ChatCompletionResponse,
        request: ChatCompletionRequest,
        messages: list[Message],
    ) -> tuple[ChatCompletionResponse, list[Message]]:
        """
        Handle tool calls in response.

        WBS 2.6.1.2.1: Implement _handle_tool_calls().
        WBS 2.6.1.2.3: Execute all tools via executor.
        WBS 2.6.1.2.4: Build tool result messages.
        WBS 2.6.1.2.5: Append to conversation.
        WBS 2.6.1.2.6: Call provider again with tool results.

        Args:
            provider: The LLM provider.
            response: The response with tool calls.
            request: The current request.
            messages: The current message list.

        Returns:
            Tuple of (new response, updated messages).
        """
        # WBS 2.6.1.2.2: Extract tool calls
        tool_calls = self._extract_tool_calls(response)

        # Add assistant message with tool calls to history
        assistant_message = Message(
            role="assistant",
            content=response.choices[0].message.content,
            tool_calls=response.choices[0].message.tool_calls,
        )
        messages = list(messages) + [assistant_message]

        # WBS 2.6.1.2.3: Execute tools
        results = await self._executor.execute_batch(tool_calls)

        # WBS 2.6.1.2.4-5: Build and append tool result messages
        for result in results:
            tool_message = Message(
                role="tool",
                content=result.content,
                tool_call_id=result.tool_call_id,
            )
            messages.append(tool_message)

        # WBS 2.6.1.2.6: Call provider again
        working_request = self._create_working_request(request, messages)
        new_response = await provider.complete(working_request)

        return new_response, messages

    async def _save_to_session(
        self,
        request: ChatCompletionRequest,
        messages: list[Message],
        response: ChatCompletionResponse,
    ) -> None:
        """
        Save messages to session if session_id provided.

        WBS 2.6.1.1.13: Save messages to session if session_id provided.

        Args:
            request: The original request.
            messages: The conversation messages.
            response: The final response.
        """
        if not request.session_id or not self._session_manager:
            return

        # Save user messages (skip history that was already in session)
        for msg in request.messages:
            domain_msg = DomainMessage(
                role=msg.role,
                content=msg.content,
                tool_calls=msg.tool_calls,
            )
            await self._session_manager.add_message(request.session_id, domain_msg)

        # Save assistant response
        if response.choices:
            assistant_content = response.choices[0].message.content
            assistant_msg = DomainMessage(
                role="assistant",
                content=assistant_content,
                tool_calls=response.choices[0].message.tool_calls,
            )
            await self._session_manager.add_message(request.session_id, assistant_msg)
