"""
OfficeComponent - Base class for document operation components.

Similar to a CrewAI Agent, an OfficeComponent has:
- name: Identifier
- purpose: Goal/objective (analogous to agent's goal)
- capabilities: List of actions it can perform

Components can be used in two modes:
1. Tool-provider mode: Export actions as function-call/MCP tool specs
2. Self-executing mode: Run with a tool-calling LLM via ComponentRunner
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


from officeplane.components.action import ComponentAction
from officeplane.components.context import ComponentContext


class OfficeComponent(ABC):
    """
    Base class for office document operation components.

    Subclasses define their capabilities by implementing the
    `_build_actions()` method to return a list of ComponentActions.
    """

    def __init__(
        self,
        name: str,
        purpose: str,
        description: Optional[str] = None,
    ) -> None:
        """
        Initialize the component.

        Args:
            name: Unique identifier for the component
            purpose: The goal/objective of this component (for LLM context)
            description: Optional longer description
        """
        self.name = name
        self.purpose = purpose
        self.description = description or purpose
        self._actions: Dict[str, ComponentAction] = {}
        self._build_actions()

    @abstractmethod
    def _build_actions(self) -> None:
        """
        Build and register the component's actions.

        Subclasses must implement this to register their actions
        using self._register_action().
        """
        raise NotImplementedError

    def _register_action(self, action: ComponentAction) -> None:
        """Register an action with this component."""
        self._actions[action.name] = action

    def actions(self) -> List[ComponentAction]:
        """Return all registered actions."""
        return list(self._actions.values())

    def get_action(self, name: str) -> Optional[ComponentAction]:
        """Get an action by name."""
        return self._actions.get(name)

    def action_names(self) -> List[str]:
        """Return names of all registered actions."""
        return list(self._actions.keys())

    async def execute(
        self,
        action_name: str,
        payload: Dict[str, Any],
        ctx: ComponentContext,
    ) -> Any:
        """
        Execute an action by name with the given payload.

        Args:
            action_name: Name of the action to execute
            payload: Input data (will be validated against action's input model)
            ctx: Component context

        Returns:
            The action's output model instance

        Raises:
            ValueError: If action not found
            ValidationError: If payload doesn't match input model
        """
        action = self._actions.get(action_name)
        if action is None:
            raise ValueError(
                f"Action '{action_name}' not found. "
                f"Available: {self.action_names()}"
            )

        # Validate and parse input
        validated_input = action.validate_input(payload)

        # Execute the action
        ctx.logger.info(f"Executing action: {action_name}")
        result = await action.invoke(ctx, validated_input)
        ctx.logger.info(f"Action {action_name} completed")

        return result

    def execute_sync(
        self,
        action_name: str,
        payload: Dict[str, Any],
        ctx: ComponentContext,
    ) -> Any:
        """
        Synchronously execute an action by name.

        Args:
            action_name: Name of the action to execute
            payload: Input data
            ctx: Component context

        Returns:
            The action's output model instance
        """
        action = self._actions.get(action_name)
        if action is None:
            raise ValueError(
                f"Action '{action_name}' not found. "
                f"Available: {self.action_names()}"
            )

        validated_input = action.validate_input(payload)
        ctx.logger.info(f"Executing action: {action_name}")
        result = action.invoke_sync(ctx, validated_input)
        ctx.logger.info(f"Action {action_name} completed")

        return result

    def to_function_tools(self) -> List[Dict[str, Any]]:
        """Export all actions as OpenAI function calling tool specs."""
        return [action.to_function_tool() for action in self.actions()]

    def to_mcp_tools(self) -> List[Dict[str, Any]]:
        """Export all actions as MCP tool specs."""
        return [action.to_mcp_tool() for action in self.actions()]

    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Export all actions as Anthropic tool specs."""
        return [action.to_anthropic_tool() for action in self.actions()]

    def system_prompt(self) -> str:
        """
        Generate a system prompt describing this component.

        Useful for LLM-driven mode to explain what the component does.
        """
        lines = [
            f"# {self.name}",
            "",
            f"**Purpose:** {self.purpose}",
            "",
            f"**Description:** {self.description}",
            "",
            "## Available Actions",
            "",
        ]

        for action in self.actions():
            lines.append(f"### {action.name}")
            lines.append(f"{action.description}")
            lines.append("")

            # Add input schema info
            schema = action.input_model.model_json_schema()
            if "properties" in schema:
                lines.append("**Parameters:**")
                for prop_name, prop_info in schema["properties"].items():
                    required = prop_name in schema.get("required", [])
                    req_str = " (required)" if required else ""
                    desc = prop_info.get("description", "")
                    lines.append(f"- `{prop_name}`{req_str}: {desc}")
                lines.append("")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, actions={self.action_names()})"
