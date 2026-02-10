"""Main Textual application for LogAI."""

from textual.app import App, ComposeResult
from textual.binding import Binding

from logai.cache.manager import CacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.screens.chat import ChatScreen


class LogAIApp(App[None]):
    """LogAI Terminal User Interface application."""

    TITLE = "LogAI - CloudWatch Assistant"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, orchestrator: LLMOrchestrator, cache_manager: CacheManager) -> None:
        """
        Initialize LogAI application.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield ChatScreen(orchestrator=self.orchestrator, cache_manager=self.cache_manager)

    async def action_quit(self) -> None:
        """Quit the application with cleanup."""
        # Shutdown cache manager
        await self.cache_manager.shutdown()
        self.exit()
