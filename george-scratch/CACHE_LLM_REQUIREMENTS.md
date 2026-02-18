# Cache LLM Behavior Requirements

## Problem Statement

During the 2026-02-13 18:08 UTC session, the LLM received a cached result containing 432 events but **failed to call `fetch_cached_result_chunk`** to retrieve the actual data. Instead, it answered follow-up questions using only the 5 sample events from the summary.

### Specific Example
**User Query:** "Of the errors pulled, how many are SSN issues?"
**Expected Behavior:** Iterate through ALL 432 cached events, counting SSN-related errors
**Actual Behavior:** Answered based on 5 sample events only (0% complete analysis)

### Impact
- Incorrect/incomplete answers to user questions
- Cache metrics show 0/0 (no fetch operations recorded)
- No cache tools visible in sidebar
- User cannot trust agent to analyze full dataset

## Root Cause

The current system prompt (lines 284-300 in orchestrator.py) provides general guidance but **lacks explicit rules** for:
1. Recognizing when follow-up questions reference cached data
2. Iterating through ALL chunks when complete analysis is required
3. Managing context space by discarding processed chunks
4. Understanding the cache is the authoritative source for the current dataset

## Requirements

### R1: Follow-Up Question Detection
**MUST:** When user asks a follow-up question that references a recent cached query result, the LLM must recognize this and fetch from cache rather than execute a new query.

**Examples of follow-up questions:**
- "How many of those are SSN errors?" → References "those" (cached results)
- "What's the breakdown by error type?" → Implies analysis of current dataset
- "Show me the first 10" → Refers to cached results
- "Count errors containing 'timeout'" → Requires full dataset scan

**Detection signals:**
- Reference pronouns: "those", "these", "them", "it"
- Implicit context: "the errors", "the logs", "the results"
- Analysis requests: "count", "breakdown", "how many", "summarize"
- Time proximity: Question asked within 5 minutes of cache creation

### R2: Complete Dataset Iteration
**MUST:** When a user question requires analysis of the full dataset (e.g., counting, grouping, finding all instances), the LLM must:
1. Calculate total chunks needed: `ceil(total_events / chunk_size)`
2. Iterate through ALL chunks sequentially
3. Accumulate results across chunks
4. Report final aggregated answer

**Examples requiring full iteration:**
- "How many errors mention SSN?" → Must scan all events
- "What are the unique error types?" → Must see all events
- "Count by service name" → Must aggregate across all events
- "Find all errors with status code 500" → Must check every event

**Examples NOT requiring full iteration:**
- "Show me the first 10 errors" → Single chunk with limit=10
- "Show an example of an SSN error" → Stop at first match

### R3: Context Space Management
**MUST:** After processing each chunk, the LLM should discard the chunk data from its working memory to save context space.

**Implementation:**
- Process chunk → Extract needed information → Forget raw events
- Keep only: running counts, unique values, matched event IDs
- Can re-fetch specific chunks later if user asks for details

**Example flow for counting:**
```
Chunk 1 (0-99):    Process → Count: 12 SSN errors → Forget events
Chunk 2 (100-199): Process → Count: 8 SSN errors  → Forget events
Chunk 3 (200-299): Process → Count: 15 SSN errors → Forget events
...
Final answer: Total 47 SSN errors found across 432 events
```

### R4: Cache as Source of Truth
**MUST:** When a cached result exists for the current question context, the LLM must treat it as the authoritative dataset.

**Rules:**
- Do NOT execute new queries when follow-up questions reference cached data
- The cache represents "the dataset we're currently analyzing"
- New query tools (search_logs, query_metrics) should only be used for NEW questions
- Cache remains valid until user changes topic or requests fresh data

### R5: Explicit Chunk Fetching Strategy
**MUST:** The system prompt must provide explicit instructions on when and how to fetch chunks.

**Decision tree:**
```
IF (received cached result):
  IF (user asks follow-up about "this data"):
    IF (question requires full dataset scan):
      → Fetch ALL chunks, iterate until offset >= total_events
    ELSE IF (question needs specific subset):
      → Fetch targeted chunks with filter_pattern or time_range
    ELSE IF (user wants samples/examples):
      → Fetch first chunk (offset=0, limit=100)
  ELSE IF (user asks NEW question):
    → Use appropriate query tool (search_logs, etc.)
```

### R6: Progress Indication
**SHOULD:** When iterating through multiple chunks, the LLM should indicate progress to the user.

**Example:**
```
"Let me analyze all 432 events from the cache..."
[Fetches chunk 1] "Processing events 0-99..."
[Fetches chunk 2] "Processing events 100-199..."
[Fetches chunk 3] "Processing events 200-299..."
...
"Analysis complete: Found 47 SSN-related errors out of 432 total."
```

## Acceptance Criteria

### AC1: Automatic Chunk Fetching
- [ ] When cached result is returned, LLM immediately fetches at least one chunk
- [ ] No user prompting required to trigger initial fetch
- [ ] Verified by: Tool sidebar shows `fetch_cached_result_chunk` call
- [ ] Verified by: Status bar shows cache_hit metric increment

### AC2: Follow-Up Question Handling
- [ ] User asks "How many of those are X?" after cached query
- [ ] LLM recognizes reference to cached data
- [ ] LLM fetches chunks from cache (not new query)
- [ ] Verified by: Logs show fetch operations, not new search_logs

### AC3: Complete Dataset Iteration
- [ ] User asks question requiring full scan (e.g., "count all X")
- [ ] LLM calculates: ceil(total_events / chunk_size) chunks needed
- [ ] LLM fetches ALL chunks until offset >= total_events
- [ ] LLM reports aggregated result
- [ ] Verified by: Logs show sequential fetch calls with increasing offsets
- [ ] Verified by: User answer reflects complete dataset (not just samples)

### AC4: Status Bar Accuracy
- [ ] After cache operations, status bar shows "Cache: X/Y (Z%)"
- [ ] Cache hit count increments with each successful fetch
- [ ] Verified by: Status bar displays non-zero values
- [ ] Verified by: Metrics match actual fetch operations in logs

### AC5: Correct Answers
- [ ] User asks "How many SSN errors?" on dataset with 432 events
- [ ] LLM scans all 432 events
- [ ] LLM reports accurate count
- [ ] Verified by: Manual verification of count
- [ ] Verified by: LLM answer includes "analyzed 432 events"

## Non-Functional Requirements

### NFR1: Performance
- Chunk fetching should be fast (<100ms per chunk per cache manager spec)
- Iterating through 500 events (5 chunks) should complete in <1 second
- LLM should minimize unnecessary refetching

### NFR2: Context Efficiency
- Processing 500 events should not balloon context to >50K tokens
- Discarding processed chunks should keep context manageable
- System should handle datasets up to 10,000 events without context overflow

### NFR3: User Experience
- User should see progress indicators for long operations
- Answers should be accurate and complete
- Cache operations should be visible in sidebar for transparency

## Technical Constraints

1. **Context Window Limit:** Results >5000 events must be cached
2. **Initial Chunk Size:** Default 100 events (configurable)
3. **Max Chunk Size:** 200 events per fetch
4. **Cache TTL:** 1 hour (3600 seconds)
5. **LLM Model:** claude-sonnet-4.5 (200K context window)

## Design Goals

1. **Make instructions IMPOSSIBLE to ignore** - Not suggestions, but strict rules
2. **Provide explicit decision logic** - No ambiguity about when to fetch
3. **Enable autonomous iteration** - LLM should handle multi-chunk analysis without user prompts
4. **Optimize for correctness first** - Accuracy matters more than speed
5. **Maintain transparency** - User can see what the agent is doing

## Success Metrics

- **Cache Hit Rate:** >95% of follow-up questions use cache (not new queries)
- **Completion Rate:** 100% of chunks fetched when full scan is required
- **Answer Accuracy:** 100% correct counts/aggregations on cached datasets
- **Status Bar Accuracy:** Cache metrics reflect actual operations within 1 second
- **User Satisfaction:** Users trust agent to analyze complete datasets

## Related Files

- `src/logai/core/orchestrator.py` - System prompt (lines 284-300, 440-463)
- `src/logai/core/context/result_cache.py` - Cache manager & summary format
- `src/logai/tools/fetch_cached_result.py` - Chunk fetching tool
- `src/logai/core/metrics.py` - Metrics collection
- `src/logai/ui/screens/chat.py` - Status bar cache metrics display

## User Feedback (Direct Quote)

> "Ideally it should have gone through the entire cache chunk by chunk counting SSN errors and reported the final number. I think we need to make sure the LLM understands its task. Ideally it should be able to get a count of the number of results in cache and be told when given requests that clearly reference the most recent query (such as my follow up question about SSN errors) it should be going through the entire cache if needed (such as to count total errors of a certain type). If possible can it be told to purge each record from its 'memory' after processing it to save context space? It can always refetch from the cache if it needs to for subsequent questions."

---

**Document Status:** Ready for design review
**Created:** 2026-02-13
**Author:** George (Technical Project Manager)
**Next Step:** Assign to Saanvi (Software Architect) for design
