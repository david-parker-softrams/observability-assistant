"""LLM Orchestrator - coordinates LLM interactions with tool execution."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.context.budget_tracker import ContextBudgetTracker
from logai.core.context.result_cache import ResultCacheManager
from logai.core.context.token_counter import TokenCounter
from logai.core.intent_detector import IntentDetector
from logai.core.metrics import MetricsCollector, MetricsTimer
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

# Set up logger for retry behavior monitoring
logger = logging.getLogger(__name__)


@dataclass
class ActiveCacheContext:
    """
    Tracks active cached dataset for follow-up detection and limit enforcement.

    This dataclass supports Phase 1 (Separate Message Timing) approach where:
    - Cache is created but no immediate guidance is injected
    - Follow-up questions are detected and trigger guidance injection
    - Fetch counts are tracked per cache_id per conversation turn
    """

    cache_id: str
    total_events: int
    created_at: float
    tool_name: str
    chunks_fetched: int = 0

    def is_recent(self, max_age_seconds: float = 600) -> bool:
        """
        Check if cache is recent enough for follow-up detection.

        Args:
            max_age_seconds: Maximum age in seconds (default 10 minutes per approved params)

        Returns:
            True if cache was created within max_age_seconds
        """
        return (time.time() - self.created_at) < max_age_seconds

    def increment_fetch_count(self) -> int:
        """Increment and return new fetch count."""
        self.chunks_fetched += 1
        return self.chunks_fetched

    def is_over_limit(self, max_fetches: int) -> bool:
        """
        Check if fetch count exceeds limit.

        Args:
            max_fetches: Maximum number of fetches allowed

        Returns:
            True if limit has been reached or exceeded
        """
        return self.chunks_fetched >= max_fetches


class OrchestratorError(Exception):
    """Raised when orchestrator encounters an error."""

    pass


class ToolCallStatus:
    """Status constants for tool call execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ToolCallRecord:
    """
    Represents a single tool call for tracking and display.

    Attributes:
        id: Unique identifier (matches tool_call_id from LLM)
        name: Tool name (e.g., "list_log_groups", "query_logs")
        arguments: Parameters passed to the tool
        result: Return value from tool execution
        status: Current execution status
        started_at: When execution started
        completed_at: When execution completed (None if still running)
        error_message: Error details if status is ERROR
    """

    id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    status: str = ToolCallStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error_message: str | None = None

    @property
    def duration_ms(self) -> int | None:
        """Calculate execution duration in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    @property
    def is_complete(self) -> bool:
        """Check if tool call has finished (success or error)."""
        return self.status in (ToolCallStatus.SUCCESS, ToolCallStatus.ERROR)


@dataclass
class RetryState:
    """Tracks retry attempts within a conversation turn.

    This class maintains state about retry attempts to prevent infinite loops
    and track what strategies have already been tried.

    Attributes:
        attempts: Number of retry attempts made
        empty_result_count: Count of empty results encountered
        strategies_tried: List of strategies that have been attempted
        last_tool_name: Name of the last tool that was called
        last_tool_args: Arguments passed to the last tool call
    """

    attempts: int = 0
    empty_result_count: int = 0
    strategies_tried: list[str] = field(default_factory=list)
    last_tool_name: str | None = None
    last_tool_args: dict[str, Any] | None = None

    def should_retry(self, max_attempts: int) -> bool:
        """Determine if we should attempt a retry.

        Args:
            max_attempts: Maximum number of attempts allowed

        Returns:
            True if we haven't exceeded the retry limit
        """
        return self.attempts < max_attempts

    def record_attempt(self, tool_name: str, args: dict[str, Any], strategy: str) -> None:
        """Record a retry attempt.

        Args:
            tool_name: Name of the tool being retried
            args: Arguments for the tool call
            strategy: The retry strategy being used
        """
        self.attempts += 1
        self.last_tool_name = tool_name
        self.last_tool_args = args
        self.strategies_tried.append(strategy)

    def record_empty_result(self) -> None:
        """Record an empty result occurrence."""
        self.empty_result_count += 1

    def reset(self) -> None:
        """Reset state for new conversation turn."""
        self.attempts = 0
        self.empty_result_count = 0
        self.strategies_tried.clear()
        self.last_tool_name = None
        self.last_tool_args = None


@dataclass
class ConversationLoopResult:
    """Result returned by _run_conversation_loop().

    Attributes:
        content: The final text content — either the LLM's response, a
            graceful error message, or a max-iterations notice.
        is_error: True when content is an error message rather than a
            normal LLM response.
        error_exception: The original exception object if is_error is True
            and the error originated from a caught exception.
            _chat_complete() will re-raise this; _chat_stream() ignores it.
    """

    content: str
    is_error: bool = False
    error_exception: Exception | None = None


class RetryPromptGenerator:
    """Generates guidance prompts for retry attempts.

    This class provides context-aware prompts to guide the agent when
    retries are needed, helping it understand what went wrong and what
    alternative approaches to try.
    """

    # Retry prompts for different scenarios
    RETRY_PROMPTS = {
        "empty_logs": """The previous search returned no results. Before giving up, please try one of these approaches:

1. **Expand Time Range**: If you searched for 1 hour, try 6 hours or 24 hours
2. **Broaden Filter**: Remove or simplify the filter pattern
3. **Different Log Group**: Try a related log group if available

Execute one of these alternatives now. Do not ask the user - try an alternative first.""",
        "log_group_not_found": """The specified log group was not found. Please:

1. Use list_log_groups to find available log groups
2. Look for similar names or common prefixes
3. Try the closest match

Execute a search now. Do not ask the user until you've tried to find alternatives.""",
        "intent_without_action": """You stated an intention but did not execute it. Please immediately call the appropriate tool to carry out your stated action. Do not describe what you will do - do it now.""",
        "partial_results": """The results may be incomplete. Consider:

1. Checking if there are more logs in a broader time range
2. Looking at related log groups for additional context
3. Searching for correlated events

If relevant, expand your search. Otherwise, proceed with your analysis.""",
    }

    @classmethod
    def generate_retry_prompt(
        cls,
        reason: str,
        retry_state: RetryState,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate an appropriate retry prompt.

        Args:
            reason: The reason for retry (key into RETRY_PROMPTS)
            retry_state: Current retry state
            context: Additional context (e.g., last tool args)

        Returns:
            Formatted retry prompt with context
        """
        base_prompt = cls.RETRY_PROMPTS.get(reason, cls.RETRY_PROMPTS["empty_logs"])

        # Add context about previous attempts
        if retry_state.attempts > 0:
            attempt_info = f"\n\nThis is retry attempt {retry_state.attempts + 1}. "
            attempt_info += f"Strategies already tried: {', '.join(retry_state.strategies_tried)}."
            base_prompt += attempt_info

        # Add specific suggestions based on last tool call
        if context and retry_state.last_tool_args:
            if "start_time" in retry_state.last_tool_args:
                base_prompt += f"\n\nPrevious time range started at: {retry_state.last_tool_args['start_time']}"
            if "filter_pattern" in retry_state.last_tool_args:
                filter_val = retry_state.last_tool_args.get("filter_pattern", "none")
                base_prompt += f"\nPrevious filter: {filter_val}"

        return base_prompt


# Guidance injected into the system prompt when MCP tools are active.
# Describes the synchronous CloudWatch Logs Insights tool exposed by the
# AWS CloudWatch MCP server.  execute_log_insights_query polls internally
# and returns complete results directly — no separate polling step is needed.
_MCP_LOGS_INSIGHTS_GUIDANCE = """
## CloudWatch Logs Insights (MCP Tools) — MANDATORY

Any request to fetch, search, summarize, show, or analyze logs MUST use the tool below.
NEVER say you lack a tool for this — these tools ARE available.

### How to fetch logs
Call `execute_log_insights_query` with these args:
- `log_group_names`: list of log group name strings (use the selected log group)
- `start_time`: ISO 8601 string, e.g. "2026-02-25T11:00:00Z"
- `end_time`: ISO 8601 string, e.g. "2026-02-25T13:00:00Z"
- `query_string`: CloudWatch Logs Insights query (see examples below)

The tool is synchronous — it waits for results and returns them directly.
DO NOT call `get_logs_insight_query_results` afterward — it is NOT needed.

### Example queries
- Show recent logs:
  `fields @timestamp, @message | sort @timestamp desc | limit 50`
- Show errors only:
  `fields @timestamp, @message | filter @message like /(?i)error/ | sort @timestamp desc | limit 50`
- Count by time bucket:
  `fields @timestamp, @message | stats count() by bin(5m)`

### After the query completes
For large result sets, the result will come back with `"cached": true` — this means
the full dataset has been stored in a local cache to protect the context window.
You MUST immediately call `fetch_cached_result_chunk` to retrieve the first chunk
of actual log events — do NOT summarize from the preview alone.
Fetch in small chunks (respecting the system's configured initial chunk size) and analyze each chunk before deciding to fetch more.

### Finding log groups
Use `describe_log_groups` to list or search log groups — do NOT use list_log_groups (not available)."""


class LLMOrchestrator:
    """
    Coordinates LLM interactions with tool execution.

    The orchestrator is the heart of the system - it manages the conversation
    loop, executes tool calls, and handles the back-and-forth between the LLM
    and external systems.
    """

    # System prompt template with self-direction instructions
    SYSTEM_PROMPT = """You are an expert observability assistant helping DevOps engineers and SREs analyze logs and troubleshoot issues.

## Your Capabilities
You have access to tools to fetch and analyze logs from AWS CloudWatch. Use these tools to help users:
- Find and analyze log entries
- Identify error patterns and root causes
- Correlate events across services
- Provide actionable insights

{log_groups_context}

## Guidelines

### Tool Usage
1. Always start by understanding what log groups are available if the user doesn't specify
2. Use appropriate time ranges - start narrow and expand if needed
3. Use filter patterns to reduce data volume when searching for specific issues
4. Fetch logs before attempting analysis

### Response Style
1. Be concise but thorough
2. Highlight important findings (errors, patterns, anomalies)
3. Provide actionable recommendations when possible
4. Use code blocks for log excerpts
5. Summarize large result sets

### Error Handling
1. If a log group doesn't exist, suggest alternatives
2. If no logs found, suggest adjusting time range or filters
3. Explain any limitations clearly

## Self-Direction & Persistence

### Automatic Retry Behavior
When you encounter empty results or no matches, YOU MUST automatically try alternative approaches before responding to the user:

1. **Empty Log Results**
   - FIRST: Expand the time range (e.g., 1h -> 6h -> 24h -> 7d)
   - SECOND: Broaden or remove the filter pattern
   - THIRD: Try a different log group if available
   - ONLY after trying 2-3 alternatives, report findings to the user

2. **Log Group Not Found**
   - FIRST: List available log groups to find similar names
   - SECOND: Try common prefixes (/aws/lambda/, /ecs/, /aws/apigateway/)
   - THIRD: Ask user for clarification only if no similar groups found

3. **Partial Results**
   - If results seem incomplete, try a broader search
   - If results are truncated, inform user and offer to narrow the search

### Action, Don't Just Describe
- NEVER say "I'll search for..." without immediately calling a tool
- NEVER say "Let me check..." without immediately making the check
- If you state an intention, execute it in the same response with a tool call
- Complete the investigation before providing your analysis

### Minimum Effort Principle
Before giving up on a search:
- You MUST have tried at least 2 different approaches
- You MUST have used at least 2 different parameter combinations
- You SHOULD expand time ranges before concluding "no logs found"

===CRITICAL: CACHED RESULTS PROTOCOL===

⚠️ When you receive ANY tool result with "cached": true, you are seeing ONLY A SMALL PREVIEW (typically 5 samples).
This preview is NOT sufficient to answer user questions. The full dataset has been cached to protect context limits.

🚨 MANDATORY IMMEDIATE ACTION REQUIRED:
You MUST call fetch_cached_result_chunk(cache_id, offset=0, limit={chunk_size}) in your IMMEDIATE next response.
DO NOT skip this step. DO NOT answer based on preview alone. DO NOT wait for user prompt.

❌ WRONG - These will give INCORRECT answers:
- Analyzing only the 5 preview samples and answering the user
- Saying "Based on the logs, I can see..." when you only saw 5 of 100 events
- Providing statistics or counts from preview data
- Waiting for the user to ask for more data

✅ CORRECT - Required workflow (SUMMARIZE AS YOU GO):
1. See "cached": true with cache_id "result_abc123" and total_events: 100
2. IMMEDIATELY call: fetch_cached_result_chunk(cache_id='result_abc123', offset=0, limit={chunk_size})
3. Receive first chunk (up to {chunk_size} events)
4. Analyze THIS chunk — summarize key findings, extract patterns, note counts
5. Decide: do you have enough information to answer the user's question?
   - YES → Answer based on what you've analyzed so far
   - NO → Fetch the next chunk: fetch_cached_result_chunk(cache_id='result_abc123', offset={chunk_size}, limit={chunk_size})
6. Repeat steps 3-5. Stop fetching once you can answer accurately. Do NOT fetch all chunks by default.

EXAMPLE:
If a log query tool returns {{"cached": true, "cache_id": "result_6d283cecb68018ad", "total_events": 100, "sample": [5 events]}},
your immediate next action MUST be calling fetch_cached_result_chunk, NOT providing analysis.

The fetch_cached_result_chunk tool supports:
- cache_id: The cache_id from the cached result (REQUIRED)
- offset: Starting index, 0-based (start with 0)
- limit: Number of events, max 200 (use {chunk_size} initially to protect context window)
- filter_pattern: Optional text search (case-insensitive)
- time_start/time_end: Optional Unix timestamp filters

IMPORTANT — CONTEXT BUDGET:
Do NOT try to load all events at once. Each chunk consumes context window space.
Fetch one chunk, analyze it, then decide if more data is needed to answer accurately.
For exact counts across large datasets, track running totals as you process each chunk.

## User-Provided Log Entries

Users can provide log entries directly via the "Add to Context" feature.
When you receive entries in your context:

1. **RECOGNITION**: Look for messages prefixed with "USER-SELECTED LOG ENTRIES for analysis"
2. **PRIORITY**: ALWAYS analyze provided logs FIRST before using any tools
3. **ANALYSIS**: Provide insights, patterns, and categorization based on the provided logs
4. **TOOLS**: Only use search/fetch tools if the provided context is insufficient

CRITICAL: Do NOT ignore user-provided logs and ask to search for logs.
The user has already given you the logs - analyze them immediately.

## Context
Current time: {current_time}
"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: type[ToolRegistry] | ToolRegistry,
        sanitizer: LogSanitizer,
        settings: LogAISettings,
        cache: CacheManager | None = None,
        metrics_collector: MetricsCollector | None = None,
        log_group_manager: "LogGroupManager | None" = None,
        result_cache: ResultCacheManager | None = None,
    ):
        """
        Initialize LLM orchestrator.

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry with available tools
            sanitizer: PII sanitizer instance
            settings: Application settings
            cache: Optional cache manager
            metrics_collector: Optional metrics collector for monitoring
            log_group_manager: Optional pre-loaded log group manager
            result_cache: Optional result cache manager (creates new if None)
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.sanitizer = sanitizer
        self.settings = settings
        self.cache = cache
        self.conversation_history: list[dict[str, Any]] = []
        self.metrics = metrics_collector or MetricsCollector()
        self.log_group_manager = log_group_manager

        # Tool call listeners for sidebar integration
        self.tool_call_listeners: list[Callable[[Any], None]] = []

        # Runtime context injections (for /refresh updates)
        self._pending_context_injection: str | None = None

        # Track active cached result for follow-up detection (Phase 1: Separate Message Timing)
        self._active_cache: ActiveCacheContext | None = None

        # Context management components
        self.budget_tracker = ContextBudgetTracker(
            settings=settings,
            model=settings.current_llm_model,
        )

        # Use provided result cache or create new one
        self.result_cache = result_cache or ResultCacheManager(
            cache_dir=settings.cache_dir / "results",
            ttl_seconds=getattr(settings, "cache_ttl_seconds", 3600),
            max_size_mb=100,
            sample_event_count=settings.cache_sample_event_count,
            metrics_collector=self.metrics,
        )

        # Context notification callback for UI updates
        self._context_notification_callback: Callable[[str, str], None] | None = None

        # Track which utilization tiers have already fired a toast notification so we
        # don't spam the user with repeated warnings on every LLM turn (Issue 3).
        # A higher-severity tier reaching "notified" also suppresses re-notification
        # of lower tiers, because the user has already seen the more important alert.
        self._notified_tiers: set[str] = set()

        logger.info("LLM Orchestrator initialized with context management")

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt with current context.

        The prompt always includes guidance for the CloudWatch Logs Insights MCP
        tools so the LLM knows how to use them correctly.  MCP is the only
        supported tool mode.

        Returns:
            Formatted system prompt including log group context and MCP tool-usage
            guidance.
        """
        now = datetime.now(UTC)

        # Get log groups context from manager if available
        if self.log_group_manager and self.log_group_manager.is_ready:
            log_groups_context = self.log_group_manager.format_for_prompt()
        else:
            # MCP mode exposes `describe_log_groups` for log-group discovery.
            log_groups_context = """## Log Groups

Log groups will be discovered via the `describe_log_groups` tool.
Use this tool to find available log groups before querying logs."""

        prompt = self.SYSTEM_PROMPT.format(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            log_groups_context=log_groups_context,
            chunk_size=self.settings.initial_chunk_size,
        )

        # MCP-specific Logs Insights guidance is always appended — MCP is the
        # only supported tool mode.
        prompt = prompt + _MCP_LOGS_INSIGHTS_GUIDANCE

        return prompt

    def register_tool_listener(self, callback: Callable[[Any], None]) -> None:
        """
        Register a callback to receive tool call events.

        Args:
            callback: Function to call when a tool call event occurs
        """
        self.tool_call_listeners.append(callback)

    def unregister_tool_listener(self, callback: Callable[[Any], None]) -> None:
        """
        Unregister a tool call callback.

        Args:
            callback: Function to remove from listeners
        """
        if callback in self.tool_call_listeners:
            self.tool_call_listeners.remove(callback)

    def _notify_tool_call(self, record: Any) -> None:
        """
        Notify all listeners of a tool call event.

        Args:
            record: Tool call record to send to listeners
        """
        for listener in self.tool_call_listeners:
            try:
                listener(record)
            except Exception as e:
                logger.warning(f"Tool listener error: {e}", exc_info=True)

    def inject_context_update(self, context_message: str) -> None:
        """
        Inject a context update to be included in the next LLM call.

        This is used to update the agent's knowledge mid-conversation,
        such as after a /refresh command updates the log group list.

        Args:
            context_message: Message to inject as system context
        """
        self._pending_context_injection = context_message
        logger.debug(f"Orchestrator stored context: {len(context_message)} chars")

    @property
    def pending_context_injection(self) -> str | None:
        """Current staged context injection, or None if nothing is pending."""
        return self._pending_context_injection

    def _get_pending_context_injection(self) -> str | None:
        """
        Get and clear any pending context injection.

        Note: Cache guidance is no longer injected here. It's now delivered
        directly in the tool result to avoid confusing the agent.
        """
        # Include user-selected log entries if available
        if self._pending_context_injection:
            injection = self._pending_context_injection
            self._pending_context_injection = None
            logger.debug(f"Orchestrator retrieved context: {len(injection)} chars")
            return injection

        return None

    def _should_inject_cache_guidance(self, user_message: str) -> bool:
        """
        Determine if cache guidance should be injected for this message.

        Phase 1 (Separate Message Timing) approach:
        - Only inject guidance for follow-up questions about cached data
        - Requires active cache that's recent (< 10 minutes per approved params)
        - Detects aggregation keywords or reference words

        Returns True if:
        - ``enable_auto_fetch_guidance`` setting is enabled
        - Active cache exists and is recent
        - Message appears to be a follow-up about cached data
        - Message requires full dataset analysis

        Args:
            user_message: The user's message to analyze

        Returns:
            True if cache guidance should be injected
        """
        # Respect the feature flag — allows disabling guidance injection via config
        if not self.settings.enable_auto_fetch_guidance:
            return False

        if not self._active_cache or not self._active_cache.is_recent(max_age_seconds=600):
            return False

        message_lower = user_message.lower()

        # Check for aggregation keywords (strong signal for needing full dataset)
        aggregation_keywords = [
            "how many",
            "count",
            "total",
            "every",
            "breakdown",
            "distribution",
            "summarize",
            "analyze all",
            "sum",
            "average",
            "percentage",
            "percent",
            "proportion",
        ]
        has_aggregation = any(kw in message_lower for kw in aggregation_keywords)

        # Check for reference words (indicates talking about previous results)
        reference_words = [
            "those",
            "these",
            "them",
            "that data",
            "the errors",
            "the logs",
            "the results",
            "the events",
            "above",
        ]
        has_reference = any(ref in message_lower for ref in reference_words)

        return has_aggregation or has_reference

    def _get_follow_up_cache_injection(self, user_message: str) -> str | None:
        """
        Generate cache guidance injection for follow-up questions about cached data.

        This is part of Phase 1 (Separate Message Timing) where:
        - Tool result was delivered first (agent saw the preview)
        - User asks a follow-up question requiring full dataset
        - We inject explicit guidance to use fetch_cached_result_chunk

        Args:
            user_message: The user's message (for logging/debugging)

        Returns:
            Injection text or None if no injection needed
        """
        if not self._should_inject_cache_guidance(user_message):
            return None

        # _should_inject_cache_guidance guarantees _active_cache is set; guard defensively
        # against any future refactor that might call this method directly.
        if self._active_cache is None:
            return None
        cache = self._active_cache
        chunk_size = self.settings.initial_chunk_size
        total_chunks = (cache.total_events + chunk_size - 1) // chunk_size

        logger.debug(
            f"Injecting cache guidance for follow-up question "
            f"(cache_id={cache.cache_id}, {cache.total_events} events)"
        )

        return f"""CACHED DATA CONTEXT:
You have an active cached dataset from a previous query:
- Cache ID: {cache.cache_id}
- Total Events: {cache.total_events}
- Chunks Available: {total_chunks} (at {chunk_size} events each)

To answer the user's question, fetch one chunk at a time:
Use fetch_cached_result_chunk(cache_id="{cache.cache_id}", offset=0, limit={chunk_size})

After each chunk, analyze what you've learned and decide if you need more data.
Only fetch another chunk if the user's question genuinely requires more data than you've already seen.
Stop fetching once you have enough information to answer the question accurately.
For exact counts or aggregations, keep running totals as you process each chunk.

Do NOT answer based only on preview samples."""

    def _reset_cache_fetch_count(self) -> None:
        """
        Reset the chunk fetch count on new user message (new turn).

        Per approved design: fetch count resets per conversation turn,
        allowing agents to make up to max_auto_chunk_fetches (default: 3) per turn.
        """
        if self._active_cache:
            self._active_cache.chunks_fetched = 0
            logger.debug(f"Reset fetch count for cache_id={self._active_cache.cache_id}")

    def _notify_context_event(self, level: str, message: str) -> None:
        """
        Notify UI about context management events.

        Args:
            level: Event level ("info", "warning", "error")
            message: Event message
        """
        if self._context_notification_callback:
            try:
                self._context_notification_callback(level, message)
            except Exception as e:
                logger.warning(f"Context notification error: {e}", exc_info=True)

        # Also log it
        if level == "error":
            logger.error(f"Context: {message}")
        elif level == "warning":
            logger.warning(f"Context: {message}")
        else:
            logger.info(f"Context: {message}")

    def set_context_notification_callback(
        self, callback: Callable[[str, str], None] | None
    ) -> None:
        """
        Set callback for context management notifications.

        Args:
            callback: Function to call with (level, message) or None to clear
        """
        self._context_notification_callback = callback

    async def _process_tool_result(
        self,
        tool_result: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        """
        Process a tool result — pass through in full, tracking token cost.

        Tool results are no longer cached or truncated. They are added to context
        in full and subject to normal history pruning if context becomes full.

        Args:
            tool_result: Raw tool result with tool_call_id and result
            tool_name: Name of the tool that produced this result

        Returns:
            The tool result, unmodified
        """
        result_data = tool_result.get("result", {})

        # Count tokens for budget tracking
        token_count = TokenCounter.estimate_json_tokens(
            result_data, self.settings.current_llm_model
        )
        self.budget_tracker.add_result_tokens(token_count)

        logger.debug(f"Tool result passed through: tool_name={tool_name}, tokens={token_count}")

        return tool_result

    # TODO: Remove _create_enhanced_cache_summary, _should_inject_cache_guidance,
    # _get_follow_up_cache_injection, _reset_cache_fetch_count, and the
    # fetch_cached_result_chunk limit-checking block in _execute_tool_calls when
    # caching is fully deprecated. See design-context-window-scaling.md (REQ-2).

    def _should_prune_history(self) -> bool:
        """
        Check if history should be pruned before next LLM call.

        Returns:
            True if pruning is needed
        """
        if not self.settings.enable_history_pruning:
            return False

        usage = self.budget_tracker.get_usage()
        threshold = self.settings.context_warning_threshold_pct

        return usage.utilization_pct >= threshold

    def _prune_history_if_needed(self) -> None:
        """
        Prune conversation history if context is getting full.

        This uses a FIFO strategy with preservation of recent messages.
        """
        if not self._should_prune_history():
            return

        usage = self.budget_tracker.get_usage()

        # Calculate how much to free (aim for 20% reduction)
        target_free = int(usage.total_tokens * 0.25)  # Free 25% to give breathing room

        # Get indices to prune from budget tracker
        to_prune = self.budget_tracker.get_prunable_messages(target_free)

        if not to_prune:
            logger.debug("No messages available for pruning")
            return

        # Estimate tokens in messages to be pruned (for notification)
        estimated_tokens = 0
        for idx in to_prune:
            if 0 <= idx < len(self.conversation_history):
                msg = self.conversation_history[idx]
                # Rough estimate: 4 characters per token
                estimated_tokens += len(str(msg)) // 4

        # Remove messages from conversation history (prune in reverse order to maintain indices)
        pruned_count = 0
        for idx in sorted(to_prune, reverse=True):
            if 0 <= idx < len(self.conversation_history):
                removed = self.conversation_history.pop(idx)
                logger.debug(f"Pruned message at index {idx}: role={removed.get('role')}")
                pruned_count += 1

        # Budget tracker will be recalculated on next _update_budget_tracker() call
        # No need to update it here since it gets reset() anyway

        # Notify UI
        self._notify_context_event(
            "info",
            f"Pruned {pruned_count} old messages to maintain context "
            f"(freed ~{estimated_tokens} tokens)",
        )

        # Log pruning stats
        logger.info(
            f"History pruned: {pruned_count} messages, ~{estimated_tokens} tokens freed (estimated)",
            extra={
                "messages_pruned": pruned_count,
                "tokens_freed_estimate": estimated_tokens,
                "utilization_before": usage.utilization_pct,
                # Note: utilization_after will be accurate on next _update_budget_tracker() call
            },
        )

        # Record metric
        self.metrics.increment(
            "history_pruned",
            labels={"message_count": str(pruned_count)},
        )

    def _update_budget_tracker(self, messages: list[dict[str, Any]]) -> None:
        """
        Update budget tracker with current conversation state.

        This should be called before each LLM invocation to ensure
        accurate token tracking.

        Args:
            messages: Current message list being sent to LLM
        """
        # Reset tracker for fresh count
        self.budget_tracker.reset()

        # Track system prompt (first message is always system)
        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0].get("content", "")
            self.budget_tracker.set_system_prompt(system_prompt)

        # Track all messages
        for msg in messages:
            self.budget_tracker.add_message(msg)

    def _log_budget_status(self) -> None:
        """Log current budget status for monitoring."""
        usage = self.budget_tracker.get_usage()

        logger.debug(
            f"Context budget: {usage.utilization_pct:.1f}% "
            f"({usage.total_tokens}/{self.budget_tracker.allocation.usable_tokens} tokens), "
            f"system={usage.system_prompt_tokens}, "
            f"history={usage.history_tokens}, "
            f"results={usage.result_tokens}",
        )

        # Determine which tier (if any) this utilization falls into.
        # Tiers are ordered from most-severe to least-severe so we always record
        # the highest applicable tier and skip lower ones that the user has already
        # seen — this avoids toast spam when utilization is stable above a threshold.
        pct = usage.utilization_pct
        if pct >= 95:
            new_tier = "critical"
        elif pct >= 90:
            new_tier = "high"
        elif pct >= 85:
            new_tier = "warning"
        elif pct >= 70:
            new_tier = "info"
        else:
            new_tier = ""

        # Only fire a notification the first time each tier is crossed.
        # Once a higher-severity tier has been notified, lower tiers are
        # implicitly covered — suppress re-notification for those too.
        TIER_RANK = {"info": 1, "warning": 2, "high": 3, "critical": 4}
        new_rank = TIER_RANK.get(new_tier, 0)
        highest_notified = max((TIER_RANK.get(t, 0) for t in self._notified_tiers), default=0)

        if new_tier and new_rank > highest_notified:
            self._notified_tiers.add(new_tier)

            # Notify if getting full — tiers from most severe to least.
            # Each tier fires a visible toast notification to the user via _notify_context_event().
            if new_tier == "critical":
                self._notify_context_event(
                    "error",
                    f"Context window critically full ({pct:.0f}%). "
                    "Conversation may need to be cleared soon.",
                )
            elif new_tier == "high":
                self._notify_context_event("warning", f"Context window {pct:.0f}% full (!)")
            elif new_tier == "warning":
                # REQ-3: User-visible warning at 85% — explicit toast so the user is
                # aware before history pruning silently removes older messages.
                self._notify_context_event(
                    "warning",
                    f"Context window is {pct:.0f}% full. "
                    "Older messages may be pruned to make room.",
                )
            elif new_tier == "info":
                self._notify_context_event("info", f"Context window {pct:.0f}% full")

    def _check_mid_loop_budget(self, messages: list[dict[str, Any]]) -> tuple[bool, int]:
        """
        Check budget status mid-loop and determine if action needed.

        This method is called after each tool result is added to messages
        during the conversation loop. It calculates remaining budget and
        determines if emergency pruning is needed.

        Args:
            messages: Current messages list (including new tool results)

        Returns:
            Tuple of (needs_action: bool, remaining_tokens: int)
            needs_action is True if remaining < emergency_threshold
        """
        # Get current usage from budget tracker
        usage = self.budget_tracker.get_usage()

        # Calculate remaining budget
        remaining = usage.remaining_tokens

        # Calculate emergency threshold as a percentage of usable context, scaling
        # correctly for all model sizes.
        #   200K model (190K usable): 4% ≈ 7,600 tokens  — adequate buffer
        #   128K model (121K usable): 4% ≈ 4,864 tokens  — comparable to old default
        #    32K model ( 30K usable): 4% ≈ 1,216 tokens  — reasonable
        #     8K model (  7.6K usable): 4% ≈ 304 tokens  — triggers only when truly full
        emergency_threshold = int(
            self.budget_tracker.allocation.usable_tokens
            * (self.settings.emergency_prune_threshold_pct / 100.0)
        )

        # Log current state at debug level
        logger.debug(
            f"Mid-loop budget check: {remaining} tokens remaining "
            f"(threshold: {emergency_threshold}), "
            f"utilization: {usage.utilization_pct:.1f}%"
        )

        needs_action = remaining < emergency_threshold

        if needs_action:
            logger.warning(
                f"Context budget critically low: {remaining} tokens remaining "
                f"(< {emergency_threshold} threshold)"
            )
            self._notify_context_event(
                "warning",
                f"Context budget low: {remaining} tokens remaining",
            )

        return needs_action, remaining

    def _emergency_prune_history(
        self, messages: list[dict[str, Any]], target_tokens_to_free: int = 0
    ) -> int:
        """
        Emergency pruning when context budget is critically low during tool execution.

        This is different from regular pruning:
        - Called mid-loop, not just at turn start
        - More aggressive (aims to free 25% of context)
        - Syncs both conversation_history AND messages list
        - Never removes system messages or current tool cycle

        Args:
            messages: Current messages list being used in LLM call (mutated in place)
            target_tokens_to_free: Minimum tokens to free. If 0, aims for 25% of context.

        Returns:
            Number of tokens actually freed
        """
        logger.warning("Emergency pruning triggered - context budget critically low")

        # Calculate target if not specified
        if target_tokens_to_free <= 0:
            usage = self.budget_tracker.get_usage()
            target_tokens_to_free = int(usage.total_tokens * 0.25)  # Free 25%

        # Identify prunable messages
        # Rules:
        # 1. Never prune index 0 (system message)
        # 2. Keep last 4 messages (2 exchanges minimum for continuity)
        # 3. Prune oldest first

        PRESERVE_RECENT = 4  # Keep last 4 messages (2 user/assistant pairs)

        # Find indices of prunable messages in conversation_history
        # Note: conversation_history doesn't include system message (it's prepended separately)
        prunable_indices = []

        for i in range(len(self.conversation_history)):
            # Skip recent messages
            if i >= len(self.conversation_history) - PRESERVE_RECENT:
                continue
            prunable_indices.append(i)

        if not prunable_indices:
            logger.warning("Emergency prune: No messages available for pruning")
            self._notify_context_event(
                "warning", "Cannot prune - minimum messages required for continuity"
            )
            return 0

        # Calculate tokens for each prunable message and select for removal
        tokens_freed = 0
        indices_to_remove = []

        for idx in prunable_indices:
            if tokens_freed >= target_tokens_to_free:
                break

            msg = self.conversation_history[idx]
            content = msg.get("content", "")
            if isinstance(content, dict):
                content = json.dumps(content)

            msg_tokens = TokenCounter.count_tokens(str(content), self.settings.current_llm_model)

            indices_to_remove.append(idx)
            tokens_freed += msg_tokens

        # Remove messages (reverse order to maintain indices)
        messages_removed = 0
        for idx in sorted(indices_to_remove, reverse=True):
            removed_msg = self.conversation_history.pop(idx)
            messages_removed += 1
            logger.debug(f"Emergency pruned message at index {idx}: role={removed_msg.get('role')}")

        # Also remove from the messages list being used in current LLM call
        # Messages list has system message at index 0, so offset by 1
        for idx in sorted(indices_to_remove, reverse=True):
            messages_idx = idx + 1  # Account for system message at index 0
            if messages_idx < len(messages):
                messages.pop(messages_idx)

        # Reset budget tracker to recalculate
        self.budget_tracker.reset()
        self._update_budget_tracker(messages)

        # Notify and log
        self._notify_context_event(
            "info",
            f"Emergency pruned {messages_removed} messages, freed ~{tokens_freed} tokens",
        )

        logger.info(
            f"Emergency pruning complete: removed {messages_removed} messages, "
            f"freed ~{tokens_freed} tokens",
            extra={
                "messages_removed": messages_removed,
                "tokens_freed": tokens_freed,
                "target_tokens": target_tokens_to_free,
            },
        )

        # Record metric
        self.metrics.increment(
            "emergency_prune", labels={"messages_removed": str(messages_removed)}
        )

        return tokens_freed

    async def chat(
        self,
        user_message: str,
        stream: bool = False,
    ) -> str:
        """
        Process a user message through the LLM with tool execution.

        Args:
            user_message: User's message/query
            stream: Whether to stream the response (currently not supported in this method,
                   use chat_stream() instead for streaming)

        Returns:
            Final response text

        Raises:
            OrchestratorError: If orchestration fails
        """
        return await self._chat_complete(user_message)

    async def chat_stream(
        self,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and stream the response.

        Args:
            user_message: User's message/query

        Yields:
            Response tokens

        Raises:
            OrchestratorError: If orchestration fails
        """
        async for token in self._chat_stream(user_message):
            yield token

    def _log_tool_call_diagnostic(
        self,
        tool_message: dict[str, Any],
        tool_result: dict[str, Any],
        caller: str,
    ) -> None:
        """Log diagnostic information about a tool result being sent to the LLM.

        Emits a brief summary log followed by deeper FETCH_LOGS_DEBUG detail when
        the result looks like an uncached ``fetch_logs`` response (i.e. it contains
        both ``events`` and ``success`` keys and is not a cache hit).

        Args:
            tool_message: The assembled message dict that will be appended to the
                conversation (contains ``role``, ``tool_call_id``, and ``content``).
            tool_result: The raw tool result dict (contains ``result`` payload used
                to decide whether deep logging applies).
            caller: Short label identifying the call site, e.g. ``"_chat_complete"``
                or ``"_chat_stream"``, included in log output for easy grepping.
        """
        logger.debug(
            f"Message to agent ({caller}): role=tool, "
            f"tool_call_id={tool_result['tool_call_id']}, "
            f"content_length={len(tool_message['content'])}, "
            f"content_preview={tool_message['content'][:200]}..."
        )

        tool_result_data = tool_result.get("result", {})
        if not isinstance(tool_result_data, dict):
            return

        has_events = "events" in tool_result_data
        has_success = "success" in tool_result_data
        is_cached = tool_result_data.get("cached", False)

        if not (has_events and has_success and not is_cached):
            return

        # Deeper per-field logging for uncached fetch_logs results.
        stream_label = " (STREAM)" if caller == "_chat_stream" else ""
        logger.debug(
            f"===== FINAL MESSAGE TO LLM{stream_label} ===== Tool result being sent to LLM"
        )
        logger.debug(f"Message role: {tool_message['role']}")
        logger.debug(f"Message tool_call_id: {tool_message['tool_call_id']}")
        logger.debug(f"Message content length: {len(tool_message['content'])} chars")
        logger.debug("Content is JSON-serialized: True")

        try:
            content_parsed = json.loads(tool_message["content"])
            logger.debug(f"Parsed content keys: {list(content_parsed.keys())}")
            logger.debug(f"Event count in message: {len(content_parsed.get('events', []))}")
            logger.debug(f"Content preview (first 300 chars): {tool_message['content'][:300]}...")
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool message content as JSON")

    async def _run_conversation_loop(self, user_message: str) -> ConversationLoopResult:
        """Execute the full conversation loop for a single user turn.

        Handles all the shared logic that was previously duplicated between
        ``_chat_complete()`` and ``_chat_stream()``:

        - Cache fetch count reset
        - History pruning (BEFORE appending the new user message — bug fix
          vs. old ``_chat_stream`` which pruned AFTER appending)
        - System prompt construction (pending context injection, cache guidance)
        - User message appended to ``self.conversation_history``
        - Messages list construction
        - Budget tracking
        - Tool-calling loop: LLM call → tool execution → result append → repeat
        - Intent detection and retry logic
        - Final assistant message appended to ``self.conversation_history``

        This method never raises — all errors are captured and returned as a
        ``ConversationLoopResult`` with ``is_error=True``.  The thin wrappers
        (``_chat_complete`` and ``_chat_stream``) decide how to surface errors
        to their respective callers.

        Args:
            user_message: The user's input text for this conversation turn.

        Returns:
            ``ConversationLoopResult`` containing the final response text and
            error status.
        """
        try:
            # ── Phase 1: Setup ────────────────────────────────────────────
            # Reset per-turn cache fetch counter (Phase 1: Separate Message Timing)
            self._reset_cache_fetch_count()

            # Prune history BEFORE appending the new user message so the
            # pruning decision reflects the existing context, not this turn's
            # input (fixes a bug in the old _chat_stream implementation).
            self._prune_history_if_needed()

            # Get pending context to inject (e.g. user-selected log entries via /refresh)
            context_to_inject = self._get_pending_context_injection()

            # Build system prompt, merging any pending injections
            system_prompt = self._get_system_prompt()
            if context_to_inject:
                system_prompt = f"{system_prompt}\n\n---\n\n{context_to_inject}"

            # Inject follow-up cache guidance when the user is asking about a
            # previously cached dataset (Phase 1: Separate Message Timing)
            follow_up_injection = self._get_follow_up_cache_injection(user_message)
            if follow_up_injection:
                system_prompt = f"{system_prompt}\n\n{follow_up_injection}"

            # Append user message to history (AFTER pruning — see note above)
            self.conversation_history.append({"role": "user", "content": user_message})

            # Build messages list: one system message, then full history
            messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            if self.conversation_history:
                messages.extend(self.conversation_history)

            # Update budget tracker with current conversation state
            self._update_budget_tracker(messages)
            self._log_budget_status()

            # Resolve tool definitions once per turn
            tools = self.tool_registry.to_function_definitions()

            # Diagnostic: log message count and per-message summary
            logger.debug(f"Sending {len(messages)} messages to LLM")
            for i, msg in enumerate(messages):
                # Use .get() to guard against multi-part content blocks (e.g. Anthropic
                # tool-use messages) where "content" may be a list or absent entirely.
                content = msg.get("content") or ""
                content_preview = content[:100] if len(content) > 100 else content
                logger.debug(
                    f"Message {i}: role={msg['role']}, "
                    f"length={len(content)} chars, "
                    f"preview={content_preview}..."
                )

            # ── Phase 2: Conversation Loop ────────────────────────────────
            retry_state = RetryState()
            response: LLMResponse | None = None
            iteration = 0
            max_iterations = self.settings.max_tool_iterations

            while iteration < max_iterations:
                iteration += 1

                try:
                    # Always call the LLM in non-streaming mode during the tool loop.
                    # _chat_stream's "streaming" is simulated by yielding the final
                    # response character-by-character after the loop completes.
                    llm_result = await self.llm_provider.chat(
                        messages=messages, tools=tools, stream=False
                    )

                    # Type guard: stream=False must always return LLMResponse
                    if not isinstance(llm_result, LLMResponse):
                        raise OrchestratorError("Expected LLMResponse but got AsyncGenerator")

                    response = llm_result

                    # ── Tool-calls branch ─────────────────────────────────
                    if response.has_tool_calls():
                        tool_results = await self._execute_tool_calls(response.tool_calls)

                        # Track last tool name/args for retry heuristics
                        for tool_call in response.tool_calls:
                            func_info = tool_call.get("function", {})
                            retry_state.last_tool_name = func_info.get("name")
                            try:
                                args_str = func_info.get("arguments", "{}")
                                retry_state.last_tool_args = (
                                    json.loads(args_str) if isinstance(args_str, str) else args_str
                                )
                            except json.JSONDecodeError:
                                retry_state.last_tool_args = {}

                        # Append assistant message (with tool_calls) to history
                        assistant_message: dict[str, Any] = {
                            "role": "assistant",
                            "content": response.content or "",
                            "tool_calls": response.tool_calls,
                        }
                        self.conversation_history.append(assistant_message)
                        messages.append(assistant_message)

                        # Append each tool result to history and messages.
                        # Token tracking is already handled inside _process_tool_result()
                        # (called via _execute_tool_calls()), so we must NOT call
                        # add_result_tokens() again here — doing so would double-count
                        # _pending_results_tokens and trigger spurious emergency pruning.
                        for tool_result in tool_results:
                            tool_message: dict[str, Any] = {
                                "role": "tool",
                                "tool_call_id": tool_result["tool_call_id"],
                                "content": json.dumps(tool_result["result"]),
                            }
                            self.conversation_history.append(tool_message)
                            messages.append(tool_message)

                            self._log_tool_call_diagnostic(
                                tool_message, tool_result, "_run_conversation_loop"
                            )

                        # Mid-loop budget check — prune if context is critically low
                        needs_prune, _ = self._check_mid_loop_budget(messages)
                        if needs_prune:
                            self._emergency_prune_history(messages)
                            _, remaining_after = self._check_mid_loop_budget(messages)
                            # Check whether pruning actually freed enough space.
                            # remaining_tokens is always >= 0 (clamped in BudgetUsage),
                            # so "< 0" is unreachable — compare against the emergency
                            # threshold instead: if we're still below it, pruning failed
                            # to make room and we must end the conversation gracefully.
                            emergency_threshold = int(
                                self.budget_tracker.allocation.usable_tokens
                                * (self.settings.emergency_prune_threshold_pct / 100.0)
                            )
                            if remaining_after < emergency_threshold:
                                error_msg = (
                                    "I've reached my context limit and cannot continue "
                                    "this conversation. Please use /clear to start a "
                                    "new conversation."
                                )
                                self.conversation_history.append(
                                    {"role": "assistant", "content": error_msg}
                                )
                                self._notify_context_event(
                                    "error", "Context exhausted - conversation ended"
                                )
                                return ConversationLoopResult(content=error_msg, is_error=True)

                        # Retry analysis
                        should_retry, retry_reason = self._analyze_tool_results(
                            tool_results, retry_state
                        )

                        if should_retry and retry_state.should_retry(
                            self.settings.max_retry_attempts
                        ):
                            self.metrics.increment(
                                "retry_attempts", labels={"reason": retry_reason}
                            )

                            backoff_delay = self._calculate_backoff_delay(retry_state.attempts)
                            logger.info(
                                "Applying exponential backoff before retry",
                                extra={
                                    "delay_seconds": backoff_delay,
                                    "attempt": retry_state.attempts,
                                },
                            )

                            with MetricsTimer(
                                self.metrics,
                                "retry_backoff_seconds",
                                labels={"attempt": str(retry_state.attempts)},
                            ):
                                await asyncio.sleep(backoff_delay)

                            retry_prompt = RetryPromptGenerator.generate_retry_prompt(
                                retry_reason, retry_state
                            )
                            retry_message = {"role": "system", "content": retry_prompt}
                            messages.append(retry_message)
                            retry_state.record_attempt(
                                retry_state.last_tool_name or "unknown",
                                retry_state.last_tool_args or {},
                                retry_reason,
                            )
                            logger.info(
                                "Injecting retry prompt",
                                extra={
                                    "reason": retry_reason,
                                    "attempt": retry_state.attempts,
                                    "strategies_tried": retry_state.strategies_tried,
                                },
                            )
                            self.metrics.increment(
                                "retry_prompt_injected", labels={"reason": retry_reason}
                            )
                        else:
                            if should_retry:
                                # Max retry attempts exhausted — record metric and continue
                                self.metrics.increment(
                                    "retry_max_attempts_reached",
                                    labels={"reason": retry_reason},
                                )

                        # Loop again so the LLM can process the tool results
                        continue

                    # ── No tool calls — intent detection ──────────────────
                    if self.settings.intent_detection_enabled and response.content:
                        detected_intent = IntentDetector.detect_intent(response.content)

                        if detected_intent and detected_intent.confidence >= 0.8:
                            self.metrics.increment(
                                "intent_detection_hits",
                                labels={
                                    "intent_type": detected_intent.intent_type.value,
                                    "confidence_bucket": self._confidence_bucket(
                                        detected_intent.confidence
                                    ),
                                },
                            )

                            # Agent stated an intent but didn't call a tool — nudge it
                            if retry_state.should_retry(self.settings.max_retry_attempts):
                                self.metrics.increment(
                                    "retry_attempts",
                                    labels={"reason": "intent_without_action"},
                                )
                                nudge_message = {
                                    "role": "system",
                                    "content": RetryPromptGenerator.generate_retry_prompt(
                                        "intent_without_action", retry_state
                                    ),
                                }
                                messages.append(nudge_message)
                                retry_state.record_attempt(
                                    "intent_detection", {}, "intent_without_action"
                                )
                                logger.info(
                                    "Detected intent without action, nudging agent",
                                    extra={
                                        "intent_type": detected_intent.intent_type.value,
                                        "confidence": detected_intent.confidence,
                                        "attempt": retry_state.attempts,
                                    },
                                )
                                continue

                        if IntentDetector.detect_premature_giving_up(response.content):
                            if retry_state.empty_result_count > 0 and retry_state.should_retry(
                                self.settings.max_retry_attempts
                            ):
                                nudge_message = {
                                    "role": "system",
                                    "content": RetryPromptGenerator.generate_retry_prompt(
                                        "empty_logs", retry_state
                                    ),
                                }
                                messages.append(nudge_message)
                                retry_state.record_attempt(
                                    "giving_up_prevention", {}, "premature_exit"
                                )
                                logger.info(
                                    "Detected premature giving up, encouraging retry",
                                    extra={
                                        "empty_result_count": retry_state.empty_result_count,
                                        "attempt": retry_state.attempts,
                                    },
                                )
                                continue

                    # ── Final response ────────────────────────────────────
                    if response.content:
                        self.conversation_history.append(
                            {"role": "assistant", "content": response.content}
                        )
                        return ConversationLoopResult(content=response.content)
                    else:
                        error_msg = "Received empty response from LLM"
                        self.conversation_history.append(
                            {"role": "assistant", "content": error_msg}
                        )
                        return ConversationLoopResult(content=error_msg, is_error=True)

                except LLMProviderError as e:
                    return ConversationLoopResult(
                        content=f"LLM provider error: {str(e)}",
                        is_error=True,
                        error_exception=e,
                    )
                except Exception as e:
                    # Self-direction errors are non-fatal — if we have content, return it
                    logger.warning(
                        "Error in self-direction logic, continuing without retry",
                        extra={"error": str(e)},
                        exc_info=True,
                    )
                    if (
                        response is not None
                        and isinstance(response, LLMResponse)
                        and response.content
                    ):
                        self.conversation_history.append(
                            {"role": "assistant", "content": response.content}
                        )
                        return ConversationLoopResult(content=response.content)
                    return ConversationLoopResult(
                        content=f"Unexpected error during orchestration: {str(e)}",
                        is_error=True,
                        error_exception=e,
                    )

            # ── Max iterations reached ────────────────────────────────────
            error_msg = (
                f"Maximum tool iterations ({max_iterations}) exceeded. "
                "The conversation may be stuck in a loop."
            )
            self.conversation_history.append({"role": "assistant", "content": error_msg})
            return ConversationLoopResult(content=error_msg, is_error=True)

        except Exception as e:
            # Outer safety net: catches any exception from Phase 1 setup code
            # (e.g. a failure in _get_system_prompt or _prune_history_if_needed)
            logger.error(
                "Unexpected error in _run_conversation_loop setup phase",
                extra={"error": str(e)},
                exc_info=True,
            )
            return ConversationLoopResult(
                content=f"Unexpected error during orchestration: {str(e)}",
                is_error=True,
                error_exception=e,
            )

    async def _chat_complete(self, user_message: str) -> str:
        """Process message and return complete response.

        Thin wrapper around ``_run_conversation_loop()``.  Re-raises
        ``OrchestratorError`` for LLM provider failures so callers that
        depend on exception-based error handling are not broken.

        Args:
            user_message: User's input message

        Returns:
            Complete response text

        Raises:
            OrchestratorError: If the conversation loop reports an error
                that has an associated exception (e.g. LLMProviderError).
        """
        result = await self._run_conversation_loop(user_message)

        # Re-raise exception-backed errors as OrchestratorError to preserve
        # the existing public API contract (callers expect exceptions, not
        # result objects, from this method).
        if result.is_error and result.error_exception is not None:
            raise OrchestratorError(result.content) from result.error_exception

        return result.content

    async def _chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Process message and stream the response character-by-character.

        Thin wrapper around ``_run_conversation_loop()``.  Yields the full
        response (or error message) one character at a time, simulating
        streaming.  Never raises — errors are yielded as text.

        Note: The entire conversation loop (all tool calls, retries, etc.)
        completes before any character is yielded.  This is intentional and
        matches the pre-refactor behaviour.  True token-level streaming is
        tracked as a post-MVP improvement.

        Args:
            user_message: User's message

        Yields:
            Response characters
        """
        result = await self._run_conversation_loop(user_message)
        for char in result.content:
            yield char

    async def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool call requests from LLM

        Returns:
            List of tool results with tool_call_id and result (possibly cached summaries)
        """
        results = []

        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "unknown")
            function_info = tool_call.get("function", {})
            function_name = function_info.get("name")
            function_args_str = function_info.get("arguments", "{}")
            record = None

            try:
                # Parse arguments
                if isinstance(function_args_str, str):
                    function_args = json.loads(function_args_str)
                else:
                    function_args = function_args_str

                # Create record and notify PENDING
                record = ToolCallRecord(
                    id=tool_call_id,
                    name=function_name,
                    arguments=function_args,
                    status=ToolCallStatus.PENDING,
                )
                self._notify_tool_call(record)

                # Update to RUNNING
                record.status = ToolCallStatus.RUNNING
                self._notify_tool_call(record)

                # Check fetch limit for cached result chunks (Phase 2)
                if function_name == "fetch_cached_result_chunk" and self._active_cache:
                    cache_id = function_args.get("cache_id")
                    if cache_id == self._active_cache.cache_id:
                        if self._active_cache.is_over_limit(self.settings.max_auto_chunk_fetches):
                            logger.warning(
                                f"Fetch limit exceeded: {self._active_cache.chunks_fetched} fetches "
                                f"for cache_id={cache_id} (limit: {self.settings.max_auto_chunk_fetches})"
                            )
                            result = {
                                "success": False,
                                "error": f"Fetch limit exceeded for this cache ({self.settings.max_auto_chunk_fetches} fetches per turn)",
                                "hint": "You have already fetched the maximum number of chunks for this cache in this turn. "
                                "If you need more data, ask the user to re-run the original query or wait for the next turn.",
                                "chunks_fetched": self._active_cache.chunks_fetched,
                                "limit": self.settings.max_auto_chunk_fetches,
                            }
                            # Update record and notify
                            record.status = ToolCallStatus.SUCCESS
                            record.result = result
                            record.completed_at = datetime.now()
                            self._notify_tool_call(record)

                            # Add to results and continue to next tool call
                            tool_result = {"tool_call_id": tool_call_id, "result": result}
                            processed_result = await self._process_tool_result(
                                tool_result, function_name
                            )
                            results.append(processed_result)
                            continue

                # Execute tool
                result = await self.tool_registry.execute(function_name, **function_args)

                # DIAGNOSTIC: Log raw tool result immediately after execution
                if function_name == "fetch_logs":
                    logger.debug(f"===== RAW TOOL EXECUTION ===== Tool executed: {function_name}")
                    logger.debug(f"Raw result type: {type(result).__name__}")
                    logger.debug(
                        f"Raw result keys: {list(result.keys()) if isinstance(result, dict) else 'non-dict'}"
                    )
                    if isinstance(result, dict):
                        # Type-safe event count extraction
                        event_count = 0
                        events = result.get("events") or result.get("logs")
                        if events and isinstance(events, list):
                            event_count = len(events)
                        logger.debug(f"Raw event count: {event_count}")
                        logger.debug(f"Raw result size: {len(str(result))} chars")
                        logger.debug(f"Raw success flag: {result.get('success', 'N/A')}")

                # Track successful fetch for limit enforcement (Phase 2)
                if function_name == "fetch_cached_result_chunk" and result.get("success"):
                    cache_id = function_args.get("cache_id")
                    if self._active_cache and cache_id == self._active_cache.cache_id:
                        new_count = self._active_cache.increment_fetch_count()
                        logger.debug(
                            f"Incremented fetch count for cache_id={cache_id}: "
                            f"{new_count}/{self.settings.max_auto_chunk_fetches}"
                        )

                # Update to SUCCESS
                record.status = ToolCallStatus.SUCCESS
                record.result = result
                record.completed_at = datetime.now()
                self._notify_tool_call(record)

                # Process through context manager (may cache large results)
                tool_result = {"tool_call_id": tool_call_id, "result": result}
                processed_result = await self._process_tool_result(tool_result, function_name)

                # DIAGNOSTIC: Log what's being added to results after processing
                if function_name == "fetch_logs":
                    logger.debug(
                        "===== AFTER PROCESSING ===== Result processed by _process_tool_result"
                    )
                    logger.debug(f"Processed result keys: {list(processed_result.keys())}")
                    processed_data = processed_result.get("result", {})
                    logger.debug(
                        f"Processed data keys: {list(processed_data.keys()) if isinstance(processed_data, dict) else 'non-dict'}"
                    )
                    if isinstance(processed_data, dict):
                        logger.debug(
                            f"Processed event count: {len(processed_data.get('events', []))}"
                        )
                        logger.debug(f"Is cached: {processed_data.get('cached', False)}")

                results.append(processed_result)

            except json.JSONDecodeError as e:
                # Invalid JSON arguments
                error_result = {
                    "success": False,
                    "error": f"Failed to parse tool arguments: {str(e)}",
                }
                results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "result": error_result,
                    }
                )

                # Notify ERROR status
                record = ToolCallRecord(
                    id=tool_call_id,
                    name=function_name or "unknown",
                    arguments={},
                    status=ToolCallStatus.ERROR,
                    error_message=str(e),
                    completed_at=datetime.now(),
                )
                self._notify_tool_call(record)

            except Exception as e:
                # Tool execution failed
                error_result = {
                    "success": False,
                    "error": f"Tool execution failed: {str(e)}",
                }
                results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "result": error_result,
                    }
                )

                # Notify ERROR status
                if record is not None:
                    record.status = ToolCallStatus.ERROR
                    record.error_message = str(e)
                    record.completed_at = datetime.now()
                    self._notify_tool_call(record)

        return results

    def _analyze_tool_results(
        self,
        tool_results: list[dict[str, Any]],
        retry_state: RetryState,
    ) -> tuple[bool, str]:
        """Analyze tool results to determine if retry is needed.

        This method examines the results from tool execution to identify
        scenarios where automatic retry would be beneficial, such as empty
        results or error conditions.

        Args:
            tool_results: Results from tool execution
            retry_state: Current retry state

        Returns:
            Tuple of (should_retry, reason) where reason is the retry scenario
        """
        if not self.settings.auto_retry_enabled:
            return False, ""

        for result in tool_results:
            result_data = result.get("result", {})

            # Check for error results
            if result_data.get("success") is False:
                error = result_data.get("error", "")

                # Log group not found - should retry with list
                if "not found" in error.lower() or "does not exist" in error.lower():
                    logger.info(
                        "Detected log group not found error, suggesting retry",
                        extra={"error": error, "attempts": retry_state.attempts},
                    )
                    return True, "log_group_not_found"

            # Check for empty results
            if result_data.get("success") is True:
                # Check various empty indicators
                count = result_data.get("count", -1)
                events = result_data.get("events", None)
                log_groups = result_data.get("log_groups", None)

                # Also check cached result format (dataset.total_events)
                dataset = result_data.get("dataset", {})
                total_events = dataset.get("total_events", -1)

                is_empty = False

                if count == 0:
                    is_empty = True
                elif total_events == 0:
                    # Cached result with 0 events
                    is_empty = True
                elif events is not None and len(events) == 0:
                    is_empty = True
                elif log_groups is not None and len(log_groups) == 0:
                    is_empty = True

                if is_empty:
                    retry_state.record_empty_result()
                    logger.info(
                        "Detected empty results, suggesting retry",
                        extra={
                            "empty_result_count": retry_state.empty_result_count,
                            "attempts": retry_state.attempts,
                        },
                    )
                    return True, "empty_logs"

        return False, ""

    def _calculate_backoff_delay(self, attempt_count: int) -> float:
        """Calculate exponential backoff delay for retry attempts.

        Uses progressive delays to prevent hammering the LLM API and give
        transient issues time to resolve.

        Args:
            attempt_count: Current retry attempt number (0-based)

        Returns:
            Delay in seconds (0.5s → 1s → 2s → 4s...)
        """
        # Base delays from settings for first few attempts
        base_delays = self.settings.orchestrator_retry_delays_list

        if attempt_count < len(base_delays):
            delay: float = base_delays[attempt_count]
            return delay

        # For attempts beyond the base delays, use exponential growth
        result: float = base_delays[-1] * (2 ** (attempt_count - len(base_delays) + 1))
        return result

    def _confidence_bucket(self, confidence: float) -> str:
        """Convert confidence score to a bucket label for metrics.

        Args:
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            Bucket label: "high" (>0.9), "medium" (0.7-0.9), or "low" (<0.7)
        """
        if confidence >= 0.9:
            return "high"
        elif confidence >= 0.7:
            return "medium"
        else:
            return "low"

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """
        Get conversation history.

        Returns:
            List of message dictionaries
        """
        return self.conversation_history.copy()

    def get_full_context_snapshot(self) -> list[dict[str, Any]]:
        """
        Get a snapshot of the full context that would be sent to the LLM.

        This includes:
        - System prompt (always prepended)
        - Full conversation history (user, assistant, tool messages)
        - Does NOT include pending/staged injections (those are shown separately in Staged Context)

        This method provides visibility into the complete context the agent is working with,
        which is useful for debugging and understanding the agent's behavior.

        Returns:
            List of message dicts representing the complete context
        """
        messages = []

        # Always include system prompt
        messages.append({"role": "system", "content": self._get_system_prompt()})

        # Add full conversation history
        messages.extend(self.conversation_history)

        return messages
