"""Context viewer modal screen for displaying agent context."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, RichLog, Static

logger = logging.getLogger(__name__)


@dataclass
class ContextMetadata:
    """Metadata about the current context."""

    total_chars: int
    total_tokens: int
    entry_count: int | None  # None if unable to parse
    log_group: str | None  # None if no log group found
    last_updated: datetime
    context_type: str  # "user-selected-logs", "cache-guidance", "empty", "unknown"


class ContextViewerScreen(ModalScreen[None]):
    """
    Modal screen for viewing the current agent context.

    Displays two collapsible sections:
    - Staged Context: Logs waiting to be injected (_pending_context_injection)
    - Agent Memory: Full conversation history the agent has in memory
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    DEFAULT_CSS = """
    ContextViewerScreen {
        align: center middle;
    }

    #context-container {
        width: 90%;
        height: 85%;
        max-width: 120;
        background: $panel;
        border: thick $primary;
        padding: 0;
        layout: vertical;
    }

    #context-header {
        height: 3;
        background: $primary;
        color: $text;
        padding: 1 2;
        text-style: bold;
        width: 100%;
    }

    #sections-container {
        layout: horizontal;
        overflow: hidden;
        height: 1fr;
        background: $panel;
    }

    /* Collapsible section styling */
    Collapsible {
        width: 1fr;
        height: 1fr;
        margin: 0 0 1 0;
        border: solid $surface-darken-2;
    }

    Collapsible > CollapsibleTitle {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }

    Collapsible > Contents {
        padding: 0;
        background: $panel;
        height: 1fr;
        max-height: 40;
    }

    /* Scroll containers for independent scrolling */
    #staged-scroll, #memory-scroll {
        width: 1fr;
        height: 1fr;
        scrollbar-gutter: stable;
    }

    /* RichLog content widgets */
    #staged-content, #memory-content {
        width: 100%;
        min-height: 20;
        height: auto;
        border: none;
        background: $panel;
        scrollbar-gutter: stable;
    }

    .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
    }

    /* Section copy buttons */
    .section-copy-btn {
        dock: right;
        width: auto;
        margin: 0 1 0 0;
        height: 1;
        min-width: 8;
        background: $accent;
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

    #copy-all-btn {
        background: $accent;
    }
    """

    def __init__(
        self,
        staged_context: str | None,
        conversation_history: list[dict[str, Any]],
        metadata: ContextMetadata,
        **kwargs: Any,
    ) -> None:
        """
        Initialize context viewer screen.

        Args:
            staged_context: Pending context injection text (None if empty)
            conversation_history: List of conversation messages
            metadata: Parsed metadata about staged context
            **kwargs: Additional arguments for ModalScreen
        """
        super().__init__(**kwargs)
        self.staged_context = staged_context or ""
        self.conversation_history = conversation_history
        self.metadata = metadata

        # Cached formatted content for copy operations
        self._formatted_staged: str | None = None
        self._formatted_history: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the context viewer layout with two sections."""
        with Container(id="context-container"):
            # Header
            yield Static("Context Viewer", id="context-header")

            # Scrollable sections container
            with Horizontal(id="sections-container"):
                # Staged Context Section
                staged_count = self._get_staged_item_count()
                with Collapsible(
                    title=f"Staged Context ({staged_count} items)",
                    collapsed=False,
                    id="staged-section",
                ):
                    with VerticalScroll(id="staged-scroll"):
                        yield RichLog(
                            id="staged-content",
                            wrap=True,
                            highlight=False,
                            markup=True,
                            auto_scroll=False,
                        )

                # Agent Memory Section
                memory_count = len(self.conversation_history)
                with Collapsible(
                    title=f"Agent Memory (Full Context: {memory_count} messages)",
                    collapsed=False,
                    id="memory-section",
                ):
                    with VerticalScroll(id="memory-scroll"):
                        yield RichLog(
                            id="memory-content",
                            wrap=True,
                            highlight=False,
                            markup=True,
                            auto_scroll=False,
                        )

            # Action buttons
            with Horizontal(id="action-buttons"):
                yield Button("Copy All", id="copy-all-btn", variant="primary")
                yield Button("Close", id="close-btn", variant="default")

    async def on_mount(self) -> None:
        """Populate sections with content asynchronously."""
        try:
            # Populate Staged Context section
            staged_log = self.query_one("#staged-content", RichLog)
            formatted_staged = self._format_staged_context()
            staged_log.write(formatted_staged)
            staged_log.refresh()
            self._formatted_staged = formatted_staged

            # Populate Agent Memory section
            memory_log = self.query_one("#memory-content", RichLog)
            formatted_history = self._format_conversation_history()
            memory_log.write(formatted_history)
            memory_log.refresh()
            self._formatted_history = formatted_history

            # Refresh the entire screen to ensure rendering
            self.refresh()

            logger.debug(
                f"Context viewer loaded: {len(self.staged_context)} staged chars, "
                f"{len(self.conversation_history)} history messages"
            )
        except Exception as e:
            logger.error(f"Failed to populate context viewer: {e}", exc_info=True)

    def _get_staged_item_count(self) -> int:
        """Get count of items in staged context."""
        if not self.staged_context:
            return 0
        # Use metadata if available
        if self.metadata.entry_count is not None:
            return self.metadata.entry_count
        # Fallback: assume at least 1 if there's content
        return 1 if self.staged_context else 0

    def _format_staged_context(self) -> str:
        """Format staged context for display."""
        if not self.staged_context:
            return self._empty_staged_message()

        # Parse metadata for header
        header_lines = []
        if self.metadata.entry_count:
            header_lines.append(f"[bold cyan]Log Entries:[/bold cyan] {self.metadata.entry_count}")
        if self.metadata.log_group:
            header_lines.append(f"[bold cyan]Log Group:[/bold cyan] {self.metadata.log_group}")
        if self.metadata.total_chars:
            header_lines.append(
                f"[bold cyan]Size:[/bold cyan] {self.metadata.total_chars:,} chars "
                f"(~{self.metadata.total_tokens:,} tokens)"
            )

        header = "\n".join(header_lines) if header_lines else ""
        separator = "\n" + "─" * 50 + "\n\n" if header else ""

        return header + separator + self.staged_context

    def _empty_staged_message(self) -> str:
        """Return empty state message for staged context."""
        return (
            "[dim italic]No logs staged for injection.[/dim italic]\n\n"
            "Logs are staged when you:\n"
            "• Select entries from the log preview (double-click a log group)\n"
            "• Receive cache guidance from large tool results\n\n"
            "Staged logs will be consumed on your next message to the agent."
        )

    def _format_conversation_history(self) -> str:
        """Format full conversation history for display."""
        if not self.conversation_history:
            return self._empty_memory_message()

        formatted_messages = []
        for msg in self.conversation_history:
            formatted_msg = self._format_conversation_message(msg)
            if formatted_msg:
                formatted_messages.append(formatted_msg)

        if not formatted_messages:
            return self._empty_memory_message()

        return "\n\n".join(formatted_messages)

    def _empty_memory_message(self) -> str:
        """Return empty state message for agent memory."""
        return (
            "[dim italic]No conversation history yet.[/dim italic]\n\n"
            "Start a conversation by typing a message below.\n"
            "This section shows the FULL context the agent has:\n"
            "• System instructions (always present)\n"
            "• Your messages\n"
            "• Agent responses\n"
            "• Tool calls and results\n"
            "• Previously injected log context"
        )

    def _format_conversation_message(self, msg: dict[str, Any]) -> str:
        """
        Format a single conversation message for display.

        Args:
            msg: Message dictionary with 'role' and 'content'

        Returns:
            Formatted message string with Rich markup
        """
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # Format based on role
        if role == "system":
            return f"[bold cyan][System][/bold cyan] {content}"

        elif role == "user":
            return f"[bold green][User][/bold green] {content}"

        elif role == "assistant":
            # Check for tool calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                lines = []
                if content:
                    lines.append(f"[bold magenta][Assistant][/bold magenta] {content}")
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "unknown")
                    args = func.get("arguments", "{}")
                    # Parse and pretty-print args if valid JSON
                    try:
                        args_dict = json.loads(args) if isinstance(args, str) else args
                        args_str = json.dumps(args_dict, indent=2)
                    except Exception:
                        args_str = str(args)
                    lines.append(f"  [bold yellow][Tool Call][/bold yellow] {name}({args_str})")
                return "\n".join(lines)
            return f"[bold magenta][Assistant][/bold magenta] {content}"

        elif role == "tool":
            tool_call_id = msg.get("tool_call_id", "")
            tool_id_short = tool_call_id[:8] + "..." if len(tool_call_id) > 8 else tool_call_id
            return f"[bold blue][Tool Result][/bold blue] ({tool_id_short}) {content}"

        else:
            return f"[dim][{role}][/dim] {content}"

    @on(Button.Pressed, "#copy-all-btn")
    def on_copy_all_pressed(self) -> None:
        """Copy both sections to clipboard."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        staged_count = self._get_staged_item_count()
        memory_count = len(self.conversation_history)

        # Build combined content
        parts = [
            "=" * 60,
            "CONTEXT VIEWER SNAPSHOT",
            f"Timestamp: {timestamp}",
            "=" * 60,
            "",
            f"===== STAGED CONTEXT ({staged_count} items) =====",
            "",
            self._formatted_staged or self._format_staged_context(),
            "",
            "",
            f"===== AGENT MEMORY ({memory_count} messages) =====",
            "",
            self._formatted_history or self._format_conversation_history(),
        ]

        combined_content = "\n".join(parts)
        self._copy_to_clipboard(combined_content, "All context")

    def _copy_to_clipboard(self, content: str, section_name: str) -> None:
        """
        Copy content to clipboard with user feedback.

        Args:
            content: Content to copy
            section_name: Name of section for notification
        """
        try:
            import pyperclip

            pyperclip.copy(content)
            self.notify(f"{section_name} copied to clipboard!", severity="information", timeout=3)
        except ImportError:
            self.notify(
                "Clipboard not available. Content shown above for manual copy.",
                severity="warning",
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to copy to clipboard: {e}")
            self.notify(f"Failed to copy: {str(e)}", severity="error", timeout=5)

    @on(Button.Pressed, "#close-btn")
    def on_close_pressed(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Handle escape key - close modal."""
        self.dismiss(None)


class ContextParser:
    """Utility class for parsing context text to extract metadata."""

    # Regex patterns for extracting metadata
    ENTRY_COUNT_PATTERN = re.compile(r"Entry Count:\s*(\d+)", re.IGNORECASE)
    TOTAL_ENTRIES_PATTERN = re.compile(r"Total Entries:\s*(\d+)", re.IGNORECASE)
    LOG_GROUP_PATTERN = re.compile(r"Log Group:\s*([^\n]+)", re.IGNORECASE)
    ENTRY_N_OF_M_PATTERN = re.compile(r"Entry \d+ of (\d+):", re.IGNORECASE)

    @classmethod
    def parse(cls, context_text: str | None) -> ContextMetadata:
        """
        Parse context text to extract metadata.

        Args:
            context_text: Raw context text

        Returns:
            ContextMetadata with parsed values
        """
        if not context_text:
            return ContextMetadata(
                total_chars=0,
                total_tokens=0,
                entry_count=None,
                log_group=None,
                last_updated=datetime.now(),
                context_type="empty",
            )

        # Calculate basic metrics
        total_chars = len(context_text)
        # Rough token estimate: ~4 chars per token for English text
        total_tokens = total_chars // 4

        # Determine context type
        context_type = cls._detect_context_type(context_text)

        # Extract entry count
        entry_count = cls._extract_entry_count(context_text)

        # Extract log group
        log_group = cls._extract_log_group(context_text)

        return ContextMetadata(
            total_chars=total_chars,
            total_tokens=total_tokens,
            entry_count=entry_count,
            log_group=log_group,
            last_updated=datetime.now(),
            context_type=context_type,
        )

    @classmethod
    def _detect_context_type(cls, text: str) -> str:
        """Detect the type of context."""
        has_user_logs = "USER-SELECTED LOG ENTRIES" in text
        has_cache_guidance = "CACHED RESULT INFORMATION" in text or "cache_id" in text.lower()

        if has_user_logs and has_cache_guidance:
            return "mixed"
        elif has_user_logs:
            return "user-selected-logs"
        elif has_cache_guidance:
            return "cache-guidance"
        else:
            return "unknown"

    @classmethod
    def _extract_entry_count(cls, text: str) -> int | None:
        """Extract log entry count from context text."""
        # Try "Entry Count: X" format first
        match = cls.ENTRY_COUNT_PATTERN.search(text)
        if match:
            return int(match.group(1))

        # Try "Total Entries: X" format
        match = cls.TOTAL_ENTRIES_PATTERN.search(text)
        if match:
            return int(match.group(1))

        # Try "Entry N of M:" format (look for highest M)
        matches = cls.ENTRY_N_OF_M_PATTERN.findall(text)
        if matches:
            return max(int(m) for m in matches)

        # Fallback: count JSON objects in array (rough estimate)
        # Look for patterns like {"timestamp": which indicate log entries
        entry_markers = text.count('"timestamp":')
        if entry_markers > 0:
            return entry_markers

        return None

    @classmethod
    def _extract_log_group(cls, text: str) -> str | None:
        """Extract log group name from context text."""
        match = cls.LOG_GROUP_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        return None
