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

SonarQube Issues Addressed (December 2025):
- Issue 42 (python:S7503): echo_tool must be sync function (no await used)
- Issue 43 (python:S7503): calculator_tool must be sync function (no await used)
- Issue 44 (python:S1066): _validate_arguments merged nested if statements
"""

import inspect
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


class TestCalculatorTool:
    """Test suite for calculator tool - Issue 39"""

    def test_calculator_division_by_zero_raises_value_error(self):
        """
        Issue 39: Calculator tool should raise ValueError for division by zero.
        
        Division by zero is an error condition, not a valid result.
        Returning float("inf") hides the error and can cause downstream issues.
        
        Note: calculator_tool is now synchronous (Issue 43 fix - python:S7503)
        """
        from src.api.routes.tools import calculator_tool
        
        with pytest.raises(ValueError) as exc_info:
            calculator_tool(a=10.0, b=0.0, operation="divide")
        
        assert "division by zero" in str(exc_info.value).lower()

    def test_calculator_normal_division_works(self):
        """
        Calculator tool should perform normal division correctly.
        
        Note: calculator_tool is now synchronous (Issue 43 fix - python:S7503)
        """
        from src.api.routes.tools import calculator_tool
        
        result = calculator_tool(a=10.0, b=2.0, operation="divide")
        
        assert result["result"] == pytest.approx(5.0)
        assert result["operation"] == "divide"

    def test_calculator_addition_works(self):
        """
        Calculator tool should perform addition correctly.
        
        Note: calculator_tool is now synchronous (Issue 43 fix - python:S7503)
        """
        from src.api.routes.tools import calculator_tool
        
        result = calculator_tool(a=3.0, b=4.0, operation="add")
        
        assert result["result"] == pytest.approx(7.0)
        assert result["operation"] == "add"


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


# =============================================================================
# SonarQube Code Quality Tests - Issues 42-44
# Validates fixes for python:S7503 (unnecessary async) and python:S1066 (nested if)
# =============================================================================


class TestSonarQubeCodeQualityFixes:
    """
    Tests validating SonarQube code smell fixes.
    
    Reference: Comp_Static_Analysis_Report_20251203.md Issues 42-44
    - Issue 42: echo_tool should be sync (no await)
    - Issue 43: calculator_tool should be sync (no await)
    - Issue 44: _validate_arguments should merge nested if statements
    """

    def test_echo_tool_is_synchronous_function(self):
        """
        Issue 42 (python:S7503): echo_tool must be a regular sync function.
        
        Rationale: Function contains no await expressions, so async keyword
        is misleading and adds unnecessary coroutine overhead.
        
        Reference: GUIDELINES pp. 466, 618 - async/await only when awaiting
        """
        from src.api.routes.tools import echo_tool
        
        # Verify it's not a coroutine function
        assert not inspect.iscoroutinefunction(echo_tool), \
            "echo_tool should be sync (not async) - no await expressions used"
        
        # Verify it can be called synchronously
        result = echo_tool("test message")
        assert result == {"echoed": "test message"}

    def test_calculator_tool_is_synchronous_function(self):
        """
        Issue 43 (python:S7503): calculator_tool must be a regular sync function.
        
        Rationale: Function performs pure computation with no I/O,
        async keyword adds unnecessary overhead.
        
        Reference: GUIDELINES pp. 466, 618 - async/await only when awaiting
        """
        from src.api.routes.tools import calculator_tool
        
        # Verify it's not a coroutine function
        assert not inspect.iscoroutinefunction(calculator_tool), \
            "calculator_tool should be sync (not async) - no await expressions used"
        
        # Verify it can be called synchronously
        result = calculator_tool(5, 3, "add")
        assert result["result"] == 8  # Calculator returns additional metadata

    def test_validate_arguments_type_check_merged_conditional(self):
        """
        Issue 44 (python:S1066): validate_arguments uses merged if statement.
        
        Verifies the fix: `if expected_type and not self._check_type(...)` 
        instead of nested `if expected_type: if not self._check_type(...)`
        
        Reference: CODING_PATTERNS_ANALYSIS Anti-Pattern 2.1 - nested conditionals
        """
        from src.models.tools import ToolDefinition
        
        # Test that validation correctly handles type checking in single pass
        executor = ToolExecutorService()
        
        # Create a tool definition with type constraint
        definition = ToolDefinition(
            name="test_tool",
            description="Test tool for validation",
            parameters={
                "type": "object",
                "properties": {
                    "value": {"type": "number"}
                },
                "required": ["value"]
            }
        )
        
        # Valid type should pass
        valid, error = executor.validate_arguments(definition, {"value": 42})
        assert valid is True
        assert error is None
        
        # Invalid type should fail with clear message
        valid, error = executor.validate_arguments(definition, {"value": "not a number"})
        assert valid is False
        assert "expected number" in error

    def test_validate_arguments_handles_missing_type_gracefully(self):
        """
        Issue 44: Merged conditional handles None type correctly.
        
        When expected_type is None/missing, the merged `if expected_type and ...`
        short-circuits without calling _check_type.
        """
        from src.models.tools import ToolDefinition
        
        executor = ToolExecutorService()
        
        # Create tool definition without type constraint (type is missing)
        definition = ToolDefinition(
            name="test_tool",
            description="Test tool for validation",
            parameters={
                "type": "object",
                "properties": {
                    "value": {}  # No type specified
                }
            }
        )
        
        # Should pass regardless of value type
        valid, error = executor.validate_arguments(definition, {"value": "anything"})
        assert valid is True
        assert error is None
        
        valid, error = executor.validate_arguments(definition, {"value": 123})
        assert valid is True
        assert error is None


# =============================================================================
# SonarQube Code Quality Fixes - Batch 6 (Issue 46)
# =============================================================================


class TestSonarQubeCodeQualityFixesBatch6:
    """
    TDD RED Phase: Tests for SonarQube code smell fixes - Batch 6.
    
    Issue 46: tools.py:186 - Fix the syntax of this issue suppression comment
    Rule: python:S1134 - Suppression comments must use correct syntax
    
    Reference: CODING_PATTERNS_ANALYSIS.md Anti-Pattern 4.2
    Pattern: Use standard # noqa: CODE or # type: ignore[code] syntax
    """

    def test_tools_noqa_comments_have_valid_syntax(self) -> None:
        """
        Issue 46 (S1134): All noqa comments should have valid syntax.
        
        SonarQube expects specific suppression comment formats.
        Ruff/flake8 noqa comments are not recognized by SonarQube.
        
        Valid formats:
        - # noqa: A002  (Ruff/flake8 - valid for those tools)
        - # NOSONAR  (SonarQube suppression)
        - # type: ignore[error-code]  (mypy)
        
        The issue is that SonarQube is flagging line 186 because it sees
        a suppression comment it doesn't understand. We need to ensure
        SonarQube doesn't try to parse Ruff comments as SonarQube comments.
        """
        import re
        import inspect
        from src.api.routes import tools
        
        source = inspect.getsource(tools)
        
        # Check for malformed suppression comments that SonarQube might misinterpret
        # Valid: # noqa: CODE - explanation
        # Invalid: # noqa - explanation (without colon and code)
        
        lines = source.split('\n')
        invalid_noqa_lines = []
        
        for i, line in enumerate(lines, 1):
            # Check for noqa without code after it (which is invalid)
            if re.search(r'#\s*noqa\s*$', line, re.IGNORECASE):
                invalid_noqa_lines.append(i)
            # Check for noqa followed by text but no colon
            elif re.search(r'#\s*noqa\s+[^:]', line, re.IGNORECASE):
                # This could be valid like "# noqa: A002 - explanation"
                # But invalid if no colon at all
                if ':' not in line.split('noqa')[1].split()[0] if 'noqa' in line.lower() else False:
                    invalid_noqa_lines.append(i)
        
        assert len(invalid_noqa_lines) == 0, (
            f"Found invalid noqa comment syntax at lines: {invalid_noqa_lines}. "
            "Use format: # noqa: CODE - explanation"
        )

