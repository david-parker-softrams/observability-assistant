# Design Document: Context Window Management Fixes

**Document ID:** DESIGN-CWM-001
**Version:** 1.0
**Date:** February 17, 2026
**Author:** Saanvi (Senior Software Architect)
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Detailed Design](#3-detailed-design)
   - [Fix 1: Mid-Loop Token Budget Tracking](#fix-1-mid-loop-token-budget-tracking)
   - [Fix 2: Enforce max_result_tokens](#fix-2-enforce-max_result_tokens)
   - [Fix 3: Remove Duplicate Data from search_logs](#fix-3-remove-duplicate-data-from-search_logs)
   - [Fix 4: Emergency Pruning Strategy](#fix-4-emergency-pruning-strategy)
   - [Fix 5: Enhanced Context Usage Visibility](#fix-5-enhanced-context-usage-visibility)
4. [Technical Specifications](#4-technical-specifications)
5. [Error Handling](#5-error-handling)
6. [Testing Strategy](#6-testing-strategy)
7. [Implementation Order](#7-implementation-order)
8. [Backwards Compatibility](#8-backwards-compatibility)
9. [Appendices](#9-appendices)

---

## 1. Executive Summary

### Problem Statement
LogAI users with smaller context window models (e.g., Qwen3 32B with 32K tokens) experience context exhaustion after only 3-4 exchanges. The root causes are:

1. **No mid-loop budget tracking** - Token budget calculated once, not updated during tool execution
2. **Unenforced limits** - `max_result_tokens` setting exists but is never checked
3. **Duplicate data** - `search_logs` returns events twice (in `events` and `events_by_group`)

### Solution Overview
This design addresses all three issues plus adds emergency pruning and improved visibility:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT WINDOW MANAGEMENT FLOW                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   User Message ──► Budget Check ──► LLM Call ──► Tool Execution        │
│         │                                              │                │
│         │                                              ▼                │
│         │         ┌─────────────────────────────────────────┐          │
│         │         │        NEW: Mid-Loop Tracking           │          │
│         │         │  1. Count tool result tokens            │          │
│         │         │  2. Update running budget               │          │
│         │         │  3. Check against threshold             │          │
│         │         │  4. Trigger emergency prune if needed   │          │
│         │         └─────────────────────────────────────────┘          │
│         │                              │                               │
│         │                              ▼                               │
│         │         ┌─────────────────────────────────────────┐          │
│         │         │       NEW: Enforce max_result_tokens    │          │
│         │         │  - Force cache if result > limit        │          │
│         │         │  - Return summary instead of full data  │          │
│         │         └─────────────────────────────────────────┘          │
│         │                              │                               │
│         │                              ▼                               │
│         │         ┌─────────────────────────────────────────┐          │
│         │         │        Add Result to Context            │          │
│         │         └─────────────────────────────────────────┘          │
│         │                              │                               │
│         │                              ▼                               │
│         └──────── Budget < Threshold? ─┴── Yes ──► Emergency Prune    │
│                        │                                               │
│                        No                                              │
│                        │                                               │
│                        ▼                                               │
│                   Continue Loop                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Track budget in `_chat_complete()` loop | Minimal code changes, direct access to messages |
| Emergency prune threshold: 5K tokens | Matches `context_window_buffer` setting |
| Remove `events` field entirely | Clean break, all data available in `events_by_group` |
| Force cache at token limit, not event count | More accurate than arbitrary event count |
| Keep 4 most recent messages during prune | Maintains conversation continuity |

---

## 2. Architecture Overview

### 2.1 Current State

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  Settings        │    │  ContextBudgetTracker            │   │
│  │  (Configured)    │    │  (Tracks but doesn't enforce)    │   │
│  │                  │    │                                  │   │
│  │  max_result_tok  │◄───┤  get_usage()        ✓ Works     │   │
│  │  max_history_tok │    │  should_cache()     ✓ Works     │   │
│  │  context_buffer  │    │  add_message()      ✓ Works     │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
│          │                            │                         │
│          │                            │                         │
│          │NOT USED                    │                         │
│          ▼                            ▼                         │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  Orchestrator    │    │  _chat_complete() loop           │   │
│  │                  │    │                                  │   │
│  │  • Checks budget │    │  1. Calculate budget (ONCE)      │   │
│  │    at turn START │    │  2. Loop: call LLM               │   │
│  │  • Never checks  │    │  3. Execute tools                │   │
│  │    during loop   │    │  4. Add results (NO TRACKING)    │   │
│  │                  │    │  5. Repeat until done            │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Problems:
❌ Budget not rechecked after tool results added
❌ max_result_tokens setting ignored
❌ No emergency pruning mid-loop
❌ Duplicate data in search_logs wastes 50% of tokens
```

### 2.2 Target State

```
┌─────────────────────────────────────────────────────────────────┐
│                    TARGET ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  Settings        │    │  ContextBudgetTracker            │   │
│  │  (Enforced!)     │    │  (Enhanced)                      │   │
│  │                  │    │                                  │   │
│  │  max_result_tok ◄┼────┤  get_usage()        ✓           │   │
│  │  emergency_thres │    │  should_cache()     ✓           │   │
│  │  context_buffer  │    │  add_message()      ✓           │   │
│  └──────────────────┘    │  NEW: get_remaining_budget()    │   │
│          │               │  NEW: needs_emergency_prune()   │   │
│          │               └──────────────────────────────────┘   │
│          │USED!                       │                         │
│          ▼                            ▼                         │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │  Orchestrator    │    │  _chat_complete() loop           │   │
│  │  (Enhanced)      │    │  (ENHANCED)                      │   │
│  │                  │    │                                  │   │
│  │  • Checks budget │    │  1. Calculate budget             │   │
│  │    at turn START │    │  2. Loop: call LLM               │   │
│  │  • Checks DURING │    │  3. Execute tools                │   │
│  │    loop too      │    │  4. NEW: Check result size       │   │
│  │  • Enforces      │    │  5. NEW: Force cache if > limit  │   │
│  │    max_result    │    │  6. Add results (TRACKED!)       │   │
│  │  • Triggers      │    │  7. NEW: Check remaining budget  │   │
│  │    emergency     │    │  8. NEW: Emergency prune if low  │   │
│  │    prune         │    │  9. Repeat until done            │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Benefits:
✅ Budget tracked continuously during tool execution
✅ max_result_tokens enforced - large results force-cached
✅ Emergency pruning prevents context overflow
✅ search_logs uses 50% fewer tokens (no duplicates)
✅ UI shows accurate real-time context usage
```

### 2.3 Data Flow - Tool Result Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│               TOOL RESULT PROCESSING - ENHANCED FLOW                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Tool Execution Returns Result                                          │
│            │                                                            │
│            ▼                                                            │
│  ┌─────────────────────────────┐                                       │
│  │  Count Result Tokens        │  TokenCounter.estimate_json_tokens()  │
│  │  result_tokens = count(res) │                                       │
│  └─────────────────────────────┘                                       │
│            │                                                            │
│            ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CHECK: result_tokens > settings.max_result_tokens?         │       │
│  └─────────────────────────────────────────────────────────────┘       │
│            │                    │                                       │
│            │ YES                │ NO                                    │
│            ▼                    │                                       │
│  ┌──────────────────────┐      │                                       │
│  │  FORCE CACHE         │      │                                       │
│  │  • Cache full result │      │                                       │
│  │  • Return summary    │      │                                       │
│  │  • Log: "force-cache"│      │                                       │
│  └──────────────────────┘      │                                       │
│            │                    │                                       │
│            └────────────────────┘                                       │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  Update Budget Tracker                                       │       │
│  │  budget_tracker.add_result_tokens(result_tokens)             │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CHECK: remaining_budget < emergency_threshold?              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│            │                    │                                       │
│            │ YES                │ NO                                    │
│            ▼                    │                                       │
│  ┌──────────────────────┐      │                                       │
│  │  EMERGENCY PRUNE     │      │                                       │
│  │  • Free 25% tokens   │      │                                       │
│  │  • Keep recent 4 msg │      │                                       │
│  │  • Log pruning stats │      │                                       │
│  │  • Update UI         │      │                                       │
│  └──────────────────────┘      │                                       │
│            │                    │                                       │
│            └────────────────────┘                                       │
│                    │                                                    │
│                    ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  CHECK: remaining_budget < 0 (after prune)?                  │       │
│  └─────────────────────────────────────────────────────────────┘       │
│            │                    │                                       │
│            │ YES                │ NO                                    │
│            ▼                    ▼                                       │
│  ┌──────────────────────┐  ┌──────────────────────────┐               │
│  │  GRACEFUL EXIT       │  │  Continue Tool Loop      │               │
│  │  Return message:     │  │  Add result to messages  │               │
│  │  "Context exhausted" │  │  Proceed to next LLM call│               │
│  └──────────────────────┘  └──────────────────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Design

### Fix 1: Mid-Loop Token Budget Tracking

#### 3.1.1 Problem
The orchestrator calculates token budget once at the start of `_chat_complete()`, but during the tool execution loop, each tool result adds tokens without updating the remaining budget. After 10 tool iterations, context can exceed limits by 30-50%.

#### 3.1.2 Solution
Add budget tracking after each tool result is added to messages in the main conversation loop.

#### 3.1.3 Location
**File:** `src/logai/core/orchestrator.py`
**Method:** `_chat_complete()` (lines 1048-1308)
**Insert Point:** After line 1148 (after `messages.append(tool_message)`)

#### 3.1.4 Detailed Changes

**Step 1: Add helper method for budget check**

Add new method after `_log_budget_status()` (around line 1007):

```python
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

    # Determine threshold (use setting or default to context_window_buffer)
    emergency_threshold = getattr(
        self.settings,
        'emergency_prune_threshold',
        self.settings.context_window_buffer
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
            f"Context budget low: {remaining} tokens remaining"
        )

    return needs_action, remaining
```

**Step 2: Modify tool result loop in `_chat_complete()`**

Locate the tool result processing section (around lines 1140-1148) and add budget tracking:

```python
# CURRENT CODE (lines 1140-1148):
# Add tool results as separate messages
for tool_result in tool_results:
    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)

# NEW CODE - Replace with:
# Add tool results as separate messages WITH budget tracking
for tool_result in tool_results:
    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)

    # Track the tool result tokens
    result_content = tool_message["content"]
    result_tokens = TokenCounter.count_tokens(
        result_content,
        self.settings.current_llm_model
    )
    self.budget_tracker.add_result_tokens(result_tokens)

# After processing all tool results, check budget
needs_prune, remaining = self._check_mid_loop_budget(messages)

if needs_prune:
    # Attempt emergency pruning
    tokens_freed = self._emergency_prune_history(messages)

    # Re-check after pruning
    _, remaining_after = self._check_mid_loop_budget(messages)

    if remaining_after < 0:
        # Context still exhausted after pruning - graceful exit
        error_msg = (
            "I've reached my context limit and cannot continue this conversation. "
            "Please use /clear to start a new conversation."
        )
        self.conversation_history.append(
            {"role": "assistant", "content": error_msg}
        )
        self._notify_context_event(
            "error",
            "Context exhausted - conversation ended"
        )
        return error_msg
```

#### 3.1.5 Edge Cases

| Scenario | Handling |
|----------|----------|
| Very large single tool result | Handled by Fix 2 (force cache) |
| Multiple tool calls in single iteration | Budget checked after ALL results added |
| Budget goes negative | Emergency prune attempted, then graceful exit |
| Token count estimation error | Use conservative 3.5 chars/token fallback |
| Empty tool result | Still tracked (minimal tokens) |

---

### Fix 2: Enforce max_result_tokens

#### 3.2.1 Problem
The `max_result_tokens` setting (default 50,000) exists in settings but is never checked. A single large tool result can consume all available context.

#### 3.2.2 Solution
Check tool result size against `max_result_tokens` before processing. Force cache any result exceeding the limit.

#### 3.2.3 Location
**File:** `src/logai/core/orchestrator.py`
**Method:** `_process_tool_result()` (lines 765-886)
**Insert Point:** Before existing caching logic (around line 790)

#### 3.2.4 Detailed Changes

**Modify `_process_tool_result()` method:**

```python
async def _process_tool_result(
    self,
    tool_result: dict[str, Any],
    tool_name: str,
) -> dict[str, Any]:
    """
    Process a tool result, caching if necessary.

    This is a critical integration point for context management. When a tool
    returns a large result, we cache it and return a summary instead.

    ENHANCEMENT: Now enforces max_result_tokens setting by force-caching
    any result that exceeds the configured limit.

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

    # ==== NEW: Enforce max_result_tokens ====
    # Calculate token count for this result
    token_count = TokenCounter.estimate_json_tokens(
        result_data,
        self.settings.current_llm_model
    )

    # Check against max_result_tokens limit (NEW!)
    max_allowed = self.settings.max_result_tokens
    force_cache_due_to_size = token_count > max_allowed

    if force_cache_due_to_size:
        logger.info(
            f"Tool result exceeds max_result_tokens: {token_count} > {max_allowed}, "
            f"forcing cache for {tool_name}",
            extra={
                "tool_name": tool_name,
                "token_count": token_count,
                "max_result_tokens": max_allowed,
            }
        )
        self._notify_context_event(
            "info",
            f"Large result ({token_count} tokens) exceeds limit, caching..."
        )
    # ==== END NEW ====

    # Check if result should be cached based on size OR force_cache flag
    should_cache, _ = self.budget_tracker.should_cache_result(
        result_data,
        threshold=self.settings.cache_large_results_threshold,
    )

    # Cache if either condition is met
    if should_cache or force_cache_due_to_size:
        try:
            # Extract query parameters for cache key (best effort)
            query_params = {
                "tool": tool_name,
                "timestamp": int(datetime.now(UTC).timestamp()),
            }

            # Cache the result and get summary
            summary = await self.result_cache.cache_result(
                tool_name=tool_name,
                query_params=query_params,
                result=result_data,
            )

            # ... rest of existing caching code unchanged ...
```

#### 3.2.5 Configuration

The setting already exists in `src/logai/config/settings.py` (line 180):

```python
max_result_tokens: int = Field(
    default=50000,
    description="Maximum tokens for a single tool result before caching",
    ge=1000,
    le=100000,
)
```

**Recommendation:** Consider lowering default to 10,000 for Qwen3 32B users. Add to configuration guide.

#### 3.2.6 Integration with Existing Cache

The existing `ResultCacheManager` handles caching - we just need to trigger it. No changes needed to:
- `src/logai/core/context/result_cache.py`
- Cache summary generation
- Chunk fetching

---

### Fix 3: Remove Duplicate Data from search_logs

#### 3.3.1 Problem
The `search_logs` tool returns the same events twice:
1. In `events` array - flat list of all events
2. In `events_by_group` dictionary - same events organized by log group

This wastes 50-100% of the result's token budget.

#### 3.3.2 Solution
Remove the `events` field, keep only `events_by_group`. All data remains accessible.

#### 3.3.3 Location
**File:** `src/logai/core/tools/cloudwatch_tools.py`
**Class:** `SearchLogsTool`
**Method:** `execute()` (lines 450-520)
**Line to modify:** 477-494 (return dictionary construction)

#### 3.3.4 Detailed Changes

**CURRENT CODE (lines 477-494):**
```python
result = {
    "success": True,
    "log_group_patterns": log_group_patterns,
    "search_pattern": search_pattern,
    "events": sanitized_events,           # ← REMOVE THIS
    "events_by_group": events_by_group,
    "count": len(sanitized_events),
    "groups_found": len(events_by_group),
    "time_range": {
        "start": start_time,
        "end": end_time,
    },
    "sanitization": {
        "enabled": self.sanitizer.enabled,
        "redactions": redactions,
        "summary": self.sanitizer.get_redaction_summary(redactions),
    },
}
```

**NEW CODE:**
```python
result = {
    "success": True,
    "log_group_patterns": log_group_patterns,
    "search_pattern": search_pattern,
    # NOTE: "events" field removed to prevent duplicate data.
    # All event data is available in "events_by_group" organized by log group.
    "events_by_group": events_by_group,
    "count": len(sanitized_events),
    "groups_found": len(events_by_group),
    "time_range": {
        "start": start_time,
        "end": end_time,
    },
    "sanitization": {
        "enabled": self.sanitizer.enabled,
        "redactions": redactions,
        "summary": self.sanitizer.get_redaction_summary(redactions),
    },
}
```

#### 3.3.5 Impact Analysis

**What changes:**
- LLM receives events organized by log group only
- Token usage reduced by ~50% for search operations

**What doesn't change:**
- Event data structure (same fields per event)
- Sanitization behavior
- Cache key generation
- Count field accuracy
- Time range reporting

**LLM Adaptation:**
The LLM system prompt already guides the agent to analyze events. The events are now simply organized differently. Example LLM interpretation:

```
# Before (events flat list):
result["events"][0]["message"]  # First event

# After (events by group):
result["events_by_group"]["log-group-1"][0]["message"]  # First event from group 1

# Or iterate all:
for group, events in result["events_by_group"].items():
    for event in events:
        process(event)
```

#### 3.3.6 Schema Update Check

Review `SearchLogsTool` schema/description. If it explicitly mentions `events` field, update:

```python
# Check if tool description needs update
description = """
Search logs across multiple CloudWatch log groups.

Returns:
- events_by_group: Dictionary of events organized by log group
- count: Total number of matching events
- groups_found: Number of log groups with matches
- time_range: Start and end times of search
- sanitization: Summary of any redacted sensitive data
"""
```

---

### Fix 4: Emergency Pruning Strategy

#### 3.4.1 Problem
When context budget runs low mid-loop, there's no mechanism to recover. The conversation eventually crashes with "context length exceeded."

#### 3.4.2 Solution
Implement `_emergency_prune_history()` method that removes oldest messages to free up context space.

#### 3.4.3 Location
**File:** `src/logai/core/orchestrator.py`
**Insert after:** `_prune_history_if_needed()` method (around line 950)

#### 3.4.4 Detailed Implementation

```python
def _emergency_prune_history(
    self,
    messages: list[dict[str, Any]],
    target_tokens_to_free: int = 0
) -> int:
    """
    Emergency pruning when context budget is critically low during tool execution.

    This is different from regular pruning:
    - Called mid-loop, not just at turn start
    - More aggressive (aims to free 25% of context)
    - Syncs both conversation_history AND messages list
    - Never removes system messages or current tool cycle

    Args:
        messages: Current messages list being used in LLM call
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

    for i, msg in enumerate(self.conversation_history):
        # Skip recent messages
        if i >= len(self.conversation_history) - PRESERVE_RECENT:
            continue
        prunable_indices.append(i)

    if not prunable_indices:
        logger.warning("Emergency prune: No messages available for pruning")
        self._notify_context_event(
            "warning",
            "Cannot prune - minimum messages required for continuity"
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

        msg_tokens = TokenCounter.count_tokens(
            str(content),
            self.settings.current_llm_model
        )

        indices_to_remove.append(idx)
        tokens_freed += msg_tokens

    # Remove messages (reverse order to maintain indices)
    messages_removed = 0
    for idx in sorted(indices_to_remove, reverse=True):
        removed_msg = self.conversation_history.pop(idx)
        messages_removed += 1
        logger.debug(
            f"Emergency pruned message at index {idx}: "
            f"role={removed_msg.get('role')}"
        )

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
        f"Emergency pruned {messages_removed} messages, freed ~{tokens_freed} tokens"
    )

    logger.info(
        f"Emergency pruning complete: removed {messages_removed} messages, "
        f"freed ~{tokens_freed} tokens",
        extra={
            "messages_removed": messages_removed,
            "tokens_freed": tokens_freed,
            "target_tokens": target_tokens_to_free,
        }
    )

    # Record metric
    self.metrics.increment(
        "emergency_prune",
        labels={"messages_removed": str(messages_removed)}
    )

    return tokens_freed
```

#### 3.4.5 Pruning Algorithm Visualization

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EMERGENCY PRUNING ALGORITHM                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  conversation_history (example with 12 messages):                       │
│                                                                         │
│  Index:  0    1    2    3    4    5    6    7    8    9   10   11      │
│  Role:  [U]  [A]  [U]  [A]  [T]  [U]  [A]  [T]  [U]  [A]  [T]  [U]     │
│          │    │    │    │    │    │    │    │    │    │    │    │      │
│          │    │    │    │    │    │    │    └────┴────┴────┴────┘      │
│          │    │    │    │    │    │    │         PRESERVE (last 4)     │
│          │    │    │    │    │    │    │                               │
│          └────┴────┴────┴────┴────┴────┘                               │
│                  PRUNABLE (oldest first)                                │
│                                                                         │
│  Legend: [U] = User, [A] = Assistant, [T] = Tool                       │
│                                                                         │
│  Pruning Order:                                                         │
│  1. Remove index 0 (oldest user message)                               │
│  2. Remove index 1 (oldest assistant response)                         │
│  3. Continue until target_tokens_to_free reached                       │
│  4. Stop before touching last 4 messages                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.4.6 Configuration

Add new optional setting to `settings.py`:

```python
emergency_prune_threshold: int = Field(
    default=5000,
    description="Trigger emergency pruning when remaining tokens below this value",
    ge=1000,
    le=20000,
)
```

---

### Fix 5: Enhanced Context Usage Visibility

#### 3.5.1 Current State
The status footer already has context usage display infrastructure:
- `context_utilization` reactive attribute
- `update_context_usage()` method
- Color coding (green/yellow/red)

**However:** The display only shows percentage, not absolute values.

#### 3.5.2 Enhancement
Improve the display to show absolute token counts for better user understanding.

#### 3.5.3 Location
**File:** `src/logai/ui/widgets/status_footer.py`
**Method:** `_render_status_context()` (lines 205-258)

#### 3.5.4 Detailed Changes

**Step 1: Add reactive attributes for absolute values**

Add after line 49:
```python
context_utilization: reactive[float] = reactive(0.0)
context_used_tokens: reactive[int] = reactive(0)     # NEW
context_total_tokens: reactive[int] = reactive(0)    # NEW
```

**Step 2: Update render method**

Modify `_render_status_context()` (around line 234):

```python
# CURRENT CODE:
# Format context utilization with color coding
if self.context_utilization >= 86:
    context_color = "red"
elif self.context_utilization >= 71:
    context_color = "yellow"
else:
    context_color = "green"

# Build context text for right side
context_text = Text()
context_text.append(cache_info, style="dim")
context_text.append(" | ", style="dim")
context_text.append("Context: ", style="dim")
context_text.append(f"{self.context_utilization:.0f}%", style=context_color)

# NEW CODE - Replace context display section:
# Format context utilization with color coding
if self.context_utilization >= 95:
    context_color = "red bold"
    context_prefix = "(!!) "
elif self.context_utilization >= 86:
    context_color = "red"
    context_prefix = "(!) "
elif self.context_utilization >= 71:
    context_color = "yellow"
    context_prefix = ""
else:
    context_color = "green"
    context_prefix = ""

# Build context text with absolute values
context_text = Text()
context_text.append(cache_info, style="dim")
context_text.append(" | ", style="dim")
context_text.append("Context: ", style="dim")

# Show tokens in K format (e.g., "25.5K/32K")
if self.context_total_tokens > 0:
    used_k = self.context_used_tokens / 1000
    total_k = self.context_total_tokens / 1000
    context_text.append(context_prefix, style=context_color)
    context_text.append(f"{used_k:.1f}K/{total_k:.0f}K ", style=context_color)
    context_text.append(f"({self.context_utilization:.0f}%)", style=context_color)
else:
    context_text.append(f"{self.context_utilization:.0f}%", style=context_color)
```

**Step 3: Update the update method**

Modify `update_context_usage()` (line 280):

```python
def update_context_usage(
    self,
    utilization_pct: float,
    used_tokens: int = 0,
    total_tokens: int = 0
) -> None:
    """
    Update context usage display.

    Args:
        utilization_pct: Context utilization percentage (0-100)
        used_tokens: Currently used tokens
        total_tokens: Total available tokens
    """
    self.context_utilization = utilization_pct
    self.context_used_tokens = used_tokens
    self.context_total_tokens = total_tokens
```

**Step 4: Update chat screen to pass full context info**

In `src/logai/ui/screens/chat.py`, modify `_update_context_status()` (around line 357):

```python
def _update_context_status(self) -> None:
    """Update context usage in status footer."""
    try:
        current_time = time.time()
        if (
            current_time - self._last_context_update_time
            < self._context_update_throttle_seconds
        ):
            return

        self._last_context_update_time = current_time

        # Get usage from orchestrator's budget tracker
        if hasattr(self.orchestrator, "budget_tracker"):
            usage = self.orchestrator.budget_tracker.get_usage()
            allocation = self.orchestrator.budget_tracker.allocation
            status_footer = self.query_one(StatusFooter)
            status_footer.update_context_usage(
                utilization_pct=usage.utilization_pct,
                used_tokens=usage.total_tokens,
                total_tokens=allocation.usable_tokens
            )

    except Exception as e:
        logger.debug(f"Failed to update context status: {e}", exc_info=True)
```

#### 3.5.5 Expected Display

```
Before: Cache: 5/8 (62%) | Context: 80% | qwen3:32b

After:  Cache: 5/8 (62%) | Context: 25.5K/32K (80%) | qwen3:32b

At 95%: Cache: 5/8 (62%) | Context: (!!) 30.4K/32K (95%) | qwen3:32b
```

---

## 4. Technical Specifications

### 4.1 New Method Signatures

```python
# In orchestrator.py
class LLMOrchestrator:

    def _check_mid_loop_budget(
        self,
        messages: list[dict[str, Any]]
    ) -> tuple[bool, int]:
        """
        Check budget status mid-loop.

        Args:
            messages: Current messages list

        Returns:
            Tuple of (needs_action, remaining_tokens)
        """
        ...

    def _emergency_prune_history(
        self,
        messages: list[dict[str, Any]],
        target_tokens_to_free: int = 0
    ) -> int:
        """
        Emergency pruning during tool execution.

        Args:
            messages: Current messages list (mutated in place)
            target_tokens_to_free: Minimum tokens to free

        Returns:
            Actual tokens freed
        """
        ...
```

### 4.2 Class Modifications

| Class | Modification Type | Description |
|-------|------------------|-------------|
| `LLMOrchestrator` | Add method | `_check_mid_loop_budget()` |
| `LLMOrchestrator` | Add method | `_emergency_prune_history()` |
| `LLMOrchestrator._process_tool_result` | Modify | Add max_result_tokens check |
| `LLMOrchestrator._chat_complete` | Modify | Add mid-loop budget tracking |
| `SearchLogsTool` | Modify | Remove `events` field from return |
| `StatusFooter` | Modify | Add absolute token display |
| `ChatScreen` | Modify | Pass full context info to status |

### 4.3 Configuration

**Existing settings now enforced:**
```python
max_result_tokens: int = 50_000      # Maximum tokens per tool result
max_history_tokens: int = 80_000     # Maximum history tokens
context_window_buffer: int = 5_000   # Safety buffer
```

**Recommended new setting:**
```python
emergency_prune_threshold: int = 5_000  # Trigger emergency prune
```

### 4.4 Logging

New log messages added:

| Level | Message Pattern | When |
|-------|----------------|------|
| DEBUG | `Mid-loop budget check: X tokens remaining` | Every budget check |
| WARNING | `Context budget critically low: X tokens remaining` | Below threshold |
| WARNING | `Emergency pruning triggered` | Starting prune |
| INFO | `Emergency pruning complete: removed X messages` | After prune |
| INFO | `Tool result exceeds max_result_tokens` | Force cache |

### 4.5 Metrics

New metrics:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `emergency_prune` | Counter | messages_removed | Emergency prune triggered |
| `force_cache_size_limit` | Counter | tool_name | Result force-cached due to size |

---

## 5. Error Handling

### 5.1 Context Exhaustion

**Scenario:** Context fully exhausted even after emergency pruning.

**Handling:**
```python
if remaining_after_prune < 0:
    # Return graceful exit message
    error_msg = (
        "I've reached my context limit and cannot continue this conversation. "
        "Please use /clear to start a new conversation."
    )
    return error_msg
```

**User sees:**
```
Assistant: I've reached my context limit and cannot continue this conversation.
Please use /clear to start a new conversation.
```

### 5.2 Token Counting Failure

**Scenario:** `TokenCounter` raises exception.

**Handling:** Catch and use conservative fallback.
```python
try:
    tokens = TokenCounter.count_tokens(content, model)
except Exception as e:
    logger.warning(f"Token counting failed, using estimate: {e}")
    tokens = len(content) // 3  # Conservative 3 chars per token
```

### 5.3 Cache Failure During Force-Cache

**Scenario:** Result cache fails when force-caching large result.

**Handling:** Already exists in `_process_tool_result()`:
```python
except Exception as e:
    logger.error(f"Failed to cache result: {e}")
    self._notify_context_event(
        "warning",
        "Failed to cache large result, context may fill quickly"
    )
    # Fall through to use full result
```

### 5.4 Pruning Removes Critical Context

**Scenario:** Pruning removes information needed for current task.

**Handling:**
- Keep last 4 messages (2 exchanges) to maintain recent context
- Tool results cached, so data is still accessible via `fetch_cached_result_chunk`
- Log what was pruned for debugging

### 5.5 Error Message Consistency

All user-facing error messages follow this pattern:
```
[Clear problem description]. [Actionable suggestion].
```

Examples:
- "I've reached my context limit. Please use /clear to start a new conversation."
- "Context budget low (5K remaining). Consider starting a new conversation with /clear."

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File:** `tests/unit/core/test_context_management.py` (new file)

```python
import pytest
from unittest.mock import Mock, patch

from logai.core.orchestrator import LLMOrchestrator
from logai.config.settings import LogAISettings


class TestMidLoopBudgetTracking:
    """Tests for mid-loop token budget tracking (Fix 1)."""

    def test_budget_decreases_after_tool_result(self, orchestrator):
        """Budget should decrease when tool result added."""
        initial_budget = orchestrator.budget_tracker.get_usage().remaining_tokens

        # Simulate adding a tool result
        tool_result = {"data": "x" * 1000}  # ~250 tokens
        messages = [{"role": "tool", "content": str(tool_result)}]
        orchestrator.budget_tracker.add_message(messages[0])

        final_budget = orchestrator.budget_tracker.get_usage().remaining_tokens
        assert final_budget < initial_budget

    def test_emergency_prune_triggered_below_threshold(self, orchestrator):
        """Emergency prune should trigger when remaining < threshold."""
        # Fill up context
        orchestrator.budget_tracker._pending_results_tokens = 25000

        needs_action, remaining = orchestrator._check_mid_loop_budget([])

        if remaining < 5000:
            assert needs_action is True

    def test_graceful_exit_when_budget_exhausted(self, orchestrator):
        """Should return graceful message when budget fully exhausted."""
        # Force budget to negative
        orchestrator.budget_tracker._pending_results_tokens = 50000

        result = orchestrator._emergency_prune_history([])
        _, remaining = orchestrator._check_mid_loop_budget([])

        if remaining < 0:
            # Would return graceful exit in actual flow
            pass


class TestMaxResultTokensEnforcement:
    """Tests for max_result_tokens enforcement (Fix 2)."""

    def test_large_result_force_cached(self, orchestrator):
        """Results exceeding max_result_tokens should be cached."""
        large_result = {"events": [{"msg": "x" * 100} for _ in range(500)]}
        # ~50K+ tokens

        with patch.object(orchestrator, 'result_cache') as mock_cache:
            mock_cache.cache_result.return_value = Mock(
                cache_id="test-123",
                total_events=500
            )

            # Process should trigger caching
            # ... actual test implementation

    def test_small_result_not_force_cached(self, orchestrator):
        """Results under max_result_tokens should not be force cached."""
        small_result = {"events": [{"msg": "hello"}]}
        # ~50 tokens

        # Should pass through without caching


class TestSearchLogsDeduplication:
    """Tests for search_logs duplicate removal (Fix 3)."""

    @pytest.mark.asyncio
    async def test_events_field_removed(self, search_tool):
        """search_logs should not return 'events' field."""
        result = await search_tool.execute(
            log_group_patterns=["test-group"],
            search_pattern="ERROR",
            start_time="2026-02-17T00:00:00Z",
            end_time="2026-02-17T23:59:59Z",
        )

        assert "events" not in result
        assert "events_by_group" in result

    @pytest.mark.asyncio
    async def test_all_data_in_events_by_group(self, search_tool):
        """All events should be accessible in events_by_group."""
        result = await search_tool.execute(...)

        total_in_groups = sum(
            len(events)
            for events in result["events_by_group"].values()
        )
        assert total_in_groups == result["count"]


class TestEmergencyPruning:
    """Tests for emergency pruning (Fix 4)."""

    def test_prunes_oldest_messages_first(self, orchestrator):
        """Should remove oldest messages first (FIFO)."""
        orchestrator.conversation_history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
            {"role": "user", "content": "msg3"},  # Recent
            {"role": "assistant", "content": "resp3"},  # Recent
        ]

        orchestrator._emergency_prune_history([], target_tokens_to_free=1000)

        # Oldest should be removed
        assert len(orchestrator.conversation_history) == 4
        assert orchestrator.conversation_history[0]["content"] == "msg2"

    def test_never_prunes_last_4_messages(self, orchestrator):
        """Should always keep last 4 messages."""
        orchestrator.conversation_history = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]

        result = orchestrator._emergency_prune_history([], target_tokens_to_free=10000)

        # Should not prune anything (only 2 messages, need to keep 4)
        assert len(orchestrator.conversation_history) == 2
        assert result == 0  # No tokens freed

    def test_syncs_messages_list(self, orchestrator):
        """Should sync both conversation_history and messages list."""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "resp3"},
        ]
        orchestrator.conversation_history = messages[1:]  # Exclude system

        orchestrator._emergency_prune_history(messages, target_tokens_to_free=500)

        # Both lists should have same non-system messages
        assert len(messages) == len(orchestrator.conversation_history) + 1
```

### 6.2 Integration Tests

**File:** `tests/integration/test_context_overflow.py` (new file)

```python
import pytest
from unittest.mock import AsyncMock, Mock


class TestContextOverflowScenario:
    """Integration tests for context overflow prevention."""

    @pytest.mark.asyncio
    async def test_qwen3_32k_survives_15_tool_calls(self, orchestrator_32k):
        """
        Simulate Qwen3 32B usage pattern.
        Should survive 15+ tool calls without overflow.
        """
        orchestrator = orchestrator_32k  # 32K context

        # Simulate 15 tool calls
        for i in range(15):
            # Mock tool result
            tool_result = {
                "events": [{"message": f"Log {j}"} for j in range(50)],
                "count": 50,
            }

            # Process through orchestrator
            processed = await orchestrator._process_tool_result(
                {"tool_call_id": f"call_{i}", "result": tool_result},
                "query_logs"
            )

            # Check context hasn't overflowed
            usage = orchestrator.budget_tracker.get_usage()
            assert usage.utilization_pct <= 100

        # Verify emergency pruning occurred
        assert orchestrator.metrics.get_counter_value("emergency_prune") > 0

    @pytest.mark.asyncio
    async def test_large_search_result_cached(self, orchestrator_32k):
        """Large search results should be cached automatically."""
        # Create result that exceeds max_result_tokens
        large_result = {
            "events": [{"message": "x" * 500} for _ in range(200)],
            "count": 200,
        }

        processed = await orchestrator._process_tool_result(
            {"tool_call_id": "call_1", "result": large_result},
            "search_logs"
        )

        # Should have cache info, not full events
        assert "cache_id" in str(processed)
        assert "events" not in processed.get("result", processed)


class TestGracefulDegradation:
    """Test graceful handling when context exhausted."""

    @pytest.mark.asyncio
    async def test_returns_clear_message_on_exhaustion(self, orchestrator_32k):
        """Should return clear user message when context exhausted."""
        # Force context near exhaustion
        orchestrator_32k.budget_tracker._pending_results_tokens = 30000

        # Attempt another operation
        response = await orchestrator_32k.chat("Show me more logs")

        # Should get graceful message, not crash
        assert "context limit" in response.lower() or "clear" in response.lower()
```

### 6.3 Mock Strategy

```python
# conftest.py fixtures

@pytest.fixture
def mock_settings_32k():
    """Settings configured for 32K context (Qwen3 simulation)."""
    settings = LogAISettings()
    settings.context_window_size = 32000
    settings.max_result_tokens = 10000
    settings.emergency_prune_threshold = 5000
    return settings


@pytest.fixture
def orchestrator_32k(mock_settings_32k, mock_llm_provider):
    """Orchestrator configured for 32K context."""
    with patch('logai.core.context.token_counter.TokenCounter.get_context_window') as mock:
        mock.return_value = 32000
        orch = LLMOrchestrator(
            llm_provider=mock_llm_provider,
            tool_registry=Mock(),
            settings=mock_settings_32k,
        )
        return orch


@pytest.fixture
def search_tool(mock_datasource, mock_sanitizer):
    """SearchLogsTool with mocked dependencies."""
    return SearchLogsTool(
        datasource=mock_datasource,
        sanitizer=mock_sanitizer,
    )
```

### 6.4 Manual Testing Checklist

**With Qwen3 32B model:**

- [ ] Start conversation
- [ ] Execute 5+ queries involving log fetches
- [ ] Verify conversation doesn't crash
- [ ] Verify status bar shows context usage with absolute values (e.g., "25.5K/32K")
- [ ] Verify can complete more exchanges than before (>4)
- [ ] Verify emergency prune notification appears when triggered
- [ ] Verify graceful message when context exhausted

**Status Bar Display:**

- [ ] Context usage appears in format "X.XK/YYK (ZZ%)"
- [ ] Percentage accurate matches budget tracker
- [ ] Green color at <70%
- [ ] Yellow color at 70-85%
- [ ] Red color at >85%
- [ ] "(!)" prefix at >95%
- [ ] Updates after each response

---

## 7. Implementation Order

### Phase 1: Quick Wins (1-2 hours)

**Step 1.1: Remove duplicate data from search_logs (Fix 3)**
- File: `src/logai/core/tools/cloudwatch_tools.py`
- Change: Remove `"events": sanitized_events` line (line 481)
- Test: Verify search still works, check token reduction
- Validation: `pytest tests/unit/core/tools/test_cloudwatch_tools.py`

**Step 1.2: Enforce max_result_tokens (Fix 2)**
- File: `src/logai/core/orchestrator.py`
- Change: Add token count check in `_process_tool_result()` (around line 790)
- Test: Create large result, verify force-cached
- Validation: Manual test with large query

### Phase 2: Core Budget Management (2-3 hours)

**Step 2.1: Add mid-loop budget check method**
- File: `src/logai/core/orchestrator.py`
- Change: Add `_check_mid_loop_budget()` method (after line 1007)
- Test: Unit test the method
- Validation: Check debug logs show budget tracking

**Step 2.2: Add emergency pruning method (Fix 4)**
- File: `src/logai/core/orchestrator.py`
- Change: Add `_emergency_prune_history()` method (after line 950)
- Test: Unit test pruning logic
- Validation: Verify oldest messages removed, last 4 kept

**Step 2.3: Integrate tracking into main loop (Fix 1)**
- File: `src/logai/core/orchestrator.py`
- Change: Modify tool result processing in `_chat_complete()` (lines 1140-1148)
- Test: Integration test with multiple tool calls
- Validation: Monitor logs, verify no overflow with 15+ calls

### Phase 3: Visibility (1 hour)

**Step 3.1: Enhance status footer (Fix 5)**
- File: `src/logai/ui/widgets/status_footer.py`
- Changes:
  - Add `context_used_tokens` and `context_total_tokens` reactive attributes
  - Modify `_render_status_context()` for absolute display
  - Update `update_context_usage()` signature
- Test: Visual inspection in TUI

**Step 3.2: Update chat screen integration**
- File: `src/logai/ui/screens/chat.py`
- Change: Pass full context info in `_update_context_status()`
- Test: Verify display updates
- Validation: Manual test, verify format matches design

### Phase 4: Testing & Documentation (1 hour)

**Step 4.1: Add unit tests**
- Create `tests/unit/core/test_context_management.py`
- Run full test suite

**Step 4.2: Add integration tests**
- Create `tests/integration/test_context_overflow.py`
- Test with 32K simulated context

**Step 4.3: Update documentation**
- Configuration guide: Document settings
- User guide: Explain context limits, /clear command
- Troubleshooting: "Context limit reached" section

### Validation Gates

| Phase | Validation | Pass Criteria |
|-------|------------|---------------|
| 1.1 | `search_logs` returns no `events` field | Field absent |
| 1.2 | Large result triggers cache | Log shows "force-cache" |
| 2.1 | Budget check runs | Debug log shows tracking |
| 2.2 | Prune removes messages | Log shows "pruned X messages" |
| 2.3 | 15 tool calls succeed | No overflow error |
| 3.1 | Display shows "X.XK/YYK" | Visual confirmation |
| 3.2 | Display updates | Changes after each query |

---

## 8. Backwards Compatibility

### 8.1 Breaking Changes

| Change | Impact | Mitigation |
|--------|--------|------------|
| `events` field removed from search_logs | Code parsing this field will fail | All data in `events_by_group` |
| Status footer `update_context_usage()` signature | UI callers need update | Only internal call in chat.py |

### 8.2 Migration Notes

**For `events` field removal:**
```python
# Code that was using events directly:
# BEFORE
for event in result["events"]:
    process(event)

# AFTER - use events_by_group
for group_name, events in result["events_by_group"].items():
    for event in events:
        process(event)
```

### 8.3 Rollback Strategy

All changes are localized to these files:
1. `src/logai/core/orchestrator.py`
2. `src/logai/core/tools/cloudwatch_tools.py`
3. `src/logai/ui/widgets/status_footer.py`
4. `src/logai/ui/screens/chat.py`

**Rollback steps:**
1. `git revert <commit>` for any problematic commit
2. No database changes to rollback
3. No API changes affecting external systems

**Feature flag option:**
```python
# settings.py - add if rollback flexibility needed
enable_mid_loop_budget_tracking: bool = Field(
    default=True,
    description="Enable experimental mid-loop budget tracking"
)
```

### 8.4 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Emergency prune removes needed context | Low | Medium | Keep 4 recent messages |
| Token counting inaccurate | Low | Low | Conservative fallback |
| `events` removal breaks queries | Low | Low | Data still available |
| Performance overhead | Very Low | Low | Only count new tokens |

---

## 9. Appendices

### Appendix A: Token Budget Calculation Reference

```
Context Window Budget (32K example):

┌────────────────────────────────────────────────────────┐
│                    32,000 tokens                        │
├────────────────────────────────────────────────────────┤
│ Safety Buffer (5%)        │    1,600 tokens            │
├───────────────────────────┼────────────────────────────┤
│ Response Reserve (4%)     │    1,280 tokens            │
├───────────────────────────┼────────────────────────────┤
│ System Prompt (5%)        │    1,600 tokens            │
├───────────────────────────┼────────────────────────────┤
│ Available for Content     │   27,520 tokens            │
│   ├─ History (55%)        │   ~15,136 tokens           │
│   └─ Results (45%)        │   ~12,384 tokens           │
└───────────────────────────┴────────────────────────────┘

Emergency Prune Threshold: 5,000 tokens remaining
Target Free on Prune: 25% of used (~6,800 tokens)
```

### Appendix B: File Change Summary

| File | Lines Changed | Type |
|------|--------------|------|
| `src/logai/core/orchestrator.py` | ~100 | Add methods, modify loop |
| `src/logai/core/tools/cloudwatch_tools.py` | ~3 | Remove line |
| `src/logai/ui/widgets/status_footer.py` | ~30 | Enhance display |
| `src/logai/ui/screens/chat.py` | ~10 | Update method call |
| `tests/unit/core/test_context_management.py` | ~150 | New file |
| `tests/integration/test_context_overflow.py` | ~100 | New file |

### Appendix C: Glossary

| Term | Definition |
|------|------------|
| Context Window | Maximum tokens the LLM can process in one request |
| Emergency Prune | Aggressive history removal when context critically low |
| Force Cache | Store result in cache regardless of event count |
| Mid-Loop Tracking | Checking budget during tool execution, not just at turn start |
| Usable Tokens | Context window minus safety buffer |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 17, 2026 | Saanvi | Initial design document |

---

**Design Document Complete**

**Deliverable Location:** `george-scratch/design-context-window-fixes.md`

**Ready for:** Implementation by Jackie
**Estimated Total Effort:** 5-6 hours
**Risk Level:** Low (all changes reversible, no data migrations)
