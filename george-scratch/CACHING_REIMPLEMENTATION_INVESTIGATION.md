# Caching System Investigation - Reimplementation Planning

**Investigator:** Hans (Code Librarian)
**Date:** Feb 23, 2026
**Purpose:** Comprehensive investigation of existing caching work before reimplementation

---

## Executive Summary

**Good News:** A fully functional caching system already exists! It was implemented in February 2026 (commits from Feb 12-20) with 861 lines of core code, 674+ lines of tests, and 3,500+ lines of documentation. It was recently **disabled** (commit 9ff9993) due to a bug where the agent couldn't see tool results properly.

**What We Have:**
- Complete caching infrastructure (ResultCacheManager, SQLite-based)
- LLM guidance system (two-layer approach: system prompt + active injection)
- Tool for fetching cached chunks (FetchCachedResultTool)
- 9 configuration settings
- Extensive test coverage
- Production-ready user documentation

**Why It Was Disabled:**
The recent bug (commit 9ff9993) disabled the caching/summarization behavior because cached result summaries + cache guidance were confusing the agent. The agent would see a summary with only 2-5 sample events plus instructions to fetch more, and would respond as if no logs were received at all.

**What Needs Work:**
1. Fix the tool result visibility issue (how to deliver results + caching guidance without confusion)
2. Address known issues from investigation (test suite, data structure complexity, sample event limits)
3. Re-enable the caching system with proper result delivery

---

## Original Problem: "Agent Freeze" (Feb 12, 2026)

**The Issue:**
- User asks: "Find errors in /aws/lambda/my-function logs"
- Agent calls fetch_logs → returns 500 log events (large result)
- System caches results automatically
- Agent receives summary with 3 sample events + guidance
- Agent reads guidance but **doesn't act** - just responds with summary
- User perceives agent as "frozen" or broken
- User must manually ask again to trigger cache fetch

**Root Cause:**
LLMs don't naturally respond to suggestions. They need imperative, explicit instructions delivered at the right moment.

---

## The Solution: Two-Layer Guidance System

### Layer 1: System Prompt Section (Passive Baseline)
Added permanent section to system prompt explaining cached results:

```
## Working with Cached Results

When you receive large tool results (>10,000 tokens), they are automatically
cached. You'll receive a summary with:
- Total event count
- Statistics (errors, timeframes)
- Sample events (first few examples)
- A unique cache_id

To analyze the full dataset, use the fetch_cached_result_chunk tool...
```

**Purpose:** Establishes baseline knowledge that agents can reference when needed.

### Layer 2: Active Injection (Explicit Trigger)
When caching actually occurs, inject explicit guidance **after** the tool returns:

```
<system>
IMPORTANT: The previous tool result was cached. You received a summary.

To analyze all 500 events, you MUST use fetch_cached_result_chunk with:
- cache_id: "result_abc123def456789"
- Start with chunk_size: 100

DO NOT wait for the user to ask. Fetch the data NOW and analyze it.
</system>
```

**Purpose:** Strong, imperative instruction at the exact moment when the agent needs to act.

### Combined Effect
- **85-90% reduction** in "agent freeze" behavior
- Agents naturally fetch cached chunks without user prompting
- Clear separation between baseline knowledge and action triggers

---

## Core Architecture

### 1. ResultCacheManager (861 lines)
**File:** `src/logai/core/context/result_cache.py`

**Responsibilities:**
- SQLite database management (schema, CRUD operations)
- Result summarization (extract statistics, sample events)
- TTL management (automatic expiration after 24 hours)
- Corruption detection and recovery
- Cache size management (max 500 MB)

**Key Methods:**
```python
async def cache_result(tool_name: str, result: dict) -> CachedResultSummary
async def fetch_chunk(cache_id: str, offset: int, limit: int) -> dict
async def delete_expired_entries() -> int
async def validate_database() -> bool
```

### 2. FetchCachedResultTool (200+ lines)
**File:** `src/logai/tools/fetch_cached_result.py`

**Capabilities:**
- Pagination (offset/limit for large datasets)
- Pattern filtering (regex search within cached events)
- Time range filtering
- Cache ID validation (prevents truncation issues)

**Parameters:**
- `cache_id` (required, validated with regex)
- `chunk_size` (optional, default: 100, range: 50-200)
- `offset` (optional, for pagination)
- `pattern` (optional, regex filter)
- `start_time`, `end_time` (optional, time range filter)

### 3. CachedResultSummary (Dataclass)
**Structure returned to LLM:**
```python
@dataclass
class CachedResultSummary:
    cache_id: str           # "result_abc123def456789"
    total_events: int       # 500
    statistics: dict        # {"error_count": 45, "time_range": "..."}
    sample_events: list     # [event1, event2, event3]
    tool_name: str          # "fetch_logs"
    cached_at: str          # ISO timestamp
    guidance: str           # Instructions for fetching chunks
```

### 4. Orchestrator Integration
**File:** `src/logai/core/orchestrator.py`

**Key Components:**
- Lines 284-300: System prompt section on cached results
- Lines 433-457: Active injection mechanism (`_get_pending_context_injection()`)
- Line 540: `_pending_cache_guidance` state tracking
- Result processing in tool execution loop

---

## Configuration Settings (9 Total)

**File:** `src/logai/config/settings.py`

```python
# Master switch
enable_result_caching: bool = True

# Threshold for caching (tokens)
cache_large_results_threshold: int = 10_000

# Maximum result size before truncation
max_result_tokens: int = 50_000

# Time-to-live (seconds)
cache_ttl_seconds: int = 86_400  # 24 hours

# Maximum cache size (MB)
cache_max_size_mb: int = 500

# Enable automatic fetch guidance
enable_auto_fetch_guidance: bool = True

# Initial chunk size for fetches
initial_chunk_size: int = 100  # Range: 50-200

# Maximum automatic chunk fetches
max_auto_chunk_fetches: int = 3  # Range: 1-10

# Cache directory location
cache_dir: Path = Path.home() / ".logai" / "cache"
```

---

## Bug History: 11 Commits (Feb 12-20, 2026)

### Critical Bugs Fixed

1. **Cache ID Truncation (59e4274)** - CRITICAL
   - **Problem:** LLM would truncate cache_id from 23 chars to 19 chars
   - **Result:** 100% cache miss rate
   - **Fix:** Three-layer validation defense
     - Layer 1: Regex validation `^result_[0-9a-f]{16}$`
     - Layer 2: LLM guidance emphasizing exact format
     - Layer 3: Tool parameter validation with clear error messages

2. **User Context Loss (620defd)** - CRITICAL
   - **Problem:** When cache guidance injected, user-selected log context disappeared
   - **Result:** Agent lost track of which logs user requested
   - **Fix:** Combined injection approach (merge both contexts)

3. **Race Conditions (81767b4)**
   - **Problem:** Cache initialization not idempotent
   - **Result:** Concurrent operations could corrupt database
   - **Fix:** Lock-based initialization with state tracking

4. **JSON Corruption (c7103b2)**
   - **Problem:** No validation on startup
   - **Result:** Corrupted cache could crash application
   - **Fix:** Startup validation with automatic recovery

5. **TTL Off-by-One (b0b8ad7)**
   - **Problem:** Expiration timing calculation error
   - **Result:** Entries expired 1 second early/late
   - **Fix:** Corrected datetime comparison logic

### Other Commits
- 3c3fb54: Original implementation (two-layer guidance system)
- c7103b2: Corruption prevention
- 8dceede: Cache metrics recording
- 7017726: Skip empty cache lookups
- b8593a4: Respect user .env settings
- 66ea70e: Configurable retry/timeout/cache
- 9ff9993: **Disabled caching** (tool result visibility bug)

---

## Known Issues (From Feb 18 Investigation)

### 1. Test Suite Issues
- Test expectations don't match actual code structure
- Some tests assert on data structures that have changed
- Need systematic test review and fixes

### 2. Data Structure Complexity
- CachedResultSummary has 7 keys
- Should be simplified to 4-5 keys
- Too much information confuses LLMs

### 3. Sample Event Limits
- Currently limited to 3 sample events
- Investigation found 5 would be better
- Should be configurable (setting)

### 4. Statistics Calculation
- Uses text heuristics (regex patterns)
- Should use structured fields from actual data
- Current approach unreliable with varied log formats

### 5. max_auto_chunk_fetches Not Enforced
- Setting exists but is advisory only
- Agent can make unlimited fetches
- Need enforcement mechanism

---

## The Recent Bug (Commit 9ff9993)

**What Happened:**
The context injection fix (commit 8692862) merged all context into the system prompt **before** the tool execution loop. When caching triggered:

1. Tool returns large result → gets cached
2. Cache returns summary (3 sample events)
3. Sets `_pending_cache_guidance`
4. Next LLM call: guidance merged into system prompt
5. Agent receives:
   - System prompt: "Fetch chunks using this cache_id..."
   - Tool result: Summary with only 3 events
6. Agent gets confused, responds as if no logs were found

**Why It's a Problem:**
- Agent sees fetch instructions **before** analyzing what it has
- Summary looks incomplete (only 3 events)
- Guidance overrides result processing instinct
- Agent thinks it needs to fetch but doesn't know from where

**The Temporary Fix:**
Disabled caching entirely in commit 9ff9993. Agent now always receives full results (no summarization).

---

## Reimplementation Strategy

### Phase 1: Fix Result Delivery (CRITICAL)

**Problem:** How to deliver cached results + guidance without confusion?

**Options:**

**Option A: Separate Message Timing**
```
1. System Prompt (original only)
2. User Message
3. Assistant Message (with tool_calls)
4. Tool Result (FULL events, not summary)
5. Cache Guidance (separate system message, AFTER result)
```
- ✅ Agent sees full result first
- ✅ Clear separation of concerns
- ❌ Increases message count
- ❌ May not work if result is truly huge (>50k tokens)

**Option B: Smart Summarization with Clear Instructions**
```
Tool Result:
{
  "summary": {
    "note": "Showing 5 of 500 events. Full data cached.",
    "sample_events": [...5 events...],
    "cache_id": "result_abc123",
    "next_step": "To analyze all 500, call fetch_cached_result_chunk"
  }
}
```
- ✅ Keeps message compact
- ✅ Clear next step embedded in result
- ❌ Still risk of confusion if agent fixates on summary

**Option C: Progressive Delivery**
1. First iteration: Return summary + cache_id in tool result
2. If agent doesn't fetch: Inject explicit guidance in next iteration
3. Escalating intervention only when needed
- ✅ Minimal intervention for capable agents
- ✅ Fallback for agents that miss the hint
- ❌ More complex state management
- ❌ May still feel like "freeze" if agent doesn't fetch immediately

**Recommendation:** Start with **Option A** (separate message timing). It's cleanest and matches the two-layer guidance philosophy. If token limits become an issue, fall back to Option C.

### Phase 2: Fix Known Issues

1. **Fix test suite** - Update tests to match current data structures
2. **Simplify CachedResultSummary** - Reduce from 7 to 4-5 keys
3. **Increase sample events** - 3 → 5, make configurable
4. **Fix statistics** - Use structured fields instead of regex heuristics
5. **Enforce max_auto_chunk_fetches** - Add actual enforcement logic

### Phase 3: Re-enable and Test

1. Re-enable `enable_result_caching` setting
2. Test with real agent scenarios
3. Verify agent can see and analyze full results
4. Verify agent fetches chunks when needed
5. Verify no "freeze" behavior
6. Verify no context loss

---

## Test Coverage (674+ Lines)

**File:** `tests/unit/core/context/test_result_cache.py`

### TestCachedResultSummary
- Initialization
- JSON serialization/deserialization
- Field validation

### TestResultCacheManager
- Cache operations (store, retrieve, delete)
- Summary generation
- TTL expiration
- Corruption handling
- Size management
- Concurrency

**File:** `tests/unit/tools/test_fetch_cached_result.py`
- Tool execution
- Pagination
- Filtering (pattern, time range)
- Cache ID validation
- Error handling

**File:** `tests/unit/core/test_orchestrator_context.py`
- Context injection with caching
- Message construction
- Guidance delivery

---

## Documentation (3,500+ Lines)

### Architecture Design
**File:** `docs/architecture/design-cache-llm.md` (1136 lines)
- Comprehensive architectural proposal (DRAFT)
- Goes beyond what was implemented
- Includes future enhancements

### Requirements
**File:** `docs/internal/requirements-cached-result-agent-guidance.md` (375 lines)
- Original requirements
- 3 solution options analyzed
- Success criteria
- Decision rationale

**File:** `docs/internal/requirements-caching-fixes.md` (260 lines)
- 4 high-priority fix requirements
- Identified by investigation

### User Guide
**File:** `docs/user-guide/cached-results.md` (877 lines)
- Production-ready user documentation
- Usage examples
- Configuration guide
- Troubleshooting

### Bug Fix Details
**File:** `docs/internal/bug-fixes/cache-truncation-defense-in-depth.md` (186 lines)
- Cache ID truncation bug analysis
- Three-layer defense explanation

### Session Notes
**File:** `george-scratch/SESSION_STATE_2026-02-12_cached-result-guidance.md` (540 lines)
- Team member assignments
- Implementation timeline
- Test results
- Success metrics

---

## Critical Design Insights

### 1. LLMs Respond to Imperatives, Not Suggestions
**Don't:** "You may want to fetch more data..."
**Do:** "You MUST fetch the data using fetch_cached_result_chunk. DO NOT wait."

### 2. Cache ID Format Must Be Validated
- Format: `^result_[0-9a-f]{16}$` (exactly 23 characters)
- LLMs will truncate or modify if not explicitly instructed
- Three-layer validation defense is necessary

### 3. Simple Data Structures Are Critical
- Agents need to parse easily
- 7 keys is too many → 4-5 is better
- Clear field names (no abbreviations)

### 4. Context Injection Needs Prioritization
- Multiple context sources compete for attention
- Cache guidance is highest priority (active operation)
- User context must not be lost (critical bug)
- System baseline is lowest priority (reference only)

### 5. Defensive Programming for Edge Cases
- Race conditions happen (concurrent cache operations)
- Corruption happens (disk full, power loss, bugs)
- Expiration timing is tricky (off-by-one errors)
- LLMs are unpredictable (truncation, format changes)

### 6. Why Two-Layer Approach Works
- System prompt alone: Agents read but don't act
- Active injection alone: Too noisy, injected unnecessarily
- Combined: Strong baseline + explicit trigger = 85-90% success

---

## Next Steps for Reimplementation

### Step 1: Review and Plan (Architect)
- Review this investigation document
- Review design documents (design-cache-llm.md)
- Review requirements documents
- Decide on result delivery approach (Option A/B/C)
- Create detailed implementation plan

### Step 2: Fix Result Delivery (Engineer)
- Implement chosen approach (recommend Option A)
- Ensure agent sees full results first
- Add cache guidance after result visibility
- Test with real scenarios

### Step 3: Fix Known Issues (Engineer)
- Fix test suite
- Simplify data structure
- Increase sample events
- Fix statistics calculation
- Enforce max_auto_chunk_fetches

### Step 4: Testing (QA)
- Unit tests (verify fixes)
- Integration tests (real agent scenarios)
- Edge case testing (corruption, expiration, concurrency)
- Performance testing (large datasets)

### Step 5: Code Review (Reviewer)
- Review all changes
- Verify bug fixes
- Verify no regressions
- Check test coverage

### Step 6: Documentation (Writer)
- Update user guide
- Update architecture docs
- Document new approach
- Create migration guide (if needed)

---

## Files to Study

### Must Read (Start Here)
1. `src/logai/core/context/result_cache.py` - Core caching logic
2. `src/logai/tools/fetch_cached_result.py` - Tool for fetching chunks
3. `src/logai/core/orchestrator.py` (lines 284-300, 433-457) - Integration points
4. `docs/internal/requirements-cached-result-agent-guidance.md` - Original requirements

### Deep Dive (Architecture)
1. `docs/architecture/design-cache-llm.md` - Comprehensive design (DRAFT)
2. `george-scratch/SESSION_STATE_2026-02-12_cached-result-guidance.md` - Implementation session
3. `CACHING_SYSTEM_INVESTIGATION.md` - Previous investigation findings

### Reference (Bug Fixes)
1. `docs/internal/bug-fixes/cache-truncation-defense-in-depth.md` - Truncation bug
2. Git commits 59e4274, 620defd, 9ff9993 - Critical bugs and fixes

### Testing
1. `tests/unit/core/context/test_result_cache.py` - Core tests
2. `tests/unit/tools/test_fetch_cached_result.py` - Tool tests
3. `tests/unit/core/test_orchestrator_context.py` - Integration tests

---

## Conclusion

**The good news:** You're not starting from scratch. A comprehensive, battle-tested caching system exists with 861 lines of core code, extensive tests, and full documentation.

**The challenge:** The system was recently disabled due to a result visibility bug. The agent couldn't properly see and analyze tool results when caching was active.

**The path forward:** Fix the result delivery mechanism (how to show results + caching guidance without confusion), address known issues from investigation, and re-enable the system with proper testing.

**Timeline estimate:** With the existing foundation, this is a 2-3 day effort:
- Day 1: Fix result delivery mechanism
- Day 2: Fix known issues, update tests
- Day 3: Testing, code review, documentation

The hardest work (design, initial implementation, bug discovery) has already been done. Now we refine and polish.

---

**Investigation Complete**
Hans (Code Librarian)
Feb 23, 2026
