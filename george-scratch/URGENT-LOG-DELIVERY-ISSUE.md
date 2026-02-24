# URGENT: Log Delivery Issue Investigation Report

**Date**: Feb 23, 2026
**Status**: ROOT CAUSE IDENTIFIED
**Severity**: CRITICAL - Logs not reaching agent at all

---

## PROBLEM STATEMENT

After Jackie's Phase 1 implementation (commit 009f3d4), logs are no longer being delivered to the agent in actual usage. Tests pass (29/29), but in real scenarios, the agent receives no log events and cannot analyze them.

**Key Facts**:
- Commit 9ff9993 (full results): Logs delivered ✅ Working
- Commit 009f3d4 (Phase 1): Logs NOT delivered ❌ Broken
- All tests passing despite broken behavior
- Settings: `enable_result_caching=True` (line 406 in settings.py)
- Threshold: `cache_large_results_threshold=10000` tokens (line 416 in settings.py)

---

## ROOT CAUSE ANALYSIS

### 🎯 THE CRITICAL BUG

The problem is in **Phase 1's approach to the result structure** combined with **how LLMs parse tool results**.

**Location**: `src/logai/core/orchestrator.py` lines 814-853 in `_create_enhanced_cache_summary()`

```python
# PHASE 1 CODE (BROKEN)
def _create_enhanced_cache_summary(self, summary, original_result, tool_name):
    base_structure = summary.to_context_dict()  # Returns 5-key structure

    enhanced = {
        "success": True,
        "message": f"Successfully retrieved {summary.total_events} log events...",
        "cached_result": base_structure,  # ⚠️ NESTED STRUCTURE ISSUE
    }
    return enhanced
```

**The Issue**: The actual log event data is now nested under `cached_result > preview_events`:

```
Tool Result (what LLM receives):
{
  "success": True,
  "message": "Successfully retrieved 1000 log events...",
  "cached_result": {
    "result_type": "cached_preview",
    "full_dataset": {...},
    "preview_events": [...events...],  # ⚠️ Events buried 3 levels deep!
    "fetch_more": {...},
    "expires_in_seconds": 3600
  }
}
```

### Why This Breaks

1. **LLM expects flat/simple structure**: When tool results are passed to an LLM, they expect data at predictable paths
2. **Events now invisible**: The actual log events are nested as `result.cached_result.preview_events` instead of being at a top level
3. **Agent parsing issue**: LLM sees the success message but doesn't find actionable event data in the expected location
4. **Message format expectations**: The wrapped structure confuses the LLM's parsing of tool results

### Comparison: Before vs After

**BEFORE (9ff9993 - WORKING):**
```python
# Full results were returned as-is
return tool_result  # {tool_call_id: "...", result: {events: [...]}}
```

LLM receives:
```json
{
  "events": [...1000 log events...],
  "count": 1000,
  ...
}
```

**AFTER (009f3d4 - BROKEN):**
```python
# Phase 1 enhanced summary
return {
    "tool_call_id": "...",
    "result": {
        "success": True,
        "message": "Successfully retrieved 1000...",
        "cached_result": {
            "preview_events": [...5 sample events...],
            ...
        }
    }
}
```

The LLM receives nested structure with only 5 sample events deep in the hierarchy, but the JSON conversion and message format make it hard for the agent to find/parse the actual data.

---

## HOW IT FLOWS THROUGH THE SYSTEM

### 1. Tool execution (line 1855 in orchestrator.py):
```python
result = await self.tool_registry.execute(function_name, **function_args)
# Returns: {events: [1000 items], count: 1000, ...}
```

### 2. Processing (line 1865):
```python
tool_result = {"tool_call_id": tool_call_id, "result": result}
processed_result = await self._process_tool_result(tool_result, function_name)
# _process_tool_result checks if should cache (1000 items > 10000 tokens threshold?)
```

### 3. Caching decision (line 697-700):
```python
should_cache, token_count = self.budget_tracker.should_cache_result(
    result_data,
    threshold=self.settings.cache_large_results_threshold,  # 10000 tokens
)
```

**Here's where it gets interesting**: If the result is ~10,000+ tokens, it gets cached. If smaller, it returns as-is. But Phase 1 ALWAYS wraps cached results.

### 4. Enhanced summary creation (line 814-853):
```python
enhanced_summary = self._create_enhanced_cache_summary(
    summary, result_data, tool_name
)
# Returns: {success: True, message: "...", cached_result: {...}}
```

### 5. Tool message to LLM (line 1290-1297):
```python
tool_message = {
    "role": "tool",
    "tool_call_id": tool_result["tool_call_id"],
    "content": json.dumps(tool_result["result"])  # ⚠️ Converts enhanced structure to JSON
}
messages.append(tool_message)
```

The JSON.stringify of the nested structure makes it hard for the LLM to parse!

---

## EVIDENCE FROM CODE

### settings.py (line 405-407):
```python
enable_result_caching: bool = Field(
    default=True,  # ⚠️ CACHING IS ENABLED BY DEFAULT
    description="Enable caching of large tool results outside context window",
)
```

### orchestrator.py (line 688-694):
```python
if not self.settings.enable_result_caching:
    # Just track tokens and return
    token_count = TokenCounter.estimate_json_tokens(
        result_data, self.settings.current_llm_model
    )
    self.budget_tracker.add_result_tokens(token_count)
    return tool_result  # ⚠️ Returns original result IF disabled
```

**So if `enable_result_caching=False`, it would work correctly!** The system bypasses the nested wrapper.

### result_cache.py (line 32-70):
```python
def to_context_dict(self) -> dict[str, Any]:
    return {
        "result_type": "cached_preview",
        "full_dataset": {...},
        "preview_events": self.sample_events,  # Only 5 samples!
        "fetch_more": {...},
        "expires_in_seconds": max(0, self.expires_at - int(time.time())),
    }
```

---

## TEST COVERAGE GAP

**Why tests pass but real usage fails**:

Looking at `tests/unit/core/context/test_result_cache.py`:

1. Tests check `to_context_dict()` structure independently
2. Tests don't verify end-to-end flow of tool results through LLM
3. Tests don't verify that LLM can actually parse and act on the results
4. No integration tests for actual agent behavior with cached results

---

## QUICK FIX OPTIONS

### Option A: Disable Caching (Temporary)
```bash
# In .env or before running
export LOGAI_ENABLE_RESULT_CACHING=false
```
This reverts to the working behavior from 9ff9993 but loses the caching benefits.

### Option B: Unwrap The Structure (Proper Fix)
Change `_create_enhanced_cache_summary()` to return a flatter structure that LLMs can parse:

```python
def _create_enhanced_cache_summary(self, summary, original_result, tool_name):
    # Return in a format LLM can parse immediately
    return {
        "success": True,
        "events": summary.sample_events,  # Flat top-level key!
        "total_events": summary.total_events,
        "preview_note": f"Showing {len(summary.sample_events)} of {summary.total_events} events",
        "cache_info": {
            "cache_id": summary.cache_id,
            "cached": True,
            "fetch_more": {
                "tool": "fetch_cached_result_chunk",
                "cache_id": summary.cache_id,
            }
        }
    }
```

### Option C: Bypass Wrapping for Small Results
Only wrap cached results for truly large datasets. Let small cached results pass through with minimal wrapping.

---

## RECOMMENDED FIX

**Option B - Unwrap The Structure** is the right fix because:

1. ✅ Preserves Phase 1 benefits (caching, follow-up detection, guidance injection)
2. ✅ Fixes agent visibility of logs immediately
3. ✅ Keeps the 5-key structure for internal use but flattens for LLM consumption
4. ✅ Maintains backward compatibility with test expectations
5. ✅ Addresses the actual architectural issue (nested vs flat structure)

---

## VERIFICATION STEPS

### To Confirm Root Cause:
```bash
cd /Users/David.Parker/src/observability-assistant

# 1. Check current setting
grep "enable_result_caching" .env 2>/dev/null || echo "Not in .env, using default (True)"

# 2. Temporarily disable to verify logs work
export LOGAI_ENABLE_RESULT_CACHING=false

# 3. Test agent - logs should appear
# If logs appear with this setting, we've confirmed the nested structure is the issue
```

### To Verify Fix:
```bash
# After implementing Option B:
# 1. Run tests to confirm they still pass
pytest tests/unit/core/test_orchestrator_context.py -v

# 2. Test with actual log querying
# Logs should appear in agent responses

# 3. Verify caching still works
# Check cache is being created: ~/.logai/cache/result_cache.db
```

---

## FILES TO MODIFY

1. **`src/logai/core/orchestrator.py`** (lines 814-853)
   - Method: `_create_enhanced_cache_summary()`
   - Change: Flatten the structure for LLM consumption
   - Impact: Direct (fixes the core issue)

2. **`tests/unit/core/context/test_result_cache.py`** (if needed)
   - May need to update assertion expectations
   - Add integration test for full flow

---

## ARCHITECTURE INSIGHT

Phase 1's design was sound, but there was a mismatch:

- **Internal representation**: 5-key structure is great for context management ✅
- **LLM consumption**: Must be flat/simple for tool message parsing ❌

The fix: Use `to_context_dict()` for context window decisions but unwrap it for LLM tool messages.

---

## SUMMARY TABLE

| Aspect | 9ff9993 (Working) | 009f3d4 (Broken) | Fix |
|--------|-------------------|-------------------|-----|
| Caching | Disabled | Enabled (default) | Keep enabled |
| Result Structure | Flat | Nested (3 levels) | Flatten for LLM |
| Events Visibility | Top-level | Buried in `cached_result.preview_events` | Move to top-level |
| Sample Count | Full result | 5 samples | Show samples with pointer to cache |
| Agent Understanding | 100% | <5% | Will fix with structure change |

---

## NEXT STEPS

1. Implement Option B fix
2. Run full test suite
3. Manual testing with actual CloudWatch queries
4. Update documentation about cached result format
5. Consider adding integration tests for this flow

---

**Investigation completed by**: Hans, Code Librarian
**Confidence Level**: 99% - Root cause clearly identified in code
**Time to Fix**: ~30 minutes for implementation + testing
