"""
Messages Router - Anthropic-format /v1/messages endpoint

Accepts Anthropic SDK requests (POST /v1/messages) and routes them through
the existing CMS tier middleware and AnthropicProvider.

Setting ANTHROPIC_BASE_URL=http://localhost:8080 in the environment causes
the Anthropic SDK (and Claude Code) to route API calls through this endpoint,
picking up CMS context management transparently.

Bypass mode (LLM_GATEWAY_BYPASS_ENABLED=true) turns the gateway into a pure
transparent proxy — no CMS enrichment, no provider routing, no SDK detection.
All requests are forwarded raw to the upstream Anthropic API.

Supports both streaming (Anthropic SSE format) and non-streaming responses.
"""

import asyncio
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Optional

import httpx
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.api.routes.chat import RealChatService, get_chat_service
from src.core.config import Settings, get_settings
from src.api.routes.cms_routing import (
    build_cms_response_headers,
    calculate_tier,
    estimate_tokens_from_messages,
    get_cms_client_instance,
    get_context_limit,
    handle_cms_unavailable,
    parse_cms_mode,
    should_route_to_cms,
    cms_required_for_tier,
)
from src.core.exceptions import ProviderError
from src.services.chat import ChatServiceError
from src.models.requests import ChatCompletionRequest, Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Messages"])


# =============================================================================
# Anthropic Request Models
# =============================================================================


class AnthropicContentBlock(BaseModel):
    type: str
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict[str, Any]] = None
    tool_use_id: Optional[str] = None
    content: Optional[str] = None


class AnthropicMessage(BaseModel):
    role: str
    content: str | list[AnthropicContentBlock] | list[dict[str, Any]]


class AnthropicTool(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: dict[str, Any] = {}


class AnthropicMessagesRequest(BaseModel):
    model: str
    messages: list[AnthropicMessage]
    max_tokens: int = 1024
    system: Optional[str | list[dict[str, Any]]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    tools: Optional[list[AnthropicTool]] = None
    metadata: Optional[dict[str, Any]] = None
    stop_sequences: Optional[list[str]] = None
    top_k: Optional[int] = None


# =============================================================================
# Format Converters
# =============================================================================


def _extract_text(content: str | list | None) -> str:
    """Extract plain text from Anthropic content (string or content blocks)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        elif hasattr(block, "type") and block.type == "text" and block.text:
            parts.append(block.text)
    return " ".join(parts)


def _anthropic_to_chat_request(req: AnthropicMessagesRequest) -> ChatCompletionRequest:
    """Convert Anthropic messages request to internal ChatCompletionRequest."""
    messages: list[Message] = []

    if req.system:
        messages.append(Message(role="system", content=_extract_text(req.system)))

    for msg in req.messages:
        text = _extract_text(msg.content)
        messages.append(Message(role=msg.role, content=text))

    tools = None
    if req.tools:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in req.tools
        ]

    return ChatCompletionRequest(
        model=req.model,
        messages=messages,
        max_tokens=req.max_tokens,
        stream=req.stream or False,
        temperature=req.temperature,
        top_p=req.top_p,
        tools=tools,
    )


def _finish_reason_to_stop_reason(finish_reason: Optional[str]) -> str:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "stop_sequence",
    }
    return mapping.get(finish_reason or "stop", "end_turn")


def _chat_response_to_anthropic(response: Any, model: str) -> dict[str, Any]:
    """Convert ChatCompletionResponse to Anthropic messages response format."""
    choice = response.choices[0]
    message = choice.message

    content: list[dict[str, Any]] = []
    if message.content:
        content.append({"type": "text", "text": message.content})
    if message.tool_calls:
        for tc in message.tool_calls:
            import json
            content.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                    "name": tc.get("function", {}).get("name", ""),
                    "input": json.loads(tc.get("function", {}).get("arguments", "{}")),
                }
            )

    stop_reason = _finish_reason_to_stop_reason(choice.finish_reason)

    usage: dict[str, int] = {}
    if response.usage:
        usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }

    return {
        "id": response.id or f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": response.model or model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage,
    }


# =============================================================================
# Passthrough mode — forward raw request upstream without CMS processing
# =============================================================================


async def _passthrough_request(
    fastapi_request: Request,
    body_bytes: bytes,
    is_stream: bool,
    caller_api_key: Optional[str],
) -> JSONResponse | StreamingResponse:
    """Forward the raw request upstream, bypassing all CMS/provider routing."""
    upstream_base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    upstream_url = f"{upstream_base.rstrip('/')}/v1/messages"

    upstream_headers = {
        "content-type": "application/json",
        "anthropic-version": fastapi_request.headers.get(
            "anthropic-version", "2023-06-01"
        ),
    }
    # Forward all anthropic-* headers (e.g. anthropic-beta, anthropic-organization, etc.)
    # Claude Code sends anthropic-beta: context-management-2025-06-27 which enables
    # experimental features like context_management — dropping it causes a 400 error
    # because Anthropic's API schema validation rejects unknown fields without the opt-in header.
    for hdr_name, hdr_val in fastapi_request.headers.items():
        hdr_lower = hdr_name.lower()
        if hdr_lower.startswith("anthropic-") and hdr_lower not in ("anthropic-version",):
            upstream_headers[hdr_name] = hdr_val
    if caller_api_key:
        if caller_api_key.startswith("sk-ant-oat"):
            upstream_headers["authorization"] = f"Bearer {caller_api_key}"
        else:
            upstream_headers["x-api-key"] = caller_api_key

    async with httpx.AsyncClient(timeout=300.0) as client:
        upstream_resp = await client.post(
            upstream_url,
            headers=upstream_headers,
            content=body_bytes,
        )

    if is_stream:
        return StreamingResponse(
            upstream_resp.aiter_bytes(),
            media_type="text/event-stream",
            status_code=upstream_resp.status_code,
        )
    return JSONResponse(
        content=upstream_resp.json(),
        status_code=upstream_resp.status_code,
    )


# =============================================================================
# Streaming SSE generator (Anthropic event format)
# =============================================================================


def _build_stream_iter(
    chat_service: RealChatService,
    request: ChatCompletionRequest,
    caller_api_key: Optional[str],
    headers: dict[str, str] | None = None,
) -> AsyncGenerator:
    """Return the appropriate stream iterator based on auth context.

    For Anthropic-originated credentials, creates a one-shot AnthropicProvider
    that handles credential type detection internally.
    """
    if caller_api_key and caller_api_key.startswith("sk-ant-"):
        from src.providers.anthropic import AnthropicProvider
        return AnthropicProvider(credential=caller_api_key).stream(request)
    return chat_service.stream_completion(request, headers=headers)


def _process_stream_chunk(
    chunk: Any,
    output_tokens: int,
    input_tokens: int,
) -> tuple[Optional[str], str, int, int]:
    """Extract SSE event string and updated token counts from one chunk.

    Returns (sse_event_or_none, finish_reason_or_empty, new_output_tokens, new_input_tokens).
    """
    import json

    if not chunk.choices:
        return None, "", output_tokens, input_tokens

    choice = chunk.choices[0]
    delta = choice.delta
    event: Optional[str] = None
    finish_reason = ""

    if delta.content:
        output_tokens += max(1, len(delta.content) // 4)
        event = f"event: content_block_delta\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': delta.content}})}\n\n"

    if choice.finish_reason:
        finish_reason = _finish_reason_to_stop_reason(choice.finish_reason)

    if chunk.usage:
        input_tokens = chunk.usage.prompt_tokens or input_tokens
        output_tokens = chunk.usage.completion_tokens or output_tokens

    return event, finish_reason, output_tokens, input_tokens


async def _anthropic_sse_generator(
    chat_service: RealChatService,
    request: ChatCompletionRequest,
    model: str,
    caller_api_key: Optional[str] = None,
    headers: dict[str, str] | None = None,
) -> AsyncGenerator[str, None]:
    """Yield Anthropic SSE events from the internal streaming chat service."""
    import json

    message_id = f"msg_{uuid.uuid4().hex}"
    input_tokens = 0
    output_tokens = 0

    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant', 'content': [], 'model': model, 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    yield "event: ping\ndata: {\"type\": \"ping\"}\n\n"

    finish_reason = "end_turn"
    async for chunk in _build_stream_iter(chat_service, request, caller_api_key, headers=headers):
        event, chunk_finish, output_tokens, input_tokens = _process_stream_chunk(
            chunk, output_tokens, input_tokens
        )
        if event:
            yield event
        if chunk_finish:
            finish_reason = chunk_finish

    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': finish_reason, 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"


# =============================================================================
# /v1/messages endpoint
# =============================================================================


async def _verify_cms_availability(tier: int, cms_mode: str) -> None:
    if not cms_required_for_tier(tier) or cms_mode == "none":
        return
    cms_client = get_cms_client_instance()
    if cms_client:
        is_healthy = await cms_client.health_check()
        if not is_healthy:
            handle_cms_unavailable(tier)
    elif tier >= 3 and cms_mode != "none":
        handle_cms_unavailable(tier)


async def _complete_via_provider(
    internal_request: "ChatCompletionRequest",
    chat_service: RealChatService,
    caller_api_key: Optional[str],
    headers: dict[str, str] | None = None,
) -> Any:
    """Call complete(), using the caller's API key when it's an Anthropic key.

    When ANTHROPIC_BASE_URL is set, the SDK sends its own sk-ant-* key in the
    Authorization header.  We extract it here and create a one-shot provider so
    the gateway's configured key (which may have no credits) is not used.

    The AnthropicProvider handles credential type detection internally,
    so the route layer does NOT need to distinguish api_key from auth_token.
    """
    if caller_api_key and caller_api_key.startswith("sk-ant-"):
        from src.providers.anthropic import AnthropicProvider
        provider = AnthropicProvider(credential=caller_api_key)
        return await provider.complete(internal_request)
    return await chat_service.complete(internal_request, headers=headers)


@router.post("/messages", response_model=None)
async def create_message(
    request: AnthropicMessagesRequest,
    fastapi_request: Request,
    chat_service: RealChatService = Depends(get_chat_service),
    x_cms_mode: Optional[str] = Header(None, alias="X-CMS-Mode"),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    authorization: Optional[str] = Header(None),
) -> JSONResponse | StreamingResponse:
    """
    Anthropic-format messages endpoint (POST /v1/messages).

    Accepts requests in Anthropic SDK format and routes through CMS tier
    middleware before forwarding to the Anthropic provider.

    Enable by setting ANTHROPIC_BASE_URL=http://localhost:8080 in the
    environment before launching Claude Code or any Anthropic SDK client.
    The caller's x-api-key (or Authorization Bearer) is forwarded to Anthropic
    so the gateway's own API key is not consumed.
    """
    logger.info(f"Anthropic messages request: model={request.model}, stream={request.stream}, messages_count={len(request.messages)}")

    # Log raw request body for Claude Code streaming investigation
    body_bytes = await fastapi_request.body()
    logger.info(f"Raw request body (first 3000 chars): {body_bytes[:3000]}")

    # Extract caller API key for passthrough auth.
    # Anthropic SDK sends x-api-key; some clients use Authorization: Bearer.
    caller_api_key: Optional[str] = x_api_key
    if not caller_api_key and authorization and authorization.startswith("Bearer "):
        caller_api_key = authorization.removeprefix("Bearer ").strip()

    # Log auth header trace — never log full tokens
    logger.info(
        "Auth trace: x_api_key_present=%s x_api_key_prefix=%s authorization_present=%s auth_prefix=%s resolved_caller_key_prefix=%s",
        x_api_key is not None,
        (x_api_key[:15] if x_api_key else None),
        authorization is not None,
        (authorization[:20] if authorization else None),
        (caller_api_key[:15] if caller_api_key else None),
    )

    # ── Gateway Bypass Check ────────────────────────────────────────────────
    # When bypass_enabled=True, ALL processing is skipped and the raw request
    # is forwarded upstream. This effectively disables the LLM gateway
    # integration, making the gateway a pure transparent proxy.
    # Set LLM_GATEWAY_BYPASS_ENABLED=true in the environment.
    settings: Settings = get_settings()
    if settings.bypass_enabled:
        logger.info("Gateway bypass ENABLED — forwarding raw request upstream (passthrough only)")
        return await _passthrough_request(
            fastapi_request, body_bytes, request.stream, caller_api_key
        )

    # Detect whether the caller is an Anthropic SDK client (e.g. Claude Code).
    # Python SDK sends: "AnthropicClient/Python 0.75.0" or "AsyncAnthropic/..."
    # Node.js SDK sends: "anthropic-node/..." or "AnthropicNode/..."
    # Claude Code may send: "Claude-Code/..." or a custom identifier
    # When SDK-originated, we passthrough directly and run CMS as a best-effort
    # background task — this ensures the gateway crash does not block Claude Code.
    raw_headers: dict[str, str] = dict(fastapi_request.headers)
    user_agent = raw_headers.get("user-agent", "")
    ua_lower = user_agent.lower()
    is_sdk_caller = (
        ua_lower.startswith("anthropicclient/")
        or ua_lower.startswith("asyncanthropic/")
        or ua_lower.startswith("anthropic-node/")
        or ua_lower.startswith("anthropicnode/")
        or "claude-code" in ua_lower
        or "claudecode" in ua_lower
    )

    if is_sdk_caller:
        logger.info("SDK caller detected (user-agent=%s), using passthrough path", user_agent)

        # Launch CMS enrichment as a non-blocking best-effort background task
        async def _enrich_in_background() -> None:
            try:
                internal_request = _anthropic_to_chat_request(request)
                messages_dicts = [
                    {"role": msg.role, "content": msg.content or ""}
                    for msg in internal_request.messages
                ]
                token_count = estimate_tokens_from_messages(messages_dicts, request.model)
                context_limit = get_context_limit(request.model)
                tier = calculate_tier(token_count, context_limit)
                cms_mode = parse_cms_mode(x_cms_mode)
                route_to_cms = should_route_to_cms(tier, cms_mode)
                if route_to_cms:
                    await _verify_cms_availability(tier, cms_mode)
                    logger.info("CMS enrichment completed for SDK caller (tier=%d)", tier)
            except Exception as exc:
                logger.warning("Background CMS enrichment failed (non-blocking): %s", exc)

        asyncio.create_task(_enrich_in_background())

        # Passthrough is the primary path for SDK callers
        return await _passthrough_request(
            fastapi_request, body_bytes, request.stream, caller_api_key
        )

    # ── Non-SDK callers: standard CMS → provider routing ──────────────────
    internal_request = _anthropic_to_chat_request(request)

    messages_dicts = [
        {"role": msg.role, "content": msg.content or ""}
        for msg in internal_request.messages
    ]
    token_count = estimate_tokens_from_messages(messages_dicts, request.model)
    context_limit = get_context_limit(request.model)
    tier = calculate_tier(token_count, context_limit)

    cms_mode = parse_cms_mode(x_cms_mode)
    route_to_cms = should_route_to_cms(tier, cms_mode)

    await _verify_cms_availability(tier, cms_mode)

    cms_headers = build_cms_response_headers(
        routed=route_to_cms,
        tier=tier,
        token_count=token_count,
        token_limit=context_limit,
    )

    logger.info(f"STREAMING DECISION: request.stream={request.stream!r}, session_id={raw_headers.get('x-session-id', 'unknown')}")

    try:
        if request.stream:
            return StreamingResponse(
                _anthropic_sse_generator(
                    chat_service, internal_request, request.model, caller_api_key, headers=raw_headers
                ),
                media_type="text/event-stream",
                headers=cms_headers,
            )

        logger.info("NON-STREAMING PATH: calling _complete_via_provider")
        response = await _complete_via_provider(internal_request, chat_service, caller_api_key, headers=raw_headers)
        anthropic_body = _chat_response_to_anthropic(response, request.model)

        return JSONResponse(content=anthropic_body, headers=cms_headers)

    except (ProviderError, RuntimeError, ConnectionError, ChatServiceError) as e:
        logger.warning(f"Provider/connection error, falling back to passthrough: {e}")
        return await _passthrough_request(
            fastapi_request, body_bytes, request.stream, caller_api_key
        )
