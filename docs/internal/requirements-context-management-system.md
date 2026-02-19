# Requirements: Intelligent Context Window Management System

**Date:** February 12, 2026
**TPM:** George
**Priority:** Critical
**Complexity:** High (Saanvi architecture required)
**Estimated Effort:** 1-2 weeks

---

## Executive Summary

The current system has a **critical context window overflow vulnerability**. When CloudWatch queries return large amounts of data (up to 1,000 events per query), results are serialized and stuffed directly into the agent's conversation history with no size checking, token counting, or intelligent management. After 2-3 large queries, the context window overflows and the agent fails.

**Solution:** Build a comprehensive intelligent context management system that:
1. Monitors and enforces token budgets
2. Caches large results outside the context window
3. Provides tools for the agent to fetch result chunks incrementally
4. Adapts allocation based on user preferences and conversation state
5. Prevents context overflow proactively

---

## Problem Statement

### Current Critical Issues

**From Investigation Report:** `/Users/David.Parker/src/observability-assistant/george-scratch/investigation-context-window-limits.md`

1. **No Size Validation**
   - CloudWatch tools can return up to 1,000 events (~500-700 KB JSON)
   - Results serialized with `json.dumps()` and added to history with ZERO checks
   - Location: `orchestrator.py` lines 513-521, 761-769

2. **No Token Counting**
   - System never counts tokens before sending to LLM
   - No awareness of context window limits (200K for Claude, 128K for GPT-4)
   - Location: Missing entirely from codebase

3. **Unlimited History Accumulation**
   - All previous messages remain in context indefinitely
   - Every LLM call includes ALL history (user msgs + assistant msgs + tool results)
   - No pruning, no sliding window, no summarization

4. **Missing Configuration**
   - No settings for: `max_result_size_bytes`, `max_context_tokens`, result truncation/chunking
   - Location: `settings.py` - completely missing

5. **Inevitable Overflow**
   - Real scenario: "Find errors" (600KB) → "Find warnings" (600KB) → "Analyze" (OVERFLOW)
   - Agent fails or produces incorrect/truncated results
   - User loses work and trust in the system

### User Impact

- **Frequent failures** when working with production logs (high volume)
- **Unpredictable behavior** - works for small queries, fails for large
- **Lost context** - must restart conversation, losing valuable history
- **Poor UX** - no warning, no graceful degradation
- **Production blocker** - can't reliably analyze large log sets

---

## Solution Vision

Build an **Intelligent Context Management System** with:

### Core Capabilities

1. **Token Budget Monitoring**
   - Track token usage across all context components
   - Enforce hard limits before sending to LLM
   - Provide real-time visibility into budget utilization

2. **Result Caching & Chunking**
   - Store large results in cache (not context)
   - Provide agent tools to fetch chunks incrementally
   - Agent decides what it needs based on user query

3. **Adaptive Allocation**
   - Dynamic budget allocation: system prompt / history / results / response
   - User-configurable preferences (e.g., "prefer full history" vs "prefer complete results")
   - Automatically adjust based on conversation state

4. **Proactive Prevention**
   - Detect oversized results BEFORE adding to context
   - Warn user when approaching limits
   - Graceful degradation (never crash)

5. **History Management**
   - Sliding window for old messages
   - Optional summarization of archived context
   - Preserve critical context (system prompt, recent messages)

---

## Functional Requirements

### FR-1: Token Counting Utility

**Description:** Accurate token counting for all text going to LLM.

**Requirements:**
- Implement token counter that works with all supported models:
  - Claude (cl100k_base tokenizer)
  - GPT-4 (cl100k_base tokenizer)
  - Ollama (model-specific tokenizers)
  - GitHub Copilot (uses GPT-4 tokenizer)
- Count tokens for:
  - System prompts
  - User messages
  - Assistant responses
  - Tool results (JSON)
- Utility functions:
  - `count_tokens(text: str, model: str) -> int`
  - `count_message_tokens(messages: list[dict], model: str) -> int`
  - `estimate_json_tokens(data: dict, model: str) -> int`

**Acceptance Criteria:**
- Token counts accurate within ±5% of actual model usage
- Supports all 4 LLM providers
- Fast enough for real-time checks (<10ms per call)

---

### FR-2: Context Window Configuration

**Description:** Settings to control context budget and allocation.

**Requirements:**
- Add to `settings.py`:
  ```python
  # Context Window Management
  context_window_size: int = 200000  # Model-specific, auto-detect
  context_window_buffer: int = 5000  # Safety margin
  max_result_tokens: int = 50000  # Max tokens for a single tool result
  max_history_tokens: int = 80000  # Max tokens for conversation history
  max_system_prompt_tokens: int = 10000  # Max for system prompt
  reserve_response_tokens: int = 8000  # Reserve for LLM response

  # Result Handling
  enable_result_caching: bool = True
  enable_incremental_fetch: bool = True
  cache_large_results_threshold: int = 10000  # Tokens
  max_events_per_chunk: int = 100

  # History Management
  enable_history_pruning: bool = True
  history_sliding_window_messages: int = 20  # Keep last N messages
  enable_history_summarization: bool = False  # Future feature

  # User Preferences
  context_allocation_strategy: str = "adaptive"  # adaptive, history-focused, result-focused
  ```

**Acceptance Criteria:**
- All settings documented in user guide
- Sensible defaults that work for 90% of use cases
- Auto-detect context window size from model name
- Validation on startup (e.g., allocations don't exceed window)

---

### FR-3: Result Caching System

**Description:** Cache large query results outside the context window.

**Requirements:**
- When tool result exceeds `cache_large_results_threshold`:
  1. Store full result in cache with unique ID
  2. Replace result in context with metadata summary:
     ```json
     {
       "cached": true,
       "cache_id": "result_abc123",
       "summary": {
         "total_events": 1000,
         "time_range": "2026-02-12 10:00 to 11:00",
         "sample_events": [<first 3 events>],
         "event_types": {"ERROR": 600, "WARN": 400}
       },
       "instructions": "Use fetch_cached_result(cache_id, offset, limit) to retrieve specific events"
     }
     ```
  3. Provide agent with tool to fetch chunks

- Cache storage:
  - Use existing `CacheManager` / `SQLiteStore`
  - Add new table: `cached_results`
  - TTL: 1 hour (configurable)
  - Max cache size: 100 MB (configurable)

**Acceptance Criteria:**
- Large results (>10K tokens) automatically cached
- Summary includes enough info for agent to decide what to fetch
- Cache retrieval is fast (<100ms)
- Old results auto-expire

---

### FR-4: Incremental Fetch Tool

**Description:** New agent tool to fetch chunks of cached results.

**Tool Definition:**
```python
{
  "name": "fetch_cached_result_chunk",
  "description": "Fetch a specific chunk of a previously cached large query result. Use this when you need specific log events from a cached result set.",
  "parameters": {
    "cache_id": {
      "type": "string",
      "description": "The cache ID from the cached result summary"
    },
    "offset": {
      "type": "integer",
      "description": "Starting index (0-based)",
      "default": 0
    },
    "limit": {
      "type": "integer",
      "description": "Number of events to fetch",
      "default": 100,
      "maximum": 200
    },
    "filter": {
      "type": "object",
      "description": "Optional filter to apply (e.g., event_type, time_range)",
      "required": false
    }
  }
}
```

**Behavior:**
- Fetch specified chunk from cache
- Apply optional filters
- Return events in same format as original tool
- If cache expired: return error with helpful message

**Acceptance Criteria:**
- Agent can fetch specific ranges of cached results
- Filtered fetches work correctly
- Error handling for expired/missing cache entries
- Works seamlessly with existing CloudWatch tools

---

### FR-5: Context Budget Tracker

**Description:** Real-time tracking and enforcement of token budgets.

**Component:** `ContextBudgetTracker` class

**Interface:**
```python
class ContextBudgetTracker:
    def __init__(self, settings: Settings, model: str):
        """Initialize with model-specific limits."""

    def add_system_prompt(self, prompt: str) -> bool:
        """Add system prompt, returns False if exceeds limit."""

    def add_message(self, message: dict) -> bool:
        """Add message, returns False if exceeds limit."""

    def add_tool_result(self, result: dict) -> tuple[bool, dict]:
        """
        Add tool result.
        Returns: (can_add, modified_result)
        - can_add: True if result fits
        - modified_result: May be cached summary if too large
        """

    def can_fit(self, text: str) -> bool:
        """Check if text would fit in remaining budget."""

    def get_usage(self) -> dict:
        """
        Get current usage stats.
        Returns: {
            "total_tokens": 50000,
            "system_prompt_tokens": 5000,
            "history_tokens": 30000,
            "result_tokens": 15000,
            "remaining_tokens": 100000,
            "utilization_pct": 50.0
        }
        """

    def should_prune_history(self) -> bool:
        """Check if history should be pruned."""

    def prune_oldest_messages(self, count: int) -> list[dict]:
        """Remove oldest messages, return pruned messages."""

    def reset(self):
        """Reset tracker (new conversation)."""
```

**Acceptance Criteria:**
- Accurate token tracking for all components
- Prevents context overflow (never exceeds limit)
- Provides clear visibility into usage
- Integrates with orchestrator seamlessly

---

### FR-6: Orchestrator Integration

**Description:** Integrate context management into orchestrator workflow.

**Changes to `orchestrator.py`:**

1. **Initialize tracker:**
   ```python
   def __init__(self, ...):
       self.budget_tracker = ContextBudgetTracker(
           settings=self.settings,
           model=self.settings.current_llm_model
       )
   ```

2. **Track system prompt:**
   ```python
   messages = [{"role": "system", "content": system_prompt}]
   self.budget_tracker.add_system_prompt(system_prompt)
   ```

3. **Track messages:**
   ```python
   for msg in self.conversation_history:
       if not self.budget_tracker.can_fit(msg["content"]):
           # Prune history if needed
           pruned = self.budget_tracker.prune_oldest_messages(1)
           logger.warning(f"Pruned {len(pruned)} messages from history")
       self.budget_tracker.add_message(msg)
   ```

4. **Handle tool results:**
   ```python
   for tool_result in tool_results:
       can_add, modified_result = self.budget_tracker.add_tool_result(tool_result)

       if not can_add:
           # Result was cached, use summary instead
           tool_result = modified_result

       tool_message = {
           "role": "tool",
           "tool_call_id": tool_result["tool_call_id"],
           "content": json.dumps(tool_result["result"])
       }
       self.conversation_history.append(tool_message)
       messages.append(tool_message)
   ```

5. **Pre-call validation:**
   ```python
   # Before calling LLM
   usage = self.budget_tracker.get_usage()
   if usage["utilization_pct"] > 90:
       logger.warning(f"Context window {usage['utilization_pct']:.1f}% full")
   ```

**Acceptance Criteria:**
- All tool results processed through budget tracker
- History pruned automatically when needed
- Large results automatically cached
- No breaking changes to existing functionality

---

### FR-7: User Notifications

**Description:** Inform users about context management actions.

**Requirements:**

1. **Warning When Approaching Limit**
   - When utilization > 80%: Show warning toast
   - Message: "Context window 85% full. Some history may be pruned."

2. **Notification When Result Cached**
   - When large result cached: Show info toast
   - Message: "Large query result cached (1,000 events). Agent can fetch details as needed."

3. **Notification When History Pruned**
   - When messages pruned: Show info toast
   - Message: "Pruned 3 old messages to maintain context window."

4. **Status Bar Enhancement** (Optional)
   - Add context usage to status bar: `Context: 45%`
   - Color coding: Green (<70%), Yellow (70-90%), Red (>90%)

**Acceptance Criteria:**
- Users understand what's happening
- Notifications don't interrupt workflow
- Status bar provides at-a-glance visibility

---

### FR-8: Adaptive Allocation Strategies

**Description:** Different allocation strategies based on user preference.

**Strategies:**

1. **"adaptive" (Default)**
   - Start with balanced allocation
   - Adjust based on conversation:
     - Long conversation: reduce history tokens, keep recent messages
     - Large results: allocate more to results, prune history
     - Short conversation: allow larger results

2. **"history-focused"**
   - Prioritize preserving conversation history
   - More aggressive result caching
   - Larger history budget (60% vs 40%)

3. **"result-focused"**
   - Prioritize complete tool results
   - More aggressive history pruning
   - Larger result budget (60% vs 40%)

**Configuration:**
```python
# .env
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive  # adaptive, history-focused, result-focused
```

**Acceptance Criteria:**
- All three strategies work as described
- User can switch strategies via config
- Strategy choice affects pruning decisions

---

## Non-Functional Requirements

### NFR-1: Performance

- Token counting: <10ms per call
- Cache storage: <50ms per result
- Cache retrieval: <100ms per chunk
- Budget checking: <5ms per operation
- No noticeable latency in user workflow

### NFR-2: Reliability

- Never crash due to context overflow
- Graceful degradation when limits reached
- All errors logged with context
- Recovery from cache failures (fall back to truncation)

### NFR-3: Observability

- Log all cache operations (debug level)
- Log all pruning operations (info level)
- Log all context overflows prevented (warning level)
- Metrics: cache hit rate, average context utilization, prune frequency

### NFR-4: Maintainability

- Clear separation of concerns (token counting, caching, budget tracking)
- Well-documented APIs
- Comprehensive unit tests (80%+ coverage)
- Integration tests for critical paths

### NFR-5: Extensibility

- Easy to add new allocation strategies
- Easy to add new caching backends
- Easy to add new token counting methods
- Pluggable architecture for future enhancements

---

## Technical Architecture (For Saanvi)

### Key Design Decisions Needed

1. **Token Counting Approach**
   - Use tiktoken library for OpenAI models?
   - How to handle Ollama (many different tokenizers)?
   - Caching token counts or recalculate each time?

2. **Cache Storage**
   - Extend existing SQLiteStore?
   - New table structure for cached results?
   - Indexing strategy for fast retrieval?
   - TTL management approach?

3. **Budget Tracker State**
   - Stateful (tracks all messages) or stateless (recalculates)?
   - Where does it live? (orchestrator, separate service?)
   - Thread-safe? (if async operations)

4. **History Pruning Strategy**
   - FIFO (oldest first)?
   - Keep system messages always?
   - Summarize before pruning?
   - User control over what gets pruned?

5. **Result Summary Format**
   - How much metadata to include?
   - How to sample events intelligently?
   - How to help agent understand what's available?

6. **Error Handling**
   - What if cache fails? (fall back to truncation)
   - What if token counting fails? (use conservative estimates)
   - What if all strategies fail? (hard limit, error to user)

### Components to Design

1. **Token Counter** (`src/logai/core/context/token_counter.py`)
2. **Context Budget Tracker** (`src/logai/core/context/budget_tracker.py`)
3. **Result Cache Manager** (`src/logai/core/context/result_cache.py`)
4. **Fetch Cached Result Tool** (add to `cloudwatch_tools.py`)
5. **Settings Extensions** (add to `settings.py`)
6. **Orchestrator Integration** (modify `orchestrator.py`)
7. **User Notifications** (modify `chat.py` for toasts/status)

### Files to Modify

**New Files:**
- `src/logai/core/context/__init__.py`
- `src/logai/core/context/token_counter.py`
- `src/logai/core/context/budget_tracker.py`
- `src/logai/core/context/result_cache.py`

**Modified Files:**
- `src/logai/config/settings.py` - Add context management settings
- `src/logai/core/orchestrator.py` - Integrate budget tracker
- `src/logai/tools/cloudwatch_tools.py` - Add fetch_cached_result_chunk tool
- `src/logai/cache/sqlite_store.py` - Add cached_results table
- `src/logai/ui/screens/chat.py` - Add context usage to status bar

**Test Files:**
- `tests/unit/core/context/test_token_counter.py`
- `tests/unit/core/context/test_budget_tracker.py`
- `tests/unit/core/context/test_result_cache.py`
- `tests/integration/test_context_management_e2e.py`

---

## Success Criteria

✅ **Complete when:**

1. **No context overflows** - System never exceeds model token limits
2. **Large results handled** - 1,000 event queries work reliably
3. **Multi-query conversations** - Users can execute 10+ queries without issues
4. **Clear visibility** - Users understand context usage and actions taken
5. **No performance degradation** - Token counting/caching adds <100ms latency
6. **95%+ uptime improvement** - Failures due to context overflow drop to near zero
7. **All tests passing** - Unit tests (80%+ coverage), integration tests pass
8. **Documentation complete** - Architecture doc, user guide, API reference

---

## Testing Strategy

### Unit Tests

1. **Token Counter**
   - Test accuracy across models
   - Test edge cases (empty strings, huge strings, special chars)
   - Performance benchmarks

2. **Budget Tracker**
   - Test budget enforcement
   - Test pruning logic
   - Test allocation strategies

3. **Result Cache**
   - Test caching/retrieval
   - Test TTL expiration
   - Test cache size limits

### Integration Tests

1. **End-to-End Context Management**
   - Test: User asks 5 queries, each returns 1,000 events
   - Verify: No context overflow, results cached, agent can fetch chunks
   - Verify: Conversation continues smoothly

2. **History Pruning**
   - Test: Long conversation (50 messages)
   - Verify: Old messages pruned, recent preserved

3. **Cached Result Fetching**
   - Test: Query returns 1,000 events → cached
   - Test: Agent calls fetch_cached_result_chunk
   - Verify: Correct chunk returned

### Manual Testing

1. **Stress Test**
   - Execute 10 large queries in a row
   - Verify no failures, smooth operation

2. **User Experience**
   - Verify notifications are helpful, not annoying
   - Verify status bar updates correctly

3. **Different Models**
   - Test with Claude, GPT-4, Ollama, GitHub Copilot
   - Verify token counting accurate for all

---

## Phased Implementation

### Phase 1: Foundation (Week 1, Days 1-3)
- Token counter utility
- Basic budget tracker
- Settings additions
- Unit tests

### Phase 2: Caching (Week 1, Days 4-5)
- Result cache manager
- Cache storage (extend SQLiteStore)
- fetch_cached_result_chunk tool
- Unit tests

### Phase 3: Integration (Week 2, Days 1-3)
- Orchestrator integration
- History pruning logic
- User notifications
- Integration tests

### Phase 4: Polish (Week 2, Days 4-5)
- Status bar enhancements
- Allocation strategies
- Performance optimization
- Documentation

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Token counting inaccurate | Medium | Use official tokenizers, test extensively |
| Cache storage slow | Medium | Use indexes, benchmark, optimize |
| Agent confused by cached results | High | Clear summary format, good instructions |
| History pruning loses context | High | Smart pruning (keep recent + important) |
| Performance degradation | Medium | Benchmark each component, optimize |
| Breaking changes | High | Comprehensive integration tests |

---

## Dependencies

- **tiktoken** library (for OpenAI token counting)
- Existing **CacheManager** and **SQLiteStore**
- Existing **ToolRegistry** for new tool
- Existing **Settings** system

---

## Out of Scope (Future Enhancements)

- History summarization (mentioned but not implemented in v1)
- Multi-level caching (memory + disk)
- Predictive token counting (before tool execution)
- Context compression techniques
- User-configurable pruning rules

---

## Questions for Saanvi

1. Should we use tiktoken or build our own token counter?
2. How should we handle Ollama's diverse tokenizers?
3. Should budget tracker be stateful or stateless?
4. Should we extend SQLiteStore or create separate cache?
5. How detailed should result summaries be?
6. Should we support multiple allocation strategies in v1 or just adaptive?

---

## References

- Investigation Report: `george-scratch/investigation-context-window-limits.md`
- Current Orchestrator: `src/logai/core/orchestrator.py`
- Current Settings: `src/logai/config/settings.py`
- CloudWatch Tools: `src/logai/tools/cloudwatch_tools.py`

---

**Status:** Ready for Architecture Design
**Assigned To:** Saanvi (Software Architect)
**Expected Delivery:** Architecture document in 1-2 days
**Implementation Start:** After architecture approval
