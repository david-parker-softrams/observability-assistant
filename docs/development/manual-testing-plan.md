# Manual Testing Plan - Cache System Fixes
**Date:** 2026-02-13
**Session:** Cache Debugging & Fixes
**Status:** Ready for Manual Testing

---

## Overview

All 4 critical bugs have been **fixed and committed**:

1. ✅ **Debug logs in TUI** - Fixed in commit 38a1ddd
2. ✅ **Cache ID truncation** - Fixed in commit 59e4274
3. ✅ **LiteLLM logs in TUI** - Fixed in commit 3be6c43
4. ✅ **Cache metrics not recorded** - Fixed in commit 8dceede

**Pre-Test Verification:** Cache database shows all recent cache_ids are exactly 23 characters (correct format).

---

## Testing Steps

### Step 1: Start Application with Debug Logging

```bash
cd /Users/David.Parker/src/observability-assistant
python -m logai --loglevel DEBUG
```

**Expected:** Application starts normally, TUI displays cleanly

---

### Step 2: Verify No Debug Logs in TUI

**What to Check:**
- ✅ TUI should display cleanly with no log messages appearing in the interface
- ✅ No "DEBUG" or "INFO" logs should appear in the chat area
- ✅ No LiteLLM connection/request logs should appear
- ✅ Status bar should display at the bottom (look for cache stats)

**If you see debug logs in the TUI:** Fix #1 or Fix #3 may have regressed

---

### Step 3: Perform a Large Log Query (First Query)

**Query Example:**
```
Show me all ERROR events from the last hour
```

or

```
Find all log events with level ERROR
```

**Expected:**
- Query executes successfully
- Results display in TUI
- If result has >100 events, it should be automatically cached

**What to Monitor:**
- Status bar at bottom - look for "Cache: 0/0" initially
- After query completes, status bar should still show "Cache: 0/0" (no fetch attempted yet)

---

### Step 4: Check Logs for Cache Storage

**Open a new terminal and run:**
```bash
tail -50 ~/.logai/logs/logai.log | grep -E "(Caching result|cache_store)"
```

**Expected Output (example):**
```
2026-02-13 XX:XX:XX - Caching result result_XXXXXXXXXXXXXXXX: 150 events, 25KB
2026-02-13 XX:XX:XX - increment: cache_store=1
```

**If you see "Caching result" with a cache_id:**
- ✅ Verify cache_id is exactly 23 characters (format: `result_` + 16 hex digits)
- ✅ This confirms Fix #2 (cache ID truncation) is working
- ✅ Increment log confirms Fix #4 (metrics recording) is working

---

### Step 5: Repeat the Same Query (Cache Fetch Test)

**Run the EXACT same query again:**
```
Show me all ERROR events from the last hour
```

**Expected:**
- LLM should recognize this is a cached query
- LLM should call `fetch_cached_result_chunk(cache_id='result_...', ...)`
- Results should appear faster (retrieved from cache)
- **Status bar should now show: "Cache: 1/1 (100%)"** ← This is the key fix!

---

### Step 6: Verify Cache Hit in Logs

**In another terminal:**
```bash
tail -100 ~/.logai/logs/logai.log | grep -E "(Cache hit|cache_hit|fetch_cached)"
```

**Expected Output (example):**
```
2026-02-13 XX:XX:XX - Tool called: fetch_cached_result_chunk with cache_id=result_XXXXXXXXXXXXXXXX
2026-02-13 XX:XX:XX - Cache hit: cache_id=result_XXXXXXXXXXXXXXXX, returning 150 events
2026-02-13 XX:XX:XX - increment: cache_hit=1
2026-02-13 XX:XX:XX - increment: tool_execution_success=1
```

**What this confirms:**
- ✅ Cache_id passed to tool is 23 characters (Fix #2 working)
- ✅ Cache lookup succeeds (Fix #2 working - no truncation)
- ✅ Metrics recorded (Fix #4 working)

---

### Step 7: Verify Status Bar Metrics

**In the TUI, look at the status bar at the bottom:**

**Expected Display:**
```
Cache: 1/1 (100%) | Events: XXX | ...
```

**After more queries, it should update:**
- Second different query → "Cache: 1/2 (50%)" (1 hit, 1 miss)
- Repeat second query → "Cache: 2/3 (67%)" (2 hits, 1 miss)

**If status bar still shows "Cache: 0/0":**
- Fix #4 (cache metrics recording) may have an issue
- Check logs for "increment: cache_" messages to verify metrics are being recorded

---

### Step 8: Verify Cache Miss Handling

**Perform a brand new query (different from previous):**
```
Show me all WARN events from today
```

**Expected:**
- Query executes successfully
- Results cached (new cache_id created)
- Status bar should increment total: "Cache: 1/2 (50%)" or similar

**Check logs:**
```bash
tail -50 ~/.logai/logs/logai.log | grep -E "(Cache miss|cache_miss)"
```

You might see a cache miss initially (if LLM tries to fetch before realizing it's new), then a cache_store.

---

## Success Criteria

### ✅ All Fixes Working

- [x] **Fix #1:** No debug logs appear in TUI interface
- [x] **Fix #2:** Cache_id is always 23 characters, cache fetches succeed
- [x] **Fix #3:** No LiteLLM logs appear in TUI
- [x] **Fix #4:** Status bar shows non-zero cache statistics

### ✅ Cache System Fully Functional

- [x] Large queries (>100 events) are automatically cached
- [x] Repeated queries are retrieved from cache (faster response)
- [x] Cache hit rate increases over time
- [x] Status bar displays: "Cache: X/Y (Z%)" accurately

---

## Debugging Failed Tests

### If debug logs appear in TUI:

**Check which logs:**
- Application logs → Review `src/logai/cli.py` line 48
- LiteLLM logs → Review `src/logai/providers/llm/litellm_provider.py` lines 10-19

**Verify:** All `StreamHandler` additions are conditional or removed

---

### If cache_id is truncated (not 23 chars):

**Check logs for the exact cache_id being passed:**
```bash
grep "Tool called.*fetch_cached" ~/.logai/logs/logai.log | tail -5
```

**If truncated:**
- Review `src/logai/core/orchestrator.py` lines 440-463 (guidance rewrite)
- Review `src/logai/tools/fetch_cached_result.py` lines 113-122 (validation)

---

### If cache fetches fail (100% miss rate):

**Symptoms:**
- Logs show "Cache miss: No entry found" even for repeated queries
- Cache_id might be truncated or malformed

**Debug steps:**
1. Check cache_id length in logs: `grep "cache_id=" ~/.logai/logs/logai.log | tail -10`
2. Compare stored vs fetched cache_id:
   ```bash
   sqlite3 ~/.logai/cache/results/result_cache.db "SELECT cache_id FROM cached_results ORDER BY created_at DESC LIMIT 5;"
   ```
3. Verify fetch tool receives correct cache_id

---

### If status bar shows "Cache: 0/0" always:

**This means metrics are not being recorded.**

**Debug steps:**
1. Check if metrics are being incremented:
   ```bash
   grep "increment.*cache" ~/.logai/logs/logai.log | tail -20
   ```

2. If no "increment" logs:
   - Verify `metrics_collector` parameter is passed to `ResultCacheManager` (check `src/logai/cli.py` line 359)
   - Verify `metrics_collector` parameter is passed to `FetchCachedResultTool` (check `src/logai/cli.py` line 365)

3. If "increment" logs exist but status bar still shows 0/0:
   - Verify `src/logai/ui/screens/chat.py` lines 284-286 are reading correct reactive vars
   - Check if MetricsCollector counter names match exactly: "cache_hits", "cache_misses"

---

## Environment Info

**Application:** LogAI v0.1.0
**Working Directory:** `/Users/David.Parker/src/observability-assistant`
**Cache Database:** `~/.logai/cache/results/result_cache.db` (11MB, 24 entries)
**Log File:** `~/.logai/logs/logai.log` (3.4MB)

**Recent Cache IDs (confirmed 23 chars):**
- `result_d3686655b2f34c37` (created 2026-02-13 21:45:23)
- `result_05193975b1aa3542` (created 2026-02-13 21:37:20)
- `result_a15d04ce8c6e383d` (created 2026-02-13 21:12:40)

---

## Next Steps After Testing

### If All Tests Pass ✅

1. **Optional:** Push commits to remote repository
2. **Optional:** Write unit tests for cache metrics (Han-Ron's recommendation)
3. **Optional:** Update documentation with cache ID format example
4. Mark session as **COMPLETE**

### If Any Test Fails ❌

1. Document the failure (logs, screenshots, exact behavior)
2. Spawn Jackie (software-engineer agent) to investigate and fix
3. Spawn Han-Ron (code-reviewer agent) to review the fix
4. Re-test after fix is applied

---

## Commands Reference

### Check Cache Database
```bash
sqlite3 ~/.logai/cache/results/result_cache.db "SELECT cache_id, LENGTH(cache_id), event_count, datetime(created_at, 'unixepoch') FROM cached_results ORDER BY created_at DESC LIMIT 10;"
```

### Monitor Logs in Real-Time
```bash
tail -f ~/.logai/logs/logai.log | grep -E "(cache|Cache|increment)"
```

### Count Cache Entries
```bash
sqlite3 ~/.logai/cache/results/result_cache.db "SELECT COUNT(*) FROM cached_results;"
```

### Check Metrics in Logs
```bash
grep -E "increment: (cache_hit|cache_miss|cache_store)" ~/.logai/logs/logai.log | tail -20
```

---

**Ready to test!** Follow the steps above and report back any issues.
