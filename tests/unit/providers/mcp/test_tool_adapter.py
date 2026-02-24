"""Unit tests for MCPToolAdapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from logai.core.tools.base import ToolExecutionError
from logai.providers.mcp.client import MCPClientManager, MCPToolError
from logai.providers.mcp.tool_adapter import MCPToolAdapter

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_SAMPLE_PARAMS: dict = {
    "type": "object",
    "properties": {"logGroupName": {"type": "string"}},
    "required": ["logGroupName"],
}


@pytest.fixture
def mock_mcp_client() -> MagicMock:
    """Return an AsyncMock representing a connected MCPClientManager."""
    client = AsyncMock(spec=MCPClientManager)
    return client


@pytest.fixture
def adapter(mock_mcp_client: MagicMock) -> MCPToolAdapter:
    """Return a basic MCPToolAdapter with no result processor."""
    return MCPToolAdapter(
        mcp_client=mock_mcp_client,
        tool_name="describe_log_groups",
        tool_description="Lists CloudWatch log groups",
        tool_parameters=_SAMPLE_PARAMS,
        result_processor=None,
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestMCPToolAdapterProperties:
    """Tests for MCPToolAdapter property accessors."""

    def test_name_property(self, adapter: MCPToolAdapter) -> None:
        """name property returns the tool name passed at construction."""
        assert adapter.name == "describe_log_groups"

    def test_description_property(self, adapter: MCPToolAdapter) -> None:
        """description property returns the description passed at construction."""
        assert adapter.description == "Lists CloudWatch log groups"

    def test_parameters_property(self, adapter: MCPToolAdapter) -> None:
        """parameters property returns the parameters dict passed at construction."""
        assert adapter.parameters == _SAMPLE_PARAMS

    def test_to_function_definition_format(self, adapter: MCPToolAdapter) -> None:
        """to_function_definition() must return correct OpenAI function-calling shape."""
        defn = adapter.to_function_definition()

        assert defn["type"] == "function"
        fn = defn["function"]
        assert fn["name"] == "describe_log_groups"
        assert fn["description"] == "Lists CloudWatch log groups"
        assert fn["parameters"] == _SAMPLE_PARAMS


# ---------------------------------------------------------------------------
# execute() tests
# ---------------------------------------------------------------------------


class TestMCPToolAdapterExecute:
    """Tests for MCPToolAdapter.execute()."""

    @pytest.mark.asyncio
    async def test_execute_calls_mcp_client(
        self, adapter: MCPToolAdapter, mock_mcp_client: MagicMock
    ) -> None:
        """execute() must delegate to MCPClientManager.call_tool() with the right args."""
        mock_mcp_client.call_tool = AsyncMock(return_value={"logGroups": []})

        result = await adapter.execute(logGroupName="/aws/lambda/fn")

        mock_mcp_client.call_tool.assert_called_once_with(
            "describe_log_groups", {"logGroupName": "/aws/lambda/fn"}
        )
        # Result should include the data plus success=True
        assert result["logGroups"] == []
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_applies_result_processor(self, mock_mcp_client: MagicMock) -> None:
        """execute() must call result_processor.process() with tool name and raw result."""
        raw_result = {"data": "raw"}
        processed_result = {"data": "processed", "sanitization": {}}
        mock_mcp_client.call_tool = AsyncMock(return_value=raw_result)

        mock_processor = AsyncMock()
        mock_processor.process = AsyncMock(return_value=processed_result)

        adapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_name="get_logs_insight_query_results",
            tool_description="Gets log insight results",
            tool_parameters=_SAMPLE_PARAMS,
            result_processor=mock_processor,
        )

        await adapter.execute(queryId="abc-123")

        mock_processor.process.assert_called_once_with("get_logs_insight_query_results", raw_result)

    @pytest.mark.asyncio
    async def test_execute_injects_success_true(self, mock_mcp_client: MagicMock) -> None:
        """execute() should inject success=True when not present in result."""
        mock_mcp_client.call_tool = AsyncMock(return_value={"data": "x"})

        adapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_name="describe_log_groups",
            tool_description="desc",
            tool_parameters=_SAMPLE_PARAMS,
        )

        result = await adapter.execute()

        assert result["success"] is True
        assert result["data"] == "x"

    @pytest.mark.asyncio
    async def test_execute_does_not_overwrite_existing_success_key(
        self, mock_mcp_client: MagicMock
    ) -> None:
        """execute() must not overwrite success=False already present in result."""
        mock_mcp_client.call_tool = AsyncMock(return_value={"success": False, "data": "x"})

        adapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_name="describe_log_groups",
            tool_description="desc",
            tool_parameters=_SAMPLE_PARAMS,
        )

        result = await adapter.execute()

        # Pre-existing success=False is NOT overwritten
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_wraps_mcp_error_as_tool_execution_error(
        self, adapter: MCPToolAdapter, mock_mcp_client: MagicMock
    ) -> None:
        """MCPToolError raised by call_tool() must become ToolExecutionError."""
        mock_mcp_client.call_tool = AsyncMock(
            side_effect=MCPToolError("describe_log_groups", "Access denied")
        )

        with pytest.raises(ToolExecutionError) as exc_info:
            await adapter.execute(logGroupName="/aws/lambda/fn")

        exc = exc_info.value
        assert exc.tool_name == "describe_log_groups"

    @pytest.mark.asyncio
    async def test_execute_wraps_generic_error_as_tool_execution_error(
        self, adapter: MCPToolAdapter, mock_mcp_client: MagicMock
    ) -> None:
        """An unexpected ValueError must also become ToolExecutionError."""
        mock_mcp_client.call_tool = AsyncMock(side_effect=ValueError("Unexpected error"))

        with pytest.raises(ToolExecutionError) as exc_info:
            await adapter.execute(logGroupName="/aws/lambda/fn")

        exc = exc_info.value
        assert exc.tool_name == "describe_log_groups"
        assert "Unexpected error" in exc.message

    @pytest.mark.asyncio
    async def test_execute_without_result_processor(self, mock_mcp_client: MagicMock) -> None:
        """When result_processor=None, execute() must succeed and return the raw result."""
        raw = {"logGroups": ["/aws/lambda/fn"], "count": 1}
        mock_mcp_client.call_tool = AsyncMock(return_value=raw)

        adapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_name="describe_log_groups",
            tool_description="desc",
            tool_parameters=_SAMPLE_PARAMS,
            result_processor=None,
        )

        result = await adapter.execute()

        assert result["logGroups"] == ["/aws/lambda/fn"]
        assert result["count"] == 1
        assert result["success"] is True
