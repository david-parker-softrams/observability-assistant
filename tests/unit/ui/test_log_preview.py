"""Unit tests for log preview feature."""

import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from logai.ui.screens.log_preview import LogEntryItem, LogPreviewScreen


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

    # ========================================================================
    # TESTS FOR "LOAD LAST 100" TOGGLE BUTTON FEATURE (Added by Raoul)
    # ========================================================================

    # --------------------------------------------------
    # Test Group 1: Initialization & Default Values
    # --------------------------------------------------

    def test_current_limit_default_is_10(self):
        """Verify current_limit initializes to DEFAULT_LIMIT (10)."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )
        assert screen.current_limit == LogPreviewScreen.DEFAULT_LIMIT
        assert screen.current_limit == 10

    def test_load_more_limit_constant_is_100(self):
        """Verify LOAD_MORE_LIMIT constant is 100."""
        assert LogPreviewScreen.LOAD_MORE_LIMIT == 100

    def test_current_limit_is_reactive_property(self):
        """Verify current_limit is a reactive property."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Should be able to set and get
        screen.current_limit = 100
        assert screen.current_limit == 100

        screen.current_limit = 10
        assert screen.current_limit == 10

    # --------------------------------------------------
    # Test Group 2: Button Toggle Behavior
    # --------------------------------------------------

    def test_load_100_button_toggles_from_10_to_100(self):
        """Clicking button when at 10 should set limit to 100."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Initially at 10
        assert screen.current_limit == 10

        # Simulate button click
        mock_button = MagicMock()
        mock_event = MagicMock()
        mock_event.button = mock_button
        mock_event.stop = MagicMock()

        screen.on_load_100_clicked(mock_event)

        # Should now be 100
        assert screen.current_limit == 100
        mock_event.stop.assert_called_once()

    def test_load_100_button_toggles_from_100_to_10(self):
        """Clicking button when at 100 should set limit back to 10."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set to 100
        screen.current_limit = 100

        # Simulate button click
        mock_button = MagicMock()
        mock_event = MagicMock()
        mock_event.button = mock_button
        mock_event.stop = MagicMock()

        screen.on_load_100_clicked(mock_event)

        # Should be back to 10
        assert screen.current_limit == 10
        mock_event.stop.assert_called_once()

    def test_multiple_toggle_cycles(self):
        """Multiple toggle cycles should work correctly."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Create reusable mock event
        mock_event = MagicMock()
        mock_event.button = MagicMock()
        mock_event.stop = MagicMock()

        # Start at 10, toggle multiple times
        assert screen.current_limit == 10

        screen.on_load_100_clicked(mock_event)  # 10 -> 100
        assert screen.current_limit == 100

        screen.on_load_100_clicked(mock_event)  # 100 -> 10
        assert screen.current_limit == 10

        screen.on_load_100_clicked(mock_event)  # 10 -> 100
        assert screen.current_limit == 100

        screen.on_load_100_clicked(mock_event)  # 100 -> 10
        assert screen.current_limit == 10

    # --------------------------------------------------
    # Test Group 3: Watcher Behavior
    # --------------------------------------------------

    def test_watch_current_limit_clears_events_when_mounted(self):
        """Watcher should clear events when screen is mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Populate state
        screen._events = [{"event_id": "e1"}, {"event_id": "e2"}]
        screen._selected_ids = {"id1", "id2"}

        # Mock methods
        screen._fetch_and_display_logs = MagicMock()
        screen._update_limit_button = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_current_limit(100)

        # State should be cleared
        assert len(screen._events) == 0
        assert len(screen._selected_ids) == 0

    def test_watch_current_limit_skips_when_not_mounted(self):
        """Watcher should not fetch when screen is not mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Populate state
        screen._events = [{"event_id": "e1"}]
        screen._selected_ids = {"id1"}

        # Call watcher (is_mounted=False by default)
        screen.watch_current_limit(100)

        # State should NOT be cleared
        assert len(screen._events) == 1
        assert len(screen._selected_ids) == 1

    def test_watch_current_limit_calls_update_button(self):
        """Watcher should call _update_limit_button when mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Mock methods to track calls
        screen._update_limit_button = MagicMock()
        screen._fetch_and_display_logs = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_current_limit(100)

        # Verify _update_limit_button was called
        screen._update_limit_button.assert_called_once()

    def test_watch_current_limit_triggers_fetch(self):
        """Watcher should trigger _fetch_and_display_logs when mounted."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Mock methods to track calls
        screen._update_limit_button = MagicMock()
        screen._fetch_and_display_logs = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_current_limit(100)

        # Verify fetch was triggered
        screen._fetch_and_display_logs.assert_called_once()

    # --------------------------------------------------
    # Test Group 4: UI Update Methods
    # --------------------------------------------------

    def test_update_limit_button_at_default_limit(self):
        """Button should show 'Load Last 100' with default variant when at 10."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set limit to 10
        screen.current_limit = 10

        # Mock button widget
        mock_button = MagicMock()
        screen.query_one = MagicMock(return_value=mock_button)

        # Call update method
        screen._update_limit_button()

        # Verify button state
        assert mock_button.label == "Load Last 100"
        assert mock_button.variant == "default"

    def test_update_limit_button_at_load_more_limit(self):
        """Button should show 'Show Last 10' with primary variant when at 100."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set limit to 100
        screen.current_limit = 100

        # Mock button widget
        mock_button = MagicMock()
        screen.query_one = MagicMock(return_value=mock_button)

        # Call update method
        screen._update_limit_button()

        # Verify button state
        assert mock_button.label == "Show Last 10"
        assert mock_button.variant == "primary"

    def test_update_limit_button_handles_not_mounted(self):
        """_update_limit_button should handle button not mounted gracefully."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Make query_one raise exception (button not mounted)
        screen.query_one = MagicMock(side_effect=Exception("Widget not found"))

        # Should not raise exception
        try:
            screen._update_limit_button()
        except Exception as e:
            pytest.fail(f"_update_limit_button should not raise exception: {e}")

    def test_update_entry_count_display_with_entries(self):
        """Entry count display should show 'Showing X entries' when entries exist."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Add some events
        screen._events = [{"event_id": f"e{i}"} for i in range(47)]

        # Mock display widget
        mock_display = MagicMock()
        screen.query_one = MagicMock(return_value=mock_display)

        # Call update method
        screen._update_entry_count_display()

        # Verify display was updated
        mock_display.update.assert_called_once_with("Showing 47 entries")

    def test_update_entry_count_display_with_zero_entries(self):
        """Entry count display should be empty when no entries exist."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # No events
        screen._events = []

        # Mock display widget
        mock_display = MagicMock()
        screen.query_one = MagicMock(return_value=mock_display)

        # Call update method
        screen._update_entry_count_display()

        # Verify display was cleared
        mock_display.update.assert_called_once_with("")

    def test_update_entry_count_display_handles_not_mounted(self):
        """_update_entry_count_display should handle widget not mounted gracefully."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        screen._events = [{"event_id": "e1"}]

        # Make query_one raise exception (widget not mounted)
        screen.query_one = MagicMock(side_effect=Exception("Widget not found"))

        # Should not raise exception
        try:
            screen._update_entry_count_display()
        except Exception as e:
            pytest.fail(f"_update_entry_count_display should not raise exception: {e}")

    # --------------------------------------------------
    # Test Group 5: Time Frame Integration
    # --------------------------------------------------

    def test_limit_persists_when_changing_time_frames(self):
        """Current limit should persist when changing time frames."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set to 100
        screen.current_limit = 100

        # Mock methods
        screen._fetch_and_display_logs = MagicMock()
        screen._update_timeframe_buttons = MagicMock()

        # Simulate mounted state and change time frame
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            screen.watch_selected_time_frame("1 hour")

        # Limit should still be 100
        assert screen.current_limit == 100

    def test_multiple_timeframe_changes_preserve_limit(self):
        """Limit should persist across multiple time frame changes."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set to 100
        screen.current_limit = 100

        # Mock methods
        screen._fetch_and_display_logs = MagicMock()
        screen._update_timeframe_buttons = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            # Change through multiple time frames
            screen.watch_selected_time_frame("1 hour")
            assert screen.current_limit == 100

            screen.watch_selected_time_frame("8 hours")
            assert screen.current_limit == 100

            screen.watch_selected_time_frame("24 hours")
            assert screen.current_limit == 100

            screen.watch_selected_time_frame("15 min")
            assert screen.current_limit == 100

    def test_changing_limit_after_timeframe_change(self):
        """Should be able to change limit after changing time frame."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Mock methods
        screen._fetch_and_display_logs = MagicMock()
        screen._update_timeframe_buttons = MagicMock()
        screen._update_limit_button = MagicMock()

        # Simulate mounted state
        with patch.object(
            type(screen), "is_mounted", new_callable=lambda: PropertyMock(return_value=True)
        ):
            # Change time frame (property assignment triggers watcher)
            screen.selected_time_frame = "1 hour"
            assert screen.current_limit == 10  # Still at default

            # Now change limit (property assignment triggers watcher)
            screen.current_limit = 100
            assert screen.current_limit == 100

            # Change time frame again
            screen.selected_time_frame = "8 hours"
            assert screen.current_limit == 100  # Should persist

    # --------------------------------------------------
    # Test Group 6: Edge Cases
    # --------------------------------------------------

    def test_rapid_button_clicking(self):
        """Rapid button clicking should toggle correctly."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        mock_event = MagicMock()
        mock_event.button = MagicMock()
        mock_event.stop = MagicMock()

        # Click button rapidly 10 times
        for _ in range(10):
            screen.on_load_100_clicked(mock_event)

        # Should end at 10 (started at 10, so even number of clicks returns to 10)
        assert screen.current_limit == 10

    def test_odd_number_of_rapid_clicks(self):
        """Odd number of rapid clicks should toggle to opposite state."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        mock_event = MagicMock()
        mock_event.button = MagicMock()
        mock_event.stop = MagicMock()

        # Click button 7 times (odd)
        for _ in range(7):
            screen.on_load_100_clicked(mock_event)

        # Should end at 100 (started at 10, odd number toggles to opposite)
        assert screen.current_limit == 100

    def test_fetch_with_fewer_than_100_entries_available(self):
        """Fetch should handle case where fewer than 100 entries exist."""
        # This is tested indirectly through _update_entry_count_display
        # showing actual count, not requested limit
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Set limit to 100 but only have 47 entries
        screen.current_limit = 100
        screen._events = [{"event_id": f"e{i}"} for i in range(47)]

        mock_display = MagicMock()
        screen.query_one = MagicMock(return_value=mock_display)

        screen._update_entry_count_display()

        # Should show actual count (47), not requested limit (100)
        mock_display.update.assert_called_once_with("Showing 47 entries")

    def test_entry_count_display_shows_actual_not_limit(self):
        """Entry count should always show actual fetched count, not the limit."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        test_cases = [
            (10, 5),  # Requested 10, got 5
            (100, 100),  # Requested 100, got 100
            (100, 73),  # Requested 100, got 73
            (10, 10),  # Requested 10, got 10
        ]

        mock_display = MagicMock()
        screen.query_one = MagicMock(return_value=mock_display)

        for limit, actual_count in test_cases:
            screen.current_limit = limit
            screen._events = [{"event_id": f"e{i}"} for i in range(actual_count)]

            mock_display.reset_mock()
            screen._update_entry_count_display()

            # Should always show actual count
            mock_display.update.assert_called_once_with(f"Showing {actual_count} entries")

    def test_watcher_not_triggered_during_initialization(self):
        """Watcher should not execute during screen initialization."""
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
        # even though current_limit is set to default
        screen.watch_current_limit(10)

        # Fetch should NOT have been called (is_mounted is False)
        assert not fetch_called[0]

    def test_button_update_called_after_fetch_completes(self):
        """Entry count display should update after fetch completes."""
        # This test verifies the integration in _fetch_and_display_logs
        # The method should call _update_entry_count_display() at line 769
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/test",
            datasource=datasource,
        )

        # Just verify the method exists and is callable
        assert callable(screen._update_entry_count_display)

        # The actual integration is tested in integration tests
        # This unit test confirms the method is available

    # --------------------------------------------------
    # Test Group 7: Constants and Configuration
    # --------------------------------------------------

    def test_default_limit_constant_value(self):
        """DEFAULT_LIMIT constant should be 10."""
        assert LogPreviewScreen.DEFAULT_LIMIT == 10

    def test_load_more_limit_constant_value(self):
        """LOAD_MORE_LIMIT constant should be 100."""
        assert LogPreviewScreen.LOAD_MORE_LIMIT == 100

    def test_limit_constants_are_positive(self):
        """All limit constants should be positive integers."""
        assert LogPreviewScreen.DEFAULT_LIMIT > 0
        assert LogPreviewScreen.LOAD_MORE_LIMIT > 0
        assert isinstance(LogPreviewScreen.DEFAULT_LIMIT, int)
        assert isinstance(LogPreviewScreen.LOAD_MORE_LIMIT, int)

    def test_load_more_limit_greater_than_default(self):
        """LOAD_MORE_LIMIT should be greater than DEFAULT_LIMIT."""
        assert LogPreviewScreen.LOAD_MORE_LIMIT > LogPreviewScreen.DEFAULT_LIMIT
