# Design Document: Log Group Preview Feature

**Version:** 1.0
**Author:** Saanvi (Senior Software Architect)
**Date:** February 18, 2026
**Status:** Ready for Implementation

---

## 1. Executive Summary

### Feature Overview
The Log Preview feature enables users to double-click any log group in the sidebar to open a modal displaying the 10 most recent log entries. Users can select specific entries via checkboxes and add them to the agent's context for analysis, creating a seamless workflow between log exploration and AI-assisted troubleshooting.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trigger mechanism | Double-click with manual timer detection | Textual doesn't have native double-click; 500ms threshold is standard |
| Modal vs. inline display | Modal (ModalScreen) | Less disruptive, can be dismissed easily, follows user expectation |
| Log fetching strategy | Fetch on modal open | Ensures fresh data; caching adds complexity for MVP |
| Entry display format | Compact with expand-on-click | Balances overview with detail access |
| Context injection method | Orchestrator's `inject_context_update()` | Reuses existing pattern, well-tested |
| Entry limit | 10 entries (last 15 minutes) | Per requirements; prevents overwhelming UI |

### Implementation Complexity Estimate
**Medium complexity** - Estimated 4-6 hours for implementation

- 2 new files (screen + widget updates)
- 3 modified files
- ~400 lines of new code
- Well-defined patterns to follow

---

## 2. Architecture Overview

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LogAIApp (Main Application)                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ChatScreen (Main Screen)                            │
│  ┌─────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────┐  │
│  │ LogGroupsSidebar│  │     MessagesContainer       │  │  ToolCallsSidebar   │  │
│  │                 │  │                             │  │                     │  │
│  │ ┌─────────────┐ │  │  ┌─────────────────────┐   │  │                     │  │
│  │ │ClickableLG  │─┼──┼─▶│ Message Handler     │   │  │                     │  │
│  │ │   Item      │ │  │  │ @on(PreviewRequested)│   │  │                     │  │
│  │ └─────────────┘ │  │  └─────────────────────┘   │  │                     │  │
│  │ ┌─────────────┐ │  │             │              │  │                     │  │
│  │ │ClickableLG  │ │  │             ▼              │  │                     │  │
│  │ │   Item      │ │  │   app.push_screen()        │  │                     │  │
│  │ └─────────────┘ │  │                             │  │                     │  │
│  └─────────────────┘  └─────────────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        LogPreviewScreen (Modal Overlay)                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ Header: "Log Preview: /aws/lambda/my-function"               [X] Close      ││
│  ├─────────────────────────────────────────────────────────────────────────────┤│
│  │ [ ] Select All    [ ] Deselect All                   "3 of 10 selected"     ││
│  ├─────────────────────────────────────────────────────────────────────────────┤│
│  │ ┌─────────────────────────────────────────────────────────────────────────┐ ││
│  │ │ [✓] 2026-02-18 10:30:45.123 | START RequestId: abc-123-def...          │ ││
│  │ ├─────────────────────────────────────────────────────────────────────────┤ ││
│  │ │ [ ] 2026-02-18 10:30:45.456 | [INFO] Processing request for user...    │ ││
│  │ ├─────────────────────────────────────────────────────────────────────────┤ ││
│  │ │ [✓] 2026-02-18 10:30:46.789 | [ERROR] Connection timeout to...         │ ││
│  │ │     ▼ EXPANDED VIEW                                                     │ ││
│  │ │     Stream: 2026/02/18/[$LATEST]abc123                                  │ ││
│  │ │     Full message: Connection timeout to database server at...           │ ││
│  │ └─────────────────────────────────────────────────────────────────────────┘ ││
│  ├─────────────────────────────────────────────────────────────────────────────┤│
│  │                    [ Add Selected to Context ] (disabled if none)           ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interaction Sequence

```
User Action          LogGroupsSidebar      ChatScreen        LogPreviewScreen       CloudWatch
    │                      │                   │                    │                   │
    │ Double-click         │                   │                    │                   │
    │ "my-log-group"       │                   │                    │                   │
    ├─────────────────────▶│                   │                    │                   │
    │                      │ emit              │                    │                   │
    │                      │ PreviewRequested  │                    │                   │
    │                      ├──────────────────▶│                    │                   │
    │                      │                   │ push_screen()      │                   │
    │                      │                   ├───────────────────▶│                   │
    │                      │                   │                    │ on_mount()        │
    │                      │                   │                    │ fetch_logs()      │
    │                      │                   │                    ├──────────────────▶│
    │                      │                   │                    │◀──────────────────┤
    │                      │                   │                    │ display events    │
    │◀─────────────────────┼───────────────────┼────────────────────┤                   │
    │                      │                   │                    │                   │
    │ Select entries       │                   │                    │                   │
    │ Click "Add to        │                   │                    │                   │
    │ Context"             │                   │                    │                   │
    ├─────────────────────▶│                   │                    │                   │
    │                      │                   │◀───────────────────┤ dismiss(result)   │
    │                      │                   │                    │                   │
    │                      │                   │ inject_context_update()               │
    │                      │                   │ mount SystemMessage                   │
    │◀─────────────────────┼───────────────────┤                    │                   │
```

### 2.3 Data Flow

1. **User Action → Event**: Double-click on `ClickableLogGroupItem` widget
2. **Event Detection**: Widget detects double-click via timer (< 500ms between clicks)
3. **Message Emission**: Widget posts `LogGroupPreviewRequested` message
4. **Screen Handler**: `ChatScreen` catches message via `@on(LogGroupPreviewRequested)`
5. **Modal Open**: `app.push_screen(LogPreviewScreen)` with log group name
6. **Data Fetch**: Modal's `on_mount()` calls `CloudWatchDataSource.fetch_logs()`
7. **Display**: Events rendered in scrollable list with checkboxes
8. **Selection**: User selects entries, clicks "Add to Context"
9. **Context Injection**: Modal dismisses with selected entries, ChatScreen injects via orchestrator
10. **Feedback**: System message displayed in chat confirming addition

---

## 3. Component Design

### 3.1 ClickableLogGroupItem Widget

**File:** `src/logai/ui/widgets/log_groups_sidebar.py` (add to existing file)

**Purpose:** Extend the existing `Label` widget to detect double-clicks and emit preview requests.

#### Class Definition

```python
from textual.events import Click
from textual.message import Message
from textual.widgets import Label
import time
from typing import Any


class ClickableLogGroupItem(Label):
    """
    Clickable log group label that emits preview requests on double-click.

    This widget extends Label to detect double-click events and notify
    parent components when a user wants to preview a log group.

    Attributes:
        log_group_name: The CloudWatch log group name this item represents
    """

    # Custom message for preview requests
    class LogGroupPreviewRequested(Message):
        """Emitted when user double-clicks to request log preview."""

        def __init__(self, log_group_name: str) -> None:
            """
            Initialize preview request message.

            Args:
                log_group_name: Name of the log group to preview
            """
            super().__init__()
            self.log_group_name = log_group_name

    # Double-click detection threshold in seconds
    DOUBLE_CLICK_THRESHOLD: float = 0.5

    def __init__(self, log_group_name: str, **kwargs: Any) -> None:
        """
        Initialize clickable log group item.

        Args:
            log_group_name: CloudWatch log group name
            **kwargs: Additional arguments passed to Label
        """
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name
        self._last_click_time: float = 0.0

    def on_click(self, event: Click) -> None:
        """
        Handle click events and detect double-clicks.

        Uses timestamp comparison to detect two clicks within
        DOUBLE_CLICK_THRESHOLD seconds.

        Args:
            event: The click event from Textual
        """
        # Only handle left mouse button
        if event.button != 1:
            return

        current_time = time.time()
        time_since_last = current_time - self._last_click_time

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            # Double-click detected - emit preview request
            self.post_message(self.LogGroupPreviewRequested(self.log_group_name))
            # Reset timer to prevent triple-click triggering again
            self._last_click_time = 0.0
        else:
            # Single click - record time for potential double-click
            self._last_click_time = current_time
```

#### CSS Updates

Add to `LogGroupsSidebar.DEFAULT_CSS`:

```css
LogGroupsSidebar .log-group-item {
    width: 100%;
    height: auto;
    padding: 0;
    color: $text;
    cursor: pointer;  /* NEW: Visual feedback for clickability */
}

LogGroupsSidebar .log-group-item:hover {
    background: $surface;
}

LogGroupsSidebar .log-group-item:active {
    background: $primary-darken-1;  /* NEW: Click feedback */
}
```

#### Integration with `_populate_log_groups()`

Change line 160 in existing `_populate_log_groups()` method:

```python
# OLD:
label = Label(name, classes="log-group-item")

# NEW:
label = ClickableLogGroupItem(name, classes="log-group-item")
```

---

### 3.2 LogPreviewScreen Modal

**File:** `src/logai/ui/screens/log_preview.py` (new file)

**Purpose:** Modal screen for displaying and selecting recent log entries.

#### Data Structures

```python
from typing import TypedDict
from dataclasses import dataclass


class LogEventData(TypedDict):
    """Type definition for CloudWatch log event data."""
    timestamp: int          # Epoch milliseconds
    message: str            # Log message content
    log_stream: str         # Log stream name
    event_id: str           # Unique event identifier


@dataclass
class LogPreviewResult:
    """Result returned when modal is dismissed after selection."""
    log_group_name: str
    selected_entries: list[LogEventData]

    @property
    def count(self) -> int:
        """Number of selected entries."""
        return len(self.selected_entries)
```

#### Screen Layout Structure

```
LogPreviewScreen
├── Container#preview-container (main modal container)
│   ├── Static#preview-header (title + close button)
│   ├── Container#selection-controls (select all/deselect all + counter)
│   │   ├── Button#select-all-btn
│   │   ├── Button#deselect-all-btn
│   │   └── Static#selection-counter
│   ├── VerticalScroll#log-entries (scrollable log list)
│   │   └── LogEntryItem (repeated for each entry)
│   └── Container#action-buttons
│       ├── Button#add-to-context-btn
│       └── Button#close-btn
```

#### Full Implementation

```python
"""Log preview screen for displaying and selecting recent log events."""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
            yield Static(message)

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
            return single_line[:self.PREVIEW_MAX_CHARS] + "..."
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
        padding: 1;
    }

    #preview-header {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        padding: 1 2;
        text-style: bold;
        width: 100%;
    }

    #selection-controls {
        dock: top;
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
        dock: bottom;
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
        self.log_group_name = log_group_name
        self.datasource = datasource
        self.time_range_minutes = time_range_minutes or self.DEFAULT_TIME_RANGE_MINUTES
        self.limit = limit or self.DEFAULT_LIMIT

        # Track fetched events and selection state
        self._events: list[dict[str, Any]] = []
        self._selected_ids: set[str] = set()

    def compose(self) -> ComposeResult:
        """Compose the preview screen layout."""
        with Container(id="preview-container"):
            # Header with log group name
            yield Static(
                f"Log Preview: {self.log_group_name}",
                id="preview-header",
            )

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
        self._fetch_and_display_logs()

    @work(exclusive=True)
    async def _fetch_and_display_logs(self) -> None:
        """Worker to fetch and display logs asynchronously."""
        container = self.query_one("#log-entries", VerticalScroll)

        # Show loading state
        loading = Static(
            "Loading recent log entries...",
            classes="loading-state",
        )
        container.mount(loading)

        try:
            # Calculate time range
            end_time = int(time.time() * 1000)
            start_time = end_time - (self.time_range_minutes * 60 * 1000)

            # Fetch logs from CloudWatch
            self._events = await self.datasource.fetch_logs(
                log_group=self.log_group_name,
                start_time=start_time,
                end_time=end_time,
                limit=self.limit,
            )

            # Remove loading indicator
            loading.remove()

            # Display events or empty state
            if self._events:
                self._display_events(container)
            else:
                container.mount(
                    Static(
                        f"No log entries found in the last {self.time_range_minutes} minutes.\n\n"
                        "The log group may have no recent activity,\n"
                        "or logs may be outside this time window.",
                        classes="empty-state",
                    )
                )

            # Update selection counter
            self._update_selection_counter()

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
            return (
                "AWS rate limit exceeded.\n\n"
                "Please wait a moment and try again."
            )
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
```

---

### 3.3 LogEntryItem Widget

**Note:** Defined inline within `log_preview.py` (see section 3.2)

#### Compact View Format

The compact view shows:
- **Timestamp**: `YYYY-MM-DD HH:MM:SS.mmm` format (e.g., `2026-02-18 10:30:45.123`)
- **Message Preview**: First 100 characters with ellipsis if truncated
- **Expand Hint**: "(click to expand)" shown only when message exceeds 100 chars

Example:
```
[✓] 2026-02-18 10:30:45.123
    [ERROR] Connection refused when attempting to connect to database...
    (click to expand)
```

#### Expanded View Format

When expanded, shows:
- **Log Stream**: Full stream name
- **Event ID**: CloudWatch event identifier
- **Full Message**: Complete log message (may be multi-line)

---

## 4. Data Flow Design

### 4.1 Event Emission → Modal Opening

```python
# In ClickableLogGroupItem.on_click()
if double_click_detected:
    self.post_message(self.LogGroupPreviewRequested(self.log_group_name))

# Message bubbles up to ChatScreen which has handler:
@on(ClickableLogGroupItem.LogGroupPreviewRequested)
async def on_log_group_preview_requested(
    self,
    event: ClickableLogGroupItem.LogGroupPreviewRequested
) -> None:
    # Open preview modal
    result = await self.app.push_screen(
        LogPreviewScreen(
            log_group_name=event.log_group_name,
            datasource=self.datasource,  # Must be available on ChatScreen
        )
    )

    if result:
        # User selected entries - inject into context
        await self._inject_log_entries_to_context(result)
```

### 4.2 Modal Dismissal → Context Injection

```python
# In ChatScreen
async def _inject_log_entries_to_context(self, result: dict[str, Any]) -> None:
    """
    Inject selected log entries into agent context.

    Args:
        result: Dictionary with log_group_name and selected_entries
    """
    log_group = result["log_group_name"]
    entries = result["selected_entries"]
    count = len(entries)

    # Format entries for context
    context_message = self._format_log_entries_for_context(log_group, entries)

    # Inject via orchestrator
    self.orchestrator.inject_context_update(context_message)

    # Show system message in chat
    messages_container = self.query_one("#messages-container", VerticalScroll)
    system_msg = SystemMessage(
        f"Added {count} log entr{'y' if count == 1 else 'ies'} from {log_group} to context"
    )
    messages_container.mount(system_msg)
    messages_container.scroll_end(animate=False)
```

### 4.3 Context Message Format

```python
def _format_log_entries_for_context(
    self,
    log_group: str,
    entries: list[dict[str, Any]]
) -> str:
    """
    Format log entries for agent context injection.

    Args:
        log_group: Name of the log group
        entries: List of log event dictionaries

    Returns:
        Formatted context string
    """
    import json
    from datetime import datetime

    formatted_entries = []
    for entry in entries:
        # Format timestamp for readability
        timestamp_ms = entry.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        formatted_entries.append({
            "timestamp": formatted_time,
            "message": entry.get("message", ""),
            "log_stream": entry.get("log_stream", ""),
        })

    return f"""USER-SELECTED LOG ENTRIES for analysis:

Log Group: {log_group}
Entry Count: {len(entries)}

The user has specifically selected these log entries for your analysis:

```json
{json.dumps(formatted_entries, indent=2)}
```

Please analyze these logs and provide insights based on the user's next question."""
```

---

## 5. API Integration

### 5.1 CloudWatch `fetch_logs` Call

**Method:** `CloudWatchDataSource.fetch_logs()`

**Parameters:**
```python
await self.datasource.fetch_logs(
    log_group=self.log_group_name,    # "/aws/lambda/my-function"
    start_time=start_time,             # Epoch milliseconds (now - 15 min)
    end_time=end_time,                 # Epoch milliseconds (now)
    limit=10,                          # Maximum 10 entries
)
```

**Time Range Calculation:**
```python
import time

end_time = int(time.time() * 1000)                    # Now in epoch ms
start_time = end_time - (15 * 60 * 1000)              # 15 minutes ago
```

### 5.2 Response Structure

```python
[
    {
        "timestamp": 1708263045123,           # Epoch milliseconds
        "message": "START RequestId: abc-123", # Log message
        "log_stream": "2026/02/18/[$LATEST]abc", # Stream name
        "event_id": "37196459123456789012345"  # CloudWatch event ID
    },
    # ... more events
]
```

### 5.3 Error Handling

The existing `CloudWatchDataSource` raises these exceptions:

| Exception | When | User Message |
|-----------|------|--------------|
| `LogGroupNotFoundError` | Log group doesn't exist | "Log group was not found..." |
| `AuthenticationError` | IAM permission denied | "Access denied to this log group..." |
| `RateLimitError` | CloudWatch rate limit hit | "AWS rate limit exceeded..." |
| `DataSourceError` | General API failure | "An unexpected error occurred..." |

---

## 6. State Management

### 6.1 Modal State

| State Variable | Type | Purpose |
|----------------|------|---------|
| `_events` | `list[dict]` | Fetched log events |
| `_selected_ids` | `set[str]` | Entry IDs that are selected |

### 6.2 Loading State Flow

```
1. Modal opens → Show "Loading recent log entries..."
2. API call in progress → Loading indicator visible
3. API success → Remove loading, display entries
4. API error → Remove loading, show error message
5. No results → Remove loading, show empty state message
```

### 6.3 Selection State

```python
# Track selections with entry IDs
_selected_ids: set[str] = set()

# On checkbox change
@on(LogEntryItem.SelectionChanged)
def on_entry_selection_changed(self, event):
    if event.selected:
        self._selected_ids.add(event.entry_id)
    else:
        self._selected_ids.discard(event.entry_id)
    self._update_selection_counter()
```

---

## 7. User Interaction Design

### 7.1 Trigger Actions

| Action | Method | Result |
|--------|--------|--------|
| Double-click log group | Left-click twice within 500ms | Opens preview modal |
| Single-click log group | Left-click once | No action (records timestamp) |

### 7.2 Modal Navigation

| Action | Trigger | Result |
|--------|---------|--------|
| Close | Press `ESC` | Modal closes, no action |
| Close | Click "Close" button | Modal closes, no action |
| Close | Click outside modal | Modal closes, no action |
| Add to context | Click "Add Selected to Context" | Modal closes, entries added |

### 7.3 Entry Interactions

| Action | Trigger | Result |
|--------|---------|--------|
| Select entry | Click checkbox | Entry marked as selected |
| Expand entry | Click anywhere on entry (not checkbox) | Shows full details |
| Collapse entry | Click expanded entry | Hides details |
| Select all | Click "Select All" button | All checkboxes checked |
| Deselect all | Click "Deselect All" button | All checkboxes unchecked |

### 7.4 Button States

| Button | Enabled When | Disabled When |
|--------|--------------|---------------|
| "Select All" | Always | Never |
| "Deselect All" | Always | Never |
| "Add Selected to Context" | 1+ entries selected | No entries selected |
| "Close" | Always | Never |

---

## 8. Context Integration Design

### 8.1 Context Injection Flow

```
1. User clicks "Add Selected to Context"
2. Modal gathers selected entries from _events list
3. Modal calls self.dismiss(result) with:
   {
     "log_group_name": "/aws/lambda/my-function",
     "selected_entries": [{...}, {...}]
   }
4. ChatScreen receives result from push_screen()
5. ChatScreen formats entries as context message
6. ChatScreen calls orchestrator.inject_context_update(context_message)
7. ChatScreen mounts SystemMessage in chat
8. Next user query will include the injected context
```

### 8.2 System Message Format

Display in chat:
```
Added 3 log entries from /aws/lambda/my-function to context
```

### 8.3 Context Message Structure

The injected context follows this template:

```
USER-SELECTED LOG ENTRIES for analysis:

Log Group: /aws/lambda/my-function
Entry Count: 3

The user has specifically selected these log entries for your analysis:

```json
[
  {
    "timestamp": "2026-02-18 10:30:45.123",
    "message": "START RequestId: abc-123...",
    "log_stream": "2026/02/18/[$LATEST]abc"
  },
  ...
]
```

Please analyze these logs and provide insights based on the user's next question.
```

### 8.4 Token Considerations

**Estimated tokens per entry:** ~50-200 tokens depending on message length

**Total context estimate for 10 entries:** ~500-2000 tokens

**Recommendation:** The existing context budget tracker will handle pruning if context becomes too large. No special handling needed for MVP.

---

## 9. Error Handling Strategy

### 9.1 Error Categories & User Messages

| Scenario | Error Type | User Message |
|----------|------------|--------------|
| Log group deleted | `LogGroupNotFoundError` | "Log group '{name}' was not found. It may have been deleted or you may not have access. Try refreshing the log groups list with /refresh." |
| No permission | `AuthenticationError` | "Access denied to this log group. Please check your IAM permissions include: logs:FilterLogEvents" |
| Rate limited | `RateLimitError` | "AWS rate limit exceeded. Please wait a moment and try again." |
| Network timeout | `TimeoutError` | "Request timed out. The log group may have a large volume of logs. Please try again in a moment." |
| Empty results | N/A (success) | "No log entries found in the last 15 minutes. The log group may have no recent activity, or logs may be outside this time window." |
| Unknown error | `Exception` | "An unexpected error occurred: {error message}" |

### 9.2 Error Display

Errors are displayed within the modal's log entries container:

```
┌─────────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-function    │
├─────────────────────────────────────────┤
│                                         │
│    [red]Error loading logs:[/red]       │
│                                         │
│    Access denied to this log group.     │
│                                         │
│    Please check your IAM permissions    │
│    include:                             │
│    - logs:FilterLogEvents               │
│                                         │
├─────────────────────────────────────────┤
│              [ Close ]                  │
└─────────────────────────────────────────┘
```

### 9.3 Retry Strategy

- Built-in retry in `CloudWatchDataSource` (3 attempts with exponential backoff)
- User can close modal and double-click again to retry
- No automatic retry in modal for MVP (user-initiated retry is simpler)

---

## 10. Testing Strategy

### 10.1 Unit Tests

**File:** `tests/unit/ui/test_log_preview.py`

```python
"""Unit tests for log preview feature."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem
from logai.ui.screens.log_preview import LogPreviewScreen, LogEntryItem


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
        assert "/refresh" in message

    @pytest.mark.asyncio
    async def test_formats_error_for_access_denied(self):
        """Should provide helpful message for permission errors."""
        datasource = AsyncMock()
        screen = LogPreviewScreen(
            log_group_name="/aws/lambda/private",
            datasource=datasource,
        )

        from logai.providers.datasources.base import AuthenticationError
        error = AuthenticationError("access denied")

        message = screen._format_error_message(error)
        assert "access denied" in message.lower()
        assert "FilterLogEvents" in message
```

### 10.2 Integration Tests

**File:** `tests/integration/ui/test_log_preview_integration.py`

```python
"""Integration tests for log preview feature end-to-end flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from textual.pilot import Pilot

from logai.ui.app import LogAIApp


class TestLogPreviewIntegration:
    """Integration tests for the log preview feature."""

    @pytest.mark.asyncio
    async def test_double_click_opens_preview(self, app_with_log_groups):
        """Double-clicking log group should open preview modal."""
        async with app_with_log_groups.run_test() as pilot:
            # Find log group item
            sidebar = app_with_log_groups.query_one("LogGroupsSidebar")
            item = sidebar.query("ClickableLogGroupItem").first()

            # Simulate double-click
            await pilot.click(item)
            await pilot.click(item)

            # Check modal opened
            screens = app_with_log_groups.screen_stack
            assert any("LogPreviewScreen" in str(type(s)) for s in screens)

    @pytest.mark.asyncio
    async def test_escape_closes_modal(self, app_with_preview_open):
        """ESC key should close the preview modal."""
        async with app_with_preview_open.run_test() as pilot:
            # Press escape
            await pilot.press("escape")

            # Check modal closed
            screens = app_with_preview_open.screen_stack
            assert not any("LogPreviewScreen" in str(type(s)) for s in screens)

    @pytest.mark.asyncio
    async def test_add_to_context_creates_system_message(
        self,
        app_with_entries_selected
    ):
        """Adding entries to context should show system message."""
        async with app_with_entries_selected.run_test() as pilot:
            # Click add to context button
            button = app_with_entries_selected.query_one("#add-to-context-btn")
            await pilot.click(button)

            # Check system message appeared
            messages = app_with_entries_selected.query("SystemMessage")
            assert any("Added" in str(m.renderable) for m in messages)
```

### 10.3 Manual Testing Checklist

**Pre-conditions:**
- [ ] App is running with valid AWS credentials
- [ ] At least one log group exists with recent logs
- [ ] Log groups sidebar is visible (F1/F2 to toggle)

**Double-click Detection:**
- [ ] Single click on log group does nothing
- [ ] Double-click (fast) opens preview modal
- [ ] Slow double-click (>500ms apart) does not open modal
- [ ] Right-click does not affect behavior

**Modal Display:**
- [ ] Modal title shows correct log group name
- [ ] Loading indicator appears while fetching
- [ ] Log entries display with correct timestamps
- [ ] Message previews are truncated appropriately
- [ ] Expand hint shows for long messages

**Selection Behavior:**
- [ ] Clicking checkbox selects/deselects entry
- [ ] "Select All" checks all checkboxes
- [ ] "Deselect All" unchecks all checkboxes
- [ ] Counter shows "X of Y selected"
- [ ] "Add to Context" button enabled when entries selected
- [ ] "Add to Context" button disabled when none selected

**Entry Expansion:**
- [ ] Clicking entry (not checkbox) expands it
- [ ] Expanded view shows stream name, event ID, full message
- [ ] Clicking again collapses entry
- [ ] Expansion doesn't affect checkbox state

**Modal Closing:**
- [ ] ESC key closes modal
- [ ] "Close" button closes modal
- [ ] Closing without selection adds nothing to context
- [ ] "Add to Context" closes modal and adds entries

**Context Integration:**
- [ ] System message appears in chat after adding entries
- [ ] Message shows correct count and log group name
- [ ] Agent can reference the logs in subsequent queries

**Error Handling:**
- [ ] Empty log group shows appropriate message
- [ ] Permission error shows helpful guidance
- [ ] Network error shows retry suggestion
- [ ] Rate limit error shows wait message

### 10.4 Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Log group with 0 entries in last 15 min | Show empty state message |
| Log group deleted between list and preview | Show "not found" error |
| Very long log messages (>10KB) | Truncate in display, full in expand |
| Log messages with special characters | Properly escaped/rendered |
| Multiple rapid double-clicks | Only one modal opens |
| Modal open while sidebar hidden | Modal still functions |
| Network disconnection mid-fetch | Show error, allow retry |

---

## 11. Implementation Phases

### Phase 1: Clickable Widget + Basic Modal (2 hours)

**Goal:** Get double-click detection working and modal opening

**Tasks:**
1. Add `ClickableLogGroupItem` class to `log_groups_sidebar.py`
2. Update `_populate_log_groups()` to use new widget
3. Create basic `LogPreviewScreen` with layout (no data fetching)
4. Add handler in `ChatScreen` to open modal
5. Verify double-click opens modal, ESC closes it

**Deliverables:**
- Clickable log group items
- Modal opens/closes correctly
- Basic modal layout visible

### Phase 2: Log Fetching and Display (1.5 hours)

**Goal:** Fetch and display real log data

**Tasks:**
1. Implement `_fetch_and_display_logs()` worker method
2. Create `LogEntryItem` widget with compact view
3. Add loading state indicator
4. Connect to `CloudWatchDataSource`
5. Display fetched entries in scrollable list

**Deliverables:**
- Real logs displayed in modal
- Loading indicator shown during fetch
- Timestamps and messages visible

### Phase 3: Selection and Context Integration (1.5 hours)

**Goal:** Enable selection and context injection

**Tasks:**
1. Add checkbox to `LogEntryItem`
2. Implement selection tracking (`_selected_ids` set)
3. Add "Select All" / "Deselect All" buttons
4. Implement `_format_log_entries_for_context()`
5. Wire up `orchestrator.inject_context_update()`
6. Display `SystemMessage` after adding to context

**Deliverables:**
- Checkboxes work correctly
- Selection counter updates
- Entries added to context successfully
- System message appears in chat

### Phase 4: Polish and Error Handling (1 hour)

**Goal:** Production-ready feature

**Tasks:**
1. Add expand/collapse functionality to `LogEntryItem`
2. Implement error message formatting
3. Add empty state handling
4. Update CSS for visual polish
5. Write unit tests
6. Manual testing and bug fixes

**Deliverables:**
- All error states handled gracefully
- Expand/collapse works
- Tests passing
- Feature complete

---

## 12. Security & Performance Considerations

### 12.1 Authentication

- **Reuse existing credentials**: `CloudWatchDataSource` already handles AWS auth
- **No new credential storage**: Use the instance passed from app initialization
- **Permission scope**: Requires `logs:FilterLogEvents` permission (already needed for other features)

### 12.2 Rate Limiting

| Concern | Mitigation |
|---------|------------|
| Rapid double-clicks | Reset timer after double-click detected |
| Multiple modal opens | `@work(exclusive=True)` ensures single fetch |
| CloudWatch rate limit | Built-in retry with exponential backoff |

### 12.3 Caching Strategy

**MVP Decision: No caching**

**Rationale:**
- Logs should be fresh (especially for debugging recent issues)
- 10 entries is a small payload (~1-5KB)
- Adding cache invalidation adds complexity
- User can re-open modal for updated data

**Future Enhancement:** Consider 30-second TTL cache if users complain about latency.

### 12.4 Memory Management

| Concern | Mitigation |
|---------|------------|
| Large log messages | Truncate display to 500 chars |
| Many modal opens | Textual handles screen cleanup on dismiss |
| Event storage | Only store 10 events max in `_events` list |

### 12.5 PII Considerations

- **Note:** Log preview does NOT apply PII sanitization (unlike FetchLogsTool)
- **Rationale:** User is viewing their own logs directly, similar to AWS Console
- **Future Enhancement:** Optional sanitization toggle if requested

---

## 13. Future Enhancements

These features are explicitly **out of scope** for MVP but noted for future consideration:

### High Priority (Post-MVP)
1. **Custom time range selector**: Allow 1h, 6h, 24h options
2. **JSON pretty-printing**: Format JSON messages for readability
3. **Copy to clipboard**: Button to copy selected entries

### Medium Priority
4. **Search/filter in preview**: Filter displayed entries by text
5. **Keyboard navigation**: Arrow keys to navigate entries
6. **Single-click quick preview**: Show tooltip on hover

### Lower Priority
7. **Export to file**: Save selected entries to JSON/text file
8. **Live streaming**: Auto-refresh to show new logs
9. **Log stream filtering**: Filter by specific streams
10. **Pagination**: Load more than 10 entries on demand

---

## 14. Files to Create/Modify

### New Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/logai/ui/screens/log_preview.py` | Modal screen implementation | ~400 |
| `tests/unit/ui/test_log_preview.py` | Unit tests | ~150 |
| `tests/integration/ui/test_log_preview_integration.py` | Integration tests | ~100 |

### Modified Files

| File | Changes | Lines Changed |
|------|---------|---------------|
| `src/logai/ui/widgets/log_groups_sidebar.py` | Add `ClickableLogGroupItem` class | +60, ~3 modified |
| `src/logai/ui/screens/chat.py` | Add handler + context injection | +50 |
| `src/logai/ui/screens/__init__.py` | Export `LogPreviewScreen` | +2 |

### Total Impact

- **New code:** ~700 lines
- **Modified code:** ~55 lines
- **Test code:** ~250 lines

---

## 15. Open Questions for TPM

1. **Discovery UX**: Should we add a hint tooltip on first use? (e.g., "Double-click to preview logs")
   - **Recommendation:** Yes, but can be Phase 2 enhancement

2. **Time range**: Is 15 minutes appropriate, or should it be configurable?
   - **Recommendation:** 15 minutes is good for MVP; make configurable in future

3. **Telemetry**: Should we track preview feature usage?
   - **Recommendation:** Yes, add metrics for: modal opens, entries selected, time to selection

---

## Appendix A: ChatScreen Integration Code

Add this to `src/logai/ui/screens/chat.py`:

```python
# Add to imports
from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem
from logai.ui.screens.log_preview import LogPreviewScreen

# Add to ChatScreen class (after existing handlers)

@on(ClickableLogGroupItem.LogGroupPreviewRequested)
async def on_log_group_preview_requested(
    self,
    event: ClickableLogGroupItem.LogGroupPreviewRequested
) -> None:
    """
    Handle double-click preview request for a log group.

    Opens the log preview modal and processes any selected entries.

    Args:
        event: The preview request event with log group name
    """
    try:
        # Get datasource from log_group_manager (it has the reference)
        if not self.log_group_manager or not self.log_group_manager.datasource:
            self.notify(
                "Cannot preview logs: CloudWatch not configured",
                severity="error",
                timeout=5,
            )
            return

        datasource = self.log_group_manager.datasource

        # Open preview modal and await result
        result = await self.app.push_screen(
            LogPreviewScreen(
                log_group_name=event.log_group_name,
                datasource=datasource,
            )
        )

        # Process result if user selected entries
        if result and result.get("selected_entries"):
            await self._inject_log_entries_to_context(result)

    except Exception as e:
        logger.error(f"Failed to open log preview: {e}", exc_info=True)
        self.notify(
            f"Failed to open preview: {str(e)}",
            severity="error",
            timeout=5,
        )

async def _inject_log_entries_to_context(self, result: dict[str, Any]) -> None:
    """
    Inject selected log entries into agent context.

    Args:
        result: Dictionary with log_group_name and selected_entries
    """
    import json
    from datetime import datetime

    log_group = result["log_group_name"]
    entries = result["selected_entries"]
    count = len(entries)

    # Format entries for context
    formatted_entries = []
    for entry in entries:
        timestamp_ms = entry.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        formatted_entries.append({
            "timestamp": formatted_time,
            "message": entry.get("message", ""),
            "log_stream": entry.get("log_stream", ""),
        })

    context_message = f"""USER-SELECTED LOG ENTRIES for analysis:

Log Group: {log_group}
Entry Count: {count}

The user has specifically selected these log entries for your analysis:

```json
{json.dumps(formatted_entries, indent=2)}
```

Please analyze these logs and provide insights based on the user's next question."""

    # Inject via orchestrator
    self.orchestrator.inject_context_update(context_message)

    # Show system message in chat
    messages_container = self.query_one("#messages-container", VerticalScroll)
    system_msg = SystemMessage(
        f"Added {count} log entr{'y' if count == 1 else 'ies'} from {log_group} to context"
    )
    messages_container.mount(system_msg)
    messages_container.scroll_end(animate=False)
```

---

## Appendix B: Quick Reference Card for Jackie

### Key Files to Modify

1. `src/logai/ui/widgets/log_groups_sidebar.py`
   - Add `ClickableLogGroupItem` class (see Section 3.1)
   - Change line 160: `Label` → `ClickableLogGroupItem`

2. `src/logai/ui/screens/chat.py`
   - Add imports for new classes
   - Add `on_log_group_preview_requested()` handler (see Appendix A)
   - Add `_inject_log_entries_to_context()` method (see Appendix A)

3. Create `src/logai/ui/screens/log_preview.py` (see Section 3.2)

4. Update `src/logai/ui/screens/__init__.py`:
   ```python
   from .log_preview import LogPreviewScreen
   __all__ = [..., "LogPreviewScreen"]
   ```

### Key Patterns to Follow

- **Event handling**: Use `@on(Message)` decorator pattern
- **Async work**: Use `@work(exclusive=True)` for async operations
- **Screen dismissal**: `self.dismiss(result)` to return data
- **Context injection**: `orchestrator.inject_context_update(message)`
- **Styling**: Use Textual CSS in `DEFAULT_CSS` class variable

### Testing Commands

```bash
# Run unit tests
pytest tests/unit/ui/test_log_preview.py -v

# Run integration tests
pytest tests/integration/ui/test_log_preview_integration.py -v

# Run all related tests
pytest -k "log_preview" -v
```

---

**Document End**

*Created by Saanvi (Senior Software Architect) on February 18, 2026*
*For implementation by Jackie (Senior Software Engineer)*
