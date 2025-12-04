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
"""

import logging
from typing import Optional, Any, Callable, Awaitable

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.tools import (
    ToolDefinition,
    ToolExecuteRequest,
    ToolExecuteResponse,
)


# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Built-in Tool Implementations
# Pattern: Command pattern (Buelta pp. 219-221)
# =============================================================================


async def echo_tool(message: str) -> dict[str, Any]:
    """
    Echo tool - returns the input message.

    Args:
        message: Message to echo

    Returns:
        dict with echoed message
    """
    return {"echoed": message}


async def calculator_tool(a: float, b: float, operation: str = "add") -> dict[str, Any]:
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

    def get_tool(self, name: str) -> Optional[tuple[ToolDefinition, ToolFunction]]:
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
    ) -> tuple[bool, Optional[str]]:
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
            if expected_type:
                if not self._check_type(arg_value, expected_type):
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
            result = await func(**request.arguments)
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
_tool_executor: Optional[ToolExecutorService] = None


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
