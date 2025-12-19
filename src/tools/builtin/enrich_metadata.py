"""
Enrich Metadata Tool - Gateway proxy to ai-agents MSEP endpoint

This module implements the enrich_metadata tool that proxies requests
to the ai-agents POST /v1/agents/enrich-metadata endpoint.

Reference Documents:
- ARCHITECTURE.md: Gateway is single entry point for all external calls
- ai-agents/src/api/routes/enrich_metadata.py: MSEP endpoint schema
- GUIDELINES pp. 1545: Tool inventory as service registry pattern
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns avoided

Pattern: Gateway Tool Proxy (following cross_reference.py pattern)
Kitchen Brigade: Gateway (MANAGER) routes to ai-agents (EXPEDITOR)

Anti-Patterns Avoided:
- S3776: Cognitive complexity < 15 per function
- #42/#43: Proper async/await patterns
- #7: Exception naming follows *Error suffix pattern
"""

from __future__ import annotations

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
    
    Pattern: Singleton per downstream service
    Reference: GUIDELINES pp. 2309 - Circuit breaker (Newman pp. 357-358)
    
    Returns:
        CircuitBreaker: Shared circuit breaker instance
    """
    global _ai_agents_circuit_breaker
    if _ai_agents_circuit_breaker is None:
        settings = get_settings()
        _ai_agents_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
            half_open_requests=settings.circuit_breaker_half_open_requests,
        )
    return _ai_agents_circuit_breaker


# =============================================================================
# Custom Exception - Gateway pattern
# =============================================================================


class EnrichMetadataServiceError(Exception):
    """Raised when the ai-agents enrich-metadata service is unavailable.

    Pattern: Domain-specific exception (CODING_PATTERNS §7/§13)
    Anti-Pattern #7: Named *ServiceError, not generic
    """

    pass


# =============================================================================
# Tool Definition - WBS Pattern from cross_reference.py
# =============================================================================

ENRICH_METADATA_DEFINITION = ToolDefinition(
    name="enrich_metadata",
    description=(
        "Enrich book chapter metadata using MSEP (Multi-Stage Enrichment Pipeline). "
        "Extracts keywords, identifies topics, and generates cross-references between "
        "chapters using semantic similarity. Returns enriched metadata with provenance "
        "tracking for each decision."
    ),
    parameters={
        "type": "object",
        "properties": {
            "corpus": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of document texts (one per chapter) to enrich.",
            },
            "chapter_index": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "book": {
                            "type": "string",
                            "description": "Book title.",
                        },
                        "chapter": {
                            "type": "integer",
                            "description": "Chapter number (1-indexed).",
                        },
                        "title": {
                            "type": "string",
                            "description": "Chapter title.",
                        },
                        "id": {
                            "type": "string",
                            "description": "Optional chapter identifier.",
                        },
                    },
                    "required": ["book", "chapter", "title"],
                },
                "description": "Metadata for each chapter corresponding to corpus entries.",
            },
            "config": {
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Similarity threshold (0.0-1.0). Default: 0.45",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Max cross-references per chapter. Default: 5",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Service timeout in seconds. Default: 30.0",
                    },
                    "same_topic_boost": {
                        "type": "number",
                        "description": "Boost for same-topic chapters. Default: 0.15",
                    },
                    "use_dynamic_threshold": {
                        "type": "boolean",
                        "description": "Enable dynamic threshold adjustment. Default: True",
                    },
                    "enable_hybrid_search": {
                        "type": "boolean",
                        "description": "Enable hybrid search. Default: True",
                    },
                },
                "description": "Optional MSEP configuration parameters.",
            },
        },
        "required": ["corpus", "chapter_index"],
    },
)


# =============================================================================
# Internal HTTP Call - Circuit breaker integration
# =============================================================================


async def _do_enrich_metadata(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Execute the HTTP call to ai-agents enrich-metadata endpoint.

    Pattern: Isolated async function for circuit breaker wrapping

    Args:
        base_url: ai-agents service base URL
        payload: EnrichMetadataRequest payload
        timeout_seconds: Request timeout

    Returns:
        EnrichMetadataResponse as dict
    """
    url = f"{base_url}/v1/agents/enrich-metadata"

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


# =============================================================================
# enrich_metadata Tool Function
# =============================================================================


async def enrich_metadata(args: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich chapter metadata via ai-agents MSEP endpoint.

    Gateway Pattern: Routes external calls through Gateway to ai-agents.
    Kitchen Brigade: Gateway (MANAGER) delegates to ai-agents (EXPEDITOR).

    Args:
        args: Dictionary containing:
            - corpus (list[str]): Document texts to enrich
            - chapter_index (list[dict]): Chapter metadata (book, chapter, title)
            - config (dict, optional): MSEP configuration parameters

    Returns:
        Dictionary containing:
            - chapters: List of enriched chapter metadata
            - processing_time_ms: Time taken to process
            - total_cross_references: Total cross-references found

    Raises:
        EnrichMetadataServiceError: If ai-agents service is unavailable
    """
    settings = get_settings()
    base_url = settings.ai_agents_url
    timeout_seconds = settings.semantic_search_timeout_seconds
    circuit_breaker = get_ai_agents_circuit_breaker()

    # Extract parameters from args
    corpus = args.get("corpus", [])
    chapter_index = args.get("chapter_index", [])
    config = args.get("config")

    # Build request payload per ai-agents EnrichMetadataRequest schema
    payload: dict[str, Any] = {
        "corpus": corpus,
        "chapter_index": chapter_index,
    }
    if config is not None:
        payload["config"] = config

    # Logging with safe string formatting (S3457 compliant)
    num_chapters = len(chapter_index)
    logger.info(
        "Enriching metadata: %d chapters, corpus size: %d",
        num_chapters,
        len(corpus),
    )
    logger.debug("Enrich metadata payload keys: %s", list(payload.keys()))

    try:
        # Circuit breaker for resilience
        result = await circuit_breaker.call(
            _do_enrich_metadata,
            base_url,
            payload,
            timeout_seconds,
        )

        logger.info(
            "Enrich metadata complete: %d chapters, %d total cross-refs, %.0fms",
            len(result.get("chapters", [])),
            result.get("total_cross_references", 0),
            result.get("processing_time_ms", 0),
        )
        return result

    except CircuitOpenError as e:
        logger.warning("Circuit breaker open for ai-agents MSEP service: %s", e)
        raise EnrichMetadataServiceError(
            "AI agents MSEP service circuit open - failing fast"
        ) from e

    except httpx.TimeoutException as e:
        logger.error("AI agents MSEP timeout after %ss: %s", timeout_seconds, e)
        raise EnrichMetadataServiceError(
            f"AI agents MSEP timeout after {timeout_seconds} seconds"
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error("AI agents MSEP HTTP error: %s", e.response.status_code)
        # Extract error detail from response
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            error_detail = str(e)
        raise EnrichMetadataServiceError(
            f"AI agents MSEP error: HTTP {e.response.status_code} - {error_detail}"
        ) from e

    except httpx.RequestError as e:
        logger.error("AI agents MSEP connection error: %s", e)
        raise EnrichMetadataServiceError(
            f"AI agents MSEP service unavailable: {e}"
        ) from e

    except Exception as e:
        logger.error("AI agents MSEP unexpected error: %s", e)
        raise EnrichMetadataServiceError(
            f"AI agents MSEP service error: {e}"
        ) from e
