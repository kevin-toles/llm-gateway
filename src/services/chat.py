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

from src.models.domain import Message as DomainMessage, ToolCall
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
        # Resolve model aliases (e.g., "openai" -> "gpt-5.2")
        resolved_model = self._router.resolve_model_alias(request.model)
        if resolved_model != request.model:
            # Create new request with resolved model
            request = ChatCompletionRequest(
                model=resolved_model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                n=request.n,
                stream=request.stream,
                stop=request.stop,
                presence_penalty=request.presence_penalty,
                frequency_penalty=request.frequency_penalty,
                tools=request.tools,
                tool_choice=request.tool_choice,
                user=request.user,
                seed=request.seed,
                session_id=request.session_id,
            )
        
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

        Issue 28 Fix: Save ALL accumulated messages including tool calls and tool
        results, not just the original request messages.

        Args:
            request: The original request.
            messages: The accumulated conversation messages (includes tool calls).
            response: The final response.
        """
        if not request.session_id or not self._session_manager:
            return

        # Issue 28 Fix: Calculate where new messages start in the accumulated list.
        # The messages list structure is: [history...] + [request.messages] + [tool calls/results]
        # History count = total messages - (request messages + any new tool messages)
        # Simpler: Find where request.messages starts by computing:
        # history_count = len(messages) - len(request.messages) - new_tool_messages
        # 
        # Actually, we need to save everything that wasn't already in history.
        # The request.messages are always at the start of "new" content after history.
        # So we find where request messages start in accumulated list.
        
        # Calculate: history_count = messages index where request.messages[0] appears
        # This is: len(messages) - len(request.messages) - tool_messages_count
        # But tool_messages_count is unknown at this point.
        # 
        # Simplest approach: history = len(messages) - count of new messages
        # New messages = request.messages + all messages after that (tool calls, etc.)
        # So find the index of first request message, that's the history_count
        
        # Even simpler: Calculate the offset as the difference
        # messages = [history] + [new_user_msgs from request] + [tool_stuff]
        # We know: request.messages are the new user messages
        # So history_count = total - (request.messages + tool_messages)
        # Without calling get_history again, we can compute:
        # new_message_count = len(messages) - history_count
        # But we need history_count to compute that...
        #
        # Best approach: Save only messages AFTER the first request message.
        # Find where request.messages[0] starts in the messages list.
        
        # NOTE: These counts document the message structure for debugging.
        # Prefixed with underscore per Anti-Pattern 4.3 (intentionally unused).
        _original_msg_count = len(request.messages)  # noqa: F841
        _total_msg_count = len(messages)  # noqa: F841
        
        # New messages start after history. We know the structure is:
        # [history...] + [request.messages...] + [tool_calls/results...]
        # The first request message is at index = history_count
        # So: new_messages = messages[history_count:]
        # And: history_count = total - (original_msg_count + tool_messages)
        # 
        # We can find history_count by matching the start of request.messages
        # Alternatively, since tool messages are added AFTER request.messages,
        # anything in messages beyond original history should be saved.
        # 
        # Simplest correct approach: Find first occurrence of request.messages[0]
        history_count = 0
        if request.messages and messages:
            first_new_msg = request.messages[0]
            for i, msg in enumerate(messages):
                if (msg.role == first_new_msg.role and 
                    msg.content == first_new_msg.content):
                    history_count = i
                    break

        # Save accumulated messages (skip already-saved history)
        for msg in messages[history_count:]:
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
