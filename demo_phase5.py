#!/usr/bin/env python
"""
Demo script for Phase 5 - LLM Integration with Tools

This demonstrates the complete flow of:
1. User query
2. LLM decides to call a tool
3. Tool executes (mocked CloudWatch)
4. LLM analyzes results
5. User receives answer

Run with: python demo_phase5.py
"""

import asyncio
from unittest.mock import AsyncMock, Mock

from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.cloudwatch_tools import FetchLogsTool, ListLogGroupsTool
from logai.core.tools.registry import ToolRegistry
from logai.providers.datasources.cloudwatch import CloudWatchDataSource
from logai.providers.llm.base import LLMResponse
from logai.providers.llm.litellm_provider import LiteLLMProvider


async def demo():
    """Run the Phase 5 demo."""
    print("=" * 80)
    print("Phase 5 Demo: LLM Integration with Tools")
    print("=" * 80)
    print()

    # Setup (in production, these would be real instances)
    print("📦 Setting up components...")

    # Mock CloudWatch datasource
    datasource = AsyncMock(spec=CloudWatchDataSource)
    datasource.list_log_groups.return_value = [
        {"name": "/aws/lambda/auth-service", "created": 1234567890000, "stored_bytes": 1024000},
        {"name": "/aws/lambda/user-service", "created": 1234567891000, "stored_bytes": 2048000},
        {"name": "/aws/lambda/payment-service", "created": 1234567892000, "stored_bytes": 512000},
    ]

    datasource.fetch_logs.return_value = [
        {
            "timestamp": 1234567890000,
            "message": "ERROR: Authentication failed for user john@example.com",
            "log_stream": "2024/02/10/[$LATEST]abc123",
            "event_id": "evt_001",
        },
        {
            "timestamp": 1234567891000,
            "message": "ERROR: Invalid token provided",
            "log_stream": "2024/02/10/[$LATEST]abc123",
            "event_id": "evt_002",
        },
        {
            "timestamp": 1234567892000,
            "message": "ERROR: Session expired for user jane@example.com",
            "log_stream": "2024/02/10/[$LATEST]abc123",
            "event_id": "evt_003",
        },
    ]

    # Real sanitizer
    sanitizer = LogSanitizer(enabled=True)

    # Mock settings
    settings = Mock(spec=LogAISettings)
    settings.llm_provider = "anthropic"
    settings.current_llm_api_key = "demo-key"
    settings.current_llm_model = "claude-3-5-sonnet-20241022"
    settings.pii_sanitization_enabled = True

    # Register tools
    ToolRegistry.clear()
    list_tool = ListLogGroupsTool(datasource=datasource, settings=settings)
    fetch_tool = FetchLogsTool(datasource=datasource, sanitizer=sanitizer, settings=settings)
    ToolRegistry.register(list_tool)
    ToolRegistry.register(fetch_tool)

    print(f"✅ Registered {len(ToolRegistry.get_all())} tools:")
    for tool in ToolRegistry.get_all():
        print(f"   - {tool.name}: {tool.description[:60]}...")
    print()

    # Mock LLM provider to simulate responses
    llm_provider = AsyncMock(spec=LiteLLMProvider)

    # Simulate conversation flow
    print('💬 User Query: "Show me recent errors from the auth service"')
    print()

    # Step 1: LLM decides to list log groups first
    print("🤖 LLM: I'll list the log groups to find the auth service...")
    tool_call_1 = LLMResponse(
        content="",
        tool_calls=[
            {
                "id": "call_001",
                "type": "function",
                "function": {"name": "list_log_groups", "arguments": '{"prefix": "/aws/lambda/"}'},
            }
        ],
        finish_reason="tool_calls",
    )

    # Step 2: After seeing log groups, fetch logs from auth service
    print("🔧 Tool: list_log_groups executed")
    print("   Found 3 log groups:")
    for lg in datasource.list_log_groups.return_value:
        print(f"   - {lg['name']}")
    print()

    print("🤖 LLM: Now I'll fetch error logs from /aws/lambda/auth-service...")
    tool_call_2 = LLMResponse(
        content="",
        tool_calls=[
            {
                "id": "call_002",
                "type": "function",
                "function": {
                    "name": "fetch_logs",
                    "arguments": '{"log_group": "/aws/lambda/auth-service", "start_time": "1h ago", "filter_pattern": "ERROR"}',
                },
            }
        ],
        finish_reason="tool_calls",
    )

    # Step 3: LLM analyzes and responds
    print("🔧 Tool: fetch_logs executed")
    print("   Retrieved 3 error log events")
    print("   🔒 PII Sanitization: Redacted 2 Email addresses")
    print()

    print("🤖 LLM: Analyzing the errors...")
    final_response = LLMResponse(
        content="""I found 3 recent errors in the auth service:

1. **Authentication failures** - Multiple users experiencing login issues
2. **Invalid token errors** - Token validation is failing
3. **Session expiration** - Users being logged out unexpectedly

**Recommendation:** This looks like a pattern of authentication problems. I suggest:
- Check if the auth token service is running properly
- Verify session configuration and timeout settings
- Review recent deployments to the auth service

The errors span approximately 2 seconds, suggesting a temporary issue or spike in failed attempts.""",
        finish_reason="stop",
    )

    # Set up the mock to return these responses in sequence
    llm_provider.chat.side_effect = [tool_call_1, tool_call_2, final_response]

    # Create orchestrator and run
    orchestrator = LLMOrchestrator(
        llm_provider=llm_provider,
        tool_registry=ToolRegistry,
        sanitizer=sanitizer,
        settings=settings,
    )

    print("🎯 Final Response:")
    print("-" * 80)
    result = await orchestrator.chat("Show me recent errors from the auth service")
    print(result)
    print("-" * 80)
    print()

    # Show conversation history
    print("📜 Conversation History:")
    print(f"   Total messages: {len(orchestrator.conversation_history)}")
    print(
        f"   - User messages: {sum(1 for m in orchestrator.conversation_history if m['role'] == 'user')}"
    )
    print(
        f"   - Assistant messages: {sum(1 for m in orchestrator.conversation_history if m['role'] == 'assistant')}"
    )
    print(
        f"   - Tool messages: {sum(1 for m in orchestrator.conversation_history if m['role'] == 'tool')}"
    )
    print()

    # Show tool definitions
    print("🛠️  Tool Definitions (exported to LLM):")
    definitions = ToolRegistry.to_function_definitions()
    for defn in definitions:
        func = defn["function"]
        print(f"   - {func['name']}")
        print(f"     Parameters: {', '.join(func['parameters']['properties'].keys())}")
        print(f"     Required: {', '.join(func['parameters'].get('required', []))}")
    print()

    print("=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)
    print()
    print("This demonstrates:")
    print("  ✓ LLM orchestration with tool calling")
    print("  ✓ Multiple sequential tool calls")
    print("  ✓ PII sanitization integration")
    print("  ✓ CloudWatch data source integration")
    print("  ✓ Conversation history management")
    print("  ✓ Error analysis and recommendations")
    print()
    print("Ready for Phase 6 (Caching) and Phase 7 (TUI)! 🚀")


if __name__ == "__main__":
    asyncio.run(demo())
