"""Tests for command handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.commands import CommandHandler


@pytest.fixture
def mock_orchestrator() -> LLMOrchestrator:
    """Create a mock orchestrator."""
    orchestrator = MagicMock(spec=LLMOrchestrator)
    orchestrator.clear_history = MagicMock()
    return orchestrator  # type: ignore


@pytest.fixture
def mock_cache_manager() -> CacheManager:
    """Create a mock cache manager."""
    cache_manager = MagicMock(spec=CacheManager)
    cache_manager.get_statistics = AsyncMock(
        return_value={
            "total_entries": 10,
            "total_size_bytes": 1024 * 1024,  # 1 MB
            "total_hits": 50,
            "total_misses": 10,
        }
    )
    cache_manager.clear = AsyncMock(return_value=10)
    cache_manager.CACHE_MAX_SIZE_MB = 500
    cache_manager.CACHE_MAX_ENTRIES = 10000
    return cache_manager  # type: ignore


@pytest.fixture
def mock_settings() -> LogAISettings:
    """Create a mock settings object."""
    settings = MagicMock(spec=LogAISettings)
    settings.llm_provider = "anthropic"
    settings.current_llm_model = "claude-3-5-sonnet-20241022"
    settings.aws_region = "us-east-1"
    settings.pii_sanitization_enabled = True
    settings.cache_dir = "/tmp/.logai/cache"
    settings.cache_max_size_mb = 500
    settings.cache_ttl_seconds = 86400
    return settings  # type: ignore


@pytest.fixture
def command_handler(
    mock_orchestrator: LLMOrchestrator,
    mock_cache_manager: CacheManager,
    mock_settings: LogAISettings,
) -> CommandHandler:
    """Create a command handler instance."""
    return CommandHandler(mock_orchestrator, mock_cache_manager, mock_settings)


class TestCommandHandler:
    """Tests for CommandHandler class."""

    def test_is_command_true(self, command_handler: CommandHandler) -> None:
        """Test that is_command returns True for commands."""
        assert command_handler.is_command("/help")
        assert command_handler.is_command("/clear")
        assert command_handler.is_command("  /cache status  ")

    def test_is_command_false(self, command_handler: CommandHandler) -> None:
        """Test that is_command returns False for non-commands."""
        assert not command_handler.is_command("Hello")
        assert not command_handler.is_command("What are the errors?")
        assert not command_handler.is_command("")

    @pytest.mark.asyncio
    async def test_handle_help_command(self, command_handler: CommandHandler) -> None:
        """Test handling /help command."""
        response = await command_handler.handle_command("/help")
        assert "Available Commands" in response
        assert "/help" in response
        assert "/clear" in response
        assert "/cache" in response

    @pytest.mark.asyncio
    async def test_handle_clear_command(
        self, command_handler: CommandHandler, mock_orchestrator: LLMOrchestrator
    ) -> None:
        """Test handling /clear command."""
        response = await command_handler.handle_command("/clear")
        assert "cleared" in response.lower()
        mock_orchestrator.clear_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_cache_status_command(self, command_handler: CommandHandler) -> None:
        """Test handling /cache status command."""
        response = await command_handler.handle_command("/cache status")
        assert "Cache Statistics" in response
        assert "Total Entries: 10" in response
        assert "1.00 MB" in response
        assert "Cache Hits: 50" in response
        assert "Cache Misses: 10" in response

    @pytest.mark.asyncio
    async def test_handle_cache_clear_command(
        self, command_handler: CommandHandler, mock_cache_manager: CacheManager
    ) -> None:
        """Test handling /cache clear command."""
        response = await command_handler.handle_command("/cache clear")
        assert "cleared" in response.lower()
        assert "10 entries" in response.lower()
        mock_cache_manager.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_model_command(self, command_handler: CommandHandler) -> None:
        """Test handling /model command."""
        response = await command_handler.handle_command("/model")
        assert "LLM Configuration" in response
        assert "anthropic" in response
        assert "claude-3-5-sonnet-20241022" in response

    @pytest.mark.asyncio
    async def test_handle_config_command(self, command_handler: CommandHandler) -> None:
        """Test handling /config command."""
        response = await command_handler.handle_command("/config")
        assert "Current Configuration" in response
        assert "anthropic" in response
        assert "us-east-1" in response
        assert "Enabled" in response

    @pytest.mark.asyncio
    async def test_handle_quit_command(self, command_handler: CommandHandler) -> None:
        """Test handling /quit command."""
        response = await command_handler.handle_command("/quit")
        assert "Ctrl+C" in response or "Ctrl+Q" in response

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self, command_handler: CommandHandler) -> None:
        """Test handling unknown command."""
        response = await command_handler.handle_command("/unknown")
        assert "Unknown command" in response
        assert "/help" in response
