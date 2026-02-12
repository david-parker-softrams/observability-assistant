"""Main chat screen for LogAI TUI."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Literal

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input

from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.core.orchestrator import LLMOrchestrator, ToolCallRecord
from logai.ui.commands import CommandHandler
from logai.ui.widgets.input_box import ChatInput
from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar
from logai.ui.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    LoadingIndicator,
    SystemMessage,
    UserMessage,
)
from logai.ui.widgets.status_bar import StatusBar
from logai.ui.widgets.tool_sidebar import ToolCallsSidebar

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

logger = logging.getLogger(__name__)


# Sidebar resize configuration
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28 (default)


class ChatScreen(Screen[None]):
    """Main chat screen."""

    BINDINGS = [
        Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
        Binding("f2", "expand_left_sidebar", "Logs ▶", show=True),
        Binding("f3", "expand_right_sidebar", "◀ Tools", show=True),
        Binding("f4", "shrink_right_sidebar", "Tools ▶", show=True),
    ]

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

    /* Left sidebar positioning */
    #log-groups-sidebar {
        dock: left;
    }

    /* Right sidebar positioning */
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
        """
        Initialize chat screen.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            log_group_manager: Optional log group manager instance
        """
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
        self._log_groups_sidebar_visible = self.settings.log_groups_sidebar_visible  # Left sidebar

        # Widget references
        self._tool_sidebar: ToolCallsSidebar | None = None
        self._log_groups_sidebar: LogGroupsSidebar | None = None

        self._recent_tool_calls: list[ToolCallRecord] = []  # Keep history for replay

        # Sidebar width state (indexes into SIDEBAR_WIDTH_STEPS)
        self._left_sidebar_width_index: int = DEFAULT_SIDEBAR_WIDTH_INDEX
        self._right_sidebar_width_index: int = DEFAULT_SIDEBAR_WIDTH_INDEX

        # Context notification throttling
        self._last_context_update_time: float = 0.0
        self._context_update_throttle_seconds: float = 1.0  # Max 1 update per second

    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        yield Header()

        # Main content area with sidebars
        with Horizontal(id="main-content"):
            # Left sidebar - log groups
            self._log_groups_sidebar = LogGroupsSidebar(
                log_group_manager=self.log_group_manager,
                id="log-groups-sidebar",
            )
            # Set initial visibility
            self._log_groups_sidebar.display = self._log_groups_sidebar_visible
            yield self._log_groups_sidebar

            # Center - messages
            yield VerticalScroll(id="messages-container")

            # Right sidebar - tool calls
            self._tool_sidebar = ToolCallsSidebar(id="tools-sidebar")
            self._tool_sidebar.display = self._tool_sidebar_visible
            yield self._tool_sidebar

        yield Container(ChatInput(), id="input-container")
        yield StatusBar(model=self.settings.current_llm_model)
        yield Footer()

    async def on_mount(self) -> None:
        """Set up the screen when mounted."""
        try:
            logger.info("Mounting ChatScreen")

            # Register for tool call events from orchestrator
            self.orchestrator.register_tool_listener(self._on_tool_call_event)

            # Register for context management notifications
            self.orchestrator.set_context_notification_callback(self._handle_context_notification)

            # Add welcome message
            messages_container = self.query_one("#messages-container", VerticalScroll)
            welcome = SystemMessage(
                "Welcome to LogAI! Ask me about your AWS CloudWatch logs.\n"
                "Type /help for available commands."
            )
            messages_container.mount(welcome)

            # Focus the input
            chat_input = self.query_one(ChatInput)
            chat_input.focus()

            logger.info("ChatScreen mounted successfully")

        except Exception as e:
            logger.error(f"Error mounting ChatScreen: {e}", exc_info=True)
            # Still try to show an error to the user if possible
            try:
                messages_container = self.query_one("#messages-container", VerticalScroll)
                error_msg = ErrorMessage(f"Failed to initialize chat: {str(e)}")
                messages_container.mount(error_msg)
            except Exception:
                # If we can't even show the error, log it and re-raise
                logger.critical("Failed to display error message to user", exc_info=True)
                raise

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        Handle user input submission.

        Args:
            event: Input submitted event
        """
        message = event.value.strip()

        # Ignore empty messages
        if not message:
            return

        # Clear the input
        event.input.value = ""

        # Add user message to chat
        messages_container = self.query_one("#messages-container", VerticalScroll)
        user_msg = UserMessage(message)
        messages_container.mount(user_msg)

        # Scroll to bottom
        messages_container.scroll_end(animate=False)

        # Check if it's a command
        if self.command_handler.is_command(message):
            response = await self.command_handler.handle_command(message)
            system_msg = SystemMessage(response)
            messages_container.mount(system_msg)
            messages_container.scroll_end(animate=False)
            return

        # Process message with LLM
        self._process_message(message)

    @work(exclusive=True)
    async def _process_message(self, user_message: str) -> None:
        """
        Process a message with the LLM orchestrator.

        This is a worker method that runs asynchronously.

        Args:
            user_message: User's message
        """
        messages_container = self.query_one("#messages-container", VerticalScroll)
        status_bar = self.query_one(StatusBar)

        try:
            # Update status
            status_bar.set_status("Thinking...")

            # Add loading indicator
            self._current_loading_indicator = LoadingIndicator()
            messages_container.mount(self._current_loading_indicator)
            messages_container.scroll_end(animate=False)

            # Create assistant message for streaming
            self._current_assistant_message = AssistantMessage("")
            messages_container.mount(self._current_assistant_message)

            # Remove loading indicator
            if self._current_loading_indicator:
                self._current_loading_indicator.remove()
                self._current_loading_indicator = None

            # Stream response
            async for token in self.orchestrator.chat_stream(user_message):
                if self._current_assistant_message:
                    self._current_assistant_message.append_token(token)
                    # Scroll to keep up with streaming
                    messages_container.scroll_end(animate=False)
                    # Small delay to make streaming visible
                    await asyncio.sleep(0.01)

            # Update status
            status_bar.set_status("Ready")

            # Update cache stats
            cache_stats = await self.cache_manager.get_statistics()
            hits = cache_stats.get("total_hits", 0)
            misses = cache_stats.get("total_misses", 0)
            status_bar.update_cache_stats(hits, misses)

            # Update context usage
            self._update_context_status()

            # Scroll to bottom
            messages_container.scroll_end(animate=False)

        except Exception as e:
            # Remove loading indicator if present
            if self._current_loading_indicator:
                self._current_loading_indicator.remove()
                self._current_loading_indicator = None

            # Show error message
            error_msg = ErrorMessage(f"An error occurred: {str(e)}")
            messages_container.mount(error_msg)
            messages_container.scroll_end(animate=False)

            # Update status
            status_bar.set_status("Error")

        finally:
            self._current_assistant_message = None

    def _handle_context_notification(self, level: str, message: str) -> None:
        """
        Handle context management notifications from orchestrator.

        Args:
            level: Severity level ("info", "warning", "error")
            message: Notification message
        """
        try:
            # Map level to Textual severity
            if level == "error":
                severity = "error"
                timeout = 10
            elif level == "warning":
                severity = "warning"
                timeout = 8
            else:
                severity = "information"
                timeout = 5

            # Show toast notification
            self.notify(message, severity=severity, timeout=timeout)

            # Update context status bar if this is a context-related notification
            # (This will be called after the main update, so we can skip throttling here)
            if any(
                keyword in message.lower() for keyword in ["cached", "pruned", "context", "token"]
            ):
                self._update_context_status()

        except Exception as e:
            logger.warning(f"Failed to handle context notification: {e}", exc_info=True)

    def _update_context_status(self) -> None:
        """Update context usage in status bar with throttling."""
        try:
            # Throttle updates to avoid UI flicker
            current_time = time.time()
            if (
                current_time - self._last_context_update_time
                < self._context_update_throttle_seconds
            ):
                return

            self._last_context_update_time = current_time

            # Get usage from orchestrator's budget tracker
            if hasattr(self.orchestrator, "budget_tracker"):
                usage = self.orchestrator.budget_tracker.get_usage()
                status_bar = self.query_one(StatusBar)
                status_bar.update_context_usage(usage.utilization_pct)

        except Exception as e:
            logger.debug(f"Failed to update context status: {e}", exc_info=True)

    # Sidebar resize methods
    def _resize_sidebar(
        self, sidebar_id: Literal["left", "right"], direction: Literal["expand", "shrink"]
    ) -> bool:
        """
        Resize a sidebar by one step in the given direction.

        Args:
            sidebar_id: Which sidebar to resize
            direction: Direction to resize

        Returns:
            True if resize happened, False if already at limit
        """
        # Get current state
        if sidebar_id == "left":
            current_index = self._left_sidebar_width_index
            sidebar = self._log_groups_sidebar
        else:
            current_index = self._right_sidebar_width_index
            sidebar = self._tool_sidebar

        # Calculate new index
        max_index = len(SIDEBAR_WIDTH_STEPS) - 1
        if direction == "expand":
            new_index = min(current_index + 1, max_index)
        else:  # shrink
            new_index = max(current_index - 1, 0)

        # Check if at limit
        if new_index == current_index:
            return False

        # Update state
        if sidebar_id == "left":
            self._left_sidebar_width_index = new_index
        else:
            self._right_sidebar_width_index = new_index

        # Apply width to widget
        new_width = SIDEBAR_WIDTH_STEPS[new_index]
        if sidebar:
            sidebar.styles.width = new_width

        return True

    def action_shrink_left_sidebar(self) -> None:
        """Shrink the left (log groups) sidebar."""
        if not self._log_groups_sidebar_visible:
            self.notify("Log groups sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("left", "shrink"):
            width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
            self.notify(f"Log groups: {width} columns")
        else:
            self.notify("Log groups sidebar at minimum width", severity="warning")

    def action_expand_left_sidebar(self) -> None:
        """Expand the left (log groups) sidebar."""
        if not self._log_groups_sidebar_visible:
            self.notify("Log groups sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("left", "expand"):
            width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
            self.notify(f"Log groups: {width} columns")
        else:
            self.notify("Log groups sidebar at maximum width", severity="warning")

    def action_shrink_right_sidebar(self) -> None:
        """Shrink the right (tool calls) sidebar."""
        if not self._tool_sidebar_visible:
            self.notify("Tool calls sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("right", "shrink"):
            width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
            self.notify(f"Tool calls: {width} columns")
        else:
            self.notify("Tool calls sidebar at minimum width", severity="warning")

    def action_expand_right_sidebar(self) -> None:
        """Expand the right (tool calls) sidebar."""
        if not self._tool_sidebar_visible:
            self.notify("Tool calls sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("right", "expand"):
            width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
            self.notify(f"Tool calls: {width} columns")
        else:
            self.notify("Tool calls sidebar at maximum width", severity="warning")

    def toggle_sidebar(self) -> None:
        """Toggle the tools sidebar visibility."""
        self._tool_sidebar_visible = not self._tool_sidebar_visible

        if self._tool_sidebar:
            self._tool_sidebar.display = self._tool_sidebar_visible

            # Refresh display when showing (in case data updated while hidden)
            if self._tool_sidebar_visible:
                # Restore saved width
                width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
                self._tool_sidebar.styles.width = width

                # Replay recent tool calls to populate sidebar
                for record in self._recent_tool_calls:
                    self._tool_sidebar.update_tool_call(record)

    def toggle_log_groups_sidebar(self) -> None:
        """Toggle the log groups sidebar visibility."""
        self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible

        if self._log_groups_sidebar:
            self._log_groups_sidebar.display = self._log_groups_sidebar_visible

            # Refresh display when showing (in case data updated while hidden)
            if self._log_groups_sidebar_visible:
                # Restore saved width
                width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
                self._log_groups_sidebar.styles.width = width

                self._log_groups_sidebar.refresh_display()

    def on_tool_call(self, record: ToolCallRecord) -> None:
        """
        Handle tool call events from orchestrator.

        Args:
            record: Tool call record to display
        """
        # Keep in recent history for replay
        # Remove oldest if at capacity
        MAX_RECENT_CALLS = 20
        if len(self._recent_tool_calls) >= MAX_RECENT_CALLS:
            self._recent_tool_calls.pop(0)

        # Update or add to history
        existing = next((r for r in self._recent_tool_calls if r.id == record.id), None)
        if existing:
            idx = self._recent_tool_calls.index(existing)
            self._recent_tool_calls[idx] = record
        else:
            self._recent_tool_calls.append(record)

        # Update sidebar if visible
        if self._tool_sidebar:
            self._tool_sidebar.update_tool_call(record)

    def _on_tool_call_event(self, record: ToolCallRecord) -> None:
        """
        Handler for tool call events from orchestrator.

        Since the orchestrator runs in the same async event loop as the UI,
        we can call on_tool_call() directly without thread marshalling.

        Args:
            record: Tool call record from orchestrator
        """
        try:
            # Orchestrator runs in same event loop, so we can call directly
            self.on_tool_call(record)
        except Exception as e:
            logger.warning(f"Failed to update tool sidebar: {e}", exc_info=True)
