# Architecture Design: Log Groups Sidebar in TUI

**Author:** Saanvi (Senior Software Architect)
**Date:** February 12, 2026
**Version:** 1.0
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Component Design](#3-component-design)
4. [Layout Architecture](#4-layout-architecture)
5. [Data Flow](#5-data-flow)
6. [State Management](#6-state-management)
7. [Command Integration](#7-command-integration)
8. [Configuration](#8-configuration)
9. [Integration Points](#9-integration-points)
10. [Implementation Guide](#10-implementation-guide)
11. [Testing Strategy](#11-testing-strategy)
12. [Risks and Mitigations](#12-risks-and-mitigations)

---

## 1. Executive Summary

This document describes the architecture for adding a left sidebar to the LogAI TUI that displays all CloudWatch log groups. The design mirrors the existing right-side ToolCallsSidebar pattern while adding callback-based update support from the LogGroupManager.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Widget Pattern | Mirror ToolCallsSidebar design | Consistency, proven patterns, reduced cognitive load |
| Layout Strategy | 3-column Horizontal container | Flexible, supports 0-2 sidebars visible |
| Sidebar Width | 28 columns (same as tool sidebar) | Visual consistency, tested column width |
| Update Mechanism | Callback registration on LogGroupManager | Decoupled, same pattern as tool events |
| Widget Type | Static + VerticalScroll (not Tree) | Better performance for 1000+ items, simpler scrolling |
| Toggle Command | `/logs` (short, intuitive) | Follows `/tools` pattern, easy to type |
| Default Visibility | Configurable via settings | User control, respects preferences |

---

## 2. System Overview

### 2.1 High-Level Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   HEADER                                     │
├─────────────┬─────────────────────────────────────┬─────────────────────────┤
│             │                                     │                         │
│   LOG       │           CHAT                      │       TOOL              │
│   GROUPS    │           MESSAGES                  │       CALLS             │
│   SIDEBAR   │           (center, 1fr)             │       SIDEBAR           │
│   (28 col)  │                                     │       (28 col)          │
│             │                                     │                         │
│   /aws/...  │   User: Show me errors...           │   ◯ list_log_groups    │
│   /aws/...  │   Assistant: Let me check...        │   ✓ fetch_logs         │
│   /ecs/...  │                                     │                         │
│   ...       │                                     │                         │
│             │                                     │                         │
├─────────────┴─────────────────────────────────────┴─────────────────────────┤
│                              INPUT BOX                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                              STATUS BAR                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Relationships

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              LogAIApp                                      │
│  - orchestrator: LLMOrchestrator                                          │
│  - cache_manager: CacheManager                                            │
│  - log_group_manager: LogGroupManager                                     │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │ creates
                                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                             ChatScreen                                     │
│  - _log_groups_sidebar_visible: bool (from settings)                      │
│  - _tool_sidebar_visible: bool (existing)                                 │
│  - _log_groups_sidebar: LogGroupsSidebar | None                           │
│  - _tool_sidebar: ToolCallsSidebar | None                                 │
└─────────────────┬─────────────────────────────────┬───────────────────────┘
                  │                                 │
        creates   │                                 │ creates
                  ▼                                 ▼
┌─────────────────────────────┐   ┌─────────────────────────────────────────┐
│    LogGroupsSidebar (NEW)   │   │     ToolCallsSidebar (existing)         │
│    - Displays log groups    │   │     - Displays tool calls               │
│    - Subscribes to updates  │   │     - Subscribes to orchestrator        │
│    - Handles scrolling      │   │                                         │
└──────────────┬──────────────┘   └─────────────────────────────────────────┘
               │ subscribes to
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         LogGroupManager (modified)                         │
│  + _update_callbacks: list[Callable]                                      │
│  + register_update_callback(callback)                                     │
│  + unregister_update_callback(callback)                                   │
│  + _notify_update()                                                       │
│  + format_log_groups() -> list[str]  (NEW: simple list for sidebar)       │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Design

### 3.1 LogGroupsSidebar Widget (NEW)

**Location:** `src/logai/ui/widgets/log_groups_sidebar.py`

**Purpose:** Display a scrollable list of log group names in the left sidebar.

**Design Rationale:**
- Use `Static` container with `VerticalScroll` for content (not Tree widget)
- Tree widget adds unnecessary complexity for a simple list
- VerticalScroll handles 1000+ items efficiently with virtualization
- Simpler code, easier testing, better performance

```python
# src/logai/ui/widgets/log_groups_sidebar.py

"""Log groups sidebar widget for displaying available CloudWatch log groups."""

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Label

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
        **kwargs,
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
            # Truncate long names to fit sidebar width
            display_name = self._truncate_name(name)
            label = Label(display_name, classes="log-group-item")
            # Store full name as data attribute for future use (click-to-insert)
            label.data = {"full_name": name}
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

    def _truncate_name(self, name: str, max_width: int = 25) -> str:
        """
        Truncate log group name to fit sidebar width.

        Strategy: Keep prefix and suffix, truncate middle with ellipsis.
        Example: /aws/lambda/very-long-function-name -> /aws/lamb...tion-name

        Args:
            name: Full log group name
            max_width: Maximum display width

        Returns:
            Truncated name or original if short enough
        """
        if len(name) <= max_width:
            return name

        # Keep first 12 chars and last 10 chars with ellipsis in middle
        prefix_len = 12
        suffix_len = max_width - prefix_len - 3  # 3 for "..."
        return f"{name[:prefix_len]}...{name[-suffix_len:]}"

    def refresh_display(self) -> None:
        """
        Manually refresh the display.

        Called when sidebar is toggled back on to ensure current data.
        """
        self._populate_log_groups()
```

### 3.2 LogGroupManager Modifications

**Location:** `src/logai/core/log_group_manager.py`

**Changes Required:**
1. Add callback registration system for sidebar updates
2. Add `format_log_groups()` method for simple list output
3. Notify callbacks after successful refresh

```python
# Additions to LogGroupManager class

# New type alias (add near other type aliases)
UpdateCallback = Callable[[], None]  # No parameters - sidebar fetches data itself


class LogGroupManager:
    """... existing docstring ..."""

    def __init__(self, datasource: CloudWatchDataSource) -> None:
        """... existing init ..."""
        # ... existing initialization ...

        # NEW: Update callbacks for sidebar notifications
        self._update_callbacks: list[UpdateCallback] = []

    # === NEW METHODS ===

    def register_update_callback(self, callback: UpdateCallback) -> None:
        """
        Register a callback to be notified when log groups are updated.

        Args:
            callback: Function to call after successful refresh.
                     Takes no parameters - use get_log_group_names() to fetch data.
        """
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def unregister_update_callback(self, callback: UpdateCallback) -> None:
        """
        Unregister an update callback.

        Args:
            callback: Function to remove from notifications
        """
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _notify_update(self) -> None:
        """
        Notify all registered callbacks that log groups have been updated.

        Called after successful load_all() or refresh().
        """
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                # Log but don't fail - UI callback errors shouldn't break manager
                import logging
                logging.getLogger(__name__).warning(
                    f"Update callback error: {e}", exc_info=True
                )

    def format_log_groups(self) -> list[str]:
        """
        Get log groups formatted for sidebar display.

        Returns:
            Sorted list of log group names
        """
        return sorted(g.name for g in self._log_groups)

    # === MODIFICATIONS TO EXISTING METHODS ===

    async def load_all(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LogGroupManagerResult:
        """... existing implementation ..."""
        # ... existing code up to success return ...

        # ADD BEFORE RETURN: Notify update callbacks
        if result.success:
            self._notify_update()  # ADD THIS LINE

        return result  # existing return
```

**Integration Point in `load_all()`:**

```python
async def load_all(
    self,
    progress_callback: ProgressCallback | None = None,
) -> LogGroupManagerResult:
    """Load all log groups from CloudWatch with full pagination."""
    start_time = time.monotonic()

    self._state = LogGroupManagerState.LOADING
    self._last_error = None

    if progress_callback:
        progress_callback(0, "Starting log group discovery...")

    try:
        # ... existing fetch logic ...

        # Update state
        self._log_groups = all_groups
        self._state = LogGroupManagerState.READY
        self._last_refresh = datetime.now(timezone.utc)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        if progress_callback:
            progress_callback(len(all_groups), "Log group discovery complete")

        # === NEW: Notify sidebar callbacks ===
        self._notify_update()

        return LogGroupManagerResult(
            success=True,
            log_groups=all_groups,
            count=len(all_groups),
            duration_ms=duration_ms,
        )

    except Exception as e:
        # ... existing error handling ...
```

---

## 4. Layout Architecture

### 4.1 Three-Column Layout Strategy

The ChatScreen needs to support four layout states:
1. Both sidebars visible (3 columns)
2. Only left sidebar visible (2 columns)
3. Only right sidebar visible (2 columns)
4. No sidebars visible (1 column)

**Key Principle:** Use Textual's `display` property to show/hide sidebars without removing from DOM. This preserves state and is more performant than mount/unmount.

### 4.2 ChatScreen Layout Modifications

**Location:** `src/logai/ui/screens/chat.py`

```python
# Modified ChatScreen class

class ChatScreen(Screen[None]):
    """Main chat screen."""

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
    }

    #main-content {
        height: 1fr;
        width: 100%;
    }

    #messages-container {
        width: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }

    #input-container {
        height: auto;
        padding: 0 2 1 2;
    }

    /* NEW: Left sidebar positioning */
    #log-groups-sidebar {
        dock: left;
    }

    /* Right sidebar positioning (existing, make explicit) */
    #tools-sidebar {
        dock: right;
    }
    """

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        cache_manager: CacheManager,
        log_group_manager: "LogGroupManager | None" = None,
    ) -> None:
        """Initialize chat screen."""
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.log_group_manager = log_group_manager
        self.settings = get_settings()
        self.command_handler = CommandHandler(
            orchestrator, cache_manager, self.settings, self, log_group_manager
        )
        self._current_assistant_message: AssistantMessage | None = None
        self._current_loading_indicator: LoadingIndicator | None = None

        # Sidebar states - read defaults from settings
        self._tool_sidebar_visible = True  # Right sidebar (existing)
        self._log_groups_sidebar_visible = self.settings.log_groups_sidebar_visible  # NEW

        # Widget references
        self._tool_sidebar: ToolCallsSidebar | None = None
        self._log_groups_sidebar: LogGroupsSidebar | None = None  # NEW

        self._recent_tool_calls: list[ToolCallRecord] = []

    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        yield Header()

        # Main content area with sidebars
        with Horizontal(id="main-content"):
            # Left sidebar - log groups (NEW)
            self._log_groups_sidebar = LogGroupsSidebar(
                log_group_manager=self.log_group_manager,
                id="log-groups-sidebar",
            )
            # Set initial visibility
            self._log_groups_sidebar.display = self._log_groups_sidebar_visible
            yield self._log_groups_sidebar

            # Center - messages
            yield VerticalScroll(id="messages-container")

            # Right sidebar - tool calls (existing)
            self._tool_sidebar = ToolCallsSidebar(id="tools-sidebar")
            self._tool_sidebar.display = self._tool_sidebar_visible
            yield self._tool_sidebar

        yield Container(ChatInput(), id="input-container")
        yield StatusBar(model=self.settings.current_llm_model)

    # === NEW METHOD ===
    def toggle_log_groups_sidebar(self) -> None:
        """Toggle the log groups sidebar visibility."""
        self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible

        if self._log_groups_sidebar:
            self._log_groups_sidebar.display = self._log_groups_sidebar_visible

            # Refresh display when showing (in case data updated while hidden)
            if self._log_groups_sidebar_visible:
                self._log_groups_sidebar.refresh_display()

    # === EXISTING METHOD (keep as-is, just rename for clarity) ===
    def toggle_sidebar(self) -> None:
        """Toggle the tools sidebar visibility (existing behavior)."""
        self._tool_sidebar_visible = not self._tool_sidebar_visible

        if self._tool_sidebar_visible:
            # Show sidebar
            if self._tool_sidebar:
                self._tool_sidebar.display = True
                # Replay recent tool calls to populate sidebar
                for record in self._recent_tool_calls:
                    self._tool_sidebar.update_tool_call(record)
        else:
            # Hide sidebar
            if self._tool_sidebar:
                self._tool_sidebar.display = False
```

### 4.3 CSS Styling

**Location:** `src/logai/ui/styles/app.tcss`

Add the following styles:

```css
/* === LOG GROUPS SIDEBAR (NEW) === */

/* Left sidebar container */
#log-groups-sidebar {
    width: 28;
    min-width: 24;
    max-width: 35;
    height: 1fr;
    background: $panel;
    border-right: solid $primary;
}

/* Sidebar title */
#log-groups-sidebar .sidebar-title {
    text-style: bold;
    color: $text;
    padding: 1 1;
    background: $panel-darken-1;
}

/* Empty state message */
#log-groups-sidebar .empty-state {
    color: $text-muted;
    text-style: italic;
    padding: 2;
    text-align: center;
}

/* Scrollable area */
#log-groups-sidebar #log-groups-scroll {
    width: 100%;
    height: 1fr;
    padding: 0 1;
}

/* Individual log group item */
#log-groups-sidebar .log-group-item {
    width: 100%;
    height: auto;
    padding: 0;
    color: $text;
}

/* Hover state for log group items */
#log-groups-sidebar .log-group-item:hover {
    background: $surface;
    color: $text;
}
```

---

## 5. Data Flow

### 5.1 Startup Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STARTUP SEQUENCE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

1. CLI starts
   │
   ▼
2. LogGroupManager.load_all() executes
   │ - Fetches all log groups from AWS
   │ - Stores in manager._log_groups
   │
   ▼
3. LogAIApp created with log_group_manager reference
   │
   ▼
4. ChatScreen created
   │ - Reads settings.log_groups_sidebar_visible
   │ - Creates LogGroupsSidebar with manager reference
   │
   ▼
5. LogGroupsSidebar.on_mount()
   │ - Registers callback with manager
   │ - Calls _populate_log_groups()
   │
   ▼
6. _populate_log_groups()
   │ - Calls manager.get_log_group_names()
   │ - Creates Label widgets for each group
   │ - Updates title count: "LOG GROUPS (135)"
   │
   ▼
7. User sees sidebar with all log groups
```

### 5.2 Refresh Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           /REFRESH COMMAND FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

1. User types: /refresh
   │
   ▼
2. CommandHandler._refresh_log_groups()
   │
   ▼
3. LogGroupManager.refresh() / load_all()
   │ - Fetches fresh data from AWS
   │ - Updates internal state
   │
   ▼
4. load_all() calls _notify_update()
   │
   ▼
5. _notify_update() iterates callbacks
   │ - Calls sidebar._on_log_groups_updated()
   │
   ▼
6. _on_log_groups_updated()
   │ - Calls _populate_log_groups()
   │
   ▼
7. _populate_log_groups()
   │ - Clears existing items
   │ - Fetches new names from manager
   │ - Creates new Label widgets
   │ - Updates title: "LOG GROUPS (142)"  (if count changed)
   │
   ▼
8. User sees updated sidebar with new log groups
```

### 5.3 Toggle Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           /LOGS TOGGLE FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

1. User types: /logs
   │
   ▼
2. CommandHandler._toggle_log_groups_sidebar()
   │
   ▼
3. ChatScreen.toggle_log_groups_sidebar()
   │ - Flips _log_groups_sidebar_visible flag
   │ - Sets sidebar.display = <new state>
   │
   ▼
4. If showing (was hidden):
   │ - sidebar.refresh_display() called
   │ - Ensures data is current
   │
   ▼
5. Textual re-renders layout
   │ - Chat area expands/contracts
   │ - No widget recreation needed
```

---

## 6. State Management

### 6.1 State Locations

| State | Location | Persistence | Description |
|-------|----------|-------------|-------------|
| Log groups list | `LogGroupManager._log_groups` | Session | Actual data |
| Left sidebar visibility | `ChatScreen._log_groups_sidebar_visible` | Session | Toggle state |
| Right sidebar visibility | `ChatScreen._tool_sidebar_visible` | Session | Toggle state |
| Default visibility | `settings.log_groups_sidebar_visible` | Config file | User preference |

### 6.2 State Initialization Order

```python
# Order of state initialization:

1. Settings loaded from .env
   settings.log_groups_sidebar_visible = True  # from LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE

2. ChatScreen.__init__()
   self._log_groups_sidebar_visible = self.settings.log_groups_sidebar_visible

3. ChatScreen.compose()
   self._log_groups_sidebar.display = self._log_groups_sidebar_visible

4. User toggles with /logs
   self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible
   # Settings value is NOT changed - session override only
```

### 6.3 State Diagram

```
                    ┌─────────────────────────┐
                    │     .env / Settings     │
                    │  (persistent defaults)  │
                    └───────────┬─────────────┘
                                │
                                │ reads on startup
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ChatScreen                                 │
│                                                                 │
│   _log_groups_sidebar_visible: bool ◄──── initialized from     │
│                      │                     settings             │
│                      │                                          │
│                      │ /logs command                            │
│                      ▼                                          │
│              toggles state                                      │
│              (session only)                                     │
│                      │                                          │
│                      │ controls                                 │
│                      ▼                                          │
│   _log_groups_sidebar.display: bool                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Command Integration

### 7.1 New Command: `/logs`

**Location:** `src/logai/ui/commands.py`

```python
# Add to CommandHandler.handle_command()

async def handle_command(self, command: str) -> str:
    """Handle a special command."""
    command = command.strip()
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()

    if cmd == "/help":
        return self._show_help()
    elif cmd == "/clear":
        return self._clear_history()
    elif cmd == "/refresh":
        return await self._refresh_log_groups(parts[1] if len(parts) > 1 else "")
    elif cmd == "/logs":  # NEW
        return self._toggle_log_groups_sidebar()
    elif cmd == "/tools":
        return self._toggle_tools_sidebar()
    # ... rest of existing commands ...


# NEW METHOD
def _toggle_log_groups_sidebar(self) -> str:
    """Toggle the log groups sidebar visibility."""
    if self.chat_screen:
        self.chat_screen.toggle_log_groups_sidebar()
        if self.chat_screen._log_groups_sidebar_visible:
            return "[dim]Log groups sidebar shown.[/dim]"
        else:
            return "[dim]Log groups sidebar hidden.[/dim]"
    else:
        return "[dim]Sidebar toggle not available.[/dim]"
```

### 7.2 Updated Help Text

```python
def _show_help(self) -> str:
    """Show help message with available commands."""
    return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/refresh[/cyan] - Refresh the log groups list from AWS
[cyan]/logs[/cyan] - Toggle log groups sidebar (left)
[cyan]/tools[/cyan] - Toggle tool calls sidebar (right)
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)

[bold]Usage Tips:[/bold]
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
- Log groups are pre-loaded at startup - use /refresh to update
- Responses are streamed in real-time
- PII sanitization is enabled by default
"""
```

---

## 8. Configuration

### 8.1 New Settings

**Location:** `src/logai/config/settings.py`

```python
# Add to LogAISettings class:

class LogAISettings(BaseSettings):
    """Main configuration settings for LogAI application."""

    # ... existing settings ...

    # === UI Settings (NEW SECTION) ===
    log_groups_sidebar_visible: bool = Field(
        default=True,
        description="Show log groups sidebar by default at startup",
    )
```

### 8.2 Environment Variable

**Name:** `LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE`

**Type:** Boolean (`true`/`false`)

**Default:** `true`

### 8.3 .env.example Update

**Location:** `.env.example`

Add to the Application Settings section:

```bash
# === UI Settings ===
# Show log groups sidebar by default (true/false, default: true)
# The sidebar can always be toggled with /logs command
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true
```

---

## 9. Integration Points

### 9.1 File Modification Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/logai/ui/widgets/log_groups_sidebar.py` | **NEW** | LogGroupsSidebar widget class |
| `src/logai/core/log_group_manager.py` | Modify | Add callback system |
| `src/logai/ui/screens/chat.py` | Modify | Add left sidebar, toggle method |
| `src/logai/ui/commands.py` | Modify | Add `/logs` command |
| `src/logai/config/settings.py` | Modify | Add sidebar visibility setting |
| `src/logai/ui/styles/app.tcss` | Modify | Add left sidebar styles |
| `.env.example` | Modify | Document new setting |
| `src/logai/ui/widgets/__init__.py` | Modify | Export LogGroupsSidebar |

### 9.2 Import Dependencies

```python
# log_groups_sidebar.py imports:
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, Label
from logai.core.log_group_manager import LogGroupManager  # TYPE_CHECKING

# chat.py new imports:
from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar
```

### 9.3 Widget Export

**Location:** `src/logai/ui/widgets/__init__.py`

```python
from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar
from logai.ui.widgets.tool_sidebar import ToolCallsSidebar

__all__ = [
    "LogGroupsSidebar",
    "ToolCallsSidebar",
    # ... other widgets ...
]
```

---

## 10. Implementation Guide

### 10.1 Implementation Phases

#### Phase 1: LogGroupManager Updates
**Estimated Time:** 30 minutes

1. Add callback registration system to `LogGroupManager`
2. Add `format_log_groups()` method
3. Add `_notify_update()` call in `load_all()`
4. Test callback mechanism

#### Phase 2: LogGroupsSidebar Widget
**Estimated Time:** 1 hour

1. Create `src/logai/ui/widgets/log_groups_sidebar.py`
2. Implement widget with compose, mount, unmount
3. Implement truncation logic
4. Add CSS styles (inline DEFAULT_CSS)
5. Test widget in isolation

#### Phase 3: ChatScreen Integration
**Estimated Time:** 45 minutes

1. Update ChatScreen imports
2. Add sidebar state variables
3. Modify `compose()` for 3-column layout
4. Add `toggle_log_groups_sidebar()` method
5. Update CSS in `app.tcss`
6. Test layout with both sidebars

#### Phase 4: Command Integration
**Estimated Time:** 30 minutes

1. Add `/logs` command to `CommandHandler`
2. Update help text
3. Test toggle functionality

#### Phase 5: Configuration
**Estimated Time:** 15 minutes

1. Add setting to `LogAISettings`
2. Update `.env.example`
3. Test config loading

#### Phase 6: Testing & Polish
**Estimated Time:** 30 minutes

1. Manual testing all scenarios
2. Test with 1000+ log groups
3. Test narrow terminal widths
4. Fix any edge cases

### 10.2 Recommended Order

```
1. LogGroupManager modifications (foundation)
   ↓
2. LogGroupsSidebar widget (core component)
   ↓
3. Configuration settings (read before ChatScreen)
   ↓
4. ChatScreen integration (ties it together)
   ↓
5. Command handler (user interface)
   ↓
6. Documentation updates (.env.example)
```

### 10.3 Quick Start Checklist

```markdown
## Implementation Checklist

### Phase 1: LogGroupManager
- [ ] Add `_update_callbacks: list[Callable]` to __init__
- [ ] Add `register_update_callback(callback)` method
- [ ] Add `unregister_update_callback(callback)` method
- [ ] Add `_notify_update()` method
- [ ] Add `_notify_update()` call in `load_all()` success path
- [ ] Add `format_log_groups()` method

### Phase 2: LogGroupsSidebar
- [ ] Create `src/logai/ui/widgets/log_groups_sidebar.py`
- [ ] Implement LogGroupsSidebar class with DEFAULT_CSS
- [ ] Implement compose() with title, empty state, scroll container
- [ ] Implement on_mount() with callback registration
- [ ] Implement on_unmount() with callback cleanup
- [ ] Implement _populate_log_groups()
- [ ] Implement _truncate_name()
- [ ] Export from `widgets/__init__.py`

### Phase 3: ChatScreen
- [ ] Add LogGroupsSidebar import
- [ ] Add `_log_groups_sidebar_visible` state
- [ ] Add `_log_groups_sidebar` widget reference
- [ ] Update compose() with 3-column layout
- [ ] Add `toggle_log_groups_sidebar()` method
- [ ] Read initial visibility from settings

### Phase 4: Commands
- [ ] Add `/logs` case in handle_command()
- [ ] Add `_toggle_log_groups_sidebar()` method
- [ ] Update _show_help() with /logs command

### Phase 5: Configuration
- [ ] Add `log_groups_sidebar_visible: bool` to LogAISettings
- [ ] Update .env.example with new setting

### Phase 6: Styles
- [ ] Add left sidebar styles to app.tcss
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

**Location:** `tests/unit/test_log_groups_sidebar.py`

```python
"""Unit tests for LogGroupsSidebar widget."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar


class TestLogGroupsSidebar:
    """Test cases for LogGroupsSidebar."""

    def test_truncate_name_short_name(self):
        """Test that short names are not truncated."""
        sidebar = LogGroupsSidebar()
        result = sidebar._truncate_name("/aws/lambda/short", max_width=25)
        assert result == "/aws/lambda/short"

    def test_truncate_name_long_name(self):
        """Test that long names are truncated with ellipsis."""
        sidebar = LogGroupsSidebar()
        long_name = "/aws/lambda/very-long-function-name-here"
        result = sidebar._truncate_name(long_name, max_width=25)
        assert len(result) <= 25
        assert "..." in result
        assert result.startswith("/aws/lamb")

    def test_get_count_no_manager(self):
        """Test count returns 0 when no manager."""
        sidebar = LogGroupsSidebar()
        assert sidebar._get_count() == 0

    def test_get_count_with_manager(self):
        """Test count returns manager count."""
        mock_manager = MagicMock()
        mock_manager.count = 135
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        assert sidebar._get_count() == 135

    def test_get_log_group_names_sorted(self):
        """Test log group names are returned sorted."""
        mock_manager = MagicMock()
        mock_manager.get_log_group_names.return_value = [
            "/ecs/app",
            "/aws/lambda/func",
            "/aws/apigateway/api",
        ]
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar._get_log_group_names()
        assert names == [
            "/aws/apigateway/api",
            "/aws/lambda/func",
            "/ecs/app",
        ]


class TestLogGroupManagerCallbacks:
    """Test callback system in LogGroupManager."""

    def test_register_callback(self):
        """Test callback registration."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        manager.register_update_callback(callback)

        assert callback in manager._update_callbacks

    def test_unregister_callback(self):
        """Test callback unregistration."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        manager.register_update_callback(callback)
        manager.unregister_update_callback(callback)

        assert callback not in manager._update_callbacks

    def test_notify_update_calls_callbacks(self):
        """Test _notify_update calls all registered callbacks."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback1 = MagicMock()
        callback2 = MagicMock()
        manager.register_update_callback(callback1)
        manager.register_update_callback(callback2)

        manager._notify_update()

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_notify_update_handles_callback_error(self):
        """Test that callback errors don't break notification chain."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback1 = MagicMock(side_effect=Exception("Callback error"))
        callback2 = MagicMock()
        manager.register_update_callback(callback1)
        manager.register_update_callback(callback2)

        # Should not raise
        manager._notify_update()

        # Second callback should still be called
        callback2.assert_called_once()
```

### 11.2 Integration Tests

```python
"""Integration tests for log groups sidebar feature."""

import pytest
from unittest.mock import MagicMock, patch

from logai.ui.commands import CommandHandler


class TestLogsCommand:
    """Test /logs command integration."""

    def test_toggle_shows_sidebar(self):
        """Test /logs shows sidebar when hidden."""
        mock_screen = MagicMock()
        mock_screen._log_groups_sidebar_visible = False

        handler = CommandHandler(
            orchestrator=MagicMock(),
            cache_manager=MagicMock(),
            settings=MagicMock(),
            chat_screen=mock_screen,
        )

        # Simulate toggle
        mock_screen._log_groups_sidebar_visible = True
        result = handler._toggle_log_groups_sidebar()

        assert "shown" in result.lower()
        mock_screen.toggle_log_groups_sidebar.assert_called_once()

    def test_toggle_hides_sidebar(self):
        """Test /logs hides sidebar when visible."""
        mock_screen = MagicMock()
        mock_screen._log_groups_sidebar_visible = True

        handler = CommandHandler(
            orchestrator=MagicMock(),
            cache_manager=MagicMock(),
            settings=MagicMock(),
            chat_screen=mock_screen,
        )

        # Simulate toggle
        mock_screen._log_groups_sidebar_visible = False
        result = handler._toggle_log_groups_sidebar()

        assert "hidden" in result.lower()
```

### 11.3 Manual Testing Scenarios

```markdown
## Manual Test Checklist

### Startup Tests
- [ ] App starts with sidebar visible (default config)
- [ ] Sidebar shows correct count in title
- [ ] All log groups are displayed
- [ ] Log groups are sorted alphabetically
- [ ] Long names are truncated properly

### Toggle Tests
- [ ] /logs hides the sidebar
- [ ] /logs shows the sidebar again
- [ ] Chat area expands when sidebar hidden
- [ ] Chat area contracts when sidebar shown
- [ ] Both sidebars can be visible simultaneously
- [ ] Both sidebars can be hidden simultaneously

### Refresh Tests
- [ ] /refresh updates sidebar automatically
- [ ] Count in title updates after refresh
- [ ] Scroll position is reasonable after refresh
- [ ] No errors during refresh with sidebar open
- [ ] No errors during refresh with sidebar closed

### Configuration Tests
- [ ] LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=false hides on startup
- [ ] /logs can still show sidebar when config is false
- [ ] LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true shows on startup

### Performance Tests
- [ ] 100 log groups render quickly
- [ ] 500 log groups render acceptably
- [ ] 1000+ log groups don't freeze UI
- [ ] Scrolling is smooth with many items
- [ ] Toggle is instant (no delay)

### Edge Cases
- [ ] Empty log groups list shows empty state
- [ ] Very narrow terminal doesn't crash
- [ ] Rapid toggle doesn't cause issues
- [ ] Multiple /refresh commands in succession
```

---

## 12. Risks and Mitigations

### 12.1 Performance Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 1000+ log groups slow to render | Medium | Medium | Use Label widgets instead of Tree; consider virtualization if needed |
| Memory usage with many items | Low | Low | Label widgets are lightweight; monitor in testing |
| Scroll performance | Medium | Low | Textual's VerticalScroll handles this well |

### 12.2 Complexity Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Layout bugs with 3 columns | Medium | Medium | Extensive testing of all layout combinations |
| Callback timing issues | Low | Low | Simple callback pattern; test with various timings |
| State synchronization | Low | Low | Single source of truth in ChatScreen |

### 12.3 UX Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Truncated names lose context | Low | Medium | Smart truncation keeping prefix and suffix |
| Narrow terminals cramped | Medium | Medium | Minimum width constraints; graceful degradation |
| Users confused by two sidebars | Low | Low | Clear naming; separate toggle commands |

### 12.4 Future Considerations

**Out of Scope but Worth Noting:**

1. **Click to Insert:** Future feature where clicking a log group inserts its name into chat. Widget stores `full_name` in data attribute for this purpose.

2. **Search/Filter:** Add filter input at top of sidebar. Would need to modify `_populate_log_groups()` to accept filter parameter.

3. **Grouping by Prefix:** Could add collapsible sections for `/aws/lambda/`, `/ecs/`, etc. Would need Tree widget instead of flat list.

4. **Keyboard Navigation:** Arrow keys to select items in sidebar. Would need to track selection state and handle key events.

5. **Resize Capability:** Drag border to resize sidebar width. Would need mouse event handling and dynamic width.

---

## Summary

This architecture provides a clean, maintainable design for the log groups sidebar that:

1. **Mirrors Existing Patterns:** Uses the same widget structure and toggle mechanism as ToolCallsSidebar
2. **Integrates Cleanly:** Adds callback system to existing LogGroupManager without breaking changes
3. **Performs Well:** Uses efficient Label widgets suitable for 1000+ items
4. **Is Configurable:** Respects user preferences via environment variable
5. **Is Extensible:** Designed with future enhancements (click-to-insert, filtering) in mind

The implementation can be completed in approximately 3 hours by following the phased approach outlined above.

---

**Document Status:** Ready for Implementation
**Assigned To:** Jackie (Implementation)
**Review:** George (TPM)
