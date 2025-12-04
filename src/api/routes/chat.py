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
"""

import os
import time
import uuid
import logging
from typing import Optional, AsyncGenerator, Union

from fastapi import APIRouter, Depends
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


# Configure logging
logger = logging.getLogger(__name__)

# Environment configuration
DEFAULT_MODEL = os.getenv("LLM_GATEWAY_DEFAULT_MODEL", "gpt-4")


# =============================================================================
# Chat Service - WBS 2.2.2.3.9 Service Layer Extraction
# Pattern: Cognitive complexity reduction (ANTI_PATTERN §4.1)
# Pattern: Dependency injection (Sinha pp. 89-91)
# =============================================================================


class ChatService:
    """
    Service class for chat completion operations.

    Pattern: Service layer extraction for business logic
    Reference: ANTI_PATTERN_ANALYSIS §4.1 - Extract complex logic to services

    This class enables:
    1. Dependency injection for testability
    2. Separation of business logic from routing
    3. Future extension for LLM provider integration
    """

    def __init__(self):
        """Initialize chat service."""
        self._default_model = DEFAULT_MODEL

    async def create_completion(
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

    async def stream_completion(
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
# =============================================================================

# Global service instance (can be overridden in tests)
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Dependency injection factory for ChatService.

    Pattern: Factory method for dependency injection (Sinha p. 90)

    Returns:
        ChatService: The chat service instance
    """
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


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
    chat_service: ChatService = Depends(get_chat_service),
) -> Union[ChatCompletionResponse, StreamingResponse, JSONResponse]:
    """
    Create a chat completion (streaming or non-streaming).

    WBS 2.2.2.3.1: POST /v1/chat/completions endpoint
    WBS 2.2.2.3.2: Returns OpenAI-compatible response
    WBS 2.2.2.3.9: Provider errors return 502 Bad Gateway
    WBS 2.2.3.2.1: Supports streaming with stream=true

    Pattern: Dependency injection for service layer (Sinha p. 90)
    Pattern: Pydantic request validation (Sinha pp. 193-195)
    Pattern: Iterator protocol with yield for streaming (GUIDELINES p. 2149)
    Pattern: Error translation (Newman pp. 273-275)

    Args:
        request: Chat completion request with messages and parameters
        chat_service: Injected chat service dependency

    Returns:
        ChatCompletionResponse: Full response (non-streaming)
        StreamingResponse: SSE stream (streaming)
        JSONResponse: Error response with 502 status

    Raises:
        HTTPException 422: Request validation failed
        JSONResponse 502: Provider error (upstream failure)
    """
    logger.debug(f"Chat completion request: model={request.model}, stream={request.stream}")

    try:
        if request.stream:
            return StreamingResponse(
                _stream_sse_generator(chat_service, request),
                media_type="text/event-stream",
            )

        return await chat_service.create_completion(request)

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
    chat_service: ChatService, request: ChatCompletionRequest
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
