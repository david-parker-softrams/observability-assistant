"""Unit tests for MCP-related behaviour in LLMOrchestrator._get_system_prompt().

Verifies that MCP guidance strings are always present (MCP is now the only
supported tool mode).  The orchestrator fixture pattern mirrors
``tests/unit/test_orchestrator.py``.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> Mock:
    """Return a fully-populated mock settings object.

    Mirrors the ``create_mock_settings`` helper in ``test_orchestrator.py`` so
    both test modules use the same baseline, with only the MCP toggle differing.
    """
    settings = Mock(spec=LogAISettings)
    settings.pii_sanitization_enabled = True
    settings.max_retry_attempts = 3
    settings.intent_detection_enabled = True
    settings.auto_retry_enabled = True
    settings.time_expansion_factor = 4.0
    settings.max_tool_iterations = 10
    settings.current_llm_model = "claude-3-5-sonnet-20241022"
    settings.enable_result_caching = True
    settings.cache_dir = Path("/tmp/cache")
    settings.cache_large_results_threshold = 5000
    settings.max_result_tokens = 10000
    settings.initial_chunk_size = 25
    settings.enable_auto_fetch_guidance = True
    settings.cache_sample_event_count = 5
    settings.enable_history_pruning = True
    settings.emergency_prune_threshold = 5000  # token count threshold (matches default)
    settings.context_warning_threshold_pct = 80.0
    settings.orchestrator_retry_delays = "1.0,2.0,4.0"
    settings.orchestrator_retry_delays_list = [1.0, 2.0, 4.0]

    for key, value in overrides.items():
        setattr(settings, key, value)

    return settings


@pytest.fixture
def mock_llm_provider():
    """Minimal async-capable LLM provider mock."""
    provider = AsyncMock()
    return provider


@pytest.fixture
def mock_tool_registry():
    """Minimal tool registry mock."""
    registry = Mock(spec=ToolRegistry)
    registry.to_function_definitions = Mock(return_value=[])
    registry.execute = AsyncMock()
    return registry


@pytest.fixture
def mock_sanitizer():
    """Minimal sanitizer mock."""
    sanitizer = Mock(spec=LogSanitizer)
    sanitizer.enabled = True
    return sanitizer


def _make_orchestrator(mock_llm_provider, mock_tool_registry, mock_sanitizer, **setting_overrides):
    """Construct an ``LLMOrchestrator`` with the given settings overrides."""
    settings = _make_settings(**setting_overrides)
    return LLMOrchestrator(
        llm_provider=mock_llm_provider,
        tool_registry=mock_tool_registry,
        sanitizer=mock_sanitizer,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Tests for _get_system_prompt() MCP guidance injection
# ---------------------------------------------------------------------------


class TestGetSystemPromptMcpGuidance:
    """Tests for the MCP guidance block injected by ``_get_system_prompt()``."""

    def test_mcp_guidance_always_present(
        self,
        mock_llm_provider,
        mock_tool_registry,
        mock_sanitizer,
    ) -> None:
        """The system prompt must always include all three MCP tool names.

        MCP is now the only supported tool mode, so ``_MCP_LOGS_INSIGHTS_GUIDANCE``
        is unconditionally appended to every system prompt.  The block names the
        three tools the LLM needs to interact with the AWS CloudWatch MCP server.
        """
        orchestrator = _make_orchestrator(
            mock_llm_provider,
            mock_tool_registry,
            mock_sanitizer,
        )

        prompt = orchestrator._get_system_prompt()

        assert (
            "execute_log_insights_query" in prompt
        ), "System prompt must always mention execute_log_insights_query"
        assert "get_logs_insight_query_results" in prompt, (
            "System prompt must warn the LLM not to call get_logs_insight_query_results "
            "(execute_log_insights_query already polls for results internally)"
        )
        assert (
            "describe_log_groups" in prompt
        ), "System prompt must always mention describe_log_groups"


# ---------------------------------------------------------------------------
# §6.3.3 — New test: MCP guidance example query uses limit 50 (not 100)
# ---------------------------------------------------------------------------


class TestMcpGuidanceQueryLimits:
    """Tests verifying that _MCP_LOGS_INSIGHTS_GUIDANCE uses conservative query limits."""

    def test_mcp_guidance_uses_limit_50_in_show_recent_example(self) -> None:
        """Test MCP guidance example query uses limit 50 for recent logs."""
        from logai.core.orchestrator import _MCP_LOGS_INSIGHTS_GUIDANCE

        assert (
            "limit 50" in _MCP_LOGS_INSIGHTS_GUIDANCE or "limit 50`" in _MCP_LOGS_INSIGHTS_GUIDANCE
        )
        # The old limit 100 should no longer appear in the "Show recent logs" example
        assert "sort @timestamp desc | limit 100" not in _MCP_LOGS_INSIGHTS_GUIDANCE
