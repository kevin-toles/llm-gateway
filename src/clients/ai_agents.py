"""
AI Agents Client - WBS 2.7.1.3

This module provides a client for the ai-agents microservice.

Reference Documents:
- ARCHITECTURE.md: Line 53 - ai_agents.py "Proxy to ai-agents-service"
- ARCHITECTURE.md: Line 233 - ai-agents-service dependency
- ARCHITECTURE.md: Line 278 - ai_agents_url configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service

Pattern: Client adapter for microservice communication
Anti-Pattern §1.1 Avoided: Uses Optional[T] with explicit None defaults
"""

from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from src.clients.http import create_http_client, HTTPClientError


# =============================================================================
# Custom Exceptions - WBS 2.7.1.3.6
# =============================================================================


class AIAgentsError(HTTPClientError):
    """Exception for AI agents service errors."""

    pass


class ToolNotFoundError(AIAgentsError):
    """Exception when a tool is not found."""

    pass


# =============================================================================
# Constants for Field descriptions
# =============================================================================

_TOOL_NAME_DESC = "Tool name"
_TOOL_DESC_DESC = "Tool description"


# =============================================================================
# Response Models - WBS 2.7.1.3.3-5
# =============================================================================


class ToolResult(BaseModel):
    """Result from executing a tool.

    Attributes:
        tool_name: Name of the tool that was executed
        success: Whether the execution was successful
        result: The result data from the tool (if successful)
        error: Error message (if not successful)
        execution_time_ms: Time taken to execute in milliseconds
    """

    tool_name: str = Field(..., description=_TOOL_NAME_DESC)
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[dict[str, Any]] = Field(default=None, description="Result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: int = Field(default=0, description="Execution time in ms")


class ToolDefinition(BaseModel):
    """Definition of an available tool.

    Attributes:
        name: Unique tool name
        description: Human-readable description
        category: Tool category (retrieval, execution, etc.)
    """

    name: str = Field(..., description=_TOOL_NAME_DESC)
    description: str = Field(..., description=_TOOL_DESC_DESC)
    category: str = Field(default="general", description="Tool category")


class ToolSchema(BaseModel):
    """JSON Schema for a tool's parameters.

    Attributes:
        name: Tool name
        description: Tool description
        parameters: JSON Schema for tool parameters
    """

    name: str = Field(..., description=_TOOL_NAME_DESC)
    description: str = Field(..., description=_TOOL_DESC_DESC)
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema")


# =============================================================================
# WBS 2.7.1.3.2: AIAgentsClient Class
# =============================================================================


class AIAgentsClient:
    """
    Client for the ai-agents microservice.

    WBS 2.7.1.3.2: Implement AIAgentsClient class.

    This client provides methods to:
    - Execute tools (WBS 2.7.1.3.3)
    - List available tools (WBS 2.7.1.3.4)
    - Get tool schemas (WBS 2.7.1.3.5)

    Pattern: Client adapter for microservice communication
    Reference: ARCHITECTURE.md Line 233 - ai-agents-service dependency

    Example:
        >>> client = AIAgentsClient(base_url="http://localhost:8082")
        >>> result = await client.execute_tool("semantic_search", {"query": "test"})
        >>> if result.success:
        ...     print(result.result)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout_seconds: float = 60.0,  # Longer timeout for tool execution
    ) -> None:
        """
        Initialize AIAgentsClient.

        Args:
            base_url: Base URL for ai-agents-service
            http_client: Optional pre-configured HTTP client (for testing)
            timeout_seconds: Request timeout in seconds (default 60s for tools)
        """
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = create_http_client(
                base_url=base_url or "http://localhost:8082",
                timeout_seconds=timeout_seconds,
            )
            self._owns_client = True

    async def close(self) -> None:
        """Close the HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AIAgentsClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # WBS 2.7.1.3.3: Execute Tool Method
    # =========================================================================

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool with the given parameters.

        WBS 2.7.1.3.3: Implement async execute_tool(tool_name, params) -> ToolResult.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters to pass to the tool

        Returns:
            ToolResult with execution results

        Raises:
            AIAgentsError: If the service is unavailable or returns an error
        """
        try:
            payload = {
                "tool_name": tool_name,
                "params": params,
            }

            response = await self._client.post("/tools/execute", json=payload)
            response.raise_for_status()

            data = response.json()
            return ToolResult(
                tool_name=data.get("tool_name", tool_name),
                success=data.get("success", False),
                result=data.get("result"),
                error=data.get("error"),
                execution_time_ms=data.get("execution_time_ms", 0),
            )

        except httpx.ConnectError as e:
            raise AIAgentsError(f"AI agents service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise AIAgentsError(f"Tool execution timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AIAgentsError(f"Tool execution error: {e}") from e
        except Exception as e:
            raise AIAgentsError(f"Tool execution failed: {e}") from e

    # =========================================================================
    # WBS 2.7.1.3.4: List Tools Method
    # =========================================================================

    async def list_tools(self) -> list[ToolDefinition]:
        """
        List all available tools.

        WBS 2.7.1.3.4: Implement async list_tools() -> list[ToolDefinition].

        Returns:
            List of available tool definitions

        Raises:
            AIAgentsError: If the service is unavailable or returns an error
        """
        try:
            response = await self._client.get("/tools")
            response.raise_for_status()

            data = response.json()
            return [ToolDefinition(**t) for t in data.get("tools", [])]

        except httpx.ConnectError as e:
            raise AIAgentsError(f"AI agents service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise AIAgentsError(f"List tools request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise AIAgentsError(f"List tools error: {e}") from e
        except Exception as e:
            raise AIAgentsError(f"List tools failed: {e}") from e

    # =========================================================================
    # WBS 2.7.1.3.5: Get Tool Schema Method
    # =========================================================================

    async def get_tool_schema(
        self,
        tool_name: str,
    ) -> ToolSchema:
        """
        Get the JSON schema for a tool's parameters.

        WBS 2.7.1.3.5: Implement async get_tool_schema(tool_name) -> ToolSchema.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolSchema with parameter definitions

        Raises:
            ToolNotFoundError: If the tool does not exist
            AIAgentsError: If the service is unavailable or returns an error
        """
        try:
            response = await self._client.get(f"/tools/{tool_name}/schema")
            response.raise_for_status()

            data = response.json()
            return ToolSchema(
                name=data.get("name", tool_name),
                description=data.get("description", ""),
                parameters=data.get("parameters", {}),
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ToolNotFoundError(f"Tool not found: {tool_name}") from e
            raise AIAgentsError(f"Get tool schema error: {e}") from e
        except httpx.ConnectError as e:
            raise AIAgentsError(f"AI agents service unavailable: {e}") from e
        except httpx.TimeoutException as e:
            raise AIAgentsError(f"Get tool schema request timed out: {e}") from e
        except Exception as e:
            raise AIAgentsError(f"Get tool schema failed: {e}") from e
