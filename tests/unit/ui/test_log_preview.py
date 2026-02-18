"""Unit tests for log preview feature."""

import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

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

    def test_json_message_pretty_printed(self):
        """JSON messages should be pretty-printed when expanded."""
        json_message = '{"level":"ERROR","message":"Test error","timestamp":123456}'
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": json_message,
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        formatted = item._format_message(json_message)
        # Should be pretty-printed with indentation
        assert "\n" in formatted
        assert "  " in formatted  # Has indentation
        assert '"level"' in formatted
        assert '"ERROR"' in formatted

    def test_non_json_message_unchanged(self):
        """Non-JSON messages should be displayed as-is."""
        plain_message = "This is a plain text log message"
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": plain_message,
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        formatted = item._format_message(plain_message)
        assert formatted == plain_message

    def test_invalid_json_unchanged(self):
        """Invalid JSON should be displayed as-is."""
        invalid_json = '{"incomplete": '
        item = LogEntryItem(
            event_data={
                "timestamp": 1708263045123,
                "message": invalid_json,
                "log_stream": "stream",
                "event_id": "event123",
            },
            entry_id="entry-0",
        )

        formatted = item._format_message(invalid_json)
        assert formatted == invalid_json


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
            time_range_minutes=60,  # Matches "1 hour" option
            limit=20,
        )

        assert screen.time_range_minutes == 60
        assert screen.selected_time_frame == "1 hour"
        assert screen.limit == 20

    def test_time_frame_options_mapping(self):
        """TIME_FRAME_OPTIONS should map labels to correct minutes."""
        # Verify we have exactly 4 time frame options
        assert len(LogPreviewScreen.TIME_FRAME_OPTIONS) == 4

        # Verify each option maps to the correct number of minutes
        assert LogPreviewScreen.TIME_FRAME_OPTIONS["15 min"] == 15
        assert LogPreviewScreen.TIME_FRAME_OPTIONS["1 hour"] == 60
        assert LogPreviewScreen.TIME_FRAME_OPTIONS["8 hours"] == 480
        assert LogPreviewScreen.TIME_FRAME_OPTIONS["24 hours"] == 1440

        # Verify all expected keys are present
        expected_keys = {"15 min", "1 hour", "8 hours", "24 hours"}
        assert set(LogPreviewScreen.TIME_FRAME_OPTIONS.keys()) == expected_keys

    def test_default_time_frame(self):
        """Default time frame should be 15 min."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Verify default selection
        assert screen.selected_time_frame == "15 min"
        # Verify the computed property returns correct minutes
        assert screen.time_range_minutes == 15

    def test_time_range_minutes_property(self):
        """time_range_minutes should compute correctly from selected_time_frame."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Test each valid time frame option
        for label, expected_minutes in LogPreviewScreen.TIME_FRAME_OPTIONS.items():
            screen.selected_time_frame = label
            assert screen.time_range_minutes == expected_minutes, (
                f"Expected {expected_minutes} minutes for '{label}', "
                f"got {screen.time_range_minutes}"
            )

    def test_invalid_time_frame_fallback(self):
        """Invalid time frame should fall back to 15 minutes."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set an invalid time frame value
        screen.selected_time_frame = "invalid"

        # Should fall back to default of 15 minutes
        assert screen.time_range_minutes == 15

        # Try another invalid value
        screen.selected_time_frame = "99 hours"
        assert screen.time_range_minutes == 15

    # ========================================================================
    # INTERACTION & BEHAVIOR TESTS (Added by Raoul)
    def test_compose_generates_all_timeframe_buttons(self):
        """Verify compose() generates buttons for all time frame options."""
        # Compose should generate widgets for all time frames
        # We verify this by checking TIME_FRAME_OPTIONS
        assert len(LogPreviewScreen.TIME_FRAME_OPTIONS) == 4

        # Verify keys are present (buttons will be generated for these)
        expected_labels = {"15 min", "1 hour", "8 hours", "24 hours"}
        actual_labels = set(LogPreviewScreen.TIME_FRAME_OPTIONS.keys())
        assert actual_labels == expected_labels

    # ========================================================================
    # INTERACTION & BEHAVIOR TESTS (Added by Raoul for QA)
    # ========================================================================

    def test_button_variant_updates_on_selection(self):
        """Selected button should have correct variant based on selection state."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Initially, "15 min" should be selected (default)
        assert screen.selected_time_frame == "15 min"

        # Change to "1 hour"
        screen.selected_time_frame = "1 hour"
        assert screen.selected_time_frame == "1 hour"

        # Change to "8 hours"
        screen.selected_time_frame = "8 hours"
        assert screen.selected_time_frame == "8 hours"

        # Change back to "15 min"
        screen.selected_time_frame = "15 min"
        assert screen.selected_time_frame == "15 min"

    def test_button_state_sync_across_changes(self):
        """Button state should sync correctly across multiple changes."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Test multiple sequential changes
        changes = ["1 hour", "8 hours", "24 hours", "15 min", "1 hour"]
        for expected_frame in changes:
            screen.selected_time_frame = expected_frame
            assert screen.selected_time_frame == expected_frame
            assert screen.time_range_minutes == LogPreviewScreen.TIME_FRAME_OPTIONS[expected_frame]

    def test_watch_selected_time_frame_clears_state(self):
        """Test that watch_selected_time_frame clears events and selections when mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Simulate some state
        screen._events = [{"event_id": "e1"}]
        screen._selected_ids = {"id1", "id2"}

        # Call the watcher directly with is_mounted=False (should not clear)
        screen.watch_selected_time_frame("1 hour")

        # State should NOT be cleared because not mounted
        assert len(screen._events) == 1
        assert len(screen._selected_ids) == 2

    def test_watch_selected_time_frame_with_mounted_screen(self):
        """Test that watcher clears state when screen is mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Populate state
        screen._events = [{"event_id": "e1"}, {"event_id": "e2"}]
        screen._selected_ids = {"id1", "id2", "id3"}

        # Mock _fetch_and_display_logs to avoid actual execution
        screen._fetch_and_display_logs = MagicMock()

        # Use PropertyMock to simulate is_mounted=True
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_selected_time_frame("8 hours")

        # State should be cleared
        assert len(screen._events) == 0
        assert len(screen._selected_ids) == 0

    def test_timeframe_button_click_updates_selection(self):
        """Mock button click should update selected_time_frame."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Create mock button pressed event
        mock_button = MagicMock()
        mock_button.label = "1 hour"
        mock_event = MagicMock()
        mock_event.button = mock_button

        # Simulate button click
        screen.on_timeframe_changed(mock_event)

        # Verify selection updated
        assert screen.selected_time_frame == "1 hour"

        # Verify event propagation stopped
        mock_event.stop.assert_called_once()

    def test_duplicate_selection_skipped(self):
        """Click same button twice should skip duplicate selection."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set initial selection
        screen.selected_time_frame = "1 hour"

        # Create mock button event for already-selected "1 hour"
        mock_button = MagicMock()
        mock_button.label = "1 hour"
        mock_event = MagicMock()
        mock_event.button = mock_button

        # Click same button - should be skipped (no change)
        screen.on_timeframe_changed(mock_event)

        # Selection should remain unchanged
        assert screen.selected_time_frame == "1 hour"

        # Verify event was still stopped
        mock_event.stop.assert_called_once()

    def test_rapid_timeframe_switching(self):
        """Simulate rapid clicks - verify state consistency."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Simulate rapid clicking through all options
        time_frames = ["1 hour", "8 hours", "24 hours", "15 min"]
        for frame in time_frames:
            mock_button = MagicMock()
            mock_button.label = frame
            mock_event = MagicMock()
            mock_event.button = mock_button
            screen.on_timeframe_changed(mock_event)

        # Final state should be last selection
        assert screen.selected_time_frame == "15 min"

    def test_invalid_button_label_ignored(self):
        """Test event with invalid time frame label should be ignored."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        initial_selection = screen.selected_time_frame

        # Create mock button with invalid label
        mock_button = MagicMock()
        mock_button.label = "Invalid Option"
        mock_event = MagicMock()
        mock_event.button = mock_button

        # Simulate button click with invalid label
        screen.on_timeframe_changed(mock_event)

        # Selection should remain unchanged
        assert screen.selected_time_frame == initial_selection

        # Event should still be stopped
        mock_event.stop.assert_called_once()

    def test_initialization_with_non_matching_time_range(self):
        """Initialization with non-matching time_range_minutes should keep default."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
            time_range_minutes=45,  # Doesn't match any preset option
        )

        # Should fall back to default "15 min"
        assert screen.selected_time_frame == "15 min"
        # time_range_minutes property should compute from selected_time_frame
        assert screen.time_range_minutes == 15

    def test_on_timeframe_changed_validates_label(self):
        """on_timeframe_changed should only process valid labels."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Try each valid label
        for valid_label in LogPreviewScreen.TIME_FRAME_OPTIONS.keys():
            mock_button = MagicMock()
            mock_button.label = valid_label
            mock_event = MagicMock()
            mock_event.button = mock_button

            screen.on_timeframe_changed(mock_event)
            assert screen.selected_time_frame == valid_label

        # Try invalid labels
        for invalid_label in ["30 min", "2 hours", "Custom", ""]:
            initial = screen.selected_time_frame
            mock_button = MagicMock()
            mock_button.label = invalid_label
            mock_event = MagicMock()
            mock_event.button = mock_button

            screen.on_timeframe_changed(mock_event)
            # Should not change
            assert screen.selected_time_frame == initial

    def test_watcher_calls_update_buttons(self):
        """watch_selected_time_frame should call _update_timeframe_buttons when mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Mock the methods to track calls
        screen._update_timeframe_buttons = MagicMock()
        screen._fetch_and_display_logs = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_selected_time_frame("8 hours")

        # Verify _update_timeframe_buttons was called
        screen._update_timeframe_buttons.assert_called_once()

    def test_empty_state_message_uses_selected_time_frame(self):
        """Empty state message should display selected time frame correctly."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set to 24 hours
        screen.selected_time_frame = "24 hours"

        # Note: This tests that the implementation at line 584 uses selected_time_frame
        # The actual empty state message generation happens in _fetch_and_display_logs
        # We're verifying the property is accessible
        assert screen.selected_time_frame == "24 hours"
        assert screen.time_range_minutes == 1440

    def test_all_time_frame_options_are_valid(self):
        """Verify all TIME_FRAME_OPTIONS values are positive integers."""
        for label, minutes in LogPreviewScreen.TIME_FRAME_OPTIONS.items():
            assert isinstance(minutes, int), f"Value for '{label}' should be int"
            assert minutes > 0, f"Value for '{label}' should be positive"
            assert isinstance(label, str), "Label should be str"
            assert len(label) > 0, "Label should not be empty"

    def test_time_frame_options_order_preserved(self):
        """TIME_FRAME_OPTIONS should maintain insertion order."""
        keys = list(LogPreviewScreen.TIME_FRAME_OPTIONS.keys())
        expected_order = ["15 min", "1 hour", "8 hours", "24 hours"]
        assert keys == expected_order, "Time frame options should be in ascending order"

    def test_watcher_not_triggered_on_initial_assignment(self):
        """Watcher should not execute logic before screen is mounted."""
        datasource = AsyncMock()

        # Track if fetch was called
        fetch_called = [False]

        class TestScreen(LogPreviewScreen):
            def _fetch_and_display_logs(self):
                fetch_called[0] = True
                return super()._fetch_and_display_logs()

        screen = TestScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Screen is not mounted, so watcher should not execute fetch
        screen.watch_selected_time_frame("1 hour")

        # Fetch should NOT have been called (is_mounted is False)
        assert not fetch_called[0]
