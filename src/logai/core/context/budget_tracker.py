"""Context budget tracking and enforcement."""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from logai.config.settings import LogAISettings
from logai.core.context.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class AllocationStrategy(Enum):
    """Context allocation strategies."""

    ADAPTIVE = "adaptive"  # Default: balance based on conversation state
    HISTORY_FOCUSED = "history-focused"  # Prioritize conversation history
    RESULT_FOCUSED = "result-focused"  # Prioritize tool results


@dataclass
class BudgetAllocation:
    """Token budget allocation for context components."""

    total_window: int
    system_prompt: int
    history: int
    results: int
    response_reserve: int
    safety_buffer: int

    @property
    def usable_tokens(self) -> int:
        """Total usable tokens (excluding safety buffer)."""
        return self.total_window - self.safety_buffer

    @property
    def available_for_content(self) -> int:
        """Tokens available for history + results."""
        return self.usable_tokens - self.system_prompt - self.response_reserve


@dataclass
class BudgetUsage:
    """Current token usage statistics."""

    system_prompt_tokens: int = 0
    history_tokens: int = 0
    result_tokens: int = 0
    total_tokens: int = 0
    remaining_tokens: int = 0
    utilization_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "system_prompt_tokens": self.system_prompt_tokens,
            "history_tokens": self.history_tokens,
            "result_tokens": self.result_tokens,
            "total_tokens": self.total_tokens,
            "remaining_tokens": self.remaining_tokens,
            "utilization_pct": round(self.utilization_pct, 1),
        }


@dataclass
class ContextMessage:
    """A tracked message in the context."""

    role: str
    content: str
    tokens: int
    is_system: bool = False
    is_tool_result: bool = False
    tool_call_id: str | None = None
    timestamp: float = field(default_factory=lambda: time.time())

    # Messages marked as important won't be pruned
    important: bool = False


class ContextBudgetTracker:
    """
    Tracks and enforces token budgets for LLM context management.

    The tracker maintains a stateful view of the context and provides:
    - Real-time budget monitoring
    - Automatic enforcement of limits
    - Adaptive allocation based on conversation state
    - History pruning recommendations

    Thread Safety: The tracker is designed for single-threaded use within
    an orchestrator instance. For multi-threaded scenarios, external
    synchronization is required.
    """

    def __init__(
        self,
        settings: LogAISettings,
        model: str | None = None,
        strategy: AllocationStrategy = AllocationStrategy.ADAPTIVE,
    ):
        """
        Initialize budget tracker.

        Args:
            settings: Application settings
            model: Model name (auto-detected from settings if None)
            strategy: Allocation strategy to use
        """
        self.settings = settings
        self.model = model or settings.current_llm_model
        self.strategy = strategy

        # Get context window for model
        self.context_window = TokenCounter.get_context_window(self.model)

        # Calculate initial allocation
        self.allocation = self._calculate_allocation()

        # Track messages
        self._system_prompt: str | None = None
        self._system_prompt_tokens: int = 0
        self._messages: list[ContextMessage] = []
        self._pending_results_tokens: int = 0

        logger.info(
            f"ContextBudgetTracker initialized: model={self.model}, "
            f"context_window={self.context_window}, strategy={self.strategy.value}"
        )

    def _calculate_allocation(self) -> BudgetAllocation:
        """
        Calculate token budget allocation based on strategy.

        Returns:
            BudgetAllocation with component budgets
        """
        # Base allocations (percentage of context window)
        safety_buffer_pct = 0.05  # 5% safety margin
        response_reserve_pct = 0.04  # 4% for response
        system_prompt_pct = 0.05  # 5% for system prompt

        # Calculate fixed allocations
        safety_buffer = int(self.context_window * safety_buffer_pct)
        response_reserve = int(self.context_window * response_reserve_pct)
        system_prompt = int(self.context_window * system_prompt_pct)

        # Remaining tokens for history and results
        remaining = self.context_window - safety_buffer - response_reserve - system_prompt

        # Split remaining based on strategy
        if self.strategy == AllocationStrategy.HISTORY_FOCUSED:
            history = int(remaining * 0.65)
            results = remaining - history
        elif self.strategy == AllocationStrategy.RESULT_FOCUSED:
            results = int(remaining * 0.60)
            history = remaining - results
        else:  # ADAPTIVE
            # Start with balanced 50/50 split
            history = int(remaining * 0.55)
            results = remaining - history

        return BudgetAllocation(
            total_window=self.context_window,
            system_prompt=system_prompt,
            history=history,
            results=results,
            response_reserve=response_reserve,
            safety_buffer=safety_buffer,
        )

    def set_system_prompt(self, prompt: str) -> bool:
        """
        Set the system prompt and track its tokens.

        Args:
            prompt: System prompt text

        Returns:
            True if prompt fits in budget, False if truncated
        """
        tokens = TokenCounter.count_tokens(prompt, self.model)

        if tokens > self.allocation.system_prompt:
            logger.warning(
                f"System prompt exceeds budget ({tokens} > {self.allocation.system_prompt}), "
                f"will be truncated in context"
            )
            # We still store it, but flag the overage
            self._system_prompt = prompt
            self._system_prompt_tokens = tokens
            return False

        self._system_prompt = prompt
        self._system_prompt_tokens = tokens
        return True

    def add_message(
        self,
        message: dict[str, Any],
        important: bool = False,
    ) -> bool:
        """
        Add a message to tracking.

        Args:
            message: Message dict with 'role' and 'content'
            important: Mark message as important (won't be pruned)

        Returns:
            True if message fits, False if it would exceed budget
        """
        role = message.get("role", "")
        content = message.get("content", "")
        tool_call_id = message.get("tool_call_id")

        # Handle different content types
        if isinstance(content, str):
            content_str = content
        elif isinstance(content, dict):
            content_str = json.dumps(content)
        else:
            content_str = str(content)

        tokens = TokenCounter.count_tokens(content_str, self.model)

        # Check if adding this would exceed budget
        current_usage = self.get_usage()
        projected_total = current_usage.total_tokens + tokens

        if projected_total > self.allocation.usable_tokens:
            logger.warning(
                f"Message would exceed budget ({projected_total} > {self.allocation.usable_tokens})"
            )
            return False

        ctx_msg = ContextMessage(
            role=role,
            content=content_str,
            tokens=tokens,
            is_system=(role == "system"),
            is_tool_result=(role == "tool"),
            tool_call_id=tool_call_id,
            important=important,
        )

        self._messages.append(ctx_msg)
        return True

    def can_fit_result(self, result: dict[str, Any]) -> tuple[bool, int]:
        """
        Check if a tool result can fit in the context.

        Args:
            result: Tool result dictionary

        Returns:
            Tuple of (can_fit, token_count)
        """
        tokens = TokenCounter.estimate_json_tokens(result, self.model)
        current_usage = self.get_usage()

        # Check against result budget specifically
        result_budget_remaining = self.allocation.results - current_usage.result_tokens

        can_fit = tokens <= result_budget_remaining
        return can_fit, tokens

    def should_cache_result(
        self, result: dict[str, Any], threshold: int = 10000
    ) -> tuple[bool, int]:
        """
        Determine if a result should be cached based on size.

        Args:
            result: Tool result dictionary
            threshold: Token threshold for caching

        Returns:
            Tuple of (should_cache, token_count)
        """
        tokens = TokenCounter.estimate_json_tokens(result, self.model)

        # Cache if exceeds threshold OR if it won't fit in budget
        can_fit, _ = self.can_fit_result(result)

        should_cache = tokens > threshold or not can_fit
        return should_cache, tokens

    def add_result_tokens(self, tokens: int) -> None:
        """
        Track tokens from a tool result (used after caching decision).

        Args:
            tokens: Number of tokens to track
        """
        self._pending_results_tokens += tokens

    def get_usage(self) -> BudgetUsage:
        """
        Get current token usage statistics.

        Returns:
            BudgetUsage with current stats
        """
        # Sum tokens by category
        history_tokens = sum(
            m.tokens for m in self._messages if not m.is_tool_result and not m.is_system
        )

        result_tokens = (
            sum(m.tokens for m in self._messages if m.is_tool_result) + self._pending_results_tokens
        )

        system_tokens = self._system_prompt_tokens + sum(
            m.tokens for m in self._messages if m.is_system
        )

        total = system_tokens + history_tokens + result_tokens

        usable = self.allocation.usable_tokens
        remaining = max(0, usable - total)
        utilization = (total / usable * 100) if usable > 0 else 100.0

        return BudgetUsage(
            system_prompt_tokens=system_tokens,
            history_tokens=history_tokens,
            result_tokens=result_tokens,
            total_tokens=total,
            remaining_tokens=remaining,
            utilization_pct=utilization,
        )

    def should_prune_history(self, threshold_pct: float = 80.0) -> bool:
        """
        Check if history should be pruned based on utilization.

        Args:
            threshold_pct: Utilization percentage threshold

        Returns:
            True if history should be pruned
        """
        usage = self.get_usage()
        return usage.utilization_pct >= threshold_pct

    def get_prunable_messages(self, target_tokens: int) -> list[int]:
        """
        Get indices of messages that can be pruned to free target tokens.

        Uses FIFO with role-based preservation:
        - Never prune system messages
        - Never prune important messages
        - Preserve most recent N messages

        Args:
            target_tokens: Target tokens to free

        Returns:
            List of message indices to prune (oldest first)
        """
        # Keep at least the 4 most recent non-system messages
        PRESERVE_RECENT = 4

        prunable: list[tuple[int, int]] = []  # (index, tokens)

        # Find prunable messages (oldest first, skip system and important)
        for i, msg in enumerate(self._messages):
            if msg.is_system or msg.important:
                continue
            prunable.append((i, msg.tokens))

        # Don't prune the most recent messages
        if len(prunable) > PRESERVE_RECENT:
            prunable = prunable[:-PRESERVE_RECENT]
        else:
            prunable = []

        # Select messages to prune until we hit target
        to_prune: list[int] = []
        freed_tokens = 0

        for idx, tokens in prunable:
            if freed_tokens >= target_tokens:
                break
            to_prune.append(idx)
            freed_tokens += tokens

        return to_prune

    def prune_messages(self, indices: list[int]) -> list[ContextMessage]:
        """
        Remove messages at specified indices.

        Args:
            indices: Message indices to remove

        Returns:
            List of pruned messages
        """
        if not indices:
            return []

        # Sort descending to remove from end first (preserve indices)
        sorted_indices = sorted(indices, reverse=True)

        pruned = []
        for idx in sorted_indices:
            if 0 <= idx < len(self._messages):
                pruned.append(self._messages.pop(idx))

        pruned.reverse()  # Return in original order

        logger.info(f"Pruned {len(pruned)} messages, freed ~{sum(m.tokens for m in pruned)} tokens")

        return pruned

    def reset(self) -> None:
        """Reset tracker state for new conversation."""
        self._system_prompt = None
        self._system_prompt_tokens = 0
        self._messages.clear()
        self._pending_results_tokens = 0

        logger.debug("Budget tracker reset")

    def get_status_display(self) -> str:
        """
        Get a short status string for UI display.

        Returns:
            Status string like "Context: 45%" or "Context: 92% (!)"
        """
        usage = self.get_usage()
        pct = usage.utilization_pct

        if pct >= 90:
            return f"Context: {pct:.0f}% (!)"
        elif pct >= 70:
            return f"Context: {pct:.0f}%"
        else:
            return f"Context: {pct:.0f}%"
