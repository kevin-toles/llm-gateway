"""
Cross-Reference Tool - WBS 2.4.3.2 Cross-Reference Tool

This module implements the cross_reference tool that proxies requests
to the ai-agents service's Cross-Reference Agent.

Reference Documents:
- ARCHITECTURE.md Line 82: ai_agents_url "http://localhost:8082"
- ai-agents ARCHITECTURE.md: Cross-Reference Agent workflow
- TIER_RELATIONSHIP_DIAGRAM.md: Spider Web Model taxonomy relationships
- GUIDELINES pp. 2309: Circuit breaker pattern (Newman pp. 357-358)
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns avoided

Pattern: Service Proxy (proxies to ai-agents microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience (Newman pp. 357-358)

Anti-Patterns Avoided (per CODING_PATTERNS_ANALYSIS.md):
- S3457: No empty f-strings - use regular strings for static messages
- S7503: Async only for functions with await
- S1066: No nested if statements - merge with and
- S6546: Use PEP 604 union syntax (X | Y)
- Anti-Pattern 1.1: Use T | None for optional types
"""

import logging
from typing import Any

import httpx

from src.clients.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# WBS 3.2.3.1: Shared Circuit Breaker for AI Agents Service
# Pattern: Singleton circuit breaker per downstream service
# =============================================================================

_ai_agents_circuit_breaker: CircuitBreaker | None = None


def get_ai_agents_circuit_breaker() -> CircuitBreaker:
    """
    Get the shared circuit breaker for ai-agents service.
    
    WBS 3.2.3.1.5: Shared circuit breaker for all ai-agents operations.
    
    Returns:
        CircuitBreaker instance configured from settings.
    """
    global _ai_agents_circuit_breaker
    if _ai_agents_circuit_breaker is None:
        settings = get_settings()
        _ai_agents_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
            name="ai-agents-service",
        )
    return _ai_agents_circuit_breaker


# =============================================================================
# WBS 2.4.3.2.2: Exceptions
# =============================================================================


class CrossReferenceServiceError(Exception):
    """Raised when the ai-agents service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 2.4.3.2: Tool Definition
# Per ai-agents CrossReferenceRequest schema
# =============================================================================


CROSS_REFERENCE_DEFINITION = ToolDefinition(
    name="cross_reference",
    description=(
        "Generate cross-references for a source chapter using the Cross-Reference Agent. "
        "This tool finds related content across the document corpus by traversing the "
        "taxonomy graph (Spider Web Model) and generates scholarly annotations with "
        "Chicago-style citations. Use this for enriching documents with cross-references "
        "to related Architecture (Tier 1), Implementation (Tier 2), and Practices (Tier 3) content."
    ),
    parameters={
        "type": "object",
        "properties": {
            "book": {
                "type": "string",
                "description": "Source book title (e.g., 'Architecture Patterns with Python').",
            },
            "chapter": {
                "type": "integer",
                "description": "Chapter number (1-indexed).",
            },
            "title": {
                "type": "string",
                "description": "Chapter title.",
            },
            "tier": {
                "type": "integer",
                "description": "Tier level: 1=Architecture, 2=Implementation, 3=Practices.",
                "enum": [1, 2, 3],
            },
            "content": {
                "type": "string",
                "description": "Chapter content text (optional, can be retrieved by agent).",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extracted keywords from the chapter.",
                "default": [],
            },
            "concepts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key concepts from the chapter.",
                "default": [],
            },
            "max_hops": {
                "type": "integer",
                "description": "Maximum traversal depth in the taxonomy graph (default: 3).",
                "default": 3,
            },
            "min_similarity": {
                "type": "number",
                "description": "Minimum similarity threshold for matches (default: 0.7).",
                "default": 0.7,
            },
            "include_tier1": {
                "type": "boolean",
                "description": "Include Tier 1 (Architecture Spine) results (default: true).",
                "default": True,
            },
            "include_tier2": {
                "type": "boolean",
                "description": "Include Tier 2 (Implementation) results (default: true).",
                "default": True,
            },
            "include_tier3": {
                "type": "boolean",
                "description": "Include Tier 3 (Engineering Practices) results (default: true).",
                "default": True,
            },
            "taxonomy_id": {
                "type": "string",
                "description": "Taxonomy identifier (default: 'ai-ml').",
                "default": "ai-ml",
            },
        },
        "required": ["book", "chapter", "title", "tier"],
    },
)


# =============================================================================
# WBS 2.4.3.2.5: HTTP Request Function
# Separated for circuit breaker wrapping
# =============================================================================


async def _do_cross_reference(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP cross-reference request.
    
    Separated for circuit breaker wrapping.
    
    Args:
        base_url: The ai-agents service base URL.
        payload: The request payload matching CrossReferenceRequest schema.
        timeout_seconds: Timeout for the HTTP request.
        
    Returns:
        Response JSON as dictionary.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/v1/agents/cross-reference",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# WBS 2.4.3.2.3: cross_reference Tool Function
# WBS 3.2.3: Integrated with circuit breaker and configurable timeout
# =============================================================================


async def cross_reference(args: dict[str, Any]) -> dict[str, Any]:
    """
    Generate cross-references for a source chapter.

    WBS 2.4.3.2.3: Implement cross_reference tool function.
    WBS 2.4.3.2.4: Accept source chapter and config parameters.
    WBS 2.4.3.2.5: Call ai-agents /v1/agents/cross-reference endpoint.
    WBS 2.4.3.2.6: Return cross-reference results as structured data.
    WBS 2.4.3.2.7: Handle service unavailable errors.
    WBS 3.2.3.1: Circuit breaker integration for resilience.

    Args:
        args: Dictionary containing:
            - book (str): Source book title.
            - chapter (int): Chapter number.
            - title (str): Chapter title.
            - tier (int): Tier level (1, 2, or 3).
            - content (str, optional): Chapter content.
            - keywords (list[str], optional): Extracted keywords.
            - concepts (list[str], optional): Key concepts.
            - max_hops (int, optional): Max traversal depth (default: 3).
            - min_similarity (float, optional): Min similarity threshold (default: 0.7).
            - include_tier1 (bool, optional): Include Tier 1 results (default: True).
            - include_tier2 (bool, optional): Include Tier 2 results (default: True).
            - include_tier3 (bool, optional): Include Tier 3 results (default: True).
            - taxonomy_id (str, optional): Taxonomy identifier (default: 'ai-ml').

    Returns:
        Dictionary containing cross-reference results with:
            - annotation: Scholarly annotation with inline citations.
            - citations: List of Chicago-style citations.
            - tier_coverage: Coverage statistics per tier.
            - processing_time_ms: Processing time in milliseconds.
            - model_used: LLM model used for synthesis.

    Raises:
        CrossReferenceServiceError: If the ai-agents service is unavailable.
    """
    settings = get_settings()
    base_url = settings.ai_agents_url
    timeout_seconds = settings.semantic_search_timeout_seconds
    circuit_breaker = get_ai_agents_circuit_breaker()

    # Extract required parameters
    book = args.get("book", "")
    chapter = args.get("chapter", 1)
    title = args.get("title", "")
    tier = args.get("tier", 1)

    # Extract optional parameters with defaults
    content = args.get("content")
    keywords = args.get("keywords", [])
    concepts = args.get("concepts", [])
    max_hops = args.get("max_hops", 3)
    min_similarity = args.get("min_similarity", 0.7)
    include_tier1 = args.get("include_tier1", True)
    include_tier2 = args.get("include_tier2", True)
    include_tier3 = args.get("include_tier3", True)
    taxonomy_id = args.get("taxonomy_id", "ai-ml")

    # Build request payload per ai-agents CrossReferenceRequest schema
    payload = {
        "source": {
            "book": book,
            "chapter": chapter,
            "title": title,
            "tier": tier,
            "content": content,
            "keywords": keywords,
            "concepts": concepts,
        },
        "config": {
            "max_hops": max_hops,
            "min_similarity": min_similarity,
            "include_tier1": include_tier1,
            "include_tier2": include_tier2,
            "include_tier3": include_tier3,
        },
        "taxonomy_id": taxonomy_id,
    }

    # NOTE: Using regular strings for logging to avoid S3457 (empty f-strings)
    logger.info(
        "Cross-referencing: book='%s', chapter=%d, title='%s'",
        book,
        chapter,
        title[:50] if title else "",
    )
    logger.debug("Cross-reference payload: %s", payload)

    try:
        # WBS 3.2.3.1: Use circuit breaker for resilience
        result = await circuit_breaker.call(
            _do_cross_reference,
            base_url,
            payload,
            timeout_seconds,
        )
        
        logger.info(
            "Cross-reference complete: %d citations, %.0fms",
            len(result.get("citations", [])),
            result.get("processing_time_ms", 0),
        )
        return result

    except CircuitOpenError as e:
        logger.warning("Circuit breaker open for ai-agents service: %s", e)
        # NOTE: Regular string - no f-string needed (S3457)
        raise CrossReferenceServiceError(
            "AI agents service circuit open - failing fast"
        ) from e

    except httpx.TimeoutException as e:
        logger.error("AI agents service timeout after %ss: %s", timeout_seconds, e)
        raise CrossReferenceServiceError(
            f"AI agents service timeout after {timeout_seconds} seconds"
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error("AI agents service HTTP error: %s", e.response.status_code)
        # Try to extract error detail from response
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            error_detail = str(e)
        raise CrossReferenceServiceError(
            f"AI agents service error: HTTP {e.response.status_code} - {error_detail}"
        ) from e

    except httpx.RequestError as e:
        logger.error("AI agents service connection error: %s", e)
        raise CrossReferenceServiceError(
            f"AI agents service unavailable: {e}"
        ) from e

    except Exception as e:
        logger.error("AI agents service unexpected error: %s", e)
        raise CrossReferenceServiceError(
            f"AI agents service error: {e}"
        ) from e
