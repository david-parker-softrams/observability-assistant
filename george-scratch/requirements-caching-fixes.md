# Requirements: Caching System Fixes

**Date**: February 18, 2026
**Author**: George (TPM)
**Priority**: High
**Context**: Hans's investigation identified multiple issues making cached data "impossible to work with" for agents

---

## Problem Statement

Agents report that cached CloudWatch results are structured in a way that makes them difficult to work with. Root causes include:
1. Broken test suite (tests expect old structure, code uses new structure)
2. Overly complex data structure (7 top-level keys with 3 levels of nesting)
3. Conflicting instructions (WARNING, MANDATORY_ACTION, iteration_info all giving different guidance)
4. Limited sample data (only 3 events when max is 5)
5. Unreliable statistics (text heuristics instead of structured fields)

---

## Success Criteria

✅ All tests pass without modification to test logic (update expectations only)
✅ Cached data structure is simplified and easy for LLM to parse
✅ Sample event count is increased and configurable
✅ Statistics are reliable and trustworthy
✅ No regressions in existing functionality

---

## Requirements

### REQ-1: Fix Broken Tests [HIGH PRIORITY]
**File**: `tests/unit/core/context/test_result_cache.py`

**Current State**:
- Tests expect `context_dict["summary"]["total_events"]`
- Code returns `context_dict["dataset"]["total_events"]`
- 2 tests failing in `TestCachedResultSummary` class (lines 55-104)

**Requirements**:
- Update test expectations to match current data structure
- Do NOT change code structure - only update tests
- All tests in `test_result_cache.py` must pass
- Maintain test coverage and assertions

**Acceptance Criteria**:
```bash
pytest tests/unit/core/context/test_result_cache.py -v
# Result: All tests PASS
```

---

### REQ-2: Simplify Cached Data Structure [HIGH PRIORITY]
**File**: `src/logai/core/context/result_cache.py`

**Current State**:
```python
{
    "WARNING": "...",           # Redundant with MANDATORY_ACTION
    "cached": true,
    "cache_id": "...",
    "dataset": {...},           # Was "summary" in old version
    "iteration_info": {...},    # Technical jargon
    "preview_only": {...},      # De-emphasizes samples
    "MANDATORY_ACTION": "...",  # Long instruction block
    "cache_metadata": {...}     # Was "cache_info" in old version
}
```

**Requirements**:
1. **Reduce top-level keys from 7 to 4-5 maximum**
2. **Consolidate instruction fields into single "guidance" section**
   - Merge WARNING, MANDATORY_ACTION, iteration_info
   - Single clear instruction set
   - No conflicting messages
3. **Use consistent, clear field names**
   - Keep "cache_id", "cached" (simple boolean)
   - Use "summary" instead of "dataset" (more intuitive)
   - Use "metadata" instead of "cache_metadata"
4. **Simplify instruction language**
   - Remove redundant warnings
   - Clear when to fetch vs. analyze
   - Conversational tone, not ALL CAPS

**Proposed Structure**:
```python
{
    "cached": true,
    "cache_id": "result_abc123...",
    "summary": {
        "total_events": 5000,
        "time_range": {"start": "...", "end": "..."},
        "statistics": {"ERROR": 100, "WARN": 200, "INFO": 4700},
        "sample_events": [...]  # 5-10 samples
    },
    "metadata": {
        "expires_in_seconds": 85000,
        "cached_at": "2026-02-18T10:00:00Z"
    },
    "guidance": "This is a summary of cached results. Use fetch_cached_result_chunk() to retrieve specific events..."
}
```

**Acceptance Criteria**:
- Maximum 5 top-level keys
- Single instruction field (not 3)
- No ALL CAPS field names
- Clear, non-conflicting guidance
- Backward compatible with fetch tool

---

### REQ-3: Increase Sample Event Count [HIGH PRIORITY]
**File**: `src/logai/core/context/result_cache.py`

**Current State**:
- Hard-coded to 3 samples: `self.sample_events[:3]`
- MAX_SAMPLE_EVENTS constant = 5 (not used)
- No configuration option

**Requirements**:
1. **Change default from 3 to 5 samples**
2. **Add configuration setting**:
   ```python
   # In settings.py
   cache_sample_event_count: int = 5  # Range: 3-10
   ```
3. **Use MIN(configured_value, MAX_SAMPLE_EVENTS, len(sample_events))**
4. **Update validation to enforce range 3-10**

**Acceptance Criteria**:
- Default returns 5 samples (not 3)
- Configurable via environment variable `LOGAI_CACHE_SAMPLE_EVENT_COUNT`
- Respects MAX_SAMPLE_EVENTS constant
- Configuration validated (3-10 range)

---

### REQ-4: Fix Statistics Calculation [MEDIUM PRIORITY]
**File**: `src/logai/core/context/result_cache.py` (lines 225-255)

**Current State**:
```python
if "ERROR" in message_upper or "EXCEPTION" in message_upper:
    stats["ERROR"] = stats.get("ERROR", 0) + 1
```
- Text heuristics (searching message content)
- False positives: "No errors found" counts as ERROR
- Doesn't use actual log level fields

**Requirements**:
1. **Use structured log level fields first**
   - Check for `level`, `log_level`, `severity` fields
   - Only fall back to text heuristics if no field found
2. **Fix false positives**
   - Don't count "ERROR" in message if level is "INFO"
   - More intelligent text analysis
3. **Add field name detection**
   - Sample first few events to detect log level field name
   - Use detected field for all events
4. **Document limitations**
   - Make it clear when using heuristics vs. structured data

**Proposed Logic**:
```python
def _generate_statistics(events):
    # 1. Detect log level field name
    level_field = _detect_level_field(events[:10])

    # 2. Use structured field if available
    if level_field:
        return _count_by_field(events, level_field)

    # 3. Fall back to improved text heuristics
    return _count_by_text_heuristics(events)
```

**Acceptance Criteria**:
- Uses structured fields when available
- No false positives from message text
- Falls back gracefully to heuristics
- Statistics are reliable and trustworthy
- Agent can make decisions based on statistics

---

## Implementation Notes

### Order of Implementation
1. **REQ-1 (Fix Tests)** - 30 minutes - Unblocks testing
2. **REQ-3 (Sample Count)** - 1 hour - Easy win, high impact
3. **REQ-2 (Simplify Structure)** - 2 hours - Core fix
4. **REQ-4 (Statistics)** - 2 hours - Quality improvement

**Total Estimated Time**: ~5-6 hours

### Testing Strategy
1. Run unit tests after each requirement
2. Integration test with real CloudWatch data
3. Test with agent to verify "impossible to work with" is resolved
4. Regression test existing caching functionality

### Backward Compatibility
- Fetch tool must still work with new structure
- Configuration changes should have sensible defaults
- Existing cached entries should still be readable (or expire naturally)

---

## Files to Modify

**Primary**:
- `src/logai/core/context/result_cache.py` - Main implementation
- `src/logai/config/settings.py` - Add sample count config
- `src/logai/config/validation.py` - Add sample count validation
- `tests/unit/core/context/test_result_cache.py` - Fix expectations

**Secondary** (if needed):
- `src/logai/tools/fetch_cached_result.py` - Verify compatibility
- `src/logai/core/orchestrator.py` - Verify cache injection

---

## Non-Requirements (Out of Scope)

❌ Auto-refresh TTL on fetch - defer to future sprint
❌ Pre-compute filter statistics - defer to future sprint
❌ Chunk count estimation - defer to future sprint
❌ Per-entry-type TTL configuration - defer to future sprint

---

## Risks and Mitigation

**Risk**: Breaking existing cache entries
**Mitigation**: Version the cache format, or let old entries expire naturally (24h TTL)

**Risk**: Agent still confused by structure
**Mitigation**: Test with actual agent before marking complete

**Risk**: Statistics still unreliable
**Mitigation**: Document when using heuristics vs. structured data

---

## Definition of Done

✅ All 4 requirements implemented
✅ All tests pass (including fixed ones)
✅ Code reviewed by Han-Ron
✅ Integration tested with real CloudWatch data
✅ Agent can successfully work with cached results
✅ No regressions in existing functionality
✅ Documentation updated (inline comments)

---

**Next Steps**: George delegates to Jackie for implementation
