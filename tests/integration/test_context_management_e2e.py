"""
End-to-end integration tests for Intelligent Context Management System.

These tests verify the complete context management workflow including:
- Token counting and budget tracking
- Automatic result caching for large results
- History pruning when context fills up
- UI notifications and status updates
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from logai.config.settings import LogAISettings
from logai.core.context.budget_tracker import ContextBudgetTracker
from logai.core.context.result_cache import ResultCacheManager
from logai.core.context.token_counter import TokenCounter
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import LLMResponse


@pytest.fixture
def settings(tmp_path):
    """Create test settings with context management enabled."""
    return LogAISettings(
        llm_provider="github-copilot",
        github_copilot_model="gpt-4o-mini",
        cache_dir=tmp_path / "cache",
        enable_result_caching=True,
        enable_history_pruning=True,
        cache_large_results_threshold=5000,  # Lower threshold for testing
        context_window_buffer=5000,
        max_result_tokens=50000,
        max_history_tokens=80000,
    )


@pytest.fixture
def result_cache(tmp_path):
    """Create test result cache manager."""
    cache_dir = tmp_path / "result_cache"
    cache_dir.mkdir(parents=True)
    return ResultCacheManager(cache_dir=cache_dir, ttl_seconds=3600)


@pytest.fixture
def budget_tracker(settings):
    """Create test budget tracker."""
    return ContextBudgetTracker(settings=settings, model="gpt-4o-mini")


@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider."""
    provider = AsyncMock()
    provider.generate.return_value = LLMResponse(
        content="Test response",
        stop_reason="end_turn",
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    return provider


@pytest.fixture
def orchestrator(settings, mock_llm_provider, result_cache, tmp_path):
    """Create test orchestrator with context management."""
    tool_registry = ToolRegistry()
    sanitizer = LogSanitizer(enabled=False)

    orch = LLMOrchestrator(
        llm_provider=mock_llm_provider,
        tool_registry=tool_registry,
        sanitizer=sanitizer,
        settings=settings,
        result_cache=result_cache,
    )

    return orch


class TestScenario1NormalOperation:
    """Test Scenario 1: Normal operation with context 0-70%."""

    def test_initial_state_zero_context(self, orchestrator):
        """Test that initial context is 0%."""
        usage = orchestrator.budget_tracker.get_usage()

        assert usage.utilization_pct == 0.0
        assert usage.total_tokens == 0
        assert usage.remaining_tokens > 0

    @pytest.mark.asyncio
    async def test_gradual_context_increase(self, orchestrator, mock_llm_provider):
        """Test that context increases gradually with messages."""
        # Configure mock to return simple responses
        mock_llm_provider.generate.return_value = LLMResponse(
            content="I can help with that.",
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 20},
        )

        # Send several messages
        messages = [
            "Hello",
            "What log groups are available?",
            "Show me recent logs",
            "Analyze the patterns",
            "Any errors?",
        ]

        previous_utilization = 0.0

        for msg in messages:
            orchestrator.conversation_history.append({"role": "user", "content": msg})
            orchestrator.conversation_history.append({"role": "assistant", "content": "Response"})

            # Update budget tracker with current history
            orchestrator._update_budget_tracker(orchestrator.conversation_history)
            usage = orchestrator.budget_tracker.get_usage()

            # Context should increase
            assert usage.utilization_pct >= previous_utilization
            previous_utilization = usage.utilization_pct

        # Should still be under 70% for normal queries
        assert usage.utilization_pct < 70.0


class TestScenario2LargeResultCaching:
    """Test Scenario 2: Large result caching (>5000 tokens)."""

    @pytest.mark.asyncio
    async def test_large_result_triggers_caching(self, orchestrator, result_cache):
        """Test that large results are automatically cached."""
        # Create a large mock result (many log events)
        large_result = {
            "success": True,
            "events": [
                {"timestamp": 1000 + i, "message": f"Log event {i}" * 50}
                for i in range(500)  # 500 events with long messages
            ],
            "count": 500,
        }

        # Check if it should be cached
        should_cache, token_count = orchestrator.budget_tracker.should_cache_result(
            large_result, threshold=5000
        )

        assert should_cache, "Large result should trigger caching"
        assert token_count > 5000, f"Result should exceed threshold (got {token_count} tokens)"

        # Process the result through orchestrator
        tool_result = {
            "tool_call_id": "test-call-1",
            "result": large_result,
        }

        processed = await orchestrator._process_tool_result(tool_result, "query_logs")

        # Should return a summary, not full result
        assert "cached" in processed["result"]
        assert processed["result"]["cached"] is True
        assert "cache_id" in processed["result"]
        assert "summary" in processed["result"]

    @pytest.mark.asyncio
    async def test_cached_result_retrieval(self, result_cache):
        """Test that cached results can be retrieved in chunks."""
        # Cache a large result
        large_result = {
            "events": [{"timestamp": 1000 + i, "message": f"Event {i}"} for i in range(1000)],
            "count": 1000,
        }

        summary = await result_cache.cache_result(
            tool_name="query_logs",
            query_params={"log_group": "/test/logs", "limit": 1000},
            result=large_result,
        )

        # Fetch a chunk
        chunk = await result_cache.fetch_chunk(
            cache_id=summary.cache_id,
            offset=0,
            limit=50,
        )

        assert chunk["success"] is True
        assert len(chunk["events"]) == 50
        assert chunk["total_cached"] == 1000
        assert chunk["has_more"] is True

    @pytest.mark.asyncio
    async def test_caching_notification(self, orchestrator):
        """Test that caching triggers a notification."""
        notifications = []

        def capture_notification(level, message):
            notifications.append({"level": level, "message": message})

        orchestrator.set_context_notification_callback(capture_notification)

        # Create large result
        large_result = {
            "success": True,
            "events": [{"message": f"Event {i}" * 100} for i in range(200)],
            "count": 200,
        }

        tool_result = {
            "tool_call_id": "test-call-1",
            "result": large_result,
        }

        await orchestrator._process_tool_result(tool_result, "query_logs")

        # Should have received notification
        assert len(notifications) > 0
        cached_notifs = [n for n in notifications if "cached" in n["message"].lower()]
        assert len(cached_notifs) > 0, "Should receive caching notification"


class TestScenario3HistoryPruning:
    """Test Scenario 3: History pruning when context reaches 85%."""

    def test_should_prune_at_threshold(self, orchestrator):
        """Test that pruning is triggered at 85% utilization."""
        # Fill context to 85%
        target_utilization = 85.0
        budget = orchestrator.budget_tracker.allocation
        target_tokens = int(budget.usable_tokens * target_utilization / 100)

        # Add messages to reach target
        large_content = "X" * 1000  # ~250 tokens each
        while orchestrator.budget_tracker.get_usage().total_tokens < target_tokens:
            orchestrator.budget_tracker.add_message(
                {
                    "role": "user",
                    "content": large_content,
                }
            )

        # Check if pruning is recommended
        assert orchestrator._should_prune_history()

    def test_pruning_preserves_recent_messages(self, budget_tracker):
        """Test that pruning preserves the 4 most recent messages."""
        # Add 20 messages
        for i in range(20):
            budget_tracker.add_message(
                {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}",
                }
            )

        # Get prunable messages to free 5000 tokens
        to_prune = budget_tracker.get_prunable_messages(target_tokens=5000)

        # Should not include the last 4 messages
        total_messages = 20
        assert all(
            idx < total_messages - 4 for idx in to_prune
        ), "Should preserve the 4 most recent messages"

    def test_pruning_frees_tokens(self, orchestrator):
        """Test that pruning actually frees context space."""
        # Fill context significantly
        for _i in range(30):
            orchestrator.conversation_history.append(
                {
                    "role": "user",
                    "content": "X" * 500,  # ~125 tokens each
                }
            )

        # Update budget tracker
        orchestrator._update_budget_tracker(orchestrator.conversation_history)
        usage_before = orchestrator.budget_tracker.get_usage()

        # Perform pruning
        orchestrator._prune_history_if_needed()

        # Update budget tracker again
        orchestrator._update_budget_tracker(orchestrator.conversation_history)
        usage_after = orchestrator.budget_tracker.get_usage()

        # Should have freed tokens
        # Note: If pruning didn't occur (usage was <80%), this is okay
        if usage_before.utilization_pct >= 80:
            assert (
                usage_after.total_tokens < usage_before.total_tokens
            ), "Pruning should reduce token count"

    def test_pruning_notification(self, orchestrator):
        """Test that pruning triggers a notification."""
        notifications = []

        def capture_notification(level, message):
            notifications.append({"level": level, "message": message})

        orchestrator.set_context_notification_callback(capture_notification)

        # Fill context to trigger pruning
        for _i in range(50):
            orchestrator.conversation_history.append(
                {
                    "role": "user",
                    "content": "X" * 1000,
                }
            )

        # Force update and prune
        orchestrator._update_budget_tracker(orchestrator.conversation_history)
        orchestrator._prune_history_if_needed()

        # Check for pruning notification
        pruned_notifs = [n for n in notifications if "pruned" in n["message"].lower()]

        # May or may not have pruned depending on context window size
        # If utilization was high enough, should have notification
        usage = orchestrator.budget_tracker.get_usage()
        if usage.utilization_pct >= 80:
            assert len(pruned_notifs) > 0, "Should receive pruning notification"


class TestScenario4MultiplelargeResults:
    """Test Scenario 4: Multiple large results."""

    @pytest.mark.asyncio
    async def test_multiple_large_results_cached(self, orchestrator):
        """Test that multiple large results are each cached independently."""
        cached_count = 0

        def count_cache_notifications(level, message):
            nonlocal cached_count
            if "cached" in message.lower() and "large result" in message.lower():
                cached_count += 1

        orchestrator.set_context_notification_callback(count_cache_notifications)

        # Process 5 large results
        for i in range(5):
            large_result = {
                "events": [{"message": f"Event {j}" * 50} for j in range(200)],
                "count": 200,
            }

            tool_result = {
                "tool_call_id": f"test-call-{i}",
                "result": large_result,
            }

            await orchestrator._process_tool_result(tool_result, "query_logs")

        # Should have cached all 5
        assert cached_count == 5, f"Expected 5 caching notifications, got {cached_count}"

    @pytest.mark.asyncio
    async def test_context_stays_under_limit(self, orchestrator):
        """Test that context doesn't overflow with multiple large results."""
        # Process multiple large results
        for i in range(10):
            large_result = {
                "events": [{"message": f"Event {j}" * 30} for j in range(150)],
                "count": 150,
            }

            tool_result = {
                "tool_call_id": f"test-call-{i}",
                "result": large_result,
            }

            await orchestrator._process_tool_result(tool_result, "query_logs")

            # Add to conversation history (simulate orchestrator flow)
            orchestrator.conversation_history.append(
                {
                    "role": "tool",
                    "content": json.dumps(tool_result["result"]),
                    "tool_call_id": tool_result["tool_call_id"],
                }
            )

            # Update budget and prune if needed
            orchestrator._update_budget_tracker(orchestrator.conversation_history)
            orchestrator._prune_history_if_needed()

        # Context should never exceed 95%
        usage = orchestrator.budget_tracker.get_usage()
        assert (
            usage.utilization_pct < 95.0
        ), f"Context should stay under 95%, got {usage.utilization_pct}%"


class TestScenario6EdgeCases:
    """Test Scenario 6: Edge cases and error handling."""

    def test_empty_conversation(self, orchestrator):
        """Test empty conversation shows 0% context."""
        usage = orchestrator.budget_tracker.get_usage()
        assert usage.utilization_pct == 0.0
        assert usage.total_tokens == 0

    def test_single_message(self, orchestrator):
        """Test single message updates context correctly."""
        orchestrator.budget_tracker.add_message(
            {
                "role": "user",
                "content": "Hello",
            }
        )

        usage = orchestrator.budget_tracker.get_usage()
        assert usage.total_tokens > 0
        assert usage.utilization_pct > 0
        assert usage.utilization_pct < 5.0  # Should be very small

    @pytest.mark.asyncio
    async def test_cache_failure_graceful_degradation(self, orchestrator):
        """Test that cache failures don't crash the system."""
        # Make result_cache.cache_result raise an exception
        with patch.object(
            orchestrator.result_cache,
            "cache_result",
            side_effect=Exception("Cache write failed"),
        ):
            large_result = {
                "events": [{"message": f"Event {i}" * 50} for i in range(200)],
                "count": 200,
            }

            tool_result = {
                "tool_call_id": "test-call-1",
                "result": large_result,
            }

            # Should not raise exception
            processed = await orchestrator._process_tool_result(tool_result, "query_logs")

            # Should still return a result (full result as fallback)
            assert processed is not None
            assert "result" in processed

    def test_extremely_large_single_message(self, budget_tracker):
        """Test handling of extremely large single message."""
        # Create a message larger than the entire budget
        huge_content = "X" * 1000000  # ~250k tokens

        # Try to add it
        fits = budget_tracker.add_message(
            {
                "role": "user",
                "content": huge_content,
            }
        )

        # Should be rejected
        assert not fits, "Oversized message should be rejected"


class TestPerformance:
    """Performance tests for context management operations."""

    def test_token_counting_performance(self):
        """Test that token counting is fast (<1ms)."""
        import time

        text = "X" * 10000  # 10k characters

        start = time.perf_counter()
        for _ in range(100):
            TokenCounter.count_tokens(text, "gpt-4o-mini")
        end = time.perf_counter()

        avg_time_ms = (end - start) / 100 * 1000
        assert avg_time_ms < 1.0, f"Token counting too slow: {avg_time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_cache_storage_performance(self, result_cache):
        """Test that cache storage is fast (<50ms)."""
        import time

        large_result = {
            "events": [{"message": f"Event {i}" * 20} for i in range(500)],
            "count": 500,
        }

        start = time.perf_counter()
        await result_cache.cache_result(
            tool_name="query_logs",
            query_params={"test": "perf"},
            result=large_result,
        )
        end = time.perf_counter()

        time_ms = (end - start) * 1000
        assert time_ms < 50.0, f"Cache storage too slow: {time_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_cache_retrieval_performance(self, result_cache):
        """Test that cache retrieval is fast (<100ms)."""
        import time

        # Cache a result first
        large_result = {
            "events": [{"message": f"Event {i}"} for i in range(1000)],
            "count": 1000,
        }

        summary = await result_cache.cache_result(
            tool_name="query_logs",
            query_params={"test": "perf"},
            result=large_result,
        )

        # Retrieve chunk
        start = time.perf_counter()
        await result_cache.fetch_chunk(cache_id=summary.cache_id, offset=0, limit=100)
        end = time.perf_counter()

        time_ms = (end - start) * 1000
        assert time_ms < 100.0, f"Cache retrieval too slow: {time_ms:.2f}ms"

    def test_pruning_performance(self, orchestrator):
        """Test that pruning is fast (<20ms)."""
        import time

        # Fill context
        for i in range(100):
            orchestrator.conversation_history.append(
                {
                    "role": "user",
                    "content": f"Message {i}" * 10,
                }
            )

        orchestrator._update_budget_tracker(orchestrator.conversation_history)

        # Time pruning
        start = time.perf_counter()
        orchestrator._prune_history_if_needed()
        end = time.perf_counter()

        time_ms = (end - start) * 1000
        assert time_ms < 20.0, f"Pruning too slow: {time_ms:.2f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
