# Caching System Investigation - Comprehensive Analysis

**Investigation Date**: February 18, 2026
**Investigator**: Hans, Code Librarian
**Status**: Complete - Issues Identified and Documented

---

## Executive Summary

The user reported that "the agent was complaining that the system was caching results in a way that made it impossible for them to work with the information." This investigation has identified **multiple interconnected issues** in the caching system that can prevent the agent from effectively processing cached results.

### Key Findings:
1. **CRITICAL**: Test suite expectations don't match implementation - tests are failing
2. **CRITICAL**: Cached data structure was recently refactored but tests weren't updated
3. **MAJOR**: Cache data presentation is highly structured with mandatory instructions that may conflict with agent reasoning
4. **MAJOR**: Recent fixes for cache_id truncation show underlying LLM parsing issues
5. **MODERATE**: Multiple edge cases in cache expiration and corruption handling

---

## Part 1: The Caching Architecture

### Overview
The caching system has two main components:

#### 1. **ResultCacheManager** (`src/logai/core/context/result_cache.py`)
- Stores large tool results in SQLite database (`~/.logai/cache/result_cache.db`)
- Generates summaries for inclusion in LLM context
- Provides chunk-based retrieval of cached data
- Manages TTL, expiration, and size limits

#### 2. **FetchCachedResultTool** (`src/logai/tools/fetch_cached_result.py`)
- Tool available to the agent to retrieve cached chunks
- Parameters: cache_id, offset, limit, filter_pattern, time_start, time_end
- Returns events in batches (default 100, max 200)

### Configuration Parameters

From `src/logai/config/settings.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `enable_result_caching` | True | Enable/disable caching |
| `cache_large_results_threshold` | 10,000 tokens | When to cache results |
| `max_result_tokens` | 50,000 tokens | Force cache if single result exceeds this |
| `cache_ttl_seconds` | 86,400 (24h) | Cache entry lifetime |
| `cache_max_size_mb` | 500 MB | Max total cache size |
| `enable_auto_fetch_guidance` | True | Inject fetch instructions |
| `initial_chunk_size` | 100 events | First chunk size |
| `max_auto_chunk_fetches` | 3 | Max automatic fetches |

---

## Part 2: The Problem - Cached Data Structure Mismatch

### THE CRITICAL ISSUE: Test-Code Mismatch

Tests expect old structure but code produces new structure - **TESTS ARE FAILING**.

#### What Tests Expect (Old Structure):
```python
context_dict["summary"]["total_events"]
context_dict["summary"]["time_range"]
context_dict["summary"]["event_statistics"]
context_dict["cache_info"]["expires_in_seconds"]
context_dict["instructions"]  # Simple string
```

#### What Code Actually Returns (New Structure):
```python
context_dict["dataset"]["total_events"]
context_dict["dataset"]["time_range"]
context_dict["dataset"]["statistics"]
context_dict["cache_metadata"]["expires_in_seconds"]
context_dict["MANDATORY_ACTION"]  # Long structured instruction
context_dict["iteration_info"]  # New section
context_dict["preview_only"]  # New section
context_dict["WARNING"]  # New field at top
```

### Current Implementation Details

The `CachedResultSummary.to_context_dict()` returns 7 top-level keys with complex nesting that makes it difficult for agents to parse and understand.

---

## Part 3: Specific Issues Making Data "Impossible to Work With"

### Issue #1: Conflicting Instructions
- "WARNING" says "must fetch chunks"
- But samples and statistics are provided
- "MANDATORY_ACTION" with multiple paragraphs of guidance
- "iteration_info" with technical vocabulary
- Mixed signals confuse agents

### Issue #2: Limited and De-Emphasized Data
- Only 3 sample events (vs. max 5)
- Marked "PREVIEW ONLY" - discourages analysis
- Unreliable statistics (heuristic text search)
- Cannot perform meaningful analysis

### Issue #3: Structural Complexity
- 7 top-level keys instead of 4
- Field name changes (summary→dataset, statistics→different)
- Non-obvious terminology
- Hard for LLM to parse correctly

### Issue #4: Recent Bug Fixes Reveal Deep Issues
- Cache ID truncation (LLM couldn't extract from prose)
- Race conditions on initialization
- Corruption prevention needed (JSON corrupted somehow)
- Expiration off-by-one bugs

---

## Part 4: Broken Tests

**File**: `tests/unit/core/context/test_result_cache.py`

Tests that currently FAIL:
- Line 76: `assert context_dict["summary"]["total_events"]` → KeyError: 'summary'
- Line 80: `assert "fetch_cached_result_chunk" in context_dict["instructions"]` → No "instructions" key
- Line 100: `context_dict["cache_info"]["expires_in_seconds"]` → KeyError: 'cache_info'

**Status**: 2 of 2 CachedResultSummary tests FAIL

---

## Part 5: Specific Code Problems

### Problem #1: Sample Events Hard-Coded to 3
```python
"sample_events": self.sample_events[:3],  # Reduced from 5 to 3
```
No configuration option. Contradicts MAX_SAMPLE_EVENTS = 5.

### Problem #2: Statistics are Heuristic-Based
```python
if "ERROR" in message_upper or "EXCEPTION" in message_upper:
    stats["ERROR"] = stats.get("ERROR", 0) + 1
```
- Doesn't use actual log level fields
- False positives: "No errors found" counts as ERROR
- Agent cannot trust statistics

### Problem #3: Time Range Extraction
```python
for e in events:
    ts = e.get("timestamp")  # Only looks for "timestamp"
```
- Different AWS services use different field names
- Returns `{start: None, end: None}` if no "timestamp" key
- Agent gets incomplete information

### Problem #4: Confusing Fetch Command Format
```python
"fetch_command": f"fetch_cached_result_chunk(cache_id='{self.cache_id}', offset=0, limit=100)",
```
This appears as example text, not as actual instruction. Confusing for LLM.

---

## Part 6: Configuration Issues

### TTL Too Long
Default 24 hours for mutable CloudWatch data. Users see stale cached results without realizing it.

### Conflicting Thresholds
- `cache_large_results_threshold` = 10k tokens (when to consider caching)
- `max_result_tokens` = 50k tokens (force caching)
- Unclear to users which applies

### Chunk Size Confusion
Multiple chunk size concepts:
- `initial_chunk_size` = 100 (for first fetch)
- `max_events_per_chunk` = 100 (database config)
- Not clear to agent how many fetches needed

---

## Part 7: Root Cause Analysis

### Why Agents Say Data is "Impossible to Work With"

1. **Cognitive Load**: 7-layer JSON structure with technical jargon
2. **Conflicting Signals**: "Must fetch" but also provides data
3. **Insufficient Data**: Only 3 samples, unreliable statistics
4. **No Intelligence**: No guidance on productive fetch operations
5. **Expiration Risk**: Cache might expire during agent processing

---

## Part 8: Recommended High-Priority Fixes

### Fix #1: Update Broken Tests (IMMEDIATE)
Update `tests/unit/core/context/test_result_cache.py` to match current structure.

### Fix #2: Simplify Cached Data Structure
Reduce from 7 keys to 3-4 essential:
- cache_id, cached (bool), total_events, time_range
- Move guidance into single section
- Remove redundant "WARNING"

### Fix #3: Provide Reliable Statistics
Use structured fields or pre-computed filter counts instead of heuristic text search.

### Fix #4: Provide More Samples
Increase from 3 to 5-10 samples and make configurable.

### Fix #5: Auto-Refresh TTL
Extend expiration when chunks are fetched to prevent mid-process expiry.

---

## Part 9: Quick Configuration Fix for Users

For users reporting "impossible to work with":

```ini
LOGAI_INITIAL_CHUNK_SIZE=150              # More initial data
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=15000 # Cache less aggressively
LOGAI_CACHE_TTL_SECONDS=3600              # 1 hour instead of 24
LOGAI_LOG_LEVEL=DEBUG                     # For troubleshooting
```

---

## Summary

**Architectural Issues**:
- Test suite doesn't match implementation
- Data structure too complex for LLM parsing
- Multiple conflicting instruction layers
- Limited sample data (3 vs. 5)

**Recent Fixes Show**:
- Cache ID truncation (LLM parsing problems)
- Race conditions (concurrency issues)
- Corruption prevention (data integrity issues)
- Expiration bugs (timing issues)

**Next Steps**:
1. Fix broken tests immediately
2. Simplify cached data structure
3. Increase sample count with configuration
4. Consolidate fetch guidance
5. Make statistics more reliable

---

**Prepared By**: Hans, Code Librarian
**Date**: February 18, 2026
**Status**: Ready for TPM Review
