"""
Tests for Tools Endpoints - WBS 2.2.4 Tools Endpoints

TDD RED Phase: These tests define expected behavior before implementation.

Reference Documents:
- GUIDELINES pp. 1489-1544: Agent tool execution patterns, tool inventories
- Percival & Gregory (Architecture Patterns) pp. 59-60, 155-157: Domain model, encapsulation
- Sinha (FastAPI) p. 89: Dependency injection for tool registry
- Buelta pp. 219-221: Command pattern for tool invocation

Anti-Patterns Avoided:
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None
- ANTI_PATTERN_ANALYSIS §3.1: No bare except clauses
- ANTI_PATTERN_ANALYSIS §4.1: Cognitive complexity < 15 per function
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import BaseModel

# RED Phase: These imports will fail until implementation
from src.api.routes.tools import router as tools_router
from src.api.routes.tools import ToolExecutorService, get_tool_executor
from src.models.tools import (
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolDefinition,
)


class TestToolsRouter:
    """Test suite for tools router setup - WBS 2.2.4.1"""

    # =========================================================================
    # WBS 2.2.4.1.1: Router Structure
    # =========================================================================

    def test_tools_router_is_fastapi_router(self):
        """
        WBS 2.2.4.1.1: Tools router must be a FastAPI APIRouter instance.

        Pattern: Router separation (Sinha p. 89)
        """
        from fastapi import APIRouter

        assert isinstance(tools_router, APIRouter)

    def test_tools_router_has_correct_prefix(self):
        """
        WBS 2.2.4.1.2: Tools router must use /v1/tools prefix.

        Pattern: API versioning
        """
        assert tools_router.prefix == "/v1/tools"

    def test_tools_router_has_correct_tags(self):
        """
        WBS 2.2.4.1.3: Tools router must have 'Tools' tag for OpenAPI docs.
        """
        assert "Tools" in tools_router.tags


class TestToolModels:
    """
    Test suite for tool models - WBS 2.2.4.2

    Pattern: Domain model with clear interfaces (Percival pp. 59-60)
    """

    # =========================================================================
    # WBS 2.2.4.2.1: ToolExecuteRequest Model
    # =========================================================================

    def test_tool_execute_request_model_exists(self):
        """WBS 2.2.4.2.1: ToolExecuteRequest model must exist."""
        assert issubclass(ToolExecuteRequest, BaseModel)

    def test_tool_execute_request_has_name_field(self):
        """WBS 2.2.4.2.1: ToolExecuteRequest must have 'name' field."""
        request = ToolExecuteRequest(name="test_tool", arguments={})
        assert request.name == "test_tool"

    def test_tool_execute_request_has_arguments_field(self):
        """WBS 2.2.4.2.1: ToolExecuteRequest must have 'arguments' field."""
        request = ToolExecuteRequest(name="test_tool", arguments={"key": "value"})
        assert request.arguments == {"key": "value"}

    def test_tool_execute_request_arguments_default_empty(self):
        """WBS 2.2.4.2.1: arguments should default to empty dict."""
        request = ToolExecuteRequest(name="test_tool")
        assert request.arguments == {}

    # =========================================================================
    # WBS 2.2.4.2.2: ToolExecuteResponse Model
    # =========================================================================

    def test_tool_execute_response_model_exists(self):
        """WBS 2.2.4.2.2: ToolExecuteResponse model must exist."""
        assert issubclass(ToolExecuteResponse, BaseModel)

    def test_tool_execute_response_has_name_field(self):
        """WBS 2.2.4.2.2: ToolExecuteResponse must have 'name' field."""
        response = ToolExecuteResponse(
            name="test_tool", result={"output": "value"}, success=True
        )
        assert response.name == "test_tool"

    def test_tool_execute_response_has_result_field(self):
        """WBS 2.2.4.2.2: ToolExecuteResponse must have 'result' field."""
        response = ToolExecuteResponse(
            name="test_tool", result={"output": "value"}, success=True
        )
        assert response.result == {"output": "value"}

    def test_tool_execute_response_has_success_field(self):
        """WBS 2.2.4.2.2: ToolExecuteResponse must have 'success' field."""
        response = ToolExecuteResponse(
            name="test_tool", result={}, success=True
        )
        assert response.success is True

    def test_tool_execute_response_has_error_field(self):
        """WBS 2.2.4.2.2: ToolExecuteResponse must have 'error' field for failures."""
        response = ToolExecuteResponse(
            name="test_tool", result=None, success=False, error="Tool failed"
        )
        assert response.error == "Tool failed"

    # =========================================================================
    # WBS 2.2.4.2.3: ToolDefinition Model
    # =========================================================================

    def test_tool_definition_model_exists(self):
        """WBS 2.2.4.2.3: ToolDefinition model must exist."""
        assert issubclass(ToolDefinition, BaseModel)

    def test_tool_definition_has_name_field(self):
        """WBS 2.2.4.2.3: ToolDefinition must have 'name' field."""
        definition = ToolDefinition(
            name="calculator",
            description="Performs calculations",
            parameters={"type": "object", "properties": {}},
        )
        assert definition.name == "calculator"

    def test_tool_definition_has_description_field(self):
        """WBS 2.2.4.2.3: ToolDefinition must have 'description' field."""
        definition = ToolDefinition(
            name="calculator",
            description="Performs calculations",
            parameters={"type": "object", "properties": {}},
        )
        assert definition.description == "Performs calculations"

    def test_tool_definition_has_parameters_field(self):
        """WBS 2.2.4.2.3: ToolDefinition must have 'parameters' JSON schema."""
        params = {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        }
        definition = ToolDefinition(
            name="calculator", description="Performs calculations", parameters=params
        )
        assert definition.parameters == params


class TestToolExecuteEndpoint:
    """Test suite for tool execution endpoint - WBS 2.2.4.3"""

    # =========================================================================
    # WBS 2.2.4.3.6: Execute Valid Tool
    # =========================================================================

    def test_execute_valid_tool_returns_200(self, client: TestClient):
        """
        WBS 2.2.4.3.6: POST /v1/tools/execute with valid tool returns 200.

        Pattern: Command pattern for tool invocation (Buelta p. 219)
        """
        payload = {"name": "echo", "arguments": {"message": "Hello"}}
        response = client.post("/v1/tools/execute", json=payload)
        assert response.status_code == status.HTTP_200_OK

    def test_execute_valid_tool_returns_result(self, client: TestClient):
        """
        WBS 2.2.4.3.6: Valid tool execution returns result in response.
        """
        payload = {"name": "echo", "arguments": {"message": "Hello"}}
        response = client.post("/v1/tools/execute", json=payload)
        data = response.json()

        assert data["name"] == "echo"
        assert data["success"] is True
        assert "result" in data

    # =========================================================================
    # WBS 2.2.4.3.7: Execute Unknown Tool Returns 404
    # =========================================================================

    def test_execute_unknown_tool_returns_404(self, client: TestClient):
        """
        WBS 2.2.4.3.7: POST /v1/tools/execute with unknown tool returns 404.

        Pattern: Tool registry validation (GUIDELINES p. 1544)
        """
        payload = {"name": "nonexistent_tool", "arguments": {}}
        response = client.post("/v1/tools/execute", json=payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_execute_unknown_tool_returns_error_detail(self, client: TestClient):
        """
        WBS 2.2.4.3.7: Unknown tool error includes tool name in detail.
        """
        payload = {"name": "nonexistent_tool", "arguments": {}}
        response = client.post("/v1/tools/execute", json=payload)
        data = response.json()

        assert "detail" in data
        assert "nonexistent_tool" in data["detail"]

    # =========================================================================
    # WBS 2.2.4.3.8: Invalid Arguments Returns 422
    # =========================================================================

    def test_execute_invalid_arguments_returns_422(self, client: TestClient):
        """
        WBS 2.2.4.3.8: POST /v1/tools/execute with invalid args returns 422.

        Pattern: Schema validation (Sinha pp. 193-195)
        """
        # Calculator requires 'a' and 'b' arguments
        payload = {"name": "calculator", "arguments": {"invalid_arg": "value"}}
        response = client.post("/v1/tools/execute", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_missing_required_arguments_returns_422(self, client: TestClient):
        """
        WBS 2.2.4.3.8: Missing required arguments returns 422.
        """
        # Calculator requires 'a' and 'b' arguments
        payload = {"name": "calculator", "arguments": {"a": 5}}  # Missing 'b'
        response = client.post("/v1/tools/execute", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_execute_wrong_argument_type_returns_422(self, client: TestClient):
        """
        WBS 2.2.4.3.8: Wrong argument type returns 422.
        """
        # Calculator expects numbers, not strings
        payload = {"name": "calculator", "arguments": {"a": "not_a_number", "b": 5}}
        response = client.post("/v1/tools/execute", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestToolExecutorService:
    """
    Test suite for ToolExecutorService - WBS 2.2.4.3

    Pattern: Service layer extraction (ANTI_PATTERN §4.1)
    Pattern: Tool registry as service registry (GUIDELINES p. 1544)
    """

    def test_tool_executor_service_exists(self):
        """
        WBS 2.2.4.3.4: ToolExecutorService must exist for tool execution.
        """
        service = ToolExecutorService()
        assert isinstance(service, ToolExecutorService)

    def test_tool_executor_has_registry(self):
        """
        WBS 2.2.4.3.2: ToolExecutorService must have tool registry.

        Pattern: Service registry (GUIDELINES p. 1544)
        """
        service = ToolExecutorService()
        assert hasattr(service, "get_tool")
        assert hasattr(service, "list_tools")

    def test_tool_executor_list_tools_returns_definitions(self):
        """
        WBS 2.2.4.3.2: list_tools must return ToolDefinition list.
        """
        service = ToolExecutorService()
        tools = service.list_tools()
        assert isinstance(tools, list)
        assert all(isinstance(t, ToolDefinition) for t in tools)

    def test_tool_executor_has_builtin_tools(self):
        """
        WBS 2.2.4.3.2: Service must have builtin tools (echo, calculator).
        """
        service = ToolExecutorService()
        tools = service.list_tools()
        tool_names = [t.name for t in tools]
        assert "echo" in tool_names
        assert "calculator" in tool_names

    @pytest.mark.asyncio
    async def test_tool_executor_execute_returns_response(self):
        """
        WBS 2.2.4.3.4: execute must return ToolExecuteResponse.
        """
        service = ToolExecutorService()
        request = ToolExecuteRequest(name="echo", arguments={"message": "test"})
        response = await service.execute(request)
        assert isinstance(response, ToolExecuteResponse)

    def test_get_tool_executor_returns_service(self):
        """
        WBS 2.2.4.3.4: get_tool_executor dependency must return ToolExecutorService.

        Pattern: Dependency injection factory (Sinha p. 90)
        """
        service = get_tool_executor()
        assert isinstance(service, ToolExecutorService)


class TestToolsListEndpoint:
    """Test suite for tools list endpoint"""

    def test_list_tools_returns_200(self, client: TestClient):
        """
        GET /v1/tools should return 200 with list of available tools.
        """
        response = client.get("/v1/tools")
        assert response.status_code == status.HTTP_200_OK

    def test_list_tools_returns_array(self, client: TestClient):
        """
        GET /v1/tools should return array of tool definitions.
        """
        response = client.get("/v1/tools")
        data = response.json()
        assert isinstance(data, list)

    def test_list_tools_includes_builtin_tools(self, client: TestClient):
        """
        GET /v1/tools should include builtin tools.
        """
        response = client.get("/v1/tools")
        data = response.json()
        tool_names = [t["name"] for t in data]
        assert "echo" in tool_names
        assert "calculator" in tool_names


# =============================================================================
# Fixtures - Following Repository Pattern for Test Doubles
# =============================================================================


@pytest.fixture
def client():
    """
    Create test client with tools router mounted.

    Pattern: FakeRepository (Architecture Patterns p. 157)
    """
    from fastapi import FastAPI
    from src.api.routes.tools import router as tools_router

    app = FastAPI()
    app.include_router(tools_router)

    return TestClient(app)
