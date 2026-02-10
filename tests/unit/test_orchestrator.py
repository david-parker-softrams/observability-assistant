"""Tests for LLM Orchestrator."""

from unittest.mock import AsyncMock, Mock

import pytest

from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator, OrchestratorError
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    return settings


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    provider = AsyncMock()
    return provider


@pytest.fixture
def mock_sanitizer():
    """Create mock sanitizer."""
    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.enabled = True
    return sanitizer


@pytest.fixture
def mock_tool_registry():
    """Create mock tool registry."""
    registry = Mock(spec=ToolRegistry)
    registry.to_function_definitions = Mock(return_value=[])
    registry.execute = AsyncMock()
    return registry


@pytest.fixture
def orchestrator(mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings):
    """Create orchestrator instance."""
    return LLMOrchestrator(
        llm_provider=mock_llm_provider,
        tool_registry=mock_tool_registry,
        sanitizer=mock_sanitizer,
        settings=mock_settings,
    )


class TestLLMOrchestrator:
    """Tests for LLMOrchestrator."""

    def test_initialization(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test orchestrator initialization."""
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
        )

        assert orchestrator.llm_provider is mock_llm_provider
        assert orchestrator.tool_registry is mock_tool_registry
        assert len(orchestrator.conversation_history) == 0

    def test_get_system_prompt(self, orchestrator):
        """Test system prompt generation."""
        prompt = orchestrator._get_system_prompt()

        assert "observability assistant" in prompt
        assert "CloudWatch" in prompt
        assert "Tool Usage" in prompt
        assert "Response Style" in prompt

    @pytest.mark.asyncio
    async def test_chat_simple_response(self, orchestrator, mock_llm_provider):
        """Test simple chat without tool calls."""
        # Mock LLM response without tool calls
        response = LLMResponse(content="Hello! I can help you with logs.", finish_reason="stop")
        mock_llm_provider.chat.return_value = response

        result = await orchestrator.chat("Hello")

        assert result == "Hello! I can help you with logs."
        assert len(orchestrator.conversation_history) == 2  # user + assistant
        assert orchestrator.conversation_history[0]["role"] == "user"
        assert orchestrator.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_chat_with_tool_call(self, orchestrator, mock_llm_provider, mock_tool_registry):
        """Test chat with single tool call."""
        # First response: LLM wants to call a tool
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "list_log_groups",
                        "arguments": '{"prefix": "/aws/lambda/"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

        # Second response: LLM processes tool result and gives final answer
        final_response = LLMResponse(
            content="I found 3 Lambda function log groups.", finish_reason="stop"
        )

        mock_llm_provider.chat.side_effect = [tool_call_response, final_response]

        # Mock tool execution
        mock_tool_registry.execute.return_value = {
            "success": True,
            "log_groups": [
                {"name": "/aws/lambda/function1"},
                {"name": "/aws/lambda/function2"},
                {"name": "/aws/lambda/function3"},
            ],
            "count": 3,
        }

        result = await orchestrator.chat("List Lambda function log groups")

        assert result == "I found 3 Lambda function log groups."
        assert mock_tool_registry.execute.called
        assert mock_tool_registry.execute.call_args[0][0] == "list_log_groups"

        # Verify conversation history includes tool call and result
        assert len(orchestrator.conversation_history) >= 3  # user, assistant, tool, assistant

    @pytest.mark.asyncio
    async def test_chat_multiple_tool_calls(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test chat with multiple tool calls."""
        # Response with two tool calls
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "tool1", "arguments": "{}"},
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "tool2", "arguments": "{}"},
                },
            ],
            finish_reason="tool_calls",
        )

        final_response = LLMResponse(content="Done!", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call_response, final_response]
        mock_tool_registry.execute.return_value = {"success": True}

        result = await orchestrator.chat("Do something")

        assert result == "Done!"
        # Should have executed both tools
        assert mock_tool_registry.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_max_iterations(self, orchestrator, mock_llm_provider, mock_tool_registry):
        """Test that max iterations prevents infinite loops."""
        # LLM always returns tool calls (infinite loop scenario)
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "some_tool", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        mock_llm_provider.chat.return_value = tool_call_response
        # Tool returns a result (not the issue)
        mock_tool_registry.execute.return_value = {"success": True}

        result = await orchestrator.chat("This will loop forever")

        assert "Maximum tool iterations" in result
        assert mock_llm_provider.chat.call_count == orchestrator.MAX_TOOL_ITERATIONS

    @pytest.mark.asyncio
    async def test_chat_tool_execution_error(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test handling of tool execution errors."""
        # LLM requests a tool
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "failing_tool", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response after tool error
        final_response = LLMResponse(content="Sorry, the tool failed.", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call_response, final_response]

        # Tool execution raises exception
        mock_tool_registry.execute.side_effect = Exception("Tool failed")

        result = await orchestrator.chat("Use failing tool")

        # Should handle the error gracefully and continue
        assert "Sorry, the tool failed." == result

    @pytest.mark.asyncio
    async def test_chat_invalid_tool_arguments(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test handling of invalid JSON in tool arguments."""
        # LLM returns invalid JSON in arguments
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "some_tool",
                        "arguments": "not valid json {{{",
                    },
                }
            ],
            finish_reason="tool_calls",
        )

        final_response = LLMResponse(content="I'll try a different approach.", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call_response, final_response]

        result = await orchestrator.chat("Do something")

        assert result == "I'll try a different approach."
        # Should not have executed the tool due to JSON error
        mock_tool_registry.execute.assert_not_called()

    def test_clear_history(self, orchestrator):
        """Test clearing conversation history."""
        orchestrator.conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        orchestrator.clear_history()

        assert len(orchestrator.conversation_history) == 0

    def test_get_history(self, orchestrator):
        """Test getting conversation history."""
        orchestrator.conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        history = orchestrator.get_history()

        assert len(history) == 2
        assert history[0]["content"] == "Hello"
        # Verify it returns a copy, not the original
        assert history is not orchestrator.conversation_history

    @pytest.mark.asyncio
    async def test_chat_stream_simple(self, orchestrator, mock_llm_provider):
        """Test streaming chat without tool calls."""
        response = LLMResponse(content="Hello world!", finish_reason="stop")
        mock_llm_provider.chat.return_value = response

        tokens = []
        async for token in orchestrator.chat_stream("Hello"):
            tokens.append(token)

        # Should stream the response character by character
        assert "".join(tokens) == "Hello world!"
        assert len(tokens) > 1  # Multiple tokens/characters

    @pytest.mark.asyncio
    async def test_chat_stream_with_tool_calls(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test streaming chat with tool calls."""
        # First: tool call (non-streaming)
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "list_log_groups", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Second: final response (streamed)
        final_response = LLMResponse(content="Done!", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call_response, final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 5}

        tokens = []
        async for token in orchestrator.chat_stream("List log groups"):
            tokens.append(token)

        assert "".join(tokens) == "Done!"
        assert mock_tool_registry.execute.called
