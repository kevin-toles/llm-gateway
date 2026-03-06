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
import re
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

# Thinking tag detection for truncated reasoning (Qwen3, DeepSeek-R1)
_THINKING_TAG_PATTERN = re.compile(
    r"<(?:think|thinking|reasoning|r|internal_thought)>",
    re.IGNORECASE,
)
_THINKING_CLOSE_PATTERN = re.compile(
    r"</(?:think|thinking|reasoning|r|internal_thought)>",
    re.IGNORECASE,
)

# Context management configuration
DEFAULT_CHARS_PER_TOKEN = 4  # Conservative estimate for token counting
CONTEXT_SAFETY_MARGIN = 0.85  # Use 85% of context limit to leave headroom
DEFAULT_CONTEXT_LIMITS = {
    # Registered external models only (gateway manages cloud, CMS manages local)
    # OpenAI
    "gpt-5.2": 128000,
    "gpt-5.2-pro": 128000,
    "gpt-5-mini": 128000,
    "gpt-5-nano": 128000,
    # Anthropic
    "claude-opus-4.5": 200000,
    "claude-sonnet-4.5": 200000,
    "claude-opus-4-5-20250514": 200000,
    "claude-sonnet-4-5-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    "claude-sonnet-4-20250514": 200000,
    # Google
    "gemini-2.0-flash": 1048576,
    "gemini-1.5-pro": 2097152,
    "gemini-1.5-flash": 1048576,
    "gemini-pro": 32768,
    # DeepSeek
    "deepseek-reasoner": 64000,
}


class ChatServiceError(Exception):
    """Base exception for chat service errors."""


class InfrastructureStatus:
    """Track status of infrastructure services (CMS, RLM, Temporal)."""
    
    def __init__(self):
        self.cms_available: bool = True
        self.rlm_available: bool = True
        self.temporal_available: bool = True
        self.last_check: float = 0
        self._failure_count: int = 0
    
    def mark_failure(self, service: str) -> None:
        """Mark a service as failed and log alert."""
        self._failure_count += 1
        if service == "cms":
            self.cms_available = False
        elif service == "rlm":
            self.rlm_available = False
        elif service == "temporal":
            self.temporal_available = False
        
        logger.warning(
            "Infrastructure service %s unavailable (failure #%d). "
            "Continuing with fallback mode.",
            service,
            self._failure_count,
        )
    
    def mark_healthy(self, service: str) -> None:
        """Mark service as recovered."""
        if service == "cms":
            self.cms_available = True
        elif service == "rlm":
            self.rlm_available = True
        elif service == "temporal":
            self.temporal_available = True


# Global infrastructure status (shared across requests)
_infra_status = InfrastructureStatus()


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

        # Proactive context management: check if we're approaching limits
        # When CMS proxy is enabled, CMS intercepts and handles context window
        # management — skip gateway-side compression to avoid double-processing.
        context_limit = self._get_context_limit(request.model)
        estimated_tokens = self._estimate_token_count(messages)
        
        from src.core.config import get_settings
        _settings = get_settings()
        cms_proxy_active = getattr(_settings, 'cms_enabled', False) and getattr(_settings, 'cms_url', None)
        
        if not cms_proxy_active and estimated_tokens > context_limit * CONTEXT_SAFETY_MARGIN:
            logger.info(
                "Proactive context management (CMS proxy disabled): %d tokens approaching limit %d for %s",
                estimated_tokens,
                context_limit,
                request.model,
            )
            messages = await self._compress_context(
                messages, 
                context_limit,
                request.model,
            )
        elif cms_proxy_active and estimated_tokens > context_limit * CONTEXT_SAFETY_MARGIN:
            logger.info(
                "CMS proxy active — delegating context management for %d tokens (limit %d) to CMS",
                estimated_tokens,
                context_limit,
            )

        # Create a working request with updated messages
        working_request = self._create_working_request(request, messages)

        # WBS 2.6.1.1.9: Initial provider call
        response = await provider.complete(working_request)

        # Handle truncated thinking (Qwen3, DeepSeek-R1 thinking mode)
        # If model exhausted tokens on thinking without answer, retry with /no_think
        if self._has_truncated_thinking(response):
            logger.info(
                "Detected truncated thinking response, retrying with /no_think"
            )
            thinking_content = self._extract_thinking_content(response)
            response = await self._retry_with_thinking_context(
                provider, request, messages, thinking_content
            )

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

    def _has_truncated_thinking(self, response: ChatCompletionResponse) -> bool:
        """
        Check if response is truncated thinking (Qwen3, DeepSeek-R1).
        
        Detects when model started thinking but hit token limit before
        producing an answer. Pattern: finish_reason="length" + unclosed <think> tag.
        
        Args:
            response: The chat completion response.
            
        Returns:
            True if response contains truncated thinking block.
        """
        if not response.choices:
            return False
        
        choice = response.choices[0]
        content = choice.message.content or ""
        
        # Must be length-truncated
        if choice.finish_reason != "length":
            return False
        
        # Check for opened but not closed thinking tag
        has_open = bool(_THINKING_TAG_PATTERN.search(content))
        has_close = bool(_THINKING_CLOSE_PATTERN.search(content))
        
        return has_open and not has_close
    
    def _extract_thinking_content(self, response: ChatCompletionResponse) -> str:
        """
        Extract the thinking content from a truncated response.
        
        Strips the opening tag and returns raw thinking for context.
        
        Args:
            response: Response with truncated thinking.
            
        Returns:
            The thinking content without tags.
        """
        if not response.choices:
            return ""
        
        content = response.choices[0].message.content or ""
        
        # Remove opening thinking tag
        cleaned = _THINKING_TAG_PATTERN.sub("", content).strip()
        return cleaned
    
    async def _retry_with_thinking_context(
        self,
        provider: LLMProvider,
        original_request: ChatCompletionRequest,
        messages: list[Message],
        thinking_content: str,
    ) -> ChatCompletionResponse:
        """
        Retry request with thinking as context and /no_think suffix.
        
        Uses the model's own reasoning as context to get a grounded answer.
        Pattern: Think → Cache → Answer (RLM/CMS integration point).
        
        Args:
            provider: The LLM provider to use.
            original_request: Original request.
            messages: Current message list.
            thinking_content: Extracted thinking from first attempt.
            
        Returns:
            Response with direct answer.
        """
        # Build new messages with thinking as assistant context
        retry_messages = list(messages)
        
        # Add the thinking as an assistant message (provides context)
        retry_messages.append(
            Message(
                role="assistant",
                content=f"[Internal reasoning: {thinking_content[:500]}...]",
            )
        )
        
        # Get the last user message and append /no_think
        last_user_idx = None
        for i in range(len(retry_messages) - 1, -1, -1):
            if retry_messages[i].role == "user":
                last_user_idx = i
                break
        
        if last_user_idx is not None:
            original_content = retry_messages[last_user_idx].content or ""
            if "/no_think" not in original_content:
                retry_messages[last_user_idx] = Message(
                    role="user",
                    content=f"{original_content} /no_think",
                )
        
        # Create retry request
        retry_request = self._create_working_request(original_request, retry_messages)
        
        logger.debug("Retrying with thinking context, %d chars", len(thinking_content))
        
        return await provider.complete(retry_request)

    # =========================================================================
    # Context Management - Proactive token/context handling
    # =========================================================================
    
    def _get_context_limit(self, model: str) -> int:
        """
        Get context limit for a model.
        
        Uses known limits or falls back to conservative default.
        Future: Query CMS for dynamic limits based on model config.
        
        Args:
            model: Model identifier.
            
        Returns:
            Context limit in tokens.
        """
        # Check known limits
        for model_key, limit in DEFAULT_CONTEXT_LIMITS.items():
            if model_key in model.lower():
                return limit
        
        # Conservative fallback for unknown models
        return 4096
    
    def _estimate_token_count(self, messages: list[Message]) -> int:
        """
        Estimate token count from messages.
        
        Uses character-based estimation. Future: Use tiktoken or model tokenizer.
        
        Args:
            messages: List of messages.
            
        Returns:
            Estimated token count.
        """
        total_chars = 0
        for msg in messages:
            if msg.content:
                total_chars += len(msg.content)
            # Account for role and formatting overhead
            total_chars += 10
        
        return total_chars // DEFAULT_CHARS_PER_TOKEN
    
    async def _compress_context(
        self,
        messages: list[Message],
        context_limit: int,
        model: str,
    ) -> list[Message]:
        """
        Compress context to fit within limits.
        
        Strategies (in order):
        1. Try CMS for intelligent summarization (if available)
        2. Truncate middle messages (keep system + recent)
        3. Hard truncate old messages
        
        Args:
            messages: Original messages.
            context_limit: Maximum tokens allowed.
            model: Model identifier.
            
        Returns:
            Compressed message list.
        """
        target_tokens = int(context_limit * CONTEXT_SAFETY_MARGIN)
        
        # Try CMS summarization if available
        if _infra_status.cms_available:
            try:
                compressed = await self._cms_compress_context(messages, target_tokens, model)
                if compressed:
                    logger.info("Context compressed via CMS: %d -> %d messages",
                               len(messages), len(compressed))
                    return compressed
            except Exception as e:
                _infra_status.mark_failure("cms")
                logger.warning("CMS compression failed, using fallback: %s", e)
        
        # Fallback: Keep system message + truncate middle + keep recent
        return self._fallback_compress(messages, target_tokens)
    
    async def _cms_compress_context(
        self,
        messages: list[Message],
        _target_tokens: int,
        model: str = "qwen2.5-7b",
    ) -> list[Message] | None:
        """
        Use CMS to intelligently compress context.
        
        CMS can optimize and chunk text to fit within token limits.
        Sends concatenated message content to CMS /v1/context/process,
        which applies token optimization strategies (prose→bullets,
        constraint handles, abbreviations) and optional chunking.
        
        Args:
            messages: Messages to compress.
            target_tokens: Target token count.
            model: Model identifier for CMS context limits.
            
        Returns:
            Compressed messages or None if CMS unavailable.
        """
        # Import CMS client (lazy to avoid circular imports)
        try:
            from src.clients.cms_client import get_cms_client, CMSError
            
            cms = get_cms_client()
            if cms is None:
                return None
            
            # Separate system message from content messages
            system_msg: Message | None = None
            content_messages = messages
            if messages and messages[0].role == "system":
                system_msg = messages[0]
                content_messages = messages[1:]
            
            if not content_messages:
                return None
            
            # Concatenate user/assistant content for CMS processing
            combined_text = "\n\n".join(
                f"[{msg.role}]: {msg.content}" 
                for msg in content_messages 
                if msg.content
            )
            
            if not combined_text:
                return None
            
            result = await cms.process(
                text=combined_text,
                model=model,
            )
            
            # Build compressed message list
            compressed: list[Message] = []
            if system_msg:
                compressed.append(system_msg)
            
            if result.chunks:
                # CMS chunked the content — use only the last chunk
                # (most recent context, fits in window)
                last_chunk = result.chunks[-1]
                compressed.append(Message(
                    role="user",
                    content=last_chunk.content,
                ))
            elif result.optimized_text:
                compressed.append(Message(
                    role="user",
                    content=result.optimized_text,
                ))
            else:
                return None
            
            logger.info(
                "CMS compression: %d -> %d tokens (ratio: %.2f, strategies: %s)",
                result.original_tokens,
                result.final_tokens,
                result.compression_ratio,
                result.strategies_applied,
            )
            
            return compressed
            
        except ImportError:
            logger.debug("CMS client not available")
            return None
        except CMSError as e:
            logger.warning("CMS compression call failed: %s", e)
            return None
    
    def _extract_system_message(
        self, messages: list[Message],
    ) -> tuple[list[Message], list[Message], int]:
        """Separate system message from the rest and count its tokens.

        Returns:
            (result_prefix, remaining_messages, tokens_used)
        """
        if messages and messages[0].role == "system":
            return [messages[0]], messages[1:], self._estimate_token_count([messages[0]])
        return [], messages, 0

    def _apply_floor_guard(
        self,
        result: list[Message],
        messages: list[Message],
        target_tokens: int,
        tokens_used: int,
    ) -> None:
        """Ensure result is non-empty by hard-truncating the last message if needed.

        LangChain trim_messages pattern: never return an empty context.
        Mutates *result* in place.
        """
        has_only_system = len(result) == 1 and result[0].role == "system"
        if result and not has_only_system:
            return
        if not messages:
            return

        last_msg = messages[-1]
        available_tokens = max(target_tokens - tokens_used, 100)
        max_chars = available_tokens * DEFAULT_CHARS_PER_TOKEN
        truncated_content = (last_msg.content or "")[:max_chars]
        if not truncated_content:
            return

        result.append(Message(
            role=last_msg.role,
            content=truncated_content,
        ))
        logger.warning(
            "Floor guard: hard-truncated message from %d to %d chars to prevent empty context",
            len(last_msg.content or ""),
            len(truncated_content),
        )

    def _fallback_compress(
        self,
        messages: list[Message],
        target_tokens: int,
    ) -> list[Message]:
        """
        Fallback context compression without CMS.
        
        Strategy: Keep system message + last N messages that fit.
        
        Args:
            messages: Original messages.
            target_tokens: Target token count.
            
        Returns:
            Truncated message list.
        """
        if not messages:
            return messages
        
        result, remaining, tokens_used = self._extract_system_message(messages)
        
        # Add messages from end until we hit limit
        messages_to_add: list[Message] = []
        for msg in reversed(remaining):
            msg_tokens = self._estimate_token_count([msg])
            if tokens_used + msg_tokens <= target_tokens:
                messages_to_add.insert(0, msg)
                tokens_used += msg_tokens
            else:
                break
        
        result.extend(messages_to_add)
        
        self._apply_floor_guard(result, remaining, target_tokens, tokens_used)
        
        original_count = len(remaining) + (len(result) - len(messages_to_add))
        if len(result) < original_count:
            logger.info(
                "Context truncated: kept %d of %d messages (~%d tokens)",
                len(result),
                original_count,
                tokens_used,
            )
        
        return result

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
