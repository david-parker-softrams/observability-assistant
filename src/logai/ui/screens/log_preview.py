"""Log preview screen for displaying and selecting recent log events."""

import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

if TYPE_CHECKING:
    from logai.providers.datasources.cloudwatch import CloudWatchDataSource

logger = logging.getLogger(__name__)


class LogEntryItem(Static):
    """
    Individual log entry widget with checkbox and expand/collapse.

    Displays log entries in compact format by default with ability
    to expand for full details.
    """

    # Message emitted when selection state changes
    class SelectionChanged(Message):
        """Emitted when entry's checkbox is toggled."""

        def __init__(self, entry_id: str, selected: bool) -> None:
            super().__init__()
            self.entry_id = entry_id
            self.selected = selected

    DEFAULT_CSS = """
    LogEntryItem {
        layout: vertical;
        width: 100%;
        height: auto;
        background: $surface;
        padding: 1;
        margin: 0 0 1 0;
        border-left: thick $accent;
    }

    LogEntryItem:hover {
        background: $surface-lighten-1;
    }

    LogEntryItem .entry-header {
        layout: horizontal;
        width: 100%;
        height: auto;
    }

    LogEntryItem .entry-checkbox {
        width: auto;
        min-width: 5;
    }

    LogEntryItem .entry-compact {
        width: 1fr;
        height: auto;
    }

    LogEntryItem .entry-timestamp {
        color: $accent;
        text-style: bold;
    }

    LogEntryItem .entry-message-preview {
        color: $text;
    }

    LogEntryItem .entry-details {
        display: none;
        padding: 1 0 0 5;
        color: $text-muted;
        border-top: dashed $surface-darken-2;
        margin-top: 1;
    }

    LogEntryItem.expanded .entry-details {
        display: block;
    }

    LogEntryItem .expand-hint {
        color: $text-muted;
        text-style: italic;
    }
    """

    # Reactive property for expanded state
    expanded = reactive(False)

    # Maximum characters for compact message preview
    PREVIEW_MAX_CHARS: int = 100

    def __init__(
        self,
        event_data: dict[str, Any],
        entry_id: str,
        **kwargs: Any,
    ) -> None:
        """
        Initialize log entry item.

        Args:
            event_data: Log event dictionary from CloudWatch
            entry_id: Unique identifier for this entry
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.event_data = event_data
        self.entry_id = entry_id
        self._selected = False
        self._checkbox: Checkbox | None = None

    def compose(self) -> ComposeResult:
        """Compose the log entry layout."""
        # Format timestamp
        timestamp_ms = self.event_data.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Get message and create preview
        message = self.event_data.get("message", "")
        message_preview = self._create_preview(message)

        # Header with checkbox and compact view
        with Horizontal(classes="entry-header"):
            yield Checkbox(
                value=False,
                id=f"checkbox-{self.entry_id}",
                classes="entry-checkbox",
            )
            with Container(classes="entry-compact"):
                yield Static(
                    f"[cyan]{time_str}[/cyan]",
                    classes="entry-timestamp",
                )
                yield Static(
                    message_preview,
                    classes="entry-message-preview",
                )
                yield Static(
                    "(click to expand)" if len(message) > self.PREVIEW_MAX_CHARS else "",
                    classes="expand-hint",
                )

        # Expandable details section
        with Container(classes="entry-details"):
            yield Static(f"[bold]Stream:[/bold] {self.event_data.get('log_stream', 'N/A')}")
            yield Static(f"[bold]Event ID:[/bold] {self.event_data.get('event_id', 'N/A')}")
            yield Static("[bold]Full Message:[/bold]")
            yield Static(self._format_message(message))

    def _format_message(self, message: str) -> str:
        """
        Format the message, pretty-printing JSON if applicable.

        Args:
            message: Raw log message

        Returns:
            Formatted message (pretty-printed JSON or raw text)
        """
        # Try to parse as JSON and pretty-print
        try:
            parsed = json.loads(message)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON, return as-is
            return message

    def _create_preview(self, message: str) -> str:
        """
        Create a truncated preview of the message.

        Args:
            message: Full log message

        Returns:
            Truncated message with ellipsis if needed
        """
        # Remove newlines for compact display
        single_line = message.replace("\n", " ").strip()

        if len(single_line) > self.PREVIEW_MAX_CHARS:
            return single_line[: self.PREVIEW_MAX_CHARS] + "..."
        return single_line

    def on_mount(self) -> None:
        """Store reference to checkbox on mount."""
        self._checkbox = self.query_one(f"#checkbox-{self.entry_id}", Checkbox)

    def on_click(self) -> None:
        """Toggle expanded state when entry is clicked."""
        self.expanded = not self.expanded

    def watch_expanded(self, expanded: bool) -> None:
        """Update CSS class when expanded state changes."""
        if expanded:
            self.add_class("expanded")
        else:
            self.remove_class("expanded")

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state changes."""
        self._selected = event.value
        self.post_message(self.SelectionChanged(self.entry_id, self._selected))
        event.stop()  # Don't propagate to prevent toggle on entry click

    @property
    def selected(self) -> bool:
        """Get current selection state."""
        return self._selected

    def set_selected(self, value: bool) -> None:
        """
        Programmatically set selection state.

        Args:
            value: New selection state
        """
        if self._checkbox:
            self._checkbox.value = value


class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    """
    Modal screen for previewing and selecting log entries from a log group.

    Displays the most recent log entries and allows users to select
    specific entries to add to the agent's context.

    Returns:
        Dictionary with log_group_name and selected_entries, or None if cancelled
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
    ]

    DEFAULT_CSS = """
    LogPreviewScreen {
        align: center middle;
    }

    #preview-container {
        width: 90%;
        height: 85%;
        max-width: 120;
        background: $panel;
        border: thick $primary;
        padding: 0;
        layout: vertical;
    }

    #preview-header {
        height: 3;
        background: $primary;
        color: $text;
        padding: 1 2;
        text-style: bold;
        width: 100%;
    }

    #timeframe-controls {
        height: 3;
        layout: horizontal;
        padding: 0 1;
        background: $surface;
        align: left middle;
        width: 100%;
    }

    .timeframe-label {
        width: auto;
        padding: 0 1 0 0;
        color: $text-muted;
        text-style: bold;
    }

    #timeframe-selector {
        width: auto;
        layout: horizontal;
        height: auto;
    }

    .timeframe-btn {
        min-width: 10;
        margin: 0 0 0 1;
    }

    .timeframe-btn:first-child {
        margin-left: 0;
    }

    #entry-limit-controls {
        height: 3;
        layout: horizontal;
        padding: 0 1;
        background: $surface;
        align: left middle;
        width: 100%;
    }

    #entry-limit-controls Button {
        min-width: 16;
        margin: 0 1 0 0;
    }

    #entry-count-display {
        width: 1fr;
        text-align: right;
        padding: 1 1;
        color: $text-muted;
    }

    #selection-controls {
        height: 3;
        layout: horizontal;
        padding: 0 1;
        background: $surface;
    }

    #selection-controls Button {
        min-width: 14;
        margin: 0 1 0 0;
    }

    #selection-counter {
        width: 1fr;
        text-align: right;
        padding: 1 1;
        color: $text-muted;
    }

    #log-entries {
        height: 1fr;
        background: $panel;
        padding: 1;
    }

    #action-buttons {
        height: 3;
        layout: horizontal;
        align: center middle;
        padding: 0 1;
        background: $surface;
    }

    #action-buttons Button {
        margin: 0 1;
    }

    #add-to-context-btn {
        background: $success;
    }

    #add-to-context-btn:disabled {
        background: $surface-darken-1;
        color: $text-muted;
    }

    .loading-state {
        width: 100%;
        height: auto;
        padding: 4;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }

    .error-state {
        width: 100%;
        height: auto;
        padding: 4;
        text-align: center;
        color: $error;
    }

    .empty-state {
        width: 100%;
        height: auto;
        padding: 4;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }
    """

    # Fetch parameters
    DEFAULT_TIME_RANGE_MINUTES: int = 15
    DEFAULT_LIMIT: int = 10
    LOAD_MORE_LIMIT: int = 100  # Limit when "Load Last 100" is active

    # Time frame options for selector
    TIME_FRAME_OPTIONS: dict[str, int] = {
        "15 min": 15,
        "1 hour": 60,
        "8 hours": 480,
        "24 hours": 1440,
    }

    # Reactive property for time frame selection
    selected_time_frame: reactive[str] = reactive("15 min")

    # Reactive property for entry limit
    current_limit: reactive[int] = reactive(10)

    def __init__(
        self,
        log_group_name: str,
        datasource: "CloudWatchDataSource",
        time_range_minutes: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize log preview screen.

        Args:
            log_group_name: CloudWatch log group to preview
            datasource: CloudWatch data source for fetching logs
            time_range_minutes: Minutes of history to fetch (default: 15)
            limit: Maximum entries to fetch (default: 10)
            **kwargs: Additional arguments for Screen
        """
        super().__init__(**kwargs)

        # DEBUG: Log initialization
        logger.debug(f"[LOG_PREVIEW] __init__ called for log group: {log_group_name}")
        logger.debug(f"[LOG_PREVIEW] TIME_FRAME_OPTIONS: {self.TIME_FRAME_OPTIONS}")
        logger.debug(f"[LOG_PREVIEW] Initial selected_time_frame: {self.selected_time_frame}")

        self.log_group_name = log_group_name
        self.datasource = datasource
        self.limit = limit or self.DEFAULT_LIMIT

        # Track fetched events and selection state
        self._events: list[dict[str, Any]] = []
        self._selected_ids: set[str] = set()

        # Set initial time frame if custom value provided
        if time_range_minutes:
            # Find matching time frame option
            for label, minutes in self.TIME_FRAME_OPTIONS.items():
                if minutes == time_range_minutes:
                    self.selected_time_frame = label
                    break
            # If no exact match, use default (keeps "15 min")
            logger.debug(
                f"[LOG_PREVIEW] Custom time_range_minutes={time_range_minutes}, selected_time_frame set to: {self.selected_time_frame}"
            )

    @property
    def time_range_minutes(self) -> int:
        """
        Get current time range in minutes based on selected frame.

        Returns:
            Number of minutes for the selected time frame.
            Defaults to 15 if selection is invalid.
        """
        return self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)

    def compose(self) -> ComposeResult:
        """Compose the preview screen layout."""
        logger.debug(
            f"[LOG_PREVIEW] compose() called, selected_time_frame: {self.selected_time_frame}"
        )

        with Container(id="preview-container"):
            # Header with log group name
            yield Static(
                f"Log Preview: {self.log_group_name}",
                id="preview-header",
            )

            # Time frame selector
            logger.debug("[LOG_PREVIEW] Entering timeframe-controls section")
            with Horizontal(id="timeframe-controls"):
                yield Static("Time Frame:", classes="timeframe-label")
                with Horizontal(id="timeframe-selector"):
                    logger.debug(
                        f"[LOG_PREVIEW] Starting to yield buttons for TIME_FRAME_OPTIONS: {list(self.TIME_FRAME_OPTIONS.keys())}"
                    )
                    for label in self.TIME_FRAME_OPTIONS.keys():
                        variant: Literal["default", "primary"] = (
                            "primary" if label == self.selected_time_frame else "default"
                        )
                        logger.debug(
                            f"[LOG_PREVIEW] Yielding button: label='{label}', variant='{variant}', is_selected={label == self.selected_time_frame}"
                        )
                        yield Button(label, variant=variant, classes="timeframe-btn")

            # Entry limit controls
            with Horizontal(id="entry-limit-controls"):
                yield Button(
                    "Load Last 100",
                    id="load-100-btn",
                    variant="default",
                )
                yield Static("", id="entry-count-display")

            # Selection controls
            with Horizontal(id="selection-controls"):
                yield Button("Select All", id="select-all-btn", variant="default")
                yield Button("Deselect All", id="deselect-all-btn", variant="default")
                yield Static("0 of 0 selected", id="selection-counter")

            # Scrollable log entries container
            yield VerticalScroll(id="log-entries")

            # Action buttons
            with Horizontal(id="action-buttons"):
                yield Button(
                    "Add Selected to Context",
                    id="add-to-context-btn",
                    variant="success",
                    disabled=True,  # Enabled when entries are selected
                )
                yield Button("Close", id="close-btn", variant="default")

    async def on_mount(self) -> None:
        """Fetch and display logs when screen mounts."""
        logger.debug("[LOG_PREVIEW] on_mount() called - starting diagnostics")

        # DEBUG: Verify timeframe-selector container exists
        try:
            selector_container = self.query_one("#timeframe-selector", Horizontal)
            logger.debug(f"[LOG_PREVIEW] Found #timeframe-selector container: {selector_container}")
        except Exception as e:
            logger.error(f"[LOG_PREVIEW] Failed to find #timeframe-selector container: {e}")
            selector_container = None

        # DEBUG: Query all buttons in timeframe-selector
        if selector_container:
            try:
                buttons = list(selector_container.query(Button))
                logger.debug(f"[LOG_PREVIEW] Found {len(buttons)} buttons in #timeframe-selector")
                for idx, button in enumerate(buttons):
                    logger.debug(
                        f"[LOG_PREVIEW]   Button {idx}: label='{button.label}', variant='{button.variant}', classes={button.classes}"
                    )
            except Exception as e:
                logger.error(f"[LOG_PREVIEW] Failed to query buttons: {e}")

        # DEBUG: Also try querying buttons with the timeframe-btn class
        try:
            all_timeframe_buttons = list(self.query(".timeframe-btn"))
            logger.debug(
                f"[LOG_PREVIEW] Found {len(all_timeframe_buttons)} buttons with .timeframe-btn class"
            )
        except Exception as e:
            logger.error(f"[LOG_PREVIEW] Failed to query .timeframe-btn buttons: {e}")

        # DEBUG: Query the timeframe-controls container
        try:
            controls_container = self.query_one("#timeframe-controls", Horizontal)
            logger.debug(f"[LOG_PREVIEW] Found #timeframe-controls container: {controls_container}")
            logger.debug(
                f"[LOG_PREVIEW] #timeframe-controls children count: {len(list(controls_container.children))}"
            )
        except Exception as e:
            logger.error(f"[LOG_PREVIEW] Failed to find #timeframe-controls container: {e}")

        self._fetch_and_display_logs()

    def watch_selected_time_frame(self, new_frame: str) -> None:
        """
        Refresh logs when time frame selection changes.

        Called automatically by Textual when selected_time_frame changes.
        Clears current state and triggers a new fetch.

        Args:
            new_frame: The newly selected time frame label
        """
        logger.debug(f"Time frame changed to: {new_frame}")

        # Only refresh if we're already mounted (not during initial compose)
        if not self.is_mounted:
            return

        # Update button visual states
        self._update_timeframe_buttons()

        # Clear current state
        self._events.clear()
        self._selected_ids.clear()

        # Trigger refresh (exclusive worker handles concurrency)
        self._fetch_and_display_logs()

    def _update_timeframe_buttons(self) -> None:
        """Update time frame button visual states to reflect selection."""
        try:
            selector = self.query_one("#timeframe-selector", Horizontal)
            for button in selector.query(Button):
                label = str(button.label)
                if label == self.selected_time_frame:
                    button.variant = "primary"
                else:
                    button.variant = "default"
        except Exception:
            pass  # Buttons may not be mounted yet

    @on(Button.Pressed, "#timeframe-selector Button")
    def on_timeframe_changed(self, event: Button.Pressed) -> None:
        """
        Handle time frame button press.

        Updates the selected_time_frame reactive property, which
        triggers the watcher to refresh the log display.

        Args:
            event: Button pressed event
        """
        button_label = str(event.button.label)

        # Only process valid time frame options
        if button_label in self.TIME_FRAME_OPTIONS:
            # Skip if already selected
            if button_label != self.selected_time_frame:
                self.selected_time_frame = button_label

        # Stop propagation to prevent other handlers
        event.stop()

    @on(Button.Pressed, "#load-100-btn")
    def on_load_100_clicked(self, event: Button.Pressed) -> None:
        """
        Handle 'Load Last 100' button click.

        Toggles between DEFAULT_LIMIT (10) and LOAD_MORE_LIMIT (100).
        The watcher automatically handles clearing state and triggering fetch.

        Args:
            event: Button pressed event
        """
        # Toggle between 10 and 100
        if self.current_limit == self.DEFAULT_LIMIT:
            self.current_limit = self.LOAD_MORE_LIMIT
        else:
            self.current_limit = self.DEFAULT_LIMIT

        # Stop propagation to prevent other handlers
        event.stop()

    def watch_current_limit(self, new_limit: int) -> None:
        """
        Refresh logs when entry limit changes.

        Called automatically by Textual when current_limit reactive property changes.
        Clears current state and triggers a new fetch with the updated limit.

        Args:
            new_limit: The new entry limit (10 or 100)
        """
        logger.debug(f"Entry limit changed to: {new_limit}")

        # Only refresh if we're already mounted (not during initial compose)
        if not self.is_mounted:
            return

        # Update button visual state
        self._update_limit_button()

        # Clear current state to prepare for new data
        self._events.clear()
        self._selected_ids.clear()

        # Trigger refresh (exclusive worker handles concurrency)
        self._fetch_and_display_logs()

    def _update_limit_button(self) -> None:
        """
        Update the limit button's label and variant based on current state.

        When at default (10): Shows "Load Last 100" with default variant
        When at 100: Shows "Show Last 10" with primary variant
        """
        try:
            button = self.query_one("#load-100-btn", Button)
            if self.current_limit == self.LOAD_MORE_LIMIT:
                button.label = "Show Last 10"
                button.variant = "primary"
            else:
                button.label = "Load Last 100"
                button.variant = "default"
        except Exception:
            pass  # Button may not be mounted yet

    def _update_entry_count_display(self) -> None:
        """
        Update the entry count display to show current number of entries.

        Shows "Showing X entries" where X is the actual count fetched.
        Display is empty when no entries exist.
        """
        try:
            display = self.query_one("#entry-count-display", Static)
            total = len(self._events)
            if total > 0:
                display.update(f"Showing {total} entries")
            else:
                display.update("")
        except Exception:
            pass  # Widget may not be mounted yet

    @work(exclusive=True)
    async def _fetch_and_display_logs(self) -> None:
        """Worker to fetch and display logs asynchronously."""
        container = self.query_one("#log-entries", VerticalScroll)

        # Clear existing entries before loading new ones
        await container.remove_children()

        # Show loading state
        loading = Static(
            "Loading recent log entries...",
            classes="loading-state",
        )
        await container.mount(loading)

        try:
            # Calculate time range
            end_time = int(time.time() * 1000)
            start_time = end_time - (self.time_range_minutes * 60 * 1000)

            # Fetch logs from CloudWatch
            self._events = await self.datasource.fetch_logs(
                log_group=self.log_group_name,
                start_time=start_time,
                end_time=end_time,
                limit=self.current_limit,
            )
            logger.debug(f"Fetched {len(self._events)} events with limit={self.current_limit}")

            # Remove loading indicator
            loading.remove()

            # Display events or empty state
            if self._events:
                self._display_events(container)
            else:
                container.mount(
                    Static(
                        f"No log entries found in the last {self.selected_time_frame}.\n\n"
                        "The log group may have no recent activity,\n"
                        "or logs may be outside this time window.",
                        classes="empty-state",
                    )
                )

            # Update selection counter
            self._update_selection_counter()

            # Update entry count display
            self._update_entry_count_display()

        except Exception as e:
            logger.error(f"Failed to fetch logs for preview: {e}", exc_info=True)
            loading.remove()

            # Determine user-friendly error message
            error_message = self._format_error_message(e)
            container.mount(
                Static(
                    f"[red]Error loading logs:[/red]\n\n{error_message}",
                    classes="error-state",
                )
            )

    def _format_error_message(self, error: Exception) -> str:
        """
        Format exception into user-friendly error message.

        Args:
            error: The exception that occurred

        Returns:
            User-friendly error message
        """
        error_str = str(error)
        error_type = type(error).__name__

        # Check for known error patterns
        if "ResourceNotFoundException" in error_str or "LogGroupNotFoundError" in error_type:
            return (
                f"Log group '{self.log_group_name}' was not found.\n\n"
                "It may have been deleted or you may not have access.\n"
                "Try refreshing the log groups list with /refresh."
            )
        elif "AccessDenied" in error_str or "AuthenticationError" in error_type:
            return (
                "Access denied to this log group.\n\n"
                "Please check your IAM permissions include:\n"
                "- logs:FilterLogEvents"
            )
        elif "ThrottlingException" in error_str or "RateLimitError" in error_type:
            return "AWS rate limit exceeded.\n\nPlease wait a moment and try again."
        elif "timeout" in error_str.lower():
            return (
                "Request timed out.\n\n"
                "The log group may have a large volume of logs.\n"
                "Please try again in a moment."
            )
        else:
            return f"An unexpected error occurred:\n{error_str}"

    def _display_events(self, container: VerticalScroll) -> None:
        """
        Display fetched log events in the container.

        Args:
            container: The scrollable container to mount entries into
        """
        for idx, event in enumerate(self._events):
            entry_id = f"entry-{idx}"
            entry = LogEntryItem(
                event_data=event,
                entry_id=entry_id,
                id=entry_id,
            )
            container.mount(entry)

    def _update_selection_counter(self) -> None:
        """Update the selection counter text."""
        try:
            counter = self.query_one("#selection-counter", Static)
            total = len(self._events)
            selected = len(self._selected_ids)
            counter.update(f"{selected} of {total} selected")

            # Enable/disable add button based on selection
            add_btn = self.query_one("#add-to-context-btn", Button)
            add_btn.disabled = selected == 0
        except Exception:
            pass  # Widget may not be mounted yet

    @on(LogEntryItem.SelectionChanged)
    def on_entry_selection_changed(self, event: LogEntryItem.SelectionChanged) -> None:
        """Handle selection state changes from log entries."""
        if event.selected:
            self._selected_ids.add(event.entry_id)
        else:
            self._selected_ids.discard(event.entry_id)

        self._update_selection_counter()

    @on(Button.Pressed, "#select-all-btn")
    def on_select_all(self) -> None:
        """Select all log entries."""
        for idx, _ in enumerate(self._events):
            entry_id = f"entry-{idx}"
            try:
                entry = self.query_one(f"#{entry_id}", LogEntryItem)
                entry.set_selected(True)
                self._selected_ids.add(entry_id)
            except Exception:
                pass

        self._update_selection_counter()

    @on(Button.Pressed, "#deselect-all-btn")
    def on_deselect_all(self) -> None:
        """Deselect all log entries."""
        for idx, _ in enumerate(self._events):
            entry_id = f"entry-{idx}"
            try:
                entry = self.query_one(f"#{entry_id}", LogEntryItem)
                entry.set_selected(False)
            except Exception:
                pass

        self._selected_ids.clear()
        self._update_selection_counter()

    @on(Button.Pressed, "#add-to-context-btn")
    def on_add_to_context(self) -> None:
        """Add selected entries to context and close modal."""
        # Gather selected events
        selected_events = []
        for idx, event in enumerate(self._events):
            entry_id = f"entry-{idx}"
            if entry_id in self._selected_ids:
                selected_events.append(event)
                # Log progress every 10 events
                if len(selected_events) % 10 == 0 or len(selected_events) == len(
                    self._selected_ids
                ):
                    logger.debug(
                        f"Gathered {len(selected_events)} of {len(self._selected_ids)} selected events"
                    )

        # Log final counts before dismiss
        logger.debug(f"Total selected_ids: {len(self._selected_ids)}")
        logger.debug(f"Total selected_events gathered: {len(selected_events)}")
        logger.debug(f"Dismissing modal with {len(selected_events)} entries")

        # Return result and dismiss
        result = {
            "log_group_name": self.log_group_name,
            "selected_entries": selected_events,
        }
        self.dismiss(result)

    @on(Button.Pressed, "#close-btn")
    def on_close(self) -> None:
        """Close modal without adding to context."""
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key - close without action."""
        self.dismiss(None)
