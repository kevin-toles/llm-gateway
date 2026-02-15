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

Issue 27 Resolution (M-1):
- Stub ChatService removed — real ChatService from src/services/chat.py
  is wired via get_chat_service() dependency injection factory

WBS-MCE0: CMS Integration
- Routes Tier 2+ requests through CMS for token management
- Adds X-CMS-* response headers for observability
"""

import os
import logging
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse, Response

from src.core.exceptions import ProviderError
from src.models.requests import ChatCompletionRequest
from src.models.responses import ChatCompletionResponse

# WBS-MCE0: CMS routing integration
from src.api.routes.cms_routing import (
    estimate_tokens_from_messages,
    get_context_limit,
    calculate_tier,
    parse_cms_mode,
    should_route_to_cms,
    get_cms_action,
    build_cms_response_headers,
    cms_required_for_tier,
    handle_cms_unavailable,
    get_cms_client_instance,
)


# Configure logging
logger = logging.getLogger(__name__)

# Environment configuration
DEFAULT_MODEL = os.getenv("LLM_GATEWAY_DEFAULT_MODEL", "gpt-5.2")


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

# Models that require the Responses API endpoint
RESPONSES_API_MODELS = frozenset({
    "gpt-5.2-pro", "gpt-5.1-pro", "gpt-5-pro", 
    "o3", "o3-mini", "o1", "o1-mini", "o1-preview"
})


async def _verify_cms_availability(tier: int, cms_mode: str) -> None:
    """Verify CMS is available for requests that require it.
    
    Args:
        tier: Token tier (1-4)
        cms_mode: CMS mode from header
        
    Raises:
        HTTPException: If CMS is required but unavailable
    """
    if not cms_required_for_tier(tier) or cms_mode == "none":
        return
    
    cms_client = get_cms_client_instance()
    if cms_client:
        is_healthy = await cms_client.health_check()
        if not is_healthy:
            handle_cms_unavailable(tier)
    elif tier >= 3 and cms_mode != "none":
        handle_cms_unavailable(tier)


def _check_responses_api_model(model: str) -> JSONResponse | None:
    """Check if model requires Responses API endpoint.
    
    Returns JSONResponse with error if model is not supported, None otherwise.
    """
    if model in RESPONSES_API_MODELS:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"Model '{model}' uses the Responses API and is not supported "
                              f"in the v1/chat/completions endpoint. Please use POST /v1/responses instead.",
                    "type": "invalid_request_error",
                    "code": "model_not_supported",
                }
            },
        )
    return None


# =============================================================================
# Chat Completions Endpoint - WBS 2.2.2.3, WBS 2.2.3
# =============================================================================


@router.post("/completions", response_model=None)
async def create_chat_completion(
    request: ChatCompletionRequest,
    chat_service: RealChatService = Depends(get_chat_service),
    x_cms_mode: Optional[str] = Header(None, alias="X-CMS-Mode"),
) -> ChatCompletionResponse | StreamingResponse | JSONResponse | Response:
    """
    Create a chat completion (streaming or non-streaming).

    WBS 2.2.2.3.1: POST /v1/chat/completions endpoint
    WBS 2.2.2.3.2: Returns OpenAI-compatible response
    WBS 2.2.2.3.9: Provider errors return 502 Bad Gateway
    WBS 2.2.3.2.1: Supports streaming with stream=true
    WBS-MCE0: CMS integration with tier-based routing

    Pattern: Dependency injection for service layer (Sinha p. 90)
    Pattern: Pydantic request validation (Sinha pp. 193-195)
    Pattern: Iterator protocol with yield for streaming (GUIDELINES p. 2149)
    Pattern: Error translation (Newman pp. 273-275)

    Args:
        request: Chat completion request with messages and parameters
        chat_service: Injected chat service dependency
        x_cms_mode: Optional CMS mode header (none, validate, optimize, plan, auto)

    Returns:
        ChatCompletionResponse: Full response (non-streaming)
        StreamingResponse: SSE stream (streaming)
        JSONResponse: Error response with 502 status

    Raises:
        HTTPException 422: Request validation failed
        HTTPException 503: CMS unavailable for Tier 3+ requests
        JSONResponse 502: Provider error (upstream failure)
    """
    logger.debug(f"Chat completion request: model={request.model}, stream={request.stream}")
    
    # Check for Responses API models first
    if error_response := _check_responses_api_model(request.model):
        return error_response
    
    # ==========================================================================
    # WBS-MCE0: CMS Tier Calculation and Routing
    # ==========================================================================
    
    # Convert messages to dicts for token estimation
    messages_dicts = [
        {"role": msg.role, "content": msg.content or ""}
        for msg in request.messages
    ]
    
    # Calculate token tier
    token_count = estimate_tokens_from_messages(messages_dicts, request.model)
    context_limit = get_context_limit(request.model)
    tier = calculate_tier(token_count, context_limit)
    
    # Parse CMS mode from header
    cms_mode = parse_cms_mode(x_cms_mode)
    
    # Determine if we should route to CMS
    route_to_cms = should_route_to_cms(tier, cms_mode)
    
    # For Tier 3+, verify CMS is available
    await _verify_cms_availability(tier, cms_mode)
    
    # Build CMS response headers
    cms_headers = build_cms_response_headers(
        routed=route_to_cms,
        tier=tier,
        token_count=token_count,
        token_limit=context_limit,
    )
    
    # ==========================================================================
    # End CMS Integration
    # ==========================================================================

    try:
        if request.stream:
            # For streaming, add CMS headers to the StreamingResponse
            return StreamingResponse(
                _stream_sse_generator(chat_service, request),
                media_type="text/event-stream",
                headers=cms_headers,
            )

        # Issue 27: Real ChatService uses complete(), not create_completion()
        response = await chat_service.complete(request)
        
        # Wrap response in JSONResponse to add CMS headers
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
