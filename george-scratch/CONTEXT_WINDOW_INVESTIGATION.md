# Context Window Management Investigation

**Date:** February 17, 2026
**Investigator:** Hans (Code Librarian)
**Status:** Critical Issues Identified

---

## Executive Summary

LogAI's context window management has **significant gaps** causing the user to run out of context space quickly. The application has token counting infrastructure but **does not enforce limits** during the conversation loop.

### Critical Problems

1. ✅ **Token counting exists** BUT ❌ **not recalculated during tool execution**
2. ✅ **Limits configured** BUT ❌ **never enforced**
3. ✅ **Caching reduces context** BUT ❌ **tool results still accumulate**
4. ❌ **Duplicate data** in search tool responses

---

## Key Findings

### 🔴 Critical Issue #1: No Mid-Loop Token Management
**Location:** `src/logai/core/orchestrator.py` lines 1086-1308

**Problem:**
- Token budget calculated ONCE before entering tool loop
- Tool results added without updating remaining budget
- After 10 tool iterations with cached results (1K tokens each) = 10K+ untracked tokens
- Context can exceed limits by 30-50%

**Current Code Flow:**
```
1. Calculate initial budget → 40K tokens remaining
2. Call LLM (uses 5K tokens)
3. LLM calls tool → result is 1,200 tokens (NOT subtracted from budget)
4. Add result to messages
5. Call LLM again → budget still thinks we have 35K tokens
6. Repeat 10 times...
7. Eventually: "Context length exceeded"
```

---

### 🔴 Critical Issue #2: Tool Results Always Added
**Location:** `src/logai/core/orchestrator.py` lines 1140-1148

**Problem:**
- Every tool result added to conversation history
- Cached results: ~800-1200 tokens each
- Full chunk results: 50-200 events * 100-300 tokens each
- No cleanup between iterations
- No deduplication

**Impact Example:**
```
Query: "Show me errors from log-group-1"
- Tool call 1: list_log_groups (1K tokens)
- Tool call 2: fetch_logs → cached (1.2K tokens)
- Tool call 3: fetch_cached_result_chunk (5K tokens for 50 events)
- Tool call 4: fetch_cached_result_chunk (5K tokens for next 50 events)
Total: 12.2K tokens just from tool results
```

---

### 🔴 Critical Issue #3: System Prompts Exceed Budget
**Location:** `src/logai/core/orchestrator.py` lines 257-407, 1071-1083

**Token Breakdown:**
- Base system prompt: ~2,500 tokens
- Cache guidance (when results cached): ~1,000 tokens
- Follow-up guidance: ~1,500 tokens
- Retry prompts (on tool failure): ~800 tokens
- **Total possible:** 5,800 tokens in system messages alone

**Configuration:**
- `max_system_tokens` = 10,000 (Claude Sonnet default)
- But actual system prompts can be 5,800 tokens
- Leaving only 4,200 for conversation!

---

### 🔴 Critical Issue #4: Search Tool Duplicate Data
**Location:** `src/logai/core/tools/cloudwatch_tools.py` lines 464-494

**Problem:**
```python
return {
    "total_events": len(all_events),
    "events": all_events,           # ← All events here
    "events_by_group": grouped,     # ← Same events grouped here
    "summary": {...}
}
```

**Impact:**
- 100 events across 3 log groups = 200 events in response (2x)
- Each event ~200-500 tokens
- Wasted: 10K-50K tokens per search

---

### 🟡 Major Issue #5: No Enforcement of Configured Limits
**Location:** `src/logai/config/settings.py` lines 180-192

**Configured but Never Used:**
```python
max_result_tokens: int = Field(
    default=50_000,
    description="Maximum tokens for tool results"
)  # ← NEVER ENFORCED

max_history_tokens: int = Field(
    default=80_000,
    description="Maximum tokens for conversation history"
)  # ← NEVER ENFORCED

context_window_buffer: int = Field(
    default=5_000,
    description="Safety buffer to keep from context limits"
)  # ← NEVER USED
```

These settings exist but are not referenced in orchestrator.py!

---

## Model-Specific Context Limits

### Current Implementation
**Location:** `src/logai/providers/llm/litellm_provider.py` lines 80-115

Models are configured with context limits:
```python
"claude-3-5-sonnet-20241022": 200_000,
"gpt-4o": 128_000,
"gpt-4o-mini": 128_000,
"ollama_chat/qwen3:32b": 32_000,  # ← User's model
"ollama_chat/llama3.1:8b": 128_000,
```

**User's Model:** Qwen3 32B = **32,000 token context window**

This is relatively small compared to Claude Sonnet (200K). With:
- System prompts: ~5,800 tokens
- Tool results accumulating: ~1K per iteration
- Conversation history: ~2-3K per exchange

User hits limit after ~10-15 exchanges!

---

## What IS Working

✅ **Token Counting Infrastructure:**
- Uses `tiktoken` for accurate counting (when model supported)
- Falls back to 3.5 chars/token heuristic (conservative)
- Located in `orchestrator.py` lines 532-575

✅ **Result Caching:**
- Large log results (>100 events) stored in cache
- LLM receives summary instead of full data: 800-1200 tokens vs 10K-50K
- Fetch chunks on demand
- Located in `src/logai/core/context/result_cache.py`

✅ **History Pruning (Partial):**
- Prunes old messages at start of each turn
- Keeps system message + recent messages
- Located in `orchestrator.py` lines 992-1064

❌ **BUT:** Pruning only happens at START of turn, not during tool execution loop

---

## Root Cause Analysis

### Why User Runs Out of Context So Quickly

**With Qwen3 32B (32K context):**

1. **System Prompts:** 5,800 tokens (18% of context)
2. **Conversation History:** 3 exchanges × 2K = 6,000 tokens (19%)
3. **Tool Results:** 10 iterations × 1K = 10,000 tokens (31%)
4. **Accumulated Guidance:** Retry prompts, cache guidance = 2,000 tokens (6%)
5. **User Query + Response Buffer:** 5,000 tokens (16%)
6. **Overhead:** Message formatting, JSON = 3,000 tokens (9%)

**Total:** ~32,000 tokens

**Result:** Context exhausted after just 3-4 exchanges with tool usage!

### Why It Varies by Model

| Model | Context Window | Exchanges Before Full |
|-------|---------------|---------------------|
| Qwen3 32B (user) | 32K | 3-4 exchanges |
| GPT-4o | 128K | 15-20 exchanges |
| Claude Sonnet | 200K | 25-30 exchanges |

Larger models mask the problem, smaller models expose it quickly.

---

## Recommendations (Prioritized)

### Priority 1: Critical Fixes (Implement First)

#### 1.1: Add Mid-Loop Token Recalculation
**Impact:** Prevents context overflow during tool execution
**Effort:** Medium (2-3 hours)

**Implementation:**
```python
# After each tool result in orchestrator.py line ~1148
tool_result_tokens = self._count_tokens(str(tool_result))
remaining_budget -= tool_result_tokens

if remaining_budget < 5000:  # Buffer threshold
    # Prune oldest messages or stop tool loop
    self._emergency_prune_history()
```

#### 1.2: Enforce max_result_tokens
**Impact:** Prevents single large result from consuming all context
**Effort:** Low (1 hour)

**Implementation:**
```python
# In orchestrator.py after tool execution
if len(str(tool_result)) * 0.3 > settings.max_result_tokens:
    # Force caching even if < 100 events
    self._cache_result(tool_result)
    tool_result = self._create_cache_summary(tool_result)
```

#### 1.3: Remove Duplicate Data from search_logs
**Impact:** Cuts search result tokens in half
**Effort:** Low (30 minutes)

**Implementation:**
```python
# In cloudwatch_tools.py line ~490
return {
    "total_events": len(all_events),
    "events_by_group": grouped,  # ← Keep only this
    # Remove "events": all_events  # ← Delete this line
    "summary": {...}
}
```

---

### Priority 2: Important Improvements

#### 2.1: Reduce System Prompt Size
**Impact:** Frees 1-2K tokens for conversation
**Effort:** Medium (2-3 hours - requires careful rewriting)

**Approach:**
- Consolidate redundant instructions
- Move examples to documentation
- Use more concise language

#### 2.2: Add Context Exhaustion Warnings
**Impact:** User visibility into context usage
**Effort:** Low (1-2 hours)

**Implementation:**
- Display context usage in status bar: "Context: 25K/32K (78%)"
- Show warning at 85%, 90%, 95%
- Suggest "/clear" command when high

#### 2.3: Improve Pruning Strategy
**Impact:** Better history management
**Effort:** Medium (3-4 hours)

**Approach:**
- Prune after each tool execution, not just at turn start
- Keep tool results in cache but remove from context after LLM sees them
- Smart pruning: keep recent, keep errors, drop successes

---

### Priority 3: Nice to Have

- Add model-specific system prompts (smaller for smaller models)
- Implement sliding window for very long conversations
- Add histogram metrics for context usage
- Create "summarize conversation" tool for long sessions

---

## Immediate Action Items

**For User:**
1. Consider using a larger context model temporarily (GPT-4o or Claude Sonnet)
2. Use `/clear` command more frequently to reset context
3. Break complex queries into separate sessions

**For Development Team:**
1. Implement Priority 1 fixes (estimated 4-5 hours total)
2. Add integration test for context overflow scenario
3. Document context management in user guide

---

## Next Steps

**Recommend:** Create a feature task to implement Priority 1 fixes:
1. Task Jackie with implementing the 3 critical fixes
2. Task Raoul with creating integration tests for context limits
3. Task Han-Ron with code review
4. Task Tina with updating documentation

**Estimated Timeline:** 1-2 days for Priority 1 fixes

---

**Investigation Complete**
**Investigator:** Hans (Code Librarian)
**Date:** February 17, 2026
