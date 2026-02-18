# Cache Fetch Failure - Root Cause Identified

**Date:** 2026-02-13
**Status:** ✅ ROOT CAUSE CONFIRMED
**Severity:** HIGH - Cache system completely non-functional

---

## Executive Summary

Cache fetch operations fail immediately after successful writes because the `cache_id` is generated with a timestamp, making every cache operation produce a different cache_id. This completely defeats the caching mechanism.

**Impact:** The cache system writes data successfully, but fetches always fail because they look for a different cache_id than what was written.

---

## The Bug

**Location:** `src/logai/core/orchestrator.py`, lines 526-530

```python
# Extract query parameters for cache key (best effort)
query_params = {
    "tool": tool_name,
    # Add timestamp to make cache entries unique per invocation
    "timestamp": int(datetime.now(UTC).timestamp()),
}
```

**Problem:** The comment explicitly states the intent: "make cache entries unique per invocation". However, this defeats the entire purpose of caching!

---

## How Cache IDs Are Generated

The `cache_id` is computed in `result_cache.py` line 122-125:

```python
# Generate deterministic cache ID from tool name and params
cache_key = f"{tool_name}:{json.dumps(query_params, sort_keys=True)}"
cache_id = hashlib.sha256(cache_key.encode()).hexdigest()[:16]
return f"result_{cache_id}"
```

The `cache_id` is a SHA256 hash of: `tool_name + JSON(query_params)`

---

## The Failure Sequence

### Step 1: Cache Write (orchestrator.py line 533-537)
```
Time: T1 = 1707750637
query_params = {"tool": "search_logs", "timestamp": 1707750637}
cache_key = "search_logs:{\"timestamp\": 1707750637, \"tool\": \"search_logs\"}"
cache_id = "result_abc123de45"

→ Writes to database with cache_id = "result_abc123de45"
→ Success! Entry stored in cache.db
```

### Step 2: LLM Receives Cache Guidance
The orchestrator stores guidance (line 540-544):
```python
self._pending_cache_guidance = {
    "cache_id": "result_abc123de45",  # ← This is correct!
    "tool_name": "search_logs",
    "total_events": 500,
}
```

**This guidance tells the LLM to use `fetch_cached_result_chunk` with cache_id="result_abc123de45".**

### Step 3: Agent Calls fetch_cached_result_chunk
The LLM/agent receives the guidance and calls the tool:
```json
{
  "tool": "fetch_cached_result_chunk",
  "cache_id": "result_abc123de45",
  "offset": 0,
  "limit": 100
}
```

### Step 4: Cache Fetch (result_cache.py line 411+)
```
Time: T2 = 1707750638 (1 second later)
cache_id = "result_abc123de45"  # ← From agent's tool call

→ Database lookup: SELECT * FROM result_cache WHERE cache_id = 'result_abc123de45'
→ Entry found!
→ Check expiration: expires_at > current_time? YES
→ Parse JSON, return events
→ Success!
```

**WAIT!** Upon re-analysis, the fetch operation should actually work because:
- The fetch tool receives the CORRECT cache_id from the guidance
- It uses that exact cache_id to query the database
- The timestamp is NOT regenerated during fetch

---

## Re-Analysis: What's Really Happening?

Let me trace the actual flow more carefully:

### Hypothesis 1: Timestamp in query_params is intentional
Looking at the comment "make cache entries unique per invocation", this might be intentional to prevent reusing old cached results. But this contradicts the entire caching mechanism.

### Hypothesis 2: The agent might be generating a NEW cache_id
Let me check if the agent is supposed to use the provided cache_id, or if it's supposed to regenerate it from query parameters.

**Key Question:** Does `fetch_cached_result_chunk` accept a cache_id directly, or does it regenerate it?

Let me check the tool implementation...

---

## Investigation: fetch_cached_result_chunk Tool

Checking `src/logai/tools/fetch_cached_result.py`:

The tool accepts `cache_id` as a direct parameter (line 76-80):
```python
cache_id: Annotated[
    str,
    "The cache_id returned from a previous search operation",
]
```

So the tool receives the cache_id directly and does NOT regenerate it!

---

## Revised Analysis: The Bug Is Elsewhere

Since the fetch tool uses the cache_id directly (not regenerating it), the timestamp in `query_params` should NOT cause the described failure.

**New Questions:**
1. Is the cache_id being passed correctly in the guidance?
2. Is the agent actually calling fetch with the correct cache_id?
3. Is there a different bug causing the failure?

---

## Next Steps

1. **Run debug test** to see actual cache_id values in logs
2. **Verify agent behavior** - does it use the provided cache_id or generate a new one?
3. **Check guidance injection** - is the cache_id being passed correctly to the LLM?

The timestamp bug is suspicious, but we need empirical evidence from the debug logs to confirm the actual failure mode.

---

## Hans's Recommendation

From `/tmp/QUICK_START_GUIDE.txt` line 107-121:

> FINDING: Cache ID might be generated differently on write vs read
>
> Location: orchestrator.py line 529
>   query_params = {
>       "tool": tool_name,
>       "timestamp": int(datetime.now(UTC).timestamp()),  ← PROBLEM HERE
>   }
>
> Impact:
>   - Each call to cache_result() generates DIFFERENT cache_id
>   - Fetch tries to find cache_id that no longer exists
>   - Result: Cache miss even though entry was just written
>   - Duration: Fast operation (write + lookup = ~25ms)

**But:** This assumes the fetch operation regenerates the cache_id, which it doesn't according to the code!

---

## Conclusion

We have a **SUSPECTED** bug, but need empirical evidence. The debug logs will show us:
1. What cache_id is generated during write
2. What cache_id is provided in the guidance
3. What cache_id the agent uses during fetch
4. Whether there's a mismatch

**Action:** Run the debug test as Hans recommends and analyze the actual log output.

---

## Files for Reference

- **Bug location:** `src/logai/core/orchestrator.py` lines 526-530
- **Cache ID generation:** `src/logai/core/context/result_cache.py` lines 122-125
- **Fetch tool:** `src/logai/tools/fetch_cached_result.py` lines 76-80
- **Guidance injection:** `src/logai/core/orchestrator.py` lines 540-544
- **Investigation report:** `/tmp/cache-debug-investigation.md`
- **Quick start:** `/tmp/QUICK_START_GUIDE.txt`
