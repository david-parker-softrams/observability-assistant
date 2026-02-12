"""Log groups sidebar widget for displaying available CloudWatch log groups."""

import logging
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Static

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

logger = logging.getLogger(__name__)


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
        max-width: 35;
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
    """

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
        self._scroll_container: VerticalScroll | None = None
        self._empty_state: Static | None = None

    def compose(self) -> ComposeResult:
        """Compose the sidebar layout."""
        # Title with count
        count = self._get_count()
        yield Static(f"LOG GROUPS ({count})", id="sidebar-title", classes="sidebar-title")

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
        self._scroll_container = self.query_one("#log-groups-scroll", VerticalScroll)
        self._empty_state = self.query_one("#empty-state", Static)

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
        """
        try:
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

        # Add log group items
        for name in log_groups:
            # Display full name with automatic wrapping
            label = Label(name, classes="log-group-item")
            self._scroll_container.mount(label)

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
