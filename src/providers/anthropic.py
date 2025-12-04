"""
Anthropic Provider - WBS 2.3.2 Anthropic Claude Adapter

This module implements the Anthropic Claude provider adapter, including
tool handling for transformation between OpenAI and Anthropic formats.

Reference Documents:
- ARCHITECTURE.md: Line 41 - anthropic.py "Anthropic Claude adapter"
- ARCHITECTURE.md: Lines 209-213 - Tool-Use Orchestrator patterns
- GUIDELINES pp. 1510-1590: Tool patterns and agent architectures
- Anthropic API Docs: tool_use/tool_result content block format
- ANTI_PATTERN_ANALYSIS §1.1: Optional types with explicit None

Format Differences (OpenAI → Anthropic):
- Tool definition: function.parameters → input_schema
- Tool use response: tool_calls[] → content blocks type="tool_use"
- Tool result: role="tool" → role="user" with type="tool_result"
"""

import json
from typing import Any



# =============================================================================
# WBS 2.3.2.2: Anthropic Tool Handler
# =============================================================================


class AnthropicToolHandler:
    """
    Handler for transforming tools between OpenAI and Anthropic formats.

    WBS 2.3.2.2: Anthropic Tool Handling.

    This class provides methods to:
    - Transform OpenAI tool definitions to Anthropic format (2.3.2.2.1)
    - Parse Anthropic tool_use responses to OpenAI format (2.3.2.2.2)
    - Format tool results for Anthropic API (2.3.2.2.3)

    Pattern: Adapter pattern for format transformation
    Reference: GUIDELINES pp. 1510-1590 - Tool inventories as service registries

    Example:
        >>> handler = AnthropicToolHandler()
        >>> anthropic_tools = handler.transform_tools(openai_tools)
        >>> tool_calls = handler.parse_tool_use_response(content_blocks)
    """

    # =========================================================================
    # WBS 2.3.2.2.1: Tool Definition Transformation
    # =========================================================================

    def transform_tool_definition(self, openai_tool: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single OpenAI tool definition to Anthropic format.

        WBS 2.3.2.2.1: Implement tool definition transformation.

        Args:
            openai_tool: OpenAI format tool definition with structure:
                {
                    "type": "function",
                    "function": {
                        "name": str,
                        "description": Optional[str],
                        "parameters": Optional[dict]
                    }
                }

        Returns:
            Anthropic format tool definition:
                {
                    "name": str,
                    "description": Optional[str],
                    "input_schema": dict
                }

        Pattern: Adapter transformation (GUIDELINES pp. 1510-1590)
        """
        function_def = openai_tool.get("function", {})

        anthropic_tool: dict[str, Any] = {
            "name": function_def.get("name", ""),
            "input_schema": function_def.get(
                "parameters", {"type": "object", "properties": {}}
            ),
        }

        # Handle optional description - Pattern: Optional[T] (ANTI_PATTERN §1.1)
        description = function_def.get("description")
        if description:
            anthropic_tool["description"] = description

        # Ensure input_schema has required structure
        if "type" not in anthropic_tool["input_schema"]:
            anthropic_tool["input_schema"]["type"] = "object"
        if "properties" not in anthropic_tool["input_schema"]:
            anthropic_tool["input_schema"]["properties"] = {}

        return anthropic_tool

    def transform_tools(
        self, openai_tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Transform a list of OpenAI tools to Anthropic format.

        WBS 2.3.2.2.1: Batch tool transformation.

        Args:
            openai_tools: List of OpenAI format tool definitions.

        Returns:
            List of Anthropic format tool definitions.
        """
        return [self.transform_tool_definition(tool) for tool in openai_tools]

    # =========================================================================
    # WBS 2.3.2.2.2: Tool Use Response Parsing
    # =========================================================================

    def parse_tool_use_response(
        self, content_blocks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Parse Anthropic tool_use content blocks to OpenAI tool_calls format.

        WBS 2.3.2.2.2: Implement tool_use response parsing.

        Args:
            content_blocks: Anthropic response content array with structure:
                [
                    {"type": "text", "text": str},
                    {
                        "type": "tool_use",
                        "id": str,
                        "name": str,
                        "input": dict
                    }
                ]

        Returns:
            OpenAI format tool_calls array:
                [
                    {
                        "id": str,
                        "type": "function",
                        "function": {
                            "name": str,
                            "arguments": str (JSON)
                        }
                    }
                ]

        Pattern: Content block filtering and transformation
        """
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_call = {
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                }
                tool_calls.append(tool_call)

        return tool_calls

    def extract_text_content(self, content_blocks: list[dict[str, Any]]) -> str:
        """
        Extract text content from Anthropic content blocks.

        WBS 2.3.2.2.2: Extract text alongside tool uses.

        Args:
            content_blocks: Anthropic response content array.

        Returns:
            Concatenated text content from text blocks.
        """
        text_parts: list[str] = []

        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    text_parts.append(text)

        return " ".join(text_parts) if text_parts else ""

    # =========================================================================
    # WBS 2.3.2.2.3: Tool Result Message Formatting
    # =========================================================================

    def format_tool_result(
        self,
        tool_use_id: str,
        content: str,
        is_error: bool = False,
    ) -> dict[str, Any]:
        """
        Format a single tool result content block.

        WBS 2.3.2.2.3: Implement tool_result message formatting.

        Args:
            tool_use_id: The ID from the original tool_use block.
            content: The tool execution result (string or JSON string).
            is_error: Whether the result represents an error.

        Returns:
            Anthropic tool_result content block:
                {
                    "type": "tool_result",
                    "tool_use_id": str,
                    "content": str,
                    "is_error": Optional[bool]
                }

        Pattern: Content block construction for continuation
        """
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
        }

        if is_error:
            result["is_error"] = True

        return result

    def format_tool_result_message(
        self, openai_tool_message: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Transform OpenAI tool message to Anthropic user message with tool_result.

        WBS 2.3.2.2.3: Transform single tool result message.

        Args:
            openai_tool_message: OpenAI format tool message:
                {
                    "role": "tool",
                    "tool_call_id": str,
                    "content": str
                }

        Returns:
            Anthropic format user message with tool_result:
                {
                    "role": "user",
                    "content": [{"type": "tool_result", ...}]
                }

        Note: Anthropic requires tool results in user messages.
        """
        tool_result = self.format_tool_result(
            tool_use_id=openai_tool_message.get("tool_call_id", ""),
            content=openai_tool_message.get("content", ""),
        )

        return {"role": "user", "content": [tool_result]}

    def format_tool_results(
        self, openai_tool_messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Transform multiple OpenAI tool messages to single Anthropic message.

        WBS 2.3.2.2.3: Batch tool result formatting.

        Args:
            openai_tool_messages: List of OpenAI format tool messages.

        Returns:
            Single Anthropic user message with multiple tool_result blocks.

        Note: Anthropic expects all tool results in a single user message.
        """
        tool_results: list[dict[str, Any]] = []

        for msg in openai_tool_messages:
            tool_result = self.format_tool_result(
                tool_use_id=msg.get("tool_call_id", ""),
                content=msg.get("content", ""),
            )
            tool_results.append(tool_result)

        return {"role": "user", "content": tool_results}
