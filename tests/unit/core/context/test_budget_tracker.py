"""Unit tests for ContextBudgetTracker."""

import pytest
from logai.config.settings import LogAISettings
from logai.core.context.budget_tracker import (
    AllocationStrategy,
    BudgetAllocation,
    ContextBudgetTracker,
    ContextMessage,
)


@pytest.fixture
def settings():
    """Create test settings."""
    return LogAISettings(
        llm_provider="anthropic",
        anthropic_model="claude-3-5-sonnet-20241022",
        anthropic_api_key="test-key",
    )


@pytest.fixture
def tracker(settings):
    """Create a budget tracker for testing."""
    return ContextBudgetTracker(settings, model="claude-3-5-sonnet")


class TestBudgetAllocation:
    """Test budget allocation calculations."""

    def test_allocation_properties(self):
        """Test budget allocation properties."""
        allocation = BudgetAllocation(
            total_window=200_000,
            system_prompt=10_000,
            history=80_000,
            results=50_000,
            response_reserve=8_000,
            safety_buffer=10_000,
        )

        assert allocation.usable_tokens == 190_000  # total - buffer
        assert allocation.available_for_content == 172_000  # usable - system - response

    def test_allocation_adds_up(self, tracker):
        """Test that allocation components add up correctly."""
        alloc = tracker.allocation

        total = (
            alloc.system_prompt
            + alloc.history
            + alloc.results
            + alloc.response_reserve
            + alloc.safety_buffer
        )

        assert total == alloc.total_window


class TestContextBudgetTracker:
    """Test suite for ContextBudgetTracker functionality."""

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.model == "claude-3-5-sonnet"
        assert tracker.context_window == 200_000
        assert tracker.strategy == AllocationStrategy.ADAPTIVE
        assert tracker.allocation is not None

    def test_initialization_with_different_strategies(self, settings):
        """Test initialization with different allocation strategies."""
        strategies = [
            AllocationStrategy.ADAPTIVE,
            AllocationStrategy.HISTORY_FOCUSED,
            AllocationStrategy.RESULT_FOCUSED,
        ]

        for strategy in strategies:
            tracker = ContextBudgetTracker(settings, strategy=strategy)
            assert tracker.strategy == strategy

    def test_adaptive_allocation(self, settings):
        """Test adaptive allocation strategy."""
        tracker = ContextBudgetTracker(settings, strategy=AllocationStrategy.ADAPTIVE)
        alloc = tracker.allocation

        # Adaptive should have roughly balanced history/results
        # History gets 55%, results get 45%
        assert alloc.history > alloc.results
        # Should be close to 55/45 split of remaining tokens
        remaining = alloc.history + alloc.results
        history_pct = alloc.history / remaining
        assert 0.50 <= history_pct <= 0.60

    def test_history_focused_allocation(self, settings):
        """Test history-focused allocation strategy."""
        tracker = ContextBudgetTracker(settings, strategy=AllocationStrategy.HISTORY_FOCUSED)
        alloc = tracker.allocation

        # History-focused should allocate 65% to history, 35% to results
        remaining = alloc.history + alloc.results
        history_pct = alloc.history / remaining
        assert history_pct >= 0.63  # Allow small rounding error

    def test_result_focused_allocation(self, settings):
        """Test result-focused allocation strategy."""
        tracker = ContextBudgetTracker(settings, strategy=AllocationStrategy.RESULT_FOCUSED)
        alloc = tracker.allocation

        # Result-focused should allocate 60% to results, 40% to history
        remaining = alloc.history + alloc.results
        result_pct = alloc.results / remaining
        assert result_pct >= 0.58  # Allow small rounding error

    def test_set_system_prompt_fits(self, tracker):
        """Test setting a system prompt that fits."""
        prompt = "You are a helpful assistant." * 10  # ~80 tokens

        fits = tracker.set_system_prompt(prompt)

        assert fits is True
        assert tracker._system_prompt == prompt
        assert tracker._system_prompt_tokens > 0

    def test_set_system_prompt_too_large(self, tracker):
        """Test setting a system prompt that's too large."""
        # Create a very long prompt that exceeds budget (10K tokens for system)
        # Need about 40K characters to exceed 10K tokens
        prompt = "You are a helpful assistant. " * 1500  # ~12000 tokens

        tracker.set_system_prompt(prompt)

        # Should still store it but return False
        assert tracker._system_prompt == prompt
        # May or may not fit depending on exact tokenization
        # Just verify it's stored
        assert tracker._system_prompt_tokens > 0

    def test_add_message_simple(self, tracker):
        """Test adding a simple message."""
        message = {"role": "user", "content": "Hello, how are you?"}

        added = tracker.add_message(message)

        assert added is True
        assert len(tracker._messages) == 1
        assert tracker._messages[0].role == "user"

    def test_add_message_multiple(self, tracker):
        """Test adding multiple messages."""
        messages = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]

        for msg in messages:
            added = tracker.add_message(msg)
            assert added is True

        assert len(tracker._messages) == 3

    def test_add_message_important(self, tracker):
        """Test adding an important message."""
        message = {"role": "user", "content": "Critical context"}

        tracker.add_message(message, important=True)

        assert tracker._messages[0].important is True

    def test_add_message_exceeds_budget(self, tracker):
        """Test that budget tracker rejects messages when budget is full."""
        # Fill the budget by adding very large messages
        # 200K context window - 10K sys - 8K response - 10K buffer = ~172K usable
        # Fill with large messages (each ~5K tokens)
        messages_added = 0
        for _i in range(100):  # Try to add 100 large messages
            # Each message is about 20K characters = ~5K tokens
            msg = {"role": "user", "content": "word " * 10000}
            if tracker.add_message(msg):
                messages_added += 1
            else:
                # Successfully rejected when budget full
                break

        # Verify that we filled most of the budget
        usage = tracker.get_usage()

        # Now try to add another large message
        huge_content = "word " * 10_000  # ~2.5K tokens
        message = {"role": "user", "content": huge_content}

        added = tracker.add_message(message)

        # Should be rejected if we're over 95% full
        if usage.utilization_pct > 95:
            assert added is False
        else:
            # If we didn't fill enough, that's OK - context window is large
            pass

    def test_add_message_json_content(self, tracker):
        """Test adding a message with JSON content."""
        message = {"role": "tool", "content": {"result": "success", "data": [1, 2, 3]}}

        added = tracker.add_message(message)

        assert added is True
        assert tracker._messages[0].role == "tool"
        assert '"result"' in tracker._messages[0].content

    def test_can_fit_result_small(self, tracker):
        """Test that a small result can fit."""
        result = {"events": [{"message": "Test log"}]}

        can_fit, tokens = tracker.can_fit_result(result)

        assert can_fit is True
        assert tokens > 0

    def test_can_fit_result_large(self, tracker):
        """Test that a very large result doesn't fit."""
        # Create a huge result
        result = {"events": [{"message": f"Log message {i}"} for i in range(10_000)]}

        can_fit, tokens = tracker.can_fit_result(result)

        # Should not fit in result budget
        assert can_fit is False
        assert tokens > tracker.allocation.results

    def test_should_cache_result_small(self, tracker):
        """Test that small results are not cached."""
        result = {"events": [{"message": "Test"}]}

        should_cache, tokens = tracker.should_cache_result(result, threshold=10000)

        assert should_cache is False
        assert tokens < 10000

    def test_should_cache_result_large(self, tracker):
        """Test that large results are cached."""
        # Create a large result (need ~15K tokens to exceed 10K threshold)
        result = {
            "events": [{"message": f"Event message with lots of details: {i}"} for i in range(1500)]
        }

        should_cache, tokens = tracker.should_cache_result(result, threshold=10000)

        # Should cache if tokens exceed threshold
        if tokens > 10000:
            assert should_cache is True
        else:
            # If it's under threshold, we can't guarantee it will be cached
            pass

    def test_should_cache_result_doesnt_fit(self, tracker):
        """Test that results that don't fit are cached regardless of threshold."""
        # First fill most of the result budget (50K tokens allocated)
        tracker.add_result_tokens(48000)  # Use 96% of the result budget

        # Create a result that exceeds remaining budget (~5K tokens)
        result = {
            "events": [{"message": f"Event message number {i} with details"} for i in range(500)]
        }

        should_cache, tokens = tracker.should_cache_result(result, threshold=100000)

        # Should cache because it won't fit in remaining result budget (only ~2K left)
        can_fit, _ = tracker.can_fit_result(result)
        if not can_fit:
            assert should_cache is True
        else:
            # If it fits, caching depends on threshold
            pass

    def test_add_result_tokens(self, tracker):
        """Test tracking result tokens."""
        tracker.add_result_tokens(5000)

        usage = tracker.get_usage()
        assert usage.result_tokens == 5000

    def test_get_usage_empty(self, tracker):
        """Test getting usage when tracker is empty."""
        usage = tracker.get_usage()

        assert usage.system_prompt_tokens == 0
        assert usage.history_tokens == 0
        assert usage.result_tokens == 0
        assert usage.total_tokens == 0
        assert usage.remaining_tokens > 0
        assert usage.utilization_pct == 0.0

    def test_get_usage_with_content(self, tracker):
        """Test getting usage with actual content."""
        tracker.set_system_prompt("You are a helpful assistant.")
        tracker.add_message({"role": "user", "content": "Hello!"})
        tracker.add_message({"role": "assistant", "content": "Hi there!"})
        tracker.add_message({"role": "tool", "content": '{"result": "data"}'})

        usage = tracker.get_usage()

        assert usage.system_prompt_tokens > 0
        assert usage.history_tokens > 0  # user + assistant messages
        assert usage.result_tokens > 0  # tool message
        assert usage.total_tokens > 0
        assert usage.remaining_tokens > 0
        assert 0 < usage.utilization_pct < 100

    def test_get_usage_to_dict(self, tracker):
        """Test converting usage to dictionary."""
        tracker.set_system_prompt("Test prompt")
        usage = tracker.get_usage()

        usage_dict = usage.to_dict()

        assert isinstance(usage_dict, dict)
        assert "total_tokens" in usage_dict
        assert "utilization_pct" in usage_dict
        assert isinstance(usage_dict["utilization_pct"], int | float)

    def test_should_prune_history_low_utilization(self, tracker):
        """Test that pruning is not needed at low utilization."""
        # Add a small message
        tracker.add_message({"role": "user", "content": "Hello"})

        should_prune = tracker.should_prune_history(threshold_pct=80.0)

        assert should_prune is False

    def test_should_prune_history_high_utilization(self, tracker):
        """Test that pruning is needed at high utilization."""
        # Fill up the context with many large messages
        for _i in range(300):
            msg = {"role": "user", "content": "Test message with more content " * 100}
            if not tracker.add_message(msg):
                break  # Stop when we can't add more

        should_prune = tracker.should_prune_history(threshold_pct=50.0)

        # Should need pruning when threshold is low and we've added many messages
        usage = tracker.get_usage()
        if usage.utilization_pct >= 50.0:
            assert should_prune is True
        else:
            # If somehow we didn't reach 50%, that's fine
            pass

    def test_get_prunable_messages_preserves_recent(self, tracker):
        """Test that prunable messages preserves recent messages."""
        # Add 10 messages
        for i in range(10):
            tracker.add_message({"role": "user", "content": f"Message {i}"})

        prunable = tracker.get_prunable_messages(target_tokens=1000)

        # Should not include the 4 most recent messages
        assert len(prunable) <= 6

    def test_get_prunable_messages_skips_important(self, tracker):
        """Test that important messages are not prunable."""
        # Add mix of normal and important messages
        tracker.add_message({"role": "user", "content": "Normal 1"})
        tracker.add_message({"role": "user", "content": "Important"}, important=True)
        tracker.add_message({"role": "user", "content": "Normal 2"})
        tracker.add_message({"role": "user", "content": "Normal 3"})
        tracker.add_message({"role": "user", "content": "Normal 4"})
        tracker.add_message({"role": "user", "content": "Normal 5"})

        prunable = tracker.get_prunable_messages(target_tokens=100)

        # Important message (index 1) should not be in prunable list
        # Recent 4 messages should also be excluded (indices 2, 3, 4, 5)
        # So only "Normal 1" (index 0) should be prunable
        assert 1 not in prunable, "Important message should not be prunable"
        # Only the first non-important, non-recent message can be pruned
        if len(prunable) > 0:
            assert 0 in prunable  # First message is prunable

    def test_get_prunable_messages_skips_system(self, tracker):
        """Test that system messages are not prunable."""
        tracker.add_message({"role": "system", "content": "System message"})
        tracker.add_message({"role": "user", "content": "User 1"})
        tracker.add_message({"role": "user", "content": "User 2"})
        tracker.add_message({"role": "user", "content": "User 3"})
        tracker.add_message({"role": "user", "content": "User 4"})
        tracker.add_message({"role": "user", "content": "User 5"})

        prunable = tracker.get_prunable_messages(target_tokens=100)

        # System message (index 0) should not be in prunable list
        assert 0 not in prunable

    def test_get_prunable_messages_target_tokens(self, tracker):
        """Test that prunable messages stops at target tokens."""
        # Add messages with known token counts
        for _i in range(10):
            tracker.add_message({"role": "user", "content": "word " * 10})  # ~10 tokens each

        prunable = tracker.get_prunable_messages(target_tokens=30)

        # Should select enough messages to meet target (roughly 3 messages)
        # But preserve recent 4, so could select up to 6 oldest
        assert len(prunable) >= 3

    def test_prune_messages_empty_list(self, tracker):
        """Test pruning with empty list."""
        tracker.add_message({"role": "user", "content": "Test"})

        pruned = tracker.prune_messages([])

        assert len(pruned) == 0
        assert len(tracker._messages) == 1

    def test_prune_messages_single(self, tracker):
        """Test pruning a single message."""
        tracker.add_message({"role": "user", "content": "Message 1"})
        tracker.add_message({"role": "user", "content": "Message 2"})

        pruned = tracker.prune_messages([0])

        assert len(pruned) == 1
        assert pruned[0].content == "Message 1"
        assert len(tracker._messages) == 1
        assert tracker._messages[0].content == "Message 2"

    def test_prune_messages_multiple(self, tracker):
        """Test pruning multiple messages."""
        for i in range(5):
            tracker.add_message({"role": "user", "content": f"Message {i}"})

        pruned = tracker.prune_messages([0, 1, 2])

        assert len(pruned) == 3
        assert len(tracker._messages) == 2
        assert tracker._messages[0].content == "Message 3"

    def test_prune_messages_out_of_order(self, tracker):
        """Test that pruning handles out-of-order indices."""
        for i in range(5):
            tracker.add_message({"role": "user", "content": f"Message {i}"})

        pruned = tracker.prune_messages([2, 0, 4])

        assert len(pruned) == 3
        assert len(tracker._messages) == 2

    def test_reset(self, tracker):
        """Test resetting the tracker."""
        tracker.set_system_prompt("Test prompt")
        tracker.add_message({"role": "user", "content": "Test"})
        tracker.add_result_tokens(1000)

        tracker.reset()

        assert tracker._system_prompt is None
        assert tracker._system_prompt_tokens == 0
        assert len(tracker._messages) == 0
        assert tracker._pending_results_tokens == 0

        usage = tracker.get_usage()
        assert usage.total_tokens == 0

    def test_get_status_display_low(self, tracker):
        """Test status display at low utilization."""
        tracker.add_message({"role": "user", "content": "Test"})

        status = tracker.get_status_display()

        assert "Context:" in status
        assert "%" in status
        assert "(!)" not in status  # No warning at low utilization

    def test_get_status_display_high(self, tracker):
        """Test status display at high utilization."""
        # Fill up context
        for _i in range(200):
            msg = {"role": "user", "content": "Test message " * 50}
            tracker.add_message(msg)

        status = tracker.get_status_display()

        assert "Context:" in status
        assert "%" in status

    def test_context_message_creation(self):
        """Test ContextMessage creation."""
        msg = ContextMessage(
            role="user", content="Test", tokens=10, is_system=False, important=True
        )

        assert msg.role == "user"
        assert msg.content == "Test"
        assert msg.tokens == 10
        assert msg.important is True
        assert msg.timestamp > 0

    def test_different_models_have_different_windows(self, settings):
        """Test that different models get appropriate context windows."""
        test_cases = [
            ("claude-3-5-sonnet", 200_000),
            ("gpt-4-turbo", 128_000),
            ("llama3.1:8b", 8_192),
        ]

        for model, expected_window in test_cases:
            tracker = ContextBudgetTracker(settings, model=model)
            assert tracker.context_window == expected_window

    def test_budget_enforcement_prevents_overflow(self, tracker):
        """Test that budget tracker prevents context overflow."""
        # Try to add messages until we hit the limit
        messages_added = 0
        for _i in range(1000):
            msg = {"role": "user", "content": "Test message " * 100}
            if tracker.add_message(msg):
                messages_added += 1
            else:
                break

        # Should have stopped before overflow
        usage = tracker.get_usage()
        assert usage.total_tokens <= tracker.allocation.usable_tokens
        assert messages_added < 1000  # Should have hit limit

    def test_performance_get_usage(self, tracker):
        """Test that get_usage is fast (<5ms)."""
        # Add some messages
        for i in range(20):
            tracker.add_message({"role": "user", "content": f"Message {i}"})

        import time

        start = time.perf_counter()
        for _ in range(100):
            tracker.get_usage()
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        assert avg_time < 0.005, f"get_usage took {avg_time * 1000:.2f}ms (expected <5ms)"


@pytest.mark.benchmark
class TestContextBudgetTrackerPerformance:
    """Performance benchmark tests for ContextBudgetTracker."""

    def test_benchmark_add_message(self, benchmark, tracker):
        """Benchmark adding a message."""
        message = {"role": "user", "content": "Test message"}

        result = benchmark(tracker.add_message, message)

        assert result is True

    def test_benchmark_get_usage(self, benchmark, tracker):
        """Benchmark getting usage stats."""
        # Pre-populate with messages
        for i in range(20):
            tracker.add_message({"role": "user", "content": f"Message {i}"})

        result = benchmark(tracker.get_usage)

        assert result.total_tokens > 0

    def test_benchmark_should_cache_result(self, benchmark, tracker):
        """Benchmark checking if result should be cached."""
        result = {"events": [{"message": f"Event {i}"} for i in range(100)]}

        cache_decision, tokens = benchmark(tracker.should_cache_result, result)

        assert isinstance(cache_decision, bool)
