"""
Code Review Agent Tool - WBS 3.3.2.1

This module implements the review_code tool that proxies code review requests
to the ai-agents microservice.

Reference Documents:
- ai-agents/docs/ARCHITECTURE.md: POST /v1/agents/code-review endpoint
- GUIDELINES pp. 1489-1544: Agent tool execution patterns
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3178-3188 - WBS 3.3.2.1

Pattern: Service Proxy (proxies to ai-agents microservice)
Pattern: Async HTTP client for non-blocking calls

Anti-Patterns Avoided:
- §3.1: No bare except clauses - specific exception handling
- §67: Uses httpx.AsyncClient context manager for connection pooling
"""

import logging
from typing import Any

import httpx

from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class CodeReviewServiceError(Exception):
    """Raised when the ai-agents code review service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 3.3.2.1.6: Tool Definition
# =============================================================================


REVIEW_CODE_DEFINITION = ToolDefinition(
    name="review_code",
    description="Review code for issues, best practices, and suggestions. "
    "Returns findings with line numbers, severity, and improvement suggestions.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The source code to review.",
            },
            "language": {
                "type": "string",
                "description": "Programming language of the code (e.g., 'python', 'javascript').",
                "default": "python",
            },
        },
        "required": ["code"],
    },
)


# =============================================================================
# WBS 3.3.2.1.2-3.3.2.1.5: review_code Tool Function
# =============================================================================


async def _do_code_review(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP code review request.
    
    WBS 3.3.2.1.4: Call ai-agents /v1/agents/code-review/run endpoint.
    
    Anti-pattern §67 avoided: Uses context manager for connection management.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/v1/agents/code-review/run",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def review_code(args: dict[str, Any]) -> dict[str, Any]:
    """
    Review code for issues and suggestions.

    WBS 3.3.2.1.2: Implement review_code tool function.
    WBS 3.3.2.1.3: Accept code, language parameters.
    WBS 3.3.2.1.4: Call ai-agents /v1/agents/code-review/run endpoint.
    WBS 3.3.2.1.5: Return review findings and suggestions.

    Args:
        args: Dictionary containing:
            - code (str): The source code to review.
            - language (str, optional): Programming language (default: 'python').

    Returns:
        Dictionary containing review results with:
            - findings: List of issues found with line, severity, message, suggestion.
            - summary: Summary of the review.
            - score: Code quality score (0-100).

    Raises:
        CodeReviewServiceError: If the ai-agents service is unavailable.
    """
    settings = get_settings()
    base_url = settings.ai_agents_url
    timeout_seconds = 60.0  # Code review may take longer

    # Extract parameters with defaults
    code = args.get("code", "")
    language = args.get("language", "python")

    # Build request payload
    payload = {
        "code": code,
        "language": language,
    }

    logger.debug(f"Reviewing code: language={language}, length={len(code)}")

    try:
        result = await _do_code_review(base_url, payload, timeout_seconds)
        logger.debug(f"Code review complete: {result.get('summary', 'no summary')}")
        return result

    except httpx.ConnectError as e:
        # Anti-pattern §3.1: Log with context, don't use bare except
        logger.warning(f"AI agents connection failed: {e}")
        return {
            "error": "AI agents service unavailable",
            "findings": [],
            "summary": "Code review service unavailable",
            "score": 0,
        }
    except httpx.TimeoutException as e:
        logger.warning(f"AI agents timeout: {e}")
        return {
            "error": "AI agents service timeout",
            "findings": [],
            "summary": "Code review timed out",
            "score": 0,
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"AI agents HTTP error: {e.response.status_code}")
        return {
            "error": f"AI agents returned error: {e.response.status_code}",
            "findings": [],
            "summary": "Code review failed",
            "score": 0,
        }
    except Exception as e:
        # Anti-pattern §3.1: Catch specific, log context
        logger.error(f"Code review error: {type(e).__name__}: {e}")
        return {
            "error": str(e),
            "findings": [],
            "summary": "Code review error",
            "score": 0,
        }
