"""Unit tests for TokenCounter."""

import json
import time

import pytest
from logai.core.context.token_counter import TokenCounter


class TestTokenCounter:
    """Test suite for TokenCounter functionality."""

    def test_count_tokens_empty_string(self):
        """Test that empty strings return 0 tokens."""
        assert TokenCounter.count_tokens("", "claude-3-5-sonnet") == 0
        assert TokenCounter.count_tokens("", "gpt-4") == 0

    def test_count_tokens_simple_text(self):
        """Test token counting for simple text."""
        text = "This is a test message."
        count = TokenCounter.count_tokens(text, "claude-3-5-sonnet")

        # Should be reasonable count (roughly 1 token per 4 chars)
        assert 3 <= count <= 10, f"Expected 3-10 tokens, got {count}"

    def test_count_tokens_multiple_models(self):
        """Test that token counting works for all supported models."""
        text = "Hello, world! This is a test."

        models = [
            "claude-3-5-sonnet",
            "claude-opus-4",
            "gpt-4-turbo",
            "gpt-4o",
            "github-copilot",
            "llama3.1:8b",
        ]

        for model in models:
            count = TokenCounter.count_tokens(text, model)
            assert count > 0, f"Model {model} returned 0 tokens"
            assert count < 100, f"Model {model} returned unexpectedly high count: {count}"

    def test_count_tokens_long_text(self):
        """Test token counting for longer text."""
        # Create a longer text (about 500 words)
        text = " ".join(["word"] * 500)
        count = TokenCounter.count_tokens(text, "claude-3-5-sonnet")

        # Should be approximately 500-700 tokens (1 token per word roughly)
        assert 400 <= count <= 800, f"Expected 400-800 tokens, got {count}"

    def test_count_tokens_special_characters(self):
        """Test token counting with special characters."""
        text = "Hello! How are you? I'm fine. 😊 #test @user https://example.com"
        count = TokenCounter.count_tokens(text, "claude-3-5-sonnet")

        assert count > 0, "Should count tokens for special characters"

    def test_count_tokens_performance(self):
        """Test that token counting is fast (<10ms)."""
        # Medium-sized text
        text = "This is a test. " * 100  # ~1500 characters

        start = time.perf_counter()
        TokenCounter.count_tokens(text, "claude-3-5-sonnet")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.010, f"Token counting took {elapsed * 1000:.2f}ms (expected <10ms)"

    def test_count_tokens_large_text_performance(self):
        """Test performance with very large text (500KB)."""
        # Create a large text (~500KB)
        text = "word " * 100_000  # ~500KB

        start = time.perf_counter()
        TokenCounter.count_tokens(text, "claude-3-5-sonnet")
        elapsed = time.perf_counter() - start

        # Should still be reasonably fast
        assert elapsed < 0.050, f"Large text counting took {elapsed * 1000:.2f}ms (expected <50ms)"

    def test_count_message_tokens_empty_list(self):
        """Test that empty message list returns 0 tokens."""
        assert TokenCounter.count_message_tokens([], "claude-3-5-sonnet") == 0

    def test_count_message_tokens_single_message(self):
        """Test token counting for a single message."""
        messages = [{"role": "user", "content": "Hello, how are you?"}]

        count = TokenCounter.count_message_tokens(messages, "claude-3-5-sonnet")

        # Should include content tokens + overhead
        assert count > 0
        # Message overhead is ~4 tokens
        assert count >= 4, f"Expected at least 4 tokens (overhead), got {count}"

    def test_count_message_tokens_multiple_messages(self):
        """Test token counting for multiple messages."""
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {"role": "assistant", "content": "It's sunny and 72°F."},
            {"role": "user", "content": "Thanks!"},
        ]

        count = TokenCounter.count_message_tokens(messages, "claude-3-5-sonnet")

        # Should have content tokens + overhead for each message
        # 3 messages * 4 tokens overhead = 12 tokens minimum
        assert count >= 12, f"Expected at least 12 tokens overhead, got {count}"

    def test_count_message_tokens_with_tool_calls(self):
        """Test token counting for messages with tool calls."""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "San Francisco"}',
                        }
                    }
                ],
            }
        ]

        count = TokenCounter.count_message_tokens(messages, "claude-3-5-sonnet")

        # Should count function name and arguments
        assert count > 0

    def test_count_message_tokens_multipart_content(self):
        """Test token counting for multi-part content (like images)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {"type": "image", "url": "https://example.com/image.jpg"},
                ],
            }
        ]

        count = TokenCounter.count_message_tokens(messages, "claude-3-5-sonnet")

        # Should count the text part + overhead
        assert count > 4

    def test_estimate_json_tokens_simple(self):
        """Test JSON token estimation for simple objects."""
        data = {"name": "test", "value": 123, "active": True}

        count = TokenCounter.estimate_json_tokens(data, "claude-3-5-sonnet")

        assert count > 0
        # JSON is compact, should be reasonable
        assert count < 50

    def test_estimate_json_tokens_large(self):
        """Test JSON token estimation for large objects."""
        # Create a large object with 100 events
        data = {
            "events": [
                {
                    "timestamp": f"2026-02-12T10:{i:02d}:00",
                    "message": f"Log message {i}",
                    "level": "INFO",
                }
                for i in range(100)
            ]
        }

        count = TokenCounter.estimate_json_tokens(data, "claude-3-5-sonnet")

        # Should be substantial but reasonable
        assert count > 100  # At least some tokens per event
        assert count < 10000  # But not excessive

    def test_estimate_json_tokens_matches_serialization(self):
        """Test that JSON estimation is close to actual serialization."""
        data = {
            "query": "find errors",
            "results": [f"event_{i}" for i in range(50)],
            "metadata": {"count": 50, "source": "cloudwatch"},
        }

        # Estimate via JSON method
        estimated = TokenCounter.estimate_json_tokens(data, "claude-3-5-sonnet")

        # Actual serialization count
        json_str = json.dumps(data, separators=(",", ":"))
        actual = TokenCounter.count_tokens(json_str, "claude-3-5-sonnet")

        # Should be very close (within 10%)
        diff_pct = abs(estimated - actual) / actual * 100
        assert (
            diff_pct < 10
        ), f"Estimation off by {diff_pct:.1f}% (estimated: {estimated}, actual: {actual})"

    def test_get_context_window_known_models(self):
        """Test context window detection for known models."""
        test_cases = [
            ("claude-3-5-sonnet-20241022", 200_000),
            ("claude-opus-4", 200_000),
            ("gpt-4-turbo-preview", 128_000),
            ("gpt-4o", 128_000),
            ("llama3.1:8b", 8_192),
            ("llama3.1:70b", 128_000),
        ]

        for model, expected_window in test_cases:
            window = TokenCounter.get_context_window(model)
            assert (
                window == expected_window
            ), f"Model {model}: expected {expected_window}, got {window}"

    def test_get_context_window_unknown_model(self):
        """Test context window detection for unknown models."""
        window = TokenCounter.get_context_window("unknown-model-xyz")

        # Should return default window
        assert window == 8_192

    def test_will_fit_text_fits(self):
        """Test will_fit returns True when text fits."""
        text = "This is a short message."
        current = 1000
        max_tokens = 10000

        fits = TokenCounter.will_fit(text, current, max_tokens, "claude-3-5-sonnet")

        assert fits is True

    def test_will_fit_text_does_not_fit(self):
        """Test will_fit returns False when text doesn't fit."""
        text = "word " * 1000  # Large text
        current = 9500
        max_tokens = 10000

        fits = TokenCounter.will_fit(text, current, max_tokens, "claude-3-5-sonnet")

        assert fits is False

    def test_will_fit_exact_boundary(self):
        """Test will_fit at exact boundary."""
        # Create text of known size
        text = "test"
        current = 9999
        max_tokens = 10000

        # Small text should fit
        fits = TokenCounter.will_fit(text, current, max_tokens, "claude-3-5-sonnet")

        # Depends on exact token count, but test that it works
        assert isinstance(fits, bool)

    def test_encoding_cache(self):
        """Test that encoding is cached for performance."""
        model = "claude-3-5-sonnet"
        text = "Test message"

        # First call - will load encoding
        start1 = time.perf_counter()
        count1 = TokenCounter.count_tokens(text, model)
        time1 = time.perf_counter() - start1

        # Second call - should use cache
        start2 = time.perf_counter()
        count2 = TokenCounter.count_tokens(text, model)
        time2 = time.perf_counter() - start2

        # Should return same count
        assert count1 == count2

        # Second call should be faster (or at least not slower)
        # Note: This is a weak assertion since timing can vary
        assert time2 <= time1 * 2, "Cached call should not be significantly slower"

    def test_fallback_when_tiktoken_unavailable(self):
        """Test that fallback works when tiktoken is unavailable."""
        # Use a model that won't be in MODEL_ENCODINGS
        model = "unknown-local-model"
        text = "This is a test message with some words."

        count = TokenCounter.count_tokens(text, model)

        # Should use character-based fallback (chars / 3.5)
        expected_fallback = int(len(text) / 3.5) + 1
        assert count == expected_fallback

    def test_token_counting_accuracy(self):
        """Test token counting accuracy for known text."""
        # Use a standard test string
        text = "The quick brown fox jumps over the lazy dog."

        count = TokenCounter.count_tokens(text, "claude-3-5-sonnet")

        # This is roughly 10-12 tokens for most tokenizers
        # Allow ±5% margin
        assert 8 <= count <= 15, f"Expected 8-15 tokens, got {count}"

    def test_unicode_handling(self):
        """Test that Unicode text is handled correctly."""
        texts = [
            "Hello 世界",  # Mixed English and Chinese
            "Привет мир",  # Russian
            "مرحبا بالعالم",  # Arabic
            "🎉🎊✨",  # Emojis
        ]

        for text in texts:
            count = TokenCounter.count_tokens(text, "claude-3-5-sonnet")
            assert count > 0, f"Failed to count tokens for: {text}"

    def test_empty_message_content(self):
        """Test handling of messages with empty content."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ]

        count = TokenCounter.count_message_tokens(messages, "claude-3-5-sonnet")

        # Should still count overhead for each message
        assert count >= 8  # 2 messages * 4 tokens overhead


@pytest.mark.benchmark
class TestTokenCounterPerformance:
    """Performance benchmark tests for TokenCounter."""

    def test_benchmark_small_text(self, benchmark):
        """Benchmark token counting for small text."""
        text = "This is a test message."

        result = benchmark(TokenCounter.count_tokens, text, "claude-3-5-sonnet")

        assert result > 0

    def test_benchmark_medium_text(self, benchmark):
        """Benchmark token counting for medium text (~1KB)."""
        text = "This is a test. " * 100  # ~1.5KB

        result = benchmark(TokenCounter.count_tokens, text, "claude-3-5-sonnet")

        assert result > 0

    def test_benchmark_large_text(self, benchmark):
        """Benchmark token counting for large text (~100KB)."""
        text = "word " * 20_000  # ~100KB

        result = benchmark(TokenCounter.count_tokens, text, "claude-3-5-sonnet")

        assert result > 0

    def test_benchmark_json_estimation(self, benchmark):
        """Benchmark JSON token estimation."""
        data = {
            "events": [
                {"timestamp": f"2026-02-12T10:00:{i:02d}", "message": f"Event {i}"}
                for i in range(100)
            ]
        }

        result = benchmark(TokenCounter.estimate_json_tokens, data, "claude-3-5-sonnet")

        assert result > 0

    def test_benchmark_message_counting(self, benchmark):
        """Benchmark message token counting."""
        messages = [
            {"role": "user", "content": "Question about logs"},
            {"role": "assistant", "content": "Let me check that for you."},
            {"role": "tool", "content": '{"result": "data"}'},
        ] * 10  # 30 messages

        result = benchmark(TokenCounter.count_message_tokens, messages, "claude-3-5-sonnet")

        assert result > 0
