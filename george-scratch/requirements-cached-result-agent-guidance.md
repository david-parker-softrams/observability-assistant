# Requirements: Agent Guidance for Cached Results

**Date:** February 12, 2026
**Type:** Enhancement
**Priority:** High
**Status:** Requirements Gathering

---

## Problem Statement

### Current Behavior
When a CloudWatch query returns a large result that exceeds the context window threshold:

1. ✅ The system caches the full result in SQLite
2. ✅ A summary is generated and returned to the agent
3. ✅ The summary includes instructions: "Use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve specific events"
4. ✅ The `fetch_cached_result_chunk` tool is available to the agent
5. ❌ **The agent does NOT automatically use the tool** - it just stops after receiving the summary

### User Experience Problem
From the user's perspective:
- User asks: "Show me errors from the last hour"
- Agent queries CloudWatch
- Result is large and gets cached
- Agent receives summary and... **does nothing**
- User sees no actual log events, just a summary saying events were cached
- User has to manually ask again: "Now show me the cached results"

**This creates a poor UX where the agent appears to "freeze" or "give up" after caching.**

---

## Root Cause Analysis

### Issue 1: Passive Instructions
The cached result summary includes this instruction:
```
"This result was cached because it exceeded the context window limit.
Use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve
specific events. You can also filter by time_range or search_pattern."
```

**Problem:** This is passive guidance. The agent reads it but doesn't automatically act on it.

### Issue 2: No Active Prompting
After the tool result with the cache summary is added to conversation history, there's no follow-up system message or prompt that says:
- "You received a cached result. Your next step should be to fetch chunks."
- "The user is waiting for log events. Use the cache_id to retrieve them."

### Issue 3: Agent Intent Unclear
The agent may not understand that:
- The user's original intent ("show me errors") is still unfulfilled
- It needs to automatically proceed to fetch chunks
- The caching was transparent and the user still expects to see logs

---

## Requirements

### High-Level Goal
**When a result is cached, the agent should automatically proceed to fetch and analyze chunks without requiring additional user prompting.**

### Functional Requirements

#### FR1: Enhanced System Prompt Guidance
**Given** the agent has access to the `fetch_cached_result_chunk` tool
**When** the system prompt is generated
**Then** it should explicitly instruct the agent:
- "When you receive a cached result summary, automatically use fetch_cached_result_chunk() to retrieve events"
- "Fetch chunks incrementally (100-200 events at a time) until you have enough to answer the user's question"
- "Don't wait for the user to ask - proceed immediately with chunk retrieval"

#### FR2: Active Follow-Up Injection
**Given** a tool result has been cached
**When** the summary is added to conversation history
**Then** inject an additional system message immediately after with strong guidance:
- "IMPORTANT: The previous result was cached. You must now fetch chunks using the cache_id provided."
- "Start with: fetch_cached_result_chunk(cache_id='<id>', offset=0, limit=100)"
- "Continue fetching chunks as needed to answer the user's question."

#### FR3: Configurable Auto-Fetch Behavior
**Given** result caching is enabled
**When** configuring the system
**Then** provide settings to control agent behavior:
- `auto_fetch_cached_chunks` (bool, default: true) - Whether agent should auto-fetch after caching
- `initial_chunk_size` (int, default: 100) - Size of first chunk to fetch
- `max_auto_fetches` (int, default: 3) - Limit auto-fetches to prevent runaway behavior

#### FR4: Contextual Chunk Fetching
**Given** the user's original query
**When** the agent fetches chunks
**Then** it should intelligently decide:
- How many chunks to fetch (based on user's question)
- Whether to filter chunks (e.g., if user asked for "errors", use filter_pattern="ERROR")
- When to stop fetching (e.g., found enough examples to answer question)

#### FR5: User Feedback During Fetching
**Given** the agent is fetching cached chunks
**When** each chunk is retrieved
**Then** provide UI feedback:
- "Retrieving cached results (chunk 1/?, 100 events)..."
- "Analyzing logs for errors..."
- "Found 15 error events, fetching more details..."

---

## Proposed Solution

### Option A: System Prompt Enhancement (Lightweight)
**Pros:**
- Minimal code changes
- Works with existing infrastructure
- LLM-dependent behavior (relies on model following instructions)

**Cons:**
- May not work consistently across all models
- No guarantee agent will follow prompt
- Harder to debug when it doesn't work

**Implementation:**
```python
# In _get_system_prompt(), add section:
CACHED_RESULT_GUIDANCE = """
When you receive a tool result with "cached": true:
1. Immediately use fetch_cached_result_chunk(cache_id, offset=0, limit=100)
2. Analyze the chunk and decide if more data is needed
3. Fetch additional chunks if necessary (increment offset)
4. Answer the user's question based on the chunks retrieved

Do NOT wait for the user to ask - proceed automatically with chunk fetching.
"""
```

### Option B: Active Injection After Caching (Recommended)
**Pros:**
- More explicit and direct
- Provides concrete action guidance
- Can be disabled via config flag
- Better control over agent behavior

**Cons:**
- Slightly more complex implementation
- Adds extra messages to context

**Implementation:**
```python
# In _process_tool_result(), after caching:
if should_cache:
    summary = await self.result_cache.cache_result(...)

    # Store pending injection for next message preparation
    self._pending_context_injection = {
        "type": "cached_result_guidance",
        "cache_id": summary.cache_id,
        "tool_name": tool_name,
        "user_intent": self._extract_user_intent(),  # from original query
    }

    return summary.to_context_dict()

# In _get_pending_context_injection():
if self._pending_context_injection["type"] == "cached_result_guidance":
    return f"""
SYSTEM INSTRUCTION: The previous query returned a large result that was cached.
Cache ID: {injection['cache_id']}
User Intent: {injection['user_intent']}

You MUST now fetch chunks to complete the user's request:
1. Call fetch_cached_result_chunk(cache_id='{injection['cache_id']}', offset=0, limit=100)
2. Analyze the results
3. Fetch more chunks if needed to fully answer the question
4. Provide a comprehensive response to the user

Do NOT wait - execute this immediately.
"""
```

### Option C: Automatic First Chunk Fetch (Most Aggressive)
**Pros:**
- Guarantees at least one chunk is fetched
- Most consistent behavior
- Agent always has real data to work with

**Cons:**
- May fetch unnecessary data if user question only needs summary stats
- More complex orchestration logic
- Harder to debug

**Implementation:**
```python
# In _process_tool_result(), after caching:
if should_cache:
    summary = await self.result_cache.cache_result(...)

    # Optionally auto-fetch first chunk
    if self.settings.auto_fetch_first_chunk:
        first_chunk = await self.result_cache.fetch_chunk(
            cache_id=summary.cache_id,
            offset=0,
            limit=self.settings.initial_chunk_size,
        )

        # Return both summary and first chunk
        return {
            "cached": True,
            "cache_id": summary.cache_id,
            "summary": summary.to_context_dict(),
            "first_chunk": first_chunk,
            "instructions": "More data available via fetch_cached_result_chunk()"
        }
```

---

## Recommended Approach

**Combination of Option A + Option B:**

1. **Enhance System Prompt** (Option A) - Add general guidance about cached results
2. **Add Active Injection** (Option B) - Inject specific guidance after each cache event
3. **Make it Configurable** - Allow users to disable if they prefer manual control

This provides:
- ✅ Explicit, actionable guidance for the agent
- ✅ Configurable behavior for advanced users
- ✅ Consistent user experience across models
- ✅ Clear debugging path when issues occur

---

## Success Criteria

### User Experience
1. **Given** user asks "Show me errors from /aws/lambda/my-function in the last hour"
   **When** the query returns 10,000 log events (exceeds threshold)
   **Then** the agent should:
   - Cache the full result
   - Automatically fetch first chunk (100 events)
   - Filter for errors if possible
   - Show the user error logs without requiring additional prompting

2. **Given** the agent has fetched one chunk
   **When** it analyzes the chunk
   **Then** it should intelligently decide:
   - "This chunk has 5 errors, user asked for errors, I should show these and maybe fetch one more chunk"
   - OR "This chunk has no errors, I should fetch more chunks with filter_pattern='ERROR'"

### Technical Requirements
1. Agent should fetch at least one chunk automatically 90%+ of the time
2. Total time from cache to first chunk display: <2 seconds
3. User should see progress feedback during chunk fetching
4. Agent should not fetch more than 5 chunks in a single turn (prevent runaway)

### Configuration Requirements
1. Setting: `enable_auto_fetch_cached_chunks` (bool, default: true)
2. Setting: `initial_chunk_size` (int, default: 100, range: 50-200)
3. Setting: `max_auto_chunk_fetches` (int, default: 3, range: 1-10)

---

## Implementation Plan

### Phase 1: System Prompt Enhancement (30 min)
- Update `_get_system_prompt()` to include cached result guidance
- Test with existing cached results

### Phase 2: Active Injection (1 hour)
- Add `_pending_context_injection` state tracking
- Implement injection after cache events
- Test with various query types

### Phase 3: Configuration & Testing (30 min)
- Add settings to LogAISettings
- Update .env.example
- Write unit tests for injection logic
- Manual testing with real CloudWatch queries

### Phase 4: Documentation (30 min)
- Update user documentation
- Add troubleshooting guide
- Document configuration options

**Total Estimated Time: 2.5 hours**

---

## Open Questions

1. **Q:** Should we extract user intent from the original query to guide chunk fetching?
   **A:** TBD - May require simple keyword extraction (e.g., "errors", "warnings", "recent")

2. **Q:** What if the agent ignores the injection and still doesn't fetch chunks?
   **A:** TBD - Could add retry logic or fallback to showing summary with manual instruction

3. **Q:** Should chunk fetching respect the context budget?
   **A:** Yes - track chunk tokens and stop fetching if approaching budget limit

4. **Q:** How do we handle multi-turn conversations where multiple results get cached?
   **A:** Each cache event should get its own injection, agent should handle sequentially

---

## Dependencies

- ✅ Context Management System (already implemented)
- ✅ ResultCacheManager (already implemented)
- ✅ FetchCachedResultTool (already implemented)
- 🔄 Enhanced System Prompt (needs implementation)
- 🔄 Active Injection Logic (needs implementation)
- 🔄 Configuration Settings (needs implementation)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent still ignores guidance | High | Add fallback to show summary + manual instruction |
| Agent fetches too many chunks (runaway) | Medium | Hard limit on max_auto_chunk_fetches |
| Chunk fetching consumes too much context | Medium | Track tokens, stop at budget threshold |
| Different LLMs behave differently | Low | Make behavior configurable per model |
| User wants manual control | Low | Provide `enable_auto_fetch_cached_chunks=false` option |

---

## Future Enhancements

1. **Smart Chunk Size Adjustment**
   - Start with small chunks (50 events) for exploratory queries
   - Use larger chunks (200 events) for known patterns

2. **Chunk Prefetching**
   - Preload first chunk while agent is processing summary
   - Reduces perceived latency

3. **Cache Result Streaming**
   - Stream chunks to user as they're fetched
   - Better UX for large datasets

4. **Intent-Based Filtering**
   - Automatically apply filters based on user query
   - "show me errors" → filter_pattern="ERROR"
   - "recent issues" → time_start=<1 hour ago>

---

## Acceptance Criteria

### Must Have
- [ ] System prompt includes cached result guidance
- [ ] Active injection added after cache events
- [ ] Agent fetches at least one chunk automatically
- [ ] Configuration settings added (enable_auto_fetch, initial_chunk_size, max_fetches)
- [ ] Unit tests for injection logic
- [ ] Manual testing with real CloudWatch queries shows improvement

### Nice to Have
- [ ] User intent extraction for smarter filtering
- [ ] Progress feedback during chunk fetching
- [ ] Chunk size optimization based on query type

### Won't Have (This Phase)
- [ ] Chunk prefetching
- [ ] Result streaming
- [ ] Advanced intent detection

---

## References

- Context Management System Architecture: `george-scratch/architecture-context-management-system.md`
- ResultCacheManager: `src/logai/core/context/result_cache.py`
- FetchCachedResultTool: `src/logai/tools/fetch_cached_result.py`
- Orchestrator: `src/logai/core/orchestrator.py`
