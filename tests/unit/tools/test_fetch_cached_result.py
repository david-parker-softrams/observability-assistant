"""Unit tests for FetchCachedResultTool."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from logai.core.context.result_cache import ResultCacheManager
from logai.core.tools.base import ToolExecutionError
from logai.tools.fetch_cached_result import FetchCachedResultTool


@pytest.fixture
async def cache_manager(tmp_path: Path) -> ResultCacheManager:
    """Create a result cache manager for testing."""
    manager = ResultCacheManager(cache_dir=tmp_path / "cache")
    await manager.initialize()
    return manager


@pytest.fixture
def fetch_tool(cache_manager: ResultCacheManager) -> FetchCachedResultTool:
    """Create a fetch cached result tool for testing."""
    return FetchCachedResultTool(result_cache=cache_manager)


@pytest.fixture
def sample_result() -> dict:
    """Create a sample result with events."""
    return {
        "events": [
            {"timestamp": 1707750000000 + i * 1000, "message": f"Event {i}"} for i in range(100)
        ]
    }


class TestFetchCachedResultTool:
    """Tests for FetchCachedResultTool."""

    def test_tool_name(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test tool name property."""
        assert fetch_tool.name == "fetch_cached_result_chunk"

    def test_tool_description(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test tool description property."""
        description = fetch_tool.description

        assert "cached" in description.lower()
        assert "chunk" in description.lower()
        assert "cache_id" in description.lower()

    def test_tool_parameters_schema(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test parameter schema is correctly defined."""
        params = fetch_tool.parameters

        assert params["type"] == "object"
        assert "cache_id" in params["properties"]
        assert "offset" in params["properties"]
        assert "limit" in params["properties"]
        assert "filter_pattern" in params["properties"]
        assert "time_start" in params["properties"]
        assert "time_end" in params["properties"]
        assert params["required"] == ["cache_id"]

    def test_tool_parameters_cache_id(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test cache_id parameter definition."""
        cache_id_param = fetch_tool.parameters["properties"]["cache_id"]

        assert cache_id_param["type"] == "string"
        assert "cache ID" in cache_id_param["description"]

    def test_tool_parameters_offset(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test offset parameter definition."""
        offset_param = fetch_tool.parameters["properties"]["offset"]

        assert offset_param["type"] == "integer"
        assert offset_param["minimum"] == 0
        assert offset_param["default"] == 0

    def test_tool_parameters_limit(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test limit parameter definition."""
        limit_param = fetch_tool.parameters["properties"]["limit"]

        assert limit_param["type"] == "integer"
        assert limit_param["minimum"] == 1
        assert limit_param["maximum"] == 200
        assert limit_param["default"] == 100

    def test_tool_parameters_filter_pattern(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test filter_pattern parameter definition."""
        filter_param = fetch_tool.parameters["properties"]["filter_pattern"]

        assert filter_param["type"] == "string"
        assert "filter" in filter_param["description"].lower()

    def test_tool_parameters_time_range(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test time_start and time_end parameter definitions."""
        time_start_param = fetch_tool.parameters["properties"]["time_start"]
        time_end_param = fetch_tool.parameters["properties"]["time_end"]

        assert time_start_param["type"] == "integer"
        assert time_end_param["type"] == "integer"
        assert "timestamp" in time_start_param["description"].lower()
        assert "timestamp" in time_end_param["description"].lower()

    def test_to_function_definition(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test conversion to function definition format."""
        func_def = fetch_tool.to_function_definition()

        assert func_def["type"] == "function"
        assert func_def["function"]["name"] == "fetch_cached_result_chunk"
        assert "description" in func_def["function"]
        assert "parameters" in func_def["function"]

    @pytest.mark.asyncio
    async def test_execute_missing_cache_id(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test execute raises error when cache_id is missing."""
        with pytest.raises(ToolExecutionError) as exc_info:
            await fetch_tool.execute()

        assert "cache_id" in str(exc_info.value).lower()
        assert exc_info.value.tool_name == "fetch_cached_result_chunk"

    @pytest.mark.asyncio
    async def test_execute_basic(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test basic execute with valid cache_id."""
        # Cache a result first
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Execute tool
        result = await fetch_tool.execute(cache_id=summary.cache_id)

        assert result["success"] is True
        assert len(result["events"]) == 100
        assert result["cache_id"] == summary.cache_id

    @pytest.mark.asyncio
    async def test_execute_with_offset_limit(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test execute with offset and limit parameters."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        result = await fetch_tool.execute(cache_id=summary.cache_id, offset=10, limit=20)

        assert result["success"] is True
        assert len(result["events"]) == 20
        assert result["offset"] == 10
        assert result["limit"] == 20
        assert result["events"][0]["message"] == "Event 10"

    @pytest.mark.asyncio
    async def test_execute_with_filter_pattern(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
    ) -> None:
        """Test execute with filter_pattern parameter."""
        result = {
            "events": [
                {"timestamp": 1707750000000, "message": "ERROR: Something failed"},
                {"timestamp": 1707750001000, "message": "INFO: Everything is fine"},
                {"timestamp": 1707750002000, "message": "ERROR: Another error"},
            ]
        }

        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        result_data = await fetch_tool.execute(cache_id=summary.cache_id, filter_pattern="ERROR")

        assert result_data["success"] is True
        assert len(result_data["events"]) == 2
        assert all("ERROR" in e["message"] for e in result_data["events"])

    @pytest.mark.asyncio
    async def test_execute_with_time_range(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test execute with time_start and time_end parameters."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Filter to events with timestamp >= 1707750010000 and <= 1707750020000
        result = await fetch_tool.execute(
            cache_id=summary.cache_id,
            time_start=1707750010000,
            time_end=1707750020000,
        )

        assert result["success"] is True
        assert len(result["events"]) == 11  # Events 10-20 inclusive
        assert result["total_filtered"] == 11

    @pytest.mark.asyncio
    async def test_execute_cache_not_found(self, fetch_tool: FetchCachedResultTool) -> None:
        """Test execute with non-existent cache_id."""
        result = await fetch_tool.execute(cache_id="result_nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_execute_default_parameters(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test that default parameters are applied correctly."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Execute with only cache_id (use defaults)
        result = await fetch_tool.execute(cache_id=summary.cache_id)

        assert result["success"] is True
        assert result["offset"] == 0  # Default offset
        assert result["limit"] == 100  # Default limit

    @pytest.mark.asyncio
    async def test_execute_error_handling(self) -> None:
        """Test error handling when cache manager raises exception."""
        # Create tool with mock cache manager that raises exception
        mock_cache = MagicMock(spec=ResultCacheManager)
        mock_cache.fetch_chunk = AsyncMock(side_effect=Exception("Database connection failed"))

        tool = FetchCachedResultTool(result_cache=mock_cache)

        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(cache_id="result_test")

        assert "Failed to fetch cached result" in str(exc_info.value)
        assert exc_info.value.tool_name == "fetch_cached_result_chunk"
        assert "cache_id" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_execute_all_parameters(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test execute with all parameters provided."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        result = await fetch_tool.execute(
            cache_id=summary.cache_id,
            offset=10,
            limit=50,
            filter_pattern="Event",
            time_start=1707750010000,
            time_end=1707750090000,
        )

        assert result["success"] is True
        assert result["filters_applied"]["pattern"] == "Event"
        assert result["filters_applied"]["time_start"] == 1707750010000
        assert result["filters_applied"]["time_end"] == 1707750090000

    @pytest.mark.asyncio
    async def test_execute_returns_pagination_info(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test that execute returns complete pagination information."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        result = await fetch_tool.execute(cache_id=summary.cache_id, offset=0, limit=25)

        assert "count" in result
        assert "offset" in result
        assert "limit" in result
        assert "total_filtered" in result
        assert "total_cached" in result
        assert "has_more" in result
        assert result["has_more"] is True  # More events available

    @pytest.mark.asyncio
    async def test_execute_last_page_has_more_false(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
        sample_result: dict,
    ) -> None:
        """Test that has_more is False on last page."""
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=sample_result,
        )

        # Fetch last page
        result = await fetch_tool.execute(cache_id=summary.cache_id, offset=75, limit=50)

        assert result["has_more"] is False  # No more events


class TestFetchCachedResultToolIntegration:
    """Integration tests for FetchCachedResultTool with ResultCacheManager."""

    @pytest.mark.asyncio
    async def test_full_workflow(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
    ) -> None:
        """Test complete workflow: cache, fetch multiple chunks."""
        # Create large result
        large_result = {
            "events": [
                {"timestamp": 1707750000000 + i * 1000, "message": f"Event {i}"} for i in range(500)
            ]
        }

        # Cache the result
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=large_result,
        )

        # Fetch first page
        page1 = await fetch_tool.execute(cache_id=summary.cache_id, offset=0, limit=100)
        assert len(page1["events"]) == 100
        assert page1["has_more"] is True

        # Fetch second page
        page2 = await fetch_tool.execute(cache_id=summary.cache_id, offset=100, limit=100)
        assert len(page2["events"]) == 100
        assert page2["has_more"] is True

        # Fetch last page
        page5 = await fetch_tool.execute(cache_id=summary.cache_id, offset=400, limit=100)
        assert len(page5["events"]) == 100
        assert page5["has_more"] is False

    @pytest.mark.asyncio
    async def test_workflow_with_filtering(
        self,
        fetch_tool: FetchCachedResultTool,
        cache_manager: ResultCacheManager,
    ) -> None:
        """Test workflow with progressive filtering."""
        # Create result with mixed event types
        result = {"events": []}
        for i in range(300):
            if i % 3 == 0:
                msg = f"ERROR: Error event {i}"
            elif i % 3 == 1:
                msg = f"WARN: Warning event {i}"
            else:
                msg = f"INFO: Info event {i}"
            result["events"].append({"timestamp": 1707750000000 + i * 1000, "message": msg})

        # Cache the result
        summary = await cache_manager.cache_result(
            tool_name="fetch_logs",
            query_params={"log_group": "/aws/lambda/test"},
            result=result,
        )

        # Fetch only ERROR events
        errors = await fetch_tool.execute(cache_id=summary.cache_id, filter_pattern="ERROR")
        assert errors["total_filtered"] == 100
        assert all("ERROR" in e["message"] for e in errors["events"])

        # Fetch only WARN events
        warnings = await fetch_tool.execute(cache_id=summary.cache_id, filter_pattern="WARN")
        assert warnings["total_filtered"] == 100
        assert all("WARN" in e["message"] for e in warnings["events"])
