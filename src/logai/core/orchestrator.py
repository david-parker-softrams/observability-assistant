"""LLM Orchestrator - coordinates LLM interactions with tool execution."""

import asyncio
import json
import logging
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

## Context
Current time: {current_time}
"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
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
        )

        # Context notification callback for UI updates
        self._context_notification_callback: Callable[[str, str], None] | None = None

        logger.info("LLM Orchestrator initialized with context management")

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt with current context.

        Returns:
            Formatted system prompt including log group context
        """
        now = datetime.now(UTC)

        # Get log groups context from manager if available
        if self.log_group_manager and self.log_group_manager.is_ready:
            log_groups_context = self.log_group_manager.format_for_prompt()
        else:
            log_groups_context = """## Log Groups

Log groups will be discovered via the `list_log_groups` tool.
Use this tool to find available log groups before querying logs."""

        return self.SYSTEM_PROMPT.format(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            log_groups_context=log_groups_context,
        )

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

    def _get_pending_context_injection(self) -> str | None:
        """Get and clear any pending context injection."""
        injection = self._pending_context_injection
        self._pending_context_injection = None
        return injection

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
        Process a tool result, caching if necessary.

        This is a critical integration point for context management. When a tool
        returns a large result, we cache it and return a summary instead.

        Args:
            tool_result: Raw tool result with tool_call_id and result
            tool_name: Name of the tool that produced this result

        Returns:
            Processed result (possibly modified to a summary) for context
        """
        result_data = tool_result["result"]
        tool_call_id = tool_result["tool_call_id"]

        # Skip processing if caching is disabled
        if not self.settings.enable_result_caching:
            return tool_result

        # Check if result should be cached based on size
        should_cache, token_count = self.budget_tracker.should_cache_result(
            result_data,
            threshold=self.settings.cache_large_results_threshold,
        )

        if should_cache:
            try:
                # Extract query parameters for cache key (best effort)
                query_params = {
                    "tool": tool_name,
                    # Add timestamp to make cache entries unique per invocation
                    "timestamp": int(datetime.now(UTC).timestamp()),
                }

                # Cache the result and get summary
                summary = await self.result_cache.cache_result(
                    tool_name=tool_name,
                    query_params=query_params,
                    result=result_data,
                )

                # Use summary instead of full result
                modified_result = summary.to_context_dict()

                # Track the summary tokens
                summary_tokens = TokenCounter.estimate_json_tokens(
                    modified_result, self.settings.current_llm_model
                )
                self.budget_tracker.add_result_tokens(summary_tokens)

                # Notify UI
                event_count = result_data.get("count", len(result_data.get("events", [])))
                self._notify_context_event(
                    "info",
                    f"Cached large result: {event_count} events, "
                    f"{token_count} tokens → {summary_tokens} token summary",
                )

                logger.info(
                    f"Result cached: {tool_name}, {token_count} tokens → {summary_tokens} token summary",
                    extra={
                        "cache_id": summary.cache_id,
                        "original_tokens": token_count,
                        "summary_tokens": summary_tokens,
                        "event_count": event_count,
                    },
                )

                # Record metric
                self.metrics.increment(
                    "result_cached",
                    labels={"tool": tool_name, "reason": "size_threshold"},
                )

                return {
                    "tool_call_id": tool_call_id,
                    "result": modified_result,
                }

            except Exception as e:
                # Cache failure should not break the workflow
                logger.error(
                    f"Failed to cache result, using full result: {e}",
                    exc_info=True,
                    extra={"tool_name": tool_name, "token_count": token_count},
                )
                self._notify_context_event(
                    "warning", "Failed to cache large result, context may fill quickly"
                )

                # Fall through to use full result
                self.budget_tracker.add_result_tokens(token_count)
                return tool_result
        else:
            # Result fits in context, use as-is
            self.budget_tracker.add_result_tokens(token_count)
            return tool_result

    def _should_prune_history(self) -> bool:
        """
        Check if history should be pruned before next LLM call.

        Returns:
            True if pruning is needed
        """
        if not self.settings.enable_history_pruning:
            return False

        usage = self.budget_tracker.get_usage()
        threshold = getattr(self.settings, "context_warning_threshold_pct", 80.0)

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

        # Warn if getting full
        if usage.utilization_pct >= 90:
            self._notify_context_event(
                "warning", f"Context window {usage.utilization_pct:.0f}% full (!)"
            )
        elif usage.utilization_pct >= 70:
            self._notify_context_event("info", f"Context window {usage.utilization_pct:.0f}% full")

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

    async def _chat_complete(self, user_message: str) -> str:
        """Process message and return complete response.

        Enhanced with self-direction capabilities and context management:
        - Detects intent without action and prompts execution
        - Automatically retries on empty results
        - Tracks retry state across the conversation turn
        - Prunes history when context fills
        - Caches large tool results

        Args:
            user_message: User's message

        Returns:
            Complete response text
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prune history if needed (before preparing messages)
        self._prune_history_if_needed()

        # Prepare messages with system prompt
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ] + self.conversation_history

        # Check for pending context injection
        pending_injection = self._get_pending_context_injection()
        if pending_injection:
            messages.append({"role": "system", "content": pending_injection})

        # Update budget tracker with current state
        self._update_budget_tracker(messages)
        self._log_budget_status()

        # Get available tools
        tools = self.tool_registry.to_function_definitions()

        # Initialize retry state for this turn
        retry_state = RetryState()
        response = None

        # Execute conversation loop with tool calling
        iteration = 0
        max_iterations = self.settings.max_tool_iterations
        while iteration < max_iterations:
            iteration += 1

            try:
                # Get LLM response
                llm_result = await self.llm_provider.chat(
                    messages=messages, tools=tools, stream=False
                )

                # Type guard: stream=False should always return LLMResponse
                if not isinstance(llm_result, LLMResponse):
                    raise OrchestratorError("Expected LLMResponse but got AsyncGenerator")

                response = llm_result

                # Check if LLM wants to use tools
                if response.has_tool_calls():
                    # Execute tool calls
                    tool_results = await self._execute_tool_calls(response.tool_calls)

                    # Track tool calls for retry logic
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

                    # Add assistant message with tool calls to history
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls,
                    }
                    self.conversation_history.append(assistant_message)
                    messages.append(assistant_message)

                    # Add tool results as separate messages
                    for tool_result in tool_results:
                        tool_message: dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "content": json.dumps(tool_result["result"]),
                        }
                        self.conversation_history.append(tool_message)
                        messages.append(tool_message)

                    # Analyze results for retry logic
                    should_retry, retry_reason = self._analyze_tool_results(
                        tool_results, retry_state
                    )

                    if should_retry and retry_state.should_retry(self.settings.max_retry_attempts):
                        # Record retry metrics
                        self.metrics.increment("retry_attempts", labels={"reason": retry_reason})

                        # Apply exponential backoff before retry
                        backoff_delay = self._calculate_backoff_delay(retry_state.attempts)
                        logger.info(
                            "Applying exponential backoff before retry",
                            extra={"delay_seconds": backoff_delay, "attempt": retry_state.attempts},
                        )

                        # Measure time spent in retry logic
                        with MetricsTimer(
                            self.metrics,
                            "retry_backoff_seconds",
                            labels={"attempt": str(retry_state.attempts)},
                        ):
                            await asyncio.sleep(backoff_delay)

                        # Inject retry guidance as system message
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

                        # Record successful retry metric
                        self.metrics.increment(
                            "retry_prompt_injected", labels={"reason": retry_reason}
                        )

                    else:
                        # Retry not triggered or max attempts reached
                        if should_retry:
                            # Max attempts reached - record failure
                            self.metrics.increment(
                                "retry_max_attempts_reached", labels={"reason": retry_reason}
                            )

                    # Continue loop - LLM will process tool results
                    continue

                # No tool calls - check for intent without action
                if self.settings.intent_detection_enabled and response.content:
                    detected_intent = IntentDetector.detect_intent(response.content)

                    if detected_intent and detected_intent.confidence >= 0.8:
                        # Record intent detection hit
                        self.metrics.increment(
                            "intent_detection_hits",
                            labels={
                                "intent_type": detected_intent.intent_type.value,
                                "confidence_bucket": self._confidence_bucket(
                                    detected_intent.confidence
                                ),
                            },
                        )

                        # Agent stated intent but didn't act - prompt to act
                        if retry_state.should_retry(self.settings.max_retry_attempts):
                            self.metrics.increment(
                                "retry_attempts", labels={"reason": "intent_without_action"}
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

                    # Check for premature giving up
                    if IntentDetector.detect_premature_giving_up(response.content):
                        if retry_state.empty_result_count > 0 and retry_state.should_retry(
                            self.settings.max_retry_attempts
                        ):
                            # Agent giving up after empty results - encourage retry
                            nudge_message = {
                                "role": "system",
                                "content": RetryPromptGenerator.generate_retry_prompt(
                                    "empty_logs", retry_state
                                ),
                            }
                            messages.append(nudge_message)
                            retry_state.record_attempt("giving_up_prevention", {}, "premature_exit")
                            logger.info(
                                "Detected premature giving up, encouraging retry",
                                extra={
                                    "empty_result_count": retry_state.empty_result_count,
                                    "attempt": retry_state.attempts,
                                },
                            )
                            continue

                # No tool calls and no retry needed - we have the final response
                if response.content:
                    self.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )
                    return response.content
                else:
                    # Empty response, shouldn't happen but handle gracefully
                    error_msg = "Received empty response from LLM"
                    self.conversation_history.append({"role": "assistant", "content": error_msg})
                    return error_msg

            except LLMProviderError as e:
                raise OrchestratorError(f"LLM provider error: {str(e)}") from e
            except Exception as e:
                # Log the error for self-direction features but don't fail the request
                logger.warning(
                    "Error in self-direction logic, continuing without retry",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                # If we have content, return it; otherwise raise
                if response is not None and isinstance(response, LLMResponse) and response.content:
                    self.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )
                    return response.content
                raise OrchestratorError(f"Unexpected error during orchestration: {str(e)}") from e

        # Hit max iterations - likely infinite loop
        error_msg = f"Maximum tool iterations ({max_iterations}) exceeded. The conversation may be stuck in a loop."
        self.conversation_history.append({"role": "assistant", "content": error_msg})
        return error_msg

    async def _chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Process message and stream the response.

        Enhanced with self-direction capabilities and context management.

        Note: For MVP, we'll handle tool calls in non-streaming mode,
        then stream the final response. Full streaming with tool calls
        is complex and can be added post-MVP.

        Args:
            user_message: User's message

        Yields:
            Response tokens
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prune history if needed (before preparing messages)
        self._prune_history_if_needed()

        # Prepare messages with system prompt
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ] + self.conversation_history

        # Check for pending context injection
        pending_injection = self._get_pending_context_injection()
        if pending_injection:
            messages.append({"role": "system", "content": pending_injection})

        # Update budget tracker with current state
        self._update_budget_tracker(messages)
        self._log_budget_status()

        # Get available tools
        tools = self.tool_registry.to_function_definitions()

        # Initialize retry state for this turn
        retry_state = RetryState()
        response = None

        # Execute conversation loop with tool calling (non-streaming)
        iteration = 0
        max_iterations = self.settings.max_tool_iterations
        while iteration < max_iterations:
            iteration += 1

            try:
                # Get LLM response (non-streaming for tool call handling)
                llm_result = await self.llm_provider.chat(
                    messages=messages, tools=tools, stream=False
                )

                # Type guard: stream=False should always return LLMResponse
                if not isinstance(llm_result, LLMResponse):
                    raise OrchestratorError("Expected LLMResponse but got AsyncGenerator")

                response = llm_result

                # Check if LLM wants to use tools
                if response.has_tool_calls():
                    # Execute tool calls
                    tool_results = await self._execute_tool_calls(response.tool_calls)

                    # Track tool calls for retry logic
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

                    # Add assistant message with tool calls to history
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls,
                    }
                    self.conversation_history.append(assistant_message)
                    messages.append(assistant_message)

                    # Add tool results as separate messages
                    for tool_result in tool_results:
                        tool_message: dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "content": json.dumps(tool_result["result"]),
                        }
                        self.conversation_history.append(tool_message)
                        messages.append(tool_message)

                    # Analyze results for retry logic
                    should_retry, retry_reason = self._analyze_tool_results(
                        tool_results, retry_state
                    )

                    if should_retry and retry_state.should_retry(self.settings.max_retry_attempts):
                        # Record retry metrics
                        self.metrics.increment("retry_attempts", labels={"reason": retry_reason})

                        # Apply exponential backoff before retry
                        backoff_delay = self._calculate_backoff_delay(retry_state.attempts)
                        logger.info(
                            "Applying exponential backoff before retry (streaming)",
                            extra={"delay_seconds": backoff_delay, "attempt": retry_state.attempts},
                        )

                        # Measure time spent in retry logic
                        with MetricsTimer(
                            self.metrics,
                            "retry_backoff_seconds",
                            labels={"attempt": str(retry_state.attempts)},
                        ):
                            await asyncio.sleep(backoff_delay)

                        # Inject retry guidance as system message
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
                            "Injecting retry prompt (streaming)",
                            extra={
                                "reason": retry_reason,
                                "attempt": retry_state.attempts,
                                "strategies_tried": retry_state.strategies_tried,
                            },
                        )

                        # Record successful retry metric
                        self.metrics.increment(
                            "retry_prompt_injected", labels={"reason": retry_reason}
                        )

                    else:
                        # Retry not triggered or max attempts reached
                        if should_retry:
                            # Max attempts reached - record failure
                            self.metrics.increment(
                                "retry_max_attempts_reached", labels={"reason": retry_reason}
                            )

                    # Continue loop - LLM will process tool results
                    continue

                # No tool calls - check for intent without action
                if self.settings.intent_detection_enabled and response.content:
                    detected_intent = IntentDetector.detect_intent(response.content)

                    if detected_intent and detected_intent.confidence >= 0.8:
                        # Record intent detection hit
                        self.metrics.increment(
                            "intent_detection_hits",
                            labels={
                                "intent_type": detected_intent.intent_type.value,
                                "confidence_bucket": self._confidence_bucket(
                                    detected_intent.confidence
                                ),
                            },
                        )

                        # Agent stated intent but didn't act - prompt to act
                        if retry_state.should_retry(self.settings.max_retry_attempts):
                            self.metrics.increment(
                                "retry_attempts", labels={"reason": "intent_without_action"}
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
                                "Detected intent without action, nudging agent (streaming)",
                                extra={
                                    "intent_type": detected_intent.intent_type.value,
                                    "confidence": detected_intent.confidence,
                                    "attempt": retry_state.attempts,
                                },
                            )
                            continue

                    # Check for premature giving up
                    if IntentDetector.detect_premature_giving_up(response.content):
                        if retry_state.empty_result_count > 0 and retry_state.should_retry(
                            self.settings.max_retry_attempts
                        ):
                            # Agent giving up after empty results - encourage retry
                            nudge_message = {
                                "role": "system",
                                "content": RetryPromptGenerator.generate_retry_prompt(
                                    "empty_logs", retry_state
                                ),
                            }
                            messages.append(nudge_message)
                            retry_state.record_attempt("giving_up_prevention", {}, "premature_exit")
                            logger.info(
                                "Detected premature giving up, encouraging retry (streaming)",
                                extra={
                                    "empty_result_count": retry_state.empty_result_count,
                                    "attempt": retry_state.attempts,
                                },
                            )
                            continue

                # No tool calls and no retry needed - stream the final response
                if response.content:
                    self.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )
                    # TODO: Real streaming with tool calls is complex. For MVP, we're "simulating" streaming
                    # by yielding the full response character-by-character. This gives the UI a streaming
                    # effect but doesn't reduce latency for the first token.
                    # Post-MVP: Implement true streaming with incremental tool calling.
                    for char in response.content:
                        yield char
                    return
                else:
                    error_msg = "Received empty response from LLM"
                    self.conversation_history.append({"role": "assistant", "content": error_msg})
                    yield error_msg
                    return

            except LLMProviderError as e:
                error_msg = f"LLM provider error: {str(e)}"
                yield error_msg
                return
            except Exception as e:
                # Log the error for self-direction features but don't fail the request
                logger.warning(
                    "Error in self-direction logic (streaming), continuing",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                error_msg = f"Unexpected error: {str(e)}"
                yield error_msg
                return

        # Hit max iterations
        error_msg = f"Maximum tool iterations ({max_iterations}) exceeded."
        self.conversation_history.append({"role": "assistant", "content": error_msg})
        yield error_msg

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

                # Execute tool
                result = await self.tool_registry.execute(function_name, **function_args)

                # Update to SUCCESS
                record.status = ToolCallStatus.SUCCESS
                record.result = result
                record.completed_at = datetime.now()
                self._notify_tool_call(record)

                # Process through context manager (may cache large results)
                tool_result = {"tool_call_id": tool_call_id, "result": result}
                processed_result = await self._process_tool_result(tool_result, function_name)

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

                is_empty = False

                if count == 0:
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
        # Base delays for first few attempts
        base_delays = [0.5, 1.0, 2.0]

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
