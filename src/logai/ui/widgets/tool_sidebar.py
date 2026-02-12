"""Tool calls sidebar widget for displaying agent tool execution."""

import json
import logging
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from logai.core.orchestrator import ToolCallRecord, ToolCallStatus

logger = logging.getLogger(__name__)


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

    ToolCallsSidebar Tree > TreeNode {
        overflow: auto;
    }

    /* Status colors */
    .status-pending { color: $text-muted; }
    .status-running { color: $warning; }
    .status-success { color: $success; }
    .status-error { color: $error; }
    """

    # Maximum number of tool calls to display
    MAX_DISPLAYED_CALLS = 20

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the tool calls sidebar."""
        super().__init__(**kwargs)
        self._history: list[ToolCallRecord] = []
        self._tree: Tree[Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose the sidebar layout."""
        yield Static("TOOL CALLS", classes="sidebar-title")
        yield Static(
            "No tool calls yet.\nAsk a question to see\nthe agent's tools here.",
            id="empty-state",
            classes="empty-state",
        )
        yield Tree("Tool Calls", id="tool-tree")

    def on_mount(self) -> None:
        """Set up the sidebar when mounted."""
        self._tree = self.query_one("#tool-tree", Tree[Any])
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
            status_class = f"status-{record.status}"
            node.add_leaf(f"Status: {record.status}")

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
                self._add_result_node(node, record.result)
            elif record.status == ToolCallStatus.ERROR and record.error_message:
                # Display full error message without truncation
                node.add_leaf(f"Error: {record.error_message}")

        # Auto-scroll to latest
        self._tree.scroll_end(animate=False)

    def _status_icon(self, status: str) -> str:
        """Get icon for tool call status."""
        icons = {
            ToolCallStatus.PENDING: "◯",
            ToolCallStatus.RUNNING: "⏳",
            ToolCallStatus.SUCCESS: "✓",
            ToolCallStatus.ERROR: "✗",
        }
        return icons.get(status, "?")

    def _format_args(self, args: dict[str, Any], max_len: int = 40) -> str:
        """Format arguments for display."""
        if not args:
            return "{}"

        # Show key names and full values without truncation
        parts = []
        for key, value in list(args.items())[:3]:  # Max 3 args shown
            val_str = str(value)
            parts.append(f"{key}={val_str}")

        result = ", ".join(parts)
        if len(args) > 3:
            result += f", +{len(args) - 3} more"

        return result

    def _add_result_node(self, parent_node: TreeNode[Any], result: dict[str, Any]) -> None:
        """
        Add result to the tree with expandable sections for large datasets.

        Args:
            parent_node: Parent tree node to add result under
            result: Result dictionary to format and display
        """
        if not result:
            parent_node.add_leaf("Result: {}")
            return

        # Handle log groups - show actual log group names with expansion
        if "log_groups" in result and isinstance(result["log_groups"], list):
            self._add_log_groups_node(parent_node, result["log_groups"])
            return

        # Handle log events - show actual log messages with expansion
        if "events" in result and isinstance(result["events"], list):
            self._add_log_events_node(parent_node, result["events"])
            return

        # Handle success/failure status
        if "success" in result:
            parent_node.add_leaf(f"Result: {'success' if result['success'] else 'failed'}")
            return

        # Fallback to full JSON for other result types
        try:
            result_str = json.dumps(result, indent=2)
            result_lines = result_str.split("\n")
            # Display all lines without truncation
            parent_node.add_leaf(f"Result: {result_lines[0]}")
            for line in result_lines[1:]:
                if line.strip():
                    parent_node.add_leaf(f"  {line}")
        except Exception:
            # If JSON serialization fails, convert to string and show full content
            result_str = str(result)
            parent_node.add_leaf(f"Result: {result_str}")

    def _add_log_groups_node(
        self, parent_node: TreeNode[Any], log_groups: list[dict[str, Any]]
    ) -> None:
        """
        Add log groups with expandable list for large datasets.

        Args:
            parent_node: Parent tree node
            log_groups: List of log group dictionaries
        """
        if not log_groups:
            parent_node.add_leaf("Result: No log groups found")
            return

        # Create result summary node
        result_node = parent_node.add(f"Result: Found {len(log_groups)} groups")

        # Show first 10 log group names with full names
        preview_count = min(10, len(log_groups))
        for i in range(preview_count):
            group = log_groups[i]
            # Extract just the name field and display full name
            name = group.get("name", str(group))
            result_node.add_leaf(f"  • {name}")

        # Add expandable node for remaining items
        if len(log_groups) > preview_count:
            remaining = len(log_groups) - preview_count
            more_node = result_node.add(
                f"▶ Show {remaining} more",
                expand=False,  # Collapsed by default
            )
            for i in range(preview_count, len(log_groups)):
                group = log_groups[i]
                name = group.get("name", str(group))
                more_node.add_leaf(f"  • {name}")

    def _add_log_events_node(
        self, parent_node: TreeNode[Any], events: list[dict[str, Any]]
    ) -> None:
        """
        Add log events with expandable list for large datasets.

        Args:
            parent_node: Parent tree node
            events: List of log event dictionaries
        """
        if not events:
            parent_node.add_leaf("Result: No events found")
            return

        # Create result summary node
        result_node = parent_node.add(f"Result: Found {len(events)} events")

        # Show first 5 log events (they can be lengthy)
        preview_count = min(5, len(events))
        for i in range(preview_count):
            event = events[i]
            self._add_single_event(result_node, event)

        # Add expandable node for remaining events
        if len(events) > preview_count:
            remaining = len(events) - preview_count
            more_node = result_node.add(
                f"▶ Show {remaining} more",
                expand=False,  # Collapsed by default
            )
            for i in range(preview_count, len(events)):
                event = events[i]
                self._add_single_event(more_node, event)

    def _add_single_event(self, parent_node: TreeNode[Any], event: dict[str, Any]) -> None:
        """
        Add a single log event to the tree.

        Args:
            parent_node: Parent tree node
            event: Log event dictionary
        """
        timestamp = event.get("timestamp", 0)
        message = event.get("message", "")

        # Format timestamp nicely
        if timestamp:
            from datetime import datetime

            dt = datetime.fromtimestamp(timestamp / 1000)
            time_str = dt.strftime("%H:%M:%S")
        else:
            time_str = "??:??:??"

        # Display full message without truncation
        message_clean = message.strip().replace("\n", " ")

        event_node = parent_node.add(f"[{time_str}]")
        event_node.add_leaf(f"  {message_clean}")

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
