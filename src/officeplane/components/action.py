"""
ComponentAction - Typed action abstraction for components.

Each action has:
- name: Unique identifier
- description: Human/LLM-readable description
- input_model: Pydantic model for input validation
- output_model: Pydantic model for output
- handler: The actual implementation

Actions can be exported as:
- Function calling tool specs (OpenAI-compatible)
- MCP tool specs
"""

from __future__ import annotations

import asyncio
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Field

from officeplane.components.context import ComponentContext

# Type variables for input/output models
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

# Handler type: sync or async callable
SyncHandler = Callable[[ComponentContext, InputT], OutputT]
AsyncHandler = Callable[[ComponentContext, InputT], Awaitable[OutputT]]
Handler = Union[SyncHandler[InputT, OutputT], AsyncHandler[InputT, OutputT]]


class ComponentAction(Generic[InputT, OutputT]):
    """
    A typed action that can be invoked on a component.

    Actions are the building blocks of components. They define
    a clear interface (input/output models) and can be exported
    as tool specifications for LLMs.
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_model: Type[InputT],
        output_model: Type[OutputT],
        handler: Handler[InputT, OutputT],
        examples: Optional[list] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.handler = handler
        self.examples = examples or []
        self._is_async = asyncio.iscoroutinefunction(handler)

    def __repr__(self) -> str:
        return f"ComponentAction(name={self.name!r})"

    async def invoke(self, ctx: ComponentContext, input_data: InputT) -> OutputT:
        """
        Invoke the action with validated input.

        Args:
            ctx: Component context
            input_data: Validated input model instance

        Returns:
            Output model instance
        """
        if self._is_async:
            return await self.handler(ctx, input_data)  # type: ignore
        else:
            # Run sync handler in executor to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.handler(ctx, input_data),  # type: ignore
            )

    def invoke_sync(self, ctx: ComponentContext, input_data: InputT) -> OutputT:
        """
        Synchronously invoke the action.

        Args:
            ctx: Component context
            input_data: Validated input model instance

        Returns:
            Output model instance
        """
        if self._is_async:
            # Run async handler in new event loop
            return asyncio.run(self.handler(ctx, input_data))  # type: ignore
        else:
            return self.handler(ctx, input_data)  # type: ignore

    def validate_input(self, data: Dict[str, Any]) -> InputT:
        """Validate and parse input data into the input model."""
        return self.input_model.model_validate(data)

    def to_function_tool(self) -> Dict[str, Any]:
        """
        Export as OpenAI function calling tool specification.

        Returns a dict compatible with OpenAI's tool format:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": { JSON Schema }
            }
        }
        """
        schema = self.input_model.model_json_schema()

        # Clean up schema for OpenAI compatibility
        if "title" in schema:
            del schema["title"]

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def to_mcp_tool(self) -> Dict[str, Any]:
        """
        Export as MCP (Model Context Protocol) tool specification.

        Returns a dict compatible with MCP's tool format:
        {
            "name": "...",
            "description": "...",
            "inputSchema": { JSON Schema }
        }
        """
        schema = self.input_model.model_json_schema()

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": schema,
        }

    def to_anthropic_tool(self) -> Dict[str, Any]:
        """
        Export as Anthropic tool specification.

        Returns a dict compatible with Anthropic's tool format:
        {
            "name": "...",
            "description": "...",
            "input_schema": { JSON Schema }
        }
        """
        schema = self.input_model.model_json_schema()

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
        }


def action(
    name: str,
    description: str,
    input_model: Type[InputT],
    output_model: Type[OutputT],
    examples: Optional[list] = None,
) -> Callable[[Handler[InputT, OutputT]], ComponentAction[InputT, OutputT]]:
    """
    Decorator to create a ComponentAction from a function.

    Usage:
        @action(
            name="convert_to_pdf",
            description="Convert an Office document to PDF",
            input_model=ConvertInput,
            output_model=ConvertOutput,
        )
        def convert_to_pdf(ctx: ComponentContext, input: ConvertInput) -> ConvertOutput:
            ...
    """

    def decorator(func: Handler[InputT, OutputT]) -> ComponentAction[InputT, OutputT]:
        return ComponentAction(
            name=name,
            description=description,
            input_model=input_model,
            output_model=output_model,
            handler=func,
            examples=examples,
        )

    return decorator


# Common input/output models for reuse

class EmptyInput(BaseModel):
    """Empty input for actions that take no parameters."""

    pass


class EmptyOutput(BaseModel):
    """Empty output for actions that return nothing."""

    pass


class MemoryInput(BaseModel):
    """Input for memory operations."""

    key: str = Field(..., description="The key to store/retrieve")
    value: Optional[Any] = Field(None, description="The value to store (for remember)")


class MemoryOutput(BaseModel):
    """Output for memory operations."""

    key: str
    value: Optional[Any] = None
    success: bool = True


class StoreInput(BaseModel):
    """Input for artifact storage."""

    name: str = Field(..., description="Name of the artifact")
    data_base64: str = Field(..., description="Base64-encoded data")
    content_type: str = Field("application/octet-stream", description="MIME type")


class StoreOutput(BaseModel):
    """Output for artifact storage."""

    url: str = Field(..., description="URL to access the stored artifact")
    name: str
    size_bytes: int
