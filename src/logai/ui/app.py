"""Main Textual application for LogAI."""

import logging
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from logai.cache.manager import CacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.screens.chat import ChatScreen

logger = logging.getLogger(__name__)


class LogAIApp(App[None]):
    """LogAI Terminal User Interface application."""

    TITLE = "LogAI - CloudWatch Assistant"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"

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

        Raises:
            FileNotFoundError: If CSS file does not exist
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager

        # Validate CSS file exists after initialization
        try:
            if isinstance(self.CSS_PATH, (str, Path)):
                css_path = Path(str(self.CSS_PATH))
                if not css_path.exists():
                    error_msg = f"CSS file not found at: {css_path}"
                    logger.error(error_msg)
                    raise FileNotFoundError(error_msg)
                logger.info(f"Loaded CSS from: {css_path}")
        except (TypeError, ValueError) as e:
            logger.warning(f"Could not validate CSS path: {e}")

        logger.info("LogAIApp initialized successfully")

    async def on_mount(self) -> None:
        """Mount the chat screen when app starts."""
        await self.push_screen(
            ChatScreen(orchestrator=self.orchestrator, cache_manager=self.cache_manager)
        )

    async def action_quit(self) -> None:
        """Quit the application with cleanup."""
        try:
            logger.info("Shutting down LogAI application")
            # Shutdown cache manager
            await self.cache_manager.shutdown()
            logger.info("Cache manager shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            # Still exit even if cleanup fails
        finally:
            self.exit()
