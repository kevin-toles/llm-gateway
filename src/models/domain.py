"""
Domain Models - WBS 2.4.1.2 Tool Definition Schema

This module contains domain models for the tool system, including
tool definitions, tool calls, and tool results.

Reference Documents:
- ARCHITECTURE.md: Line 70 - domain.py "Domain models (Message, Tool, etc.)"
- GUIDELINES pp. 276: Domain modeling with Pydantic or @dataclass(frozen=True)
- GUIDELINES pp. 1510-1569: Tool inventory patterns, tool_calls format
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Pattern: Domain models as value objects (Percival & Gregory pp. 59-65)
Pattern: Pydantic for validation at API boundaries (Sinha pp. 193-195)

Note: These models are distinct from the request/response Tool model in
requests.py. These are internal domain models used by the tool registry
and executor.
"""

import json
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field


# =============================================================================
# WBS 2.4.1.2.2-3: ToolDefinition Model
# =============================================================================


class ToolDefinition(BaseModel):
    """
    Tool definition schema for tool registration.

    WBS 2.4.1.2.2-3: Tool model with name, description, parameters.

    This is the metadata describing a tool - its name, what it does,
    and the JSON Schema for its parameters. It does not include the
    handler callable; see RegisteredTool for that.

    Pattern: Value object (identified by data, not identity)
    Pattern: JSON Schema for parameters (OpenAI/Anthropic compatible)

    Attributes:
        name: Unique tool identifier.
        description: Human-readable description of what the tool does.
        parameters: JSON Schema defining the tool's input parameters.

    Example:
        >>> tool = ToolDefinition(
        ...     name="search",
        ...     description="Search for information",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "query": {"type": "string", "description": "Search query"}
        ...         },
        ...         "required": ["query"]
        ...     }
        ... )
    """

    name: str = Field(..., description="Unique tool identifier")
    description: Optional[str] = Field(
        default=None, description="Human-readable description"
    )
    parameters: dict[str, Any] = Field(
        ..., description="JSON Schema for input parameters"
    )

    model_config = {"frozen": True}  # Value object: immutable


# =============================================================================
# WBS 2.4.1.2.4: RegisteredTool Model
# =============================================================================


class RegisteredTool(BaseModel):
    """
    A tool with its definition and handler callable.

    WBS 2.4.1.2.4: Add handler callable reference.

    This combines a ToolDefinition with the actual callable that executes
    the tool. The handler can be sync or async and receives the parsed
    arguments as a dict.

    Pattern: Tool inventory with callable handlers (GUIDELINES pp. 1518)

    Attributes:
        definition: The tool's metadata (name, description, parameters).
        handler: Callable that executes the tool.

    Example:
        >>> async def search_handler(args: dict) -> str:
        ...     return f"Results for: {args['query']}"
        ...
        >>> tool = RegisteredTool(
        ...     definition=ToolDefinition(name="search", ...),
        ...     handler=search_handler
        ... )
    """

    definition: ToolDefinition
    handler: Callable[..., Any] = Field(..., description="Tool execution callable")

    model_config = {"arbitrary_types_allowed": True}

    @property
    def name(self) -> str:
        """Get tool name from definition."""
        return self.definition.name

    @property
    def description(self) -> Optional[str]:
        """Get tool description from definition."""
        return self.definition.description

    @property
    def parameters(self) -> dict[str, Any]:
        """Get tool parameters from definition."""
        return self.definition.parameters


# =============================================================================
# WBS 2.4.1.2.5: ToolCall Model
# =============================================================================


class ToolCall(BaseModel):
    """
    A request to execute a specific tool with arguments.

    WBS 2.4.1.2.5: Implement ToolCall model.

    Represents the LLM's request to call a tool. This is parsed from
    the tool_calls field in an LLM response and contains the tool name
    and arguments to pass.

    Pattern: Command pattern (encapsulates a request as an object)
    Pattern: Compatible with OpenAI/Anthropic tool_call formats

    Attributes:
        id: Unique identifier for this tool call.
        name: Name of the tool to execute.
        arguments: Arguments to pass to the tool handler.

    Example:
        >>> tool_call = ToolCall(
        ...     id="call_abc123",
        ...     name="search",
        ...     arguments={"query": "Python tutorials"}
        ... )
    """

    id: str = Field(..., description="Unique tool call identifier")
    name: str = Field(..., description="Name of tool to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments for tool"
    )

    @classmethod
    def from_openai_format(cls, tool_call: dict[str, Any]) -> "ToolCall":
        """
        Parse a ToolCall from OpenAI's tool_calls format.

        Pattern: Factory method for format conversion

        Args:
            tool_call: OpenAI format tool call:
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {
                        "name": "tool_name",
                        "arguments": "{\"arg\": \"value\"}"  # JSON string
                    }
                }

        Returns:
            ToolCall instance with parsed arguments.
        """
        function = tool_call.get("function", {})
        arguments_str = function.get("arguments", "{}")

        # Parse JSON string arguments
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}

        return cls(
            id=tool_call.get("id", ""),
            name=function.get("name", ""),
            arguments=arguments,
        )


# =============================================================================
# WBS 2.4.1.2.6: ToolResult Model
# =============================================================================


class ToolResult(BaseModel):
    """
    Result of executing a tool.

    WBS 2.4.1.2.6: Implement ToolResult model.

    Contains the output from executing a tool, along with the original
    tool_call_id for correlation. Can indicate whether the result is
    an error.

    Pattern: Result object for tool execution
    Pattern: Compatible with OpenAI/Anthropic tool result formats

    Attributes:
        tool_call_id: ID of the ToolCall this result responds to.
        content: The tool's output (string).
        is_error: Whether the result represents an error.

    Example:
        >>> result = ToolResult(
        ...     tool_call_id="call_abc123",
        ...     content="Found 5 results for 'Python tutorials'",
        ...     is_error=False
        ... )
    """

    tool_call_id: str = Field(..., description="ID of originating tool call")
    content: str = Field(..., description="Tool output content")
    is_error: bool = Field(default=False, description="Whether result is an error")

    def to_message_dict(self) -> dict[str, Any]:
        """
        Convert to OpenAI message format.

        Returns:
            Dict suitable for appending to messages array:
                {
                    "role": "tool",
                    "tool_call_id": "call_xyz",
                    "content": "tool output"
                }
        """
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }
