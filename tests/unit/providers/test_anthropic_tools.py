"""
Tests for Anthropic Provider Tool Handling - WBS 2.3.2.2

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Lines 41, 209-213 - Anthropic adapter, tool-use orchestrator
- GUIDELINES pp. 1510-1590: Tool patterns and agent architectures
- Anthropic API: tool_use/tool_result content block format
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Format Differences (OpenAI → Anthropic):
- Tool definition: function.parameters → input_schema
- Tool use response: tool_calls[] → content blocks type="tool_use"
- Tool result: role="tool" → role="user" with type="tool_result"

Test Categories:
- Tool definition transformation (2.3.2.2.1, 2.3.2.2.4)
- Tool use response parsing (2.3.2.2.2, 2.3.2.2.5)
- Tool result message formatting (2.3.2.2.3)
"""

import pytest
from typing import Any


# =============================================================================
# WBS 2.3.2.2.4: Test tools transformed correctly
# =============================================================================


class TestToolDefinitionTransformation:
    """Tests for transforming OpenAI tool format to Anthropic format."""

    def test_transform_single_tool_to_anthropic_format(self) -> None:
        """
        WBS 2.3.2.2.1, 2.3.2.2.4: Transform single tool definition.

        OpenAI format: {"type": "function", "function": {"name": ..., "parameters": ...}}
        Anthropic format: {"name": ..., "input_schema": ...}
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"],
                },
            },
        }

        handler = AnthropicToolHandler()
        anthropic_tool = handler.transform_tool_definition(openai_tool)

        assert anthropic_tool["name"] == "get_weather"
        assert anthropic_tool["description"] == "Get weather for a location"
        assert "input_schema" in anthropic_tool
        assert anthropic_tool["input_schema"]["type"] == "object"
        assert "location" in anthropic_tool["input_schema"]["properties"]

    def test_transform_tool_without_description(self) -> None:
        """
        WBS 2.3.2.2.1: Handle tool without description.

        Pattern: Optional[T] with None default (ANTI_PATTERN §1.1)
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "simple_tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }

        handler = AnthropicToolHandler()
        anthropic_tool = handler.transform_tool_definition(openai_tool)

        assert anthropic_tool["name"] == "simple_tool"
        # Description should be empty string or absent, not cause error
        assert anthropic_tool.get("description") in (None, "")

    def test_transform_tool_without_parameters(self) -> None:
        """
        WBS 2.3.2.2.1: Handle tool without parameters (no-arg tool).
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get current time",
            },
        }

        handler = AnthropicToolHandler()
        anthropic_tool = handler.transform_tool_definition(openai_tool)

        assert anthropic_tool["name"] == "get_time"
        # input_schema should have empty object type
        assert anthropic_tool["input_schema"]["type"] == "object"
        assert anthropic_tool["input_schema"].get("properties", {}) == {}

    def test_transform_multiple_tools(self) -> None:
        """
        WBS 2.3.2.2.1: Transform list of tools.
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool_a",
                    "description": "First tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_b",
                    "description": "Second tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

        handler = AnthropicToolHandler()
        anthropic_tools = handler.transform_tools(openai_tools)

        assert len(anthropic_tools) == 2
        assert anthropic_tools[0]["name"] == "tool_a"
        assert anthropic_tools[1]["name"] == "tool_b"

    def test_transform_tool_preserves_complex_schema(self) -> None:
        """
        WBS 2.3.2.2.1: Preserve complex JSON Schema properties.
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search documents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "filters": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["query"],
                },
            },
        }

        handler = AnthropicToolHandler()
        anthropic_tool = handler.transform_tool_definition(openai_tool)

        schema = anthropic_tool["input_schema"]
        assert schema["properties"]["limit"]["minimum"] == 1
        assert schema["properties"]["filters"]["type"] == "array"
        assert schema["required"] == ["query"]


# =============================================================================
# WBS 2.3.2.2.5: Test tool_use parsed correctly
# =============================================================================


class TestToolUseResponseParsing:
    """Tests for parsing Anthropic tool_use responses to OpenAI format."""

    def test_parse_single_tool_use_block(self) -> None:
        """
        WBS 2.3.2.2.2, 2.3.2.2.5: Parse single tool_use content block.

        Anthropic format: content block with type="tool_use"
        OpenAI format: tool_calls array in message
        """
        from src.providers.anthropic import AnthropicToolHandler

        anthropic_content = [
            {
                "type": "tool_use",
                "id": "toolu_01abc123",
                "name": "get_weather",
                "input": {"location": "San Francisco"},
            }
        ]

        handler = AnthropicToolHandler()
        tool_calls = handler.parse_tool_use_response(anthropic_content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "toolu_01abc123"
        assert tool_calls[0]["type"] == "function"
        assert tool_calls[0]["function"]["name"] == "get_weather"
        assert tool_calls[0]["function"]["arguments"] == '{"location": "San Francisco"}'

    def test_parse_multiple_tool_use_blocks(self) -> None:
        """
        WBS 2.3.2.2.2: Parse multiple parallel tool uses.
        """
        from src.providers.anthropic import AnthropicToolHandler

        anthropic_content = [
            {
                "type": "text",
                "text": "I'll check the weather in both cities.",
            },
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "get_weather",
                "input": {"location": "San Francisco"},
            },
            {
                "type": "tool_use",
                "id": "toolu_02",
                "name": "get_weather",
                "input": {"location": "New York"},
            },
        ]

        handler = AnthropicToolHandler()
        tool_calls = handler.parse_tool_use_response(anthropic_content)

        assert len(tool_calls) == 2
        assert tool_calls[0]["id"] == "toolu_01"
        assert tool_calls[1]["id"] == "toolu_02"

    def test_parse_tool_use_with_complex_input(self) -> None:
        """
        WBS 2.3.2.2.2: Handle complex nested input objects.
        """
        from src.providers.anthropic import AnthropicToolHandler

        anthropic_content = [
            {
                "type": "tool_use",
                "id": "toolu_complex",
                "name": "search",
                "input": {
                    "query": "test query",
                    "filters": ["filter1", "filter2"],
                    "options": {"limit": 10, "offset": 0},
                },
            }
        ]

        handler = AnthropicToolHandler()
        tool_calls = handler.parse_tool_use_response(anthropic_content)

        import json

        args = json.loads(tool_calls[0]["function"]["arguments"])
        assert args["query"] == "test query"
        assert args["filters"] == ["filter1", "filter2"]
        assert args["options"]["limit"] == 10

    def test_parse_content_without_tool_use(self) -> None:
        """
        WBS 2.3.2.2.2: Handle response with no tool_use blocks.
        """
        from src.providers.anthropic import AnthropicToolHandler

        anthropic_content = [{"type": "text", "text": "Just a regular response."}]

        handler = AnthropicToolHandler()
        tool_calls = handler.parse_tool_use_response(anthropic_content)

        assert tool_calls == []

    def test_parse_extracts_text_content(self) -> None:
        """
        WBS 2.3.2.2.2: Extract text content alongside tool uses.
        """
        from src.providers.anthropic import AnthropicToolHandler

        anthropic_content = [
            {"type": "text", "text": "Let me help with that."},
            {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "helper",
                "input": {},
            },
        ]

        handler = AnthropicToolHandler()
        text_content = handler.extract_text_content(anthropic_content)

        assert text_content == "Let me help with that."


# =============================================================================
# WBS 2.3.2.2.3: Test tool_result message formatting
# =============================================================================


class TestToolResultFormatting:
    """Tests for formatting tool results for Anthropic API."""

    def test_format_single_tool_result(self) -> None:
        """
        WBS 2.3.2.2.3: Format single tool result message.

        OpenAI format: {"role": "tool", "tool_call_id": ..., "content": ...}
        Anthropic format: {"role": "user", "content": [{"type": "tool_result", ...}]}
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool_message = {
            "role": "tool",
            "tool_call_id": "toolu_01abc123",
            "content": '{"temperature": 72, "unit": "F"}',
        }

        handler = AnthropicToolHandler()
        anthropic_message = handler.format_tool_result_message(openai_tool_message)

        assert anthropic_message["role"] == "user"
        content = anthropic_message["content"]
        assert len(content) == 1
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "toolu_01abc123"
        assert content[0]["content"] == '{"temperature": 72, "unit": "F"}'

    def test_format_tool_result_with_error(self) -> None:
        """
        WBS 2.3.2.2.3: Format tool result indicating error.
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool_message = {
            "role": "tool",
            "tool_call_id": "toolu_error",
            "content": '{"error": "Location not found"}',
        }

        handler = AnthropicToolHandler()
        anthropic_message = handler.format_tool_result_message(openai_tool_message)

        content = anthropic_message["content"][0]
        assert content["tool_use_id"] == "toolu_error"
        # Error content should be preserved
        assert "error" in content["content"]

    def test_format_multiple_tool_results(self) -> None:
        """
        WBS 2.3.2.2.3: Format multiple tool results into single message.
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool_messages = [
            {
                "role": "tool",
                "tool_call_id": "toolu_01",
                "content": '{"result": "first"}',
            },
            {
                "role": "tool",
                "tool_call_id": "toolu_02",
                "content": '{"result": "second"}',
            },
        ]

        handler = AnthropicToolHandler()
        anthropic_message = handler.format_tool_results(openai_tool_messages)

        assert anthropic_message["role"] == "user"
        content = anthropic_message["content"]
        assert len(content) == 2
        assert content[0]["tool_use_id"] == "toolu_01"
        assert content[1]["tool_use_id"] == "toolu_02"

    def test_format_tool_result_with_is_error_flag(self) -> None:
        """
        WBS 2.3.2.2.3: Support Anthropic's is_error flag.
        """
        from src.providers.anthropic import AnthropicToolHandler

        handler = AnthropicToolHandler()
        anthropic_message = handler.format_tool_result(
            tool_use_id="toolu_fail",
            content="Tool execution failed: timeout",
            is_error=True,
        )

        assert anthropic_message["type"] == "tool_result"
        assert anthropic_message["tool_use_id"] == "toolu_fail"
        assert anthropic_message["is_error"] is True


# =============================================================================
# Integration Tests
# =============================================================================


class TestToolHandlerIntegration:
    """Integration tests for complete tool handling flow."""

    def test_round_trip_tool_definition(self) -> None:
        """
        Integration: OpenAI tool → Anthropic → validates correctly.
        """
        from src.providers.anthropic import AnthropicToolHandler

        openai_tool = {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform calculation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"},
                    },
                    "required": ["expression"],
                },
            },
        }

        handler = AnthropicToolHandler()
        anthropic_tool = handler.transform_tool_definition(openai_tool)

        # Validate Anthropic format structure
        assert "name" in anthropic_tool
        assert "input_schema" in anthropic_tool
        assert "type" not in anthropic_tool  # No wrapper type

    def test_handler_can_be_instantiated(self) -> None:
        """
        Basic test: AnthropicToolHandler can be created.
        """
        from src.providers.anthropic import AnthropicToolHandler

        handler = AnthropicToolHandler()
        assert handler is not None

