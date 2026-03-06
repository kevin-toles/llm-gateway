"""
Tool Models - WBS 2.2.4.2 Tool Models

This module contains Pydantic models for tool execution request/response.

Reference Documents:
- GUIDELINES pp. 1489-1544: Agent tool execution patterns, tool inventories
- Percival & Gregory (Architecture Patterns) pp. 59-60: Domain model with interfaces
- Sinha (FastAPI) pp. 193-195: Pydantic validation patterns

Anti-Patterns Avoided:
- §1.1: Optional fields use Optional[T] with explicit None default
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# ToolDefinition - WBS 2.2.4.2.3
# Pattern: Domain model with clear interfaces (Percival pp. 59-60)
# =============================================================================


class ToolDefinition(BaseModel):
    """
    Tool definition for the registry.

    WBS 2.2.4.2.3: ToolDefinition model for tool registry.

    Pattern: Service registry entry (GUIDELINES p. 1544)

    Attributes:
        name: Unique tool identifier
        description: Human-readable description
        parameters: JSON Schema for tool arguments
    """

    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(
        ..., description="JSON Schema for tool arguments"
    )


# =============================================================================
# ToolExecuteRequest - WBS 2.2.4.2.1
# =============================================================================


class ToolExecuteRequest(BaseModel):
    """
    Tool execution request model.

    WBS 2.2.4.2.1: ToolExecuteRequest model.

    Pattern: Command pattern input (Buelta p. 219)

    Attributes:
        name: Tool name to execute
        arguments: Tool arguments (validated against tool schema)
    """

    name: str = Field(..., description="Tool name to execute")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )


# =============================================================================
# ToolExecuteResponse - WBS 2.2.4.2.2
# =============================================================================


class ToolExecuteResponse(BaseModel):
    """
    Tool execution response model.

    WBS 2.2.4.2.2: ToolExecuteResponse model.

    Pattern: Command pattern output (Buelta p. 219)

    Attributes:
        name: Tool name that was executed
        result: Tool execution result (can be any JSON-serializable value)
        success: Whether execution succeeded
        error: Error message if execution failed
    """

    name: str = Field(..., description="Tool name")
    result: Optional[Any] = Field(default=None, description="Execution result")
    success: bool = Field(..., description="Whether execution succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
