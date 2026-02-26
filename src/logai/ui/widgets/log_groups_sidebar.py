"""Log groups sidebar widget for displaying available CloudWatch log groups."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.widgets import Label, Static

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

logger = logging.getLogger(__name__)


class SelectableLogGroupItem(Label):
    """
    Selectable log group label with double-click preview support.

    This widget handles three types of clicks:
    - Single click: Select this group (replaces current selection)
    - Ctrl/Cmd + click: Add to/remove from selection (multi-select)
    - Double click: Open preview modal (preserves existing functionality)

    The implementation uses a timing strategy to distinguish between
    single and double clicks:
    - First click starts a 350ms timer
    - Second click within 300ms → double-click → open preview
    - No second click → timer fires → emit selection event
    - Ctrl/Cmd state is captured at first click

    This ensures double-click preview functionality is preserved while
    adding new selection capabilities.

    Attributes:
        log_group_name: The CloudWatch log group name this item represents
    """

    # Timing constants based on standard OS behavior
    DOUBLE_CLICK_THRESHOLD: float = 0.3  # 300ms - standard OS timing
    SINGLE_CLICK_DELAY: float = 0.35  # 350ms - slightly longer to ensure double detected

    class LogGroupSelected(Message):
        """
        Emitted when user single-clicks to select a log group.

        This message is sent after the SINGLE_CLICK_DELAY has elapsed
        without a second click being detected (i.e., not a double-click).

        Attributes:
            log_group_name: Name of the log group that was selected
            add_to_selection: True if Ctrl/Cmd was held (multi-select),
                            False for normal click (replace selection)
        """

        def __init__(self, log_group_name: str, add_to_selection: bool) -> None:
            """
            Initialize log group selection message.

            Args:
                log_group_name: Name of the log group to select
                add_to_selection: True if adding to selection (Ctrl/Cmd held),
                                False to replace selection (normal click)
            """
            super().__init__()
            self.log_group_name = log_group_name
            self.add_to_selection = add_to_selection

    class LogGroupPreviewRequested(Message):
        """
        Emitted when user double-clicks to request log preview.

        This preserves the existing double-click functionality.

        Attributes:
            log_group_name: Name of the log group to preview
        """

        def __init__(self, log_group_name: str) -> None:
            """
            Initialize preview request message.

            Args:
                log_group_name: Name of the log group to preview
            """
            super().__init__()
            self.log_group_name = log_group_name

    def __init__(self, log_group_name: str, **kwargs: Any) -> None:
        """
        Initialize selectable log group item.

        Args:
            log_group_name: CloudWatch log group name
            **kwargs: Additional arguments passed to Label
        """
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name
        self._last_click_time: float = 0.0
        self._pending_select_task: asyncio.Task | None = None
        self._pending_ctrl_state: bool = False

    def on_click(self, event: Click) -> None:
        """
        Handle click events with double-click detection and modifier key support.

        This implements the timing strategy for distinguishing between:
        - Single click (delayed by SINGLE_CLICK_DELAY)
        - Double click (detected within DOUBLE_CLICK_THRESHOLD)

        The Ctrl/Cmd key state is captured at first click and preserved
        for the delayed single-click action.

        Args:
            event: The click event from Textual
        """
        # Only handle left mouse button
        if event.button != 1:
            return

        current_time = time.time()
        time_since_last = current_time - self._last_click_time

        # Detect Ctrl (Linux/Windows) or Cmd (Mac)
        ctrl_held = event.ctrl or event.meta

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            # Double-click detected within threshold
            # Cancel pending single-click action and emit preview request
            self._cancel_pending_select()
            self.post_message(self.LogGroupPreviewRequested(self.log_group_name))
            # Reset timer to prevent triple-click from triggering another double-click
            self._last_click_time = 0.0
        else:
            # Potential single-click - schedule delayed action
            # Record time for double-click detection
            self._last_click_time = current_time
            # Capture the Ctrl/Cmd state now (will be used if single-click fires)
            self._pending_ctrl_state = ctrl_held
            # Schedule the delayed single-click action
            self._schedule_single_click()

    def _schedule_single_click(self) -> None:
        """
        Schedule a delayed single-click action.

        Cancels any existing pending action before scheduling a new one.
        The delay allows time to detect a potential double-click.
        """
        # Cancel any existing pending action
        self._cancel_pending_select()
        # Create new async task for delayed action
        self._pending_select_task = asyncio.create_task(self._delayed_single_click())

    async def _delayed_single_click(self) -> None:
        """
        Execute single-click action after delay.

        This method is called via async task after SINGLE_CLICK_DELAY.
        If a double-click occurs during the delay, this task will be cancelled.

        Emits LogGroupSelected message with the captured Ctrl/Cmd state.
        """
        try:
            # Wait for the delay period
            await asyncio.sleep(self.SINGLE_CLICK_DELAY)
            # Delay elapsed without cancellation - emit selection event
            self.post_message(
                self.LogGroupSelected(
                    self.log_group_name, add_to_selection=self._pending_ctrl_state
                )
            )
        except asyncio.CancelledError:
            # Task was cancelled by double-click detection - this is normal
            pass
        finally:
            # Clean up task reference
            self._pending_select_task = None

    def _cancel_pending_select(self) -> None:
        """
        Cancel any pending single-click action.

        Called when a double-click is detected to prevent the first click's
        delayed selection action from firing.
        """
        if self._pending_select_task and not self._pending_select_task.done():
            self._pending_select_task.cancel()
            self._pending_select_task = None

    def on_unmount(self) -> None:
        """
        Clean up pending tasks when widget is unmounted.

        This ensures that any pending click tasks are properly cancelled
        when the widget is destroyed, preventing potential issues with
        tasks trying to post messages to destroyed widgets.
        """
        self._cancel_pending_select()


class LogGroupsSidebar(Static):
    """
    Sidebar widget showing available CloudWatch log groups.

    Displays a scrollable list of log group names that automatically
    updates when the LogGroupManager refreshes.
    """

    DEFAULT_CSS = """
    LogGroupsSidebar {
        width: 28;
        min-width: 24;
        max-width: 70;
        height: 1fr;
        background: $panel;
        border-right: solid $primary;
        padding: 0 1;
    }

    LogGroupsSidebar .sidebar-title {
        text-style: bold;
        color: $text;
        padding: 1 0;
        width: 100%;
    }

    LogGroupsSidebar .selection-counter {
        color: $accent;
        text-style: italic;
        padding: 0 0 1 0;
        height: auto;
    }

    LogGroupsSidebar .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
        text-align: center;
    }

    LogGroupsSidebar #log-groups-scroll {
        width: 100%;
        height: 1fr;
        padding: 0;
    }

    LogGroupsSidebar .log-group-item {
        width: 100%;
        height: auto;
        padding: 0;
        color: $text;
    }

    LogGroupsSidebar .log-group-item:hover {
        background: $surface;
    }

    LogGroupsSidebar .log-group-item.selected {
        background: $primary-lighten-3;
        color: $text;
        text-style: bold;
    }

    LogGroupsSidebar .log-group-item.selected:hover {
        background: $primary-lighten-2;
    }
    """

    # Maximum number of log groups that can be selected at once
    # Prevents performance issues with very large selections
    MAX_SELECTION_COUNT = 20

    def __init__(
        self,
        log_group_manager: "LogGroupManager | None" = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the log groups sidebar.

        Args:
            log_group_manager: Manager containing the log groups to display
        """
        super().__init__(**kwargs)
        self._log_group_manager = log_group_manager
        self._title_label: Static | None = None
        self._selection_counter: Static | None = None
        self._scroll_container: VerticalScroll | None = None
        self._empty_state: Static | None = None
        self._selected_groups: set[str] = set()

    def compose(self) -> ComposeResult:
        """Compose the sidebar layout."""
        # Title with count
        count = self._get_count()
        yield Static(f"LOG GROUPS ({count})", id="sidebar-title", classes="sidebar-title")

        # Selection counter (hidden by default, shown when groups are selected)
        yield Static("", id="selection-counter", classes="selection-counter")

        # Empty state message
        yield Static(
            "No log groups loaded.\nUse /refresh to load.",
            id="empty-state",
            classes="empty-state",
        )

        # Scrollable container for log groups
        yield VerticalScroll(id="log-groups-scroll")

    def on_mount(self) -> None:
        """Set up the sidebar when mounted."""
        self._title_label = self.query_one("#sidebar-title", Static)
        self._selection_counter = self.query_one("#selection-counter", Static)
        self._scroll_container = self.query_one("#log-groups-scroll", VerticalScroll)
        self._empty_state = self.query_one("#empty-state", Static)

        # Hide counter initially (no selection)
        self._selection_counter.display = False

        # Register for updates from log group manager
        if self._log_group_manager:
            self._log_group_manager.register_update_callback(self._on_log_groups_updated)

        # Initial population
        self._populate_log_groups()

    def on_unmount(self) -> None:
        """Clean up when unmounted."""
        # Unregister callback
        if self._log_group_manager:
            self._log_group_manager.unregister_update_callback(self._on_log_groups_updated)

    def _on_log_groups_updated(self) -> None:
        """
        Handle log group updates from the manager.

        This callback is invoked when /refresh completes.
        Selection is cleared as log groups may have changed.
        """
        try:
            # Clear selection when log groups are refreshed
            # (groups may have been added/removed)
            self.clear_selection()

            # Repopulate the list
            self._populate_log_groups()
        except Exception as e:
            logger.warning(f"Failed to update log groups sidebar: {e}", exc_info=True)

    def _populate_log_groups(self) -> None:
        """Populate the sidebar with log groups from the manager."""
        if not self._scroll_container:
            return

        # Update title with count
        count = self._get_count()
        if self._title_label:
            self._title_label.update(f"LOG GROUPS ({count})")

        # Clear existing content
        self._scroll_container.remove_children()

        # Get log group names
        log_groups = self._get_log_group_names()

        # Update empty state visibility
        if self._empty_state:
            self._empty_state.display = len(log_groups) == 0

        if not log_groups:
            return

        # Hide empty state
        if self._empty_state:
            self._empty_state.display = False

        # Add log group items with selection support
        for name in log_groups:
            # Create selectable item with single-click selection and double-click preview
            item = SelectableLogGroupItem(name, classes="log-group-item")
            self._scroll_container.mount(item)

    # === Selection State Management Methods ===

    def get_selected_groups(self) -> list[str]:
        """
        Get currently selected log group names.

        Returns a sorted list of selected log group names for consistent ordering.
        This is the public API for other components (like ChatScreen) to query
        the current selection state.

        Returns:
            List of selected log group names (sorted alphabetically)
        """
        return sorted(self._selected_groups)

    def has_selection(self) -> bool:
        """
        Check if any log groups are currently selected.

        Returns:
            True if at least one group is selected, False otherwise
        """
        return len(self._selected_groups) > 0

    @property
    def selection_count(self) -> int:
        """
        Get the number of currently selected log groups.

        Returns:
            Count of selected groups
        """
        return len(self._selected_groups)

    def select_group(self, name: str, add_to_selection: bool = False) -> None:
        """
        Select a log group, with support for multi-select.

        This method implements the core selection logic:
        - Normal click (add_to_selection=False): Replace current selection with this group
        - Ctrl/Cmd-click (add_to_selection=True): Toggle this group in the selection

        When toggling (Ctrl/Cmd-click), if the group is already selected, it will be
        deselected. This allows users to remove individual items from a multi-selection.

        Args:
            name: Log group name to select
            add_to_selection: If True, add to/toggle in current selection (Ctrl-click)
                            If False, replace current selection (regular click)
        """
        if not add_to_selection:
            # Normal click - clear previous selection and select only this group
            self._selected_groups.clear()
            self._selected_groups.add(name)
        else:
            # Ctrl/Cmd-click - toggle this group in the selection
            if name in self._selected_groups:
                # Already selected - deselect it (toggle off)
                self._selected_groups.remove(name)
            else:
                # Not selected - check limit before adding
                if len(self._selected_groups) >= self.MAX_SELECTION_COUNT:
                    self.app.notify(
                        f"Maximum {self.MAX_SELECTION_COUNT} groups can be selected",
                        severity="warning",
                    )
                    return
                # Add it to selection
                self._selected_groups.add(name)

        # Update the visual styling to reflect new selection state
        self._update_selection_styling()
        # Update the counter display to reflect new selection state
        self._update_selection_counter()

    def clear_selection(self) -> None:
        """
        Clear all selected log groups.

        This is called when log groups are refreshed (/refresh command)
        since the list of available groups may have changed.
        """
        self._clear_selection_styling()
        self._selected_groups.clear()
        self._update_selection_counter()

    def _update_selection_counter(self) -> None:
        """
        Update the selection counter display based on current selection state.

        The counter shows:
        - Hidden when no groups are selected
        - "1 group selected" when exactly one group is selected (grammatically correct)
        - "N selected" when multiple groups are selected (concise)
        """
        if not self._selection_counter:
            return

        count = len(self._selected_groups)
        if count == 0:
            # No selection - hide the counter
            self._selection_counter.display = False
        else:
            # Format the counter text
            if count == 1:
                text = "1 group selected"
            else:
                text = f"{count} selected"

            # Update and show the counter
            self._selection_counter.update(text)
            self._selection_counter.display = True

    def _clear_selection_styling(self) -> None:
        """
        Remove selected class from all log group items.

        This is called when clearing the entire selection to ensure
        no items have the selected visual styling.
        """
        if self._scroll_container:
            for item in self._scroll_container.query(".log-group-item"):
                item.remove_class("selected")

    def _update_selection_styling(self) -> None:
        """
        Update visual styling for all log group items based on selection state.

        Iterates through all SelectableLogGroupItem widgets and applies the
        'selected' CSS class to items that are in the _selected_groups set,
        and removes it from items that are not selected.

        This ensures the UI accurately reflects the current selection state.
        """
        if self._scroll_container:
            for item in self._scroll_container.query(SelectableLogGroupItem):
                if item.log_group_name in self._selected_groups:
                    item.add_class("selected")
                else:
                    item.remove_class("selected")

    # === Event Handlers ===

    def on_selectable_log_group_item_log_group_selected(
        self, event: SelectableLogGroupItem.LogGroupSelected
    ) -> None:
        """
        Handle log group selection events from SelectableLogGroupItem widgets.

        This event is emitted when a user single-clicks a log group item
        (after the click delay to distinguish from double-click).

        Args:
            event: Selection event containing log group name and modifier key state
        """
        self.select_group(event.log_group_name, event.add_to_selection)

    # === Helper Methods ===

    def _get_count(self) -> int:
        """Get the count of log groups."""
        if self._log_group_manager:
            return self._log_group_manager.count
        return 0

    def _get_log_group_names(self) -> list[str]:
        """Get sorted list of log group names."""
        if self._log_group_manager:
            names = self._log_group_manager.get_log_group_names()
            return sorted(names)
        return []

    def refresh_display(self) -> None:
        """
        Manually refresh the display.

        Called when sidebar is toggled back on to ensure current data.
        """
        self._populate_log_groups()
