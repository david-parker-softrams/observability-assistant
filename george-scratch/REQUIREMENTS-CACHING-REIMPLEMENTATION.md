# Requirements: Caching System Reimplementation

**Project:** Full Reimplementation of Result Caching System
**Date:** Feb 23, 2026
**Owner:** George (TPM)
**Architect:** Saanvi (Software Architect)

---

## Project Overview

Re-enable and improve the result caching system that was disabled in commit 9ff9993 due to a result visibility bug. The existing system has a solid foundation (861 lines of core code, extensive tests, documentation) but needs architectural fixes to properly deliver cached results to the agent without confusion.

---

## Background

### What Exists
- Complete caching infrastructure (ResultCacheManager, FetchCachedResultTool)
- Two-layer LLM guidance system (system prompt + active injection)
- 9 configuration settings
- 674+ lines of tests
- 3,500+ lines of documentation

### Why It Was Disabled
The agent couldn't properly see tool results when caching was active:
1. Tool returns large result (500+ events)
2. System caches it and returns summary (3 sample events)
3. Cache guidance tells agent to fetch more chunks
4. Agent sees summary + fetch instructions and gets confused
5. Agent responds as if no logs were received at all

### Original Success (Before Disable)
The two-layer guidance system achieved 85-90% reduction in "agent freeze" behavior where agents wouldn't automatically fetch cached data.

---

## Requirements

### FR-1: Fix Result Delivery Mechanism (CRITICAL)
**Priority:** P0 (Must Have)

The agent must be able to see and analyze tool results without confusion, even when caching is active.

**Acceptance Criteria:**
- Agent receives tool results in a format that allows immediate analysis
- Cache guidance is delivered without interfering with result visibility
- Agent understands it has data to analyze AND knows how to get more if needed
- No "agent freeze" behavior (agent ignoring results or claiming no data received)

**Current Problem:**
Cache guidance merges into system prompt BEFORE agent sees tool results, causing confusion.

**Proposed Solutions to Evaluate:**
1. **Separate Message Timing** - Deliver full result first, cache guidance after
2. **Smart Summarization** - Embed clear instructions within tool result itself
3. **Progressive Delivery** - Start with summary, escalate intervention if agent doesn't fetch

Architect should evaluate these options and recommend best approach.

### FR-2: Simplify CachedResultSummary Data Structure
**Priority:** P1 (High)

Reduce complexity of data structure returned to LLM.

**Current State:**
- 7 keys: cache_id, total_events, statistics, sample_events, tool_name, cached_at, guidance
- Too complex, confuses LLMs

**Required:**
- Simplify to 4-5 keys
- Keep essential information only
- Clear, intuitive field names
- Easy for LLM to parse and understand

**Acceptance Criteria:**
- CachedResultSummary has ≤5 keys
- All fields have clear purpose and naming
- LLM can easily extract cache_id and understand next steps

### FR-3: Improve Sample Event Quality
**Priority:** P1 (High)

Increase sample events and make count configurable.

**Current State:**
- Fixed at 3 sample events
- Investigation found 5 is better
- Not configurable

**Required:**
- Increase default to 5 sample events
- Make count configurable (new setting: `cache_sample_event_count`)
- Range: 3-10 events
- Sample selection should be intelligent (not just first N):
  - Include variety (different timestamps, different log levels if applicable)
  - Prioritize errors/warnings over info messages
  - Show time range coverage (first, middle, last)

**Acceptance Criteria:**
- Default sample count is 5
- New setting `cache_sample_event_count` in settings.py
- Sample selection uses intelligent algorithm (not just first N)
- Tests verify sample selection logic

### FR-4: Fix Statistics Calculation
**Priority:** P1 (High)

Use structured fields instead of text heuristics.

**Current State:**
- Uses regex patterns to extract statistics from text
- Unreliable with varied log formats
- Error counts, time ranges often wrong

**Required:**
- Use actual structured fields from data
- If tool returns structured data (timestamps, levels, etc.), use those
- Only fall back to heuristics if no structured data available
- Clearly document when statistics are heuristic vs. precise

**Acceptance Criteria:**
- Statistics use structured fields when available
- Heuristic fallback only when necessary
- Statistics include confidence indicator (precise vs. estimated)
- Tests verify statistics accuracy with various data formats

### FR-5: Enforce max_auto_chunk_fetches
**Priority:** P2 (Medium)

Make the setting actually enforced, not advisory.

**Current State:**
- Setting exists: `max_auto_chunk_fetches` (default: 3)
- Not enforced - agents can make unlimited fetches
- Just a suggestion in guidance text

**Required:**
- Track number of chunk fetches per cache_id per iteration
- Return error or warning when limit exceeded
- Provide clear feedback to agent about limit
- Make limit reset behavior clear (per query? per session?)

**Acceptance Criteria:**
- Orchestrator tracks chunk fetch count
- FetchCachedResultTool enforces limit
- Clear error message when limit exceeded
- Tests verify enforcement
- Documentation explains reset behavior

### FR-6: Fix Test Suite
**Priority:** P1 (High)

Update tests to match current code structure.

**Current State:**
- Test expectations don't match actual data structures
- Some tests pass but don't test the right things
- Need systematic review

**Required:**
- Review all caching-related tests
- Fix assertions to match actual code
- Ensure comprehensive coverage:
  - Result delivery mechanism
  - Data structure changes
  - Statistics calculation
  - Sample event selection
  - Limit enforcement
- Add integration tests for agent scenarios

**Acceptance Criteria:**
- All tests pass
- Tests verify actual behavior (not stale expectations)
- Coverage ≥80% for caching code
- Integration tests cover end-to-end scenarios

### FR-7: Maintain Existing Functionality
**Priority:** P0 (Must Have)

Don't break what works.

**Must Preserve:**
- ✅ Two-layer guidance system (system prompt + active injection)
- ✅ Cache ID validation (three-layer defense against truncation)
- ✅ TTL management (24-hour expiration)
- ✅ Corruption handling (validation on startup)
- ✅ Race condition fixes (lock-based initialization)
- ✅ Size management (500 MB max)
- ✅ User context preservation (no loss when injecting guidance)
- ✅ All 9 existing configuration settings
- ✅ FetchCachedResultTool capabilities (pagination, filtering)

**Acceptance Criteria:**
- All existing bug fixes remain in place
- No regressions on previously fixed issues
- All existing features still work
- Configuration settings respected

---

## Non-Functional Requirements

### NFR-1: Performance
- Caching operations should not add >100ms latency to tool execution
- Database operations should be async
- Large result summarization should be efficient

### NFR-2: Reliability
- No data loss (cache corruption must be recoverable)
- Graceful degradation (if cache fails, return full results)
- Clear error messages for debugging

### NFR-3: Maintainability
- Clean separation of concerns
- Well-documented design decisions
- Comprehensive test coverage
- Clear code comments for complex logic

### NFR-4: Backward Compatibility
- Existing cache database should work with new code (migration if needed)
- Configuration settings maintain same names/defaults
- No breaking changes to tool interface

---

## Success Criteria

### Primary Goals
1. ✅ Agent can see and analyze tool results when caching is active (no confusion)
2. ✅ Agent automatically fetches cached chunks without user prompting (≥85% success rate)
3. ✅ No "agent freeze" behavior
4. ✅ All tests pass
5. ✅ All known issues fixed

### Secondary Goals
1. ✅ Improved data structure simplicity
2. ✅ Better sample event quality
3. ✅ Accurate statistics
4. ✅ Enforced limits
5. ✅ Comprehensive documentation

### Metrics
- Agent fetch success rate: ≥85% (maintain current level)
- Test coverage: ≥80%
- Performance: <100ms overhead
- Zero regressions on fixed bugs

---

## Constraints

### Must Use Existing Infrastructure
- ResultCacheManager (can modify, but don't replace)
- FetchCachedResultTool (can modify, but don't replace)
- SQLite database (same schema or migration path)
- Existing configuration settings (can add, don't remove)

### Must Maintain Git History
- Clear commit messages explaining changes
- Preserve bug fix commits (don't squash history)
- Reference original commits when fixing

### Timeline
- Target: 2-3 days for implementation
- Day 1: Result delivery fix
- Day 2: Known issues fixes
- Day 3: Testing and polish

---

## Out of Scope

The following are NOT part of this reimplementation:

- ❌ New caching backends (Redis, Memcached) - SQLite only
- ❌ Distributed caching - single machine only
- ❌ Cache sharing between users - per-user cache only
- ❌ Result compression - store as-is
- ❌ Cache analytics dashboard - basic metrics only
- ❌ Migration to different database schema - maintain current schema or simple migration
- ❌ New tools beyond FetchCachedResultTool

---

## Reference Documentation

### Must Read
1. `george-scratch/CACHING_REIMPLEMENTATION_INVESTIGATION.md` - Hans's complete investigation
2. `docs/internal/requirements-cached-result-agent-guidance.md` - Original requirements
3. `docs/architecture/design-cache-llm.md` - Architectural design (DRAFT)

### Important Code Files
1. `src/logai/core/context/result_cache.py` - Core caching (861 lines)
2. `src/logai/tools/fetch_cached_result.py` - Fetch tool (200+ lines)
3. `src/logai/core/orchestrator.py` (lines 284-300, 433-457) - Integration

### Critical Bug Fixes to Preserve
1. Commit 59e4274 - Cache ID truncation defense
2. Commit 620defd - User context preservation
3. Commit 81767b4 - Race condition fix
4. Commit c7103b2 - Corruption handling
5. Commit b0b8ad7 - TTL off-by-one fix

---

## Architecture Task

**Saanvi (Software Architect):** Please review this requirements document and all reference documentation, then create a comprehensive design plan that:

1. **Evaluates result delivery options** (Separate Timing vs. Smart Summarization vs. Progressive)
2. **Proposes data structure changes** (which keys to keep/remove/rename)
3. **Designs sample event selection algorithm** (intelligent sampling)
4. **Designs statistics calculation approach** (structured fields with fallback)
5. **Designs chunk fetch limit enforcement** (tracking mechanism, reset behavior)
6. **Creates implementation plan** (phases, file changes, test plan)
7. **Identifies risks** (what could go wrong, mitigation)
8. **Provides timeline estimate** (detailed task breakdown)

Document should include:
- Architecture diagrams (message flow, data flow)
- API/interface changes (if any)
- Database schema changes (if any)
- Configuration changes (new settings)
- Migration plan (if needed)
- Testing strategy
- Rollback plan (if implementation fails)

**Deliverable:** Design document in `george-scratch/DESIGN-CACHING-REIMPLEMENTATION.md`

---

**Questions?** Ask George (TPM) for clarification before starting design work.

---

**Document Status:** ✅ Complete - Ready for Architect Review
**Created:** Feb 23, 2026
**Author:** George (TPM)
