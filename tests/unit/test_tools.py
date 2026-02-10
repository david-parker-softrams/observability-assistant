"""Tests for tool base classes and registry."""

import pytest

from logai.core.tools.base import BaseTool, ToolExecutionError
from logai.core.tools.registry import ToolRegistry


class MockTool(BaseTool):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "test_param": {
                    "type": "string",
                    "description": "Test parameter",
                }
            },
            "required": ["test_param"],
        }

    async def execute(self, **kwargs) -> dict:
        if "test_param" not in kwargs:
            raise ToolExecutionError(
                message="test_param is required",
                tool_name=self.name,
            )
        return {"success": True, "result": kwargs["test_param"]}


class FailingTool(BaseTool):
    """Tool that always fails for testing error handling."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "A tool that fails"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> dict:
        raise ValueError("This tool always fails")


class TestBaseTool:
    """Tests for BaseTool."""

    def test_to_function_definition(self):
        """Test conversion to function definition format."""
        tool = MockTool()
        definition = tool.to_function_definition()

        assert definition["type"] == "function"
        assert definition["function"]["name"] == "mock_tool"
        assert definition["function"]["description"] == "A mock tool for testing"
        assert "properties" in definition["function"]["parameters"]
        assert "test_param" in definition["function"]["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful tool execution."""
        tool = MockTool()
        result = await tool.execute(test_param="hello")

        assert result["success"] is True
        assert result["result"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_missing_param(self):
        """Test execution with missing required parameter."""
        tool = MockTool()

        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute()

        assert "test_param is required" in str(exc_info.value)
        assert exc_info.value.tool_name == "mock_tool"


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        ToolRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        ToolRegistry.clear()

    def test_register_tool(self):
        """Test registering a tool."""
        tool = MockTool()
        ToolRegistry.register(tool)

        assert ToolRegistry.get("mock_tool") is tool
        assert len(ToolRegistry.get_all()) == 1

    def test_register_duplicate_tool(self):
        """Test that registering duplicate tool raises error."""
        tool1 = MockTool()
        tool2 = MockTool()

        ToolRegistry.register(tool1)

        with pytest.raises(ValueError) as exc_info:
            ToolRegistry.register(tool2)

        assert "already registered" in str(exc_info.value)

    def test_unregister_tool(self):
        """Test unregistering a tool."""
        tool = MockTool()
        ToolRegistry.register(tool)
        assert ToolRegistry.get("mock_tool") is not None

        ToolRegistry.unregister("mock_tool")
        assert ToolRegistry.get("mock_tool") is None

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        result = ToolRegistry.get("nonexistent")
        assert result is None

    def test_get_all_tools(self):
        """Test getting all registered tools."""
        tool1 = MockTool()
        tool2 = FailingTool()

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)

        all_tools = ToolRegistry.get_all()
        assert len(all_tools) == 2
        assert tool1 in all_tools
        assert tool2 in all_tools

    def test_to_function_definitions(self):
        """Test converting all tools to function definitions."""
        tool1 = MockTool()
        tool2 = FailingTool()

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)

        definitions = ToolRegistry.to_function_definitions()
        assert len(definitions) == 2
        assert all(d["type"] == "function" for d in definitions)
        assert any(d["function"]["name"] == "mock_tool" for d in definitions)
        assert any(d["function"]["name"] == "failing_tool" for d in definitions)

    @pytest.mark.asyncio
    async def test_execute_existing_tool(self):
        """Test executing a registered tool."""
        tool = MockTool()
        ToolRegistry.register(tool)

        result = await ToolRegistry.execute("mock_tool", test_param="test")

        assert result["success"] is True
        assert result["result"] == "test"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        with pytest.raises(ToolExecutionError) as exc_info:
            await ToolRegistry.execute("nonexistent", test_param="test")

        assert "not found in registry" in str(exc_info.value)
        assert exc_info.value.tool_name == "nonexistent"

    @pytest.mark.asyncio
    async def test_execute_failing_tool(self):
        """Test executing a tool that raises an exception."""
        tool = FailingTool()
        ToolRegistry.register(tool)

        with pytest.raises(ToolExecutionError) as exc_info:
            await ToolRegistry.execute("failing_tool")

        assert "This tool always fails" in str(exc_info.value)
        assert exc_info.value.tool_name == "failing_tool"

    def test_clear_registry(self):
        """Test clearing the registry."""
        tool1 = MockTool()
        tool2 = FailingTool()

        ToolRegistry.register(tool1)
        ToolRegistry.register(tool2)
        assert len(ToolRegistry.get_all()) == 2

        ToolRegistry.clear()
        assert len(ToolRegistry.get_all()) == 0
