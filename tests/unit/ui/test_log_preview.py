"""Unit tests for log preview feature."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from logai.ui.screens.log_preview import LogEntryItem, LogPreviewScreen
from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem


class TestClickableLogGroupItem:
    """Tests for the clickable log group item widget."""

    def test_stores_log_group_name(self):
        """Item should store the log group name."""
        item = ClickableLogGroupItem("/aws/lambda/test")
        assert item.log_group_name == "/aws/lambda/test"

    def test_single_click_does_not_emit_message(self):
        """Single click should not trigger preview request."""
        item = ClickableLogGroupItem("/aws/lambda/test")
        messages = []
        item.post_message = lambda m: messages.append(m)

        # Simulate single click
        click_event = MagicMock(button=1)
        item.on_click(click_event)

        assert len(messages) == 0

    def test_double_click_emits_preview_request(self):
        """Double-click should emit LogGroupPreviewRequested message."""
        item = ClickableLogGroupItem("/aws/lambda/test")
        messages = []
        item.post_message = lambda m: messages.append(m)

        # Simulate double-click (two clicks within threshold)
        click_event = MagicMock(button=1)
        item.on_click(click_event)
        item.on_click(click_event)  # Second click immediately

        assert len(messages) == 1
        assert isinstance(messages[0], ClickableLogGroupItem.LogGroupPreviewRequested)
        assert messages[0].log_group_name == "/aws/lambda/test"

    def test_slow_double_click_does_not_emit(self):
        """Clicks spaced more than 500ms should not trigger preview."""
        item = ClickableLogGroupItem("/aws/lambda/test")
        messages = []
        item.post_message = lambda m: messages.append(m)

        # Simulate slow double-click
        click_event = MagicMock(button=1)
        item.on_click(click_event)
        item._last_click_time -= 1.0  # Simulate 1 second passing
        item.on_click(click_event)

        assert len(messages) == 0

    def test_right_click_ignored(self):
        """Right-click should not affect double-click detection."""
        item = ClickableLogGroupItem("/aws/lambda/test")

        right_click = MagicMock(button=3)
        item.on_click(right_click)

        # Last click time should not be updated
        assert item._last_click_time == 0.0


class TestLogEntryItem:
    """Tests for the log entry item widget."""

    def test_message_preview_truncation(self):
        """Long messages should be truncated in preview."""
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": "x" * 200,  # 200 characters
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        preview = item._create_preview("x" * 200)
        assert len(preview) <= 103  # 100 chars + "..."
        assert preview.endswith("...")

    def test_short_message_not_truncated(self):
        """Short messages should not be truncated."""
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": "short message",
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        preview = item._create_preview("short message")
        assert preview == "short message"
        assert "..." not in preview

    def test_newlines_removed_in_preview(self):
        """Newlines should be replaced with spaces in preview."""
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": "line1\nline2\nline3",
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        preview = item._create_preview("line1\nline2\nline3")
        assert "\n" not in preview
        assert preview == "line1 line2 line3"


class TestLogPreviewScreen:
    """Tests for the log preview screen."""

    @pytest.mark.asyncio
    async def test_formats_error_for_not_found(self):
        """Should provide helpful message for missing log groups."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/deleted",
            datasource=datasource,
        )

        from logai.providers.datasources.base import LogGroupNotFoundError

        error = LogGroupNotFoundError("not found")

        message = screen._format_error_message(error)
        assert "not found" in message.lower()
        assert "refresh" in message.lower()
        assert screen.log_group_name in message

    @pytest.mark.asyncio
    async def test_formats_error_for_access_denied(self):
        """Should provide helpful message for permission errors."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/restricted",
            datasource=datasource,
        )

        from logai.providers.datasources.base import AuthenticationError

        error = AuthenticationError("access denied")

        message = screen._format_error_message(error)
        assert "access denied" in message.lower()
        assert "permissions" in message.lower() or "iam" in message.lower()

    @pytest.mark.asyncio
    async def test_formats_error_for_rate_limit(self):
        """Should provide helpful message for rate limit errors."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/busy",
            datasource=datasource,
        )

        from logai.providers.datasources.base import RateLimitError

        error = RateLimitError("throttling")

        message = screen._format_error_message(error)
        assert "rate limit" in message.lower()
        assert "try again" in message.lower()

    @pytest.mark.asyncio
    async def test_formats_error_for_timeout(self):
        """Should provide helpful message for timeout errors."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/slow",
            datasource=datasource,
        )

        error = TimeoutError("operation timeout")

        message = screen._format_error_message(error)
        assert "timed out" in message.lower()
        assert "try again" in message.lower()

    def test_initialization_with_defaults(self):
        """Screen should initialize with default parameters."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        assert screen.log_group_name == "/aws/lambda/test"
        assert screen.datasource == datasource
        assert screen.time_range_minutes == LogPreviewScreen.DEFAULT_TIME_RANGE_MINUTES
        assert screen.limit == LogPreviewScreen.DEFAULT_LIMIT

    def test_initialization_with_custom_params(self):
        """Screen should accept custom time range and limit."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
            time_range_minutes=30,
            limit=20,
        )

        assert screen.time_range_minutes == 30
        assert screen.limit == 20
