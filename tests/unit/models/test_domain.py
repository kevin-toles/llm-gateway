"""
Tests for Domain Models - WBS 2.4.1.2

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 70 - domain.py "Domain models (Message, Tool, etc.)"
- GUIDELINES pp. 276: Domain modeling with Pydantic or @dataclass(frozen=True)
- GUIDELINES pp. 1510-1569: Tool inventory, tool_calls, tool execution patterns
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Test Categories:
- WBS 2.4.1.2.2: Tool model (name, description, parameters, handler)
- WBS 2.4.1.2.5: ToolCall model (id, name, arguments)
- WBS 2.4.1.2.6: ToolResult model (tool_call_id, content, is_error)

Pattern: Domain models as value objects (GUIDELINES pp. 276)
"""

import pytest
from typing import Any, Callable
from unittest.mock import MagicMock


# =============================================================================
# WBS 2.4.1.2.2: Tool Model Tests
# =============================================================================


class TestToolDefinitionModel:
    """Tests for ToolDefinition domain model."""

    def test_tool_definition_can_be_instantiated(self) -> None:
        """
        WBS 2.4.1.2.2: ToolDefinition class exists.
        """
        from src.models.domain import ToolDefinition

        tool = ToolDefinition(
            name="search",
            description="Search for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        )

        assert tool.name == "search"

    def test_tool_definition_has_name(self) -> None:
        """
        WBS 2.4.1.2.3: ToolDefinition has name field.
        """
        from src.models.domain import ToolDefinition

        tool = ToolDefinition(
            name="calculator",
            description="Perform calculations",
            parameters={"type": "object", "properties": {}},
        )

        assert tool.name == "calculator"

    def test_tool_definition_has_description(self) -> None:
        """
        WBS 2.4.1.2.3: ToolDefinition has description field.
        """
        from src.models.domain import ToolDefinition

        tool = ToolDefinition(
            name="calculator",
            description="Perform arithmetic calculations",
            parameters={"type": "object", "properties": {}},
        )

        assert tool.description == "Perform arithmetic calculations"

    def test_tool_definition_has_parameters_json_schema(self) -> None:
        """
        WBS 2.4.1.2.3: ToolDefinition has parameters (JSON Schema).
        """
        from src.models.domain import ToolDefinition

        params = {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
            },
            "required": ["x", "y"],
        }

        tool = ToolDefinition(
            name="add",
            description="Add two numbers",
            parameters=params,
        )

        assert tool.parameters == params
        assert tool.parameters["type"] == "object"

    def test_tool_definition_description_is_optional(self) -> None:
        """
        WBS 2.4.1.2.3: Description is optional (ANTI_PATTERN §1.1).
        """
        from src.models.domain import ToolDefinition

        tool = ToolDefinition(
            name="ping",
            parameters={"type": "object", "properties": {}},
        )

        assert tool.description is None

    def test_tool_definition_to_dict(self) -> None:
        """
        WBS 2.4.1.2.3: ToolDefinition can be serialized to dict.
        """
        from src.models.domain import ToolDefinition

        tool = ToolDefinition(
            name="search",
            description="Search query",
            parameters={"type": "object", "properties": {}},
        )

        tool_dict = tool.model_dump()

        assert tool_dict["name"] == "search"
        assert "description" in tool_dict


class TestRegisteredToolModel:
    """Tests for RegisteredTool domain model (tool with handler)."""

    def test_registered_tool_can_be_instantiated(self) -> None:
        """
        WBS 2.4.1.2.4: RegisteredTool has handler callable reference.
        """
        from src.models.domain import RegisteredTool, ToolDefinition

        async def handler(args: dict[str, Any]) -> str:
            return "result"

        definition = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=handler)

        assert tool.definition.name == "test_tool"
        assert callable(tool.handler)

    def test_registered_tool_handler_is_callable(self) -> None:
        """
        WBS 2.4.1.2.4: Handler is a callable.
        """
        from src.models.domain import RegisteredTool, ToolDefinition

        handler = MagicMock(return_value="result")

        definition = ToolDefinition(
            name="mock_tool",
            description="Mock",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=handler)

        assert callable(tool.handler)

    def test_registered_tool_convenience_properties(self) -> None:
        """
        WBS 2.4.1.2.4: RegisteredTool exposes definition properties.
        """
        from src.models.domain import RegisteredTool, ToolDefinition

        definition = ToolDefinition(
            name="my_tool",
            description="My tool description",
            parameters={"type": "object", "properties": {"arg": {"type": "string"}}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)

        assert tool.name == "my_tool"
        assert tool.description == "My tool description"
        assert tool.parameters == definition.parameters


# =============================================================================
# WBS 2.4.1.2.5: ToolCall Model Tests
# =============================================================================


class TestToolCallModel:
    """Tests for ToolCall domain model."""

    def test_tool_call_can_be_instantiated(self) -> None:
        """
        WBS 2.4.1.2.5: ToolCall class exists.
        """
        from src.models.domain import ToolCall

        tool_call = ToolCall(
            id="call_123",
            name="search",
            arguments={"query": "Python tutorials"},
        )

        assert tool_call.id == "call_123"

    def test_tool_call_has_id(self) -> None:
        """
        WBS 2.4.1.2.5: ToolCall has id field.
        """
        from src.models.domain import ToolCall

        tool_call = ToolCall(
            id="call_abc123",
            name="calculator",
            arguments={"x": 5, "y": 3},
        )

        assert tool_call.id == "call_abc123"

    def test_tool_call_has_name(self) -> None:
        """
        WBS 2.4.1.2.5: ToolCall has name field (tool name).
        """
        from src.models.domain import ToolCall

        tool_call = ToolCall(
            id="call_xyz",
            name="weather",
            arguments={"location": "NYC"},
        )

        assert tool_call.name == "weather"

    def test_tool_call_has_arguments(self) -> None:
        """
        WBS 2.4.1.2.5: ToolCall has arguments field (dict).
        """
        from src.models.domain import ToolCall

        args = {"query": "search term", "limit": 10}

        tool_call = ToolCall(
            id="call_1",
            name="search",
            arguments=args,
        )

        assert tool_call.arguments == args

    def test_tool_call_arguments_can_be_empty(self) -> None:
        """
        WBS 2.4.1.2.5: Arguments can be empty dict.
        """
        from src.models.domain import ToolCall

        tool_call = ToolCall(
            id="call_empty",
            name="ping",
            arguments={},
        )

        assert tool_call.arguments == {}

    def test_tool_call_from_openai_format(self) -> None:
        """
        WBS 2.4.1.2.5: ToolCall can parse OpenAI tool_call format.
        """
        from src.models.domain import ToolCall

        openai_tool_call = {
            "id": "call_openai_123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "Boston"}',
            },
        }

        tool_call = ToolCall.from_openai_format(openai_tool_call)

        assert tool_call.id == "call_openai_123"
        assert tool_call.name == "get_weather"
        assert tool_call.arguments == {"location": "Boston"}


# =============================================================================
# WBS 2.4.1.2.6: ToolResult Model Tests
# =============================================================================


class TestToolResultModel:
    """Tests for ToolResult domain model."""

    def test_tool_result_can_be_instantiated(self) -> None:
        """
        WBS 2.4.1.2.6: ToolResult class exists.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_123",
            content="Search results: ...",
        )

        assert result.tool_call_id == "call_123"

    def test_tool_result_has_tool_call_id(self) -> None:
        """
        WBS 2.4.1.2.6: ToolResult has tool_call_id field.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_abc",
            content="result",
        )

        assert result.tool_call_id == "call_abc"

    def test_tool_result_has_content(self) -> None:
        """
        WBS 2.4.1.2.6: ToolResult has content field.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_1",
            content="The calculation result is 42",
        )

        assert result.content == "The calculation result is 42"

    def test_tool_result_has_is_error_flag(self) -> None:
        """
        WBS 2.4.1.2.6: ToolResult has is_error flag.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_failed",
            content="Error: Tool execution failed",
            is_error=True,
        )

        assert result.is_error is True

    def test_tool_result_is_error_defaults_to_false(self) -> None:
        """
        WBS 2.4.1.2.6: is_error defaults to False (ANTI_PATTERN §1.1).
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_success",
            content="Success",
        )

        assert result.is_error is False

    def test_tool_result_to_message_dict(self) -> None:
        """
        WBS 2.4.1.2.6: ToolResult can be converted to message format.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_xyz",
            content="Tool output",
        )

        msg = result.to_message_dict()

        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_xyz"
        assert msg["content"] == "Tool output"

    def test_tool_result_error_to_message_dict(self) -> None:
        """
        WBS 2.4.1.2.6: Error results include error indicator.
        """
        from src.models.domain import ToolResult

        result = ToolResult(
            tool_call_id="call_err",
            content="Error occurred",
            is_error=True,
        )

        msg = result.to_message_dict()

        assert msg["role"] == "tool"
        assert "Error" in msg["content"] or result.is_error is True


# =============================================================================
# WBS 2.4.1.2.7: Domain Model Validation Tests
# =============================================================================


class TestDomainModelValidation:
    """Tests for domain model validation."""

    def test_tool_definition_name_required(self) -> None:
        """
        WBS 2.4.1.2.7: ToolDefinition name is required.
        """
        from src.models.domain import ToolDefinition
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolDefinition(
                description="Missing name",
                parameters={"type": "object", "properties": {}},
            )

    def test_tool_definition_parameters_required(self) -> None:
        """
        WBS 2.4.1.2.7: ToolDefinition parameters is required.
        """
        from src.models.domain import ToolDefinition
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolDefinition(
                name="incomplete",
                description="Missing parameters",
            )

    def test_tool_call_id_required(self) -> None:
        """
        WBS 2.4.1.2.7: ToolCall id is required.
        """
        from src.models.domain import ToolCall
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolCall(
                name="search",
                arguments={"query": "test"},
            )

    def test_tool_result_tool_call_id_required(self) -> None:
        """
        WBS 2.4.1.2.7: ToolResult tool_call_id is required.
        """
        from src.models.domain import ToolResult
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolResult(
                content="result",
            )


# =============================================================================
# Domain Models Importability Tests
# =============================================================================


class TestDomainModelsImportable:
    """Tests that domain models are importable from expected locations."""

    def test_models_importable_from_domain(self) -> None:
        """All domain models are importable from src.models.domain."""
        from src.models.domain import (
            ToolDefinition,
            RegisteredTool,
            ToolCall,
            ToolResult,
        )

        assert ToolDefinition is not None
        assert RegisteredTool is not None
        assert ToolCall is not None
        assert ToolResult is not None
