"""Main chat screen for LogAI TUI."""

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Input

from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.core.orchestrator import LLMOrchestrator
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


class ChatScreen(Screen[None]):
    """Main chat screen."""

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
    }

    #messages-container {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }
    
    #input-container {
        height: auto;
        padding: 0 2 1 2;
    }
    """

    def __init__(self, orchestrator: LLMOrchestrator, cache_manager: CacheManager) -> None:
        """
        Initialize chat screen.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.settings = get_settings()
        self.command_handler = CommandHandler(orchestrator, cache_manager, self.settings)
        self._current_assistant_message: AssistantMessage | None = None
        self._current_loading_indicator: LoadingIndicator | None = None

    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        yield Header()
        yield VerticalScroll(id="messages-container")
        yield Container(ChatInput(), id="input-container")
        yield StatusBar(model=self.settings.current_llm_model)

    def on_mount(self) -> None:
        """Set up the screen when mounted."""
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
