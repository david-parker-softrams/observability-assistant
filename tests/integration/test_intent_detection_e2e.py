"""End-to-end integration tests for intent detection system.

These tests verify the complete flow of intent detection from agent response
through nudging and eventual action execution.
"""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from logai.config.settings import LogAISettings
from logai.core.intent_detector import IntentDetector, IntentType
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def e2e_settings():
    """Settings for end-to-end testing."""
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = True
    settings.time_expansion_factor = 4.0
    return settings


@pytest.fixture
def mock_sanitizer():
    """Create mock sanitizer."""
    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.enabled = True
    return sanitizer


class TestIntentDetectionPatterns:
    """Test detection of various intent patterns."""

    def test_detect_search_intent(self):
        """Test detection of search intentions."""
        test_cases = [
            "I'll search for errors in the logs.",
            "Let me look for authentication failures.",
            "I will check the CloudWatch logs now.",
            "I'm going to investigate the error logs.",
        ]
        
        for text in test_cases:
            intent = IntentDetector.detect_intent(text)
            assert intent is not None, f"Failed to detect intent in: {text}"
            assert intent.intent_type == IntentType.SEARCH_LOGS
            assert intent.confidence >= 0.8

    def test_detect_list_groups_intent(self):
        """Test detection of list log groups intentions."""
        test_cases = [
            "I'll list the available log groups.",
            "Let me show the log groups.",
            "I will get the available log groups.",
        ]
        
        for text in test_cases:
            intent = IntentDetector.detect_intent(text)
            assert intent is not None, f"Failed to detect intent in: {text}"
            assert intent.intent_type == IntentType.LIST_GROUPS
            assert intent.confidence >= 0.8

    def test_detect_time_expansion_intent(self):
        """Test detection of time expansion intentions."""
        test_cases = [
            "Let me expand the time range.",
            "I'll widen the time window.",
            "We should broaden the time period.",
        ]
        
        for text in test_cases:
            intent = IntentDetector.detect_intent(text)
            assert intent is not None, f"Failed to detect intent in: {text}"
            assert intent.intent_type == IntentType.EXPAND_TIME
            assert intent.confidence >= 0.7

    def test_detect_filter_change_intent(self):
        """Test detection of filter change intentions."""
        test_cases = [
            "Let me try a different filter.",
            "I'll use a broader filter pattern.",
            "We should try another filter.",
        ]
        
        for text in test_cases:
            intent = IntentDetector.detect_intent(text)
            assert intent is not None, f"Failed to detect intent in: {text}"
            assert intent.intent_type == IntentType.CHANGE_FILTER
            assert intent.confidence >= 0.7

    def test_no_intent_in_analysis(self):
        """Test that analysis statements don't trigger intent detection."""
        test_cases = [
            "Based on the logs, there are 5 errors.",
            "The logs show authentication failures at 3 PM.",
            "These errors indicate a database connection issue.",
            "I analyzed the results and found the problem.",
        ]
        
        for text in test_cases:
            intent = IntentDetector.detect_intent(text)
            # Should either be None or be ANALYZE type with low confidence
            if intent is not None:
                assert intent.intent_type == IntentType.ANALYZE or intent.confidence < 0.8

    def test_detect_premature_giving_up(self):
        """Test detection of giving up patterns."""
        test_cases = [
            "No logs were found.",
            "I couldn't find any matching entries.",
            "There are no logs in the time range.",
            "The search returned no results.",
            "Unfortunately, I was unable to find logs.",
        ]
        
        for text in test_cases:
            is_giving_up = IntentDetector.detect_premature_giving_up(text)
            assert is_giving_up is True, f"Failed to detect giving up in: {text}"

    def test_no_giving_up_in_success(self):
        """Test that success messages don't trigger giving up detection."""
        test_cases = [
            "I found 15 error logs.",
            "Here are the results from the search.",
            "The logs show several issues.",
            "I retrieved 100 log entries.",
        ]
        
        for text in test_cases:
            is_giving_up = IntentDetector.detect_premature_giving_up(text)
            assert is_giving_up is False, f"False positive giving up in: {text}"


class TestIntentNudgingFlow:
    """Test the complete flow from intent detection to action."""

    @pytest.mark.asyncio
    async def test_search_intent_leads_to_tool_call(self, e2e_settings, mock_sanitizer):
        """Test that search intent without action leads to actual tool call."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. States intent
            LLMResponse(content="I'll search for ERROR logs.", finish_reason="stop"),
            # 2. After nudge, calls tool
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
                                "filter_pattern": "ERROR"
                            })
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response
            LLMResponse(content="Found 5 errors.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={
                "success": True,
                "count": 5,
                "events": [{"message": f"ERROR {i}"} for i in range(5)],
            }
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Find errors")
        
        # Verify the complete flow
        assert mock_llm.chat.call_count >= 2  # Initial + nudge + ...
        assert mock_tools.execute.called
        assert "5" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_list_intent_leads_to_list_call(self, e2e_settings, mock_sanitizer):
        """Test that list intent without action leads to list_log_groups call."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. States intent
            LLMResponse(content="Let me list the available log groups.", finish_reason="stop"),
            # 2. After nudge, calls tool
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "list_log_groups",
                            "arguments": json.dumps({})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response
            LLMResponse(content="Here are the available log groups.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={
                "success": True,
                "log_groups": [
                    {"name": "/aws/lambda/service1"},
                    {"name": "/aws/lambda/service2"},
                ],
                "count": 2,
            }
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Show log groups")
        
        # Verify the flow
        assert mock_tools.execute.called
        assert mock_tools.execute.call_args[0][0] == "list_log_groups"

    @pytest.mark.asyncio
    async def test_multiple_intents_single_conversation(self, e2e_settings, mock_sanitizer):
        """Test handling multiple stated intents in sequence."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. First intent
            LLMResponse(content="I'll check the log groups first.", finish_reason="stop"),
            # 2. After nudge, list
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_log_groups", "arguments": "{}"},
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Second intent
            LLMResponse(content="Now I'll search for errors.", finish_reason="stop"),
            # 4. After nudge, search
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"log_group": "/test", "filter_pattern": "ERROR"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 5. Final response
            LLMResponse(content="Analysis complete.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "log_groups": [{"name": "/test"}], "count": 1},
            {"success": True, "count": 3, "events": [{"message": "ERROR"}] * 3},
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Check logs")
        
        # Verify both tools were called
        assert mock_tools.execute.call_count == 2


class TestIntentWithRetry:
    """Test interaction between intent detection and retry logic."""

    @pytest.mark.asyncio
    async def test_intent_after_empty_result(self, e2e_settings, mock_sanitizer):
        """Test intent detection after receiving empty results."""
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
                            "arguments": json.dumps({"log_group": "/test", "start_time": "1h ago"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. After empty result, states intent to expand
            LLMResponse(content="I'll expand the time range to find more logs.", finish_reason="stop"),
            # 3. After nudge, actually expands
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"log_group": "/test", "start_time": "24h ago"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 4. Final response
            LLMResponse(content="Found logs in expanded range.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "count": 0, "events": []},  # Empty
            {"success": True, "count": 5, "events": [{"message": "Log"}] * 5},  # Found
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Get logs")
        
        # Verify retry occurred after intent was stated
        assert mock_tools.execute.call_count == 2
        assert "found" in result.lower()

    @pytest.mark.asyncio
    async def test_giving_up_prevented_by_nudge(self, e2e_settings, mock_sanitizer):
        """Test that premature giving up is prevented by nudging."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # 1. Tool call
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"log_group": "/test"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 2. Tries to give up
            LLMResponse(content="No logs were found.", finish_reason="stop"),
            # 3. After nudge, retries
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"log_group": "/test", "start_time": "24h ago"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 4. Success
            LLMResponse(content="Found logs with expanded time.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        mock_tools.execute.side_effect = [
            {"success": True, "count": 0, "events": []},
            {"success": True, "count": 3, "events": [{"message": "Log"}] * 3},
        ]
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Find logs")
        
        # Verify nudge prevented giving up
        assert mock_tools.execute.call_count == 2
        assert "found" in result.lower()


class TestEdgeCases:
    """Test edge cases in intent detection."""

    @pytest.mark.asyncio
    async def test_mixed_intent_and_action(self, e2e_settings, mock_sanitizer):
        """Test response that states intent AND includes tool call."""
        mock_llm = AsyncMock()
        
        mock_llm.chat.side_effect = [
            # States intent AND calls tool in same response
            LLMResponse(
                content="I'll search for errors.",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": json.dumps({"filter_pattern": "ERROR"})
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # Final response
            LLMResponse(content="Found errors.", finish_reason="stop"),
        ]
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock(
            return_value={"success": True, "count": 3, "events": [{"message": "ERROR"}] * 3}
        )
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Find errors")
        
        # Should process normally without extra nudge
        assert mock_tools.execute.call_count == 1
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_max_nudge_attempts(self, e2e_settings, mock_sanitizer):
        """Test that nudging respects max retry attempts."""
        mock_llm = AsyncMock()
        
        # Agent keeps stating intent without action
        responses = []
        for i in range(10):
            responses.append(
                LLMResponse(content="I'll search for logs.", finish_reason="stop")
            )
        
        mock_llm.chat.side_effect = responses
        
        mock_tools = Mock(spec=ToolRegistry)
        mock_tools.to_function_definitions = Mock(return_value=[])
        mock_tools.execute = AsyncMock()
        
        orchestrator = LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=mock_tools,
            sanitizer=mock_sanitizer,
            settings=e2e_settings,
        )
        
        result = await orchestrator.chat("Find logs")
        
        # Should eventually give up and return the response
        # Max retry attempts is 3, so should not loop forever
        assert "search" in result.lower()
        assert mock_llm.chat.call_count <= 5  # Should stop after a few attempts
