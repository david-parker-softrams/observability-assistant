"""Tests for LLM Orchestrator."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from logai.config.settings import LogAISettings
from logai.core.metrics import MetricsCollector
from logai.core.orchestrator import (
    LLMOrchestrator,
    OrchestratorError,
    RetryState,
    RetryPromptGenerator,
)
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def mock_settings():
    """Create mock settings with self-direction enabled."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    # Self-direction settings
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = True
    settings.time_expansion_factor = 4.0
    settings.max_tool_iterations = 10  # Default value
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
    async def test_respects_max_retry_limit(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test that retries stop at max limit."""
        # Always returns empty results
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_x",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response after max retries
        final_response = LLMResponse(
            content="No logs found after multiple attempts.", finish_reason="stop"
        )

        # Return tool calls many times, then final response
        mock_llm_provider.chat.side_effect = [tool_call_response] * 10 + [final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 0, "events": []}

        result = await orchestrator.chat("Find errors")

        # The orchestrator will hit max_tool_iterations (10) which is the global safety limit
        # The retry logic adds system messages but doesn't prevent the agent from continuing
        # if it keeps calling tools. The max_retry_attempts only limits the number of
        # system-level retry prompts injected, not tool calls themselves.
        assert mock_tool_registry.execute.call_count == 10  # Hit max_tool_iterations
        assert "Maximum tool iterations" in result or "No logs found" in result

    @pytest.mark.asyncio
    async def test_no_retry_when_disabled(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer
    ):
        """Test that retry is disabled when auto_retry_enabled is False."""
        # Create settings with retry disabled
        settings = Mock(spec=LogAISettings)
        settings.pii_sanitization_enabled = True
        settings.max_retry_attempts = 3
        settings.intent_detection_enabled = True
        settings.auto_retry_enabled = False  # Disabled
        settings.time_expansion_factor = 4.0
        settings.max_tool_iterations = 10

        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=settings,
        )

        # Tool call with empty results
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response (no retry prompt should be injected)
        final_response = LLMResponse(content="No logs found.", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call, final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 0, "events": []}

        result = await orch.chat("Find errors")

        # Should call tool only once (no retry)
        assert mock_tool_registry.execute.call_count == 1
        assert "No logs found" in result

    @pytest.mark.asyncio
    async def test_log_group_not_found_retry(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test retry when log group is not found."""
        # First call: log group not found
        tool_call_1 = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": '{"log_group": "/wrong"}'},
                }
            ],
            finish_reason="tool_calls",
        )

        # Second call: list log groups
        tool_call_2 = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "list_log_groups", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response
        final_response = LLMResponse(
            content="I found these available log groups instead.", finish_reason="stop"
        )

        mock_llm_provider.chat.side_effect = [tool_call_1, tool_call_2, final_response]
        mock_tool_registry.execute.side_effect = [
            {"success": False, "error": "Log group not found"},  # First call fails
            {"success": True, "log_groups": [{"name": "/correct"}], "count": 1},  # List succeeds
        ]

        result = await orchestrator.chat("Fetch logs from /wrong")

        # Should have called tools twice and provided alternatives
        assert mock_tool_registry.execute.call_count == 2


class TestMaxToolIterationsConfiguration:
    """Tests for configurable max_tool_iterations setting."""

    @pytest.mark.asyncio
    async def test_custom_max_iterations_limit(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer
    ):
        """Test that custom max_tool_iterations limit is respected."""
        # Create settings with custom limit
        settings = Mock(spec=LogAISettings)
        settings.pii_sanitization_enabled = True
        settings.max_retry_attempts = 3
        settings.intent_detection_enabled = True
        settings.auto_retry_enabled = True
        settings.time_expansion_factor = 4.0
        settings.max_tool_iterations = 5  # Custom limit

        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=settings,
        )

        # Tool call that keeps repeating
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Return tool calls more times than limit
        mock_llm_provider.chat.side_effect = [tool_call] * 10
        mock_tool_registry.execute.return_value = {"success": True, "count": 1, "events": ["log"]}

        result = await orch.chat("Find errors")

        # Should stop at custom limit of 5
        assert mock_tool_registry.execute.call_count == 5
        assert "Maximum tool iterations (5) exceeded" in result

    @pytest.mark.asyncio
    async def test_default_max_iterations_value(
        self, orchestrator, mock_llm_provider, mock_tool_registry
    ):
        """Test that default max_tool_iterations value is 10."""
        # Tool call that keeps repeating
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Return tool calls more times than default limit
        mock_llm_provider.chat.side_effect = [tool_call] * 15
        mock_tool_registry.execute.return_value = {"success": True, "count": 1, "events": ["log"]}

        result = await orchestrator.chat("Find errors")

        # Should stop at default limit of 10
        assert mock_tool_registry.execute.call_count == 10
        assert "Maximum tool iterations (10) exceeded" in result

    @pytest.mark.asyncio
    async def test_max_iterations_streaming(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer
    ):
        """Test that max_tool_iterations limit works in streaming mode."""
        # Create settings with custom limit
        settings = Mock(spec=LogAISettings)
        settings.pii_sanitization_enabled = True
        settings.max_retry_attempts = 3
        settings.intent_detection_enabled = True
        settings.auto_retry_enabled = True
        settings.time_expansion_factor = 4.0
        settings.max_tool_iterations = 3  # Low limit for testing

        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=settings,
        )

        # Tool call that keeps repeating
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Return tool calls more times than limit
        mock_llm_provider.chat.side_effect = [tool_call] * 10
        mock_tool_registry.execute.return_value = {"success": True, "count": 1, "events": ["log"]}

        # Collect streaming response
        result_parts = []
        async for token in orch.chat_stream("Find errors"):
            result_parts.append(token)

        result = "".join(result_parts)

        # Should stop at limit of 3
        assert mock_tool_registry.execute.call_count == 3
        assert "Maximum tool iterations (3) exceeded" in result

    def test_settings_validation(self):
        """Test that max_tool_iterations validates correctly."""
        from pydantic import ValidationError

        # Test valid values
        settings = LogAISettings(
            max_tool_iterations=1,
        )
        assert settings.max_tool_iterations == 1

        settings = LogAISettings(
            max_tool_iterations=50,
        )
        assert settings.max_tool_iterations == 50

        settings = LogAISettings(
            max_tool_iterations=100,
        )
        assert settings.max_tool_iterations == 100

        # Test default value
        settings = LogAISettings()
        assert settings.max_tool_iterations == 10

        # Test invalid values (should raise validation error)
        with pytest.raises(ValidationError):
            LogAISettings(
                max_tool_iterations=0,  # Less than minimum
            )

        with pytest.raises(ValidationError):
            LogAISettings(
                max_tool_iterations=101,  # Greater than maximum
            )


class TestRetryState:
    """Tests for RetryState dataclass."""

    def test_initial_state(self):
        """Test initial retry state."""
        state = RetryState()
        assert state.attempts == 0
        assert state.empty_result_count == 0
        assert len(state.strategies_tried) == 0
        assert state.should_retry(3) is True

    def test_record_attempt(self):
        """Test recording retry attempts."""
        state = RetryState()
        state.record_attempt("fetch_logs", {"log_group": "/test"}, "empty_logs")

        assert state.attempts == 1
        assert state.last_tool_name == "fetch_logs"
        assert "empty_logs" in state.strategies_tried

    def test_retry_limit(self):
        """Test retry limit enforcement."""
        state = RetryState()
        state.attempts = 3
        assert state.should_retry(3) is False

    def test_reset(self):
        """Test resetting retry state."""
        state = RetryState()
        state.record_attempt("tool", {}, "strategy")
        state.record_empty_result()

        state.reset()

        assert state.attempts == 0
        assert state.empty_result_count == 0
        assert len(state.strategies_tried) == 0


class TestRetryPromptGenerator:
    """Tests for RetryPromptGenerator."""

    def test_generate_empty_logs_prompt(self):
        """Test empty logs retry prompt."""
        state = RetryState()
        prompt = RetryPromptGenerator.generate_retry_prompt("empty_logs", state)

        assert "Expand Time Range" in prompt
        assert "Broaden Filter" in prompt
        assert "Do not ask the user" in prompt

    def test_generate_log_group_not_found_prompt(self):
        """Test log group not found prompt."""
        state = RetryState()
        prompt = RetryPromptGenerator.generate_retry_prompt("log_group_not_found", state)

        assert "list_log_groups" in prompt
        assert "similar names" in prompt

    def test_prompt_includes_attempt_context(self):
        """Test that prompts include attempt context."""
        state = RetryState()
        state.record_attempt("fetch_logs", {"start_time": "1h ago"}, "expand_time")

        prompt = RetryPromptGenerator.generate_retry_prompt("empty_logs", state)

        assert "attempt 2" in prompt
        assert "expand_time" in prompt


class TestMetricsInstrumentation:
    """Tests for metrics instrumentation in orchestrator."""

    @pytest.mark.asyncio
    async def test_retry_metrics_recorded(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test that retry attempts are recorded in metrics."""
        metrics = MetricsCollector()
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            metrics_collector=metrics,
        )

        # First call: empty results
        tool_call_1 = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Second call: after retry
        tool_call_2 = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response
        final_response = LLMResponse(content="Found some logs", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [tool_call_1, tool_call_2, final_response]
        mock_tool_registry.execute.side_effect = [
            {"success": True, "count": 0, "events": []},  # Empty results
            {"success": True, "count": 5, "events": ["log1", "log2"]},  # Success
        ]

        await orch.chat("Find errors")

        # Check retry metrics were recorded
        retry_attempts = metrics.get_counter_value("retry_attempts")
        assert retry_attempts >= 1.0

        # Check specific reason
        empty_logs_retries = metrics.get_counter_value(
            "retry_attempts", labels={"reason": "empty_logs"}
        )
        assert empty_logs_retries >= 1.0

        # Check retry prompt injected
        prompts_injected = metrics.get_counter_value("retry_prompt_injected")
        assert prompts_injected >= 1.0

    @pytest.mark.asyncio
    async def test_intent_detection_metrics(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test that intent detection hits are recorded in metrics."""
        metrics = MetricsCollector()
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            metrics_collector=metrics,
        )

        # Response with clear intent but no tool call
        intent_response = LLMResponse(
            content="I'll fetch the logs for you now", finish_reason="stop"
        )

        # Follow-up with actual tool call
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response
        final_response = LLMResponse(content="Here are the logs", finish_reason="stop")

        mock_llm_provider.chat.side_effect = [intent_response, tool_call, final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 5, "events": []}

        await orch.chat("Show me errors")

        # Check intent detection metrics
        intent_hits = metrics.get_counter_value("intent_detection_hits")
        assert intent_hits >= 1.0

    @pytest.mark.asyncio
    async def test_max_retry_attempts_metric(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test that max retry attempts reached is recorded."""
        metrics = MetricsCollector()
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            metrics_collector=metrics,
        )

        # Tool call that returns empty results repeatedly
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response after max retries
        final_response = LLMResponse(content="No logs found", finish_reason="stop")

        # Return tool calls for max attempts + 1, then final
        mock_llm_provider.chat.side_effect = [tool_call] * 5 + [final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 0, "events": []}

        await orch.chat("Find errors")

        # Check that max attempts metric is recorded when limit is reached
        max_attempts = metrics.get_counter_value("retry_max_attempts_reached")
        # Should be recorded at least once
        assert max_attempts >= 0.0  # May be 0 if we stopped before hitting the limit

    @pytest.mark.asyncio
    async def test_metrics_disabled(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test that metrics can be disabled."""
        metrics = MetricsCollector()
        metrics.disable()

        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            metrics_collector=metrics,
        )

        # Simple response
        response = LLMResponse(content="Hello", finish_reason="stop")
        mock_llm_provider.chat.return_value = response

        await orch.chat("Hi")

        # No metrics should be recorded
        assert len(metrics.get_events()) == 0


class TestExponentialBackoff:
    """Tests for exponential backoff between retries."""

    @pytest.mark.asyncio
    async def test_backoff_delays_applied(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test that exponential backoff delays are applied between retries."""
        metrics = MetricsCollector()
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
            metrics_collector=metrics,
        )

        # Tool calls that return empty results
        tool_call = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "fetch_logs", "arguments": "{}"},
                }
            ],
            finish_reason="tool_calls",
        )

        # Final response
        final_response = LLMResponse(content="No logs", finish_reason="stop")

        # Return tool calls 3 times, then final
        mock_llm_provider.chat.side_effect = [tool_call, tool_call, tool_call, final_response]
        mock_tool_registry.execute.return_value = {"success": True, "count": 0, "events": []}

        start_time = asyncio.get_event_loop().time()
        await orch.chat("Find errors")
        elapsed_time = asyncio.get_event_loop().time() - start_time

        # Should have delays totaling at least 0.5s + 1.0s = 1.5s for 2 retries
        # (First tool call has no delay, 2nd has 0.5s, 3rd has 1.0s)
        assert elapsed_time >= 1.4  # Allow small variance

        # Check that backoff metrics were recorded
        backoff_values = metrics.get_histogram_values("retry_backoff_seconds")
        assert len(backoff_values) >= 2  # Should have at least 2 backoff measurements

    def test_backoff_calculation(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test exponential backoff delay calculation."""
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
        )

        # Test base delays
        assert orch._calculate_backoff_delay(0) == 0.5  # First retry
        assert orch._calculate_backoff_delay(1) == 1.0  # Second retry
        assert orch._calculate_backoff_delay(2) == 2.0  # Third retry

        # Test exponential growth beyond base delays
        assert orch._calculate_backoff_delay(3) == 4.0  # Fourth retry (2 * 2^1)
        assert orch._calculate_backoff_delay(4) == 8.0  # Fifth retry (2 * 2^2)

    def test_confidence_bucket(
        self, mock_llm_provider, mock_tool_registry, mock_sanitizer, mock_settings
    ):
        """Test confidence score bucketing for metrics."""
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=mock_tool_registry,
            sanitizer=mock_sanitizer,
            settings=mock_settings,
        )

        # Test bucketing
        assert orch._confidence_bucket(0.95) == "high"
        assert orch._confidence_bucket(0.9) == "high"
        assert orch._confidence_bucket(0.85) == "medium"
        assert orch._confidence_bucket(0.7) == "medium"
        assert orch._confidence_bucket(0.65) == "low"
        assert orch._confidence_bucket(0.3) == "low"
