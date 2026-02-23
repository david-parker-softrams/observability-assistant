# Fetch Flow Issue - Executive Summary

**Status**: 🔴 CRITICAL - Root Cause Identified
**Confidence**: 95%
**Fix Time**: 15 minutes (10 min code + 5 min test)

---

## Problem In One Sentence

Agent's fetch_cached_result_chunk results are being re-cached into new summaries instead of being delivered as-is, so agent receives 5 samples instead of the 100 events it explicitly requested.

---

## The Bug

```
Agent: "Give me 100 events (offset=0, limit=100)"
System: "Here's a summary with 5 samples instead"
Agent: "But I asked for 100!"
System: ¯\_(ツ)_/¯
```

### What's Happening

1. Agent calls `fetch_cached_result_chunk(cache_id, offset=0, limit=100)`
2. Tool correctly returns `{events: [...100 actual events...], count: 100}`
3. **BUG**: Result goes through `_process_tool_result()`
4. If result > 10K tokens, it gets RE-CACHED
5. New cache creates summary with only 5 samples
6. Agent receives summary instead of 100 events ❌

### Why Tests Pass

Tests use small result sets (~1K tokens) that never exceed threshold, so re-caching code never runs.

---

## Root Cause

**File**: `src/logai/core/orchestrator.py`
**Method**: `_process_tool_result()` (lines 659-812)
**Issue**: No special handling for `fetch_cached_result_chunk` - it goes through normal caching flow

---

## The Fix

Add **4 lines** at start of `_process_tool_result()`:

```python
# Never cache fetch results - agent requested full events, not summary
if tool_name == "fetch_cached_result_chunk":
    token_count = TokenCounter.estimate_json_tokens(result_data, self.settings.current_llm_model)
    self.budget_tracker.add_result_tokens(token_count)
    return tool_result  # Return as-is, no caching!
```

**Impact**:
- ✅ Fetch results bypass caching
- ✅ Agent gets all requested events
- ✅ No side effects on other tools
- ✅ Budget tracking still works

---

## Verification

1. Implement fix (10 min)
2. Run: `pytest tests/unit/core/ -v` (2 min)
3. Manual test: Query → Fetch → Analyze (3 min)
4. All should work

---

## Files To Change

- `src/logai/core/orchestrator.py` - Add 4 lines in `_process_tool_result()`

**That's it!**

---

**Investigation**: Hans
**Status**: Ready to implement
**Blocker**: NO - Can merge immediately after fix
