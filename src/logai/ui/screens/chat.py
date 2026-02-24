"""Main chat screen for LogAI TUI."""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Input

from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.core.orchestrator import LLMOrchestrator, ToolCallRecord
from logai.ui.commands import CommandHandler
from logai.ui.screens.context_viewer import ContextParser, ContextViewerScreen
from logai.ui.widgets.input_box import ChatInput
from logai.ui.widgets.log_groups_sidebar import (
    ClickableLogGroupItem,
    LogGroupsSidebar,
    SelectableLogGroupItem,
)
from logai.ui.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    LoadingIndicator,
    SystemMessage,
    UserMessage,
)
from logai.ui.widgets.status_footer import StatusFooter
from logai.ui.widgets.tool_sidebar import ToolCallsSidebar

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager
    from logai.providers.mcp.client import MCPClientManager
    from logai.providers.mcp.sanitization import ResultProcessor

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
        mcp_client: "MCPClientManager | None" = None,
        result_processor: "ResultProcessor | None" = None,
    ) -> None:
        """
        Initialize chat screen.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            log_group_manager: Optional log group manager instance
            mcp_client: Optional unstarted MCP client manager.  When provided
                alongside ``result_processor``, this screen will start the MCP
                server in ``on_mount`` and register MCP tools into the
                ``ToolRegistry``.  Lifecycle ownership stays with ``LogAIApp``,
                which calls ``mcp_client.stop()`` in ``action_quit``.
            result_processor: Optional MCP result post-processor.  Must be
                supplied alongside ``mcp_client``.
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.log_group_manager = log_group_manager
        self._mcp_client = mcp_client
        self._result_processor = result_processor
        self.settings = get_settings()
        self.command_handler = CommandHandler(
            orchestrator, cache_manager, self.settings, self, log_group_manager
        )
        self._current_assistant_message: AssistantMessage | None = None
        self._current_loading_indicator: LoadingIndicator | None = None

        # Tool progress tracking (Phase 1, step 2)
        self._current_tool_index: int = 0
        self._total_tools: int = 0
        self._loading_indicator_start_time: float = 0.0

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
        self._context_update_throttle_seconds: float = (
            self.settings.ui_context_update_throttle
        )  # Max updates per second from settings

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
        yield StatusFooter(model=self.settings.current_llm_model)

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

            # If an MCP client was provided (MCP mode), start it now inside
            # Textual's own event loop via a worker so we never nest asyncio.run().
            if self._mcp_client is not None and self._result_processor is not None:
                # Disable input and surface a status message so the user knows
                # why they cannot type yet.  The worker re-enables input once
                # all MCP tools are registered (or on failure).  This prevents
                # the race condition where a message sent during the ~9-second
                # MCP startup window reaches the LLM with only 1 tool registered.
                chat_input.disabled = True
                status_footer = self.query_one(StatusFooter)
                status_footer.set_status("Connecting to MCP server...")
                logger.info("Chat input disabled while MCP client starts")
                self._start_mcp_client()

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

    @work(exclusive=False)
    async def _start_mcp_client(self) -> None:
        """
        Start the MCP server subprocess and register MCP tools.

        Runs as a Textual worker so it executes inside Textual's event loop —
        avoiding the ``asyncio.run()`` nesting that caused the original crash.
        If startup fails, the error is surfaced as a TUI notification and the
        ``ToolRegistry`` retains whatever tools were registered before the TUI
        launched (i.e. ``fetch_cached_result`` only).  The user can still
        interact with the app; they'll just see tool-call errors until they
        restart with ``--no-mcp``.
        """
        from logai.cli import register_mcp_tools

        assert self._mcp_client is not None  # guarded by caller
        assert self._result_processor is not None

        try:
            logger.info("Starting MCP client from ChatScreen worker")
            await self._mcp_client.start()

            mcp_tool_names = await register_mcp_tools(self._mcp_client, self._result_processor)
            logger.info("Registered %d MCP tools: %s", len(mcp_tool_names), mcp_tool_names)

            # Re-enable the chat input now that all MCP tools are registered.
            # Safe to call directly because this is an async worker running in
            # Textual's own event loop (not a thread worker).
            chat_input = self.query_one(ChatInput)
            chat_input.disabled = False
            chat_input.focus()

            status_footer = self.query_one(StatusFooter)
            status_footer.set_status("Ready")
            logger.info("Chat input re-enabled after MCP startup")

            # Let the user know MCP is ready without cluttering the chat —
            # an informational toast is unobtrusive.
            self.notify(
                f"MCP tools ready ({len(mcp_tool_names)} tools loaded)",
                severity="information",
                timeout=4,
            )

        except Exception as exc:
            # Log the full traceback to file; show a concise message in the TUI.
            logger.warning("MCP startup failed inside ChatScreen worker: %s", exc, exc_info=True)

            # Re-enable the chat input even on failure — the user can still
            # interact with the app, they just won't have MCP log tools.
            try:
                chat_input = self.query_one(ChatInput)
                chat_input.disabled = False
                chat_input.focus()

                status_footer = self.query_one(StatusFooter)
                status_footer.set_status("Ready (MCP unavailable)")
                logger.info("Chat input re-enabled after MCP startup failure")
            except Exception as ui_exc:
                logger.warning("Failed to re-enable chat input after MCP failure: %s", ui_exc)

            self.notify(
                f"MCP server failed to start: {exc}\n"
                "CloudWatch MCP tools are unavailable. "
                "Restart with --no-mcp to use native tools.",
                severity="error",
                timeout=10,
            )

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
        status_footer = self.query_one(StatusFooter)

        try:
            # Inject selected groups context if any are selected
            if self._log_groups_sidebar and self._log_groups_sidebar.has_selection():
                selected_groups = self._log_groups_sidebar.get_selected_groups()
                selection_context = self._format_selected_groups_context(selected_groups)
                self.orchestrator.inject_context_update(selection_context)
                logger.debug(f"Injected {len(selected_groups)} selected groups into context")

            # Update status
            status_footer.set_status("Thinking...")

            # Add loading indicator (Phase 1, step 3: Track start time for minimum display)
            self._loading_indicator_start_time = time.time()
            self._current_loading_indicator = LoadingIndicator()
            messages_container.mount(self._current_loading_indicator)
            messages_container.scroll_end(animate=False)

            # Create assistant message for streaming
            self._current_assistant_message = AssistantMessage("")
            messages_container.mount(self._current_assistant_message)

            # Remove loading indicator (Phase 1, step 3: Ensure minimum 200ms display time)
            if self._current_loading_indicator:
                # Calculate elapsed time since loading indicator was shown
                elapsed = time.time() - self._loading_indicator_start_time
                min_display_time = 0.2  # 200ms minimum

                # Wait if needed to reach minimum display time
                if elapsed < min_display_time:
                    await asyncio.sleep(min_display_time - elapsed)

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
            status_footer.set_status("Ready")

            # Get cache stats from metrics instead of cache manager
            hits = int(self.orchestrator.metrics.get_counter_value("cache_hit"))
            misses = int(self.orchestrator.metrics.get_counter_value("cache_miss"))
            status_footer.update_cache_stats(hits, misses)

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
            status_footer.set_status("Error")

        finally:
            self._current_assistant_message = None

    @on(ClickableLogGroupItem.LogGroupPreviewRequested)
    @on(SelectableLogGroupItem.LogGroupPreviewRequested)
    async def on_log_group_preview_requested(
        self,
        event: ClickableLogGroupItem.LogGroupPreviewRequested
        | SelectableLogGroupItem.LogGroupPreviewRequested,
    ) -> None:
        """
        Handle request to preview logs from a log group.

        Args:
            event: Preview request event with log group name
        """
        try:
            # Get datasource from tool registry via orchestrator
            # The tools are registered with datasource instances
            tool = self.orchestrator.tool_registry.get("list_log_groups")
            if tool is None or not hasattr(tool, "datasource"):
                self.notify(
                    "Preview feature not available - datasource not found",
                    severity="error",
                    timeout=5,
                )
                logger.error("Could not access datasource from tool registry")
                return

            datasource = tool.datasource

            # Import LogPreviewScreen here to avoid circular imports
            from logai.ui.screens.log_preview import LogPreviewScreen

            # Define callback to handle modal result
            def handle_log_selection(result: dict[str, Any] | None) -> None:
                """Handle the result from the log preview modal."""
                if result:
                    entry_count = len(result.get("selected_entries", []))
                    logger.debug(f"Injecting {entry_count} log entries from preview to context")
                    # Use call_later to schedule the async operation
                    self.call_later(self._inject_log_entries_to_context, result)
                else:
                    logger.debug("Log preview modal dismissed without selection")

            # Show preview modal with callback
            self.app.push_screen(
                LogPreviewScreen(
                    log_group_name=event.log_group_name,
                    datasource=datasource,
                ),
                handle_log_selection,
            )

        except Exception as e:
            logger.error(f"Failed to open log preview: {e}", exc_info=True)
            self.notify(
                f"Failed to open preview: {str(e)}",
                severity="error",
                timeout=5,
            )

    @on(StatusFooter.ContextViewRequested)
    async def on_context_view_requested(self, event: StatusFooter.ContextViewRequested) -> None:
        """
        Handle request to view context from status bar click.

        Args:
            event: Context view request event
        """
        try:
            # Get current staged context from orchestrator
            staged_context = self.orchestrator._pending_context_injection

            # Get full context snapshot from orchestrator (includes system prompt)
            conversation_history = self.orchestrator.get_full_context_snapshot()

            # Parse metadata for staged context
            metadata = ContextParser.parse(staged_context)

            # Update metadata with actual token count from budget tracker
            if hasattr(self.orchestrator, "budget_tracker"):
                usage = self.orchestrator.budget_tracker.get_usage()
                metadata.total_tokens = usage.total_tokens

            # Define callback (follows pattern from log preview fix)
            def handle_context_viewer_close(result: None) -> None:
                """Handle context viewer modal close."""
                logger.debug("Context viewer modal closed")

            # Show modal with callback
            self.app.push_screen(
                ContextViewerScreen(
                    staged_context=staged_context,
                    conversation_history=conversation_history,
                    metadata=metadata,
                ),
                handle_context_viewer_close,
            )

        except Exception as e:
            logger.error(f"Failed to open context viewer: {e}", exc_info=True)
            self.notify(
                f"Failed to open context viewer: {str(e)}",
                severity="error",
                timeout=5,
            )

    def _format_selected_groups_context(self, selected_groups: list[str]) -> str:
        """
        Format selected log groups for agent context injection.

        Creates a clear message that tells the agent which log groups
        the user has selected, allowing natural references like "these logs".

        Args:
            selected_groups: List of selected log group names

        Returns:
            Formatted context string for agent
        """
        count = len(selected_groups)

        # Truncate display if too many groups to prevent excessive context size
        MAX_DISPLAY_GROUPS = 20
        if count > MAX_DISPLAY_GROUPS:
            group_list = "\n".join(f"- {name}" for name in selected_groups[:MAX_DISPLAY_GROUPS])
            group_list += f"\n... and {count - MAX_DISPLAY_GROUPS} more groups"
            group_names = (
                ", ".join(selected_groups[:MAX_DISPLAY_GROUPS])
                + f" (and {count - MAX_DISPLAY_GROUPS} more)"
            )
        else:
            # Show all groups if within limit
            group_list = "\n".join(f"- {name}" for name in selected_groups)
            group_names = ", ".join(selected_groups)

        return f"""USER HAS SELECTED THE FOLLOWING LOG GROUPS:

The user has explicitly selected {count} log group(s) in the sidebar. When they refer to "these logs", "selected groups", "these", or make requests without specifying a log group, they are referring to:

{group_list}

INSTRUCTIONS:
1. When the user says "search these", "check these logs", "look at these", etc. - use the above log groups
2. When the user asks about "errors", "issues", etc. without specifying a group - search the selected groups
3. If the user explicitly names a different log group, use that instead
4. You do NOT need to ask which log groups to search - the user has already told you by selecting them

Selected groups: {group_names}
"""

    async def _inject_log_entries_to_context(self, result: dict[str, Any]) -> None:
        """
        Inject selected log entries into agent context.

        Args:
            result: Dictionary with log_group_name and selected_entries
        """
        try:
            log_group = result["log_group_name"]
            entries = result["selected_entries"]
            count = len(entries)

            # Format entries for context
            context_message = self._format_log_entries_for_context(log_group, entries)
            logger.info(
                f"Adding {count} log entries from {log_group} to context ({len(context_message)} chars)"
            )

            # Inject via orchestrator
            self.orchestrator.inject_context_update(context_message)

            # Show system message in chat
            messages_container = self.query_one("#messages-container", VerticalScroll)
            entry_word = "entry" if count == 1 else "entries"
            system_msg = SystemMessage(
                f"Added {count} log {entry_word} from {log_group} to context"
            )
            messages_container.mount(system_msg)
            messages_container.scroll_end(animate=False)

        except Exception as e:
            logger.error(f"Failed to inject log entries to context: {e}", exc_info=True)
            self.notify(
                f"Failed to add logs to context: {str(e)}",
                severity="error",
                timeout=5,
            )

    def _format_log_entries_for_context(self, log_group: str, entries: list[dict[str, Any]]) -> str:
        """
        Format log entries for agent context injection.

        Args:
            log_group: Name of the log group
            entries: List of log event dictionaries

        Returns:
            Formatted context string
        """
        formatted_entries = []
        for entry in entries:
            # Format timestamp for readability
            timestamp_ms = entry.get("timestamp", 0)
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            formatted_entries.append(
                {
                    "timestamp": formatted_time,
                    "message": entry.get("message", ""),
                    "log_stream": entry.get("log_stream", ""),
                }
            )

        return f"""USER-SELECTED LOG ENTRIES for analysis:

Log Group: {log_group}
Entry Count: {len(entries)}

The user has specifically selected these log entries for your analysis:

```json
{json.dumps(formatted_entries, indent=2)}
```

YOU MUST analyze these {len(entries)} log entries. Do NOT ask for a log group to search. The logs are provided above. Provide insights, patterns, and categorization based on these specific entries."""

    def _handle_context_notification(self, level: str, message: str) -> None:
        """
        Handle context management notifications from orchestrator.

        Args:
            level: Severity level ("info", "warning", "error")
            message: Notification message
        """
        try:
            # Map level to Textual severity with configurable timeouts
            severity: Literal["error", "warning", "information"]
            if level == "error":
                severity = "error"
                timeout = self.settings.ui_tool_timeout_initial
            elif level == "warning":
                severity = "warning"
                timeout = self.settings.ui_tool_timeout_subsequent
            else:
                severity = "information"
                timeout = self.settings.ui_tool_timeout_final

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
                allocation = self.orchestrator.budget_tracker.allocation
                status_footer = self.query_one(StatusFooter)
                status_footer.update_context_usage(
                    utilization_pct=usage.utilization_pct,
                    used_tokens=usage.total_tokens,
                    total_tokens=allocation.usable_tokens,
                )

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
            sidebar: LogGroupsSidebar | ToolCallsSidebar | None = self._log_groups_sidebar
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
            # Resize successful - no notification needed
            pass
        else:
            self.notify("Log groups sidebar at minimum width", severity="warning")

    def action_expand_left_sidebar(self) -> None:
        """Expand the left (log groups) sidebar."""
        if not self._log_groups_sidebar_visible:
            self.notify("Log groups sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("left", "expand"):
            # Resize successful - no notification needed
            pass
        else:
            self.notify("Log groups sidebar at maximum width", severity="warning")

    def action_shrink_right_sidebar(self) -> None:
        """Shrink the right (tool calls) sidebar."""
        if not self._tool_sidebar_visible:
            self.notify("Tool calls sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("right", "shrink"):
            # Resize successful - no notification needed
            pass
        else:
            self.notify("Tool calls sidebar at minimum width", severity="warning")

    def action_expand_right_sidebar(self) -> None:
        """Expand the right (tool calls) sidebar."""
        if not self._tool_sidebar_visible:
            self.notify("Tool calls sidebar is hidden", severity="warning")
            return

        if self._resize_sidebar("right", "expand"):
            # Resize successful - no notification needed
            pass
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

            # Phase 1, step 2: Update status footer based on tool execution
            status_footer = self.query_one(StatusFooter)

            # Update status based on tool state
            if record.status == "running":
                # Tool is executing - show progress
                # Count total tools to show progress (simple heuristic: count recent tools)
                running_tools = [r for r in self._recent_tool_calls if r.status == "running"]
                if len(running_tools) > 1:
                    # Multiple tools - show progress counter
                    tool_index = (
                        len(
                            [
                                r
                                for r in self._recent_tool_calls
                                if r.status in ["completed", "error"]
                            ]
                        )
                        + 1
                    )
                    total = len(self._recent_tool_calls)
                    status_footer.set_status(f"Running tool {tool_index}/{total}: {record.name}...")
                else:
                    # Single tool or first tool
                    status_footer.set_status(f"Running tool: {record.name}...")
            elif record.status == "completed":
                # Tool completed - show processing message
                status_footer.set_status("Processing results...")
            elif record.status == "error":
                # Tool failed - show error
                status_footer.set_status(f"Tool error: {record.name}")

        except Exception as e:
            logger.warning(f"Failed to update tool sidebar or status: {e}", exc_info=True)
