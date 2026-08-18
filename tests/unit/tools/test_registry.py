"""
Tests for Tool Registry - WBS 2.4.1.1

TDD RED Phase: Tests written BEFORE implementation.

Reference Documents:
- ARCHITECTURE.md: Line 48 - registry.py "Tool registration"
- ARCHITECTURE.md: Line 85 - config/tools.json "Tool definitions"
- GUIDELINES pp. 1545: Tool inventory as service registry pattern
- GUIDELINES pp. 276: Service registry analogous to dependency injection

Test Categories:
- WBS 2.4.1.1.3: ToolRegistry class
- WBS 2.4.1.1.4: register(name, tool) method
- WBS 2.4.1.1.5: get(name) -> Tool method
- WBS 2.4.1.1.6: list() -> list[ToolDefinition] method
- WBS 2.4.1.1.7: has(name) -> bool method
- WBS 2.4.1.1.8: Load tools from config/tools.json on init
- WBS 2.4.1.1.9-11: RED tests for register/retrieve/list

Pattern: Service Registry (GUIDELINES pp. 1545)
"""

import pytest
from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock
import json


# =============================================================================
# WBS 2.4.1.1.3: ToolRegistry Class Tests
# =============================================================================


class TestToolRegistryClass:
    """Tests for ToolRegistry class structure."""

    def test_tool_registry_can_be_instantiated(self) -> None:
        """
        WBS 2.4.1.1.3: ToolRegistry class exists.
        """
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        assert registry is not None

    def test_tool_registry_starts_empty(self) -> None:
        """
        WBS 2.4.1.1.3: Registry starts with no registered tools.
        """
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        assert len(registry.list()) == 0

    def test_tool_registry_is_singleton_pattern(self) -> None:
        """
        WBS 2.4.1.1.3: Registry follows singleton-like access.
        """
        from src.tools.registry import get_tool_registry

        registry1 = get_tool_registry()
        registry2 = get_tool_registry()

        # Same instance returned
        assert registry1 is registry2


# =============================================================================
# WBS 2.4.1.1.4: register() Method Tests
# =============================================================================


class TestToolRegistryRegister:
    """Tests for register method."""

    def test_register_adds_tool(self) -> None:
        """
        WBS 2.4.1.1.9: Register and retrieve tool.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        async def handler(args: dict[str, Any]) -> str:
            return "result"

        definition = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=handler)

        registry.register("test_tool", tool)

        assert registry.has("test_tool")

    def test_register_with_name(self) -> None:
        """
        WBS 2.4.1.1.4: register(name, tool) uses provided name.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="original_name",
            description="Test",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)

        registry.register("custom_name", tool)

        assert registry.has("custom_name")
        assert not registry.has("original_name")

    def test_register_overwrites_existing(self) -> None:
        """
        WBS 2.4.1.1.4: Registering same name overwrites.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        def handler1(args: dict) -> str:
            return "v1"

        def handler2(args: dict) -> str:
            return "v2"

        definition1 = ToolDefinition(
            name="tool",
            description="Version 1",
            parameters={"type": "object", "properties": {}},
        )

        definition2 = ToolDefinition(
            name="tool",
            description="Version 2",
            parameters={"type": "object", "properties": {}},
        )

        registry.register("tool", RegisteredTool(definition=definition1, handler=handler1))
        registry.register("tool", RegisteredTool(definition=definition2, handler=handler2))

        tool = registry.get("tool")
        assert tool.description == "Version 2"


# =============================================================================
# WBS 2.4.1.1.5: get() Method Tests
# =============================================================================


class TestToolRegistryGet:
    """Tests for get method."""

    def test_get_returns_registered_tool(self) -> None:
        """
        WBS 2.4.1.1.5: get(name) returns registered tool.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="my_tool",
            description="My tool",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)

        registry.register("my_tool", tool)

        retrieved = registry.get("my_tool")

        assert retrieved is tool
        assert retrieved.name == "my_tool"

    def test_get_unknown_tool_raises_error(self) -> None:
        """
        WBS 2.4.1.1.10: get unknown tool raises error.
        """
        from src.tools.registry import ToolRegistry, ToolNotFoundError

        registry = ToolRegistry()

        with pytest.raises(ToolNotFoundError) as exc_info:
            registry.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_get_after_unregister_raises_error(self) -> None:
        """
        WBS 2.4.1.1.5: get after unregister raises error.
        """
        from src.tools.registry import ToolRegistry, ToolNotFoundError
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="temp_tool",
            description="Temporary",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)

        registry.register("temp_tool", tool)
        registry.unregister("temp_tool")

        with pytest.raises(ToolNotFoundError):
            registry.get("temp_tool")


# =============================================================================
# WBS 2.4.1.1.6: list() Method Tests
# =============================================================================


class TestToolRegistryList:
    """Tests for list method."""

    def test_list_returns_all_tool_definitions(self) -> None:
        """
        WBS 2.4.1.1.11: list returns all tools.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        for name in ["tool_a", "tool_b", "tool_c"]:
            definition = ToolDefinition(
                name=name,
                description=f"Description of {name}",
                parameters={"type": "object", "properties": {}},
            )
            tool = RegisteredTool(definition=definition, handler=lambda x: x)
            registry.register(name, tool)

        tools = registry.list()

        assert len(tools) == 3

    def test_list_returns_tool_definitions(self) -> None:
        """
        WBS 2.4.1.1.6: list() returns list[ToolDefinition].
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="search",
            description="Search tool",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)
        registry.register("search", tool)

        definitions = registry.list()

        assert len(definitions) == 1
        assert isinstance(definitions[0], ToolDefinition)
        assert definitions[0].name == "search"

    def test_list_empty_registry(self) -> None:
        """
        WBS 2.4.1.1.6: list() returns empty list for empty registry.
        """
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        assert registry.list() == []


# =============================================================================
# WBS 2.4.1.1.7: has() Method Tests
# =============================================================================


class TestToolRegistryHas:
    """Tests for has method."""

    def test_has_returns_true_for_registered_tool(self) -> None:
        """
        WBS 2.4.1.1.7: has(name) returns True for registered tool.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="existing",
            description="Exists",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)
        registry.register("existing", tool)

        assert registry.has("existing") is True

    def test_has_returns_false_for_unregistered_tool(self) -> None:
        """
        WBS 2.4.1.1.7: has(name) returns False for unregistered tool.
        """
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        assert registry.has("not_registered") is False

    def test_has_returns_false_after_unregister(self) -> None:
        """
        WBS 2.4.1.1.7: has returns False after unregister.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="temporary",
            description="Will be removed",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)
        registry.register("temporary", tool)
        registry.unregister("temporary")

        assert registry.has("temporary") is False


# =============================================================================
# WBS 2.4.1.1.8: Load from config/tools.json Tests
# =============================================================================


class TestToolRegistryLoadFromConfig:
    """Tests for loading tools from config file."""

    def test_load_from_json_file(self) -> None:
        """
        WBS 2.4.1.1.8: Load tools from config/tools.json on init.
        """
        from src.tools.registry import ToolRegistry
        from pathlib import Path
        from io import StringIO

        sample_config = {
            "tools": [
                {
                    "name": "search",
                    "description": "Search for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            ]
        }

        mock_file = StringIO(json.dumps(sample_config))

        with patch.object(Path, "exists", return_value=True), \
             patch("builtins.open", return_value=mock_file):

            registry = ToolRegistry()
            registry.load_from_file("config/tools.json")

        # Tool definitions should be loaded (handlers registered separately)
        # Note: This loads definitions only, not handlers
        assert registry.has_definition("search")

    def test_load_from_json_registers_definitions(self) -> None:
        """
        WBS 2.4.1.1.8: Loaded tools are retrievable as definitions.
        """
        from src.tools.registry import ToolRegistry
        from pathlib import Path
        from io import StringIO

        sample_config = {
            "tools": [
                {
                    "name": "calculator",
                    "description": "Perform math",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"}
                        }
                    }
                }
            ]
        }

        mock_file = StringIO(json.dumps(sample_config))

        with patch.object(Path, "exists", return_value=True), \
             patch("builtins.open", return_value=mock_file):

            registry = ToolRegistry()
            registry.load_from_file("config/tools.json")

        definition = registry.get_definition("calculator")
        assert definition.name == "calculator"
        assert definition.description == "Perform math"


# =============================================================================
# Error Classes Tests
# =============================================================================


class TestToolRegistryErrors:
    """Tests for registry error classes."""

    def test_tool_not_found_error_is_importable(self) -> None:
        """
        ToolNotFoundError is importable.
        """
        from src.tools.registry import ToolNotFoundError

        error = ToolNotFoundError("test_tool")
        assert "test_tool" in str(error)

    def test_tool_not_found_error_is_exception(self) -> None:
        """
        ToolNotFoundError is an Exception subclass.
        """
        from src.tools.registry import ToolNotFoundError

        assert issubclass(ToolNotFoundError, Exception)


# =============================================================================
# Unregister Tests
# =============================================================================


class TestToolRegistryUnregister:
    """Tests for unregister method."""

    def test_unregister_removes_tool(self) -> None:
        """
        Unregister removes tool from registry.
        """
        from src.tools.registry import ToolRegistry
        from src.models.domain import ToolDefinition, RegisteredTool

        registry = ToolRegistry()

        definition = ToolDefinition(
            name="to_remove",
            description="Will be removed",
            parameters={"type": "object", "properties": {}},
        )

        tool = RegisteredTool(definition=definition, handler=lambda x: x)
        registry.register("to_remove", tool)

        assert registry.has("to_remove")

        registry.unregister("to_remove")

        assert not registry.has("to_remove")

    def test_unregister_nonexistent_is_safe(self) -> None:
        """
        Unregister nonexistent tool does not raise error.
        """
        from src.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Should not raise
        registry.unregister("does_not_exist")


# =============================================================================
# Registry Importability Tests
# =============================================================================


class TestToolRegistryImportable:
    """Tests that registry is importable from expected locations."""

    def test_registry_importable_from_tools(self) -> None:
        """ToolRegistry is importable from src.tools."""
        from src.tools import ToolRegistry

        assert ToolRegistry is not None

    def test_get_tool_registry_importable(self) -> None:
        """get_tool_registry is importable from src.tools."""
        from src.tools import get_tool_registry

        assert callable(get_tool_registry)

    def test_error_importable_from_tools(self) -> None:
        """ToolNotFoundError is importable from src.tools."""
        from src.tools import ToolNotFoundError

        assert issubclass(ToolNotFoundError, Exception)
