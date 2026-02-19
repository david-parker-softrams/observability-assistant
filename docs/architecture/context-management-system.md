# Architecture: Intelligent Context Management System

**Author:** Saanvi (Senior Software Architect)
**Date:** February 12, 2026
**Version:** 1.0
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Component Specifications](#3-component-specifications)
4. [Integration Points](#4-integration-points)
5. [Token Counting Strategy](#5-token-counting-strategy)
6. [Budget Allocation Algorithm](#6-budget-allocation-algorithm)
7. [Caching Strategy](#7-caching-strategy)
8. [History Management](#8-history-management)
9. [Error Handling](#9-error-handling)
10. [Performance Considerations](#10-performance-considerations)
11. [Testing Strategy](#11-testing-strategy)
12. [Implementation Phases](#12-implementation-phases)
13. [File Structure](#13-file-structure)
14. [Migration Strategy](#14-migration-strategy)
15. [Future Enhancements](#15-future-enhancements)

---

## 1. Executive Summary

### 1.1 Problem Statement

The LogAI system has a **critical context window overflow vulnerability**. CloudWatch queries can return up to 1,000 events (~500-700 KB of JSON), which are serialized directly into the agent's conversation history with zero validation. After 2-3 large queries, the context window overflows and the agent fails catastrophically.

### 1.2 Solution Overview

This architecture defines an **Intelligent Context Management System** comprising five core components:

1. **TokenCounter** - Fast, accurate token counting across all LLM providers
2. **ContextBudgetTracker** - Real-time budget monitoring and enforcement
3. **ResultCacheManager** - External storage for oversized results with intelligent summaries
4. **FetchCachedResultTool** - Agent tool for incremental result retrieval
5. **HistoryManager** - Sliding window pruning with smart context preservation

### 1.3 Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Token Counting** | tiktoken + fallback heuristics | Industry standard, accurate for OpenAI/Claude, fast (<1ms) |
| **Budget Tracker** | Stateful, recalculates on access | Balance of accuracy and performance; handles message mutations |
| **Cache Storage** | Extend SQLiteStore | Leverage existing infrastructure, proven reliability |
| **History Pruning** | FIFO with role-based preservation | Simple, predictable, preserves critical context |
| **Allocation Strategies** | Adaptive only in v1 | Complexity vs. value; adaptive handles 95% of cases |
| **Result Summaries** | Metadata + sampling + statistics | Give agent enough info to make smart fetch decisions |

### 1.4 Design Principles

1. **Never Overflow** - Hard limits enforced at every entry point
2. **Graceful Degradation** - Cache failures fall back to truncation, not crashes
3. **Agent Autonomy** - Agent decides what to fetch based on intelligent summaries
4. **User Visibility** - Clear notifications about context management actions
5. **Performance First** - All operations within strict latency budgets
6. **Extensibility** - Clean interfaces for future enhancements

---

## 2. System Architecture

### 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                USER INTERFACE                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐ │
│  │ Status Bar  │  │   Toasts    │  │         Chat Messages               │ │
│  │ [Context:45%│  │ "Result     │  │                                     │ │
│  │  ████░░░░░] │  │  cached..." │  │                                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────────┘ │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             LLM ORCHESTRATOR                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      ContextBudgetTracker                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │   System    │  │   History   │  │   Results   │  │  Response   │  │ │
│  │  │   Prompt    │  │   Budget    │  │   Budget    │  │   Reserve   │  │ │
│  │  │   ~8K       │  │   ~80K      │  │   ~50K      │  │   ~8K       │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                       │                                     │
│  ┌────────────────────┐  ┌────────────┴────────────┐  ┌──────────────────┐ │
│  │   TokenCounter     │  │    HistoryManager       │  │ ResultCacheManager│ │
│  │                    │  │                         │  │                  │ │
│  │ count_tokens()     │  │ prune_oldest()          │  │ cache_result()   │ │
│  │ count_messages()   │  │ get_preserved()         │  │ get_summary()    │ │
│  │ estimate_json()    │  │ should_prune()          │  │ fetch_chunk()    │ │
│  └────────────────────┘  └─────────────────────────┘  └────────┬─────────┘ │
└──────────────────────────────────────────────────────────────────┼──────────┘
                                                                   │
                                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOOL REGISTRY                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐│
│  │list_log_groups│ │ fetch_logs   │  │ search_logs  │  │fetch_cached_chunk ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘│
└──────────────────────────────────────────────────────────────────┬──────────┘
                                                                   │
                                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                   │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │           SQLiteStore           │  │       ResultCache (NEW)         │  │
│  │  ┌─────────────────────────┐    │  │  ┌─────────────────────────┐   │  │
│  │  │    cache_entries        │    │  │  │   cached_results        │   │  │
│  │  │    (existing)           │    │  │  │   (NEW TABLE)           │   │  │
│  │  └─────────────────────────┘    │  │  └─────────────────────────┘   │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        TOOL RESULT PROCESSING FLOW                            │
└──────────────────────────────────────────────────────────────────────────────┘

CloudWatch Tool Returns Result
            │
            ▼
    ┌───────────────────┐
    │ TokenCounter      │
    │ count_json_tokens │──────────────────────┐
    └───────────────────┘                      │
            │                                  │
            ▼                                  ▼
    ┌───────────────────┐              ┌───────────────────┐
    │ result_tokens <   │──── YES ────▶│ Add directly to   │
    │ cache_threshold?  │              │ context + history │
    └───────────────────┘              └───────────────────┘
            │                                  │
           NO                                  │
            │                                  │
            ▼                                  │
    ┌───────────────────┐                      │
    │ ResultCacheManager│                      │
    │ cache_result()    │                      │
    └───────────────────┘                      │
            │                                  │
            ├──────────────────┐               │
            ▼                  ▼               │
    ┌───────────────┐  ┌───────────────┐       │
    │ Store full    │  │ Generate      │       │
    │ result in DB  │  │ summary       │       │
    └───────────────┘  └───────────────┘       │
                               │               │
                               ▼               │
                       ┌───────────────┐       │
                       │ Add summary   │       │
                       │ to context    │◀──────┘
                       └───────────────┘
                               │
                               ▼
                       ┌───────────────┐
                       │ Send toast:   │
                       │ "Result cached│
                       │ (1,000 events)│
                       └───────────────┘
```

### 2.3 Context Budget Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT BUDGET ENFORCEMENT                            │
└──────────────────────────────────────────────────────────────────────────────┘

                    Context Window: 200,000 tokens
    ┌─────────────────────────────────────────────────────────────────────┐
    │                                                                     │
    │  ┌──────────┐  ┌─────────────────────────┐  ┌──────────┐  ┌──────┐│
    │  │ System   │  │      Conversation       │  │  Result  │  │ Resp ││
    │  │ Prompt   │  │       History           │  │  Space   │  │ Rsrv ││
    │  │          │  │                         │  │          │  │      ││
    │  │  10K     │  │         80K             │  │   50K    │  │  8K  ││
    │  │ (fixed)  │  │    (sliding window)     │  │ (shared) │  │(safe)││
    │  └──────────┘  └─────────────────────────┘  └──────────┘  └──────┘│
    │                                                                     │
    │  ◀──────────────── 148K usable ─────────────────▶  ◀── 52K buffer ─▶│
    └─────────────────────────────────────────────────────────────────────┘

    ENFORCEMENT POINTS:

    1. System Prompt: Hard limit 10K tokens (truncate if exceeded)
    2. History:       Sliding window, prune when > 80K
    3. Results:       Cache if > cache_threshold (10K default)
    4. Response:      Always reserve 8K for LLM response
    5. Buffer:        52K safety margin (never touch)
```

---

## 3. Component Specifications

### 3.1 TokenCounter

**Location:** `src/logai/core/context/token_counter.py`

**Purpose:** Fast, accurate token counting for all supported LLM providers.

**Design Decision: tiktoken + Fallback Heuristics**

After careful analysis, I recommend using `tiktoken` as the primary token counter with fallback heuristics:

- **tiktoken** is the official OpenAI tokenizer, used by both GPT-4 and Claude models
- It's extremely fast (<1ms per call for typical content)
- Accuracy is within 1-2% for OpenAI/Anthropic models
- For Ollama, we use a character-based heuristic (chars/3.5) which is conservative

```python
"""Token counting utilities for context management."""

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy load tiktoken to avoid startup cost
_tokenizer_cache: dict[str, Any] = {}


class TokenCounter:
    """
    Fast, accurate token counting for LLM context management.

    Uses tiktoken for OpenAI/Claude models with fallback heuristics
    for unsupported models. All methods are static for ease of use.

    Performance: <1ms for typical content, <10ms for very large content (500KB)
    Accuracy: Within ±5% for supported models
    """

    # Model family to tokenizer encoding mapping
    MODEL_ENCODINGS: dict[str, str] = {
        # OpenAI models
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        # Anthropic models (use cl100k_base as approximation)
        "claude": "cl100k_base",
        # GitHub Copilot (uses GPT-4 or Claude backend)
        "github-copilot": "cl100k_base",
    }

    # Default tokens per character for unknown models (conservative)
    DEFAULT_CHARS_PER_TOKEN: float = 3.5

    # Context window sizes by model family
    CONTEXT_WINDOWS: dict[str, int] = {
        "gpt-4-turbo": 128_000,
        "gpt-4o": 128_000,
        "gpt-4": 8_192,
        "claude-3-5-sonnet": 200_000,
        "claude-3-opus": 200_000,
        "claude-opus-4": 200_000,
        "claude-sonnet-4": 200_000,
        "llama3.1:8b": 8_192,
        "llama3.1:70b": 128_000,
        # Default for unknown models
        "default": 8_192,
    }

    @classmethod
    def _get_encoding(cls, model: str) -> Any:
        """
        Get or create tokenizer encoding for a model.

        Uses lazy loading and caching for performance.

        Args:
            model: Model name or identifier

        Returns:
            tiktoken Encoding object or None if unavailable
        """
        # Check cache first
        if model in _tokenizer_cache:
            return _tokenizer_cache[model]

        # Find the right encoding
        encoding_name = None
        model_lower = model.lower()

        for model_prefix, enc_name in cls.MODEL_ENCODINGS.items():
            if model_prefix in model_lower:
                encoding_name = enc_name
                break

        if encoding_name is None:
            _tokenizer_cache[model] = None
            return None

        try:
            import tiktoken
            encoding = tiktoken.get_encoding(encoding_name)
            _tokenizer_cache[model] = encoding
            return encoding
        except ImportError:
            logger.warning("tiktoken not installed, using character-based estimation")
            _tokenizer_cache[model] = None
            return None
        except Exception as e:
            logger.warning(f"Failed to load tokenizer for {model}: {e}")
            _tokenizer_cache[model] = None
            return None

    @classmethod
    def count_tokens(cls, text: str, model: str = "claude-3-5-sonnet") -> int:
        """
        Count tokens in text for a specific model.

        Args:
            text: Text to count tokens for
            model: Model name (used to select tokenizer)

        Returns:
            Estimated token count

        Performance: <1ms for typical content
        """
        if not text:
            return 0

        encoding = cls._get_encoding(model)

        if encoding is not None:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed, using fallback: {e}")

        # Fallback: character-based estimation (conservative)
        return int(len(text) / cls.DEFAULT_CHARS_PER_TOKEN) + 1

    @classmethod
    def count_message_tokens(
        cls,
        messages: list[dict[str, Any]],
        model: str = "claude-3-5-sonnet"
    ) -> int:
        """
        Count total tokens in a list of messages.

        Accounts for message overhead (role tokens, separators, etc.)

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name

        Returns:
            Total estimated token count
        """
        if not messages:
            return 0

        total = 0

        # Per-message overhead: role tokens + separators
        # This is approximately 4 tokens per message for most models
        MESSAGE_OVERHEAD = 4

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += cls.count_tokens(content, model)
            elif isinstance(content, list):
                # Handle multi-part content (e.g., images)
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += cls.count_tokens(part["text"], model)

            # Add overhead for role and separators
            total += MESSAGE_OVERHEAD

            # Count tool_calls if present
            tool_calls = msg.get("tool_calls", [])
            for tool_call in tool_calls:
                # Tool call overhead: function name + arguments
                func = tool_call.get("function", {})
                total += cls.count_tokens(func.get("name", ""), model) + 2
                total += cls.count_tokens(func.get("arguments", ""), model)

        return total

    @classmethod
    def estimate_json_tokens(
        cls,
        data: dict[str, Any],
        model: str = "claude-3-5-sonnet"
    ) -> int:
        """
        Estimate tokens for JSON-serialized data without serializing.

        This is a fast estimation method that avoids the cost of
        json.dumps() for large objects. Accuracy is within 10%.

        Args:
            data: Dictionary to estimate
            model: Model name

        Returns:
            Estimated token count
        """
        import json

        # For small objects, just serialize and count
        # (faster than traversing the structure)
        try:
            json_str = json.dumps(data, separators=(',', ':'))
            return cls.count_tokens(json_str, model)
        except (TypeError, ValueError) as e:
            logger.warning(f"JSON serialization failed: {e}")
            # Fallback: rough estimate based on str representation
            return cls.count_tokens(str(data), model)

    @classmethod
    def get_context_window(cls, model: str) -> int:
        """
        Get context window size for a model.

        Args:
            model: Model name

        Returns:
            Context window size in tokens
        """
        model_lower = model.lower()

        for model_prefix, window_size in cls.CONTEXT_WINDOWS.items():
            if model_prefix in model_lower:
                return window_size

        return cls.CONTEXT_WINDOWS["default"]

    @classmethod
    def will_fit(
        cls,
        text: str,
        current_tokens: int,
        max_tokens: int,
        model: str = "claude-3-5-sonnet"
    ) -> bool:
        """
        Quick check if text will fit in remaining budget.

        Args:
            text: Text to check
            current_tokens: Current token usage
            max_tokens: Maximum allowed tokens
            model: Model name

        Returns:
            True if text will fit
        """
        text_tokens = cls.count_tokens(text, model)
        return (current_tokens + text_tokens) <= max_tokens
```

### 3.2 ContextBudgetTracker

**Location:** `src/logai/core/context/budget_tracker.py`

**Purpose:** Track and enforce token budgets across all context components.

**Design Decision: Stateful with Validation on Access**

The tracker maintains state (tracked messages) but validates/recalculates on each budget check. This provides:
- Fast operations (O(1) budget checks most of the time)
- Accuracy (recalculates when messages mutate)
- Thread safety (no shared mutable state during calculations)

```python
"""Context budget tracking and enforcement."""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from logai.config.settings import LogAISettings
from logai.core.context.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class AllocationStrategy(Enum):
    """Context allocation strategies."""
    ADAPTIVE = "adaptive"  # Default: balance based on conversation state
    HISTORY_FOCUSED = "history_focused"  # Prioritize conversation history
    RESULT_FOCUSED = "result_focused"  # Prioritize tool results


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
    timestamp: float = field(default_factory=lambda: __import__('time').time())

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
            f"ContextBudgetTracker initialized",
            extra={
                "model": self.model,
                "context_window": self.context_window,
                "strategy": self.strategy.value,
            }
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

    def should_cache_result(self, result: dict[str, Any], threshold: int = 10000) -> tuple[bool, int]:
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
            m.tokens for m in self._messages
            if not m.is_tool_result and not m.is_system
        )

        result_tokens = sum(
            m.tokens for m in self._messages if m.is_tool_result
        ) + self._pending_results_tokens

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

        logger.info(
            f"Pruned {len(pruned)} messages, freed ~{sum(m.tokens for m in pruned)} tokens"
        )

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
```

### 3.3 ResultCacheManager

**Location:** `src/logai/core/context/result_cache.py`

**Purpose:** Cache large tool results outside the context window and provide intelligent summaries.

**Design Decision: Extend SQLiteStore**

Using the existing SQLiteStore infrastructure:
- Proven reliability and performance
- Consistent with existing caching patterns
- Reduces maintenance burden
- Automatic TTL and size management

```python
"""Result cache manager for large tool results."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class CachedResultSummary:
    """Summary of a cached result for context inclusion."""
    cache_id: str
    total_events: int
    time_range: dict[str, Any]
    sample_events: list[dict[str, Any]]
    event_statistics: dict[str, int]
    original_tool: str
    original_query: dict[str, Any]
    cached_at: int
    expires_at: int

    def to_context_dict(self) -> dict[str, Any]:
        """
        Convert to dict suitable for LLM context.

        This is what the agent sees instead of the full result.
        """
        return {
            "cached": True,
            "cache_id": self.cache_id,
            "summary": {
                "total_events": self.total_events,
                "time_range": self.time_range,
                "sample_events": self.sample_events,
                "event_statistics": self.event_statistics,
            },
            "original_query": {
                "tool": self.original_tool,
                "parameters": self.original_query,
            },
            "cache_info": {
                "cached_at": self.cached_at,
                "expires_in_seconds": max(0, self.expires_at - int(time.time())),
            },
            "instructions": (
                "This result was cached because it exceeded the context window limit. "
                "Use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve "
                "specific events. You can also filter by time_range or search_pattern."
            ),
        }


class ResultCacheManager:
    """
    Manages caching of large tool results outside the context window.

    When a tool result is too large for the context window, this manager:
    1. Stores the full result in SQLite
    2. Generates an intelligent summary
    3. Provides chunk-based retrieval

    Performance targets:
    - Cache storage: <50ms
    - Summary generation: <10ms
    - Chunk retrieval: <100ms
    """

    # Configuration
    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    MAX_SAMPLE_EVENTS = 5
    MAX_CACHE_SIZE_MB = 100

    def __init__(
        self,
        cache_dir: Path,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_size_mb: int = MAX_CACHE_SIZE_MB,
    ):
        """
        Initialize result cache manager.

        Args:
            cache_dir: Directory for cache database
            ttl_seconds: Time-to-live for cached results
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "result_cache.db"
        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Create cached results table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cached_results (
                    cache_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    query_params TEXT NOT NULL,
                    result_data TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    data_size_bytes INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_accessed INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Create indexes for efficient queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_results_expires
                ON cached_results(expires_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_results_created
                ON cached_results(created_at DESC)
            """)

            await db.commit()

        self._initialized = True
        logger.debug(f"ResultCacheManager initialized at {self.db_path}")

    def _generate_cache_id(
        self,
        tool_name: str,
        query_params: dict[str, Any]
    ) -> str:
        """
        Generate a unique cache ID for a result.

        Uses hash of tool name + query parameters for deduplication.
        """
        content = f"{tool_name}:{json.dumps(query_params, sort_keys=True)}"
        hash_digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"result_{hash_digest}"

    def _extract_event_statistics(
        self,
        events: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        Extract statistics from events for the summary.

        Analyzes log levels, error types, and patterns.
        """
        stats: dict[str, int] = {}

        for event in events:
            message = event.get("message", "")

            # Count by log level (heuristic detection)
            message_upper = message.upper()
            if "ERROR" in message_upper or "EXCEPTION" in message_upper:
                stats["ERROR"] = stats.get("ERROR", 0) + 1
            elif "WARN" in message_upper:
                stats["WARN"] = stats.get("WARN", 0) + 1
            elif "INFO" in message_upper:
                stats["INFO"] = stats.get("INFO", 0) + 1
            elif "DEBUG" in message_upper:
                stats["DEBUG"] = stats.get("DEBUG", 0) + 1
            else:
                stats["OTHER"] = stats.get("OTHER", 0) + 1

        return stats

    def _extract_time_range(
        self,
        events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Extract time range from events."""
        if not events:
            return {"start": None, "end": None}

        timestamps = [
            e.get("timestamp") for e in events
            if e.get("timestamp") is not None
        ]

        if not timestamps:
            return {"start": None, "end": None}

        return {
            "start": min(timestamps),
            "end": max(timestamps),
            "span_ms": max(timestamps) - min(timestamps),
        }

    def _sample_events(
        self,
        events: list[dict[str, Any]],
        count: int = MAX_SAMPLE_EVENTS
    ) -> list[dict[str, Any]]:
        """
        Sample representative events for the summary.

        Strategy: Take first, last, and evenly distributed middle samples.
        This gives the agent a sense of the data distribution.
        """
        if len(events) <= count:
            return events

        sampled = []

        # Always include first event
        sampled.append(events[0])

        # Include evenly distributed middle events
        if count > 2:
            step = len(events) // (count - 1)
            for i in range(1, count - 1):
                idx = min(i * step, len(events) - 1)
                if events[idx] not in sampled:
                    sampled.append(events[idx])

        # Always include last event
        if events[-1] not in sampled:
            sampled.append(events[-1])

        return sampled[:count]

    async def cache_result(
        self,
        tool_name: str,
        query_params: dict[str, Any],
        result: dict[str, Any],
    ) -> CachedResultSummary:
        """
        Cache a large tool result and return a summary.

        Args:
            tool_name: Name of the tool that generated the result
            query_params: Parameters passed to the tool
            result: Full result dictionary

        Returns:
            CachedResultSummary for context inclusion
        """
        await self.initialize()

        # Generate cache ID
        cache_id = self._generate_cache_id(tool_name, query_params)

        # Extract events (handle different result formats)
        events = result.get("events", result.get("logs", []))
        if not isinstance(events, list):
            events = []

        # Generate summary components
        event_stats = self._extract_event_statistics(events)
        time_range = self._extract_time_range(events)
        sample_events = self._sample_events(events)

        # Serialize result
        result_json = json.dumps(result)
        data_size = len(result_json.encode('utf-8'))

        now = int(time.time())
        expires_at = now + self.ttl_seconds

        # Store in database
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("""
                INSERT OR REPLACE INTO cached_results
                (cache_id, tool_name, query_params, result_data, event_count,
                 data_size_bytes, created_at, expires_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                cache_id,
                tool_name,
                json.dumps(query_params),
                result_json,
                len(events),
                data_size,
                now,
                expires_at,
                now,
            ))
            await db.commit()

        logger.info(
            f"Cached result {cache_id}: {len(events)} events, {data_size} bytes"
        )

        # Enforce cache size limit
        await self._enforce_size_limit()

        return CachedResultSummary(
            cache_id=cache_id,
            total_events=len(events),
            time_range=time_range,
            sample_events=sample_events,
            event_statistics=event_stats,
            original_tool=tool_name,
            original_query=query_params,
            cached_at=now,
            expires_at=expires_at,
        )

    async def fetch_chunk(
        self,
        cache_id: str,
        offset: int = 0,
        limit: int = 100,
        filter_pattern: str | None = None,
        time_start: int | None = None,
        time_end: int | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a chunk of events from a cached result.

        Args:
            cache_id: Cache ID from summary
            offset: Starting index (0-based)
            limit: Number of events to fetch (max 200)
            filter_pattern: Optional text pattern to filter events
            time_start: Optional start timestamp filter
            time_end: Optional end timestamp filter

        Returns:
            Dictionary with events and metadata
        """
        await self.initialize()

        # Enforce limit
        limit = min(limit, 200)

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Fetch cached result
            async with db.execute("""
                SELECT result_data, event_count, expires_at
                FROM cached_results
                WHERE cache_id = ?
            """, (cache_id,)) as cursor:
                row = await cursor.fetchone()

            if not row:
                return {
                    "success": False,
                    "error": f"Cache entry '{cache_id}' not found",
                    "hint": "The cached result may have expired. Re-run the original query.",
                }

            result_data, event_count, expires_at = row

            # Check expiration
            if expires_at < int(time.time()):
                await db.execute(
                    "DELETE FROM cached_results WHERE cache_id = ?",
                    (cache_id,)
                )
                await db.commit()
                return {
                    "success": False,
                    "error": f"Cache entry '{cache_id}' has expired",
                    "hint": "Re-run the original query to get fresh results.",
                }

            # Update access stats
            await db.execute("""
                UPDATE cached_results
                SET last_accessed = ?, access_count = access_count + 1
                WHERE cache_id = ?
            """, (int(time.time()), cache_id))
            await db.commit()

        # Parse result
        try:
            result = json.loads(result_data)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse cached result",
            }

        # Extract events
        events = result.get("events", result.get("logs", []))

        # Apply filters
        filtered_events = events

        if filter_pattern:
            pattern_lower = filter_pattern.lower()
            filtered_events = [
                e for e in filtered_events
                if pattern_lower in e.get("message", "").lower()
            ]

        if time_start is not None:
            filtered_events = [
                e for e in filtered_events
                if e.get("timestamp", 0) >= time_start
            ]

        if time_end is not None:
            filtered_events = [
                e for e in filtered_events
                if e.get("timestamp", float('inf')) <= time_end
            ]

        # Apply pagination
        total_filtered = len(filtered_events)
        chunk = filtered_events[offset:offset + limit]

        return {
            "success": True,
            "cache_id": cache_id,
            "events": chunk,
            "count": len(chunk),
            "offset": offset,
            "limit": limit,
            "total_filtered": total_filtered,
            "total_cached": event_count,
            "has_more": (offset + len(chunk)) < total_filtered,
            "filters_applied": {
                "pattern": filter_pattern,
                "time_start": time_start,
                "time_end": time_end,
            },
        }

    async def delete_expired(self) -> int:
        """Delete all expired cache entries."""
        await self.initialize()

        now = int(time.time())

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                "DELETE FROM cached_results WHERE expires_at < ?",
                (now,)
            )
            await db.commit()
            return cursor.rowcount or 0

    async def _enforce_size_limit(self) -> None:
        """Enforce cache size limit by removing oldest entries."""
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Get current size
            async with db.execute(
                "SELECT COALESCE(SUM(data_size_bytes), 0) FROM cached_results"
            ) as cursor:
                row = await cursor.fetchone()
                current_size = row[0] if row else 0

            if current_size <= self.max_size_bytes:
                return

            # Need to free space - remove oldest entries
            target_size = int(self.max_size_bytes * 0.8)  # Free 20%

            async with db.execute("""
                SELECT cache_id, data_size_bytes
                FROM cached_results
                ORDER BY last_accessed ASC
            """) as cursor:
                rows = await cursor.fetchall()

            to_delete = []
            freed = 0

            for cache_id, size in rows:
                if current_size - freed <= target_size:
                    break
                to_delete.append(cache_id)
                freed += size

            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                await db.execute(
                    f"DELETE FROM cached_results WHERE cache_id IN ({placeholders})",
                    to_delete
                )
                await db.commit()
                logger.info(f"Evicted {len(to_delete)} cached results to enforce size limit")

    async def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        await self.initialize()

        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute("""
                SELECT
                    COUNT(*) as entry_count,
                    COALESCE(SUM(data_size_bytes), 0) as total_size,
                    COALESCE(SUM(event_count), 0) as total_events,
                    COALESCE(SUM(access_count), 0) as total_accesses
                FROM cached_results
            """) as cursor:
                row = await cursor.fetchone()

        return {
            "entry_count": row[0] if row else 0,
            "total_size_bytes": row[1] if row else 0,
            "total_size_mb": round((row[1] or 0) / (1024 * 1024), 2),
            "total_events": row[2] if row else 0,
            "total_accesses": row[3] if row else 0,
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
            "ttl_seconds": self.ttl_seconds,
        }
```

### 3.4 FetchCachedResultTool

**Location:** `src/logai/core/tools/fetch_cached_result.py`

**Purpose:** Agent tool for incremental retrieval of cached results.

```python
"""Tool for fetching chunks of cached large results."""

from typing import Any

from logai.core.context.result_cache import ResultCacheManager
from logai.core.tools.base import BaseTool, ToolExecutionError


class FetchCachedResultTool(BaseTool):
    """
    Tool to fetch chunks of previously cached large query results.

    When a CloudWatch query returns too many results for the context window,
    the results are cached and a summary is provided. This tool allows the
    agent to retrieve specific chunks of those cached results.
    """

    def __init__(self, result_cache: ResultCacheManager) -> None:
        """
        Initialize FetchCachedResultTool.

        Args:
            result_cache: Result cache manager instance
        """
        self.result_cache = result_cache

    @property
    def name(self) -> str:
        """Return tool name."""
        return "fetch_cached_result_chunk"

    @property
    def description(self) -> str:
        """Return tool description."""
        return (
            "Fetch a specific chunk of a previously cached large query result. "
            "Use this when you need to access specific log events from a result "
            "that was too large to fit in context. The cache_id is provided in "
            "the cached result summary. You can filter by text pattern or time range."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """Return parameter schema."""
        return {
            "type": "object",
            "properties": {
                "cache_id": {
                    "type": "string",
                    "description": "The cache ID from the cached result summary (e.g., 'result_abc123')",
                },
                "offset": {
                    "type": "integer",
                    "description": "Starting index for pagination (0-based, default: 0)",
                    "minimum": 0,
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of events to fetch (default: 100, max: 200)",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 100,
                },
                "filter_pattern": {
                    "type": "string",
                    "description": (
                        "Optional text pattern to filter events (case-insensitive). "
                        "Example: 'ERROR' to find only error messages."
                    ),
                },
                "time_start": {
                    "type": "integer",
                    "description": "Optional start timestamp (epoch milliseconds) to filter events",
                },
                "time_end": {
                    "type": "integer",
                    "description": "Optional end timestamp (epoch milliseconds) to filter events",
                },
            },
            "required": ["cache_id"],
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the fetch_cached_result_chunk tool.

        Args:
            **kwargs: Tool parameters

        Returns:
            Dictionary with events and metadata
        """
        cache_id = kwargs.get("cache_id")

        if not cache_id:
            raise ToolExecutionError(
                message="cache_id parameter is required",
                tool_name=self.name,
                details={"provided_params": list(kwargs.keys())},
            )

        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 100)
        filter_pattern = kwargs.get("filter_pattern")
        time_start = kwargs.get("time_start")
        time_end = kwargs.get("time_end")

        try:
            result = await self.result_cache.fetch_chunk(
                cache_id=cache_id,
                offset=offset,
                limit=limit,
                filter_pattern=filter_pattern,
                time_start=time_start,
                time_end=time_end,
            )

            return result

        except Exception as e:
            raise ToolExecutionError(
                message=f"Failed to fetch cached result: {str(e)}",
                tool_name=self.name,
                details={
                    "cache_id": cache_id,
                    "offset": offset,
                    "limit": limit,
                },
            ) from e
```

### 3.5 HistoryManager

**Location:** `src/logai/core/context/history_manager.py`

**Purpose:** Manage conversation history with sliding window pruning.

```python
"""Conversation history management with sliding window pruning."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PruneResult:
    """Result of a history pruning operation."""
    messages_pruned: int
    tokens_freed: int
    pruned_messages: list[dict[str, Any]]


class HistoryManager:
    """
    Manages conversation history with intelligent pruning.

    Pruning Strategy:
    - FIFO (oldest first) for user/assistant messages
    - Never prune system messages
    - Never prune tool results from current turn
    - Preserve N most recent messages
    - Optionally summarize pruned content (future)
    """

    # Configuration
    PRESERVE_RECENT_COUNT = 6  # Keep last N messages always

    def __init__(self, preserve_recent: int = PRESERVE_RECENT_COUNT):
        """
        Initialize history manager.

        Args:
            preserve_recent: Number of recent messages to always preserve
        """
        self.preserve_recent = preserve_recent

    def get_prunable_indices(
        self,
        messages: list[dict[str, Any]],
        message_tokens: list[int],
        target_tokens: int,
    ) -> list[int]:
        """
        Get indices of messages that can be pruned to free target tokens.

        Args:
            messages: List of message dictionaries
            message_tokens: Token count for each message (parallel list)
            target_tokens: Target tokens to free

        Returns:
            List of indices to prune (oldest first)
        """
        if len(messages) != len(message_tokens):
            logger.error("Message and token lists have different lengths")
            return []

        # Identify prunable messages
        prunable: list[tuple[int, int, dict]] = []  # (index, tokens, message)

        for i, (msg, tokens) in enumerate(zip(messages, message_tokens)):
            role = msg.get("role", "")

            # Skip system messages
            if role == "system":
                continue

            # Skip tool messages (needed for current context)
            if role == "tool":
                continue

            prunable.append((i, tokens, msg))

        # Preserve most recent messages
        if len(prunable) > self.preserve_recent:
            prunable = prunable[:-self.preserve_recent]
        else:
            # Nothing to prune while preserving recent
            return []

        # Select messages to prune (oldest first)
        to_prune: list[int] = []
        freed = 0

        for idx, tokens, _ in prunable:
            if freed >= target_tokens:
                break
            to_prune.append(idx)
            freed += tokens

        return to_prune

    def prune_history(
        self,
        history: list[dict[str, Any]],
        indices_to_prune: list[int],
    ) -> tuple[list[dict[str, Any]], PruneResult]:
        """
        Prune messages from history at specified indices.

        Args:
            history: Conversation history list
            indices_to_prune: Indices to remove

        Returns:
            Tuple of (new_history, prune_result)
        """
        if not indices_to_prune:
            return history, PruneResult(
                messages_pruned=0,
                tokens_freed=0,
                pruned_messages=[],
            )

        indices_set = set(indices_to_prune)

        pruned_messages = []
        new_history = []

        for i, msg in enumerate(history):
            if i in indices_set:
                pruned_messages.append(msg)
            else:
                new_history.append(msg)

        # Estimate tokens freed (rough estimate)
        tokens_freed = sum(
            len(msg.get("content", "")) // 4  # ~4 chars per token
            for msg in pruned_messages
        )

        result = PruneResult(
            messages_pruned=len(pruned_messages),
            tokens_freed=tokens_freed,
            pruned_messages=pruned_messages,
        )

        logger.info(
            f"Pruned {result.messages_pruned} messages, "
            f"freed ~{result.tokens_freed} tokens"
        )

        return new_history, result

    def should_summarize_pruned(
        self,
        pruned_messages: list[dict[str, Any]],
    ) -> bool:
        """
        Determine if pruned messages should be summarized.

        For v1, this always returns False (summarization is future work).

        Args:
            pruned_messages: Messages that were pruned

        Returns:
            True if summarization recommended
        """
        # Future: implement summarization heuristics
        # - Summarize if pruned > N messages
        # - Summarize if pruned contains important context
        return False

    def generate_summary(
        self,
        pruned_messages: list[dict[str, Any]],
    ) -> str:
        """
        Generate a summary of pruned messages.

        For v1, this is a placeholder that returns a simple description.
        Future versions will use LLM-based summarization.

        Args:
            pruned_messages: Messages to summarize

        Returns:
            Summary string
        """
        # Placeholder for v1
        user_count = sum(1 for m in pruned_messages if m.get("role") == "user")
        assistant_count = sum(1 for m in pruned_messages if m.get("role") == "assistant")

        return (
            f"[Earlier conversation context pruned: {user_count} user messages, "
            f"{assistant_count} assistant responses]"
        )
```

### 3.6 Configuration Extensions

**Location:** `src/logai/config/settings.py` (additions)

```python
# === Context Management Settings ===
# Add these fields to LogAISettings class

# Context Window Management
context_window_buffer: int = Field(
    default=10000,
    description="Safety buffer tokens to reserve (never use)",
    ge=1000,
    le=50000,
)

response_reserve_tokens: int = Field(
    default=8000,
    description="Tokens to reserve for LLM response",
    ge=1000,
    le=20000,
)

# Result Caching
enable_result_caching: bool = Field(
    default=True,
    description="Cache large results outside context window",
)

cache_result_threshold_tokens: int = Field(
    default=10000,
    description="Token threshold above which results are cached",
    ge=1000,
    le=50000,
)

result_cache_ttl_seconds: int = Field(
    default=3600,
    description="TTL for cached results (default: 1 hour)",
    ge=300,
    le=86400,
)

result_cache_max_size_mb: int = Field(
    default=100,
    description="Maximum size for result cache in MB",
    ge=10,
    le=1000,
)

# History Management
enable_history_pruning: bool = Field(
    default=True,
    description="Enable automatic history pruning when context fills",
)

history_preserve_recent: int = Field(
    default=6,
    description="Number of recent messages to always preserve",
    ge=2,
    le=20,
)

context_warning_threshold_pct: int = Field(
    default=80,
    description="Show warning when context utilization exceeds this percentage",
    ge=50,
    le=95,
)
```

---

## 4. Integration Points

### 4.1 Orchestrator Modifications

The orchestrator requires careful integration to avoid breaking existing functionality. Here's the detailed modification plan:

**File:** `src/logai/core/orchestrator.py`

#### 4.1.1 Initialization Changes

```python
# In LLMOrchestrator.__init__()

from logai.core.context.budget_tracker import ContextBudgetTracker
from logai.core.context.result_cache import ResultCacheManager
from logai.core.context.history_manager import HistoryManager

def __init__(
    self,
    llm_provider: BaseLLMProvider,
    tool_registry: ToolRegistry,
    settings: LogAISettings,
    cache_manager: CacheManager | None = None,
    log_group_manager: "LogGroupManager | None" = None,
):
    # ... existing init code ...

    # NEW: Initialize context management components
    self.budget_tracker = ContextBudgetTracker(
        settings=settings,
        model=settings.current_llm_model,
    )

    self.result_cache = ResultCacheManager(
        cache_dir=settings.cache_dir / "results",
        ttl_seconds=settings.result_cache_ttl_seconds,
        max_size_mb=settings.result_cache_max_size_mb,
    )

    self.history_manager = HistoryManager(
        preserve_recent=settings.history_preserve_recent,
    )

    # Notification callback for UI updates
    self._context_notification_callback: Callable[[str, str], None] | None = None
```

#### 4.1.2 Tool Result Processing (Critical Path)

```python
# Replace the tool result handling at lines 513-521 and 761-769

async def _process_tool_result(
    self,
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a tool result, caching if necessary.

    Returns the result (possibly modified to a summary) for context.
    """
    result_data = tool_result["result"]
    tool_call_id = tool_result["tool_call_id"]

    # Check if result should be cached
    should_cache, token_count = self.budget_tracker.should_cache_result(
        result_data,
        threshold=self.settings.cache_result_threshold_tokens,
    )

    if should_cache and self.settings.enable_result_caching:
        # Cache the result and get summary
        tool_name = tool_result.get("tool_name", "unknown")
        query_params = tool_result.get("query_params", {})

        summary = await self.result_cache.cache_result(
            tool_name=tool_name,
            query_params=query_params,
            result=result_data,
        )

        # Use summary instead of full result
        modified_result = summary.to_context_dict()

        # Track the summary tokens
        summary_tokens = TokenCounter.estimate_json_tokens(
            modified_result,
            self.settings.current_llm_model
        )
        self.budget_tracker.add_result_tokens(summary_tokens)

        # Notify UI
        event_count = result_data.get("count", len(result_data.get("events", [])))
        self._notify_context_event(
            "info",
            f"Large result cached ({event_count} events). Agent can fetch details as needed."
        )

        logger.info(
            f"Cached large result: {token_count} tokens -> {summary_tokens} token summary"
        )

        return {
            "tool_call_id": tool_call_id,
            "result": modified_result,
        }
    else:
        # Result fits in context, use as-is
        self.budget_tracker.add_result_tokens(token_count)
        return tool_result


# Modified tool result handling in _chat_complete() and _chat_stream()
for tool_result in tool_results:
    # NEW: Process through context manager
    processed_result = await self._process_tool_result(tool_result)

    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": processed_result["tool_call_id"],
        "content": json.dumps(processed_result["result"]),
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)
```

#### 4.1.3 History Pruning Integration

```python
# Add before each LLM call

async def _prepare_messages_for_llm(self) -> list[dict[str, Any]]:
    """
    Prepare messages for LLM call with context management.

    Handles:
    - System prompt tracking
    - History pruning if needed
    - Budget validation
    """
    # Start with system prompt
    system_prompt = self._get_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    self.budget_tracker.set_system_prompt(system_prompt)

    # Check if we need to prune history
    if self.settings.enable_history_pruning:
        usage = self.budget_tracker.get_usage()

        if usage.utilization_pct >= self.settings.context_warning_threshold_pct:
            # Calculate how much to free
            target_free = int(usage.total_tokens * 0.2)  # Free 20%

            # Get token counts for each message
            message_tokens = [
                TokenCounter.count_tokens(
                    m.get("content", ""),
                    self.settings.current_llm_model
                )
                for m in self.conversation_history
            ]

            # Get prunable indices
            to_prune = self.history_manager.get_prunable_indices(
                self.conversation_history,
                message_tokens,
                target_free,
            )

            if to_prune:
                # Prune the history
                self.conversation_history, prune_result = \
                    self.history_manager.prune_history(
                        self.conversation_history,
                        to_prune,
                    )

                # Reset and rebuild budget tracker
                self.budget_tracker.reset()
                self.budget_tracker.set_system_prompt(system_prompt)

                # Notify UI
                self._notify_context_event(
                    "info",
                    f"Pruned {prune_result.messages_pruned} old messages to maintain context."
                )

    # Add conversation history
    messages.extend(self.conversation_history)

    # Track all messages in budget
    for msg in self.conversation_history:
        self.budget_tracker.add_message(msg)

    return messages
```

#### 4.1.4 Pre-Call Validation

```python
# Add validation before LLM call

def _validate_context_before_call(self, messages: list[dict[str, Any]]) -> None:
    """
    Final validation before sending to LLM.

    Raises:
        OrchestratorError: If context would overflow
    """
    usage = self.budget_tracker.get_usage()

    # Log current state
    logger.debug(
        f"Context state before LLM call: {usage.utilization_pct:.1f}% "
        f"({usage.total_tokens}/{self.budget_tracker.allocation.usable_tokens} tokens)"
    )

    # Warn at threshold
    if usage.utilization_pct >= self.settings.context_warning_threshold_pct:
        self._notify_context_event(
            "warning",
            f"Context window {usage.utilization_pct:.0f}% full"
        )

    # Hard stop at 95%
    if usage.utilization_pct >= 95:
        logger.error(
            f"Context overflow prevented: {usage.utilization_pct:.1f}%"
        )
        raise OrchestratorError(
            "Context window nearly full. Please start a new conversation "
            "or the assistant won't be able to respond properly."
        )
```

### 4.2 Tool Registration

**File:** `src/logai/core/tools/__init__.py` or wherever tools are registered

```python
# Register the new fetch_cached_result_chunk tool

from logai.core.tools.fetch_cached_result import FetchCachedResultTool

def register_tools(
    datasource: CloudWatchDataSource,
    sanitizer: LogSanitizer,
    settings: LogAISettings,
    cache: CacheManager | None,
    result_cache: ResultCacheManager,  # NEW
) -> None:
    """Register all available tools."""

    # Existing tools
    ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache))
    ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache))
    ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache))

    # NEW: Cached result fetch tool
    ToolRegistry.register(FetchCachedResultTool(result_cache))
```

### 4.3 UI Integration

**File:** `src/logai/ui/screens/chat.py`

```python
# Add context status to status bar

class ChatScreen(Screen[None]):

    def __init__(self, ...):
        # ... existing init ...

        # Register for context notifications
        self.orchestrator.set_context_notification_callback(
            self._on_context_notification
        )

    def _on_context_notification(self, level: str, message: str) -> None:
        """Handle context management notifications."""
        if level == "warning":
            self.notify(message, severity="warning", timeout=5)
        elif level == "info":
            self.notify(message, severity="information", timeout=3)
        elif level == "error":
            self.notify(message, severity="error", timeout=10)

    async def _update_context_status(self) -> None:
        """Update status bar with context utilization."""
        usage = self.orchestrator.budget_tracker.get_usage()
        status_bar = self.query_one(StatusBar)

        # Update context display
        status_bar.update_context(usage.utilization_pct)


# StatusBar modifications
class StatusBar(Widget):

    def update_context(self, utilization_pct: float) -> None:
        """Update context utilization display."""
        if utilization_pct >= 90:
            color = "red"
            suffix = " (!)"
        elif utilization_pct >= 70:
            color = "yellow"
            suffix = ""
        else:
            color = "green"
            suffix = ""

        self.context_label = f"[{color}]Context: {utilization_pct:.0f}%{suffix}[/]"
        self.refresh()
```

---

## 5. Token Counting Strategy

### 5.1 Provider-Specific Approach

| Provider | Tokenizer | Accuracy | Performance |
|----------|-----------|----------|-------------|
| **Anthropic (Claude)** | tiktoken cl100k_base | ~98% | <1ms |
| **OpenAI (GPT-4)** | tiktoken cl100k_base | ~99% | <1ms |
| **GitHub Copilot** | tiktoken cl100k_base | ~98% | <1ms |
| **Ollama** | Character heuristic | ~85% | <0.1ms |

### 5.2 Ollama Handling

For Ollama models with unknown tokenizers, we use a conservative character-based heuristic:

```python
# Characters per token varies by model:
# - llama3.1: ~3.5 chars/token (English)
# - codellama: ~2.8 chars/token (code)
# - mistral: ~3.2 chars/token

# We use 3.5 as a conservative default
DEFAULT_CHARS_PER_TOKEN = 3.5

def estimate_ollama_tokens(text: str) -> int:
    return int(len(text) / DEFAULT_CHARS_PER_TOKEN) + 1
```

This ensures we never underestimate token counts for Ollama, preventing overflow.

### 5.3 Performance Optimization

1. **Lazy Loading**: tiktoken is loaded on first use, not at import time
2. **Encoding Cache**: Tokenizer encodings are cached per model
3. **Early Exit**: Empty strings return 0 immediately
4. **Batch Counting**: Messages are counted in a single pass

### 5.4 Accuracy vs Speed Tradeoffs

For real-time operations (<10ms requirement):
- Use tiktoken for supported models (accurate + fast)
- Use character heuristic for unsupported models (conservative + instant)

For background operations (can take longer):
- Could implement actual model-specific tokenizers
- Could use API-based token counting (future)

---

## 6. Budget Allocation Algorithm

### 6.1 Adaptive Allocation Strategy

The adaptive strategy dynamically adjusts allocations based on conversation state:

```python
def adaptive_allocation(
    context_window: int,
    conversation_length: int,
    pending_result_size: int,
) -> BudgetAllocation:
    """
    Calculate adaptive allocation based on conversation state.

    Heuristics:
    - Short conversation (<10 messages): Allow larger results
    - Long conversation (>30 messages): Prioritize history preservation
    - Large pending result: Reduce history allocation
    """

    # Fixed allocations
    safety_buffer = int(context_window * 0.05)  # 5%
    response_reserve = int(context_window * 0.04)  # 4%
    system_prompt = int(context_window * 0.05)  # 5%

    available = context_window - safety_buffer - response_reserve - system_prompt

    # Adaptive split based on conversation state
    if conversation_length < 10:
        # Short conversation: allow larger results
        history_pct = 0.40
    elif conversation_length > 30:
        # Long conversation: preserve history
        history_pct = 0.65
    else:
        # Default balanced
        history_pct = 0.55

    # Adjust for pending result
    if pending_result_size > available * 0.3:
        # Large result coming: reduce history
        history_pct = min(history_pct, 0.40)

    history = int(available * history_pct)
    results = available - history

    return BudgetAllocation(
        total_window=context_window,
        system_prompt=system_prompt,
        history=history,
        results=results,
        response_reserve=response_reserve,
        safety_buffer=safety_buffer,
    )
```

### 6.2 When to Prune History

History pruning is triggered when:

1. **Utilization > 80%**: Proactive pruning to prevent overflow
2. **Before Large Result**: If pending result + current > 90%
3. **After Failed Add**: If a message can't be added due to budget

### 6.3 When to Cache Results

Results are cached when:

1. **Token Count > Threshold**: Default 10,000 tokens
2. **Won't Fit in Budget**: Even small results cached if budget exhausted
3. **User Preference**: If result_focused strategy, cache threshold is higher

### 6.4 Decision Flow

```
New Tool Result Arrives
        │
        ▼
┌───────────────────┐
│ Count result      │
│ tokens            │
└───────────────────┘
        │
        ▼
┌───────────────────┐     YES    ┌──────────────────┐
│ tokens >          │───────────▶│ Cache result,    │
│ cache_threshold?  │            │ return summary   │
└───────────────────┘            └──────────────────┘
        │ NO
        ▼
┌───────────────────┐     NO     ┌──────────────────┐
│ fits in current   │───────────▶│ Can we prune     │
│ result budget?    │            │ history?         │
└───────────────────┘            └──────────────────┘
        │ YES                            │
        ▼                          YES   │   NO
┌───────────────────┐                    ▼    ▼
│ Add to context    │            ┌───────────────────┐
│ as-is             │            │ Prune history,    │
└───────────────────┘            │ then add result   │
                                 └───────────────────┘
                                         │
                            Still won't fit after prune?
                                         │
                                         ▼
                                 ┌───────────────────┐
                                 │ Cache result      │
                                 │ (forced)          │
                                 └───────────────────┘
```

---

## 7. Caching Strategy

### 7.1 Cache Threshold Decision

**Recommended: 10,000 tokens (~40KB JSON)**

Rationale:
- Small enough to cache frequently (most large queries exceed this)
- Large enough to not cache unnecessarily (small results stay in context)
- Leaves room for ~5-10 results before hitting budget

### 7.2 Summary Format

The cached result summary provides:

```json
{
  "cached": true,
  "cache_id": "result_a1b2c3d4e5f6",
  "summary": {
    "total_events": 1000,
    "time_range": {
      "start": 1707750000000,
      "end": 1707753600000,
      "span_ms": 3600000
    },
    "sample_events": [
      {"timestamp": 1707750000000, "message": "First event..."},
      {"timestamp": 1707751800000, "message": "Middle event..."},
      {"timestamp": 1707753600000, "message": "Last event..."}
    ],
    "event_statistics": {
      "ERROR": 150,
      "WARN": 300,
      "INFO": 550
    }
  },
  "original_query": {
    "tool": "fetch_logs",
    "parameters": {
      "log_group": "/aws/lambda/my-function",
      "start_time": "2h ago"
    }
  },
  "cache_info": {
    "cached_at": 1707754000,
    "expires_in_seconds": 3540
  },
  "instructions": "Use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve specific events..."
}
```

This summary is ~800-1200 tokens, giving the agent:
- Total count to understand scale
- Time range to understand temporal distribution
- Sample events to understand content
- Statistics to identify patterns
- Instructions for retrieval

### 7.3 TTL and Size Management

**TTL: 1 hour (default)**
- Long enough for typical investigation sessions
- Short enough to not accumulate stale data
- Configurable per deployment

**Size Limit: 100MB (default)**
- ~100-200 cached results depending on size
- LRU eviction when limit reached
- Automatic cleanup of expired entries

### 7.4 Cache Miss Handling

When the agent requests a chunk from an expired/missing cache entry:

```json
{
  "success": false,
  "error": "Cache entry 'result_abc123' has expired",
  "hint": "Re-run the original query to get fresh results."
}
```

The agent can then decide to re-execute the original query or inform the user.

---

## 8. History Management

### 8.1 Pruning Algorithm

```python
def select_messages_to_prune(
    messages: list[Message],
    target_tokens: int,
) -> list[int]:
    """
    Select messages to prune using FIFO with preservation rules.

    Rules:
    1. Never prune system messages
    2. Never prune tool messages (breaks context)
    3. Never prune last N messages (preserve recent)
    4. Prune oldest user/assistant messages first
    """

    # Filter to prunable messages
    prunable = [
        (i, m) for i, m in enumerate(messages)
        if m.role not in ("system", "tool")
    ]

    # Keep last PRESERVE_RECENT messages
    if len(prunable) > PRESERVE_RECENT:
        prunable = prunable[:-PRESERVE_RECENT]

    # Select oldest until target met
    indices = []
    freed = 0

    for i, msg in prunable:
        if freed >= target_tokens:
            break
        indices.append(i)
        freed += msg.tokens

    return indices
```

### 8.2 What to Preserve

| Message Type | Preserve? | Reason |
|--------------|-----------|--------|
| System prompt | Always | Required for agent behavior |
| System injections | Always | Retry prompts, context injections |
| Tool results | Always* | Breaks tool call chains if removed |
| Recent user messages | Always | Active context |
| Recent assistant | Always | Active context |
| Old user/assistant | Prunable | Can be recovered by asking |

*Tool results from very old turns could potentially be pruned, but this adds complexity. For v1, we keep all tool results.

### 8.3 Future: Summarization Approach

In future versions, instead of simply deleting pruned messages, we could:

1. **Summarize Before Prune**
   - Use LLM to generate a summary of pruned context
   - Insert summary as system message
   - Preserves important context at reduced token cost

2. **Implementation Sketch**
   ```python
   async def summarize_and_prune(
       messages: list[Message],
       llm: LLMProvider,
   ) -> tuple[list[Message], Message]:
       """
       Summarize messages before pruning.

       Returns new message list and summary message.
       """
       summary_prompt = f"""
       Summarize the following conversation context in 2-3 sentences,
       focusing on key topics discussed and any important conclusions:

       {format_messages(messages)}
       """

       summary = await llm.chat([{"role": "user", "content": summary_prompt}])

       summary_message = {
           "role": "system",
           "content": f"[Previous context summary: {summary.content}]"
       }

       return [], summary_message
   ```

This is deferred to v2 due to:
- Additional LLM calls (cost, latency)
- Complexity of summarization quality
- Edge cases with tool results

---

## 9. Error Handling

### 9.1 Error Hierarchy

```
ContextManagementError (base)
├── TokenCountingError
│   └── Fallback to character heuristic
├── CacheStorageError
│   └── Fallback to truncation
├── CacheRetrievalError
│   └── Return error message to agent
├── BudgetExceededError
│   └── Prune or cache, then retry
└── ContextOverflowError
    └── Hard stop, user notification
```

### 9.2 Fallback Strategies

**Token Counting Failure:**
```python
try:
    tokens = TokenCounter.count_tokens(text, model)
except Exception as e:
    logger.warning(f"Token counting failed: {e}")
    # Conservative fallback: 3 chars per token
    tokens = len(text) // 3 + 1
```

**Cache Storage Failure:**
```python
try:
    summary = await result_cache.cache_result(...)
except Exception as e:
    logger.error(f"Cache storage failed: {e}")
    # Fallback: truncate result to fit
    truncated = truncate_result(result, max_tokens=10000)
    return truncated
```

**Cache Retrieval Failure:**
```python
try:
    chunk = await result_cache.fetch_chunk(cache_id, ...)
except Exception as e:
    logger.error(f"Cache retrieval failed: {e}")
    return {
        "success": False,
        "error": "Failed to retrieve cached result",
        "hint": "Re-run the original query",
    }
```

### 9.3 Hard Limits

Despite all protections, if context somehow exceeds 95%:

```python
if usage.utilization_pct >= 95:
    raise OrchestratorError(
        "Context window critically full (95%). "
        "Please start a new conversation to continue."
    )
```

This prevents sending oversized requests to the LLM.

### 9.4 User-Facing Errors

All context management errors should be user-friendly:

| Internal Error | User Message |
|----------------|--------------|
| `TokenCountingError` | (Silent, handled internally) |
| `CacheStorageError` | "Note: Result was truncated due to size." |
| `BudgetExceededError` | "Some conversation history was trimmed." |
| `ContextOverflowError` | "Context full. Please start a new conversation." |

---

## 10. Performance Considerations

### 10.1 Latency Budgets

| Operation | Target | Max Acceptable |
|-----------|--------|----------------|
| Token counting (single text) | <1ms | 5ms |
| Token counting (all messages) | <10ms | 50ms |
| Cache storage | <50ms | 200ms |
| Cache retrieval | <100ms | 500ms |
| Budget calculation | <1ms | 5ms |
| History pruning decision | <5ms | 20ms |

### 10.2 Optimization Strategies

**Token Counting:**
- Cache tokenizer encodings (done in TokenCounter)
- Use fast paths for empty/small strings
- Consider caching token counts for immutable messages

**Cache Operations:**
- Use connection pooling for SQLite (aiosqlite handles this)
- Batch deletes for expired entries
- Index on cache_id, expires_at

**Memory Management:**
- Don't load full cached results into memory for chunk fetches
- Stream large JSON parsing if needed
- Limit sample event size in summaries

### 10.3 Benchmarking Approach

```python
# Benchmark suite for context management

async def benchmark_token_counting():
    """Benchmark token counting performance."""
    test_cases = [
        ("small", "Hello world"),
        ("medium", "x" * 10000),
        ("large", "x" * 100000),
        ("json", json.dumps({"events": [{"message": "test"}] * 1000})),
    ]

    for name, text in test_cases:
        start = time.perf_counter()
        for _ in range(100):
            TokenCounter.count_tokens(text, "claude-3-5-sonnet")
        elapsed = (time.perf_counter() - start) / 100
        print(f"{name}: {elapsed*1000:.2f}ms")

async def benchmark_cache_operations():
    """Benchmark cache storage and retrieval."""
    cache = ResultCacheManager(Path("/tmp/bench_cache"))

    # Generate test result
    result = {
        "events": [{"timestamp": i, "message": f"Log {i}"} for i in range(1000)]
    }

    # Benchmark storage
    start = time.perf_counter()
    for i in range(10):
        await cache.cache_result(f"tool_{i}", {"query": i}, result)
    storage_time = (time.perf_counter() - start) / 10

    # Benchmark retrieval
    start = time.perf_counter()
    for i in range(10):
        await cache.fetch_chunk(f"result_...", 0, 100)
    retrieval_time = (time.perf_counter() - start) / 10

    print(f"Storage: {storage_time*1000:.2f}ms")
    print(f"Retrieval: {retrieval_time*1000:.2f}ms")
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

**TokenCounter Tests:**
```python
# tests/unit/core/context/test_token_counter.py

class TestTokenCounter:
    def test_count_empty_string(self):
        assert TokenCounter.count_tokens("", "claude") == 0

    def test_count_simple_text(self):
        tokens = TokenCounter.count_tokens("Hello, world!", "claude")
        assert 3 <= tokens <= 5  # Approximately 4 tokens

    def test_count_large_text(self):
        text = "x" * 100000
        start = time.perf_counter()
        tokens = TokenCounter.count_tokens(text, "claude")
        elapsed = time.perf_counter() - start

        assert tokens > 0
        assert elapsed < 0.01  # Under 10ms

    def test_count_messages(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = TokenCounter.count_message_tokens(messages, "claude")
        assert tokens > 0

    def test_unknown_model_fallback(self):
        # Should use character heuristic
        tokens = TokenCounter.count_tokens("Hello", "unknown-model")
        assert tokens > 0

    def test_context_window_lookup(self):
        assert TokenCounter.get_context_window("claude-3-5-sonnet") == 200000
        assert TokenCounter.get_context_window("gpt-4-turbo") == 128000
        assert TokenCounter.get_context_window("unknown") == 8192
```

**BudgetTracker Tests:**
```python
# tests/unit/core/context/test_budget_tracker.py

class TestContextBudgetTracker:
    @pytest.fixture
    def tracker(self, settings):
        return ContextBudgetTracker(settings, "claude-3-5-sonnet")

    def test_initial_allocation(self, tracker):
        assert tracker.allocation.total_window == 200000
        assert tracker.allocation.safety_buffer > 0

    def test_add_message_tracks_tokens(self, tracker):
        msg = {"role": "user", "content": "Hello"}
        assert tracker.add_message(msg) is True

        usage = tracker.get_usage()
        assert usage.history_tokens > 0

    def test_budget_enforcement(self, tracker):
        # Fill up the budget
        large_content = "x" * 500000  # Way over budget
        msg = {"role": "user", "content": large_content}

        assert tracker.add_message(msg) is False

    def test_should_cache_large_result(self, tracker):
        result = {"events": [{"message": "x" * 100}] * 1000}

        should_cache, tokens = tracker.should_cache_result(result)
        assert should_cache is True
        assert tokens > 10000

    def test_prunable_messages(self, tracker):
        # Add several messages
        for i in range(20):
            tracker.add_message({"role": "user", "content": f"Message {i}"})
            tracker.add_message({"role": "assistant", "content": f"Response {i}"})

        # Should be able to prune older messages
        prunable = tracker.get_prunable_messages(1000)
        assert len(prunable) > 0
```

**ResultCacheManager Tests:**
```python
# tests/unit/core/context/test_result_cache.py

class TestResultCacheManager:
    @pytest.fixture
    async def cache(self, tmp_path):
        cache = ResultCacheManager(tmp_path)
        await cache.initialize()
        return cache

    async def test_cache_and_retrieve(self, cache):
        result = {"events": [{"message": f"Event {i}"} for i in range(100)]}

        summary = await cache.cache_result("fetch_logs", {"group": "test"}, result)

        assert summary.cache_id.startswith("result_")
        assert summary.total_events == 100

    async def test_fetch_chunk(self, cache):
        result = {"events": [{"message": f"Event {i}"} for i in range(100)]}
        summary = await cache.cache_result("fetch_logs", {}, result)

        chunk = await cache.fetch_chunk(summary.cache_id, offset=10, limit=20)

        assert chunk["success"] is True
        assert chunk["count"] == 20
        assert chunk["offset"] == 10

    async def test_fetch_with_filter(self, cache):
        result = {"events": [
            {"message": "ERROR: something bad"},
            {"message": "INFO: all good"},
            {"message": "ERROR: another error"},
        ]}
        summary = await cache.cache_result("fetch_logs", {}, result)

        chunk = await cache.fetch_chunk(
            summary.cache_id,
            filter_pattern="ERROR"
        )

        assert chunk["count"] == 2

    async def test_expired_cache(self, cache):
        # Create cache with very short TTL
        cache.ttl_seconds = 1

        result = {"events": [{"message": "test"}]}
        summary = await cache.cache_result("test", {}, result)

        # Wait for expiration
        await asyncio.sleep(2)

        chunk = await cache.fetch_chunk(summary.cache_id)
        assert chunk["success"] is False
        assert "expired" in chunk["error"]
```

### 11.2 Integration Tests

```python
# tests/integration/test_context_management_e2e.py

class TestContextManagementE2E:
    """End-to-end tests for context management."""

    @pytest.fixture
    async def orchestrator(self, settings, mock_llm):
        """Create orchestrator with context management."""
        return LLMOrchestrator(
            llm_provider=mock_llm,
            tool_registry=ToolRegistry(),
            settings=settings,
        )

    async def test_large_result_is_cached(self, orchestrator, mock_cloudwatch):
        """Test that large results are automatically cached."""
        # Configure mock to return large result
        mock_cloudwatch.return_value = {
            "events": [{"message": f"Event {i}"} for i in range(1000)]
        }

        # Execute query
        response = await orchestrator.chat("Find all errors")

        # Check that result was cached
        assert "cached" in response.content.lower() or \
               "fetch_cached_result" in str(orchestrator.conversation_history)

    async def test_history_pruning_on_overflow(self, orchestrator):
        """Test that history is pruned when approaching limit."""
        # Fill up context with messages
        for i in range(50):
            await orchestrator.chat(f"Message {i} " + "x" * 1000)

        # History should have been pruned
        assert len(orchestrator.conversation_history) < 100

    async def test_multiple_large_queries(self, orchestrator, mock_cloudwatch):
        """Test handling of multiple large queries in sequence."""
        mock_cloudwatch.return_value = {
            "events": [{"message": f"Event {i}"} for i in range(500)]
        }

        # Execute multiple large queries
        for _ in range(5):
            await orchestrator.chat("Find more logs")

        # Should not crash, context should be managed
        usage = orchestrator.budget_tracker.get_usage()
        assert usage.utilization_pct < 100
```

### 11.3 Performance Tests

```python
# tests/performance/test_context_performance.py

class TestContextPerformance:
    """Performance benchmarks for context management."""

    def test_token_counting_latency(self):
        """Token counting must be under 10ms."""
        text = "x" * 50000  # 50KB

        start = time.perf_counter()
        for _ in range(100):
            TokenCounter.count_tokens(text, "claude")
        avg_ms = (time.perf_counter() - start) / 100 * 1000

        assert avg_ms < 10, f"Token counting too slow: {avg_ms}ms"

    async def test_cache_storage_latency(self, cache):
        """Cache storage must be under 50ms."""
        result = {"events": [{"message": "x" * 100}] * 500}

        start = time.perf_counter()
        for i in range(10):
            await cache.cache_result(f"tool_{i}", {"i": i}, result)
        avg_ms = (time.perf_counter() - start) / 10 * 1000

        assert avg_ms < 50, f"Cache storage too slow: {avg_ms}ms"

    async def test_cache_retrieval_latency(self, cache):
        """Cache retrieval must be under 100ms."""
        result = {"events": [{"message": "x" * 100}] * 500}
        summary = await cache.cache_result("tool", {}, result)

        start = time.perf_counter()
        for _ in range(10):
            await cache.fetch_chunk(summary.cache_id, 0, 100)
        avg_ms = (time.perf_counter() - start) / 10 * 1000

        assert avg_ms < 100, f"Cache retrieval too slow: {avg_ms}ms"
```

---

## 12. Implementation Phases

### Phase 1: Foundation (Days 1-3)

**Goal:** Establish core infrastructure for token counting and budget tracking.

**Deliverables:**
- [ ] `TokenCounter` class with tiktoken integration
- [ ] `ContextBudgetTracker` class with allocation logic
- [ ] Settings additions for context management
- [ ] Unit tests for TokenCounter (100% coverage)
- [ ] Unit tests for BudgetTracker (100% coverage)

**Success Criteria:**
- Token counting accurate within ±5%
- Token counting under 10ms for all test cases
- Budget tracker correctly enforces limits

### Phase 2: Caching System (Days 4-5)

**Goal:** Implement result caching with summary generation.

**Deliverables:**
- [ ] `ResultCacheManager` class
- [ ] SQLite schema for cached_results table
- [ ] Summary generation logic
- [ ] `FetchCachedResultTool` class
- [ ] Tool registration
- [ ] Unit tests for cache manager (100% coverage)
- [ ] Unit tests for fetch tool (100% coverage)

**Success Criteria:**
- Large results cached in <50ms
- Chunk retrieval in <100ms
- Summaries provide useful context for agent

### Phase 3: Orchestrator Integration (Days 6-8)

**Goal:** Integrate context management into orchestrator workflow.

**Deliverables:**
- [ ] `_process_tool_result()` method
- [ ] `_prepare_messages_for_llm()` method
- [ ] `_validate_context_before_call()` method
- [ ] History pruning integration
- [ ] Notification callback system
- [ ] Integration tests (5+ scenarios)

**Success Criteria:**
- No breaking changes to existing functionality
- Large results automatically cached
- History pruned when needed
- Notifications sent to UI

### Phase 4: UI & Polish (Days 9-10)

**Goal:** Complete UI integration and optimize performance.

**Deliverables:**
- [ ] StatusBar context utilization display
- [ ] Toast notifications for context events
- [ ] Performance benchmarks
- [ ] Performance optimizations if needed
- [ ] End-to-end tests
- [ ] Documentation updates

**Success Criteria:**
- Status bar shows context percentage
- Users notified of cache/prune actions
- All latency targets met
- All tests passing

---

## 13. File Structure

### 13.1 New Files

```
src/logai/core/context/
├── __init__.py                 # Package exports
├── token_counter.py            # TokenCounter class
├── budget_tracker.py           # ContextBudgetTracker class
├── result_cache.py             # ResultCacheManager class
└── history_manager.py          # HistoryManager class

src/logai/core/tools/
└── fetch_cached_result.py      # FetchCachedResultTool class

tests/unit/core/context/
├── __init__.py
├── test_token_counter.py
├── test_budget_tracker.py
├── test_result_cache.py
└── test_history_manager.py

tests/integration/
└── test_context_management_e2e.py

tests/performance/
└── test_context_performance.py
```

### 13.2 Modified Files

| File | Changes |
|------|---------|
| `src/logai/config/settings.py` | Add context management settings (~20 lines) |
| `src/logai/core/orchestrator.py` | Add context management integration (~150 lines) |
| `src/logai/core/tools/__init__.py` | Register FetchCachedResultTool |
| `src/logai/ui/screens/chat.py` | Add context notification handling (~30 lines) |
| `src/logai/ui/widgets/status_bar.py` | Add context utilization display (~20 lines) |
| `pyproject.toml` | Add tiktoken dependency |

### 13.3 Dependencies

Add to `pyproject.toml`:

```toml
[project.dependencies]
tiktoken = ">=0.5.0"  # For token counting
```

---

## 14. Migration Strategy

### 14.1 Backward Compatibility

The context management system is **additive** and **opt-in by default**:

- All new settings have sensible defaults
- Existing behavior preserved when `enable_result_caching=False`
- No database migrations required (new table)
- No API changes to existing tools

### 14.2 Rollout Approach

**Stage 1: Internal Testing**
- Deploy to development environment
- Run integration test suite
- Monitor for regressions

**Stage 2: Beta Release**
- Enable for select users
- Gather feedback on notifications
- Monitor cache hit rates

**Stage 3: General Availability**
- Enable by default for all users
- Monitor performance metrics
- Adjust thresholds based on feedback

### 14.3 Feature Flags

If needed, implement via settings:

```python
# Disable all context management (emergency rollback)
LOGAI_ENABLE_CONTEXT_MANAGEMENT=false

# Disable specific features
LOGAI_ENABLE_RESULT_CACHING=false
LOGAI_ENABLE_HISTORY_PRUNING=false
```

### 14.4 Rollback Plan

If critical issues are discovered:

1. Set `LOGAI_ENABLE_CONTEXT_MANAGEMENT=false` in environment
2. Restart application
3. System reverts to previous behavior (unlimited context)
4. Investigate and fix issues
5. Re-enable gradually

---

## 15. Future Enhancements

### 15.1 History Summarization (v2)

Instead of simply deleting pruned messages, generate LLM summaries:

```python
async def summarize_pruned_messages(
    messages: list[dict],
    llm: LLMProvider,
) -> str:
    """Generate a summary of pruned conversation context."""
    # Use a smaller, faster model for summarization
    summary = await llm.chat([{
        "role": "user",
        "content": f"Summarize this conversation in 2 sentences:\n{format(messages)}"
    }])
    return summary.content
```

### 15.2 Predictive Token Counting (v2)

Predict result size before tool execution:

```python
async def predict_result_size(
    tool_name: str,
    params: dict,
) -> int:
    """Predict token count of tool result based on parameters."""
    if tool_name == "fetch_logs":
        # Estimate based on limit and typical event size
        limit = params.get("limit", 100)
        avg_event_tokens = 150  # Historical average
        return limit * avg_event_tokens
```

### 15.3 Multi-Level Caching (v2)

Implement memory + disk caching for better performance:

```python
class MultiLevelResultCache:
    """Two-level cache: memory (fast) + disk (persistent)."""

    def __init__(self):
        self.memory_cache = LRUCache(max_size=10)  # Last 10 results
        self.disk_cache = ResultCacheManager(...)

    async def get(self, cache_id: str) -> dict | None:
        # Check memory first
        if result := self.memory_cache.get(cache_id):
            return result

        # Fall back to disk
        if result := await self.disk_cache.fetch_chunk(cache_id, 0, -1):
            self.memory_cache.set(cache_id, result)
            return result

        return None
```

### 15.4 Context Compression (v3)

Compress context to fit more information:

```python
async def compress_context(
    messages: list[dict],
    llm: LLMProvider,
) -> list[dict]:
    """Compress messages to reduce token count while preserving meaning."""
    # Techniques:
    # - Remove redundant information
    # - Compress JSON structures
    # - Summarize verbose assistant responses
    pass
```

### 15.5 Smart Result Filtering (v2)

Let the agent specify what it needs before tool execution:

```python
# Agent can request filtered results
await fetch_logs(
    log_group="...",
    start_time="1h ago",
    # New: pre-filter options
    select_fields=["timestamp", "message"],  # Don't return all fields
    sample_rate=0.1,  # Return 10% sample
    max_message_length=200,  # Truncate long messages
)
```

---

## Appendix A: Answers to Questions from Requirements

### Q1: Should we use tiktoken or build our own token counter?

**Answer: Use tiktoken with fallback heuristics.**

Rationale:
- tiktoken is the industry standard, maintained by OpenAI
- Extremely fast (<1ms) and accurate
- Works well for Claude (cl100k_base approximation)
- Fallback to character heuristic for Ollama/unknown models

### Q2: How should we handle Ollama's diverse tokenizers?

**Answer: Use conservative character-based estimation.**

Rationale:
- Ollama supports many models with different tokenizers
- Implementing each tokenizer is impractical
- Character heuristic (chars/3.5) is conservative and safe
- Better to over-estimate than under-estimate

### Q3: Should budget tracker be stateful or stateless?

**Answer: Stateful with validation on access.**

Rationale:
- Stateful allows O(1) budget checks
- Validation on access handles mutations
- Memory overhead is minimal (just token counts)
- Simpler API for orchestrator integration

### Q4: Should we extend SQLiteStore or create separate cache?

**Answer: Create separate database file, same pattern.**

Rationale:
- Separation of concerns (query cache vs result cache)
- Different TTL requirements
- Independent cleanup cycles
- Reuse SQLite patterns from existing code

### Q5: How detailed should result summaries be?

**Answer: Metadata + 5 sample events + statistics.**

Rationale:
- Agent needs enough info to decide what to fetch
- Sample events show data format and content
- Statistics (ERROR/WARN/INFO counts) highlight patterns
- ~1000 tokens is a good summary size

### Q6: Should we support multiple allocation strategies in v1?

**Answer: Adaptive only in v1.**

Rationale:
- Adaptive handles 95% of use cases
- Reduces testing complexity
- Users rarely need fine-grained control
- Can add more strategies in v2 based on feedback

---

## Appendix B: Token Count Examples

| Content | Approx Tokens | Notes |
|---------|---------------|-------|
| Empty string | 0 | |
| "Hello, world!" | 4 | Simple text |
| 1 log event (avg) | 100-200 | Depends on message length |
| 100 log events | 10,000-20,000 | Typical small query |
| 1,000 log events | 100,000-200,000 | Large query, needs caching |
| System prompt | 2,000-5,000 | Depends on log group context |
| User message (avg) | 20-50 | Short queries |
| Assistant response (avg) | 100-500 | Varies by task |

---

## Appendix C: Configuration Reference

```python
# All context management settings with defaults

# Context Window Management
context_window_buffer: int = 10000        # Safety buffer (never use)
response_reserve_tokens: int = 8000       # Reserve for LLM response

# Result Caching
enable_result_caching: bool = True        # Enable/disable caching
cache_result_threshold_tokens: int = 10000  # Cache if exceeds
result_cache_ttl_seconds: int = 3600      # 1 hour TTL
result_cache_max_size_mb: int = 100       # Max cache size

# History Management
enable_history_pruning: bool = True       # Enable/disable pruning
history_preserve_recent: int = 6          # Always keep N recent
context_warning_threshold_pct: int = 80   # Warn at this %
```

---

**End of Architecture Document**

---

**Document History:**
- v1.0 (2026-02-12): Initial architecture by Saanvi

**Review Status:**
- [ ] TPM Review (George)
- [ ] Implementation Review (Jackie)
- [ ] Security Review
- [ ] Performance Review
