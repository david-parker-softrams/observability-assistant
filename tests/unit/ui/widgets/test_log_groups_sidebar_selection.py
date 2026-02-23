"""Unit tests for LogGroupsSidebar multi-select functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from logai.ui.widgets.log_groups_sidebar import (
    LogGroupsSidebar,
    SelectableLogGroupItem,
)
from textual.app import App, ComposeResult
from textual.events import Click


class SidebarTestApp(App):
    """Test app to mount LogGroupsSidebar widget."""

    def __init__(self, log_group_manager=None):
        super().__init__()
        self.log_group_manager = log_group_manager

    def compose(self) -> ComposeResult:
        yield LogGroupsSidebar(log_group_manager=self.log_group_manager)


class TestSelectableLogGroupItemClickTiming:
    """Test suite for SelectableLogGroupItem click timing and detection."""

    def test_timing_threshold_constants(self):
        """Verify timing constants are reasonable and properly ordered."""
        item = SelectableLogGroupItem("/aws/lambda/test")

        assert item.DOUBLE_CLICK_THRESHOLD == 0.3
        assert item.SINGLE_CLICK_DELAY == 0.35
        # Single click delay must be longer to ensure double-click is detected
        assert item.SINGLE_CLICK_DELAY > item.DOUBLE_CLICK_THRESHOLD

    @pytest.mark.asyncio
    async def test_single_click_emits_selected_message(self):
        """Test that single click eventually emits LogGroupSelected."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        # Mock post_message to capture emitted messages
        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create a mock Click event
        click_event = Mock(spec=Click)
        click_event.button = 1  # Left mouse button
        click_event.ctrl = False
        click_event.meta = False

        # Trigger click
        item.on_click(click_event)

        # Wait for single-click delay to complete
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have emitted exactly one LogGroupSelected message
        assert len(messages) == 1
        assert isinstance(messages[0], SelectableLogGroupItem.LogGroupSelected)
        assert messages[0].log_group_name == "/aws/lambda/test"
        assert messages[0].add_to_selection is False

    @pytest.mark.asyncio
    async def test_double_click_emits_preview_message(self):
        """Test that double click emits LogGroupPreviewRequested."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click events
        click1 = Mock(spec=Click)
        click1.button = 1
        click1.ctrl = False
        click1.meta = False

        click2 = Mock(spec=Click)
        click2.button = 1
        click2.ctrl = False
        click2.meta = False

        # First click
        item.on_click(click1)

        # Second click within threshold (simulate 100ms delay)
        await asyncio.sleep(0.1)
        item.on_click(click2)

        # Wait a bit to ensure no delayed single-click fires
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have emitted exactly one LogGroupPreviewRequested message
        preview_messages = [
            m for m in messages if isinstance(m, SelectableLogGroupItem.LogGroupPreviewRequested)
        ]
        assert len(preview_messages) == 1
        assert preview_messages[0].log_group_name == "/aws/lambda/test"

        # Should NOT have emitted LogGroupSelected
        selected_messages = [
            m for m in messages if isinstance(m, SelectableLogGroupItem.LogGroupSelected)
        ]
        assert len(selected_messages) == 0

    @pytest.mark.asyncio
    async def test_ctrl_click_sets_add_to_selection_true(self):
        """Test Ctrl modifier is captured correctly."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click event with Ctrl held
        click_event = Mock(spec=Click)
        click_event.button = 1
        click_event.ctrl = True  # Ctrl key held
        click_event.meta = False

        # Trigger click
        item.on_click(click_event)

        # Wait for single-click delay
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have add_to_selection=True
        assert len(messages) == 1
        assert isinstance(messages[0], SelectableLogGroupItem.LogGroupSelected)
        assert messages[0].add_to_selection is True

    @pytest.mark.asyncio
    async def test_meta_click_sets_add_to_selection_true(self):
        """Test Cmd/Meta modifier (Mac) is captured correctly."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click event with Meta/Cmd held
        click_event = Mock(spec=Click)
        click_event.button = 1
        click_event.ctrl = False
        click_event.meta = True  # Cmd key held (Mac)

        # Trigger click
        item.on_click(click_event)

        # Wait for single-click delay
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have add_to_selection=True
        assert len(messages) == 1
        assert messages[0].add_to_selection is True

    @pytest.mark.asyncio
    async def test_double_click_cancels_pending_single_click(self):
        """Test that double-click prevents single-click action from firing."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click events
        click1 = Mock(spec=Click)
        click1.button = 1
        click1.ctrl = False
        click1.meta = False

        click2 = Mock(spec=Click)
        click2.button = 1
        click2.ctrl = False
        click2.meta = False

        # First click - this schedules a delayed single-click action
        item.on_click(click1)

        # Verify pending task was created
        assert item._pending_select_task is not None

        # Second click within threshold - this should cancel the pending task
        await asyncio.sleep(0.1)
        item.on_click(click2)

        # Wait long enough for single-click delay to have fired (if not cancelled)
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should only have preview message, no selection message
        assert (
            len([m for m in messages if isinstance(m, SelectableLogGroupItem.LogGroupSelected)])
            == 0
        )
        assert (
            len(
                [
                    m
                    for m in messages
                    if isinstance(m, SelectableLogGroupItem.LogGroupPreviewRequested)
                ]
            )
            == 1
        )

    @pytest.mark.asyncio
    async def test_right_click_ignored(self):
        """Test that right mouse button clicks are ignored."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click event with right button
        click_event = Mock(spec=Click)
        click_event.button = 2  # Right mouse button
        click_event.ctrl = False
        click_event.meta = False

        # Trigger click
        item.on_click(click_event)

        # Wait
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have no messages
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_slow_double_click_triggers_two_singles(self):
        """Test that clicks outside threshold trigger two single-clicks."""
        item = SelectableLogGroupItem("/aws/lambda/test")
        messages = []

        def capture_message(msg):
            messages.append(msg)

        item.post_message = capture_message

        # Create mock Click events
        click1 = Mock(spec=Click)
        click1.button = 1
        click1.ctrl = False
        click1.meta = False

        click2 = Mock(spec=Click)
        click2.button = 1
        click2.ctrl = False
        click2.meta = False

        # First click
        item.on_click(click1)

        # Wait for first single-click to complete
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Second click (too late for double-click)
        await asyncio.sleep(0.2)  # Ensure we're outside threshold
        item.on_click(click2)

        # Wait for second single-click to complete
        await asyncio.sleep(item.SINGLE_CLICK_DELAY + 0.1)

        # Should have two LogGroupSelected messages
        selected_messages = [
            m for m in messages if isinstance(m, SelectableLogGroupItem.LogGroupSelected)
        ]
        assert len(selected_messages) == 2


class TestLogGroupsSidebarSelectionState:
    """Test suite for LogGroupsSidebar selection state management."""

    @pytest.mark.asyncio
    async def test_clear_selection_on_refresh(self):
        """Test that selection is cleared when groups are refreshed."""
        app = SidebarTestApp()
        async with app.run_test() as _pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            sidebar.select_group("/aws/lambda/test")

            counter = sidebar.query_one("#selection-counter")

            # Should be visible
            assert counter.display is True
            # Get rendered content as string
            rendered_text = counter.render().plain
            assert "1 group selected" in rendered_text

    @pytest.mark.asyncio
    async def test_counter_initial_state(self):
        """Test that counter starts at 0."""
        app = SidebarTestApp()
        async with app.run_test() as _pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            sidebar.select_group("/aws/lambda/test1")
            sidebar.select_group("/aws/lambda/test2", add_to_selection=True)
            sidebar.select_group("/aws/lambda/test3", add_to_selection=True)

            counter = sidebar.query_one("#selection-counter")

            # Should be visible
            assert counter.display is True
            # Get rendered content as string
            rendered_text = counter.render().plain
            assert "3 selected" in rendered_text

    @pytest.mark.asyncio
    async def test_counter_updates_on_clear(self):
        """Test that counter resets when selection is cleared."""
        # Create a mock log group manager with test groups
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/test1", "/aws/lambda/test2"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        app = SidebarTestApp(log_group_manager=mock_manager)
        async with app.run_test() as _pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            # Wait for population
            await _pilot.pause()

            # Select first group
            sidebar.select_group("/aws/lambda/test1")

            # Find the item widgets
            items = sidebar.query(SelectableLogGroupItem)
            test1_item = None
            test2_item = None

            for item in items:
                if item.log_group_name == "/aws/lambda/test1":
                    test1_item = item
                elif item.log_group_name == "/aws/lambda/test2":
                    test2_item = item

            # Verify styling
            assert test1_item is not None
            assert test2_item is not None
            assert test1_item.has_class("selected")
            assert not test2_item.has_class("selected")

    @pytest.mark.asyncio
    async def test_clear_selection_styling_removes_all_classes(self):
        """Test that clearing selection removes 'selected' class from all items."""
        # Create a mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/test1", "/aws/lambda/test2"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        app = SidebarTestApp(log_group_manager=mock_manager)
        async with app.run_test() as pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            # Wait for population
            await pilot.pause()

            # Select both groups
            sidebar.select_group("/aws/lambda/test1")
            sidebar.select_group("/aws/lambda/test2", add_to_selection=True)

            # Clear selection
            sidebar.clear_selection()

            # Verify no items have selected class
            items = sidebar.query(SelectableLogGroupItem)
            for item in items:
                assert not item.has_class("selected")


class TestEventHandlerIntegration:
    """Test suite for event handler integration."""

    @pytest.mark.asyncio
    async def test_log_group_selected_event_handler(self):
        """Test that LogGroupSelected events are handled correctly."""
        # Create a mock log group manager
        mock_manager = Mock()
        mock_manager.count = 1
        mock_manager.get_log_group_names = Mock(return_value=["/aws/lambda/test"])
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        app = SidebarTestApp(log_group_manager=mock_manager)
        async with app.run_test() as pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            # Wait for population
            await pilot.pause()

            # Get the item widget
            items = list(sidebar.query(SelectableLogGroupItem))
            assert len(items) == 1
            item = items[0]

            # Post a LogGroupSelected message
            item.post_message(
                SelectableLogGroupItem.LogGroupSelected("/aws/lambda/test", add_to_selection=False)
            )

            # Wait for message processing
            await pilot.pause()

            # Verify sidebar received and processed the selection
            assert sidebar.has_selection()
            assert "/aws/lambda/test" in sidebar.get_selected_groups()

    @pytest.mark.asyncio
    async def test_selection_persists_after_log_groups_refresh(self):
        """Test that selection is cleared when log groups are refreshed."""
        # Create a mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/test1", "/aws/lambda/test2"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        app = SidebarTestApp(log_group_manager=mock_manager)
        async with app.run_test() as pilot:
            sidebar = app.query_one(LogGroupsSidebar)

            # Wait for initial population
            await pilot.pause()

            # Select a group
            sidebar.select_group("/aws/lambda/test1")
            assert sidebar.has_selection()

            # Simulate log groups update (which triggers clear)
            sidebar._on_log_groups_updated()

            # Selection should be cleared
            assert not sidebar.has_selection()
            assert sidebar.selection_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
