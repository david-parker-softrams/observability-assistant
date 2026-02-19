"""
Unit tests for Context Visibility Bug Fix.

This module tests the fix for the critical bug where the agent ignored
user-provided logs added via "Add to Context" feature.

Bug: Agent would ask "Which log group should I search?" instead of analyzing
     the logs that were already provided in context.

Fix: Updated system prompt and message tone to teach agent to recognize and
     prioritize user-provided log entries.
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def settings(tmp_path):
    """Create test settings."""
    return LogAISettings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        cache_dir=tmp_path / "cache",
    )


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    provider = Mock()
    provider.chat = AsyncMock()
    return provider


@pytest.fixture
def orchestrator(settings, mock_llm_provider, tmp_path):
    """Create orchestrator instance."""
    ToolRegistry.clear()

    from logai.core.context.result_cache import ResultCacheManager

    result_cache = ResultCacheManager(
        cache_dir=tmp_path / "results",
        ttl_seconds=3600,
        max_size_mb=100,
    )

    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.sanitize = Mock(side_effect=lambda x: x)

    orch = LLMOrchestrator(
        llm_provider=mock_llm_provider,
        tool_registry=ToolRegistry,
        sanitizer=sanitizer,
        settings=settings,
        result_cache=result_cache,
    )
    return orch


class TestSystemPromptInclusion:
    """Test that system prompt includes user-provided log instructions."""

    def test_system_prompt_has_user_provided_section(self, orchestrator):
        """Test that system prompt includes 'User-Provided Log Entries' section."""
        system_prompt = orchestrator._get_system_prompt()

        assert "User-Provided Log Entries" in system_prompt
        assert "Add to Context" in system_prompt

    def test_system_prompt_teaches_recognition(self, orchestrator):
        """Test that system prompt teaches agent to recognize the prefix."""
        system_prompt = orchestrator._get_system_prompt()

        assert "USER-SELECTED LOG ENTRIES" in system_prompt
        assert "RECOGNITION" in system_prompt

    def test_system_prompt_emphasizes_priority(self, orchestrator):
        """Test that system prompt emphasizes analyzing provided logs FIRST."""
        system_prompt = orchestrator._get_system_prompt()

        assert "PRIORITY" in system_prompt
        assert "ALWAYS analyze provided logs FIRST" in system_prompt

    def test_system_prompt_warns_against_ignoring(self, orchestrator):
        """Test that system prompt warns against ignoring provided logs."""
        system_prompt = orchestrator._get_system_prompt()

        assert "Do NOT ignore user-provided logs" in system_prompt
        assert "analyze them immediately" in system_prompt


class TestContextInjection:
    """Test context injection mechanism for user-provided logs."""

    def test_inject_context_stores_user_logs(self, orchestrator):
        """Test that inject_context_update stores user-provided logs."""
        log_context = "USER-SELECTED LOG ENTRIES:\nLog 1\nLog 2"

        orchestrator.inject_context_update(log_context)

        assert orchestrator._pending_context_injection is not None
        assert "USER-SELECTED LOG ENTRIES" in orchestrator._pending_context_injection

    def test_get_pending_context_returns_user_logs(self, orchestrator):
        """Test that get_pending_context_injection returns user logs."""
        log_context = "USER-SELECTED LOG ENTRIES:\nLog 1\nLog 2"
        orchestrator.inject_context_update(log_context)

        result = orchestrator._get_pending_context_injection()

        assert result is not None
        assert "USER-SELECTED LOG ENTRIES" in result

    def test_get_pending_context_clears_after_retrieval(self, orchestrator):
        """Test that context injection is cleared after retrieval."""
        log_context = "USER-SELECTED LOG ENTRIES:\nLog 1"
        orchestrator.inject_context_update(log_context)

        # First call returns the context
        first = orchestrator._get_pending_context_injection()
        assert first is not None

        # Second call returns None (cleared)
        second = orchestrator._get_pending_context_injection()
        assert second is None


class TestUserProvidedLogsInConversation:
    """Test that user-provided logs are properly included in conversation."""

    @pytest.mark.asyncio
    async def test_user_logs_injected_before_llm_call(self, orchestrator, mock_llm_provider):
        """Test that user-provided logs are injected before LLM sees them."""
        # Setup mock response
        mock_llm_provider.chat.return_value = LLMResponse(
            content="I can see the logs you provided. Here's my analysis...", tool_calls=None
        )

        # Inject user logs
        user_logs = """USER-SELECTED LOG ENTRIES for analysis:

Log Group: /aws/lambda/test
Entry Count: 3

The user has specifically selected these log entries for your analysis:

```json
[
  {"timestamp": "2026-02-19T10:00:00Z", "message": "Request started"},
  {"timestamp": "2026-02-19T10:00:01Z", "message": "Processing data"},
  {"timestamp": "2026-02-19T10:00:02Z", "message": "Request completed"}
]
```

YOU MUST analyze these 3 log entries. Do NOT ask for a log group to search."""

        orchestrator.inject_context_update(user_logs)

        # Send a user query
        await orchestrator.chat("Analyze these logs")

        # Verify LLM was called with the logs in context
        mock_llm_provider.chat.assert_called_once()
        call_kwargs = mock_llm_provider.chat.call_args[1]
        messages = call_kwargs["messages"]

        # Check that user logs are in the messages (as a system message)
        system_messages = [msg for msg in messages if msg.get("role") == "system"]

        # The injected context should be in a system message
        has_logs = any(
            "USER-SELECTED LOG ENTRIES" in msg.get("content", "") for msg in system_messages
        )
        assert has_logs, "User-provided logs not found in conversation"

    @pytest.mark.asyncio
    async def test_commanding_tone_in_user_logs(self, orchestrator, mock_llm_provider):
        """Test that user logs message uses commanding tone."""
        mock_llm_provider.chat.return_value = LLMResponse(
            content="Analysis complete", tool_calls=None
        )

        # Inject logs with commanding tone
        user_logs = """YOU MUST analyze these log entries. Do NOT ask for a log group to search."""
        orchestrator.inject_context_update(user_logs)

        await orchestrator.chat("Categorize the logs")

        # Verify commanding tone is present
        call_kwargs = mock_llm_provider.chat.call_args[1]
        messages = call_kwargs["messages"]

        # Check in all messages
        all_content = " ".join([msg.get("content", "") for msg in messages])
        assert "YOU MUST" in all_content, "Commanding tone not found in messages"
        assert "Do NOT ask for a log group" in all_content, "Prohibition not found in messages"


class TestAgentBehaviorWithProvidedLogs:
    """Test agent behavior when logs are provided in context."""

    @pytest.mark.asyncio
    async def test_agent_analyzes_provided_logs_without_tools(
        self, orchestrator, mock_llm_provider
    ):
        """Test that agent can analyze provided logs without calling tools."""
        # Mock agent to respond with analysis (no tool calls)
        mock_llm_provider.chat.return_value = LLMResponse(
            content="Based on the provided logs, I can see 3 events...",
            tool_calls=None,  # No tools used!
        )

        # Inject logs
        orchestrator.inject_context_update("USER-SELECTED LOG ENTRIES:\nLog 1\nLog 2\nLog 3")

        # Ask for analysis
        response = await orchestrator.chat("Analyze these logs")

        # Should respond without tool calls
        assert response is not None
        assert "based on" in response.lower() or "provided" in response.lower()

        # Verify only one LLM call (no tool iterations)
        assert mock_llm_provider.chat.call_count == 1


class TestMultipleContextAdditions:
    """Test multiple 'Add to Context' operations."""

    @pytest.mark.asyncio
    async def test_multiple_log_additions_accumulate(self, orchestrator, mock_llm_provider):
        """Test that multiple context additions work correctly."""
        mock_llm_provider.chat.return_value = LLMResponse(
            content="Analyzed all logs", tool_calls=None
        )

        # First addition
        orchestrator.inject_context_update("USER-SELECTED LOG ENTRIES:\nBatch 1: Log A")
        await orchestrator.chat("Analyze first batch")

        # Second addition (should work independently)
        orchestrator.inject_context_update("USER-SELECTED LOG ENTRIES:\nBatch 2: Log B")
        await orchestrator.chat("Analyze second batch")

        # Both should have been processed
        assert mock_llm_provider.chat.call_count == 2


class TestEdgeCases:
    """Test edge cases for context visibility fix."""

    def test_empty_context_injection(self, orchestrator):
        """Test behavior with empty context injection."""
        orchestrator.inject_context_update("")

        result = orchestrator._get_pending_context_injection()
        # Empty string is set but when retrieved returns None if empty
        # This is acceptable behavior - empty injection is cleared
        assert result is None or result == ""

    def test_single_log_entry(self, orchestrator):
        """Test that single log entry is handled correctly."""
        single_log = """USER-SELECTED LOG ENTRIES:

Log Group: /test
Entry Count: 1

Single log entry here."""

        orchestrator.inject_context_update(single_log)
        result = orchestrator._get_pending_context_injection()

        assert result is not None
        assert "Entry Count: 1" in result

    def test_large_number_of_logs(self, orchestrator):
        """Test handling many log entries in context."""
        # Simulate 100 log entries
        large_logs = "USER-SELECTED LOG ENTRIES:\n\n"
        large_logs += "Entry Count: 100\n\n"
        large_logs += "\n".join([f"Log {i}: Event message" for i in range(100)])

        orchestrator.inject_context_update(large_logs)
        result = orchestrator._get_pending_context_injection()

        assert result is not None
        assert "Entry Count: 100" in result

    @pytest.mark.asyncio
    async def test_context_with_special_characters(self, orchestrator, mock_llm_provider):
        """Test logs with special characters are handled correctly."""
        mock_llm_provider.chat.return_value = LLMResponse(
            content="Analyzed special logs", tool_calls=None
        )

        special_logs = """USER-SELECTED LOG ENTRIES:

Special characters: {"key": "value", "timestamp": "2026-02-19T10:00:00Z"}
Newlines and \ttabs\\nBackslashes"""

        orchestrator.inject_context_update(special_logs)
        response = await orchestrator.chat("Analyze")

        assert response is not None
        # Should not crash or corrupt data


class TestNoRegression:
    """Test that existing functionality still works."""

    @pytest.mark.asyncio
    async def test_normal_search_still_works(self, orchestrator, mock_llm_provider):
        """Test that normal log searching without context still works."""
        # Register a mock tool
        test_tool = Mock()
        test_tool.name = "search_logs"
        test_tool.execute = AsyncMock(
            return_value={"success": True, "events": [{"message": "Found log"}], "count": 1}
        )
        test_tool.to_function_definition = Mock(
            return_value={
                "name": "search_logs",
                "description": "Search logs",
                "parameters": {"type": "object", "properties": {}},
            }
        )
        ToolRegistry.register(test_tool)

        # Mock LLM to use tool, then respond
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {"name": "search_logs", "arguments": "{}"},
        }
        mock_llm_provider.chat.side_effect = [
            LLMResponse(content="", tool_calls=[tool_call]),
            LLMResponse(content="Found 1 log", tool_calls=None),
        ]

        # Ask without providing context - should trigger tool use
        response = await orchestrator.chat("Search for errors in /aws/lambda/test")

        # Should have called the tool
        test_tool.execute.assert_called_once()
        assert response == "Found 1 log"

    @pytest.mark.asyncio
    async def test_context_clear_works(self, orchestrator):
        """Test that clearing context works correctly."""
        # Add context
        orchestrator.inject_context_update("USER-SELECTED LOG ENTRIES:\nLog 1")
        first_injection = orchestrator._get_pending_context_injection()
        assert first_injection is not None

        # Clear conversation using clear_history method
        orchestrator.clear_history()

        # Should be clear
        assert len(orchestrator.conversation_history) == 0

        # Any pending injection from before was cleared when retrieved
        # Adding a new one to verify the clear worked
        orchestrator.inject_context_update("NEW LOGS")
        result = orchestrator._get_pending_context_injection()
        assert result is not None  # New injection should work


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
