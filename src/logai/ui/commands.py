"""Command handler for special slash commands."""

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator


class CommandHandler:
    """Handles special slash commands in the chat."""

    def __init__(
        self,
        orchestrator: LLMOrchestrator,
        cache_manager: CacheManager,
        settings: LogAISettings,
    ) -> None:
        """
        Initialize command handler.

        Args:
            orchestrator: LLM orchestrator instance
            cache_manager: Cache manager instance
            settings: Application settings
        """
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.settings = settings

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
        else:
            return f"Unknown command: {cmd}\nUse /help to see available commands."

    def _show_help(self) -> str:
        """Show help message with available commands."""
        return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)

[bold]Usage Tips:[/bold]
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
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
