"""
Chat Router - WBS 2.2.2, WBS 2.2.3 Chat Completions & Streaming

This module implements the chat completions API following OpenAI compatibility patterns.

Reference Documents:
- GUIDELINES: FastAPI dependency injection (Sinha pp. 89-91)
- GUIDELINES: Pydantic validators (Sinha pp. 193-195)
- GUIDELINES: Tool/function calling (AI Engineering pp. 1463-1587)
- GUIDELINES: REST constraints (Buelta pp. 92-93, 126)
- GUIDELINES p. 2149: Token generation and streaming patterns
- GUIDELINES p. 2043: Reactive programming patterns (Observable streams)

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses
- ANTI_PATTERN_ANALYSIS §4.1: Cognitive complexity < 15 per function

CMS Integration (WBS-CMS11):
- AC-11.1: Gateway routes Tier 2+ requests to CMS
- AC-11.2: X-CMS-Mode header protocol implemented
- AC-11.3: X-CMS-Routed response header set
- AC-11.4: Tier 3+ returns 503 when CMS unavailable
- AC-11.5: Fast token estimation in Gateway
"""

import os
import time
import uuid
import logging
from typing import Optional, AsyncGenerator, Union

from fastapi import APIRouter, Depends, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse

from src.core.exceptions import ProviderError
from src.models.requests import ChatCompletionRequest
from src.models.responses import (
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    Usage,
    ChatCompletionChunk,
    ChunkChoice,
    ChunkDelta,
)

# CMS Routing Imports (WBS-CMS11)
from src.api.routes.cms_routing import (
    calculate_tier,
    parse_cms_mode,
    should_route_to_cms,
    get_cms_action,
    build_cms_response_headers,
    cms_required_for_tier,
    handle_cms_unavailable,
    estimate_tokens_from_messages,
    get_context_limit,
    get_cms_client_instance,
)


# Configure logging
logger = logging.getLogger(__name__)

# Environment configuration
DEFAULT_MODEL = os.getenv("LLM_GATEWAY_DEFAULT_MODEL", "gpt-4")


# =============================================================================
# Chat Service - WBS 2.2.2.3.9 Service Layer Extraction
# Pattern: Cognitive complexity reduction (ANTI_PATTERN §4.1)
# Pattern: Dependency injection (Sinha pp. 89-91)
#
# NOTE Issue 27 (Comp_Static_Analysis_Report_20251203.md):
# This stub ChatService should be replaced with the real implementation from
# src/services/chat.ChatService. The full migration requires:
# 1. Setting up FastAPI dependency injection for ProviderRouter, ToolExecutor, SessionManager
# 2. Updating get_chat_service() to wire up real dependencies
# 3. Creating test fixtures for mocking the real service dependencies
#
# The stub is retained for backwards compatibility during incremental migration.
# Real implementation: src/services/chat.py - ChatService with full provider routing,
# tool execution, and session management.
# Implementation deferred to Stage 4: Full Service Migration (WBS 4.x)
# =============================================================================


class ChatService:
    """
    STUB Service class for chat completion operations.

    WARNING: This is a simplified stub implementation used for initial development
    and testing. For production LLM integration, use src/services/chat.ChatService.

    Pattern: Service layer extraction for business logic
    Reference: ANTI_PATTERN_ANALYSIS §4.1 - Extract complex logic to services

    See Also:
        src/services/chat.ChatService: Full implementation with provider routing
    """

    def __init__(self):
        """Initialize chat service."""
        self._default_model = DEFAULT_MODEL

    async def create_completion(  # NOSONAR - async for LLM provider compatibility
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Create a chat completion.

        WBS 2.2.2.3.10: Service method for creating completions.

        Args:
            request: Validated chat completion request

        Returns:
            ChatCompletionResponse: The completion response

        Note:
            This is a stub implementation that uses async for future LLM provider
            integration. In production, this would:
            1. Route to the appropriate LLM provider (async HTTP calls)
            2. Handle token counting
            3. Implement caching strategy
            4. Apply rate limiting
            
            The async keyword is intentionally retained for API compatibility
            with future implementations that require async I/O.
        """
        # Generate response ID
        response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        # Stub response - in production, this calls the LLM provider
        # Pattern: Stateless REST (Buelta p. 93)
        completion_content = self._generate_stub_response(request)

        # Calculate stub token usage
        prompt_tokens = self._estimate_prompt_tokens(request)
        completion_tokens = len(completion_content.split()) * 2  # Rough estimate
        total_tokens = prompt_tokens + completion_tokens

        return ChatCompletionResponse(
            id=response_id,
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ChoiceMessage(
                        role="assistant",
                        content=completion_content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

    def _generate_stub_response(self, request: ChatCompletionRequest) -> str:
        """
        Generate stub response for testing.

        In production, this is replaced with actual LLM call.
        """
        last_user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user" and msg.content:
                last_user_message = msg.content
                break

        if last_user_message:
            return f"This is a stub response to: {last_user_message[:50]}..."
        return "This is a stub response from the LLM Gateway."

    def _estimate_prompt_tokens(self, request: ChatCompletionRequest) -> int:
        """
        Estimate prompt tokens for stub response.

        In production, use actual tokenizer.
        """
        total_chars = sum(
            len(msg.content or "") for msg in request.messages if msg.content
        )
        # Rough estimate: ~4 chars per token
        return max(1, total_chars // 4)

    # =========================================================================
    # Streaming Support - WBS 2.2.3
    # Pattern: Token generation and streaming (GUIDELINES p. 2149)
    # Pattern: Observable patterns with async generators (Sinha)
    # =========================================================================

    async def stream_completion(  # NOSONAR - async generator for LLM streaming
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        Stream a chat completion as chunks.

        WBS 2.2.3.2.6: Async generator for streaming completions.

        Pattern: Iterator protocol with yield (GUIDELINES p. 2149)
        Pattern: Observable patterns (Sinha)

        Args:
            request: Validated chat completion request

        Yields:
            ChatCompletionChunk: Each chunk of the streamed response
        """
        # Generate consistent response ID for all chunks
        response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())

        # Generate stub response and split into tokens
        full_response = self._generate_stub_response(request)
        tokens = full_response.split()

        # First chunk: role only
        yield ChatCompletionChunk(
            id=response_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(role="assistant"),
                    finish_reason=None,
                )
            ],
        )

        # Content chunks: yield each token
        for i, token in enumerate(tokens):
            # Add space before token (except first)
            content = f" {token}" if i > 0 else token

            yield ChatCompletionChunk(
                id=response_id,
                created=created,
                model=request.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=ChunkDelta(content=content),
                        finish_reason=None,
                    )
                ],
            )

        # Final chunk: finish_reason
        yield ChatCompletionChunk(
            id=response_id,
            created=created,
            model=request.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChunkDelta(),
                    finish_reason="stop",
                )
            ],
        )


# =============================================================================
# Dependency Injection - FastAPI Pattern (Sinha p. 90)
# WBS 2.2.2.3.11: Dependency factory for ChatService
# Issue 27 Resolution: Wire to real ChatService with provider routing
# =============================================================================

# Global service instance (can be overridden in tests)
_chat_service: Optional["RealChatService"] = None


def get_chat_service() -> "RealChatService":
    """
    Dependency injection factory for ChatService.

    Pattern: Factory method for dependency injection (Sinha p. 90)
    
    Issue 27 Resolution (Comp_Static_Analysis_Report_20251203.md):
    This function now returns the real ChatService from src/services/chat.py
    with properly wired dependencies:
    - ProviderRouter: For model-based provider selection
    - ToolExecutor: For tool/function calling capability

    Returns:
        ChatService: The real chat service instance with provider routing
    """
    global _chat_service
    if _chat_service is None:
        # Import here to avoid circular imports
        from src.services.chat import ChatService as RealChatService
        from src.providers.router import create_provider_router
        from src.tools.executor import ToolExecutor
        from src.tools.registry import get_tool_registry
        from src.core.config import get_settings
        
        settings = get_settings()
        router = create_provider_router(settings)
        executor = ToolExecutor(registry=get_tool_registry())
        
        _chat_service = RealChatService(
            router=router,
            executor=executor,
        )
    return _chat_service


# Type alias for the real ChatService (used in type hints above)
from src.services.chat import ChatService as RealChatService


# =============================================================================
# Router - WBS 2.2.2.1
# =============================================================================

router = APIRouter(prefix="/v1/chat", tags=["Chat"])


# =============================================================================
# Chat Completions Endpoint - WBS 2.2.2.3, WBS 2.2.3
# =============================================================================


@router.post("/completions", response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest,
    chat_service: RealChatService = Depends(get_chat_service),
    x_cms_mode: Optional[str] = Header(None, alias="X-CMS-Mode"),
) -> ChatCompletionResponse | StreamingResponse | JSONResponse:
    """
    Create a chat completion (streaming or non-streaming).

    WBS 2.2.2.3.1: POST /v1/chat/completions endpoint
    WBS 2.2.2.3.2: Returns OpenAI-compatible response
    WBS 2.2.2.3.9: Provider errors return 502 Bad Gateway
    WBS 2.2.3.2.1: Supports streaming with stream=true
    
    CMS Integration (WBS-CMS11):
    - AC-11.1: Gateway routes Tier 2+ requests to CMS
    - AC-11.2: X-CMS-Mode header protocol implemented
    - AC-11.3: X-CMS-Routed response header set
    - AC-11.4: Tier 3+ returns 503 when CMS unavailable
    - AC-11.5: Fast token estimation in Gateway

    Pattern: Dependency injection for service layer (Sinha p. 90)
    Pattern: Pydantic request validation (Sinha pp. 193-195)
    Pattern: Iterator protocol with yield for streaming (GUIDELINES p. 2149)
    Pattern: Error translation (Newman pp. 273-275)

    Args:
        request: Chat completion request with messages and parameters
        chat_service: Injected chat service dependency
        x_cms_mode: Optional CMS mode header (none|validate|optimize|plan|auto)

    Returns:
        ChatCompletionResponse: Full response (non-streaming)
        StreamingResponse: SSE stream (streaming)
        JSONResponse: Error response with 502 status

    Raises:
        HTTPException 422: Request validation failed
        HTTPException 503: CMS unavailable for Tier 3+
        JSONResponse 502: Provider error (upstream failure)
    """
    logger.debug(f"Chat completion request: model={request.model}, stream={request.stream}")
    
    # Check for Responses API models - they should use /v1/responses endpoint
    RESPONSES_API_MODELS = {"gpt-5.2-pro", "gpt-5.1-pro", "gpt-5-pro", "o3", "o3-mini", "o1", "o1-mini", "o1-preview"}
    if request.model in RESPONSES_API_MODELS:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"Model '{request.model}' uses the Responses API and is not supported "
                              f"in the v1/chat/completions endpoint. Please use POST /v1/responses instead.",
                    "type": "invalid_request_error",
                    "code": "model_not_supported",
                }
            },
        )

    # ==========================================================================
    # CMS Integration (WBS-CMS11)
    # ==========================================================================
    
    # AC-11.5: Fast token estimation
    messages_for_estimation = [
        {"role": m.role, "content": m.content or ""} for m in request.messages
    ]
    token_count = estimate_tokens_from_messages(messages_for_estimation, request.model)
    context_limit = get_context_limit(request.model)
    
    # AC-11.1: Calculate tier
    tier = calculate_tier(token_count, context_limit)
    
    # AC-11.2: Parse CMS mode header
    cms_mode = parse_cms_mode(x_cms_mode)
    
    # Determine if we should route to CMS
    route_to_cms = should_route_to_cms(tier, cms_mode)
    cms_routed = False
    
    if route_to_cms:
        # Get CMS client
        cms_client = get_cms_client_instance()
        
        # Check CMS availability
        cms_available = await cms_client.health_check()
        
        if not cms_available:
            # AC-11.4: Tier 3+ requires CMS - return 503
            if cms_required_for_tier(tier):
                handle_cms_unavailable(tier)
            # Tier 1-2 can proceed without CMS (graceful degradation)
            logger.warning(f"CMS unavailable, degrading gracefully for tier {tier}")
        else:
            # CMS is available, process the request
            cms_action = get_cms_action(tier, cms_mode)
            
            if cms_action != "none":
                try:
                    # Build text from messages for CMS processing
                    combined_text = "\n".join(
                        f"{m.role}: {m.content}" for m in request.messages if m.content
                    )
                    
                    # Call CMS
                    cms_result = await cms_client.process(
                        text=combined_text,
                        model=request.model,
                    )
                    
                    cms_routed = True
                    
                    # Update token count with actual from CMS
                    token_count = cms_result.optimized_tokens
                    
                    logger.info(
                        f"CMS processed: tier={tier}, action={cms_action}, "
                        f"compression={cms_result.compression_ratio:.1%}"
                    )
                    
                    # Apply CMS optimized text to request messages
                    # CMS returns optimized text in format "role: content\nrole: content"
                    # For optimization, we merge all into a single user message since
                    # the LLM context is what matters for token efficiency
                    if cms_result.compression_ratio > 0 and not cms_result.rolled_back:
                        # Create a new messages list with optimized content
                        # Keep system message intact, replace user messages with optimized
                        optimized_messages = []
                        for msg in request.messages:
                            if msg.role == "system":
                                # Preserve system messages unchanged
                                optimized_messages.append(msg)
                        
                        # Add the optimized user content as final message
                        # Import Message from models to create new message
                        from src.models.requests import Message
                        optimized_messages.append(Message(
                            role="user",
                            content=cms_result.optimized_text,
                        ))
                        
                        # Update request with optimized messages
                        request = request.model_copy(update={"messages": optimized_messages})
                        
                        logger.debug(
                            f"Applied CMS optimization: {len(request.messages)} messages, "
                            f"tokens {cms_result.original_tokens}→{cms_result.optimized_tokens}"
                        )
                    
                except Exception as e:
                    logger.error(f"CMS processing failed: {e}")
                    # For Tier 3+, this is critical
                    if cms_required_for_tier(tier):
                        handle_cms_unavailable(tier)
                    # Tier 1-2 continues without CMS
    
    # AC-11.3: Build response headers
    cms_headers = build_cms_response_headers(
        routed=cms_routed,
        tier=tier,
        token_count=token_count,
        token_limit=context_limit,
    )

    try:
        if request.stream:
            return StreamingResponse(
                _stream_sse_generator(chat_service, request),
                media_type="text/event-stream",
                headers=cms_headers,
            )

        # Issue 27: Real ChatService uses complete(), not create_completion()
        response = await chat_service.complete(request)
        
        # Add CMS headers to non-streaming response
        return JSONResponse(
            content=response.model_dump(),
            headers=cms_headers,
        )

    except ProviderError as e:
        # WBS 2.2.2.3.9: Translate provider errors to 502 Bad Gateway
        # Pattern: Error translation (Newman pp. 273-275)
        # Pattern: Exception logging (ANTI_PATTERN §3.1)
        logger.error(
            f"Provider error during chat completion: provider={e.provider}, "
            f"message={e.message}, status_code={e.status_code}"
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": e.message,
                    "code": e.error_code,
                    "provider": e.provider,
                    "type": "provider_error",
                }
            },
        )


async def _stream_sse_generator(
    chat_service: RealChatService, request: ChatCompletionRequest
) -> AsyncGenerator[str, None]:
    """
    Generate SSE-formatted stream from chat service.

    WBS 2.2.3.2.3: Format chunks as SSE 'data: ' lines.
    WBS 2.2.3.3.1: End stream with 'data: [DONE]' marker.

    Pattern: Server-Sent Events (SSE) format
    Pattern: Observable patterns (Sinha)

    Args:
        chat_service: The chat service instance
        request: The chat completion request

    Yields:
        str: SSE-formatted data lines
    """
    async for chunk in chat_service.stream_completion(request):
        yield f"data: {chunk.model_dump_json()}\n\n"

    # End marker - WBS 2.2.3.3.1
    yield "data: [DONE]\n\n"
