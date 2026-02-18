# Requirements: Fix Unnecessary Cache Lookups for Empty Results

**Date:** 2026-02-17
**Priority:** High
**Type:** Bug Fix

## Problem Statement

When a tool call (like `search_logs` or `fetch_logs`) returns **zero results** (`total_events: 0`), the system is incorrectly instructing the LLM to perform a cache lookup using `fetch_cached_result_chunk`. This creates unnecessary LLM calls and confuses the assistant because:

1. There's nothing in the cache to fetch (0 events)
2. The cache lookup returns empty results
3. The LLM wastes a turn calling a tool that will inevitably return nothing

## Current Behavior (Incorrect)

```
User: "Search for error messages in app3 ecs over the past 7 days"
↓
search_logs returns: {"total_events": 0, "cached": true, "cache_id": "result_xxx"}
↓
System injects: "MUST fetch chunks... call fetch_cached_result_chunk with cache_id=result_xxx"
↓
LLM calls: fetch_cached_result_chunk("result_xxx", 0, 100)
↓
Tool returns: {"events": [], "count": 0, "total_cached": 0}
↓
System injects: "Try alternative approaches" (retry prompt)
```

## Expected Behavior (Correct)

```
User: "Search for error messages in app3 ecs over the past 7 days"
↓
search_logs returns: {"total_events": 0, "cached": true, "cache_id": "result_xxx"}
↓
System injects: "The search returned 0 results. Try alternative approaches" (retry prompt IMMEDIATELY)
↓
LLM tries alternative: broader time range, different log group, etc.
```

## Requirements

### 1. Detection Logic
- When a tool result has `"cached": true` AND `"total_events": 0` (or `dataset.total_events == 0`), DO NOT inject cache fetch instructions
- Skip the cache fetch step entirely for empty results

### 2. System Message Injection
- **IF cached=true AND total_events > 0:** Inject "fetch chunks" instruction (current behavior)
- **IF cached=true AND total_events == 0:** Skip cache instruction, go directly to retry prompt
- **IF cached=false:** No change (current behavior works)

### 3. Affected Files
Likely location: `src/logai/core/orchestrator.py`
- Look for where system messages about cache fetching are injected
- Look for logic that decides when to tell LLM to call `fetch_cached_result_chunk`

### 4. Success Criteria
- When tool returns 0 events, LLM should NOT be instructed to fetch from cache
- LLM should immediately see the retry prompt and try alternatives
- One fewer LLM call per empty result scenario

## Example Scenarios

### Scenario 1: Empty search results
**Input:** search_logs returns `{"total_events": 0, "cached": true}`
**Expected:** No cache fetch instruction, immediate retry prompt

### Scenario 2: Non-empty search results
**Input:** search_logs returns `{"total_events": 150, "cached": true}`
**Expected:** Cache fetch instruction injected (current behavior, keep this)

### Scenario 3: Non-cached results
**Input:** fetch_logs returns `{"cached": false, "events": [...]}`
**Expected:** No cache instruction (current behavior, keep this)

## Technical Notes

- This is a logic fix in the orchestrator's result processing
- Look for where `tool_result` is checked for `"cached": true`
- Add an additional check: `and tool_result.get("dataset", {}).get("total_events", 0) > 0`
- Or check: `tool_result.get("total_events", 0) > 0`

## Out of Scope

- Changing the caching mechanism itself
- Modifying tool implementations
- Changing retry logic (just remove the wasteful cache lookup step)

## Dependencies

None - this is a standalone fix to the orchestrator logic
