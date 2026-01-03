"""
Tool Schema Adapters

Utilities for exporting component actions to various tool formats:
- OpenAI function calling
- MCP (Model Context Protocol)
- Anthropic tool use
- LangChain tools
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from officeplane.components.base import OfficeComponent
    from officeplane.components.action import ComponentAction


def to_openai_tools(components: List[OfficeComponent]) -> List[Dict[str, Any]]:
    """
    Export multiple components' actions as OpenAI function calling tools.

    Args:
        components: List of components to export

    Returns:
        List of OpenAI tool specifications
    """
    tools = []
    for component in components:
        for action in component.actions():
            tool = action.to_function_tool()
            # Prefix action name with component name for uniqueness
            tool["function"]["name"] = f"{component.name}.{action.name}"
            tools.append(tool)
    return tools


def to_mcp_tools(components: List[OfficeComponent]) -> List[Dict[str, Any]]:
    """
    Export multiple components' actions as MCP tool specifications.

    Args:
        components: List of components to export

    Returns:
        List of MCP tool specifications
    """
    tools = []
    for component in components:
        for action in component.actions():
            tool = action.to_mcp_tool()
            tool["name"] = f"{component.name}.{action.name}"
            tools.append(tool)
    return tools


def to_anthropic_tools(components: List[OfficeComponent]) -> List[Dict[str, Any]]:
    """
    Export multiple components' actions as Anthropic tool specifications.

    Args:
        components: List of components to export

    Returns:
        List of Anthropic tool specifications
    """
    tools = []
    for component in components:
        for action in component.actions():
            tool = action.to_anthropic_tool()
            tool["name"] = f"{component.name}.{action.name}"
            tools.append(tool)
    return tools


class MCPToolRegistry:
    """
    Registry for MCP tool registration.

    Allows components to register their actions as MCP tools
    that can be called by an MCP client.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Tuple[OfficeComponent, ComponentAction[Any, Any]]] = {}

    def register_component(self, component: OfficeComponent) -> None:
        """
        Register all actions from a component.

        Args:
            component: The component to register
        """
        for action in component.actions():
            tool_name = f"{component.name}.{action.name}"
            self._tools[tool_name] = action.to_mcp_tool()
            self._tools[tool_name]["name"] = tool_name

            # Store handler reference
            self._handlers[tool_name] = (component, action)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return all registered tool specifications."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Dict[str, Any] | None:
        """Get a tool specification by name."""
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        ctx: Any,
    ) -> Any:
        """
        Call a registered tool.

        Args:
            name: Tool name (component.action format)
            arguments: Tool arguments
            ctx: ComponentContext for execution

        Returns:
            Tool result
        """
        if name not in self._handlers:
            raise ValueError(f"Tool '{name}' not registered")

        component, action = self._handlers[name]
        validated_input = action.validate_input(arguments)
        return await action.invoke(ctx, validated_input)


class FunctionCallingDispatcher:
    """
    Dispatcher for handling LLM function calls.

    Parses function call responses from LLMs and routes them
    to the appropriate component action.
    """

    def __init__(self) -> None:
        self._components: Dict[str, OfficeComponent] = {}

    def register_component(self, component: OfficeComponent) -> None:
        """Register a component for dispatching."""
        self._components[component.name] = component

    def parse_tool_call(self, tool_call: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
        """
        Parse an OpenAI-style tool call.

        Args:
            tool_call: Tool call from LLM response

        Returns:
            Tuple of (component_name, action_name, arguments)
        """
        function = tool_call.get("function", {})
        full_name = function.get("name", "")
        arguments = function.get("arguments", "{}")

        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        # Parse component.action format
        if "." in full_name:
            component_name, action_name = full_name.split(".", 1)
        else:
            # Assume single component or default
            component_name = list(self._components.keys())[0] if self._components else ""
            action_name = full_name

        return component_name, action_name, arguments

    async def dispatch(
        self,
        tool_call: Dict[str, Any],
        ctx: Any,
    ) -> Any:
        """
        Dispatch a tool call to the appropriate component action.

        Args:
            tool_call: Tool call from LLM response
            ctx: ComponentContext for execution

        Returns:
            Action result
        """
        component_name, action_name, arguments = self.parse_tool_call(tool_call)

        if component_name not in self._components:
            raise ValueError(f"Component '{component_name}' not registered")

        component = self._components[component_name]
        return await component.execute(action_name, arguments, ctx)

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all tool specifications for registered components."""
        return to_openai_tools(list(self._components.values()))


def generate_tool_manifest(
    components: List[OfficeComponent],
    format: str = "openai",
) -> str:
    """
    Generate a JSON manifest of all tools.

    Args:
        components: List of components
        format: Output format ("openai", "mcp", "anthropic")

    Returns:
        JSON string of tool specifications
    """
    if format == "openai":
        tools = to_openai_tools(components)
    elif format == "mcp":
        tools = to_mcp_tools(components)
    elif format == "anthropic":
        tools = to_anthropic_tools(components)
    else:
        raise ValueError(f"Unknown format: {format}")

    return json.dumps(tools, indent=2)
