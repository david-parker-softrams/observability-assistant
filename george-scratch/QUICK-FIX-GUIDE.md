# Quick Fix Guide - "Add to Context" Bug

## TL;DR

**Problem:** User's selected logs get lost when tool calls generate cached results

**Location:** `src/logai/core/orchestrator.py` lines 435-470

**Fix:** Combine both pending injections instead of choosing one

## The Bug (3 lines to understand)

```python
# Line 438: Cache guidance checked FIRST
if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
    return cache_guidance  # ← User context lost!

# Line 468: User context only checked if cache guidance wasn't set
injection = self._pending_context_injection
return injection  # Only reached if cache guidance is None
```

## The Fix (Replace lines 435-470)

```python
def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    injections = []

    # Include cache guidance if available
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None  # Clear after use
        cache_guidance = f"""SYSTEM INSTRUCTION: The previous tool call returned a large result that was automatically cached.

CACHED RESULT INFORMATION:
- Cache ID: {guidance["cache_id"]}
- Total events cached: {guidance["total_events"]}

You MUST now fetch chunks to show the user actual log events:

STEP 1: Fetch first chunk
Call fetch_cached_result_chunk with these parameters:
- cache_id: {guidance["cache_id"]} (use this exact value)
- offset: 0
- limit: {self.settings.initial_chunk_size}

STEP 2: Analyze and fetch more if needed
If you need more events, call again with:
- cache_id: {guidance["cache_id"]} (same value)
- offset: {self.settings.initial_chunk_size}
- limit: {self.settings.initial_chunk_size}

IMPORTANT: Always use the exact cache_id value shown above.

DO NOT just acknowledge the cache - fetch and show the user actual events.
"""
        injections.append(cache_guidance)

    # Include user-selected log entries if available
    if self._pending_context_injection:
        injection = self._pending_context_injection
        self._pending_context_injection = None
        injections.append(injection)

    # Return combined injections or None if empty
    if injections:
        return "\n\n---\n\n".join(injections)
    return None
```

## What Changes

| Before | After |
|--------|-------|
| If cache guidance exists → return it | If cache guidance exists → include it |
| User context → ignored | User context → also included |
| One injection per call | Multiple injections combined |
| Data loss | No data loss |

## Test Cases

### Test 1: Both injections present
```python
orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}
orchestrator.inject_context_update("USER LOGS: ...")

result = orchestrator._get_pending_context_injection()

# Should contain BOTH
assert "SYSTEM INSTRUCTION" in result  # Cache guidance
assert "USER-SELECTED LOG ENTRIES" in result  # User context
```

### Test 2: Only user context
```python
orchestrator.inject_context_update("USER LOGS: ...")

result = orchestrator._get_pending_context_injection()

assert "USER-SELECTED LOG ENTRIES" in result
assert result.count("---") == 0  # No separator if only one
```

### Test 3: Only cache guidance
```python
orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}

result = orchestrator._get_pending_context_injection()

assert "SYSTEM INSTRUCTION" in result
assert "USER-SELECTED LOG ENTRIES" not in result
```

## Why This Works

1. **No data loss** - Both injections are preserved
2. **Maintains priority** - Cache guidance listed first, user context second
3. **Backward compatible** - Still returns single injection when only one exists
4. **Simple separator** - Uses `\n\n---\n\n` to clearly separate sections
5. **Clears both** - Both variables are set to None after retrieval

## Files Modified

- `src/logai/core/orchestrator.py` - Lines 435-470 (one method)

## Lines of Code Changed

~35 lines modified (mostly just including the cache guidance text block)

## Risk Level

**LOW** - Only changes injection retrieval, not orchestration logic

## Deployment

1. Backup `orchestrator.py`
2. Replace `_get_pending_context_injection()` method
3. Run unit tests to verify
4. Run integration tests to verify
5. Manual QA: Add logs to context + ask question with tool calls

## Verification

After fix, test this scenario:
1. Open LogAI
2. Double-click log group → preview opens
3. Select some log entries
4. Click "Add to Context"
5. Ask a question about those logs (might trigger tool call)
6. In logs/debugging, verify BOTH cache guidance AND user context are in messages sent to LLM
7. Agent should answer with knowledge of selected logs ✅

---

**Full Investigation:** See `investigation-add-to-context-bug.md`
