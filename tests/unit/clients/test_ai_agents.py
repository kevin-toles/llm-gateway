"""
Tests for AI Agents Client - WBS 2.7.1.3

TDD RED Phase: Tests for AIAgentsClient class.

Reference Documents:
- ARCHITECTURE.md: Line 53 - ai_agents.py "Proxy to ai-agents-service"
- ARCHITECTURE.md: Line 233 - ai-agents-service dependency
- ARCHITECTURE.md: Line 278 - ai_agents_url configuration
- GUIDELINES pp. 2309: Connection pooling per downstream service

WBS Items Covered:
- 2.7.1.3.1: Create src/clients/ai_agents.py
- 2.7.1.3.2: Implement AIAgentsClient class
- 2.7.1.3.3: Implement async execute_tool(tool_name: str, params: dict) -> ToolResult
- 2.7.1.3.4: Implement async list_tools() -> list[ToolDefinition]
- 2.7.1.3.5: Implement async get_tool_schema(tool_name: str) -> ToolSchema
- 2.7.1.3.6: Add error handling for service unavailable
- 2.7.1.3.7: RED tests with mocked responses
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def ai_agents_client(mock_http_client):
    """Create AIAgentsClient with mock HTTP client."""
    from src.clients.ai_agents import AIAgentsClient

    return AIAgentsClient(http_client=mock_http_client)


@pytest.fixture
def sample_tool_result():
    """Sample tool execution result."""
    return {
        "tool_name": "semantic_search",
        "success": True,
        "result": {
            "chunks": [
                {"id": "chunk-1", "content": "Result content"},
            ]
        },
        "execution_time_ms": 150,
    }


@pytest.fixture
def sample_tool_list():
    """Sample list of available tools."""
    return {
        "tools": [
            {
                "name": "semantic_search",
                "description": "Search for relevant document chunks",
                "category": "retrieval",
            },
            {
                "name": "code_execution",
                "description": "Execute Python code in sandbox",
                "category": "execution",
            },
        ]
    }


@pytest.fixture
def sample_tool_schema():
    """Sample tool schema response."""
    return {
        "name": "semantic_search",
        "description": "Search for relevant document chunks",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    }


# =============================================================================
# WBS 2.7.1.3.1-2: Package and Class Tests
# =============================================================================


class TestAIAgentsClientClass:
    """Tests for AIAgentsClient class structure."""

    def test_ai_agents_module_importable(self) -> None:
        """
        WBS 2.7.1.3.1: ai_agents module is importable.
        """
        from src.clients import ai_agents
        assert ai_agents is not None

    def test_ai_agents_client_class_exists(self) -> None:
        """
        WBS 2.7.1.3.2: AIAgentsClient class exists.
        """
        from src.clients.ai_agents import AIAgentsClient
        assert AIAgentsClient is not None

    def test_client_accepts_http_client(self, mock_http_client) -> None:
        """
        AIAgentsClient accepts HTTP client dependency.
        """
        from src.clients.ai_agents import AIAgentsClient

        client = AIAgentsClient(http_client=mock_http_client)
        assert client is not None

    def test_client_accepts_base_url(self) -> None:
        """
        AIAgentsClient can be created with base_url.
        """
        from src.clients.ai_agents import AIAgentsClient

        client = AIAgentsClient(base_url="http://localhost:8082")
        assert client is not None


# =============================================================================
# WBS 2.7.1.3.3: Execute Tool Method Tests
# =============================================================================


class TestExecuteToolMethod:
    """Tests for execute_tool method."""

    @pytest.mark.asyncio
    async def test_execute_tool_returns_result(
        self, ai_agents_client, mock_http_client, sample_tool_result
    ) -> None:
        """
        WBS 2.7.1.3.3: execute_tool returns ToolResult.
        """
        from src.clients.ai_agents import ToolResult

        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_result
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await ai_agents_client.execute_tool(
            "semantic_search",
            {"query": "test"}
        )

        assert isinstance(result, ToolResult)
        assert result.tool_name == "semantic_search"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_tool_passes_parameters(
        self, ai_agents_client, mock_http_client, sample_tool_result
    ) -> None:
        """
        execute_tool passes parameters to the tool.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_result
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        await ai_agents_client.execute_tool(
            "semantic_search",
            {"query": "test", "limit": 5}
        )

        call_kwargs = mock_http_client.post.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_execute_tool_includes_execution_time(
        self, ai_agents_client, mock_http_client, sample_tool_result
    ) -> None:
        """
        ToolResult includes execution time.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_result
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await ai_agents_client.execute_tool(
            "semantic_search",
            {"query": "test"}
        )

        assert result.execution_time_ms == 150


# =============================================================================
# WBS 2.7.1.3.4: List Tools Method Tests
# =============================================================================


class TestListToolsMethod:
    """Tests for list_tools method."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_list(
        self, ai_agents_client, mock_http_client, sample_tool_list
    ) -> None:
        """
        WBS 2.7.1.3.4: list_tools returns list of ToolDefinition.
        """
        from src.clients.ai_agents import ToolDefinition

        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_list
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        tools = await ai_agents_client.list_tools()

        assert isinstance(tools, list)
        assert len(tools) == 2
        assert all(isinstance(t, ToolDefinition) for t in tools)

    @pytest.mark.asyncio
    async def test_list_tools_includes_names(
        self, ai_agents_client, mock_http_client, sample_tool_list
    ) -> None:
        """
        Tools include name and description.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_list
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        tools = await ai_agents_client.list_tools()

        assert tools[0].name == "semantic_search"
        assert tools[0].description == "Search for relevant document chunks"


# =============================================================================
# WBS 2.7.1.3.5: Get Tool Schema Method Tests
# =============================================================================


class TestGetToolSchemaMethod:
    """Tests for get_tool_schema method."""

    @pytest.mark.asyncio
    async def test_get_tool_schema_returns_schema(
        self, ai_agents_client, mock_http_client, sample_tool_schema
    ) -> None:
        """
        WBS 2.7.1.3.5: get_tool_schema returns ToolSchema.
        """
        from src.clients.ai_agents import ToolSchema

        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_schema
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        schema = await ai_agents_client.get_tool_schema("semantic_search")

        assert isinstance(schema, ToolSchema)
        assert schema.name == "semantic_search"

    @pytest.mark.asyncio
    async def test_get_tool_schema_includes_parameters(
        self, ai_agents_client, mock_http_client, sample_tool_schema
    ) -> None:
        """
        ToolSchema includes parameter definitions.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = sample_tool_schema
        mock_response.raise_for_status = MagicMock()
        mock_http_client.get.return_value = mock_response

        schema = await ai_agents_client.get_tool_schema("semantic_search")

        assert schema.parameters is not None
        assert "properties" in schema.parameters


# =============================================================================
# WBS 2.7.1.3.6: Error Handling Tests
# =============================================================================


class TestAIAgentsErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_service_unavailable_raises_error(
        self, ai_agents_client, mock_http_client
    ) -> None:
        """
        WBS 2.7.1.3.6: Service unavailable raises AIAgentsError.
        """
        from src.clients.ai_agents import AIAgentsError

        mock_http_client.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(AIAgentsError) as exc_info:
            await ai_agents_client.execute_tool("test_tool", {})

        assert "unavailable" in str(exc_info.value).lower() or "connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_timeout_raises_error(
        self, ai_agents_client, mock_http_client
    ) -> None:
        """
        Timeout raises AIAgentsError.
        """
        from src.clients.ai_agents import AIAgentsError

        mock_http_client.post.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(AIAgentsError):
            await ai_agents_client.execute_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_tool_not_found_raises_error(
        self, ai_agents_client, mock_http_client
    ) -> None:
        """
        Tool not found raises ToolNotFoundError.
        """
        from src.clients.ai_agents import ToolNotFoundError

        # Use MagicMock for response since raise_for_status is synchronous
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_http_client.get.return_value = mock_response

        with pytest.raises(ToolNotFoundError):
            await ai_agents_client.get_tool_schema("nonexistent")

    @pytest.mark.asyncio
    async def test_tool_execution_failure_returns_result(
        self, ai_agents_client, mock_http_client
    ) -> None:
        """
        Tool execution failure returns ToolResult with success=False.
        """
        # Use MagicMock for response since json() is synchronous
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tool_name": "test_tool",
            "success": False,
            "error": "Tool execution failed",
            "execution_time_ms": 50,
        }
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        result = await ai_agents_client.execute_tool("test_tool", {})

        assert result.success is False
        assert result.error == "Tool execution failed"


# =============================================================================
# Import Tests
# =============================================================================


class TestAIAgentsImportable:
    """Tests for exports."""

    def test_ai_agents_client_importable_from_clients(self) -> None:
        """
        AIAgentsClient importable from src.clients.
        """
        from src.clients import AIAgentsClient
        assert AIAgentsClient is not None

    def test_tool_result_importable(self) -> None:
        """
        ToolResult importable from src.clients.
        """
        from src.clients import ToolResult
        assert ToolResult is not None

    def test_tool_definition_importable(self) -> None:
        """
        ToolDefinition importable from src.clients.
        """
        from src.clients import ToolDefinition
        assert ToolDefinition is not None

    def test_tool_schema_importable(self) -> None:
        """
        ToolSchema importable from src.clients.
        """
        from src.clients import ToolSchema
        assert ToolSchema is not None

    def test_ai_agents_error_importable(self) -> None:
        """
        AIAgentsError importable from src.clients.
        """
        from src.clients import AIAgentsError
        assert AIAgentsError is not None
