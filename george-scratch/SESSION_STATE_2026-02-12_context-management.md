# Session State - Context Management System

**Date:** February 12, 2026 (continued)
**TPM:** George
**Status:** 🚧 In Progress - Architecture Approved, Starting Implementation

---

## Executive Summary

Started work on a **critical production blocker**: context window overflow when large CloudWatch query results overwhelm the agent's token limits.

**Current Status:**
- ✅ Problem investigation complete (Hans)
- ✅ Requirements documented (George)
- ✅ Architecture designed (Saanvi)
- ✅ Architecture approved by user
- 🚧 Starting Phase 1 implementation (Jackie)

**Estimated Completion:** 10 days (Feb 22, 2026)

---

## Problem Statement

### The Critical Vulnerability

The system has NO protection against context window overflow:

1. **CloudWatch queries can return 1,000 events** (~500-700 KB JSON)
2. **Results dumped into context with ZERO validation**
3. **No token counting, no size limits, no truncation**
4. **History accumulates indefinitely** (all previous messages stay in context)
5. **After 2-3 large queries: CONTEXT OVERFLOW** → Agent fails

### Real-World Impact

```
User: "Find error logs"
  → Query returns 1,000 errors (600 KB added to context)

User: "Find warnings"
  → Query returns 1,000 warnings (600 KB added to context)

User: "Analyze patterns"
  → Context: 1.4 MB + system prompt + new query = OVERFLOW ✗
  → Agent fails completely
```

**User Impact:** Production blocker, can't analyze large log sets reliably

---

## Solution: Intelligent Context Management System

### Core Capabilities

1. **Token Counting** - Accurate counting with tiktoken library
2. **Budget Tracking** - Real-time monitoring and enforcement
3. **Result Caching** - Store large results outside context, provide summaries
4. **Incremental Fetch** - Agent tool to pull result chunks as needed
5. **History Management** - Sliding window with smart preservation
6. **Adaptive Allocation** - Dynamic budget allocation based on conversation state
7. **User Visibility** - Status bar showing context usage, notifications for actions

### Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Token Counting** | tiktoken library + fallback | Industry standard, 98-99% accurate, <1ms |
| **Budget Tracker** | Stateful with validation | Balance performance and accuracy |
| **Cache Storage** | Extend SQLiteStore | Reuse proven infrastructure |
| **History Pruning** | FIFO with role preservation | Simple, predictable, safe |
| **Allocation** | Adaptive only (v1) | Handles 95% of cases, defer complexity |

---

## Team Assignments

### Investigation Phase ✅ Complete

**Hans (Librarian)** - Context Window Investigation
- **Deliverable:** `investigation-context-window-limits.md` (787 lines)
- **Status:** ✅ Complete
- **Key Findings:**
  - No size validation in `orchestrator.py` lines 513-521, 761-769
  - Tools allow 1,000 events per query (500-700 KB JSON)
  - No token counting anywhere in codebase
  - Missing settings: `max_result_tokens`, `max_context_tokens`, etc.

### Requirements Phase ✅ Complete

**George (TPM)** - Requirements Documentation
- **Deliverable:** `requirements-context-management-system.md`
- **Status:** ✅ Complete
- **Scope:** 8 functional requirements, comprehensive solution
- **Timeline:** 1-2 weeks implementation
- **User Decisions:**
  - Comprehensive solution (not quick fix)
  - Cache and pull incrementally (not truncate)
  - Adaptive allocation with user control

### Architecture Phase ✅ Complete

**Saanvi (Architect)** - System Architecture Design
- **Deliverable:** `architecture-context-management-system.md` (3,344 lines!)
- **Status:** ✅ Complete, Approved
- **Quality:** Production-ready, comprehensive, implementable
- **Key Components:**
  - TokenCounter (tiktoken + fallback)
  - ContextBudgetTracker (stateful, adaptive)
  - ResultCacheManager (SQLite-based)
  - FetchCachedResultTool (agent tool)
  - HistoryManager (sliding window)

### Implementation Phase 🚧 Starting Now

**Jackie (Engineer)** - Implementation (10 days)
- **Status:** 🚧 Starting Phase 1
- **Phase 1 (Days 1-3):** TokenCounter, BudgetTracker, Settings
- **Phase 2 (Days 4-5):** ResultCacheManager, FetchTool
- **Phase 3 (Days 6-8):** Orchestrator integration, History management
- **Phase 4 (Days 9-10):** UI integration, Performance optimization

**Han-Ron (Reviewer)** - Code Review
- **Status:** ⏳ Awaiting implementation
- **Scope:** Review all context management code before merge

**Raoul (QA)** - Integration Testing
- **Status:** ⏳ Awaiting implementation
- **Scope:** End-to-end testing, stress testing, edge cases

**Tina (Writer)** - User Documentation
- **Status:** ⏳ Awaiting implementation
- **Scope:** Update user guide with context management features

---

## Implementation Roadmap

### Phase 1: Foundation (Days 1-3)

**Tasks:**
- [ ] Implement `TokenCounter` utility
  - Use tiktoken for OpenAI/Claude models
  - Character-based fallback for Ollama
  - Performance: <10ms per call

- [ ] Implement `ContextBudgetTracker`
  - Stateful tracking with validation
  - Adaptive allocation algorithm
  - Pruning decision logic

- [ ] Add context settings to `settings.py`
  - `context_window_size`, `max_result_tokens`, etc.
  - Sensible defaults for all models
  - Auto-detect limits from model name

- [ ] Write unit tests
  - TokenCounter: accuracy, performance, edge cases
  - BudgetTracker: budget enforcement, pruning logic

**Files:**
- NEW: `src/logai/core/context/__init__.py`
- NEW: `src/logai/core/context/token_counter.py`
- NEW: `src/logai/core/context/budget_tracker.py`
- MODIFIED: `src/logai/config/settings.py`
- NEW: `tests/unit/core/context/test_token_counter.py`
- NEW: `tests/unit/core/context/test_budget_tracker.py`

### Phase 2: Caching (Days 4-5)

**Tasks:**
- [ ] Implement `ResultCacheManager`
  - SQLite storage for cached results
  - TTL management (1 hour default)
  - Intelligent summary generation

- [ ] Implement `FetchCachedResultTool`
  - Agent tool for incremental fetch
  - Support offset, limit, filters
  - Error handling for expired cache

- [ ] Write unit tests
  - Cache storage/retrieval
  - Summary generation
  - TTL expiration

**Files:**
- NEW: `src/logai/core/context/result_cache.py`
- NEW: `src/logai/tools/fetch_cached_result.py`
- MODIFIED: `src/logai/cache/sqlite_store.py` (add cached_results table)
- NEW: `tests/unit/core/context/test_result_cache.py`
- NEW: `tests/unit/tools/test_fetch_cached_result.py`

### Phase 3: Integration (Days 6-8)

**Tasks:**
- [ ] Integrate BudgetTracker into orchestrator
  - Initialize tracker on startup
  - Track all messages and results
  - Enforce limits before LLM calls

- [ ] Implement history pruning
  - FIFO with role-based preservation
  - Never prune system messages or tool results
  - Preserve last 6 messages always

- [ ] Add result caching logic
  - Detect oversized results
  - Cache and replace with summary
  - Notify user when caching occurs

- [ ] Write integration tests
  - End-to-end context management
  - Large result handling
  - Multi-query conversations

**Files:**
- MODIFIED: `src/logai/core/orchestrator.py` (major changes)
- NEW: `tests/integration/test_context_management_e2e.py`

### Phase 4: Polish (Days 9-10)

**Tasks:**
- [ ] Add context usage to status bar
  - Show percentage: "Context: 45%"
  - Color coding: Green/Yellow/Red

- [ ] Add user notifications
  - Toast when result cached
  - Toast when history pruned
  - Warning when approaching limit (>80%)

- [ ] Performance optimization
  - Benchmark all operations
  - Optimize hot paths
  - Cache token counts when possible

- [ ] Final testing and documentation

**Files:**
- MODIFIED: `src/logai/ui/screens/chat.py`
- MODIFIED: `src/logai/ui/widgets/status_bar.py`

---

## Success Criteria

✅ **Complete when:**

1. **No context overflows** - System never exceeds model token limits
2. **Large results handled** - 1,000 event queries work reliably
3. **Multi-query sessions** - Users can execute 10+ queries without issues
4. **Clear visibility** - Users understand context usage and actions taken
5. **No performance hit** - <100ms latency added by context management
6. **95%+ uptime improvement** - Context overflow failures drop to near zero
7. **All tests passing** - Unit (80%+ coverage) and integration tests pass
8. **Production deployment** - Merged to main, deployed, monitored

---

## Key Documents

| Document | Location | Author | Lines | Status |
|----------|----------|--------|-------|--------|
| **Investigation Report** | `investigation-context-window-limits.md` | Hans | 787 | ✅ Complete |
| **Requirements** | `requirements-context-management-system.md` | George | 800+ | ✅ Complete |
| **Architecture** | `architecture-context-management-system.md` | Saanvi | 3,344 | ✅ Complete |
| **Implementation** | (Multiple files) | Jackie | TBD | 🚧 In Progress |
| **Code Review** | TBD | Han-Ron | TBD | ⏳ Pending |
| **QA Report** | TBD | Raoul | TBD | ⏳ Pending |
| **User Guide** | TBD | Tina | TBD | ⏳ Pending |

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **tiktoken accuracy issues** | Medium | Low | Extensive testing, fallback heuristics |
| **Performance degradation** | Medium | Medium | Strict latency budgets, benchmarking |
| **Agent confused by summaries** | High | Medium | Clear summary format, testing |
| **Cache storage fills up** | Low | Low | TTL management, size limits |
| **Breaking existing functionality** | High | Low | Comprehensive integration tests |
| **Implementation takes >10 days** | Medium | Medium | Phased approach, can deploy phases incrementally |

---

## Dependencies

### External Libraries (New)
- **tiktoken** - Token counting for OpenAI/Claude models
  - License: MIT
  - Maintained by: OpenAI
  - Version: Latest stable (0.5.x)
  - **Status:** ✅ Approved by user

### Internal Dependencies (Existing)
- `CacheManager` and `SQLiteStore` - Cache infrastructure
- `ToolRegistry` - Tool registration for FetchCachedResultTool
- `Settings` system - Configuration management
- `Orchestrator` - Core agent loop (major modifications needed)

---

## Timeline

| Phase | Days | Start | End | Status |
|-------|------|-------|-----|--------|
| **Investigation** | 1 | Feb 12 | Feb 12 | ✅ Complete |
| **Requirements** | 1 | Feb 12 | Feb 12 | ✅ Complete |
| **Architecture** | 1 | Feb 12 | Feb 12 | ✅ Complete |
| **Phase 1: Foundation** | 3 | Feb 13 | Feb 15 | 🚧 Starting |
| **Phase 2: Caching** | 2 | Feb 16 | Feb 17 | ⏳ Pending |
| **Phase 3: Integration** | 3 | Feb 18 | Feb 20 | ⏳ Pending |
| **Phase 4: Polish** | 2 | Feb 21 | Feb 22 | ⏳ Pending |
| **Code Review** | 1 | Feb 23 | Feb 23 | ⏳ Pending |
| **QA Testing** | 1 | Feb 24 | Feb 24 | ⏳ Pending |
| **Documentation** | 1 | Feb 25 | Feb 25 | ⏳ Pending |
| **Deployment** | 1 | Feb 26 | Feb 26 | ⏳ Pending |

**Total: ~14 days** (10 dev + 4 review/qa/docs)

---

## Communication Plan

### Daily Standups (with George)
- Jackie reports: What completed yesterday, what's today, any blockers
- George coordinates: dependencies, prioritization, resource allocation

### Phase Milestones
- **After Phase 1:** Demo token counting and budget tracking
- **After Phase 2:** Demo result caching and incremental fetch
- **After Phase 3:** Demo full integration with large queries
- **After Phase 4:** Demo final UI and performance

### Escalation Path
- **Blocker:** Jackie → George → User (for decisions)
- **Architecture question:** Jackie → Saanvi → George
- **Requirements clarification:** Anyone → George → User

---

## Monitoring & Metrics

### Development Metrics
- Code coverage: Target 80%+ for new code
- Performance benchmarks: All operations within budget
- Integration test pass rate: 100%

### Production Metrics (Post-Deployment)
- Context overflow rate: Should drop to <1% (from ~20%)
- Cache hit rate: Monitor effectiveness
- Average context utilization: Track over time
- Pruning frequency: Ensure not too aggressive
- User complaints: Monitor for confusion about caching

---

## Next Steps

1. **Jackie starts Phase 1 implementation** (TokenCounter + BudgetTracker)
2. **Daily check-ins with George** to track progress
3. **Saanvi available for architecture questions**
4. **User reviews progress at phase milestones**

---

**Status:** 🚧 Active Development
**Next Milestone:** Phase 1 complete (Feb 15)
**Risk Level:** Medium (complex feature, many integration points)
**Confidence:** High (excellent architecture, clear requirements)

---

*Document prepared by George, Technical Project Manager*
*Session Date: February 12, 2026*
*Status: In Progress*
