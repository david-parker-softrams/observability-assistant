# Tool Calls Sidebar - Comprehensive Design Document

**Author**: Sally (Senior Software Architect)  
**Date**: February 11, 2026  
**Status**: Ready for Implementation  
**Version**: 1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [UI/UX Design](#2-uiux-design)
3. [Data Model](#3-data-model)
4. [Command System](#4-command-system)
5. [Integration Points](#5-integration-points)
6. [Technical Architecture](#6-technical-architecture)
7. [User Experience Flow](#7-user-experience-flow)
8. [Edge Cases](#8-edge-cases)
9. [Configuration](#9-configuration)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Testing Strategy](#11-testing-strategy)
12. [Success Metrics](#12-success-metrics)
13. [Appendix: Diagrams & References](#13-appendix-diagrams--references)

---

## 1. Executive Summary

### Feature Overview

The Tool Calls Sidebar is a new UI component for LogAI's TUI that provides real-time visibility into the agent's tool execution. It displays a chronological list of tool calls made by the LLM orchestrator, including tool names, parameters, results, timing, and status.

### User Value Proposition

| Problem | Solution |
|---------|----------|
| Users can't see what tools the agent is calling | Sidebar shows each tool call in real-time |
| Users don't know if the agent is "stuck" or working | Live status updates show execution progress |
| Debugging agent behavior is difficult | Full visibility into parameters and results |
| Hard to verify the agent is doing the right thing | Users can sanity-check tool calls as they happen |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Right sidebar** (not left) | Preserves natural reading flow; chat remains primary focus |
| **Open by default** | Per user requirement; maximum transparency from the start |
| **25-30 column width** | Balances visibility with screen real estate |
| **Tree-based display** | Hierarchical view for tool details; collapsible for space |
| **Callback pattern** for updates | Efficient, event-driven; no polling overhead |
| **Maximum 20 tool calls** stored | Prevents memory bloat while keeping useful history |
| **Auto-scroll to latest** | Users always see the most recent activity |

---

## 2. UI/UX Design

### 2.1 Layout

The sidebar will be positioned on the right side of the screen, adjacent to the messages container.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Header: LogAI - CloudWatch Assistant                                           │
├──────────────────────────────────────────────────────┬──────────────────────────┤
│                                                      │  TOOL CALLS              │
│  Messages Container                                  │  ────────────────────    │
│  (chat history)                                      │                          │
│                                                      │  ▼ list_log_groups       │
│  ┌─────────────────────────────────────────────┐    │    Status: ✓ Success     │
│  │ [You] Show me errors in lambda logs         │    │    Duration: 245ms       │
│  └─────────────────────────────────────────────┘    │    Results: 12 groups    │
│                                                      │                          │
│  ┌─────────────────────────────────────────────┐    │  ▼ query_logs            │
│  │ [Assistant] I found 47 errors in the last   │    │    Status: ⏳ Running... │
│  │ hour. The most common pattern is...         │    │                          │
│  └─────────────────────────────────────────────┘    │                          │
│                                                      │                          │
│                                                      │                          │
├──────────────────────────────────────────────────────┤                          │
│  [Type your message...]                              │                          │
├──────────────────────────────────────────────────────┴──────────────────────────┤
│  Status: Ready | Cache: 5 hits (83%) | Model: claude-3.5-sonnet                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Dimensions

| Property | Value | Rationale |
|----------|-------|-----------|
| **Width** | 28 columns (fixed) | Fits tool names + key info; tested for common terminals |
| **Min Width** | 24 columns | Absolute minimum for readability |
| **Max Width** | 35 columns | Cap to prevent over-expansion |
| **Height** | `1fr` (flexible) | Fills available vertical space |
| **Responsive breakpoint** | 100 columns total | Hide sidebar automatically below this |

### 2.3 Content Display

Each tool call entry displays:

```
┌──────────────────────────────┐
│ ▼ list_log_groups            │  ← Tool name (expandable)
│   Status: ✓ Success          │  ← Execution status
│   Time: 14:32:05             │  ← Timestamp
│   Duration: 245ms            │  ← Execution time
│   ┌─ Args ─────────────────┐ │  ← Expandable sections
│   │ prefix: "/aws/lambda"  │ │
│   └────────────────────────┘ │
│   ┌─ Result ───────────────┐ │
│   │ count: 12              │ │
│   │ groups: ["/aws/la..."] │ │  ← Truncated if too long
│   └────────────────────────┘ │
└──────────────────────────────┘
```

### 2.4 Styling

```css
/* Color scheme aligned with existing app.tcss */
ToolCallsSidebar {
    background: $panel;
    border-left: solid $primary;
    padding: 0 1;
}

/* Tool call entry states */
.tool-entry-pending   { color: $text-muted; }      /* Waiting to execute */
.tool-entry-running   { color: $warning; }         /* Currently executing */
.tool-entry-success   { color: $success; }         /* Completed successfully */
.tool-entry-error     { color: $error; }           /* Failed with error */

/* Status icons */
/* ⏳ - Running (animated spinner optional) */
/* ✓  - Success */
/* ✗  - Error */
/* ◯  - Pending */
```

### 2.5 Default State

**Open by default** (per user requirement)

- Sidebar is visible when the application starts
- User can close it with `/tools` command if they want more space
- State persists within session (close it once, stays closed)

### 2.6 Empty State

When no tool calls have been made yet:

```
┌──────────────────────────────┐
│  TOOL CALLS                  │
│  ────────────────────────    │
│                              │
│    [dim italic]              │
│    No tool calls yet.        │
│    Ask a question to see     │
│    the agent's tools here.   │
│    [/dim italic]             │
│                              │
└──────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Tool Call Record Structure

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ToolCallStatus(Enum):
    """Status of a tool call execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolCallRecord:
    """
    Represents a single tool call for display in the sidebar.
    
    Attributes:
        id: Unique identifier (matches tool_call_id from LLM)
        name: Tool name (e.g., "list_log_groups", "query_logs")
        arguments: Parameters passed to the tool
        result: Return value from tool execution
        status: Current execution status
        started_at: When execution started
        completed_at: When execution completed (None if still running)
        error_message: Error details if status is ERROR
    """
    id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    status: ToolCallStatus = ToolCallStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_message: str | None = None
    
    @property
    def duration_ms(self) -> int | None:
        """Calculate execution duration in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if tool call has finished (success or error)."""
        return self.status in (ToolCallStatus.SUCCESS, ToolCallStatus.ERROR)
    
    def truncated_result(self, max_length: int = 100) -> str:
        """Get truncated result string for display."""
        if self.result is None:
            return "..."
        result_str = str(self.result)
        if len(result_str) > max_length:
            return result_str[:max_length - 3] + "..."
        return result_str
```

### 3.2 Tool Call History Manager

```python
from collections import deque
from typing import Callable


class ToolCallHistory:
    """
    Manages the history of tool calls for the sidebar.
    
    Uses a fixed-size deque to prevent unbounded memory growth.
    """
    
    MAX_ENTRIES = 20  # Maximum tool calls to keep in history
    
    def __init__(self):
        self._history: deque[ToolCallRecord] = deque(maxlen=self.MAX_ENTRIES)
        self._listeners: list[Callable[[ToolCallRecord], None]] = []
    
    def add(self, record: ToolCallRecord) -> None:
        """Add a new tool call record."""
        self._history.append(record)
        self._notify_listeners(record)
    
    def update(self, record_id: str, **updates) -> None:
        """Update an existing record by ID."""
        for record in self._history:
            if record.id == record_id:
                for key, value in updates.items():
                    setattr(record, key, value)
                self._notify_listeners(record)
                break
    
    def get_all(self) -> list[ToolCallRecord]:
        """Get all tool call records (most recent last)."""
        return list(self._history)
    
    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
    
    def register_listener(self, callback: Callable[[ToolCallRecord], None]) -> None:
        """Register a callback for tool call updates."""
        self._listeners.append(callback)
    
    def unregister_listener(self, callback: Callable[[ToolCallRecord], None]) -> None:
        """Unregister a callback."""
        self._listeners.remove(callback)
    
    def _notify_listeners(self, record: ToolCallRecord) -> None:
        """Notify all listeners of an update."""
        for listener in self._listeners:
            listener(record)
```

### 3.3 Information Captured

| Field | Source | Notes |
|-------|--------|-------|
| `id` | `tool_call["id"]` | From LLM response |
| `name` | `tool_call["function"]["name"]` | Tool function name |
| `arguments` | `tool_call["function"]["arguments"]` | Parsed JSON arguments |
| `result` | Return from `tool_registry.execute()` | Full result dict |
| `status` | Computed during execution | PENDING→RUNNING→SUCCESS/ERROR |
| `started_at` | Captured before execution | `datetime.now()` |
| `completed_at` | Captured after execution | `datetime.now()` |
| `error_message` | Exception message if failed | Error details |

### 3.4 Result Truncation Strategy

Large results (e.g., 1000 log entries) will be truncated for display:

| Result Size | Display Strategy |
|-------------|------------------|
| < 100 chars | Show full result |
| 100-500 chars | Show first 100 chars + "..." |
| > 500 chars | Show summary: `{count: N, ...}` |
| Lists > 5 items | Show first 3 + `...and N more` |

Example truncation:
```python
def format_result_for_display(result: dict, max_chars: int = 100) -> str:
    """Format a tool result for sidebar display."""
    if "events" in result and isinstance(result["events"], list):
        count = len(result["events"])
        return f"{{count: {count}, events: [...]}}"
    
    result_str = json.dumps(result)
    if len(result_str) > max_chars:
        return result_str[:max_chars - 3] + "..."
    return result_str
```

---

## 4. Command System

### 4.1 Command Name

**Primary command**: `/tools`

| Alternative considered | Rejected because |
|------------------------|------------------|
| `/toggle-tools` | Too verbose |
| `/sidebar` | Less specific |
| `/tool-sidebar` | Too long |

### 4.2 Command Behavior

```python
# In CommandHandler.handle_command():

elif cmd == "/tools":
    return await self._toggle_tools_sidebar()

async def _toggle_tools_sidebar(self) -> str:
    """Toggle the tools sidebar visibility."""
    # The actual toggle is done by posting a message to the ChatScreen
    # CommandHandler just returns a confirmation message
    # Note: This requires coordination with ChatScreen via app reference
    
    # For MVP, we'll use app.post_message() pattern
    from logai.ui.events import ToggleToolsSidebar
    self.app.post_message(ToggleToolsSidebar())
    
    # Return empty string - the visual change IS the feedback
    return ""
```

### 4.3 Help Text Update

```python
def _show_help(self) -> str:
    """Show help message with available commands."""
    return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/tools[/cyan] - Toggle tool calls sidebar
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)
...
"""
```

### 4.4 Keyboard Shortcut (Optional Enhancement)

For Phase 3, consider adding a keyboard shortcut:

```python
# In ChatScreen:
BINDINGS = [
    ("ctrl+t", "toggle_tools", "Toggle Tools"),
]

def action_toggle_tools(self) -> None:
    """Toggle the tools sidebar."""
    self._toggle_sidebar()
```

### 4.5 State Machine

```
                    ┌─────────────────┐
                    │                 │
                    │  SIDEBAR_OPEN   │◄─────── Initial State (default)
                    │                 │
                    └────────┬────────┘
                             │
                             │ /tools command or Ctrl+T
                             │
                             ▼
                    ┌─────────────────┐
                    │                 │
                    │  SIDEBAR_CLOSED │
                    │                 │
                    └────────┬────────┘
                             │
                             │ /tools command or Ctrl+T
                             │
                             └──────────► back to SIDEBAR_OPEN
```

---

## 5. Integration Points

### 5.1 Orchestrator Integration

The orchestrator needs to emit events when tool calls happen. We'll use a callback/observer pattern:

```python
# In LLMOrchestrator.__init__:
self.tool_call_listeners: list[Callable[[ToolCallRecord], None]] = []

def register_tool_listener(self, callback: Callable[[ToolCallRecord], None]) -> None:
    """Register a callback to receive tool call events."""
    self.tool_call_listeners.append(callback)

def _notify_tool_call(self, record: ToolCallRecord) -> None:
    """Notify all listeners of a tool call event."""
    for listener in self.tool_call_listeners:
        try:
            listener(record)
        except Exception as e:
            logger.warning(f"Tool listener error: {e}")
```

**Modified `_execute_tool_calls` method:**

```python
async def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Execute multiple tool calls with event notifications."""
    results = []
    
    for tool_call in tool_calls:
        tool_call_id = tool_call.get("id", "unknown")
        function_info = tool_call.get("function", {})
        function_name = function_info.get("name")
        function_args_str = function_info.get("arguments", "{}")
        
        # Parse arguments
        try:
            function_args = json.loads(function_args_str) if isinstance(function_args_str, str) else function_args_str
        except json.JSONDecodeError:
            function_args = {}
        
        # Create record and notify PENDING
        record = ToolCallRecord(
            id=tool_call_id,
            name=function_name,
            arguments=function_args,
            status=ToolCallStatus.PENDING,
        )
        self._notify_tool_call(record)
        
        # Update to RUNNING
        record.status = ToolCallStatus.RUNNING
        self._notify_tool_call(record)
        
        try:
            # Execute tool
            result = await self.tool_registry.execute(function_name, **function_args)
            
            # Update to SUCCESS
            record.status = ToolCallStatus.SUCCESS
            record.result = result
            record.completed_at = datetime.now()
            self._notify_tool_call(record)
            
            results.append({"tool_call_id": tool_call_id, "result": result})
            
        except Exception as e:
            # Update to ERROR
            record.status = ToolCallStatus.ERROR
            record.error_message = str(e)
            record.completed_at = datetime.now()
            self._notify_tool_call(record)
            
            results.append({
                "tool_call_id": tool_call_id,
                "result": {"success": False, "error": str(e)},
            })
    
    return results
```

### 5.2 TUI App Integration

**Data flow from orchestrator to sidebar:**

```
┌─────────────────┐      callback       ┌─────────────────┐
│                 │ ─────────────────► │                 │
│  Orchestrator   │                     │   ChatScreen    │
│                 │                     │                 │
└─────────────────┘                     └────────┬────────┘
                                                 │
                                                 │ update()
                                                 │
                                                 ▼
                                        ┌─────────────────┐
                                        │                 │
                                        │ ToolCallsSidebar│
                                        │                 │
                                        └─────────────────┘
```

**ChatScreen integration:**

```python
class ChatScreen(Screen[None]):
    """Main chat screen with tool calls sidebar."""
    
    def __init__(self, orchestrator: LLMOrchestrator, cache_manager: CacheManager) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.settings = get_settings()
        self.command_handler = CommandHandler(orchestrator, cache_manager, self.settings)
        
        # Sidebar state
        self._sidebar_visible = True  # Open by default per requirement
        self._tool_sidebar: ToolCallsSidebar | None = None
        
        # Register for tool call events
        self.orchestrator.register_tool_listener(self._on_tool_call)
    
    def _on_tool_call(self, record: ToolCallRecord) -> None:
        """Handle tool call events from orchestrator."""
        if self._tool_sidebar:
            # Post message to update sidebar (thread-safe)
            self.call_from_thread(self._tool_sidebar.update_tool_call, record)
```

### 5.3 Event System

We'll define custom Textual events for sidebar communication:

```python
# src/logai/ui/events.py

from textual.message import Message
from logai.ui.widgets.tool_calls_sidebar import ToolCallRecord


class ToggleToolsSidebar(Message):
    """Request to toggle the tools sidebar visibility."""
    pass


class ToolCallUpdated(Message):
    """A tool call record was updated."""
    
    def __init__(self, record: ToolCallRecord) -> None:
        super().__init__()
        self.record = record
```

### 5.4 State Management

| State | Location | Persistence |
|-------|----------|-------------|
| Sidebar visibility | `ChatScreen._sidebar_visible` | Session only (not persisted) |
| Tool call history | `ToolCallsSidebar._history` | Session only (cleared on exit) |
| Scroll position | `ToolCallsSidebar` internal | Session only |

**Future Enhancement** (Phase 4): Persist sidebar state to `~/.logai/ui_state.json`

---

## 6. Technical Architecture

### 6.1 New Component: `ToolCallsSidebar`

**File**: `src/logai/ui/widgets/tool_calls_sidebar.py`

```python
"""Tool calls sidebar widget for displaying agent tool execution."""

from datetime import datetime
from textual.reactive import reactive
from textual.widgets import Static, Tree
from textual.containers import VerticalScroll

from logai.core.orchestrator import ToolCallRecord, ToolCallStatus


class ToolCallsSidebar(Static):
    """
    Sidebar widget showing recent tool calls and their results.
    
    Displays a chronological list of tool calls made by the LLM orchestrator,
    with expandable details for each call.
    """
    
    DEFAULT_CSS = """
    ToolCallsSidebar {
        width: 28;
        min-width: 24;
        max-width: 35;
        height: 1fr;
        background: $panel;
        border-left: solid $primary;
        padding: 0 1;
    }
    
    ToolCallsSidebar .sidebar-title {
        text-style: bold;
        color: $text;
        padding: 1 0;
    }
    
    ToolCallsSidebar .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
        text-align: center;
    }
    
    ToolCallsSidebar Tree {
        width: 100%;
        height: 1fr;
        padding: 0;
    }
    
    /* Status colors */
    .status-pending { color: $text-muted; }
    .status-running { color: $warning; }
    .status-success { color: $success; }
    .status-error { color: $error; }
    """
    
    # Maximum number of tool calls to display
    MAX_DISPLAYED_CALLS = 20
    
    def __init__(self, **kwargs) -> None:
        """Initialize the tool calls sidebar."""
        super().__init__(**kwargs)
        self._history: list[ToolCallRecord] = []
        self._tree: Tree | None = None
    
    def compose(self) -> ComposeResult:
        """Compose the sidebar layout."""
        yield Static("TOOL CALLS", classes="sidebar-title")
        yield Static("No tool calls yet.\nAsk a question to see\nthe agent's tools here.", 
                     id="empty-state", classes="empty-state")
        yield Tree("", id="tool-tree")
    
    def on_mount(self) -> None:
        """Set up the sidebar when mounted."""
        self._tree = self.query_one("#tool-tree", Tree)
        self._tree.show_root = False
        self._update_empty_state()
    
    def update_tool_call(self, record: ToolCallRecord) -> None:
        """
        Update the sidebar with a tool call record.
        
        Args:
            record: Tool call record to display/update
        """
        # Find existing record or add new
        existing = next((r for r in self._history if r.id == record.id), None)
        
        if existing:
            # Update existing record
            idx = self._history.index(existing)
            self._history[idx] = record
        else:
            # Add new record (remove oldest if at capacity)
            if len(self._history) >= self.MAX_DISPLAYED_CALLS:
                self._history.pop(0)
            self._history.append(record)
        
        # Rebuild tree display
        self._rebuild_tree()
        self._update_empty_state()
    
    def _rebuild_tree(self) -> None:
        """Rebuild the tree display from current history."""
        if not self._tree:
            return
        
        self._tree.clear()
        
        for record in self._history:
            # Create node label with status icon
            icon = self._status_icon(record.status)
            label = f"{icon} {record.name}"
            
            node = self._tree.root.add(label, expand=False)
            
            # Add status
            status_class = f"status-{record.status.value}"
            node.add_leaf(f"Status: {record.status.value}")
            
            # Add timestamp
            time_str = record.started_at.strftime("%H:%M:%S")
            node.add_leaf(f"Time: {time_str}")
            
            # Add duration if complete
            if record.duration_ms is not None:
                node.add_leaf(f"Duration: {record.duration_ms}ms")
            
            # Add arguments summary
            if record.arguments:
                args_summary = self._format_args(record.arguments)
                node.add_leaf(f"Args: {args_summary}")
            
            # Add result or error
            if record.status == ToolCallStatus.SUCCESS and record.result:
                result_summary = self._format_result(record.result)
                node.add_leaf(f"Result: {result_summary}")
            elif record.status == ToolCallStatus.ERROR and record.error_message:
                node.add_leaf(f"Error: {record.error_message[:50]}...")
        
        # Auto-scroll to latest
        self._tree.scroll_end(animate=False)
    
    def _status_icon(self, status: ToolCallStatus) -> str:
        """Get icon for tool call status."""
        icons = {
            ToolCallStatus.PENDING: "◯",
            ToolCallStatus.RUNNING: "⏳",
            ToolCallStatus.SUCCESS: "✓",
            ToolCallStatus.ERROR: "✗",
        }
        return icons.get(status, "?")
    
    def _format_args(self, args: dict, max_len: int = 40) -> str:
        """Format arguments for display."""
        if not args:
            return "{}"
        
        # Show key names and truncated values
        parts = []
        for key, value in list(args.items())[:3]:  # Max 3 args shown
            val_str = str(value)[:15] + "..." if len(str(value)) > 15 else str(value)
            parts.append(f"{key}={val_str}")
        
        result = ", ".join(parts)
        if len(args) > 3:
            result += f", +{len(args) - 3} more"
        
        return result[:max_len]
    
    def _format_result(self, result: dict, max_len: int = 50) -> str:
        """Format result for display."""
        if not result:
            return "{}"
        
        # Special handling for common result patterns
        if "count" in result:
            return f"count: {result['count']}"
        if "events" in result and isinstance(result["events"], list):
            return f"{len(result['events'])} events"
        if "log_groups" in result and isinstance(result["log_groups"], list):
            return f"{len(result['log_groups'])} groups"
        if "success" in result:
            return "success" if result["success"] else "failed"
        
        # Fallback to truncated JSON
        import json
        result_str = json.dumps(result)
        if len(result_str) > max_len:
            return result_str[:max_len - 3] + "..."
        return result_str
    
    def _update_empty_state(self) -> None:
        """Show/hide empty state based on history."""
        empty_state = self.query_one("#empty-state", Static)
        if self._history:
            empty_state.display = False
        else:
            empty_state.display = True
    
    def clear(self) -> None:
        """Clear all tool call history."""
        self._history.clear()
        if self._tree:
            self._tree.clear()
        self._update_empty_state()
```

### 6.2 Layout Modification

**Modified `ChatScreen.compose()`:**

```python
from textual.containers import Horizontal

def compose(self) -> ComposeResult:
    """Compose the chat screen layout."""
    yield Header()
    
    # Main content area with optional sidebar
    with Horizontal(id="main-content"):
        yield VerticalScroll(id="messages-container")
        if self._sidebar_visible:
            yield ToolCallsSidebar(id="tools-sidebar")
    
    yield Container(ChatInput(), id="input-container")
    yield StatusBar(model=self.settings.current_llm_model)
```

**CSS updates for layout:**

```css
/* Add to app.tcss */

#main-content {
    height: 1fr;
    width: 100%;
}

#messages-container {
    width: 1fr;  /* Takes remaining space after sidebar */
}

#tools-sidebar {
    /* Sidebar styles defined in widget DEFAULT_CSS */
}
```

### 6.3 Toggle Implementation

```python
def _toggle_sidebar(self) -> None:
    """Toggle the tools sidebar visibility."""
    self._sidebar_visible = not self._sidebar_visible
    
    if self._sidebar_visible:
        # Mount sidebar
        main_content = self.query_one("#main-content", Horizontal)
        self._tool_sidebar = ToolCallsSidebar(id="tools-sidebar")
        main_content.mount(self._tool_sidebar)
        
        # Replay recent tool calls to populate sidebar
        for record in self._recent_tool_calls:
            self._tool_sidebar.update_tool_call(record)
    else:
        # Remove sidebar
        try:
            sidebar = self.query_one("#tools-sidebar")
            sidebar.remove()
            self._tool_sidebar = None
        except NoMatches:
            pass
```

### 6.4 Performance Considerations

| Concern | Mitigation |
|---------|------------|
| **Large tool results** | Truncate to 100 chars max in display |
| **Rapid tool calls** | Debounce tree rebuilds (50ms) |
| **Memory growth** | Fixed-size deque (20 entries max) |
| **UI blocking** | Use `call_from_thread` for cross-thread updates |
| **Tree rendering** | Only update changed nodes where possible |

---

## 7. User Experience Flow

### 7.1 Normal Flow: Tool Execution

```
User types: "Show me errors in lambda logs"
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│ Chat shows: [You] Show me errors in lambda logs    │
│ Sidebar shows: (pending tool call appears)         │
│   ◯ list_log_groups                                │
│     Status: pending                                │
└─────────────────────────────────────────────────────┘
                    │
                    ▼ (tool starts executing)
┌─────────────────────────────────────────────────────┐
│ Sidebar updates:                                   │
│   ⏳ list_log_groups                               │
│     Status: running                                │
│     Time: 14:32:05                                 │
└─────────────────────────────────────────────────────┘
                    │
                    ▼ (tool completes)
┌─────────────────────────────────────────────────────┐
│ Sidebar updates:                                   │
│   ✓ list_log_groups                                │
│     Status: success                                │
│     Time: 14:32:05                                 │
│     Duration: 245ms                                │
│     Result: 12 groups                              │
│                                                    │
│ Next tool starts:                                  │
│   ⏳ query_logs                                    │
│     Status: running                                │
└─────────────────────────────────────────────────────┘
                    │
                    ▼ (final response streams)
┌─────────────────────────────────────────────────────┐
│ Chat shows: [Assistant] I found 47 errors...       │
│ Sidebar shows all completed tools:                 │
│   ✓ list_log_groups - 245ms                        │
│   ✓ query_logs - 1.2s                              │
│   ✓ get_log_events - 890ms                         │
└─────────────────────────────────────────────────────┘
```

### 7.2 Error Flow

```
Tool execution fails:
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│ Sidebar shows:                                     │
│   ✗ query_logs                                     │
│     Status: error                                  │
│     Error: Log group not found                     │
│     Duration: 156ms                                │
└─────────────────────────────────────────────────────┘
```

### 7.3 Scrolling Behavior

- **Auto-scroll**: Sidebar always scrolls to show the latest tool call
- **User scroll**: If user manually scrolls up, disable auto-scroll until they scroll back to bottom
- **Expansion**: User can expand any tool call node to see full details

### 7.4 Interaction Capabilities

| Action | Available? | Notes |
|--------|------------|-------|
| Scroll through history | Yes | Mouse wheel or arrow keys |
| Expand/collapse details | Yes | Click or Enter on tree node |
| Copy tool result | Phase 4 | Future enhancement |
| Re-run tool | No | Not in scope |
| Filter by status | Phase 4 | Future enhancement |

---

## 8. Edge Cases

### 8.1 Very Long Tool Results

**Problem**: A `query_logs` call returns 500 log entries (megabytes of data).

**Solution**:
```python
def _format_result(self, result: dict, max_len: int = 50) -> str:
    """Format result with intelligent truncation."""
    # For events/logs, show count only
    if "events" in result:
        count = len(result["events"])
        return f"{count} events returned"
    
    # For other large results, truncate
    result_str = json.dumps(result)
    if len(result_str) > max_len:
        return result_str[:max_len - 3] + "..."
    return result_str
```

### 8.2 Many Rapid Tool Calls

**Problem**: Agent calls 10 tools in 2 seconds.

**Solution**:
- Fixed-size history (20 max) prevents overflow
- Debounce tree rebuilds with 50ms delay
- Batch updates when possible

```python
import asyncio

class ToolCallsSidebar(Static):
    _rebuild_task: asyncio.Task | None = None
    
    async def _debounced_rebuild(self) -> None:
        """Rebuild tree with debounce."""
        await asyncio.sleep(0.05)  # 50ms debounce
        self._rebuild_tree()
    
    def update_tool_call(self, record: ToolCallRecord) -> None:
        """Update with debounced rebuild."""
        # ... update history ...
        
        # Cancel pending rebuild
        if self._rebuild_task:
            self._rebuild_task.cancel()
        
        # Schedule new rebuild
        self._rebuild_task = asyncio.create_task(self._debounced_rebuild())
```

### 8.3 Tool Execution Errors

**Problem**: Tool throws an unexpected exception.

**Solution**: Display error message in sidebar with clear visual indicator (red ✗ icon).

```
✗ query_logs
  Status: error
  Error: AccessDenied: User does not have permission...
  Duration: 45ms
```

### 8.4 Small Terminal Windows

**Problem**: Terminal is less than 100 columns wide.

**Solution**: Auto-hide sidebar and show indicator in status bar.

```python
MIN_TERMINAL_WIDTH = 100

def on_resize(self, event: Resize) -> None:
    """Handle terminal resize events."""
    if event.size.width < self.MIN_TERMINAL_WIDTH:
        if self._sidebar_visible:
            self._auto_hide_sidebar()
            self._show_sidebar_hidden_notice()
    else:
        # Could auto-show, but better to let user control
        pass

def _show_sidebar_hidden_notice(self) -> None:
    """Show notice that sidebar was hidden due to small terminal."""
    # Update status bar or show system message
    status_bar = self.query_one(StatusBar)
    status_bar.set_status("Sidebar hidden (terminal too narrow)")
```

### 8.5 No Tool Calls Made

**Problem**: User only uses commands or has simple conversations.

**Solution**: Show friendly empty state message (already designed in 2.6).

### 8.6 Sidebar Toggle While Tools Running

**Problem**: User closes sidebar while tools are executing.

**Solution**: 
- Tool calls continue in background
- History is preserved
- When sidebar reopens, show complete history

```python
def _toggle_sidebar(self) -> None:
    """Toggle sidebar - preserves history across toggles."""
    self._sidebar_visible = not self._sidebar_visible
    
    if self._sidebar_visible and self._tool_sidebar is None:
        # Create sidebar and replay history
        self._tool_sidebar = ToolCallsSidebar(id="tools-sidebar")
        for record in self._recent_tool_calls:  # Preserved list
            self._tool_sidebar.update_tool_call(record)
```

---

## 9. Configuration

### 9.1 Settings to Control Sidebar

For MVP, minimal configuration. Future enhancements can add more.

```python
# In LogAISettings (settings.py)

# Tool sidebar settings (Phase 3)
tools_sidebar_width: int = 28           # Column width
tools_sidebar_enabled: bool = True      # Can disable entirely
tools_sidebar_open_default: bool = True # Open by default
tools_sidebar_max_history: int = 20     # Max tool calls to keep
```

### 9.2 Environment Variables (Future)

```bash
# Phase 4 - Optional environment overrides
LOGAI_SIDEBAR_WIDTH=30
LOGAI_SIDEBAR_ENABLED=true
LOGAI_SIDEBAR_DEFAULT_OPEN=true
```

### 9.3 Persistent State Across Sessions (Future)

**Phase 4 enhancement**: Remember sidebar state across app restarts.

```python
# ~/.logai/ui_state.json
{
    "sidebar_visible": false,  # User's last preference
    "sidebar_width": 28
}
```

---

## 10. Implementation Roadmap

### Phase 1: Basic Sidebar Structure (2 hours)

**Tasks:**
- [ ] Create `ToolCallsSidebar` widget class
- [ ] Add sidebar to `ChatScreen.compose()` layout
- [ ] Add CSS styling for sidebar
- [ ] Implement `/tools` command to toggle visibility
- [ ] Test basic show/hide functionality

**Deliverables:**
- Working sidebar that can be toggled
- Static content (no real tool data yet)

### Phase 2: Orchestrator Integration (2 hours)

**Tasks:**
- [ ] Add `ToolCallRecord` dataclass to orchestrator
- [ ] Add callback registration to `LLMOrchestrator`
- [ ] Modify `_execute_tool_calls` to emit events
- [ ] Register callback in `ChatScreen.on_mount()`
- [ ] Implement `update_tool_call()` in sidebar

**Deliverables:**
- Real tool calls appear in sidebar
- Status updates in real-time (pending → running → success/error)

### Phase 3: Polish & UX (2 hours)

**Tasks:**
- [ ] Add duration calculation and display
- [ ] Implement result/args truncation
- [ ] Add auto-scroll behavior
- [ ] Handle small terminal widths
- [ ] Add empty state display
- [ ] Add keyboard shortcut (Ctrl+T)

**Deliverables:**
- Polished user experience
- Responsive to terminal size
- Proper handling of edge cases

### Phase 4: Advanced Features (Optional, 2+ hours)

**Tasks:**
- [ ] Add copy-to-clipboard for tool results
- [ ] Add filtering by status (show only errors)
- [ ] Persist sidebar state across sessions
- [ ] Add search within tool history
- [ ] Add expandable full result view

**Deliverables:**
- Power-user features
- Full configurability

### Implementation Checklist for Jackie

```markdown
## Phase 1 Checklist
- [ ] Create file: `src/logai/ui/widgets/tool_calls_sidebar.py`
- [ ] Add to widgets `__init__.py`
- [ ] Modify `src/logai/ui/screens/chat.py`:
  - [ ] Import ToolCallsSidebar
  - [ ] Add `_sidebar_visible` state
  - [ ] Update `compose()` method
  - [ ] Add `_toggle_sidebar()` method
- [ ] Modify `src/logai/ui/commands.py`:
  - [ ] Add `/tools` command handler
  - [ ] Update help text
- [ ] Modify `src/logai/ui/styles/app.tcss`:
  - [ ] Add `#main-content` styles
  - [ ] Add sidebar-related styles

## Phase 2 Checklist
- [ ] Create file: `src/logai/ui/models/tool_call.py` (ToolCallRecord)
- [ ] Modify `src/logai/core/orchestrator.py`:
  - [ ] Add `tool_call_listeners` list
  - [ ] Add `register_tool_listener()` method
  - [ ] Modify `_execute_tool_calls()` to emit events
- [ ] Modify `src/logai/ui/screens/chat.py`:
  - [ ] Register listener in `on_mount()`
  - [ ] Add `_on_tool_call()` handler
  - [ ] Maintain `_recent_tool_calls` list

## Phase 3 Checklist
- [ ] Add duration display in sidebar
- [ ] Implement truncation helpers
- [ ] Add resize handler for small terminals
- [ ] Add Ctrl+T keyboard shortcut
- [ ] Test all edge cases
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

**File**: `tests/unit/ui/widgets/test_tool_calls_sidebar.py`

```python
import pytest
from datetime import datetime
from logai.ui.widgets.tool_calls_sidebar import ToolCallsSidebar
from logai.core.orchestrator import ToolCallRecord, ToolCallStatus


class TestToolCallsSidebar:
    """Unit tests for ToolCallsSidebar widget."""
    
    def test_sidebar_initialization(self):
        """Test sidebar initializes with empty state."""
        sidebar = ToolCallsSidebar()
        assert len(sidebar._history) == 0
    
    def test_add_tool_call(self):
        """Test adding a tool call record."""
        sidebar = ToolCallsSidebar()
        record = ToolCallRecord(
            id="call_123",
            name="list_log_groups",
            arguments={"prefix": "/aws/lambda"},
            status=ToolCallStatus.SUCCESS,
        )
        sidebar.update_tool_call(record)
        assert len(sidebar._history) == 1
        assert sidebar._history[0].name == "list_log_groups"
    
    def test_max_history_limit(self):
        """Test that history is capped at MAX_DISPLAYED_CALLS."""
        sidebar = ToolCallsSidebar()
        for i in range(25):
            record = ToolCallRecord(
                id=f"call_{i}",
                name=f"tool_{i}",
                arguments={},
                status=ToolCallStatus.SUCCESS,
            )
            sidebar.update_tool_call(record)
        
        assert len(sidebar._history) == sidebar.MAX_DISPLAYED_CALLS
        # Oldest should be removed
        assert sidebar._history[0].id == "call_5"  # 25 - 20 = 5
    
    def test_update_existing_record(self):
        """Test updating a record that already exists."""
        sidebar = ToolCallsSidebar()
        
        # Add pending record
        record = ToolCallRecord(
            id="call_123",
            name="query_logs",
            arguments={},
            status=ToolCallStatus.PENDING,
        )
        sidebar.update_tool_call(record)
        
        # Update to success
        record.status = ToolCallStatus.SUCCESS
        record.result = {"count": 42}
        sidebar.update_tool_call(record)
        
        assert len(sidebar._history) == 1
        assert sidebar._history[0].status == ToolCallStatus.SUCCESS
    
    def test_duration_calculation(self):
        """Test duration calculation for completed calls."""
        from datetime import timedelta
        
        record = ToolCallRecord(
            id="call_123",
            name="query_logs",
            arguments={},
            status=ToolCallStatus.SUCCESS,
            started_at=datetime(2026, 2, 11, 14, 30, 0),
            completed_at=datetime(2026, 2, 11, 14, 30, 0, 250000),  # +250ms
        )
        assert record.duration_ms == 250
    
    def test_format_args_truncation(self):
        """Test argument formatting with truncation."""
        sidebar = ToolCallsSidebar()
        args = {
            "log_group": "/aws/lambda/very-long-function-name-here",
            "filter_pattern": "ERROR",
            "start_time": "2026-02-11T00:00:00Z",
            "extra_param": "value",
        }
        formatted = sidebar._format_args(args)
        assert len(formatted) <= 40
        assert "+1 more" in formatted  # 4th arg truncated
    
    def test_format_result_events(self):
        """Test result formatting for events."""
        sidebar = ToolCallsSidebar()
        result = {"events": [{"msg": "test"}] * 100}
        formatted = sidebar._format_result(result)
        assert "100 events" in formatted
    
    def test_status_icons(self):
        """Test status icon mapping."""
        sidebar = ToolCallsSidebar()
        assert sidebar._status_icon(ToolCallStatus.PENDING) == "◯"
        assert sidebar._status_icon(ToolCallStatus.RUNNING) == "⏳"
        assert sidebar._status_icon(ToolCallStatus.SUCCESS) == "✓"
        assert sidebar._status_icon(ToolCallStatus.ERROR) == "✗"
```

### 11.2 Integration Tests

**File**: `tests/integration/ui/test_sidebar_integration.py`

```python
import pytest
from textual.pilot import Pilot
from logai.ui.app import LogAIApp


class TestSidebarIntegration:
    """Integration tests for sidebar with full app."""
    
    @pytest.mark.asyncio
    async def test_sidebar_visible_by_default(self):
        """Test that sidebar is visible when app starts."""
        app = LogAIApp()
        async with app.run_test() as pilot:
            sidebar = app.query_one("#tools-sidebar")
            assert sidebar is not None
            assert sidebar.display is True
    
    @pytest.mark.asyncio
    async def test_toggle_sidebar_command(self):
        """Test /tools command toggles sidebar."""
        app = LogAIApp()
        async with app.run_test() as pilot:
            # Sidebar should be visible initially
            sidebar = app.query_one("#tools-sidebar")
            assert sidebar.display is True
            
            # Type /tools command
            await pilot.type("/tools")
            await pilot.press("enter")
            
            # Sidebar should be hidden
            with pytest.raises(NoMatches):
                app.query_one("#tools-sidebar")
    
    @pytest.mark.asyncio
    async def test_tool_call_appears_in_sidebar(self):
        """Test that tool calls from orchestrator appear in sidebar."""
        # This requires mocking the orchestrator
        pass  # Implementation depends on test fixtures
```

### 11.3 Manual Testing Scenarios

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| **Basic visibility** | Launch app | Sidebar is visible on right side |
| **Toggle off** | Type `/tools` | Sidebar disappears, chat expands |
| **Toggle on** | Type `/tools` again | Sidebar reappears with history |
| **Tool execution** | Ask "What log groups exist?" | See `list_log_groups` appear in sidebar |
| **Status progression** | Watch during tool execution | See ◯ → ⏳ → ✓ progression |
| **Error handling** | Trigger invalid query | See ✗ status with error message |
| **Long result** | Query many logs | See truncated result summary |
| **Rapid calls** | Complex query with many tools | All tools appear, no UI lag |
| **Small terminal** | Resize to < 100 cols | Sidebar auto-hides gracefully |
| **Scroll history** | Make many queries | Can scroll through tool history |

### 11.4 Visual Regression (Optional)

If the project uses visual regression testing:

```python
# tests/visual/test_sidebar_appearance.py
async def test_sidebar_appearance(pilot: Pilot):
    """Capture sidebar appearance for visual regression."""
    await pilot.wait_for_scheduled_animations()
    await pilot.take_snapshot("sidebar_default_state")
```

---

## 12. Success Metrics

### 12.1 Feature Completion Criteria

| Criterion | Target | Verification |
|-----------|--------|--------------|
| Sidebar visible by default | 100% | Manual test |
| Toggle works correctly | 100% | Unit + manual test |
| Tool calls appear in real-time | < 100ms latency | Performance test |
| Status updates correctly | All 4 states | Unit test |
| Duration shown for completed calls | 100% | Unit test |
| History limited to 20 entries | Exactly 20 max | Unit test |
| Works on 100+ column terminals | No visual bugs | Manual test |
| Graceful on small terminals | Auto-hide or degrade | Manual test |

### 12.2 User Feedback to Gather

After release, gather feedback on:

1. **Usefulness**: "Did the sidebar help you understand what the agent was doing?"
2. **Visibility**: "Is the sidebar the right size? Too big? Too small?"
3. **Information**: "Was the information shown sufficient? Missing anything?"
4. **Performance**: "Did you notice any lag or slowdown?"
5. **Default state**: "Do you prefer sidebar open by default, or would you rather it start closed?"

### 12.3 Metrics to Track (If Telemetry Exists)

```python
# Potential metrics to add
sidebar_toggled_count     # How often users toggle
sidebar_time_visible_pct  # % of session time with sidebar open
tools_per_session         # Average tool calls per session
```

---

## 13. Appendix: Diagrams & References

### 13.1 ASCII Layout Mockup: Open State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LogAI - CloudWatch Assistant                                               [X] │
├──────────────────────────────────────────────────────┬──────────────────────────┤
│                                                      │ TOOL CALLS               │
│                                                      │ ────────────────────     │
│  ┌─────────────────────────────────────────────────┐│                          │
│  │ Welcome to LogAI! Ask me about your AWS        ││ ▼ list_log_groups        │
│  │ CloudWatch logs.                                ││   Status: ✓ success      │
│  │ Type /help for available commands.             ││   Time: 14:32:05         │
│  └─────────────────────────────────────────────────┘│   Duration: 245ms        │
│                                                      │   Args: prefix=/aws/la.. │
│  ┌─────────────────────────────────────────────────┐│   Result: 12 groups      │
│  │ [You] Show me errors in my lambda functions    ││                          │
│  └─────────────────────────────────────────────────┘│ ▼ query_logs             │
│                                                      │   Status: ✓ success      │
│  ┌─────────────────────────────────────────────────┐│   Time: 14:32:06         │
│  │ [Assistant] I found 47 errors in your lambda   ││   Duration: 1.2s         │
│  │ functions over the last hour. Here's a         ││   Args: filter=ERROR     │
│  │ breakdown by function:                          ││   Result: 47 events      │
│  │                                                 ││                          │
│  │ 1. payment-processor: 23 errors                ││ ▼ get_log_events         │
│  │    - Most common: TimeoutError (15)            ││   Status: ⏳ running...   │
│  │    - DynamoDB throttling (8)                   ││   Time: 14:32:08         │
│  │ 2. user-auth: 18 errors                        ││                          │
│  │    - JWT validation failures (12)              ││                          │
│  │    - Connection reset (6)                      ││                          │
│  │ ...                                             ││                          │
│  └─────────────────────────────────────────────────┘│                          │
│                                                      │                          │
├──────────────────────────────────────────────────────┤                          │
│  [Type your message... ]                             │                          │
├──────────────────────────────────────────────────────┴──────────────────────────┤
│  Status: Ready | Cache: 5 hits (83%) | Model: claude-3.5-sonnet                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 ASCII Layout Mockup: Closed State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  LogAI - CloudWatch Assistant                                               [X] │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │ Welcome to LogAI! Ask me about your AWS CloudWatch logs.                  │ │
│  │ Type /help for available commands.                                        │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │ [You] Show me errors in my lambda functions                               │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │ [Assistant] I found 47 errors in your lambda functions over the last     │ │
│  │ hour. Here's a breakdown by function:                                     │ │
│  │                                                                           │ │
│  │ 1. payment-processor: 23 errors                                          │ │
│  │    - Most common: TimeoutError (15)                                      │ │
│  │    - DynamoDB throttling (8)                                             │ │
│  │ ...                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  [Type your message... ]                                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Status: Ready | Cache: 5 hits (83%) | Model: claude-3.5-sonnet                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.3 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 USER INPUT                                      │
│                          "Show me lambda errors"                                │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ChatScreen                                         │
│                       (handles user input)                                      │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            LLMOrchestrator                                      │
│                                                                                 │
│  1. Send to LLM → LLM responds with tool_calls                                  │
│  2. For each tool_call:                                                         │
│     a. Create ToolCallRecord (PENDING)                                          │
│     b. Notify listeners ─────────────────────────────┐                          │
│     c. Update status (RUNNING)                       │                          │
│     d. Notify listeners ─────────────────────────────┤                          │
│     e. Execute tool                                  │                          │
│     f. Update status (SUCCESS/ERROR)                 │                          │
│     g. Notify listeners ─────────────────────────────┘                          │
│  3. Continue conversation loop                       │                          │
└──────────────────────────────────────────────────────┼──────────────────────────┘
                                                       │
                                                       │ callbacks
                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ChatScreen._on_tool_call()                           │
│                                                                                 │
│  1. Receive ToolCallRecord                                                      │
│  2. Store in _recent_tool_calls list                                            │
│  3. If sidebar visible:                                                         │
│     sidebar.update_tool_call(record)                                            │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ToolCallsSidebar                                      │
│                                                                                 │
│  1. Update internal _history                                                    │
│  2. Rebuild tree display                                                        │
│  3. Auto-scroll to latest                                                       │
│  4. Update empty state visibility                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.4 State Machine: Sidebar Visibility

```
                              ┌───────────────────────┐
                              │                       │
         ┌────────────────────┤   APP_STARTING        │
         │                    │                       │
         │                    └───────────────────────┘
         │
         │ on_mount()
         │ (sidebar_enabled = true by default)
         │
         ▼
┌───────────────────────┐                      ┌───────────────────────┐
│                       │                      │                       │
│   SIDEBAR_VISIBLE     │◄────────────────────►│   SIDEBAR_HIDDEN      │
│                       │   /tools command     │                       │
│   - Sidebar mounted   │   or Ctrl+T          │   - Sidebar removed   │
│   - Receiving updates │                      │   - History preserved │
│   - User can scroll   │                      │   - Updates buffered  │
│                       │                      │                       │
└──────────┬────────────┘                      └───────────────────────┘
           │
           │ terminal width < 100
           │
           ▼
┌───────────────────────┐
│                       │
│   SIDEBAR_AUTO_HIDDEN │
│                       │
│   - Hidden due to     │
│     small terminal    │
│   - Status bar shows  │
│     "Sidebar hidden"  │
│   - Restored when     │
│     terminal expands  │
│                       │
└───────────────────────┘
```

### 13.5 References

- **Hans' Investigation**: `george-scratch/TUI_ARCHITECTURE_INVESTIGATION.md`
- **Textual Documentation**: https://textual.textualize.io/
- **Textual Tree Widget**: https://textual.textualize.io/widgets/tree/
- **Current TUI Code**: `src/logai/ui/`
- **Orchestrator**: `src/logai/core/orchestrator.py`

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-11 | Sally | Initial design document |

---

**Document Status**: Ready for Implementation

**Next Steps**:
1. George (TPM) to review and approve
2. Jackie to begin Phase 1 implementation
3. Hans available for technical questions

**Estimated Total Implementation Time**: 6-8 hours (Phases 1-3)
