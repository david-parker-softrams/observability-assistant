#!/usr/bin/env python3
"""
Visual verification that the context injection fix works correctly.
This script demonstrates that only ONE system message is created when context is injected.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from logai.config.settings import LogAISettings
from logai.core.context.result_cache import ResultCacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


async def main():
    """Demonstrate the fix."""
    print("=" * 80)
    print("CONTEXT INJECTION FIX VERIFICATION")
    print("=" * 80)
    print()

    # Create test settings
    settings = LogAISettings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        cache_dir=Path("/tmp/test-cache"),
    )

    # Create mock LLM provider that captures messages
    captured_messages = []

    async def capture_chat(messages, tools, stream):
        """Capture messages sent to LLM."""
        captured_messages.clear()
        captured_messages.extend(messages)
        return LLMResponse(content="Test response", tool_calls=None)

    mock_llm_provider = Mock()
    mock_llm_provider.chat = AsyncMock(side_effect=capture_chat)

    # Create mock sanitizer
    mock_sanitizer = Mock(spec=LogSanitizer)
    mock_sanitizer.sanitize = Mock(side_effect=lambda x: x)

    # Create result cache
    result_cache = ResultCacheManager(
        cache_dir=Path("/tmp/test-cache/results"),
        ttl_seconds=3600,
        max_size_mb=100,
    )

    # Clear tool registry
    ToolRegistry.clear()

    # Create orchestrator
    orchestrator = LLMOrchestrator(
        llm_provider=mock_llm_provider,
        tool_registry=ToolRegistry,
        sanitizer=mock_sanitizer,
        settings=settings,
        result_cache=result_cache,
    )

    # Test 1: Without context injection
    print("TEST 1: Without context injection")
    print("-" * 80)
    await orchestrator.chat("Hello, can you help me?")

    system_msgs = [msg for msg in captured_messages if msg["role"] == "system"]
    print(f"✓ Number of system messages: {len(system_msgs)}")
    print(f"✓ System message length: {len(system_msgs[0]['content'])} chars")
    assert len(system_msgs) == 1, f"Expected 1 system message, got {len(system_msgs)}"
    print()

    # Test 2: With context injection
    print("TEST 2: With context injection (the critical fix)")
    print("-" * 80)

    # Set up pending context injection
    context_text = """CONTEXT: User selected log entries:

Entry 1:
Timestamp: 2024-01-01T12:00:00Z
Level: ERROR
Message: Database connection timeout
Service: api-server

Entry 2:
Timestamp: 2024-01-01T12:00:05Z
Level: ERROR
Message: Failed to process request
Service: api-server
"""

    orchestrator._pending_context_injection = context_text
    print(f"Context injection size: {len(context_text)} chars")
    print()

    # Send a message (this triggers context injection)
    await orchestrator.chat("Analyze these errors")

    # Count system messages
    system_msgs = [msg for msg in captured_messages if msg["role"] == "system"]

    print(f"✓ Number of system messages: {len(system_msgs)}")

    if len(system_msgs) == 1:
        print("✓ SUCCESS! Only ONE system message (as required)")
    else:
        print(f"✗ FAILURE! Found {len(system_msgs)} system messages")

    # Verify the system message contains both original prompt and context
    system_content = system_msgs[0]["content"]
    print(f"✓ Total system message length: {len(system_content)} chars")

    has_original = "observability" in system_content.lower()
    has_context = "User selected log entries" in system_content
    has_separator = "\n\n---\n\n" in system_content

    print(f"✓ Contains original prompt: {has_original}")
    print(f"✓ Contains injected context: {has_context}")
    print(f"✓ Contains separator: {has_separator}")
    print()

    # Show a preview of the merged content
    print("System message structure:")
    print("-" * 80)
    lines = system_content.split("\n")
    print(f"Line 1: {lines[0][:70]}...")
    print("...")
    separator_idx = system_content.find("\n\n---\n\n")
    if separator_idx > 0:
        context_start = separator_idx + len("\n\n---\n\n")
        context_preview = system_content[context_start : context_start + 100]
        print(f"After separator: {context_preview}...")
    print()

    # Final assertions
    assert len(system_msgs) == 1, "CRITICAL: Must have exactly ONE system message"
    assert has_original, "System message must contain original prompt"
    assert has_context, "System message must contain injected context"
    assert has_separator, "Context must be separated from original prompt"

    print("=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("✓ Context is properly merged into single system message")
    print("✓ OpenAI API will now see the context (it was being ignored before)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
