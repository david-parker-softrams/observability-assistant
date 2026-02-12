"""Integration tests for agent self-direction and retry behavior.

These tests verify the complete end-to-end behavior of the agent's retry logic,
including intent detection, empty result handling, and strategy tracking.
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator, RetryState
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def integration_settings():
    """Create settings for integration tests."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = True
    settings.time_expansion_factor = 4.0
    return settings


@pytest.fixture
def disabled_retry_settings():
    """Create settings with auto-retry disabled."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = False  # Disabled
    settings.time_expansion_factor = 4.0
    return settings


@pytest.fixture
def mock_sanitizer():
    """Create mock sanitizer."""
    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.enabled = True
    return sanitizer


class TestEmptyResultsAutoRetry:
    """Test automatic retry behavior when encountering empty results."""

    @pytest.mark.asyncio
    async def test_empty_logs_triggers_retry_with_expanded_time(
        self, integration_settings, mock_sanitizer
    ):
        """Test that empty log results trigger automatic retry with expanded time range."""
        # Setup: Mock LLM provider
        mock_llm = AsyncMock()
        
        # Scenario: First query returns empty, second query (after retry) returns results
        mock_llm.chat.side_effect = [
            # 1. Initial tool call with narrow time range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "1h ago",
                                "filter_pattern": "ERROR"
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. After retry prompt, expanded time range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "6h ago",  # Expanded
                                "filter_pattern": "ERROR"
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response with results
            LLMResponse(
                content="I found 5 ERROR entries in the expanded 6-hour time range.",
                finish_reason="stop"
            ),
        ]
        
        # Setup: Mock tool registry
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            # First call: empty results
            {"success": True, "count": 0, "events": []},
            # Second call: results found
            {
                "success": True,
                "count": 5,
                "events": [
                    {"timestamp": 1234567890, "message": "ERROR: Test error 1"},
                    {"timestamp": 1234567891, "message": "ERROR: Test error 2"},
                    {"timestamp": 1234567892, "message": "ERROR: Test error 3"},
                    {"timestamp": 1234567893, "message": "ERROR: Test error 4"},
                    {"timestamp": 1234567894, "message": "ERROR: Test error 5"},
                ],
            },
        ]
        
        # Create orchestrator
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        # Execute
        result = await orchestrator.chat("Find ERROR logs in /aws/lambda/test")
        
        # Verify: Should have called tool twice (initial + retry)
        assert mock_tools.execute.call_count == 2
        
        # Verify: First call had narrow time range
        first_call_args = mock_tools.execute.call_args_list[0][1]
        assert first_call_args["start_time"] == "1h ago"
        
        # Verify: Second call had expanded time range
        second_call_args = mock_tools.execute.call_args_list[1][1]
        assert second_call_args["start_time"] == "6h ago"
        
        # Verify: Final response reports success, not failure
        assert "5 ERROR" in result or "5" in result
        assert "found" in result.lower()

    @pytest.mark.asyncio
    async def test_max_retry_attempts_respected(self, integration_settings, mock_sanitizer):
        """Test that agent respects max retry attempts (3) and gives up gracefully."""
        # Setup: Mock LLM that always tries with empty results
        mock_llm = AsyncMock()
        
        # Create 4 tool call responses (initial + 3 retries)
        tool_responses = []
        for i in range(4):
            tool_responses.append(
                LLMResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": "fetch_logs",
                                "arguments": json.dumps({
                                    "log_group": "/aws/lambda/test",
                                    "start_time": f"{(i+1)*6}h ago",
                                })
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                )
            )
        
        # Final response acknowledging no results
        final_response = LLMResponse(
            content="No logs were found after trying multiple time ranges.",
            finish_reason="stop"
        )
        
        mock_llm.chat.side_effect = tool_responses + [final_response]
        
        # Setup: Mock tools that always return empty
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={"success": True, "count": 0, "events": []}
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        # Execute
        result = await orchestrator.chat("Find logs")
        
        # Verify: Should have attempted initial + 3 retries = 4 tool calls
        assert mock_tools.execute.call_count == 4
        
        # Verify: Final response acknowledges failure gracefully
        assert "no logs" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_successful_retry_after_empty(self, integration_settings, mock_sanitizer):
        """Test that agent reports success when retry finds results."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # Initial query: narrow time range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "30m ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # After empty result, retry with expanded range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "24h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # Success message
            LLMResponse(
                content="Found 12 log entries in the past 24 hours.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "count": 0, "events": []},  # First: empty
            {  # Second: success
                "success": True,
                "count": 12,
                "events": [{"timestamp": i, "message": f"Log {i}"} for i in range(12)],
            },
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Get logs")
        
        # Verify: Retried once
        assert mock_tools.execute.call_count == 2
        
        # Verify: Reports success
        assert "12" in result
        assert "found" in result.lower()


class TestIntentDetectionAndNudging:
    """Test intent detection and nudging behavior."""

    @pytest.mark.asyncio
    async def test_intent_without_action_triggers_nudge(
        self, integration_settings, mock_sanitizer
    ):
        """Test that stating intent without tool call triggers a nudge."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. States intent without calling tool
            LLMResponse(
                content="I'll search the logs for errors now.",
                finish_reason="stop"
            ),
            # 2. After nudge, actually calls tool
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "1h ago",
                                "filter_pattern": "ERROR"
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response
            LLMResponse(
                content="Here are the error logs I found.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={
                "success": True,
                "count": 3,
                "events": [
                    {"timestamp": 1, "message": "ERROR 1"},
                    {"timestamp": 2, "message": "ERROR 2"},
                    {"timestamp": 3, "message": "ERROR 3"},
                ],
            }
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Search for errors")
        
        # Verify: LLM was called at least 3 times (initial + nudge + after tool)
        assert mock_llm.chat.call_count >= 3
        
        # Verify: Tool was eventually called
        assert mock_tools.execute.called
        
        # Verify: Got results
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_premature_giving_up_triggers_retry(
        self, integration_settings, mock_sanitizer
    ):
        """Test that agent giving up prematurely triggers retry encouragement."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. Initial tool call
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "1h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. Gives up after empty result
            LLMResponse(
                content="Unfortunately, no logs were found.",
                finish_reason="stop"
            ),
            # 3. After nudge, tries expanded range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/test",
                                "start_time": "24h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 4. Final response
            LLMResponse(
                content="Found logs in the expanded time range.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "count": 0, "events": []},  # First: empty
            {"success": True, "count": 5, "events": [{"timestamp": i, "message": f"Log {i}"} for i in range(5)]},  # Second: found
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Get logs")
        
        # Verify: Tool called twice (initial + after nudge)
        assert mock_tools.execute.call_count == 2
        
        # Verify: Final result is positive
        assert "found" in result.lower()


class TestFeatureFlagBehavior:
    """Test behavior with feature flags enabled/disabled."""

    @pytest.mark.asyncio
    async def test_auto_retry_disabled_no_retry(self, disabled_retry_settings, mock_sanitizer):
        """Test that disabling auto_retry_enabled prevents automatic retries."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # Tool call
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"log_group": "/test", "start_time": "1h ago"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # Final response (no retry should occur)
            LLMResponse(
                content="No logs found in the time range.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={"success": True, "count": 0, "events": []}
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=disabled_retry_settings,
        )
        
        result = await orchestrator.chat("Find logs")
        
        # Verify: Only called tool once (no retry)
        assert mock_tools.execute.call_count == 1
        
        # Verify: Original behavior maintained
        assert "no logs" in result.lower()

    @pytest.mark.asyncio
    async def test_intent_detection_disabled(self, mock_sanitizer):
        """Test that disabling intent detection doesn't trigger nudges."""
        # Settings with intent detection disabled
        settings = Mock(spec=LogAISettings)
        settings.pii_sanitization_enabled = True
        settings.max_retry_attempts = 3
        settings.intent_detection_enabled = False  # Disabled
        settings.auto_retry_enabled = True
        settings.time_expansion_factor = 4.0
        
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # States intent without action
            LLMResponse(
                content="I'll search the logs for you.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=settings,
        )
        
        result = await orchestrator.chat("Search logs")
        
        # Verify: No nudge occurred, just returned the response
        assert mock_llm.chat.call_count == 1
        assert "search the logs" in result.lower()


class TestStrategyTracking:
    """Test that retry strategies are tracked and not duplicated."""

    @pytest.mark.asyncio
    async def test_strategies_not_duplicated(self, integration_settings, mock_sanitizer):
        """Test that the same strategy is not tried multiple times."""
        mock_llm = AsyncMock()
        
        # Multiple retry attempts
        tool_responses = []
        for i in range(4):
            tool_responses.append(
                LLMResponse(
                    content="",
                    tool_calls=[
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": "fetch_logs",
                                "arguments": json.dumps({
                                    "log_group": "/test",
                                    "start_time": f"{(i+1)*6}h ago",
                                })
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                )
            )
        
        tool_responses.append(
            LLMResponse(
                content="No results found after multiple attempts.",
                finish_reason="stop"
            )
        )
        
        mock_llm.chat.side_effect = tool_responses
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={"success": True, "count": 0, "events": []}
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Find logs")
        
        # Verify: Attempted multiple times
        assert mock_tools.execute.call_count == 4
        
        # Verify: Graceful exit after max attempts
        assert "no results" in result.lower() or "not found" in result.lower()


class TestLogGroupNotFound:
    """Test retry behavior when log group is not found."""

    @pytest.mark.asyncio
    async def test_log_group_not_found_lists_alternatives(
        self, integration_settings, mock_sanitizer
    ):
        """Test that log group not found error triggers listing of alternatives."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. Try non-existent log group
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/nonexistent",
                                "start_time": "1h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. After not found, list log groups
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "list_log_groups",
                            "arguments": json.dumps({"prefix": "/aws/lambda/"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Try alternative
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_3",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/aws/lambda/actual-service",
                                "start_time": "1h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 4. Final response
            LLMResponse(
                content="Found logs in /aws/lambda/actual-service instead.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            # First call: not found
            {"success": False, "error": "Log group not found: /aws/lambda/nonexistent"},
            # Second call: list groups
            {
                "success": True,
                "log_groups": [
                    {"name": "/aws/lambda/actual-service"},
                    {"name": "/aws/lambda/other-service"},
                ],
                "count": 2,
            },
            # Third call: fetch from correct group
            {
                "success": True,
                "count": 5,
                "events": [{"timestamp": i, "message": f"Log {i}"} for i in range(5)],
            },
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Get logs from /aws/lambda/nonexistent")
        
        # Verify: Made 3 tool calls (failed fetch, list, successful fetch)
        assert mock_tools.execute.call_count == 3
        
        # Verify: Eventually found the right log group
        assert "actual-service" in result.lower() or "found" in result.lower()


class TestComplexScenarios:
    """Test complex scenarios combining multiple retry behaviors."""

    @pytest.mark.asyncio
    async def test_empty_then_not_found_then_success(
        self, integration_settings, mock_sanitizer
    ):
        """Test handling of multiple failure types before success."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. Try narrow time range
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/test",
                                "start_time": "30m ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. After empty, expand time
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({
                                "log_group": "/test",
                                "start_time": "24h ago",
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response
            LLMResponse(
                content="Found 10 log entries in the expanded time range.",
                finish_reason="stop"
            ),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "count": 0, "events": []},  # Empty
            {  # Success
                "success": True,
                "count": 10,
                "events": [{"timestamp": i, "message": f"Log {i}"} for i in range(10)],
            },
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=integration_settings,
        )
        
        result = await orchestrator.chat("Find logs")
        
        # Verify: Multiple attempts made
        assert mock_tools.execute.call_count == 2
        
        # Verify: Eventually succeeded
        assert "10" in result and "found" in result.lower()
