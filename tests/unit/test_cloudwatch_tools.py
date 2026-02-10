"""Tests for CloudWatch tools."""

from unittest.mock import AsyncMock, Mock

import pytest

from logai.config.settings import LogAISettings
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.cloudwatch_tools import (
    FetchLogsTool,
    ListLogGroupsTool,
    SearchLogsTool,
)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    return settings


@pytest.fixture
def mock_datasource():
    """Create mock CloudWatch datasource."""
    datasource = AsyncMock()
    return datasource


@pytest.fixture
def mock_sanitizer():
    """Create mock sanitizer."""
    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.enabled = True
    sanitizer.sanitize_log_events = Mock(return_value=([], {}))
    sanitizer.get_redaction_summary = Mock(return_value="No sensitive data redacted")
    return sanitizer


class TestListLogGroupsTool:
    """Tests for ListLogGroupsTool."""

    @pytest.mark.asyncio
    async def test_list_log_groups_success(self, mock_datasource, mock_settings):
        """Test successful log group listing."""
        # Setup
        mock_datasource.list_log_groups.return_value = [
            {"name": "/aws/lambda/function1", "created": 1234567890000},
            {"name": "/aws/lambda/function2", "created": 1234567891000},
        ]

        tool = ListLogGroupsTool(datasource=mock_datasource, settings=mock_settings)

        # Execute
        result = await tool.execute()

        # Assert
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["log_groups"]) == 2
        mock_datasource.list_log_groups.assert_called_once_with(prefix=None, limit=50)

    @pytest.mark.asyncio
    async def test_list_log_groups_with_prefix(self, mock_datasource, mock_settings):
        """Test listing with prefix filter."""
        mock_datasource.list_log_groups.return_value = [
            {"name": "/aws/lambda/function1", "created": 1234567890000},
        ]

        tool = ListLogGroupsTool(datasource=mock_datasource, settings=mock_settings)
        result = await tool.execute(prefix="/aws/lambda/", limit=10)

        assert result["success"] is True
        assert result["prefix"] == "/aws/lambda/"
        mock_datasource.list_log_groups.assert_called_once_with(prefix="/aws/lambda/", limit=10)

    def test_tool_definition(self, mock_datasource, mock_settings):
        """Test tool definition format."""
        tool = ListLogGroupsTool(datasource=mock_datasource, settings=mock_settings)

        assert tool.name == "list_log_groups"
        assert "CloudWatch log groups" in tool.description

        params = tool.parameters
        assert params["type"] == "object"
        assert "prefix" in params["properties"]
        assert "limit" in params["properties"]


class TestFetchLogsTool:
    """Tests for FetchLogsTool."""

    @pytest.mark.asyncio
    async def test_fetch_logs_success(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test successful log fetching."""
        # Setup
        mock_events = [
            {"timestamp": 1234567890000, "message": "Log message 1"},
            {"timestamp": 1234567891000, "message": "Log message 2"},
        ]
        mock_datasource.fetch_logs.return_value = mock_events
        mock_sanitizer.sanitize_log_events.return_value = (mock_events, {"email": 1})
        mock_sanitizer.get_redaction_summary.return_value = "Redacted: 1 Email"

        tool = FetchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        # Execute
        result = await tool.execute(
            log_group="/aws/lambda/test",
            start_time="1h ago",
            end_time="now",
        )

        # Assert
        assert result["success"] is True
        assert result["log_group"] == "/aws/lambda/test"
        assert result["count"] == 2
        assert len(result["events"]) == 2
        assert result["sanitization"]["enabled"] is True
        assert result["sanitization"]["redactions"] == {"email": 1}

        # Verify datasource was called
        mock_datasource.fetch_logs.assert_called_once()
        call_kwargs = mock_datasource.fetch_logs.call_args[1]
        assert call_kwargs["log_group"] == "/aws/lambda/test"

        # Verify sanitization was applied
        mock_sanitizer.sanitize_log_events.assert_called_once_with(mock_events)

    @pytest.mark.asyncio
    async def test_fetch_logs_with_filter(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test fetching with filter pattern."""
        mock_datasource.fetch_logs.return_value = []
        mock_sanitizer.sanitize_log_events.return_value = ([], {})

        tool = FetchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        result = await tool.execute(
            log_group="/aws/lambda/test",
            start_time="1h ago",
            filter_pattern="ERROR",
            limit=50,
        )

        assert result["success"] is True
        assert result["filter_pattern"] == "ERROR"

        call_kwargs = mock_datasource.fetch_logs.call_args[1]
        assert call_kwargs["filter_pattern"] == "ERROR"
        assert call_kwargs["limit"] == 50

    @pytest.mark.asyncio
    async def test_fetch_logs_missing_required_param(
        self, mock_datasource, mock_sanitizer, mock_settings
    ):
        """Test that missing required parameters raise errors."""
        from logai.core.tools.base import ToolExecutionError

        tool = FetchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        # Missing log_group
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(start_time="1h ago")
        assert "log_group" in str(exc_info.value)

        # Missing start_time
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(log_group="/aws/lambda/test")
        assert "start_time" in str(exc_info.value)

    def test_tool_definition(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test tool definition format."""
        tool = FetchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        assert tool.name == "fetch_logs"
        assert "fetch log events" in tool.description.lower()

        params = tool.parameters
        assert "log_group" in params["properties"]
        assert "start_time" in params["properties"]
        assert "end_time" in params["properties"]
        assert "filter_pattern" in params["properties"]
        assert "log_group" in params["required"]
        assert "start_time" in params["required"]


class TestSearchLogsTool:
    """Tests for SearchLogsTool."""

    @pytest.mark.asyncio
    async def test_search_logs_success(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test successful log searching."""
        # Setup
        mock_events = [
            {
                "timestamp": 1234567890000,
                "message": "Error in service A",
                "log_stream": "/aws/lambda/service-a",
            },
            {
                "timestamp": 1234567891000,
                "message": "Error in service B",
                "log_stream": "/aws/lambda/service-b",
            },
        ]
        mock_datasource.search_logs.return_value = mock_events
        mock_sanitizer.sanitize_log_events.return_value = (mock_events, {})

        tool = SearchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        # Execute
        result = await tool.execute(
            log_group_patterns=["/aws/lambda/"],
            search_pattern="ERROR",
            start_time="1h ago",
        )

        # Assert
        assert result["success"] is True
        assert result["count"] == 2
        assert result["search_pattern"] == "ERROR"
        assert len(result["log_group_patterns"]) == 1

        mock_datasource.search_logs.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_logs_missing_params(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test that missing required parameters raise errors."""
        from logai.core.tools.base import ToolExecutionError

        tool = SearchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        # Missing log_group_patterns
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(search_pattern="ERROR", start_time="1h ago")
        assert "log_group_patterns" in str(exc_info.value)

        # Empty log_group_patterns
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.execute(log_group_patterns=[], search_pattern="ERROR", start_time="1h ago")
        assert "log_group_patterns" in str(exc_info.value)

    def test_tool_definition(self, mock_datasource, mock_sanitizer, mock_settings):
        """Test tool definition format."""
        tool = SearchLogsTool(
            datasource=mock_datasource, sanitizer=mock_sanitizer, settings=mock_settings
        )

        assert tool.name == "search_logs"
        assert "search across multiple" in tool.description.lower()

        params = tool.parameters
        assert "log_group_patterns" in params["properties"]
        assert "search_pattern" in params["properties"]
        assert params["properties"]["log_group_patterns"]["type"] == "array"
