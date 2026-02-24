"""Unit tests for ResultProcessor (MCP sanitization pipeline)."""

import asyncio
from unittest.mock import MagicMock

import pytest
from logai.core.sanitizer import LogSanitizer, SanitizationResult
from logai.providers.mcp.sanitization import ResultProcessor

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_sanitizer(enabled: bool = True) -> MagicMock:
    """Return a MagicMock that mimics an enabled LogSanitizer."""
    sanitizer = MagicMock(spec=LogSanitizer)
    sanitizer.enabled = enabled
    # sanitize() returns a SanitizationResult — replaces text with [REDACTED]
    sanitizer.sanitize.side_effect = lambda text: SanitizationResult(
        sanitized_text=text.replace("secret", "[REDACTED]"),
        redaction_count=1 if "secret" in text else 0,
        redactions={"generic": 1} if "secret" in text else {},
    )
    sanitizer.sanitize_log_events.side_effect = lambda events: (
        [{**e, "message": e.get("message", "").replace("secret", "[REDACTED]")} for e in events],
        {"generic": 1},
    )
    sanitizer.get_redaction_summary.return_value = "Redacted: 1 Generic"
    return sanitizer


@pytest.fixture
def enabled_sanitizer() -> MagicMock:
    return _make_sanitizer(enabled=True)


@pytest.fixture
def disabled_sanitizer() -> MagicMock:
    return _make_sanitizer(enabled=False)


@pytest.fixture
def processor(enabled_sanitizer: MagicMock) -> ResultProcessor:
    """Return a ResultProcessor backed by an enabled mock sanitizer."""
    return ResultProcessor(sanitizer=enabled_sanitizer)


# ---------------------------------------------------------------------------
# Strategy routing tests
# ---------------------------------------------------------------------------


class TestResultProcessorStrategyRouting:
    """Tests for per-tool strategy selection (passthrough vs. sanitize)."""

    @pytest.mark.asyncio
    async def test_passthrough_tools_not_sanitized(
        self, processor: ResultProcessor, enabled_sanitizer: MagicMock
    ) -> None:
        """describe_log_groups uses the passthrough strategy — sanitizer not called."""
        raw = {"logGroups": ["/aws/lambda/fn"], "count": 1}

        result = await processor.process("describe_log_groups", raw)

        # Passthrough: result unchanged and sanitize never invoked
        assert result == raw
        enabled_sanitizer.sanitize.assert_not_called()
        enabled_sanitizer.sanitize_log_events.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_tool_defaults_to_passthrough(
        self, processor: ResultProcessor, enabled_sanitizer: MagicMock
    ) -> None:
        """A tool name not in the strategy map passes through unchanged."""
        raw = {"someKey": "someValue"}

        result = await processor.process("totally_unknown_tool", raw)

        assert result == raw
        enabled_sanitizer.sanitize.assert_not_called()


# ---------------------------------------------------------------------------
# Insights-format sanitization tests
# ---------------------------------------------------------------------------


class TestResultProcessorInsightsSanitization:
    """Tests for sanitization of get_logs_insight_query_results results."""

    @pytest.mark.asyncio
    async def test_insights_results_sanitized(
        self, processor: ResultProcessor, enabled_sanitizer: MagicMock
    ) -> None:
        """For get_logs_insight_query_results, the results list values are sanitized."""
        raw = {
            "results": [
                {"@message": "user logged in with secret password", "@timestamp": "2024-01-01"},
                {"@message": "no sensitive data here", "@timestamp": "2024-01-01"},
            ]
        }

        result = await processor.process("get_logs_insight_query_results", raw)

        # The @message fields should have been passed through sanitizer.sanitize()
        enabled_sanitizer.sanitize.assert_called()
        messages = [r["@message"] for r in result["results"]]
        assert any("[REDACTED]" in m for m in messages)

    @pytest.mark.asyncio
    async def test_insights_results_sanitization_metadata_injected(
        self, processor: ResultProcessor
    ) -> None:
        """After processing insights results, a 'sanitization' dict is injected."""
        raw = {
            "results": [
                {"@message": "contains secret data", "@timestamp": "2024-01-01"},
            ]
        }

        result = await processor.process("get_logs_insight_query_results", raw)

        assert "sanitization" in result
        san = result["sanitization"]
        assert san["enabled"] is True
        assert "redactions" in san
        assert "summary" in san


# ---------------------------------------------------------------------------
# Events-format sanitization tests
# ---------------------------------------------------------------------------


class TestResultProcessorEventsSanitization:
    """Tests for sanitization of analyze_log_group results."""

    @pytest.mark.asyncio
    async def test_events_list_sanitized(
        self, processor: ResultProcessor, enabled_sanitizer: MagicMock
    ) -> None:
        """For analyze_log_group, the events list is passed through sanitize_log_events()."""
        raw = {
            "events": [
                {"message": "User secret123 logged in", "timestamp": "2024-01-01T00:00:00Z"},
                {"message": "Normal event", "timestamp": "2024-01-01T00:01:00Z"},
            ]
        }

        result = await processor.process("analyze_log_group", raw)

        # sanitize_log_events must have been called with the events list
        enabled_sanitizer.sanitize_log_events.assert_called_once_with(raw["events"])
        # Sanitization metadata injected
        assert "sanitization" in result
        assert result["sanitization"]["enabled"] is True


# ---------------------------------------------------------------------------
# No sanitizer / disabled sanitizer tests
# ---------------------------------------------------------------------------


class TestResultProcessorNoSanitizer:
    """Tests for ResultProcessor when no sanitizer is supplied."""

    @pytest.mark.asyncio
    async def test_no_sanitizer_passthrough(self) -> None:
        """With sanitizer=None, even log-returning tools pass through unchanged."""
        processor = ResultProcessor(sanitizer=None)
        raw = {"results": [{"@message": "secret data", "@timestamp": "2024-01-01"}]}

        result = await processor.process("get_logs_insight_query_results", raw)

        # No sanitization applied — result is identical to input
        assert result == raw

    @pytest.mark.asyncio
    async def test_disabled_sanitizer_is_passthrough(self, disabled_sanitizer: MagicMock) -> None:
        """When sanitizer.enabled=False, the sanitize strategy is skipped."""
        processor = ResultProcessor(sanitizer=disabled_sanitizer)
        raw = {"results": [{"@message": "secret data", "@timestamp": "2024-01-01"}]}

        result = await processor.process("get_logs_insight_query_results", raw)

        # sanitize must NOT be called because sanitizer.enabled is False
        disabled_sanitizer.sanitize.assert_not_called()
        # Result passes through unchanged
        assert result == raw


# ---------------------------------------------------------------------------
# Async API contract
# ---------------------------------------------------------------------------


class TestResultProcessorAsyncContract:
    """Tests verifying the async nature of ResultProcessor.process()."""

    def test_process_is_async(self) -> None:
        """ResultProcessor.process() must be a coroutine function."""
        assert asyncio.iscoroutinefunction(ResultProcessor.process)


# ---------------------------------------------------------------------------
# Non-dict result handling
# ---------------------------------------------------------------------------


class TestResultProcessorNonDictInput:
    """Tests for how ResultProcessor handles unexpected non-dict results."""

    @pytest.mark.asyncio
    async def test_non_dict_result_is_wrapped(self, processor: ResultProcessor) -> None:
        """A non-dict result (e.g. a list) is wrapped in ``{"raw_text": ...}``.

        ``MCPClientManager.call_tool()`` normally returns a dict, but defensive
        wrapping ensures that any unexpected value type is still returned as a
        valid dict rather than propagating a type error up the call stack.
        """
        result = await processor.process("describe_log_groups", ["unexpected", "list"])

        assert "raw_text" in result
