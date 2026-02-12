"""Command handler for special slash commands."""

from typing import TYPE_CHECKING

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator

if TYPE_CHECKING:
    from logai.ui.screens.chat import ChatScreen
    from logai.core.log_group_manager import LogGroupManager


class CommandHandler:
    """Handles special slash commands in the chat."""

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        cache_manager: CacheManager,
        settings: LogAISettings,
        chat_screen: "ChatScreen | None" = None,
        log_group_manager: "LogGroupManager | None" = None,
    ) -> None:
        """
        Initialize command handler.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            settings: Application settings
            chat_screen: Optional reference to chat screen for UI commands
            log_group_manager: Optional log group manager for refresh
        """
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.settings = settings
        self.chat_screen = chat_screen
        self.log_group_manager = log_group_manager

    def is_command(self, message: str) -> bool:
        """
        Check if a message is a command.

        Args:
            message: User message

        Returns:
            True if message starts with '/'
        """
        return message.strip().startswith("/")

    async def handle_command(self, command: str) -> str:
        """
        Handle a special command.

        Args:
            command: Command string (including the /)

        Returns:
            Response message
        """
        command = command.strip()
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == "/help":
            return self._show_help()
        elif cmd == "/clear":
            return self._clear_history()
        elif cmd == "/refresh":
            return await self._refresh_log_groups(parts[1] if len(parts) > 1 else "")
        elif cmd == "/cache":
            if len(parts) > 1:
                subcmd = parts[1].lower()
                if subcmd == "status":
                    return await self._cache_status()
                elif subcmd == "clear":
                    return await self._cache_clear()
                else:
                    return f"Unknown cache command: {subcmd}\nUse /help to see available commands."
            else:
                return "Usage: /cache [status|clear]"
        elif cmd == "/quit" or cmd == "/exit":
            return "Use Ctrl+C or Ctrl+Q to quit the application."
        elif cmd == "/model":
            return self._show_model()
        elif cmd == "/config":
            return self._show_config()
        elif cmd == "/tools":
            return self._toggle_tools_sidebar()
        else:
            return f"Unknown command: {cmd}\nUse /help to see available commands."

    async def _refresh_log_groups(self, args: str) -> str:
        """
        Refresh the pre-loaded log groups list.

        Args:
            args: Optional arguments (currently none supported)

        Returns:
            Status message
        """
        if not self.log_group_manager:
            return "[red]Error:[/red] Log group manager not initialized."

        # Reject any arguments for now (prefix filtering not yet implemented)
        if args:
            return (
                "[red]Error:[/red] /refresh does not accept arguments currently.\nUsage: /refresh"
            )

        # Perform refresh
        result = await self.log_group_manager.refresh()

        if result.success:
            # Calculate diff if we had previous data
            count = result.count
            duration_sec = result.duration_ms / 1000

            # Inject context update to orchestrator
            refresh_notice = f"""## Log Groups Updated

The log group list has been refreshed. You now have access to {count} log groups.
Please use this updated list for subsequent queries. The previous list is now outdated.

{self.log_group_manager.format_for_prompt()}
"""
            self.orchestrator.inject_context_update(refresh_notice)

            return f"""[green]Log groups refreshed successfully![/green]

[bold]Found:[/bold] {count} log groups
[bold]Duration:[/bold] {duration_sec:.1f}s

The agent's context has been updated with the new list."""
        else:
            return f"""[red]Failed to refresh log groups[/red]

[bold]Error:[/bold] {result.error_message}

The previous log group list (if any) has been preserved."""

    def _show_help(self) -> str:
        """Show help message with available commands."""
        return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/refresh[/cyan] - Refresh the log groups list from AWS
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/tools[/cyan] - Toggle tool calls sidebar
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)

[bold]Usage Tips:[/bold]
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
- Log groups are pre-loaded at startup - use /refresh to update
- Responses are streamed in real-time
- PII sanitization is enabled by default
"""

    def _clear_history(self) -> str:
        """Clear conversation history."""
        self.orchestrator.clear_history()
        return "[dim]Conversation history cleared.[/dim]"

    async def _cache_status(self) -> str:
        """Show cache statistics."""
        stats = await self.cache_manager.get_statistics()

        total_entries = stats.get("total_entries", 0)
        total_size_mb = stats.get("total_size_bytes", 0) / (1024 * 1024)
        total_hits = stats.get("total_hits", 0)
        total_misses = stats.get("total_misses", 0)

        # Calculate hit rate
        total_requests = total_hits + total_misses
        if total_requests > 0:
            hit_rate = (total_hits / total_requests) * 100
        else:
            hit_rate = 0.0

        return f"""[bold]Cache Statistics:[/bold]

Total Entries: {total_entries}
Total Size: {total_size_mb:.2f} MB
Cache Hits: {total_hits}
Cache Misses: {total_misses}
Hit Rate: {hit_rate:.1f}%

Cache Directory: {self.settings.cache_dir}
Max Size: {self.cache_manager.CACHE_MAX_SIZE_MB} MB
Max Entries: {self.cache_manager.CACHE_MAX_ENTRIES}
"""

    async def _cache_clear(self) -> str:
        """Clear the cache."""
        count = await self.cache_manager.clear()
        return f"[dim]Cache cleared. Removed {count} entries.[/dim]"

    def _show_model(self) -> str:
        """Show current LLM model information."""
        return f"""[bold]LLM Configuration:[/bold]

Provider: {self.settings.llm_provider}
Model: {self.settings.current_llm_model}
Streaming: Enabled
"""

    def _show_config(self) -> str:
        """Show current configuration."""
        return f"""[bold]Current Configuration:[/bold]

LLM Provider: {self.settings.llm_provider}
LLM Model: {self.settings.current_llm_model}
AWS Region: {self.settings.aws_region}
PII Sanitization: {"Enabled" if self.settings.pii_sanitization_enabled else "Disabled"}
Cache Directory: {self.settings.cache_dir}
Cache Max Size: {self.settings.cache_max_size_mb} MB
Cache TTL: {self.settings.cache_ttl_seconds}s
"""

    def _toggle_tools_sidebar(self) -> str:
        """Toggle the tools sidebar visibility."""
        if self.chat_screen:
            self.chat_screen.toggle_sidebar()
            if self.chat_screen._sidebar_visible:
                return "[dim]Tool calls sidebar shown.[/dim]"
            else:
                return "[dim]Tool calls sidebar hidden.[/dim]"
        else:
            return "[dim]Sidebar toggle not available.[/dim]"
