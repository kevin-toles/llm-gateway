"""
Tool Registry - WBS 2.4.1.1 Registry Implementation

This module implements the tool registry for managing available tools.
The registry follows the service registry pattern for tool inventory
management.

Reference Documents:
- ARCHITECTURE.md: Line 48 - registry.py "Tool registration"
- ARCHITECTURE.md: Line 85 - config/tools.json "Tool definitions"
- GUIDELINES pp. 1545: Tool inventory as service registry pattern
- GUIDELINES pp. 276: Service registry analogous to dependency injection

Pattern: Service Registry (microservices pattern applied to tool management)
Pattern: Singleton for global registry access

The registry manages two types of entries:
1. Full RegisteredTool instances (with handlers) for execution
2. ToolDefinition instances (without handlers) for LLM tool schemas
"""

import json
import logging
from pathlib import Path
from typing import Optional

from src.models.domain import ToolDefinition, RegisteredTool

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found in the registry."""

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


# =============================================================================
# WBS 2.4.1.1.3: ToolRegistry Class
# =============================================================================


class ToolRegistry:
    """
    Registry for managing available tools.

    WBS 2.4.1.1.3: Implement ToolRegistry class.

    The registry maintains a collection of registered tools and their
    definitions. Tools can be registered with handlers for execution,
    or just definitions for LLM tool schemas.

    Pattern: Service Registry (GUIDELINES pp. 1545)
    Pattern: Tool inventory with callable handlers

    Attributes:
        _tools: Dictionary mapping tool names to RegisteredTool instances.
        _definitions: Dictionary mapping tool names to ToolDefinition instances.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register("search", search_tool)
        >>> tool = registry.get("search")
        >>> result = await tool.handler({"query": "test"})
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, RegisteredTool] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    # =========================================================================
    # WBS 2.4.1.1.4: register() Method
    # =========================================================================

    def register(self, name: str, tool: RegisteredTool) -> None:
        """
        Register a tool with the given name.

        WBS 2.4.1.1.4: Implement register(name, tool) method.

        Registers both the full tool (with handler) and its definition.
        If a tool with the same name exists, it is overwritten.

        Args:
            name: The name to register the tool under.
            tool: The RegisteredTool instance to register.

        Example:
            >>> registry.register("search", search_tool)
        """
        self._tools[name] = tool
        self._definitions[name] = tool.definition
        logger.debug(f"Registered tool: {name}")

    # =========================================================================
    # WBS 2.4.1.1.5: get() Method
    # =========================================================================

    def get(self, name: str) -> RegisteredTool:
        """
        Get a registered tool by name.

        WBS 2.4.1.1.5: Implement get(name) -> Tool method.

        Args:
            name: The name of the tool to retrieve.

        Returns:
            The RegisteredTool instance.

        Raises:
            ToolNotFoundError: If the tool is not registered.

        Example:
            >>> tool = registry.get("search")
            >>> result = await tool.handler({"query": "test"})
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    # =========================================================================
    # WBS 2.4.1.1.6: list() Method
    # =========================================================================

    def list(self) -> list[ToolDefinition]:
        """
        List all registered tool definitions.

        WBS 2.4.1.1.6: Implement list() -> list[ToolDefinition] method.

        Returns definitions for all registered tools, suitable for
        passing to LLM APIs as available tools.

        Returns:
            List of ToolDefinition instances.

        Example:
            >>> definitions = registry.list()
            >>> for tool in definitions:
            ...     print(tool.name, tool.description)
        """
        return list(self._definitions.values())

    # =========================================================================
    # WBS 2.4.1.1.7: has() Method
    # =========================================================================

    def has(self, name: str) -> bool:
        """
        Check if a tool is registered.

        WBS 2.4.1.1.7: Implement has(name) -> bool method.

        Args:
            name: The name of the tool to check.

        Returns:
            True if the tool is registered, False otherwise.

        Example:
            >>> if registry.has("search"):
            ...     tool = registry.get("search")
        """
        return name in self._tools

    # =========================================================================
    # Additional Methods
    # =========================================================================

    def unregister(self, name: str) -> None:
        """
        Remove a tool from the registry.

        Args:
            name: The name of the tool to remove.

        Note:
            Does not raise an error if the tool doesn't exist.
        """
        self._tools.pop(name, None)
        self._definitions.pop(name, None)
        logger.debug(f"Unregistered tool: {name}")

    def has_definition(self, name: str) -> bool:
        """
        Check if a tool definition exists.

        This includes tools loaded from config files that may not
        have handlers registered yet.

        Args:
            name: The name of the tool definition to check.

        Returns:
            True if the definition exists, False otherwise.
        """
        return name in self._definitions

    def get_definition(self, name: str) -> ToolDefinition:
        """
        Get a tool definition by name.

        Args:
            name: The name of the tool definition to retrieve.

        Returns:
            The ToolDefinition instance.

        Raises:
            ToolNotFoundError: If the definition doesn't exist.
        """
        if name not in self._definitions:
            raise ToolNotFoundError(name)
        return self._definitions[name]

    # =========================================================================
    # WBS 2.4.1.1.8: Load from config file
    # =========================================================================

    def load_from_file(self, filepath: str) -> None:
        """
        Load tool definitions from a JSON config file.

        WBS 2.4.1.1.8: Load tools from config/tools.json on init.

        The config file should have the format:
        {
            "tools": [
                {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": { ... JSON Schema ... }
                }
            ]
        }

        Note: This loads definitions only. Handlers must be registered
        separately using register() or register_handler().

        Args:
            filepath: Path to the JSON config file.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Tool config file not found: {filepath}")
            return

        with open(path) as f:
            config = json.load(f)

        tools = config.get("tools", [])
        for tool_data in tools:
            definition = ToolDefinition(
                name=tool_data["name"],
                description=tool_data.get("description"),
                parameters=tool_data.get("parameters", {"type": "object", "properties": {}}),
            )
            self._definitions[definition.name] = definition
            logger.debug(f"Loaded tool definition: {definition.name}")

        logger.info(f"Loaded {len(tools)} tool definitions from {filepath}")


# =============================================================================
# Singleton Access
# =============================================================================

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns the same ToolRegistry instance on every call (singleton pattern).

    Returns:
        The global ToolRegistry instance.

    Example:
        >>> registry = get_tool_registry()
        >>> registry.register("search", search_tool)
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def reset_tool_registry() -> None:
    """
    Reset the global tool registry.

    Primarily used for testing to ensure a clean state.
    """
    global _registry
    _registry = None
