"""
CMS Routing Module - WBS-CMS11: Gateway Integration

This module provides routing logic for integrating with the Context Management Service.

Reference Documents:
- WBS_CONTEXT_MANAGEMENT_SERVICE.md: CMS11 Acceptance Criteria
- Architecture Doc → Integration Architecture

Header Protocol:
    Request:
        X-CMS-Mode: none | validate | optimize | plan
    
    Response:
        X-CMS-Routed: true | false
        X-CMS-Tier: 1 | 2 | 3 | 4
        X-Token-Count: 4521
        X-Token-Limit: 16384
        X-Headroom-Pct: 72

Tier Definitions:
    Tier 1: < 25% utilization - bypass CMS
    Tier 2: 25-50% utilization - validate only
    Tier 3: 50-75% utilization - optimize
    Tier 4: > 75% utilization - plan (chunking)
"""

import logging
from typing import Optional

from fastapi import HTTPException


logger = logging.getLogger(__name__)


# =============================================================================
# Model Context Limits
# =============================================================================

MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "qwen3-8b": 8192,
    "codellama-7b": 16384,
    "codellama-13b": 16384,
    "deepseek-coder-v2-lite": 131072,
    "llama-3.2-3b": 8192,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "claude-3-sonnet": 200000,
    "claude-3-opus": 200000,
}

DEFAULT_CONTEXT_LIMIT = 8192

# Estimation ratios (chars per token) by model family
ESTIMATION_RATIOS: dict[str, float] = {
    "qwen": 3.5,
    "codellama": 3.8,
    "deepseek": 3.2,
    "llama": 3.5,
    "gpt": 4.0,
    "claude": 3.8,
    "default": 4.0,
}


# =============================================================================
# CMS Client Reference (set by dependency injection)
# =============================================================================

_cms_client = None


def set_cms_client(client):
    """Set CMS client for routing (dependency injection for testing)."""
    global _cms_client
    _cms_client = client


def get_cms_client_instance():
    """Get the current CMS client instance."""
    global _cms_client
    if _cms_client is None:
        from src.clients.cms_client import get_cms_client
        _cms_client = get_cms_client()
    return _cms_client


# =============================================================================
# Tier Calculation (AC-11.1)
# =============================================================================


def calculate_tier(token_count: int, context_limit: int) -> int:
    """
    Calculate the CMS tier based on token utilization.
    
    Tier Definitions:
        Tier 1: < 25% utilization - bypass CMS
        Tier 2: 25-50% utilization - validate only
        Tier 3: 50-75% utilization - optimize
        Tier 4: > 75% utilization - plan (chunking)
    
    Args:
        token_count: Estimated or exact token count
        context_limit: Model's context window limit
        
    Returns:
        Tier number (1-4)
    """
    if context_limit <= 0:
        return 4  # Invalid limit, assume worst case
    
    utilization = token_count / context_limit
    
    if utilization < 0.25:
        return 1
    elif utilization < 0.50:
        return 2
    elif utilization < 0.75:
        return 3
    else:
        return 4


# =============================================================================
# CMS Mode Parsing (AC-11.2)
# =============================================================================


VALID_CMS_MODES = {"none", "validate", "optimize", "plan", "auto"}


def parse_cms_mode(mode: Optional[str]) -> str:
    """
    Parse X-CMS-Mode header value.
    
    Valid modes:
        - none: Bypass CMS entirely
        - validate: Count tokens only
        - optimize: Optimize text
        - plan: Full planning (optimize + chunk if needed)
        - auto: Use tier to determine action (default)
    
    Args:
        mode: Header value (case-insensitive)
        
    Returns:
        Normalized mode string
    """
    if mode is None:
        return "auto"
    
    normalized = mode.lower().strip()
    
    if normalized in VALID_CMS_MODES:
        return normalized
    
    logger.warning(f"Invalid CMS mode '{mode}', defaulting to 'auto'")
    return "auto"


# =============================================================================
# Routing Logic (AC-11.1, AC-11.2)
# =============================================================================


def should_route_to_cms(tier: int, mode: str) -> bool:
    """
    Determine if request should be routed to CMS.
    
    Args:
        tier: Calculated tier (1-4)
        mode: Parsed CMS mode
        
    Returns:
        True if should route to CMS
    """
    if mode == "none":
        return False
    
    if mode in ("validate", "optimize", "plan"):
        return True
    
    # Auto mode: route Tier 2+
    return tier >= 2


def get_cms_action(tier: int, mode: str) -> str:
    """
    Get the CMS action to perform.
    
    Args:
        tier: Calculated tier (1-4)
        mode: Parsed CMS mode
        
    Returns:
        Action string: "none", "validate", "optimize", or "plan"
    """
    if mode != "auto":
        return mode
    
    # Auto mode: map tier to action
    tier_actions = {
        1: "none",
        2: "validate",
        3: "optimize",
        4: "plan",
    }
    
    return tier_actions.get(tier, "optimize")


# =============================================================================
# Response Headers (AC-11.3)
# =============================================================================


def build_cms_response_headers(
    routed: bool,
    tier: int,
    token_count: int,
    token_limit: int,
) -> dict[str, str]:
    """
    Build CMS response headers.
    
    Headers:
        X-CMS-Routed: true | false
        X-CMS-Tier: 1 | 2 | 3 | 4
        X-Token-Count: <count>
        X-Token-Limit: <limit>
        X-Headroom-Pct: <percentage>
    
    Args:
        routed: Whether request was routed to CMS
        tier: Calculated tier
        token_count: Token count
        token_limit: Context limit
        
    Returns:
        Dict of header names to values
    """
    headroom_pct = 0
    if token_limit > 0:
        headroom_pct = int((token_limit - token_count) / token_limit * 100)
    
    return {
        "X-CMS-Routed": "true" if routed else "false",
        "X-CMS-Tier": str(tier),
        "X-Token-Count": str(token_count),
        "X-Token-Limit": str(token_limit),
        "X-Headroom-Pct": str(max(0, headroom_pct)),
    }


# =============================================================================
# CMS Availability (AC-11.4)
# =============================================================================


def cms_required_for_tier(tier: int) -> bool:
    """
    Check if CMS is required for this tier.
    
    CMS is required for Tier 3+ to ensure optimization/chunking.
    Tier 1-2 can proceed without CMS (graceful degradation).
    
    Args:
        tier: Calculated tier
        
    Returns:
        True if CMS is required
    """
    return tier >= 3


def handle_cms_unavailable(tier: int) -> None:
    """
    Handle CMS unavailability.
    
    Raises HTTPException 503 for Tier 3+ requests when CMS is unavailable.
    
    Args:
        tier: Calculated tier
        
    Raises:
        HTTPException: 503 if CMS required but unavailable
    """
    if cms_required_for_tier(tier):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "CMS unavailable",
                "message": f"Context Management Service is unavailable. Tier {tier} requests require CMS for optimization.",
                "tier": tier,
            },
        )


# =============================================================================
# Fast Token Estimation (AC-11.5)
# =============================================================================


def get_estimation_ratio(model: str) -> float:
    """
    Get character-to-token ratio for a model.
    
    Args:
        model: Model name
        
    Returns:
        Characters per token ratio
    """
    model_lower = model.lower()
    
    for prefix, ratio in ESTIMATION_RATIOS.items():
        if prefix in model_lower:
            return ratio
    
    return ESTIMATION_RATIOS["default"]


def estimate_tokens_fast(text: str, model: str) -> int:
    """
    Fast token estimation without loading tokenizer.
    
    Uses character-to-token ratio for quick estimation.
    Completes in <1ms for any text size.
    
    Args:
        text: Text to estimate
        model: Target model
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    ratio = get_estimation_ratio(model)
    return int(len(text) / ratio)


def estimate_tokens_from_messages(
    messages: list[dict],
    model: str,
) -> int:
    """
    Estimate tokens from chat messages.
    
    Includes overhead for message structure (~4 tokens per message).
    
    Args:
        messages: List of message dicts with role and content
        model: Target model
        
    Returns:
        Estimated token count
    """
    total_chars = 0
    message_overhead = 4  # ~4 tokens per message for role, separators
    
    for msg in messages:
        content = msg.get("content", "")
        if content:
            total_chars += len(content)
    
    base_estimate = estimate_tokens_fast("a" * total_chars, model) if total_chars else 0
    overhead = len(messages) * message_overhead
    
    return base_estimate + overhead


# =============================================================================
# Context Limit Lookup (AC-11.5)
# =============================================================================


def get_context_limit(model: str) -> int:
    """
    Get context limit for a model.
    
    Args:
        model: Model name
        
    Returns:
        Context limit in tokens
    """
    # Exact match
    if model in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[model]
    
    # Partial match (e.g., "gpt-4-turbo-preview" -> "gpt-4-turbo")
    model_lower = model.lower()
    for known_model, limit in MODEL_CONTEXT_LIMITS.items():
        if known_model in model_lower or model_lower in known_model:
            return limit
    
    return DEFAULT_CONTEXT_LIMIT
