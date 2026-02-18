# Requirements: Context Window Management Fixes

**Date:** February 17, 2026
**Project:** LogAI
**Type:** Bug Fix / Enhancement
**Priority:** High
**Estimated Effort:** 4-5 hours

---

## Problem Statement

Users running LogAI with smaller context window models (e.g., Qwen3 32B with 32K tokens) run out of context space after only 3-4 exchanges. Investigation revealed that while token counting infrastructure exists, the application:

1. Does not track token usage during tool execution loops
2. Does not enforce configured token limits
3. Accumulates tool results without cleanup
4. Returns duplicate data in search results

**Impact:** Makes the application unusable with smaller context models, limits long conversations even with larger models.

---

## Scope

This feature will implement **3 critical fixes** to resolve context window exhaustion:

### In Scope
1. ✅ Mid-loop token tracking and budget management
2. ✅ Enforcement of max_result_tokens configuration
3. ✅ Removal of duplicate data from search_logs tool
4. ✅ Emergency pruning when context nears limit
5. ✅ Context usage visibility in status bar

### Out of Scope (Future Enhancements)
- System prompt optimization (Priority 2)
- Model-specific prompt templates
- Conversation summarization
- Sliding window for very long sessions

---

## Requirements

### FR1: Mid-Loop Token Budget Management

**Description:** Track and update token budget after each tool execution during the orchestration loop.

**Acceptance Criteria:**
- [ ] Token budget recalculated after each tool result is added to messages
- [ ] Remaining budget tracked and logged at debug level
- [ ] When remaining budget falls below safety threshold (5K tokens), trigger emergency pruning
- [ ] If budget exhausted after pruning, gracefully stop tool loop with informative message to user
- [ ] Budget tracking does not break existing functionality

**Technical Details:**
- Location: `src/logai/core/orchestrator.py` in `_run_conversation_turn()` method
- Add token counting after line ~1148 (after tool result added)
- Maintain running total of: system_tokens + history_tokens + tool_result_tokens
- Use existing `_count_tokens()` method
- Respect existing `context_window_buffer` setting from config

**Example Logic:**
```python
# After adding tool result to messages
tool_result_tokens = self._count_tokens(str(tool_result))
total_tokens_used = system_tokens + history_tokens + tool_result_tokens
remaining_budget = context_limit - total_tokens_used - context_window_buffer

if remaining_budget < 5000:
    logger.warning(f"Context budget low: {remaining_budget} tokens remaining")
    self._emergency_prune_history()
    # Recalculate after pruning

if remaining_budget < 0:
    return "I've reached my context limit. Please start a new conversation with /clear"
```

---

### FR2: Enforce max_result_tokens Configuration

**Description:** Enforce the configured `max_result_tokens` limit to prevent single large tool results from consuming excessive context.

**Acceptance Criteria:**
- [ ] Tool results exceeding `max_result_tokens` are automatically cached (even if < 100 events)
- [ ] LLM receives cache summary instead of full result when limit exceeded
- [ ] Setting `max_result_tokens` is honored (currently defaults to 50,000)
- [ ] Logged when result is force-cached due to size
- [ ] Fetch cached result tool still allows retrieving full data in chunks

**Technical Details:**
- Location: `src/logai/core/orchestrator.py` in `_execute_tool()` method
- After tool execution, before adding result to messages
- Check token count of result against `settings.max_result_tokens`
- If exceeded, call `_maybe_cache_result()` with force=True parameter
- Add force parameter to caching method if needed

**Example Logic:**
```python
# After tool executes successfully
result_tokens = self._count_tokens(str(tool_result))

if result_tokens > self.settings.max_result_tokens:
    logger.info(f"Tool result ({result_tokens} tokens) exceeds max_result_tokens "
                f"({self.settings.max_result_tokens}), forcing cache")
    cached_summary = self._maybe_cache_result(
        tool_name=tool_name,
        tool_result=tool_result,
        force_cache=True
    )
    tool_result = cached_summary  # Replace with summary
```

---

### FR3: Remove Duplicate Data from search_logs

**Description:** The `search_logs` tool currently returns the same events twice: once in `events` array and again in `events_by_group` structure. This wastes 50-100% of the result's token budget.

**Acceptance Criteria:**
- [ ] `search_logs` tool returns events only once (in `events_by_group` structure)
- [ ] Remove redundant `events` array from response
- [ ] LLM can still access all event data through `events_by_group`
- [ ] Existing queries continue to work (backward compatible)
- [ ] Token usage reduced by ~50% for search operations

**Technical Details:**
- Location: `src/logai/core/tools/cloudwatch_tools.py` in `SearchLogsTool.execute()` method
- Line ~490: Remove `"events": all_events` from return dictionary
- Keep `events_by_group` which contains all the same data organized by log group
- Update tool description/schema if it references the `events` field

**Example Change:**
```python
# BEFORE (line ~490)
return {
    "total_events": len(all_events),
    "events": all_events,              # ← REMOVE THIS
    "events_by_group": grouped_events,
    "summary": {...}
}

# AFTER
return {
    "total_events": len(all_events),
    "events_by_group": grouped_events,  # Contains all data
    "summary": {...}
}
```

---

### FR4: Emergency Pruning Strategy

**Description:** When context budget is low, intelligently prune conversation history to free up space.

**Acceptance Criteria:**
- [ ] Emergency pruning triggered when remaining budget < 5K tokens
- [ ] Prunes oldest user/assistant message pairs first
- [ ] Never prunes system message
- [ ] Never prunes current tool execution cycle
- [ ] Keeps at least last 2 message pairs for continuity
- [ ] Logs pruning action and tokens freed

**Technical Details:**
- Location: `src/logai/core/orchestrator.py` - new method or enhance existing `_prune_old_messages()`
- Current pruning happens at start of turn; this adds mid-loop pruning
- Strategy: Remove oldest message pairs until budget is safe (>10K remaining)
- Don't prune more than necessary

**Example Logic:**
```python
def _emergency_prune_history(self, target_tokens_to_free: int = 5000):
    """Prune history during tool execution when context budget is low."""
    logger.warning("Emergency pruning triggered due to low context budget")

    # Skip system message (index 0), keep recent messages
    prunable_messages = self.messages[1:-4]  # Keep last 2 pairs

    tokens_freed = 0
    messages_removed = 0

    for msg in prunable_messages:
        if tokens_freed >= target_tokens_to_free:
            break
        msg_tokens = self._count_tokens(msg["content"])
        self.messages.remove(msg)
        tokens_freed += msg_tokens
        messages_removed += 1

    logger.info(f"Pruned {messages_removed} messages, freed {tokens_freed} tokens")
    return tokens_freed
```

---

### FR5: Context Usage Visibility

**Description:** Display current context usage in the TUI status bar so users can see when they're approaching limits.

**Acceptance Criteria:**
- [ ] Status bar shows: `Context: 25.5K/32K (80%)`
- [ ] Updates after each LLM response
- [ ] Color coding: Green (<70%), Yellow (70-85%), Orange (85-95%), Red (>95%)
- [ ] Clicking shows tooltip: "Use /clear to reset conversation"

**Technical Details:**
- Location: `src/logai/ui/screens/chat.py` in status bar widget
- Add context_tokens and context_limit to status display
- Orchestrator exposes `get_context_usage()` method
- Update after each turn completes

**Example Display:**
```
Models: qwen3:32b | Cache: 5/8 (62%) | Context: 25.5K/32K (80%) | Type /help for commands
```

---

## Configuration Changes

### Existing Settings to Honor

These settings already exist in `settings.py` but are not currently enforced:

```python
max_result_tokens: int = Field(
    default=50_000,
    description="Maximum tokens for single tool result before forcing cache"
)

max_history_tokens: int = Field(
    default=80_000,
    description="Maximum tokens to keep in conversation history"
)

context_window_buffer: int = Field(
    default=5_000,
    description="Safety buffer to keep from context limits"
)
```

**Action:** Enforce these settings in the orchestrator.

### New Settings (Optional)

Consider adding:

```python
emergency_prune_threshold: int = Field(
    default=5_000,
    description="Trigger emergency pruning when remaining budget below this"
)

show_context_in_status: bool = Field(
    default=True,
    description="Display context usage in status bar"
)
```

---

## Technical Approach

### File Changes Required

1. **`src/logai/core/orchestrator.py`** (Primary changes)
   - Add mid-loop token budget tracking
   - Add emergency pruning method
   - Enforce max_result_tokens
   - Expose get_context_usage() for UI

2. **`src/logai/core/tools/cloudwatch_tools.py`**
   - Remove duplicate events from search_logs response

3. **`src/logai/ui/screens/chat.py`**
   - Add context usage to status bar
   - Color coding based on usage percentage

4. **`src/logai/ui/widgets/status_bar.py`** (if exists, or modify chat.py)
   - Update status bar layout to include context info

---

## Testing Requirements

### Unit Tests

1. **Token Budget Tracking**
   - Test budget decreases after each tool result
   - Test emergency pruning triggered at threshold
   - Test graceful stop when budget exhausted

2. **max_result_tokens Enforcement**
   - Test large result is cached when exceeds limit
   - Test small result not cached when under limit
   - Test cache summary replaces full result

3. **Search Deduplication**
   - Test search_logs returns only events_by_group
   - Test no duplicate event data in response
   - Verify token count reduction

4. **Emergency Pruning**
   - Test prunes oldest messages first
   - Test keeps minimum message pairs
   - Test never prunes system message
   - Test tokens freed calculation

### Integration Tests

1. **Context Exhaustion Scenario**
   - Simulate conversation with Qwen3 32K model
   - Execute 15+ tool calls
   - Verify context doesn't overflow
   - Verify emergency pruning activates
   - Verify graceful handling when limit reached

2. **Long Conversation**
   - Test 10+ exchanges with tool usage
   - Verify context stays within limits
   - Verify older messages pruned appropriately

3. **Large Result Handling**
   - Query that returns 500+ events
   - Verify result cached due to token size
   - Verify LLM receives summary
   - Verify can still fetch chunks

### Manual Testing

1. **With Qwen3 32B model:**
   - Start conversation
   - Perform 5+ queries involving log fetches
   - Verify conversation doesn't crash
   - Verify status bar shows context usage
   - Verify can complete more exchanges than before (>4)

2. **Status Bar Display:**
   - Verify context usage appears
   - Verify percentage accurate
   - Verify color changes at thresholds
   - Verify updates after each response

---

## Success Metrics

**Before Fix:**
- Qwen3 32B: 3-4 exchanges before context overflow
- No visibility into context usage
- Search results use 2x tokens unnecessarily

**After Fix:**
- Qwen3 32B: 10+ exchanges without overflow
- Context usage visible in status bar
- Search results use 50% fewer tokens
- Emergency pruning prevents crashes
- Graceful degradation when limits approached

---

## Dependencies

### Internal
- Existing token counting infrastructure (`_count_tokens()`)
- Existing result caching system
- Existing history pruning logic
- Status bar widget

### External
- None (uses existing libraries)

---

## Risks & Mitigations

**Risk 1:** Emergency pruning breaks conversation continuity
**Mitigation:** Keep minimum 2 message pairs, only prune when necessary, log all pruning actions

**Risk 2:** Token counting inaccurate for some models
**Mitigation:** Use conservative fallback (3.5 chars/token), add buffer, test with multiple models

**Risk 3:** Removing `events` field from search breaks existing queries
**Mitigation:** All data still available in `events_by_group`, test existing queries, LLM adapts

**Risk 4:** Context tracking adds performance overhead
**Mitigation:** Only count tokens that are added (not entire history), use efficient tiktoken, minimal impact

---

## Implementation Order

1. **FR3 first** (Remove duplicate data) - Easiest, immediate 50% reduction in search tokens
2. **FR2 second** (Enforce max_result_tokens) - Prevents single large result from overwhelming context
3. **FR1 & FR4 third** (Mid-loop tracking + emergency pruning) - Core budget management
4. **FR5 last** (Status bar visibility) - Nice to have, depends on FR1

---

## Rollback Plan

If issues arise:
1. All changes are in orchestrator.py and cloudwatch_tools.py
2. Can revert commits individually
3. No database schema changes
4. No breaking API changes
5. Feature flag can disable emergency pruning if needed

---

## Documentation Updates

After implementation, update:
1. **User Guide** - Explain context limits, /clear command, status bar indicators
2. **Configuration Guide** - Document max_result_tokens, max_history_tokens, context_window_buffer
3. **Architecture Doc** - Explain context management strategy
4. **Troubleshooting Guide** - Add "Context limit reached" section

---

## Questions for Product Owner

1. Should we add configuration for emergency_prune_threshold or use hardcoded 5K?
2. Should context usage display be optional (configurable)?
3. What color scheme for context usage? (Green/Yellow/Orange/Red?)
4. Should we add metrics for context_overflow_prevented events?

---

## Acceptance Criteria Summary

**This feature is complete when:**

- [ ] Users can complete 10+ exchanges with Qwen3 32B without context overflow
- [ ] max_result_tokens setting is enforced
- [ ] Search results use 50% fewer tokens (duplicate data removed)
- [ ] Emergency pruning prevents context crashes
- [ ] Status bar displays context usage with color coding
- [ ] All unit tests pass (10+ new tests)
- [ ] Integration tests demonstrate improvement
- [ ] Manual testing confirms 3x improvement in conversation length
- [ ] Code reviewed and approved
- [ ] Documentation updated

---

**Requirements Author:** George (TPM)
**Date:** February 17, 2026
**Estimated Effort:** 4-5 hours
**Target Completion:** 1-2 days
