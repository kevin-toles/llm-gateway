"""
Code-Orchestrator Tools - WBS-CPA2 Gateway → Code-Orchestrator Tool Exposure

This module implements tools that proxy to Code-Orchestrator-Service endpoints
for external clients (MCP, external LLMs, llm-document-enhancer).

Reference Documents:
- CONSOLIDATED_PLATFORM_ARCHITECTURE_WBS.md: WBS-CPA2 Gateway → Code-Orchestrator Tool Exposure
- Code-Orchestrator-Service/src/api/similarity.py: /v1/similarity, /v1/embeddings endpoints
- Code-Orchestrator-Service/src/api/keywords.py: /v1/keywords endpoint
- CODING_PATTERNS_ANALYSIS.md: Anti-patterns to avoid

Pattern: Service Proxy (proxies to external microservice)
Pattern: Async HTTP client for non-blocking calls
Pattern: Circuit Breaker for resilience

Communication Pattern:
- INTERNAL (platform services): Direct API calls (:8083)
- EXTERNAL (MCP, external LLMs): Gateway (:8080) -> these tools
"""

import logging
from typing import Any, Optional

import httpx

from src.clients.circuit_breaker import CircuitBreaker, CircuitOpenError
from src.core.config import get_settings
from src.models.domain import ToolDefinition

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (AP-1 compliance: tool names as constants)
# =============================================================================

TOOL_NAME_SIMILARITY = "compute_similarity"
TOOL_NAME_KEYWORDS = "extract_keywords"
TOOL_NAME_EMBEDDINGS = "generate_embeddings"

ENDPOINT_SIMILARITY = "/v1/similarity"
ENDPOINT_KEYWORDS = "/v1/keywords"
ENDPOINT_EMBEDDINGS = "/v1/embeddings"


# =============================================================================
# Circuit Breaker for Code-Orchestrator Service
# Pattern: Singleton circuit breaker per downstream service
# =============================================================================

_code_orchestrator_circuit_breaker: Optional[CircuitBreaker] = None


def get_code_orchestrator_circuit_breaker() -> CircuitBreaker:
    """
    Get the shared circuit breaker for Code-Orchestrator-Service.
    
    WBS-CPA2: Shared circuit breaker for all Code-Orchestrator operations.
    
    Returns:
        CircuitBreaker instance configured from settings.
    """
    global _code_orchestrator_circuit_breaker
    if _code_orchestrator_circuit_breaker is None:
        settings = get_settings()
        _code_orchestrator_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
            name="code-orchestrator-service",
        )
    return _code_orchestrator_circuit_breaker


# =============================================================================
# Exceptions (AP-5 compliance: {Service}Error prefix)
# =============================================================================


class CodeOrchestratorServiceError(Exception):
    """Raised when the Code-Orchestrator service is unavailable or returns an error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# =============================================================================
# WBS-CPA2.2: Compute Similarity Tool Definition
# =============================================================================


COMPUTE_SIMILARITY_DEFINITION = ToolDefinition(
    name=TOOL_NAME_SIMILARITY,
    description="Compute cosine similarity between two texts using SBERT embeddings. "
    "Returns a score from -1 (opposite) to 1 (identical). "
    "Use this to measure semantic similarity between documents or passages.",
    parameters={
        "type": "object",
        "properties": {
            "text1": {
                "type": "string",
                "description": "First text to compare.",
            },
            "text2": {
                "type": "string",
                "description": "Second text to compare.",
            },
        },
        "required": ["text1", "text2"],
    },
)


# =============================================================================
# WBS-CPA2.3: Extract Keywords Tool Definition
# =============================================================================


EXTRACT_KEYWORDS_DEFINITION = ToolDefinition(
    name=TOOL_NAME_KEYWORDS,
    description="Extract top keywords from a corpus of documents using TF-IDF. "
    "Returns the most important terms for each document based on term frequency "
    "and inverse document frequency scores.",
    parameters={
        "type": "object",
        "properties": {
            "corpus": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of document strings to extract keywords from.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top keywords to return per document (default: 10).",
                "default": 10,
            },
        },
        "required": ["corpus"],
    },
)


# =============================================================================
# WBS-CPA2.4: Generate Embeddings Tool Definition
# =============================================================================


GENERATE_EMBEDDINGS_DEFINITION = ToolDefinition(
    name=TOOL_NAME_EMBEDDINGS,
    description="Generate embedding vectors for a batch of texts using SBERT. "
    "Returns dense vectors suitable for semantic similarity calculations, "
    "clustering, or vector database storage.",
    parameters={
        "type": "object",
        "properties": {
            "texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of texts to generate embeddings for.",
            },
        },
        "required": ["texts"],
    },
)


# =============================================================================
# Internal HTTP Request Function
# =============================================================================


async def _do_code_orchestrator_request(
    endpoint: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Internal function to perform HTTP request to Code-Orchestrator-Service.
    
    Separated for circuit breaker wrapping.
    
    Args:
        endpoint: API endpoint path (e.g., /v1/similarity).
        payload: Request payload.
        timeout_seconds: Request timeout.
        
    Returns:
        Response JSON.
    """
    settings = get_settings()
    base_url = settings.code_orchestrator_url
    
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}{endpoint}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# Error Handler (reduces duplication across tool functions)
# =============================================================================


def _handle_code_orchestrator_error(
    error: Exception,
    operation: str,
    timeout_seconds: float,
) -> None:
    """
    Handle errors from Code-Orchestrator-Service calls.
    
    Args:
        error: The exception that was raised.
        operation: Name of the operation for error messages.
        timeout_seconds: Timeout value for timeout error messages.
        
    Raises:
        CodeOrchestratorServiceError: Always raises with appropriate message.
    """
    if isinstance(error, CircuitOpenError):
        logger.warning(f"Circuit breaker open for Code-Orchestrator {operation}: {error}")
        raise CodeOrchestratorServiceError(
            f"Code-Orchestrator {operation} circuit open - failing fast"
        ) from error
    
    if isinstance(error, httpx.TimeoutException):
        logger.error(f"Code-Orchestrator {operation} timeout after {timeout_seconds}s: {error}")
        raise CodeOrchestratorServiceError(
            f"Code-Orchestrator {operation} timeout after {timeout_seconds} seconds"
        ) from error
    
    if isinstance(error, httpx.HTTPStatusError):
        logger.error(f"Code-Orchestrator {operation} HTTP error: {error.response.status_code}")
        raise CodeOrchestratorServiceError(
            f"Code-Orchestrator {operation} error: HTTP {error.response.status_code}"
        ) from error
    
    if isinstance(error, httpx.RequestError):
        logger.error(f"Code-Orchestrator {operation} connection error: {error}")
        raise CodeOrchestratorServiceError(
            f"Code-Orchestrator {operation} service unavailable: {error}"
        ) from error
    
    logger.error(f"Code-Orchestrator {operation} unexpected error: {error}")
    raise CodeOrchestratorServiceError(
        f"Code-Orchestrator {operation} error: {error}"
    ) from error


# =============================================================================
# WBS-CPA2.2: Compute Similarity Tool Function
# =============================================================================


async def compute_similarity(args: dict[str, Any]) -> dict[str, Any]:
    """
    Compute cosine similarity between two texts using SBERT embeddings.

    WBS-CPA2.2: Implement compute_similarity tool.
    
    This tool proxies requests from external clients (MCP, external LLMs) through
    the Gateway to the Code-Orchestrator-Service. Internal platform services call
    Code-Orchestrator-Service directly.

    Args:
        args: Dictionary containing:
            - text1 (str): First text to compare.
            - text2 (str): Second text to compare.

    Returns:
        Dictionary containing:
            - score (float): Cosine similarity score (-1 to 1).
            - model (str): Model name used for computation.
            - processing_time_ms (float): Processing time in milliseconds.

    Raises:
        CodeOrchestratorServiceError: If the service is unavailable.
    """
    settings = get_settings()
    timeout_seconds = settings.code_orchestrator_timeout_seconds
    circuit_breaker = get_code_orchestrator_circuit_breaker()

    # Extract parameters
    text1 = args.get("text1", "")
    text2 = args.get("text2", "")

    # Build request payload - matches SimilarityRequest schema
    payload = {
        "text1": text1,
        "text2": text2,
    }

    logger.debug(f"Computing similarity: text1='{text1[:30]}...', text2='{text2[:30]}...'")

    try:
        result = await circuit_breaker.call(
            _do_code_orchestrator_request,
            ENDPOINT_SIMILARITY,
            payload,
            timeout_seconds,
        )
        return result
    except Exception as e:
        _handle_code_orchestrator_error(e, "similarity", timeout_seconds)
        raise  # Should not reach here, but satisfies type checker


# =============================================================================
# WBS-CPA2.3: Extract Keywords Tool Function
# =============================================================================


async def extract_keywords(args: dict[str, Any]) -> dict[str, Any]:
    """
    Extract top keywords from a corpus of documents using TF-IDF.

    WBS-CPA2.3: Implement extract_keywords tool.
    
    This tool proxies requests from external clients (MCP, external LLMs) through
    the Gateway to the Code-Orchestrator-Service.

    Args:
        args: Dictionary containing:
            - corpus (list[str]): List of document strings.
            - top_k (int, optional): Number of top keywords per document (default: 10).

    Returns:
        Dictionary containing:
            - keywords (list[list[str]]): List of keyword lists, one per document.
            - processing_time_ms (float): Processing time in milliseconds.

    Raises:
        CodeOrchestratorServiceError: If the service is unavailable.
    """
    settings = get_settings()
    timeout_seconds = settings.code_orchestrator_timeout_seconds
    circuit_breaker = get_code_orchestrator_circuit_breaker()

    # Extract parameters with defaults
    corpus = args.get("corpus", [])
    top_k = args.get("top_k", 10)

    # Build request payload - matches KeywordsRequest schema
    payload = {
        "corpus": corpus,
        "top_k": top_k,
    }

    logger.debug(f"Extracting keywords: corpus_size={len(corpus)}, top_k={top_k}")

    try:
        result = await circuit_breaker.call(
            _do_code_orchestrator_request,
            ENDPOINT_KEYWORDS,
            payload,
            timeout_seconds,
        )
        return result
    except Exception as e:
        _handle_code_orchestrator_error(e, "keywords", timeout_seconds)
        raise


# =============================================================================
# WBS-CPA2.4: Generate Embeddings Tool Function
# =============================================================================


async def generate_embeddings(args: dict[str, Any]) -> dict[str, Any]:
    """
    Generate embedding vectors for a batch of texts using SBERT.

    WBS-CPA2.4: Implement generate_embeddings tool.
    
    This tool proxies requests from external clients (MCP, external LLMs) through
    the Gateway to the Code-Orchestrator-Service.

    Args:
        args: Dictionary containing:
            - texts (list[str]): List of texts to generate embeddings for.

    Returns:
        Dictionary containing:
            - embeddings (list[list[float]]): List of embedding vectors.
            - model (str): Model name used for computation.
            - processing_time_ms (float): Processing time in milliseconds.

    Raises:
        CodeOrchestratorServiceError: If the service is unavailable.
    """
    settings = get_settings()
    timeout_seconds = settings.code_orchestrator_timeout_seconds
    circuit_breaker = get_code_orchestrator_circuit_breaker()

    # Extract parameters
    texts = args.get("texts", [])

    # Build request payload - matches EmbeddingsRequest schema
    payload = {
        "texts": texts,
    }

    logger.debug(f"Generating embeddings: num_texts={len(texts)}")

    try:
        result = await circuit_breaker.call(
            _do_code_orchestrator_request,
            ENDPOINT_EMBEDDINGS,
            payload,
            timeout_seconds,
        )
        return result
    except Exception as e:
        _handle_code_orchestrator_error(e, "embeddings", timeout_seconds)
        raise
