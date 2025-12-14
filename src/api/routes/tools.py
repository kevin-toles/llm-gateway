"""
Tools Router - WBS 2.2.4 Tools Endpoints

This module implements the tools execution API for agent tool invocation.

Reference Documents:
- GUIDELINES pp. 1489-1544: Agent tool execution patterns, tool inventories
- Percival & Gregory (Architecture Patterns) pp. 59-60: Domain model, encapsulation
- Sinha (FastAPI) p. 89: Dependency injection for tool registry
- Buelta pp. 219-221: Command pattern for tool invocation

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses
- ANTI_PATTERN_ANALYSIS §4.1: Cognitive complexity < 15 per function

WBS 3.2.2: Search Tool Integration
- 3.2.2.1: search_corpus tool registered and wired to semantic-search-service
- 3.2.2.2: get_chunk tool registered and wired to semantic-search-service
"""

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.tools import (
    ToolDefinition,
    ToolExecuteRequest,
    ToolExecuteResponse,
)

# WBS 3.2.2: Import semantic search tool functions (not definitions)
from src.tools.builtin.chunk_retrieval import get_chunk
from src.tools.builtin.semantic_search import search_corpus

# WBS 3.3.2: Import AI agent tool functions
from src.tools.builtin.code_review import review_code
from src.tools.builtin.architecture import analyze_architecture
from src.tools.builtin.doc_generate import generate_documentation

# WBS 2.4.3.2: Import cross-reference tool (ai-agents proxy)
from src.tools.builtin.cross_reference import cross_reference

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Built-in Tool Implementations
# Pattern: Command pattern (Buelta pp. 219-221)
# =============================================================================


def echo_tool(message: str) -> dict[str, Any]:
    """
    Echo tool - returns the input message.

    Args:
        message: Message to echo

    Returns:
        dict with echoed message
    """
    return {"echoed": message}


def calculator_tool(a: float, b: float, operation: str = "add") -> dict[str, Any]:
    """
    Calculator tool - performs basic arithmetic.

    Args:
        a: First operand
        b: Second operand
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        dict with calculation result

    Raises:
        ValueError: If operation is invalid or division by zero
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y,  # Issue 39: Let Python raise ZeroDivisionError
    }

    if operation not in operations:
        raise ValueError(f"Unknown operation: {operation}")

    # Issue 39: Explicit check for division by zero with clear error message
    if operation == "divide" and b == 0:
        raise ValueError("Division by zero")

    result = operations[operation](a, b)
    return {"result": result, "operation": operation, "a": a, "b": b}


# =============================================================================
# WBS 3.2.2: Semantic Search Tool Wrappers
# Pattern: Adapter pattern - adapt dict-based tools to keyword args
# =============================================================================


async def search_corpus_wrapper(
    query: str,
    top_k: int = 10,
    collection: str = "documents",
) -> dict[str, Any]:
    """
    Wrapper for search_corpus tool to adapt to keyword args pattern.

    WBS 3.2.2.1.3: Call search_corpus tool through gateway.

    Args:
        query: The search query.
        top_k: Maximum number of results (default: 10).
        collection: Collection to search (default: 'documents').

    Returns:
        Search results from semantic-search-service.
    """
    args = {"query": query, "top_k": top_k, "collection": collection}
    return await search_corpus(args)


async def get_chunk_wrapper(chunk_id: str) -> dict[str, Any]:
    """
    Wrapper for get_chunk tool to adapt to keyword args pattern.

    WBS 3.2.2.2.1: Call get_chunk tool through gateway.

    Args:
        chunk_id: The unique identifier of the chunk.

    Returns:
        Chunk data from semantic-search-service.
    """
    args = {"chunk_id": chunk_id}
    return await get_chunk(args)


# =============================================================================
# WBS 3.3.2: AI Agent Tool Wrappers
# Pattern: Adapter pattern - adapt dict-based tools to keyword args
# =============================================================================


async def review_code_wrapper(code: str, language: str = "python") -> dict[str, Any]:
    """
    Wrapper for review_code tool to adapt to keyword args pattern.

    WBS 3.3.2.1.3: Call code review tool through gateway.

    Args:
        code: The source code to review.
        language: Programming language (default: 'python').

    Returns:
        Code review findings from ai-agents service.
    """
    args = {"code": code, "language": language}
    return await review_code(args)


async def analyze_architecture_wrapper(code: str, context: str = "") -> dict[str, Any]:
    """
    Wrapper for analyze_architecture tool to adapt to keyword args pattern.

    WBS 3.3.2.2.3: Call architecture analysis tool through gateway.

    Args:
        code: The source code to analyze.
        context: Additional context about the codebase.

    Returns:
        Architecture analysis from ai-agents service.
    """
    args = {"code": code, "context": context}
    return await analyze_architecture(args)


async def generate_documentation_wrapper(
    code: str, format: str = "markdown"  # NOSONAR A002 - 'format' shadows builtin, intentional API match
) -> dict[str, Any]:
    """
    Wrapper for generate_documentation tool to adapt to keyword args pattern.

    WBS 3.3.2.3.3: Call doc generation tool through gateway.

    Args:
        code: The source code to document.
        format: Output format (default: 'markdown').

    Returns:
        Generated documentation from ai-agents service.
    """
    args = {"code": code, "format": format}
    return await generate_documentation(args)


# =============================================================================
# WBS 2.4.3.2: Cross-Reference Tool Wrapper
# Pattern: Service proxy (proxies to ai-agents Cross-Reference Agent)
# =============================================================================


async def cross_reference_wrapper(
    book: str,
    chapter: int,
    title: str,
    tier: int,
    content: str | None = None,
    keywords: list[str] | None = None,
    concepts: list[str] | None = None,
    max_hops: int = 3,
    min_similarity: float = 0.7,
    include_tier1: bool = True,
    include_tier2: bool = True,
    include_tier3: bool = True,
    taxonomy_id: str = "ai-ml",
) -> dict[str, Any]:
    """
    Wrapper for cross_reference tool to adapt to keyword args pattern.

    WBS 2.4.3.2.5: Call cross_reference tool through gateway.

    This tool proxies to the ai-agents Cross-Reference Agent, which:
    - Traverses the taxonomy graph (Spider Web Model)
    - Finds related content across tiers
    - Generates scholarly annotations with Chicago-style citations

    Args:
        book: Source book title.
        chapter: Chapter number (1-indexed).
        title: Chapter title.
        tier: Tier level (1=Architecture, 2=Implementation, 3=Practices).
        content: Chapter content text (optional).
        keywords: Extracted keywords from the chapter.
        concepts: Key concepts from the chapter.
        max_hops: Maximum traversal depth in taxonomy graph (default: 3).
        min_similarity: Minimum similarity threshold (default: 0.7).
        include_tier1: Include Architecture Spine results (default: True).
        include_tier2: Include Implementation results (default: True).
        include_tier3: Include Practices results (default: True).
        taxonomy_id: Taxonomy identifier (default: 'ai-ml').

    Returns:
        Cross-reference results from ai-agents service.
    """
    args = {
        "book": book,
        "chapter": chapter,
        "title": title,
        "tier": tier,
        "content": content,
        "keywords": keywords or [],
        "concepts": concepts or [],
        "max_hops": max_hops,
        "min_similarity": min_similarity,
        "include_tier1": include_tier1,
        "include_tier2": include_tier2,
        "include_tier3": include_tier3,
        "taxonomy_id": taxonomy_id,
    }
    return await cross_reference(args)


# =============================================================================
# Tool Registry - WBS 2.2.4.3.2
# Pattern: Service registry (GUIDELINES p. 1544)
# =============================================================================


# Type alias for tool functions
ToolFunction = Callable[..., Awaitable[dict[str, Any]]]


# Built-in tool definitions
BUILTIN_TOOLS: dict[str, tuple[ToolDefinition, ToolFunction]] = {
    "echo": (
        ToolDefinition(
            name="echo",
            description="Echoes the input message back",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo"},
                },
                "required": ["message"],
            },
        ),
        echo_tool,
    ),
    "calculator": (
        ToolDefinition(
            name="calculator",
            description="Performs basic arithmetic operations",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First operand"},
                    "b": {"type": "number", "description": "Second operand"},
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "default": "add",
                        "description": "Operation to perform",
                    },
                },
                "required": ["a", "b"],
            },
        ),
        calculator_tool,
    ),
    # =========================================================================
    # WBS 3.2.2.1: Semantic Search Tool
    # Pattern: Service proxy (proxies to semantic-search-service)
    # =========================================================================
    "search_corpus": (
        ToolDefinition(
            name="search_corpus",
            description="Search the document corpus for relevant content using semantic similarity. "
            "Returns the most relevant chunks matching the query.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant documents.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10).",
                        "default": 10,
                    },
                    "collection": {
                        "type": "string",
                        "description": "The document collection to search (default: 'default').",
                        "default": "default",
                    },
                },
                "required": ["query"],
            },
        ),
        search_corpus_wrapper,
    ),
    # =========================================================================
    # WBS 3.2.2.2: Chunk Retrieval Tool
    # Pattern: Service proxy (proxies to semantic-search-service)
    # =========================================================================
    "get_chunk": (
        ToolDefinition(
            name="get_chunk",
            description="Retrieve a specific document chunk by its ID. "
            "Returns the chunk content and associated metadata.",
            parameters={
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "The unique identifier of the chunk to retrieve.",
                    },
                },
                "required": ["chunk_id"],
            },
        ),
        get_chunk_wrapper,
    ),
    # =========================================================================
    # WBS 3.3.2.1: Code Review Tool
    # Pattern: Service proxy (proxies to ai-agents microservice)
    # =========================================================================
    "review_code": (
        ToolDefinition(
            name="review_code",
            description="Perform code review on source code. "
            "Returns findings including issues, suggestions, and best practice violations.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The source code to review.",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language of the code (default: 'python').",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        ),
        review_code_wrapper,
    ),
    # =========================================================================
    # WBS 3.3.2.2: Architecture Analysis Tool
    # Pattern: Service proxy (proxies to ai-agents microservice)
    # =========================================================================
    "analyze_architecture": (
        ToolDefinition(
            name="analyze_architecture",
            description="Analyze code architecture and design patterns. "
            "Returns architectural insights, pattern usage, and recommendations.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The source code to analyze.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context about the codebase.",
                        "default": "",
                    },
                },
                "required": ["code"],
            },
        ),
        analyze_architecture_wrapper,
    ),
    # =========================================================================
    # WBS 3.3.2.3: Documentation Generation Tool
    # Pattern: Service proxy (proxies to ai-agents microservice)
    # =========================================================================
    "generate_documentation": (
        ToolDefinition(
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
        ),
        generate_documentation_wrapper,
    ),
    # =========================================================================
    # WBS 2.4.3.2: Cross-Reference Tool
    # Pattern: Service proxy (proxies to ai-agents Cross-Reference Agent)
    # Kitchen Brigade: Gateway -> ai-agents -> semantic-search
    # =========================================================================
    "cross_reference": (
        ToolDefinition(
            name="cross_reference",
            description="Generate cross-references for a source chapter using the Cross-Reference Agent. "
            "This tool finds related content across the document corpus by traversing the taxonomy graph "
            "(Spider Web Model) and generates scholarly annotations with Chicago-style citations.",
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
        ),
        cross_reference_wrapper,
    ),
}


# =============================================================================
# ToolExecutorService - WBS 2.2.4.3.4
# Pattern: Service layer extraction (ANTI_PATTERN §4.1)
# Pattern: Tool registry as service registry (GUIDELINES p. 1544)
# =============================================================================


class ToolExecutorService:
    """
    Service class for tool execution operations.

    Pattern: Service layer extraction for business logic
    Reference: GUIDELINES p. 1544 - Tool inventories as service registries

    This class enables:
    1. Tool registration and lookup
    2. Argument validation against JSON schema
    3. Tool execution with error handling
    """

    def __init__(self):
        """Initialize tool executor with builtin tools."""
        self._tools: dict[str, tuple[ToolDefinition, ToolFunction]] = dict(BUILTIN_TOOLS)

    def get_tool(self, name: str) -> tuple[ToolDefinition, ToolFunction] | None:
        """
        Get tool definition and function by name.

        WBS 2.2.4.3.2: Validate tool name exists in registry.

        Args:
            name: Tool name to look up

        Returns:
            Tuple of (ToolDefinition, ToolFunction) or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """
        List all available tool definitions.

        Returns:
            List of ToolDefinition objects
        """
        return [definition for definition, _ in self._tools.values()]

    def validate_arguments(
        self, definition: ToolDefinition, arguments: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Validate arguments against tool schema.

        WBS 2.2.4.3.3: Validate tool arguments against schema.

        Pattern: Schema validation (Sinha pp. 193-195)

        Args:
            definition: Tool definition with parameter schema
            arguments: Arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = definition.parameters

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in arguments:
                return False, f"Missing required argument: {field}"

        # Check argument types
        properties = schema.get("properties", {})
        for arg_name, arg_value in arguments.items():
            if arg_name not in properties:
                return False, f"Unknown argument: {arg_name}"

            expected_type = properties[arg_name].get("type")
            if expected_type and not self._check_type(arg_value, expected_type):
                return False, f"Invalid type for '{arg_name}': expected {expected_type}"

        return True, None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected JSON Schema type.

        Args:
            value: Value to check
            expected_type: JSON Schema type (string, number, boolean, etc.)

        Returns:
            True if type matches
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected_class = type_map.get(expected_type)
        if expected_class is None:
            return True  # Unknown type, assume valid
        return isinstance(value, expected_class)  # type: ignore[arg-type]

    async def execute(self, request: ToolExecuteRequest) -> ToolExecuteResponse:
        """
        Execute a tool with given arguments.

        WBS 2.2.4.3.4: Execute tool via executor service.
        WBS 2.2.4.3.5: Return tool result or error.

        Pattern: Command pattern execution (Buelta p. 219)

        Args:
            request: Tool execution request

        Returns:
            ToolExecuteResponse with result or error
        """
        tool_entry = self.get_tool(request.name)
        if tool_entry is None:
            return ToolExecuteResponse(
                name=request.name,
                result=None,
                success=False,
                error=f"Tool not found: {request.name}",
            )

        definition, func = tool_entry

        # Validate arguments
        is_valid, error_msg = self.validate_arguments(definition, request.arguments)
        if not is_valid:
            return ToolExecuteResponse(
                name=request.name,
                result=None,
                success=False,
                error=error_msg,
            )

        # Execute tool
        try:
            # Handle both sync and async tool functions (Issue 42-43 fix)
            # Reference: GUIDELINES pp. 466, 618 - async only when awaiting
            if inspect.iscoroutinefunction(func):
                result = await func(**request.arguments)
            else:
                result = func(**request.arguments)
            return ToolExecuteResponse(
                name=request.name,
                result=result,
                success=True,
            )
        except Exception as e:
            # ANTI_PATTERN §3.1: Log exception with context
            logger.warning(f"Tool execution failed: {request.name} - {e}")
            return ToolExecuteResponse(
                name=request.name,
                result=None,
                success=False,
                error=str(e),
            )


# =============================================================================
# Dependency Injection - FastAPI Pattern (Sinha p. 90)
# =============================================================================

# Global service instance (can be overridden in tests)
_tool_executor: ToolExecutorService | None = None


def get_tool_executor() -> ToolExecutorService:
    """
    Dependency injection factory for ToolExecutorService.

    Pattern: Factory method for dependency injection (Sinha p. 90)

    Returns:
        ToolExecutorService: The tool executor instance
    """
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutorService()
    return _tool_executor


# =============================================================================
# Router - WBS 2.2.4.1
# =============================================================================

router = APIRouter(prefix="/v1/tools", tags=["Tools"])


# =============================================================================
# List Tools Endpoint
# =============================================================================


@router.get("", response_model=list[ToolDefinition])
async def list_tools(
    tool_executor: ToolExecutorService = Depends(get_tool_executor),
) -> list[ToolDefinition]:
    """
    List all available tools.

    Returns:
        List of tool definitions
    """
    return tool_executor.list_tools()


# =============================================================================
# Tool Execution Endpoint - WBS 2.2.4.3
# =============================================================================


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    request: ToolExecuteRequest,
    tool_executor: ToolExecutorService = Depends(get_tool_executor),
) -> ToolExecuteResponse:
    """
    Execute a tool with given arguments.

    WBS 2.2.4.3.1: POST /v1/tools/execute endpoint
    WBS 2.2.4.3.2: Validate tool name exists in registry
    WBS 2.2.4.3.3: Validate tool arguments against schema
    WBS 2.2.4.3.4: Execute tool via executor service
    WBS 2.2.4.3.5: Return tool result or error

    Pattern: Command pattern for tool invocation (Buelta p. 219)

    Args:
        request: Tool execution request
        tool_executor: Injected tool executor service

    Returns:
        ToolExecuteResponse with result or error

    Raises:
        HTTPException 404: Tool not found in registry
        HTTPException 422: Invalid tool arguments
    """
    logger.debug(f"Tool execution request: {request.name}")

    # Check tool exists
    tool_entry = tool_executor.get_tool(request.name)
    if tool_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {request.name}",
        )

    definition, _ = tool_entry

    # Validate arguments
    is_valid, error_msg = tool_executor.validate_arguments(definition, request.arguments)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )

    # Execute tool
    return await tool_executor.execute(request)
