"""
ComponentRunner - Self-executing mode for components.

Provides a protocol for running components with a tool-calling LLM,
without locking into a specific LLM SDK.

Usage:
    runner = ComponentRunner(
        components=[DocComponent()],
        llm=MyLLMAdapter(),  # Implements LLMProtocol
        ctx=context,
    )
    result = await runner.kickoff("Convert this document to PDF and render page 1")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from officeplane.components.base import OfficeComponent
from officeplane.components.context import ComponentContext


@runtime_checkable
class LLMProtocol(Protocol):
    """
    Protocol for LLM adapters.

    Implement this protocol to plug in any tool-calling LLM
    (OpenAI, Anthropic, local models, etc.)
    """

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Send messages to the LLM with available tools.

        Args:
            messages: List of message dicts (role, content)
            tools: List of tool specifications

        Returns:
            Response dict with:
            - content: Optional text response
            - tool_calls: Optional list of tool calls
            - finish_reason: "stop", "tool_calls", etc.
        """
        ...


@dataclass
class RunResult:
    """Result of a component runner execution."""

    success: bool
    output: Any = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls_made: int = 0
    error: Optional[str] = None


class ComponentRunner:
    """
    Runner for self-executing component mode.

    Orchestrates a conversation loop between an LLM and components,
    executing tool calls as the LLM requests them.
    """

    def __init__(
        self,
        components: List[OfficeComponent],
        llm: LLMProtocol,
        ctx: ComponentContext,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
    ) -> None:
        """
        Initialize the runner.

        Args:
            components: List of components to expose as tools
            llm: LLM adapter implementing LLMProtocol
            ctx: Component context for execution
            max_iterations: Maximum tool-call iterations
            system_prompt: Optional custom system prompt
        """
        self.components = {c.name: c for c in components}
        self.llm = llm
        self.ctx = ctx
        self.max_iterations = max_iterations

        # Build tools list
        self.tools: List[Dict[str, Any]] = []
        for component in components:
            for action in component.actions():
                tool = action.to_function_tool()
                tool["function"]["name"] = f"{component.name}.{action.name}"
                self.tools.append(tool)

        # Build system prompt
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self._build_system_prompt(components)

    def _build_system_prompt(self, components: List[OfficeComponent]) -> str:
        """Build a system prompt describing available components."""
        lines = [
            "You are an assistant that helps with office document operations.",
            "You have access to the following components and their actions:",
            "",
        ]

        for component in components:
            lines.append(f"## {component.name}")
            lines.append(f"Purpose: {component.purpose}")
            lines.append("")
            lines.append("Actions:")
            for action in component.actions():
                lines.append(f"- {component.name}.{action.name}: {action.description}")
            lines.append("")

        lines.extend([
            "When the user asks you to perform a task, use the appropriate tools.",
            "Always explain what you're doing before making tool calls.",
            "After completing the task, summarize what was done.",
        ])

        return "\n".join(lines)

    async def kickoff(self, task: str) -> RunResult:
        """
        Execute a task using the LLM and available components.

        Args:
            task: The user's task description

        Returns:
            RunResult with execution details
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        tool_calls_made = 0

        for iteration in range(self.max_iterations):
            try:
                response = await self.llm.chat(messages, self.tools)
            except Exception as e:
                return RunResult(
                    success=False,
                    messages=messages,
                    tool_calls_made=tool_calls_made,
                    error=f"LLM error: {e}",
                )

            # Handle text response
            if response.get("content"):
                messages.append({
                    "role": "assistant",
                    "content": response["content"],
                })

            # Check if done
            if response.get("finish_reason") == "stop":
                return RunResult(
                    success=True,
                    output=response.get("content"),
                    messages=messages,
                    tool_calls_made=tool_calls_made,
                )

            # Handle tool calls
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                # No tool calls and not stopped - assume done
                return RunResult(
                    success=True,
                    output=response.get("content"),
                    messages=messages,
                    tool_calls_made=tool_calls_made,
                )

            # Add assistant message with tool calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "tool_calls": tool_calls,
            }
            if response.get("content"):
                assistant_msg["content"] = response["content"]
            messages.append(assistant_msg)

            # Execute each tool call
            for tool_call in tool_calls:
                tool_calls_made += 1
                result = await self._execute_tool_call(tool_call)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "name": tool_call.get("function", {}).get("name", ""),
                    "content": json.dumps(result),
                })

        return RunResult(
            success=False,
            messages=messages,
            tool_calls_made=tool_calls_made,
            error=f"Max iterations ({self.max_iterations}) reached",
        )

    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool call and return the result."""
        try:
            function = tool_call.get("function", {})
            full_name = function.get("name", "")
            arguments = function.get("arguments", "{}")

            if isinstance(arguments, str):
                arguments = json.loads(arguments)

            # Parse component.action format
            if "." not in full_name:
                return {"error": f"Invalid tool name format: {full_name}"}

            component_name, action_name = full_name.split(".", 1)

            if component_name not in self.components:
                return {"error": f"Component not found: {component_name}"}

            component = self.components[component_name]
            result = await component.execute(action_name, arguments, self.ctx)

            # Convert Pydantic model to dict if needed
            if hasattr(result, "model_dump"):
                return dict(result.model_dump())
            if isinstance(result, dict):
                return result
            return {"result": result}

        except Exception as e:
            return {"error": str(e)}

    def kickoff_sync(self, task: str) -> RunResult:
        """Synchronous version of kickoff."""
        import asyncio
        return asyncio.run(self.kickoff(task))


class SimpleLLMAdapter:
    """
    Simple LLM adapter for testing.

    This is a mock that doesn't actually call an LLM - useful for testing
    the runner logic without API calls.
    """

    def __init__(self, responses: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Initialize with canned responses.

        Args:
            responses: List of responses to return in sequence
        """
        self.responses = responses or []
        self.call_count = 0

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return the next canned response."""
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response

        # Default: stop
        return {
            "content": "I've completed the task.",
            "finish_reason": "stop",
        }


# Example LLM adapters for common providers
# (These are templates - actual implementation would need SDK imports)


class OpenAIAdapter:
    """
    OpenAI API adapter template.

    Usage:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        adapter = OpenAIAdapter(client)
    """

    def __init__(self, client: Any, model: str = "gpt-4") -> None:
        self.client = client
        self.model = model

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
        )

        choice = response.choices[0]
        result: Dict[str, Any] = {
            "finish_reason": choice.finish_reason,
        }

        if choice.message.content:
            result["content"] = choice.message.content

        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result


class AnthropicAdapter:
    """
    Anthropic API adapter template.

    Usage:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        adapter = AnthropicAdapter(client)
    """

    def __init__(self, client: Any, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = client
        self.model = model

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Convert tools to Anthropic format
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"],
            })

        # Extract system message
        system = None
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                filtered_messages.append(msg)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=filtered_messages,
            tools=anthropic_tools if anthropic_tools else None,
        )

        result: Dict[str, Any] = {
            "finish_reason": response.stop_reason,
        }

        # Extract content and tool calls
        for block in response.content:
            if block.type == "text":
                result["content"] = block.text
            elif block.type == "tool_use":
                if "tool_calls" not in result:
                    result["tool_calls"] = []
                result["tool_calls"].append({
                    "id": block.id,
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    },
                })

        return result
