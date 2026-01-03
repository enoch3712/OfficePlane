"""
Tests for the OfficePlane Component Framework.

Tests cover:
- ComponentContext creation and usage
- ComponentMemory implementations
- ComponentAction creation and invocation
- DocComponent actions
- Tool schema export (OpenAI, MCP, Anthropic)
- ComponentRunner with mock LLM
"""

import base64
import pytest

from officeplane.components.context import ComponentContext
from officeplane.components.memory import InMemoryComponentMemory
from officeplane.components.action import ComponentAction, EmptyOutput
from officeplane.components.doc import DocComponent
from officeplane.components.adapters import (
    to_openai_tools,
    to_mcp_tools,
    MCPToolRegistry,
    FunctionCallingDispatcher,
)
from officeplane.components.runner import ComponentRunner, SimpleLLMAdapter
from officeplane.drivers.mock_driver import MockDriver
from officeplane.storage.local import LocalArtifactStore


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_driver():
    """Create a mock driver for testing."""
    return MockDriver()


@pytest.fixture
def temp_store(tmp_path):
    """Create a temporary artifact store."""
    return LocalArtifactStore(str(tmp_path))


@pytest.fixture
def memory():
    """Create an in-memory component memory."""
    return InMemoryComponentMemory()


@pytest.fixture
def context(mock_driver, temp_store, memory):
    """Create a component context for testing."""
    return ComponentContext.create(
        driver=mock_driver,
        store=temp_store,
        memory=memory,
        request_id="test-request-123",
    )


@pytest.fixture
def doc_component():
    """Create a DocComponent for testing."""
    return DocComponent()


# ============================================================
# ComponentContext Tests
# ============================================================


class TestComponentContext:
    def test_create_context(self, mock_driver, temp_store):
        """Test context creation with factory method."""
        ctx = ComponentContext.create(
            driver=mock_driver,
            store=temp_store,
        )

        assert ctx.request_id is not None
        assert ctx.driver is mock_driver
        assert ctx.store is temp_store
        assert ctx.memory is not None
        assert ctx.logger is not None

    def test_create_context_with_request_id(self, mock_driver, temp_store):
        """Test context creation with custom request_id."""
        ctx = ComponentContext.create(
            driver=mock_driver,
            store=temp_store,
            request_id="custom-id",
        )

        assert ctx.request_id == "custom-id"

    def test_context_extras(self, context):
        """Test context extras storage."""
        context.set_extra("key1", "value1")
        context.set_extra("key2", {"nested": True})

        assert context.get_extra("key1") == "value1"
        assert context.get_extra("key2") == {"nested": True}
        assert context.get_extra("missing", "default") == "default"

    def test_child_context(self, context):
        """Test creating child contexts."""
        child = context.child("sub-operation")

        assert child.request_id == f"{context.request_id}/sub-operation"
        assert child.driver is context.driver
        assert child.store is context.store
        assert child.memory is context.memory


# ============================================================
# ComponentMemory Tests
# ============================================================


class TestComponentMemory:
    def test_remember_recall(self, memory):
        """Test basic remember/recall operations."""
        memory.remember("key1", "value1")
        memory.remember("key2", {"complex": "data"})

        assert memory.recall("key1") == "value1"
        assert memory.recall("key2") == {"complex": "data"}
        assert memory.recall("missing") is None
        assert memory.recall("missing", "default") == "default"

    def test_forget(self, memory):
        """Test forget operation."""
        memory.remember("key", "value")
        assert memory.has("key")

        memory.forget("key")
        assert not memory.has("key")

    def test_list_keys(self, memory):
        """Test listing all keys."""
        memory.remember("a", 1)
        memory.remember("b", 2)
        memory.remember("c", 3)

        keys = memory.list_keys()
        assert set(keys) == {"a", "b", "c"}

    def test_clear(self, memory):
        """Test clearing all memory."""
        memory.remember("a", 1)
        memory.remember("b", 2)

        memory.clear()
        assert len(memory.list_keys()) == 0

    def test_remember_many(self, memory):
        """Test batch remember."""
        memory.remember_many({"a": 1, "b": 2, "c": 3})

        assert memory.recall("a") == 1
        assert memory.recall("b") == 2
        assert memory.recall("c") == 3

    def test_recall_many(self, memory):
        """Test batch recall."""
        memory.remember_many({"a": 1, "b": 2, "c": 3})

        result = memory.recall_many(["a", "c", "missing"])
        assert result == {"a": 1, "c": 3}


# ============================================================
# ComponentAction Tests
# ============================================================


class TestComponentAction:
    def test_create_action(self):
        """Test action creation."""
        from pydantic import BaseModel, Field

        class TestInput(BaseModel):
            name: str = Field(..., description="The name")

        class TestOutput(BaseModel):
            greeting: str

        def handler(ctx, input: TestInput) -> TestOutput:
            return TestOutput(greeting=f"Hello, {input.name}!")

        action = ComponentAction(
            name="greet",
            description="Greet someone by name",
            input_model=TestInput,
            output_model=TestOutput,
            handler=handler,
        )

        assert action.name == "greet"
        assert action.description == "Greet someone by name"

    def test_action_invoke_sync(self, context):
        """Test synchronous action invocation."""
        from pydantic import BaseModel

        class TestInput(BaseModel):
            value: int

        class TestOutput(BaseModel):
            result: int

        def handler(ctx, input: TestInput) -> TestOutput:
            return TestOutput(result=input.value * 2)

        action = ComponentAction(
            name="double",
            description="Double a number",
            input_model=TestInput,
            output_model=TestOutput,
            handler=handler,
        )

        input_data = action.validate_input({"value": 21})
        result = action.invoke_sync(context, input_data)

        assert result.result == 42

    def test_action_to_function_tool(self):
        """Test export to OpenAI function tool format."""
        from pydantic import BaseModel, Field

        class TestInput(BaseModel):
            name: str = Field(..., description="Person's name")
            age: int = Field(0, description="Person's age")

        action = ComponentAction(
            name="process",
            description="Process a person",
            input_model=TestInput,
            output_model=EmptyOutput,
            handler=lambda ctx, input: EmptyOutput(),
        )

        tool = action.to_function_tool()

        assert tool["type"] == "function"
        assert tool["function"]["name"] == "process"
        assert tool["function"]["description"] == "Process a person"
        assert "properties" in tool["function"]["parameters"]
        assert "name" in tool["function"]["parameters"]["properties"]

    def test_action_to_mcp_tool(self):
        """Test export to MCP tool format."""
        from pydantic import BaseModel

        class TestInput(BaseModel):
            query: str

        action = ComponentAction(
            name="search",
            description="Search for something",
            input_model=TestInput,
            output_model=EmptyOutput,
            handler=lambda ctx, input: EmptyOutput(),
        )

        tool = action.to_mcp_tool()

        assert tool["name"] == "search"
        assert tool["description"] == "Search for something"
        assert "inputSchema" in tool


# ============================================================
# DocComponent Tests
# ============================================================


class TestDocComponent:
    def test_doc_component_creation(self, doc_component):
        """Test DocComponent initialization."""
        assert doc_component.name == "doc"
        assert "convert" in doc_component.purpose.lower()

    def test_doc_component_actions(self, doc_component):
        """Test that all expected actions are registered."""
        action_names = doc_component.action_names()

        assert "convert_to_pdf" in action_names
        assert "render_pdf_to_images" in action_names
        assert "render_document" in action_names
        assert "store_bytes" in action_names
        assert "remember" in action_names
        assert "recall" in action_names

    def test_convert_to_pdf_action(self, doc_component, context):
        """Test convert_to_pdf action."""
        # Create a minimal test document (mock driver will handle it)
        test_data = b"test document content"
        encoded = base64.b64encode(test_data).decode("utf-8")

        result = doc_component.execute_sync(
            "convert_to_pdf",
            {"filename": "test.pptx", "data_base64": encoded},
            context,
        )

        assert result.pdf_sha256 is not None
        assert result.pdf_base64 is not None
        assert result.size_bytes > 0

    def test_render_document_action(self, doc_component, context):
        """Test render_document action (full pipeline)."""
        test_data = b"test document content"
        encoded = base64.b64encode(test_data).decode("utf-8")

        result = doc_component.execute_sync(
            "render_document",
            {
                "filename": "test.pptx",
                "data_base64": encoded,
                "dpi": 120,
                "image_format": "png",
                "output": "both",
            },
            context,
        )

        assert result.request_id == context.request_id
        assert result.pages_count == 2  # Mock driver returns 2 pages
        assert len(result.pages) == 2
        assert result.pdf is not None
        assert "convert" in result.timings_ms

    def test_remember_recall_actions(self, doc_component, context):
        """Test memory actions."""
        # Remember
        doc_component.execute_sync(
            "remember",
            {"key": "test_key", "value": "test_value"},
            context,
        )

        # Recall
        result = doc_component.execute_sync(
            "recall",
            {"key": "test_key"},
            context,
        )

        assert result.key == "test_key"
        assert result.value == "test_value"
        assert result.found is True

    def test_store_bytes_action(self, doc_component, context):
        """Test store_bytes action."""
        test_data = b"artifact data"
        encoded = base64.b64encode(test_data).decode("utf-8")

        result = doc_component.execute_sync(
            "store_bytes",
            {
                "name": "test.bin",
                "data_base64": encoded,
                "content_type": "application/octet-stream",
            },
            context,
        )

        assert result.name == "test.bin"
        assert result.size_bytes == len(test_data)
        assert result.url is not None

    def test_to_function_tools(self, doc_component):
        """Test exporting all actions as function tools."""
        tools = doc_component.to_function_tools()

        assert len(tools) == 6  # All DocComponent actions
        assert all(t["type"] == "function" for t in tools)

    def test_to_mcp_tools(self, doc_component):
        """Test exporting all actions as MCP tools."""
        tools = doc_component.to_mcp_tools()

        assert len(tools) == 6
        assert all("inputSchema" in t for t in tools)

    def test_system_prompt(self, doc_component):
        """Test system prompt generation."""
        prompt = doc_component.system_prompt()

        assert "doc" in prompt
        assert "convert_to_pdf" in prompt
        assert "render_document" in prompt


# ============================================================
# Adapter Tests
# ============================================================


class TestAdapters:
    def test_to_openai_tools(self, doc_component):
        """Test multi-component OpenAI tool export."""
        tools = to_openai_tools([doc_component])

        assert len(tools) == 6
        # Names should be prefixed with component name
        assert all("doc." in t["function"]["name"] for t in tools)

    def test_to_mcp_tools(self, doc_component):
        """Test multi-component MCP tool export."""
        tools = to_mcp_tools([doc_component])

        assert len(tools) == 6
        assert all("doc." in t["name"] for t in tools)

    def test_mcp_registry(self, doc_component, context):
        """Test MCP tool registry."""
        registry = MCPToolRegistry()
        registry.register_component(doc_component)

        tools = registry.list_tools()
        assert len(tools) == 6
        assert registry.has_tool("doc.remember")

    def test_function_calling_dispatcher(self, doc_component):
        """Test function calling dispatcher setup."""
        dispatcher = FunctionCallingDispatcher()
        dispatcher.register_component(doc_component)

        tools = dispatcher.get_tools()
        assert len(tools) == 6


# ============================================================
# ComponentRunner Tests
# ============================================================


class TestComponentRunner:
    @pytest.mark.asyncio
    async def test_runner_simple_task(self, doc_component, context):
        """Test runner with a simple task (no tool calls)."""
        llm = SimpleLLMAdapter(responses=[
            {"content": "I completed the task.", "finish_reason": "stop"}
        ])

        runner = ComponentRunner(
            components=[doc_component],
            llm=llm,
            ctx=context,
        )

        result = await runner.kickoff("Hello, test task")

        assert result.success is True
        assert result.output == "I completed the task."
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_runner_with_tool_call(self, doc_component, context):
        """Test runner executing a tool call."""
        # LLM first makes a tool call, then returns final response
        llm = SimpleLLMAdapter(responses=[
            {
                "content": "I'll remember that for you.",
                "finish_reason": "tool_calls",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {
                        "name": "doc.remember",
                        "arguments": '{"key": "test", "value": "hello"}',
                    },
                }],
            },
            {
                "content": "Done! I've stored the value.",
                "finish_reason": "stop",
            },
        ])

        runner = ComponentRunner(
            components=[doc_component],
            llm=llm,
            ctx=context,
        )

        result = await runner.kickoff("Remember 'hello' as 'test'")

        assert result.success is True
        assert result.tool_calls_made == 1

        # Verify the value was actually stored
        assert context.memory.recall("test") == "hello"

    @pytest.mark.asyncio
    async def test_runner_max_iterations(self, doc_component, context):
        """Test runner hitting max iterations."""
        # LLM keeps making tool calls forever
        llm = SimpleLLMAdapter(responses=[
            {
                "content": "Making another call...",
                "finish_reason": "tool_calls",
                "tool_calls": [{
                    "id": f"call_{i}",
                    "function": {
                        "name": "doc.recall",
                        "arguments": '{"key": "test"}',
                    },
                }],
            }
            for i in range(20)
        ])

        runner = ComponentRunner(
            components=[doc_component],
            llm=llm,
            ctx=context,
            max_iterations=3,
        )

        result = await runner.kickoff("Infinite task")

        assert result.success is False
        assert "Max iterations" in result.error
        assert result.tool_calls_made == 3

    def test_runner_sync(self, doc_component, context):
        """Test synchronous runner execution."""
        llm = SimpleLLMAdapter(responses=[
            {"content": "Done.", "finish_reason": "stop"}
        ])

        runner = ComponentRunner(
            components=[doc_component],
            llm=llm,
            ctx=context,
        )

        result = runner.kickoff_sync("Sync task")

        assert result.success is True
