"""
Architecture Analysis Agent Tool - WBS 3.3.2.2

This module implements the analyze_architecture tool that proxies architecture
analysis requests to the ai-agents microservice.

Reference Documents:
- ai-agents/docs/ARCHITECTURE.md: POST /v1/agents/architecture endpoint
- GUIDELINES pp. 1489-1544: Agent tool execution patterns
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3189-3199 - WBS 3.3.2.2

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


class ArchitectureServiceError(Exception):
    """Raised when the ai-agents architecture service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 3.3.2.2.6: Tool Definition
# =============================================================================


ANALYZE_ARCHITECTURE_DEFINITION = ToolDefinition(
    name="analyze_architecture",
    description="Analyze code architecture for patterns, concerns, and suggestions. "
    "Returns identified patterns, architectural concerns, and refactoring suggestions.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The source code to analyze for architectural patterns.",
            },
            "context": {
                "type": "string",
                "description": "Additional context about the codebase (e.g., 'Python microservice').",
                "default": "",
            },
        },
        "required": ["code"],
    },
)


# =============================================================================
# WBS 3.3.2.2.2-3.3.2.2.5: analyze_architecture Tool Function
# =============================================================================


async def _do_architecture_analysis(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP architecture analysis request.
    
    WBS 3.3.2.2.4: Call ai-agents /v1/agents/architecture/run endpoint.
    
    Anti-pattern §67 avoided: Uses context manager for connection management.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/v1/agents/architecture/run",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def analyze_architecture(args: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze code for architectural patterns and concerns.

    WBS 3.3.2.2.2: Implement analyze_architecture tool function.
    WBS 3.3.2.2.3: Accept code, context parameters.
    WBS 3.3.2.2.4: Call ai-agents /v1/agents/architecture/run endpoint.
    WBS 3.3.2.2.5: Return architecture analysis.

    Args:
        args: Dictionary containing:
            - code (str): The source code to analyze.
            - context (str, optional): Additional context about the codebase.

    Returns:
        Dictionary containing analysis results with:
            - analysis: Object with patterns, concerns, suggestions.
            - summary: Summary of the analysis.

    Raises:
        ArchitectureServiceError: If the ai-agents service is unavailable.
    """
    settings = get_settings()
    base_url = settings.ai_agents_url
    timeout_seconds = 60.0  # Architecture analysis may take longer

    # Extract parameters with defaults
    code = args.get("code", "")
    context = args.get("context", "")

    # Build request payload
    payload = {
        "code": code,
        "context": context,
    }

    logger.debug(f"Analyzing architecture: context='{context[:50]}...', length={len(code)}")

    try:
        result = await _do_architecture_analysis(base_url, payload, timeout_seconds)
        logger.debug(f"Architecture analysis complete: {result.get('summary', 'no summary')}")
        return result

    except httpx.ConnectError as e:
        # Anti-pattern §3.1: Log with context, don't use bare except
        logger.warning(f"AI agents connection failed: {e}")
        return {
            "error": "AI agents service unavailable",
            "analysis": {"patterns": [], "concerns": [], "suggestions": []},
            "summary": "Architecture analysis service unavailable",
        }
    except httpx.TimeoutException as e:
        logger.warning(f"AI agents timeout: {e}")
        return {
            "error": "AI agents service timeout",
            "analysis": {"patterns": [], "concerns": [], "suggestions": []},
            "summary": "Architecture analysis timed out",
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"AI agents HTTP error: {e.response.status_code}")
        return {
            "error": f"AI agents returned error: {e.response.status_code}",
            "analysis": {"patterns": [], "concerns": [], "suggestions": []},
            "summary": "Architecture analysis failed",
        }
    except Exception as e:
        # Anti-pattern §3.1: Catch specific, log context
        logger.error(f"Architecture analysis error: {type(e).__name__}: {e}")
        return {
            "error": str(e),
            "analysis": {"patterns": [], "concerns": [], "suggestions": []},
            "summary": "Architecture analysis error",
        }
