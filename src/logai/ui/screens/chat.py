"""Main chat screen for LogAI TUI."""

import asyncio
import logging
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Input

from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.core.orchestrator import LLMOrchestrator, ToolCallRecord, ToolCallStatus
from logai.ui.commands import CommandHandler
from logai.ui.widgets.input_box import ChatInput
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

        # Sidebar state - open by default per user requirement
        self._sidebar_visible = True
        self._tool_sidebar: ToolCallsSidebar | None = None
        self._recent_tool_calls: list[ToolCallRecord] = []  # Keep history for replay

    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        yield Header()

        # Main content area with optional sidebar
        with Horizontal(id="main-content"):
            yield VerticalScroll(id="messages-container")
            if self._sidebar_visible:
                self._tool_sidebar = ToolCallsSidebar(id="tools-sidebar")
                yield self._tool_sidebar

        yield Container(ChatInput(), id="input-container")
        yield StatusBar(model=self.settings.current_llm_model)

    async def on_mount(self) -> None:
        """Set up the screen when mounted."""
        try:
            logger.info("Mounting ChatScreen")

            # Register for tool call events from orchestrator
            self.orchestrator.register_tool_listener(self._on_tool_call_event)

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

    def toggle_sidebar(self) -> None:
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
            if self._tool_sidebar:
                self._tool_sidebar.remove()
                self._tool_sidebar = None

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
