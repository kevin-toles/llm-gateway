"""
Tool Executor - WBS 2.4.2.1 Executor Implementation

This module implements the tool executor for executing registered tools.
The executor handles tool lookup, argument validation, execution, and
error handling.

Reference Documents:
- ARCHITECTURE.md Line 49: executor.py "Tool execution orchestration"
- ARCHITECTURE.md Lines 211-212: "Executes tools (local or proxied)"
- GUIDELINES pp. 1489: Command pattern for tool invocation
- GUIDELINES pp. 466: Fail-fast error handling with retry at orchestration level
- GUIDELINES pp. 1004: Circuit breakers and timeouts

Pattern: Command Executor (executes tool calls as commands)
Pattern: Async-first with sync handler support
Pattern: Fail-fast validation with graceful error wrapping
"""

import asyncio
import inspect
import logging
from typing import Any, Optional

from src.models.domain import ToolCall, ToolResult
from src.tools.registry import ToolRegistry, ToolNotFoundError, get_tool_registry

logger = logging.getLogger(__name__)

# Default execution timeout in seconds
DEFAULT_TIMEOUT = 30.0


# =============================================================================
# Exceptions
# =============================================================================


class ToolExecutionError(Exception):
    """Base exception for tool execution errors."""

    def __init__(self, message: str, tool_name: Optional[str] = None) -> None:
        self.tool_name = tool_name
        super().__init__(message)


class ToolValidationError(ToolExecutionError):
    """Raised when tool arguments fail validation."""

    def __init__(
        self, message: str, tool_name: Optional[str] = None, field: Optional[str] = None
    ) -> None:
        self.field = field
        super().__init__(message, tool_name)


# =============================================================================
# WBS 2.4.2.1.2: ToolExecutor Class
# =============================================================================


class ToolExecutor:
    """
    Executor for running registered tools.

    WBS 2.4.2.1.2: Implement ToolExecutor class.
    WBS 2.4.2.1.3: Inject ToolRegistry dependency.

    The executor looks up tools in the registry, validates arguments against
    the tool's JSON Schema, executes the handler, and wraps results.

    Pattern: Command Executor (GUIDELINES pp. 1489)
    Pattern: Dependency Injection (registry is injected)
    Pattern: Async-first execution

    Attributes:
        registry: The ToolRegistry to look up tools from.
        timeout: Maximum execution time in seconds.

    Example:
        >>> executor = ToolExecutor(registry=get_tool_registry())
        >>> result = await executor.execute(tool_call)
    """

    def __init__(
        self, registry: ToolRegistry, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize the executor with a registry.

        WBS 2.4.2.1.3: Inject ToolRegistry dependency.
        WBS 2.4.2.1.10: Add execution timeout.

        Args:
            registry: The ToolRegistry to use for tool lookup.
            timeout: Maximum execution time in seconds (default: 30).
        """
        self.registry = registry
        self.timeout = timeout

    # =========================================================================
    # WBS 2.4.2.1.4: execute() Method
    # =========================================================================

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call and return the result.

        WBS 2.4.2.1.4: Implement async execute(tool_call: ToolCall) -> ToolResult.
        WBS 2.4.2.1.5: Validate tool exists in registry.
        WBS 2.4.2.1.6: Validate arguments against tool schema.
        WBS 2.4.2.1.7: Execute tool handler.
        WBS 2.4.2.1.8: Wrap result in ToolResult.
        WBS 2.4.2.1.9: Handle execution errors gracefully.
        WBS 2.4.2.1.10: Add execution timeout.

        Args:
            tool_call: The ToolCall containing tool name and arguments.

        Returns:
            ToolResult with execution output or error information.

        Raises:
            ToolExecutionError: If tool not found in registry.
            ToolValidationError: If arguments fail schema validation.
        """
        tool_name = tool_call.name
        tool_call_id = tool_call.id

        # WBS 2.4.2.1.5: Validate tool exists
        try:
            tool = self.registry.get(tool_name)
        except ToolNotFoundError as e:
            raise ToolExecutionError(
                f"Tool not found: {tool_name}", tool_name=tool_name
            ) from e

        # WBS 2.4.2.1.6: Validate arguments against schema
        self._validate_arguments(tool_name, tool.parameters, tool_call.arguments)

        # WBS 2.4.2.1.7: Execute handler with timeout
        # WBS 2.4.2.1.9: Handle errors gracefully
        try:
            result_content = await self._execute_with_timeout(
                tool.handler, tool_call.arguments
            )
            # WBS 2.4.2.1.8: Wrap in ToolResult
            return ToolResult(
                tool_call_id=tool_call_id,
                content=str(result_content),
                is_error=False,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Tool {tool_name} timed out after {self.timeout}s")
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"Tool execution timeout after {self.timeout}s",
                is_error=True,
            )
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            return ToolResult(
                tool_call_id=tool_call_id,
                content=f"Tool execution failed: {e}",
                is_error=True,
            )

    # =========================================================================
    # WBS 2.4.2.1.6: Argument Validation
    # =========================================================================

    def _validate_arguments(
        self, tool_name: str, schema: dict[str, Any], arguments: dict[str, Any]
    ) -> None:
        """
        Validate arguments against tool's JSON Schema.

        WBS 2.4.2.1.6: Validate arguments against tool schema.

        Performs basic validation:
        - Required properties are present
        - Type checking for known types

        Args:
            tool_name: Name of the tool (for error messages).
            schema: JSON Schema for the tool's parameters.
            arguments: Arguments provided in the tool call.

        Raises:
            ToolValidationError: If validation fails.
        """
        # Check required properties
        required = schema.get("required", [])
        for prop in required:
            if prop not in arguments:
                raise ToolValidationError(
                    f"Missing required argument: {prop}",
                    tool_name=tool_name,
                    field=prop,
                )

        # Check types of provided properties
        properties = schema.get("properties", {})
        for prop_name, value in arguments.items():
            if prop_name not in properties:
                continue  # Allow extra properties

            prop_schema = properties[prop_name]
            expected_type = prop_schema.get("type")

            if expected_type and not self._check_type(value, expected_type):
                raise ToolValidationError(
                    f"Invalid type for '{prop_name}': expected {expected_type}, "
                    f"got {type(value).__name__}",
                    tool_name=tool_name,
                    field=prop_name,
                )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if a value matches the expected JSON Schema type.

        Args:
            value: The value to check.
            expected_type: The JSON Schema type string.

        Returns:
            True if the value matches the type, False otherwise.
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_map.get(expected_type)
        if python_type is None:
            return True  # Unknown type, allow

        # Special case: integers are valid numbers
        if expected_type == "number" and isinstance(value, bool):
            return False  # bool is subclass of int, but not a valid number

        return isinstance(value, python_type)

    # =========================================================================
    # WBS 2.4.2.1.10: Timeout Handling
    # =========================================================================

    async def _execute_with_timeout(
        self, handler: Any, arguments: dict[str, Any]
    ) -> Any:
        """
        Execute a handler with timeout protection.

        WBS 2.4.2.1.10: Add execution timeout.

        Handles both sync and async handlers. Sync handlers are run in
        the default executor to avoid blocking.

        Args:
            handler: The tool handler callable.
            arguments: Arguments to pass to the handler.

        Returns:
            The handler's return value.

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout.
        """
        # Check if handler is async
        if inspect.iscoroutinefunction(handler):
            # Async handler - use wait_for with timeout
            coro = handler(arguments)
            return await asyncio.wait_for(coro, timeout=self.timeout)
        else:
            # Sync handler - run in executor with timeout
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, handler, arguments)
            return await asyncio.wait_for(future, timeout=self.timeout)

    # =========================================================================
    # WBS 2.4.2.2.1: Batch Execution
    # =========================================================================

    async def execute_batch(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolResult]:
        """
        Execute multiple tool calls concurrently.

        WBS 2.4.2.2.1: Implement execute_batch(tool_calls) -> list[ToolResult].
        WBS 2.4.2.2.2: Execute tools concurrently with asyncio.gather.
        WBS 2.4.2.2.3: Preserve order of results.
        WBS 2.4.2.2.4: Handle partial failures.

        All tool calls are executed in parallel using asyncio.gather.
        Results are returned in the same order as input tool_calls.
        Failures in individual tools don't affect other executions.

        Args:
            tool_calls: List of ToolCalls to execute.

        Returns:
            List of ToolResults in same order as input.
        """
        if not tool_calls:
            return []

        # Execute all concurrently, wrapping errors in ToolResult
        async def safe_execute(tool_call: ToolCall) -> ToolResult:
            """Execute a single tool call, catching validation errors."""
            try:
                return await self.execute(tool_call)
            except (ToolExecutionError, ToolValidationError) as e:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=f"Tool error: {e}",
                    is_error=True,
                )

        # WBS 2.4.2.2.2: Concurrent execution with gather
        results = await asyncio.gather(
            *[safe_execute(tc) for tc in tool_calls],
            return_exceptions=False,  # We handle exceptions in safe_execute
        )

        return list(results)


# =============================================================================
# Singleton Access
# =============================================================================

_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """
    Get the global tool executor instance.

    Returns the same ToolExecutor instance on every call (singleton pattern).
    Uses the global tool registry.

    Returns:
        The global ToolExecutor instance.

    Example:
        >>> executor = get_tool_executor()
        >>> result = await executor.execute(tool_call)
    """
    global _executor
    if _executor is None:
        _executor = ToolExecutor(registry=get_tool_registry())
    return _executor


def reset_tool_executor() -> None:
    """
    Reset the global tool executor.

    Primarily used for testing to ensure a clean state.
    """
    global _executor
    _executor = None
