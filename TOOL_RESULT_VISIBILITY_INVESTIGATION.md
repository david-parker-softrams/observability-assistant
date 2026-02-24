# Investigation Report: Agent Not Seeing Tool Results After fetch_logs

**Investigator**: Hans (Code Librarian)
**Date**: Feb 23, 2026
**Status**: Investigation Complete - Root Cause Identified

## Executive Summary

I've investigated why the agent calls `fetch_logs` tool successfully, receives log results, but then responds as if it didn't receive any logs. The investigation traced the entire tool execution flow and identified the likely root cause related to the context injection fix (commit 8692862).

**Key Finding**: While the technical flow appears correct, there's a critical issue with how the context injection fix handles message visibility to the LLM, combined with a result caching side effect.

---

## Detailed Investigation

### 1. Tool Implementation ✓ CORRECT

**File**: `src/logai/core/tools/cloudwatch_tools.py` (lines 127-309)

- `FetchLogsTool` is properly implemented
- Returns correct structure: `{"success": True, "events": [...], ...}`
- Tool execution doesn't have errors

### 2. Tool Result Message Wrapping ✓ CORRECT

**File**: `src/logai/core/orchestrator.py` (lines 1100-1107)

Tool results are properly wrapped and added to messages:
```python
tool_message: dict[str, Any] = {
    "role": "tool",
    "tool_call_id": tool_result["tool_call_id"],
    "content": json.dumps(tool_result["result"]),
}
self.conversation_history.append(tool_message)
messages.append(tool_message)  # ← Added to messages array
```

This format is correct for OpenAI API.

### 3. Message Array Accumulation ✓ MOSTLY CORRECT

**File**: `src/logai/core/orchestrator.py` (lines 1030-1107)

Messages array is built BEFORE the loop (lines 1030-1034):
```python
messages = [{"role": "system", "content": system_prompt}]
if self.conversation_history:
    messages.extend(self.conversation_history)
```

Then INSIDE the loop, tool results are added to this same `messages` array (line 1107).

**Expected Flow**:
- Iteration 1: LLM call with `[system, user]`
- LLM returns tool_calls
- Tool results added to `messages` → `[system, user, assistant, tool]`
- Iteration 2: LLM call with `[system, user, assistant, tool]`
- Agent should see the tool results ✓

### 4. CRITICAL: Context Injection Fix Side Effects ⚠ ISSUE FOUND

**File**: `src/logai/core/orchestrator.py` (lines 1016-1034)

The context injection fix (commit 8692862) made these changes:

**Before**: Multiple system messages (broken for OpenAI API)
```python
messages = [{"role": "system", "content": system_prompt}]
messages.extend(conversation_history)
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})  # 2nd system msg!
```

**After**: Single merged system message
```python
system_prompt = self._get_system_prompt()
pending_injection = self._get_pending_context_injection()
if pending_injection:
    system_prompt = system_prompt + "\n\n---\n\n" + pending_injection  # Merge into one
messages = [{"role": "system", "content": system_prompt}]
messages.extend(self.conversation_history)
```

**The Issue**:
1. Context injection is merged into system prompt BEFORE the while loop
2. This creates ONE large system message with potentially problematic formatting
3. Subsequent tool messages might not be parsed correctly by the LLM API

### 5. Result Caching Side Effect ⚠ LIKELY CULPRIT

**File**: `src/logai/core/orchestrator.py` (lines 528-677, specifically 605-610)

```python
if summary.total_events > 0:
    self._pending_cache_guidance = {
        "cache_id": summary.cache_id,
        "tool_name": tool_name,
        "total_events": summary.total_events,
    }
```

This sets `_pending_cache_guidance` which modifies the system prompt on the NEXT LLM call!

**The Real Problem**:
1. Tool executes and returns results
2. `_process_tool_result()` MIGHT cache the result
3. If cached, it returns a SUMMARY instead of the full result
4. Then `_pending_cache_guidance` is set
5. On the next LLM call, this guidance is merged into the system prompt
6. The guidance tells the agent to FETCH CHUNKS, not to analyze the result
7. Agent never sees the actual log data, only fetch instructions!

### 6. Message Visibility Issue - THE REAL BUG

**The Problem Chain**:

1. `fetch_logs` returns 500 log events
2. `_process_tool_result()` checks if result should be cached (line 557)
3. Result size > threshold → triggers caching (line 568)
4. Result is cached, summary returned with 0-5 sample events
5. Pending cache guidance is SET (line 606)
6. Tool result added to messages as summary (line 654-657)
7. On next LLM call, `_get_pending_context_injection()` is called (line 1019)
8. Cache guidance is merged into system prompt as injection (line 457-480)
9. System prompt now contains: original_system + context_injection + cache_fetch_instructions
10. But agent receives tool result as SUMMARY, then sees instructions to FETCH CHUNKS
11. Agent responds based on cached summary, not actual logs!

---

## Root Cause Analysis

The bug is a **COMBINATION** of two features interacting badly:

1. **Context Injection Fix (commit 8692862)**: Merges ALL context into system prompt
2. **Result Caching Feature**: Caches large results and sets pending guidance

**The Interaction**:
- Context injection merges cache guidance into system prompt
- This happens BEFORE the agent processes the cached result
- The agent gets confused about whether to analyze the result or fetch chunks
- Result visibility is compromised because guidance interferes with result processing

---

## Recommended Fix Approach

### Option 1: Prevent Caching for Tool Results (Quick Fix)
Modify `_process_tool_result()` to NOT cache tool results, only cache user-provided data.

**Pros**:
- Simple, fast fix
- Restores full visibility

**Cons**:
- Larger context usage for large result sets

### Option 2: Separate Cache Guidance from Context Injection (Better)
Don't merge cache guidance into system prompt. Instead:
- Add cache guidance as a separate system message AFTER tool results
- Keep system prompt clean (only original + user context)

**Pros**:
- Maintains cache benefits
- Clear separation of concerns
- Tool results fully visible

**Cons**:
- Slightly more complex

### Option 3: Fix Message Ordering (Best)
1. System prompt (original only)
2. User/history messages
3. Tool results (WITH their actual content, even if cached)
4. Cache guidance (as optional system message AFTER results)

**Pros**:
- LLM sees results before fetch instructions
- All information visible
- Clean architecture

**Cons**:
- Requires careful implementation

---

## Files to Review

1. **`src/logai/core/orchestrator.py`**
   - Lines 1016-1034: Context injection merger (works but affects message structure)
   - Lines 1099-1107: Tool result addition (correct format)
   - Lines 1019-1027: Pending injection handling
   - Lines 528-677: `_process_tool_result()` (likely source of caching/guidance)
   - Lines 602-610: `_pending_cache_guidance` setting (the problem!)
   - Lines 449-493: `_get_pending_context_injection()` (merges guidance into system prompt)

2. **`tests/unit/core/test_orchestrator_context.py`**
   - Tests for context injection (all passing but don't test tool results with caching)

---

## Test Cases to Add

1. Test that tool results are visible when caching threshold is exceeded
2. Test that cache guidance doesn't interfere with result analysis
3. Test message order with tool calls + cached results
4. Test with context injection + tool results combined

---

## Git Commits to Review

- **8692862**: Context injection fix (merged context into system prompt)
- **6a6e2c1**: Message reordering fix (tool result ordering)
- **620defd**: Cache guidance feature (added pending_cache_guidance)

---

## Conclusion

The agent is NOT seeing tool results because:

1. Tool results are correctly added to messages ✓
2. BUT large results trigger caching
3. Cached results return SUMMARY instead of full data
4. Cache fetch guidance is merged into system prompt
5. Agent gets confused between analyzing summary vs fetching chunks
6. Agent responds as if no logs found (because summary is minimal)

**Recommendation**: Implement Option 2 or 3 to separate cache guidance from system prompt context, ensuring tool results are always visible to the agent before any fetch instructions.
