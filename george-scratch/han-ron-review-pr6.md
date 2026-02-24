# Han-Ron Code Review — PR #6: feature/fix-tool-result-caching
**Reviewer:** Han-Ron
**Date:** Feb 24, 2026
**Verdict:** MERGE AFTER FIXES | Confidence: MEDIUM

---

## 🔴 BLOCKING Issues (must fix before merge)

### B1 — `_chat_complete` missing `_prune_history_if_needed()`
**File:** `src/logai/core/orchestrator.py`
`_prune_history_if_needed()` was removed from `_chat_complete` during this PR's refactor but still exists in `_chat_stream`. This means `_chat_complete` can hit the LLM with an over-budget history. It's a behavioral regression introduced by this PR.

### B2 — `_sample_events`: `remaining` tracking inconsistency
**File:** `src/logai/core/context/result_cache.py`, lines ~491–501
The error block uses `remaining -= len(sampled)` (subtracts all accumulated samples) while the warning block uses `remaining = count - len(sampled)` (recalculates). These should both use the same idiom: `remaining = count - len(sampled)`. Can cause incorrect slot allocation in edge cases.

---

## 🟡 IMPORTANT Issues (should fix before/soon after merge)

### I1 — Excessive diagnostic logging on hot paths
**File:** `src/logai/core/orchestrator.py`, ~40 occurrences
`[DIAGNOSTIC]` and `[FETCH_LOGS_DEBUG]` prefixed `logger.info` calls fire on every tool call. Downgrade to `logger.debug` or remove before merging to a long-lived branch.

### I2 — `to_context_dict()` is now dead code
**File:** `src/logai/core/context/result_cache.py`, lines 32–70
`_create_enhanced_cache_summary()` replaced `summary.to_context_dict()` but the old method is still defined and tested. Delete it or document it as testing-only to avoid two divergent dict representations.

### I3 — `enable_auto_fetch_guidance` setting is orphaned
**File:** `src/logai/config/settings.py`, line 455
The setting is no longer honored by the new `_get_follow_up_cache_injection` path. Either wire it back in or deprecate/remove it.

### I4 — `increment_fetch_count()` / `is_over_limit()` on `ActiveCacheContext` never called
**File:** `src/logai/core/orchestrator.py`, lines 60–75
The orchestrator mutates `chunks_fetched` and checks the limit inline, bypassing the dataclass helpers. Use the methods or remove them.

### I5 — `import time` inside method bodies
**File:** `src/logai/core/orchestrator.py`, lines 56, 840
`time` is a stdlib module and should be at top-of-file, not deferred inside methods.

### I6 — `_chat_complete` / `_chat_stream` 50-line diagnostic block copy-pasted
**File:** `src/logai/core/orchestrator.py`
The large diagnostic logging block is duplicated between both paths. Extract into a shared helper `_handle_tool_result_message()`.

---

## 🔵 MINOR Issues (nice to have)

### M1 — `chunk_size = 100` hardcoded in `to_context_dict()`
Use `initial_chunk_size` from settings instead of a magic literal.

### M2 — `_select_time_diverse` uses value equality (`not in`) on dicts
Could silently produce short lists with duplicate events. Prefer identity check.

### M3 — `"all"` keyword in `_should_inject_cache_guidance` too broad
Will match "that's all", "all good", etc. Consider removing or adding word-boundary matching.

### M4 — `assert` used for control flow in `_get_follow_up_cache_injection`
`assert` is stripped under `python -O`. Use a proper `if ... return None` guard.

### M5 — `_prune_history_if_needed` called after `_get_follow_up_cache_injection` in `_chat_complete`
Secondary consequence of B1.

---

## ✅ Positives

- Core bypass removal is correct and clean
- Flat enhanced summary structure is LLM-friendly
- Strengthened system prompt uses validated prompt-engineering techniques (❌/✅, 🚨, concrete examples)
- `_extract_event_statistics` confidence metadata is a nice touch
- Diverse sampling (errors/warnings priority) is a genuine improvement
- `ActiveCacheContext` dataclass is well-designed
- 910/910 tests pass
- Graceful cache failure degradation preserved

---

## Summary Table

| Severity | Count |
|---|---|
| 🔴 BLOCKING | 2 |
| 🟡 IMPORTANT | 6 |
| 🔵 MINOR | 5 |

**Recommendation:** Fix B1 + B2 (blockers) and I1–I6 (important). Minors can be follow-up issues.
