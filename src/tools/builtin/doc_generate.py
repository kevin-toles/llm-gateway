"""
Documentation Generation Agent Tool - WBS 3.3.2.3

This module implements the generate_documentation tool that proxies documentation
generation requests to the ai-agents microservice.

Reference Documents:
- ai-agents/docs/ARCHITECTURE.md: POST /v1/agents/doc-generate endpoint
- GUIDELINES pp. 1489-1544: Agent tool execution patterns
- DEPLOYMENT_IMPLEMENTATION_PLAN.md: Lines 3200-3210 - WBS 3.3.2.3

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


class DocGenerateServiceError(Exception):
    """Raised when the ai-agents doc-generate service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS 3.3.2.3.6: Tool Definition
# =============================================================================


GENERATE_DOCUMENTATION_DEFINITION = ToolDefinition(
    name="generate_documentation",
    description="Generate documentation for source code. "
    "Returns formatted documentation including descriptions, parameters, and examples.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The source code to document.",
            },
            "format": {
                "type": "string",
                "description": "Output format for documentation (e.g., 'markdown', 'rst', 'docstring').",
                "default": "markdown",
            },
        },
        "required": ["code"],
    },
)


# =============================================================================
# WBS 3.3.2.3.2-3.3.2.3.5: generate_documentation Tool Function
# =============================================================================


async def _do_doc_generate(
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform the actual HTTP doc generation request.
    
    WBS 3.3.2.3.4: Call ai-agents /v1/agents/doc-generate/run endpoint.
    
    Anti-pattern §67 avoided: Uses context manager for connection management.
    """
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/v1/agents/doc-generate/run",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def generate_documentation(args: dict[str, Any]) -> dict[str, Any]:
    """
    Generate documentation for source code.

    WBS 3.3.2.3.2: Implement generate_documentation tool function.
    WBS 3.3.2.3.3: Accept code, format parameters.
    WBS 3.3.2.3.4: Call ai-agents /v1/agents/doc-generate/run endpoint.
    WBS 3.3.2.3.5: Return generated documentation.

    Args:
        args: Dictionary containing:
            - code (str): The source code to document.
            - format (str, optional): Output format (default: 'markdown').

    Returns:
        Dictionary containing documentation with:
            - documentation: Generated documentation string.
            - format: The format of the output.
            - sections: List of documentation sections generated.

    Raises:
        DocGenerateServiceError: If the ai-agents service is unavailable.
    """
    settings = get_settings()
    base_url = settings.ai_agents_url
    timeout_seconds = 60.0  # Doc generation may take longer

    # Extract parameters with defaults
    code = args.get("code", "")
    doc_format = args.get("format", "markdown")

    # Build request payload
    payload = {
        "code": code,
        "format": doc_format,
    }

    logger.debug(f"Generating documentation: format={doc_format}, length={len(code)}")

    try:
        result = await _do_doc_generate(base_url, payload, timeout_seconds)
        logger.debug("Documentation generation complete")
        return result

    except httpx.ConnectError as e:
        # Anti-pattern §3.1: Log with context, don't use bare except
        logger.warning(f"AI agents connection failed: {e}")
        return {
            "error": "AI agents service unavailable",
            "documentation": "",
            "format": doc_format,
            "sections": [],
        }
    except httpx.TimeoutException as e:
        logger.warning(f"AI agents timeout: {e}")
        return {
            "error": "AI agents service timeout",
            "documentation": "",
            "format": doc_format,
            "sections": [],
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"AI agents HTTP error: {e.response.status_code}")
        return {
            "error": f"AI agents returned error: {e.response.status_code}",
            "documentation": "",
            "format": doc_format,
            "sections": [],
        }
    except Exception as e:
        # Anti-pattern §3.1: Catch specific, log context
        logger.error(f"Doc generation error: {type(e).__name__}: {e}")
        return {
            "error": str(e),
            "documentation": "",
            "format": doc_format,
            "sections": [],
        }
