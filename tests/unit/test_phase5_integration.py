"""Integration test for Phase 5 - LLM Integration with Tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.cloudwatch_tools import FetchLogsTool, ListLogGroupsTool
from logai.core.tools.registry import ToolRegistry
from logai.providers.datasources.cloudwatch import CloudWatchDataSource
from logai.providers.llm.base import LLMResponse
from logai.providers.llm.litellm_provider import LiteLLMProvider


@pytest.fixture
def mock_settings():
    """Create test settings."""
    settings = Mock(spec=LogAISettings)
    settings.llm_provider = "anthropic"
    settings.current_llm_api_key = "test-key"
    settings.current_llm_model = "claude-3-5-sonnet-20241022"
    settings.pii_sanitization_enabled = True
    # Add self-direction settings for new features
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = True
    settings.time_expansion_factor = 4.0
    return settings


@pytest.fixture
def setup_tools():
    """Setup tools for integration test."""
    # Clear registry before test
    ToolRegistry.clear()

    # Create mock datasource
    datasource = AsyncMock(spec=CloudWatchDataSource)
    sanitizer = LogSanitizer(enabled=True)
    settings = Mock(spec=LogAISettings)

    # Register tools
    list_tool = ListLogGroupsTool(datasource=datasource, settings=settings)
    fetch_tool = FetchLogsTool(datasource=datasource, sanitizer=sanitizer, settings=settings)

    ToolRegistry.register(list_tool)
    ToolRegistry.register(fetch_tool)

    yield {"datasource": datasource, "sanitizer": sanitizer}

    # Cleanup
    ToolRegistry.clear()


class TestPhase5Integration:
    """Integration tests for Phase 5 - LLM with Tools."""

    @pytest.mark.asyncio
    async def test_full_workflow_list_log_groups(self, setup_tools, mock_settings):
        """Test complete workflow: user query -> LLM -> tool call -> response."""
        # Setup
        datasource = setup_tools["datasource"]
        sanitizer = setup_tools["sanitizer"]

        # Mock CloudWatch response
        datasource.list_log_groups.return_value = [
            {"name": "/aws/lambda/function1", "created": 1234567890000},
            {"name": "/aws/lambda/function2", "created": 1234567891000},
        ]

        # Mock LLM provider
        llm_provider = AsyncMock(spec=LiteLLMProvider)

        # First call: LLM decides to use list_log_groups tool
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

        # Second call: LLM processes tool result and responds to user
        final_response = LLMResponse(
            content="I found 2 Lambda function log groups:\n1. /aws/lambda/function1\n2. /aws/lambda/function2",
            finish_reason="stop",
        )

        llm_provider.chat.side_effect = [tool_call_response, final_response]

        # Create orchestrator
        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=mock_settings,
        )

        # Execute
        result = await orchestrator.chat("List all Lambda function log groups")

        # Verify
        assert "2 Lambda function log groups" in result
        assert "function1" in result
        assert "function2" in result
        assert datasource.list_log_groups.called

    @pytest.mark.asyncio
    async def test_full_workflow_fetch_logs_with_sanitization(self, setup_tools, mock_settings):
        """Test fetching logs with PII sanitization."""
        # Setup
        datasource = setup_tools["datasource"]
        sanitizer = setup_tools["sanitizer"]

        # Mock CloudWatch response with PII
        datasource.fetch_logs.return_value = [
            {
                "timestamp": 1234567890000,
                "message": "User john@example.com logged in from [IP_REDACTED]",
                "log_stream": "stream1",
            },
            {
                "timestamp": 1234567891000,
                "message": "Payment processed for card [CC_REDACTED]",
                "log_stream": "stream1",
            },
        ]

        # Mock LLM provider
        llm_provider = AsyncMock(spec=LiteLLMProvider)

        # First call: LLM decides to fetch logs
        tool_call_response = LLMResponse(
            content="",
            tool_calls=[
                {
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "fetch_logs",
                        "arguments": '{"log_group": "/aws/lambda/auth", "start_time": "1h ago"}',
                    },
                }
            ],
            finish_reason="tool_calls",
        )

        # Second call: LLM analyzes logs and responds
        final_response = LLMResponse(
            content="I found 2 log entries. The logs show user login activity and payment processing. "
            "PII was sanitized before analysis.",
            finish_reason="stop",
        )

        llm_provider.chat.side_effect = [tool_call_response, final_response]

        # Create orchestrator
        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=mock_settings,
        )

        # Execute
        result = await orchestrator.chat("Show me logs from auth service in last hour")

        # Verify
        assert "2 log entries" in result
        assert datasource.fetch_logs.called

        # Verify fetch_logs was called with correct parameters
        call_kwargs = datasource.fetch_logs.call_args[1]
        assert call_kwargs["log_group"] == "/aws/lambda/auth"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_conversation(self, setup_tools, mock_settings):
        """Test conversation with multiple sequential tool calls."""
        # Setup
        datasource = setup_tools["datasource"]
        sanitizer = setup_tools["sanitizer"]

        # Mock responses
        datasource.list_log_groups.return_value = [
            {"name": "/aws/lambda/auth", "created": 1234567890000},
        ]
        datasource.fetch_logs.return_value = [
            {
                "timestamp": 1234567890000,
                "message": "ERROR: Authentication failed",
                "log_stream": "stream1",
            },
        ]

        # Mock LLM provider
        llm_provider = AsyncMock(spec=LiteLLMProvider)

        # Conversation: list -> fetch -> analyze
        responses = [
            # 1. List log groups
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
            # 2. After seeing groups, fetch logs
            LLMResponse(
                content="",
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "fetch_logs",
                            "arguments": '{"log_group": "/aws/lambda/auth", "start_time": "1h ago"}',
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            # 3. Final response
            LLMResponse(
                content="I found authentication errors in the /aws/lambda/auth log group.",
                finish_reason="stop",
            ),
        ]

        llm_provider.chat.side_effect = responses

        # Create orchestrator
        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=mock_settings,
        )

        # Execute
        result = await orchestrator.chat("Find authentication errors")

        # Verify
        assert "authentication errors" in result
        assert datasource.list_log_groups.called
        assert datasource.fetch_logs.called

    @pytest.mark.asyncio
    async def test_tool_registry_function_definitions(self, setup_tools):
        """Test that tool registry exports correct function definitions."""
        definitions = ToolRegistry.to_function_definitions()

        # Should have 2 tools registered
        assert len(definitions) == 2

        # Verify structure
        for definition in definitions:
            assert definition["type"] == "function"
            assert "function" in definition
            assert "name" in definition["function"]
            assert "description" in definition["function"]
            assert "parameters" in definition["function"]

        # Verify specific tools
        tool_names = [d["function"]["name"] for d in definitions]
        assert "list_log_groups" in tool_names
        assert "fetch_logs" in tool_names

    @pytest.mark.asyncio
    async def test_conversation_history_maintained(self, setup_tools, mock_settings):
        """Test that conversation history is properly maintained."""
        datasource = setup_tools["datasource"]
        sanitizer = setup_tools["sanitizer"]

        datasource.list_log_groups.return_value = []

        llm_provider = AsyncMock(spec=LiteLLMProvider)

        # Simple response without tools
        llm_provider.chat.return_value = LLMResponse(
            content="Hello! How can I help with logs?", finish_reason="stop"
        )

        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=mock_settings,
        )

        # First message
        await orchestrator.chat("Hello")
        assert len(orchestrator.conversation_history) == 2  # user + assistant

        # Second message
        await orchestrator.chat("Thanks")
        assert len(orchestrator.conversation_history) == 4  # 2 pairs

        # Get history
        history = orchestrator.get_history()
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[3]["role"] == "assistant"

        # Clear history
        orchestrator.clear_history()
        assert len(orchestrator.conversation_history) == 0
