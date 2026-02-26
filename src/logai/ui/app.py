"""Main Textual application for LogAI."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

from logai.cache.manager import CacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.screens.chat import ChatScreen

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager
    from logai.providers.datasources.cloudwatch import CloudWatchDataSource
    from logai.providers.mcp.client import MCPClientManager
    from logai.providers.mcp.sanitization import ResultProcessor

logger = logging.getLogger(__name__)


class LogAIApp(App[None]):
    """LogAI Terminal User Interface application."""

    TITLE = "LogAI - CloudWatch Assistant"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        cache_manager: CacheManager,
        log_group_manager: "LogGroupManager | None" = None,
        mcp_client: "MCPClientManager | None" = None,
        result_processor: "ResultProcessor | None" = None,
        datasource: "CloudWatchDataSource | None" = None,
    ) -> None:
        """
        Initialize LogAI application.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            log_group_manager: Optional log group manager instance
            mcp_client: Optional unstarted MCP client manager.  When provided
                (and ``result_processor`` is also given), ``ChatScreen`` will
                start the MCP server inside its ``on_mount`` worker and register
                MCP tools into the ``ToolRegistry``.
            result_processor: Optional MCP result post-processor (sanitization,
                caching).  Must be supplied alongside ``mcp_client``.
            datasource: Optional CloudWatch data source instance.  Threaded
                through to ``ChatScreen`` so log preview works in MCP mode
                without relying on the tool registry.

        Raises:
            FileNotFoundError: If CSS file does not exist
        """
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.log_group_manager = log_group_manager
        self.mcp_client = mcp_client
        self.result_processor = result_processor
        self.datasource = datasource

        # Validate CSS file exists after initialization
        try:
            if isinstance(self.CSS_PATH, str | Path):
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
            ChatScreen(
                orchestrator=self.orchestrator,
                cache_manager=self.cache_manager,
                log_group_manager=self.log_group_manager,
                mcp_client=self.mcp_client,
                result_processor=self.result_processor,
                datasource=self.datasource,
            )
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
            # Stop the MCP server subprocess if one was started.  This is a
            # no-op if mcp_client is None (native-tools mode) or if start()
            # was never called (e.g. the TUI exited before on_mount finished).
            if self.mcp_client is not None:
                try:
                    await self.mcp_client.stop()
                    logger.info("MCP client stopped")
                except Exception as e:
                    logger.warning("Error stopping MCP client during shutdown: %s", e)
            self.exit()
