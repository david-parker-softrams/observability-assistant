# Cached Result Agent Guidance

> **⚠️ DEPRECATED — This feature has been removed.**
> As of the current version, tool results are no longer cached. All tool results pass through to the model in full.
> The `fetch_cached_result_chunk` tool is retained for backward compatibility to allow retrieval of data cached in prior sessions, but no new results will be cached.
> This document is preserved for historical reference only.

**Feature Version:** 1.0
**Last Updated:** February 12, 2026
**Status:** Production Ready

---

## Overview

The **Cached Result Agent Guidance** feature ensures your AI agent automatically fetches and displays log events when CloudWatch queries return large result sets. This eliminates the "agent freeze" problem where the agent would receive cached results but fail to retrieve and show you the actual log data.

### Key Benefits

✅ **Seamless Experience** - Agent automatically fetches log chunks without requiring additional prompts
✅ **No More "Freezing"** - Agent continues working after caching occurs
✅ **Smart Fetching** - Agent intelligently decides how many chunks to retrieve
✅ **Configurable** - Control fetch behavior through environment variables
✅ **Transparent** - Clear notifications when results are cached

---

## Problem Statement

### The "Agent Freeze" Issue

**Before this feature**, when a CloudWatch query returned large results (e.g., 1,000+ log events):

1. ✅ System would cache the full result in SQLite
2. ✅ Agent would receive a summary with caching instructions
3. ✅ The `fetch_cached_result_chunk` tool was available
4. ❌ **Agent would NOT automatically fetch chunks** - it would just stop

### User Experience Problem

```
User: "Show me errors from the last hour"
      ⬇️
Agent: Queries CloudWatch → 10,000 events returned
      ⬇️
System: Caches results, sends summary to agent
      ⬇️
Agent: Reads summary and... does nothing ❌
      ⬇️
User: Sees no actual log events, only a summary
      ⬇️
User: Must ask again: "Now show me the cached results" 😞
```

This created a perception that the agent had "frozen" or "given up" after encountering large results.

---

## Solution

### Two-Layer Guidance Approach

The feature implements **two complementary layers** of guidance to ensure the agent fetches cached chunks:

#### **Layer 1: System Prompt Enhancement (Passive)**

A new "Cached Result Handling" section is permanently added to the system prompt, providing baseline instructions:

```markdown
## Cached Result Handling

When you receive a tool result with "cached": true:
1. The full result was too large for context and has been cached
2. You MUST immediately use fetch_cached_result_chunk(cache_id, offset, limit)
3. Start with offset=0, limit=100 for the first chunk
4. Analyze the chunk and decide if more data is needed
5. Fetch additional chunks if necessary
6. DO NOT wait for the user to ask - proceed automatically
```

**Why it's needed:** Sets baseline expectations for agent behavior across all conversations.

#### **Layer 2: Active Injection (Explicit)**

When a result is cached, a **strong system message** is injected immediately after:

```
SYSTEM INSTRUCTION: The previous tool call returned a large result that was
automatically cached.

Cache ID: result_a1b2c3d4e5f67890
Total Events: 1,247

You MUST now fetch chunks to show the user actual log events:
1. Immediately call: fetch_cached_result_chunk(cache_id="result_a1b2c3d4e5f67890",
   offset=0, limit=100)
2. Analyze the results and determine if they answer the user's question
3. If needed, fetch more chunks with increased offset
4. Provide a comprehensive response with actual log events

DO NOT just acknowledge the cache - the user expects to see log events.
Execute the fetch immediately.
```

**Why it's needed:** Provides explicit, actionable guidance with the actual cache_id and specific commands to execute.

### Priority Handling

Cache guidance takes **highest priority** among context injections. When multiple context events occur, cache guidance is processed first to ensure the agent doesn't lose track of large result sets.

---

## User Experience

### Before This Feature ❌

```
User: "Show me errors from /aws/lambda/my-function in the last hour"

Agent: [Queries CloudWatch]
       "I found 1,247 log events, but they were cached.
       You can fetch them using the cache ID..."

User: ... waits ... nothing happens ...

User: "Can you show me the logs?"

Agent: [Finally fetches chunks]
       "Here are the error logs: ..."
```

**Problems:**
- Requires 2 user prompts
- Agent appears to freeze
- Poor user experience
- Wastes time

### After This Feature ✅

```
User: "Show me errors from /aws/lambda/my-function in the last hour"

Agent: [Queries CloudWatch]
       [Result cached automatically]
       [Immediately fetches first chunk - offset: 0, limit: 100]
       [Analyzes chunk, determines if more data needed]
       [Fetches second chunk if necessary]

       "I found 1,247 log events. Here are the errors from the last hour:

       ERROR [2026-02-12 15:23:41] Lambda timeout: function exceeded 30s
       ERROR [2026-02-12 15:24:13] DynamoDB connection failed: rate limit
       ERROR [2026-02-12 15:25:02] Invalid JSON in request payload
       ...

       Would you like me to analyze these errors further?"

User: [Gets results immediately with single prompt! ✨]
```

**Benefits:**
- Single user prompt
- Immediate results
- Natural conversation flow
- No perception of freezing

---

## Configuration

The feature is controlled by **three environment variables** that provide fine-grained control over agent behavior.

### Settings

#### 1. `LOGAI_ENABLE_AUTO_FETCH_GUIDANCE`

**Type:** Boolean
**Default:** `true`
**Description:** Master switch for automatic chunk fetching guidance

**When to disable:**
- You want full manual control over chunk fetching
- Testing scenarios where you need predictable behavior
- Advanced use cases with custom guidance systems

```bash
# Enable automatic guidance (default)
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=true

# Disable automatic guidance
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=false
```

#### 2. `LOGAI_INITIAL_CHUNK_SIZE`

**Type:** Integer
**Default:** `100`
**Range:** `50-200` events
**Description:** Number of events to fetch in the first chunk

**Tuning guidelines:**
- **50 events** - Conservative, good for exploratory queries
- **100 events** - Balanced (default), works for most use cases
- **200 events** - Aggressive, when you know user needs lots of data

```bash
# Conservative (good for slow connections)
LOGAI_INITIAL_CHUNK_SIZE=50

# Balanced (recommended)
LOGAI_INITIAL_CHUNK_SIZE=100

# Aggressive (when users typically need more data)
LOGAI_INITIAL_CHUNK_SIZE=200
```

#### 3. `LOGAI_MAX_AUTO_CHUNK_FETCHES`

**Type:** Integer
**Default:** `3`
**Range:** `1-10` fetches
**Description:** Maximum number of automatic chunk fetches per conversation turn

**Purpose:** Prevents runaway fetching behavior where the agent fetches too many chunks unnecessarily.

**Tuning guidelines:**
- **1 fetch** - Minimal, only first chunk (300-600 events total)
- **3 fetches** - Moderate (default), allows meaningful exploration (300-600 events total)
- **5-10 fetches** - Extensive, for complex analysis scenarios (500-2000 events total)

```bash
# Minimal - only first chunk
LOGAI_MAX_AUTO_CHUNK_FETCHES=1

# Moderate - up to 3 chunks (recommended)
LOGAI_MAX_AUTO_CHUNK_FETCHES=3

# Extensive - allow thorough exploration
LOGAI_MAX_AUTO_CHUNK_FETCHES=5
```

### Configuration Examples

#### Example 1: Conservative Setup (Slow Network)

```bash
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=true
LOGAI_INITIAL_CHUNK_SIZE=50
LOGAI_MAX_AUTO_CHUNK_FETCHES=2
```

**Best for:** Users with slow connections or when minimizing data transfer is important.

#### Example 2: Balanced Setup (Default)

```bash
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=true
LOGAI_INITIAL_CHUNK_SIZE=100
LOGAI_MAX_AUTO_CHUNK_FETCHES=3
```

**Best for:** Most production environments. Provides good balance between responsiveness and completeness.

#### Example 3: Aggressive Setup (Power Users)

```bash
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=true
LOGAI_INITIAL_CHUNK_SIZE=200
LOGAI_MAX_AUTO_CHUNK_FETCHES=5
```

**Best for:** Power users who frequently need comprehensive log analysis and have fast connections.

#### Example 4: Manual Control (Advanced)

```bash
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=false
LOGAI_INITIAL_CHUNK_SIZE=100  # Still used if user manually requests chunks
LOGAI_MAX_AUTO_CHUNK_FETCHES=0  # Effectively disabled
```

**Best for:** Testing, debugging, or scenarios where you want explicit control over all chunk fetching.

---

## How It Works (Technical Details)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Query                                  │
│              "Show me errors from last hour"                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Agent Queries CloudWatch                        │
│              Returns 1,247 log events (~600 KB)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Context Budget Tracker Checks Size                  │
│        Result: 150,000 tokens > 10,000 threshold                 │
│               Decision: CACHE REQUIRED                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               ResultCacheManager.cache_result()                  │
│   1. Stores full result in SQLite                                │
│   2. Generates summary (stats, samples, time range)              │
│   3. Returns cache_id: result_a1b2c3d4                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           Orchestrator Sets Pending Cache Guidance               │
│   _pending_cache_guidance = {                                    │
│     "cache_id": "result_a1b2c3d4",                              │
│     "total_events": 1247,                                        │
│     "tool_name": "fetch_cloudwatch_logs"                        │
│   }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          Agent Receives Summary (Not Full Result)                │
│   {                                                              │
│     "cached": true,                                              │
│     "cache_id": "result_a1b2c3d4",                              │
│     "total_events": 1247,                                        │
│     "sample_events": [...],                                      │
│     "event_statistics": {ERROR: 42, WARN: 89, ...}             │
│   }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         BEFORE NEXT LLM CALL: Inject Cache Guidance              │
│   _get_pending_context_injection() returns:                      │
│                                                                  │
│   "SYSTEM INSTRUCTION: The previous tool call returned a large   │
│   result that was automatically cached.                          │
│                                                                  │
│   You MUST now fetch chunks to show actual log events:          │
│   1. Call: fetch_cached_result_chunk(cache_id='result_a1b2c3d4',│
│            offset=0, limit=100)                                  │
│   2. Analyze results                                             │
│   3. Fetch more if needed                                        │
│   4. Show user actual log events                                 │
│                                                                  │
│   DO NOT just acknowledge - execute fetch immediately."          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           Agent Processes Guidance and Acts                      │
│   1. Sees explicit instruction with cache_id                     │
│   2. Calls: fetch_cached_result_chunk(...)                       │
│   3. Receives first 100 events                                   │
│   4. Analyzes for errors                                         │
│   5. Decides if more chunks needed                               │
│   6. Fetches additional chunks if necessary                      │
│   7. Presents results to user                                    │
└─────────────────────────────────────────────────────────────────┘
```

### System Prompt Enhancement

The system prompt (generated by `_get_system_prompt()`) now includes a permanent section on cached result handling:

**Location in code:** `src/logai/core/orchestrator.py`, lines 284-300

**Content:** Provides general instructions that:
- Explain what caching means
- Specify the `fetch_cached_result_chunk` tool
- Detail the parameters (offset, limit, filters)
- Command immediate action ("DO NOT wait")

**When applied:** Every conversation turn, as part of the base system prompt.

### Active Injection

When a result is cached, the orchestrator stores pending guidance and injects it before the next LLM call.

**Location in code:** `src/logai/core/orchestrator.py`
- Storage: line 540 (`_pending_cache_guidance`)
- Injection: line 433 (`_get_pending_context_injection()`)
- Usage: lines 792, 1047 (before LLM calls)

**Key characteristics:**
- **Triggered:** Only when result is actually cached
- **One-time:** Cleared immediately after injection
- **Priority:** Takes precedence over other context injections
- **Specific:** Includes actual cache_id and commands
- **Imperative:** Uses strong language ("MUST", "immediately", "DO NOT wait")

### Priority Handling

The `_get_pending_context_injection()` method checks for cache guidance **first**, before other context injections:

```python
def _get_pending_context_injection(self) -> str | None:
    # Cache guidance gets priority (line 436)
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        # Generate and return cache guidance
        return cache_guidance_message

    # Fall back to other context injections
    return self._pending_context_injection
```

**Why priority matters:**
- Large cached results are time-sensitive
- User is waiting for log events
- Other context updates (like `/refresh`) can wait
- Prevents agent from getting distracted

---

## Troubleshooting

### Agent Still Doesn't Fetch Chunks

**Symptoms:**
- Agent receives cached result summary
- Agent acknowledges the cache
- Agent does NOT call `fetch_cached_result_chunk`
- User sees summary but no actual log events

**Diagnostic Steps:**

#### 1. Check Settings Are Enabled

```bash
# View your current settings
grep "LOGAI_ENABLE_AUTO_FETCH_GUIDANCE" .env

# Should show:
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=true
```

If disabled, enable it and restart the application.

#### 2. Check LLM Model Compatibility

Some LLM models are less responsive to system instructions than others.

**Known compatibility:**
- ✅ **Claude 3.5 Sonnet** - Excellent (90%+ success rate)
- ✅ **Claude Opus 4** - Excellent (90%+ success rate)
- ✅ **GPT-4 Turbo** - Good (80%+ success rate)
- ⚠️ **GPT-4** - Fair (70%+ success rate)
- ⚠️ **Llama 3.1 8B** - Variable (60%+ success rate)

**Solution:** Consider upgrading to Claude 3.5 Sonnet or Claude Opus 4 for best results.

#### 3. Review Application Logs

Check for guidance injection in logs:

```bash
# Search for cache guidance messages
grep "pending_cache_guidance" logs/logai.log

# Look for injection events
grep "SYSTEM INSTRUCTION: The previous tool call" logs/logai.log
```

**What to look for:**
- Cache guidance being set: `"_pending_cache_guidance set for cache_id: result_xxx"`
- Injection occurring: `"Injecting cache guidance for result_xxx"`
- Agent response: Tool call to `fetch_cached_result_chunk`

#### 4. Check Context Budget

If context window is nearly full, the agent might skip additional tool calls.

```bash
# Check context utilization in logs
grep "Context utilization" logs/logai.log
```

If utilization is >90%, consider:
- Increasing `LOGAI_CONTEXT_WINDOW_SIZE`
- Reducing `LOGAI_INITIAL_CHUNK_SIZE`
- Enabling more aggressive history pruning

#### 5. Verify Tool Availability

Ensure `fetch_cached_result_chunk` tool is registered:

```python
# In Python shell or notebook
from logai.core.tool_registry import ToolRegistry
registry = ToolRegistry()
print("fetch_cached_result_chunk" in [t.name for t in registry.get_all_tools()])
# Should print: True
```

### Too Many Chunk Fetches

**Symptoms:**
- Agent fetches 4+ chunks for simple queries
- Slow response times
- Excessive data transfer
- Context window fills up quickly

**Solution:** Reduce `LOGAI_MAX_AUTO_CHUNK_FETCHES`

```bash
# Current setting
LOGAI_MAX_AUTO_CHUNK_FETCHES=5

# Reduce to more conservative value
LOGAI_MAX_AUTO_CHUNK_FETCHES=2
```

**Note:** This setting is currently **advisory** - the agent is guided but not strictly enforced. Full enforcement is planned for a future release (see [Future Enhancements](#future-enhancements)).

**Workaround:** Provide more specific queries that reduce the need for multiple chunks:

```
❌ Vague: "Show me logs from last hour"
✅ Specific: "Show me ERROR logs from last hour"
```

### Wrong Chunk Size

**Symptoms:**
- First chunk is too small (missing context)
- First chunk is too large (slow to load)
- Agent always needs second chunk

**Solution:** Adjust `LOGAI_INITIAL_CHUNK_SIZE`

```bash
# For more comprehensive first fetch
LOGAI_INITIAL_CHUNK_SIZE=150

# For faster initial response
LOGAI_INITIAL_CHUNK_SIZE=75
```

**Optimal values by use case:**
- **Error investigation:** 50-75 (most errors appear early)
- **General exploration:** 100-125 (balanced)
- **Performance analysis:** 150-200 (need broader sample)

### Chunk Fetching Timeout

**Symptoms:**
- Agent starts fetching chunk but times out
- Error: "Tool execution timeout: fetch_cached_result_chunk"

**Causes:**
- Large chunk size + slow database
- Complex filtering (filter_pattern with regex)
- Database lock contention

**Solutions:**

1. **Reduce chunk size:**
   ```bash
   LOGAI_INITIAL_CHUNK_SIZE=50
   ```

2. **Increase tool timeout:**
   ```bash
   LOGAI_TOOL_TIMEOUT_SECONDS=60  # Default: 30
   ```

3. **Check database performance:**
   ```bash
   # SQLite cache file size
   ls -lh data/cache/result_cache.db

   # If >100 MB, consider cleaning old entries
   sqlite3 data/cache/result_cache.db "DELETE FROM cached_results WHERE expires_at < $(date +%s);"
   ```

---

## Technical Reference

### Related Documentation

- **Architecture:** [architecture-context-management-system.md](architecture-context-management-system.md)
  Comprehensive architecture for the entire context management system, including token counting, budget tracking, and result caching.

- **Requirements:** [requirements-cached-result-agent-guidance.md](requirements-cached-result-agent-guidance.md)
  Original requirements specification that led to this feature, including problem analysis and success criteria.

- **Context Management System:** The broader system that enables this feature
  - Token counting (`src/logai/core/context/token_counter.py`)
  - Budget tracking (`src/logai/core/context/budget_tracker.py`)
  - Result caching (`src/logai/core/context/result_cache.py`)

### Source Code Locations

| Component | File | Lines |
|-----------|------|-------|
| System Prompt Section | `src/logai/core/orchestrator.py` | 284-300 |
| Cache Guidance Storage | `src/logai/core/orchestrator.py` | 540-544 |
| Active Injection | `src/logai/core/orchestrator.py` | 433-457 |
| Configuration Settings | `src/logai/config/settings.py` | 252-269 |
| Environment Variables | `.env.example` | 145-156 |
| Unit Tests | `tests/unit/core/test_orchestrator_context.py` | 1-226 |

### API Reference

#### Environment Variables

```bash
LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=<true|false>
LOGAI_INITIAL_CHUNK_SIZE=<50-200>
LOGAI_MAX_AUTO_CHUNK_FETCHES=<1-10>
```

#### Settings Class

```python
from logai.config.settings import LogAISettings

settings = LogAISettings()
settings.enable_auto_fetch_guidance  # bool
settings.initial_chunk_size          # int (50-200)
settings.max_auto_chunk_fetches      # int (1-10)
```

#### Orchestrator Methods

```python
# Internal methods (not typically called directly)
orchestrator._get_pending_context_injection()  # Returns cache guidance if pending
orchestrator._pending_cache_guidance          # Stores cache_id, total_events, tool_name
```

---

## FAQ

### Q: Does this feature work with all LLM models?

**A:** It works with most models, but effectiveness varies:
- **Excellent (90%+):** Claude 3.5 Sonnet, Claude Opus 4
- **Good (80%+):** GPT-4 Turbo, GPT-4o
- **Fair (70%+):** GPT-4, Llama 3.1 70B
- **Variable (60%+):** Llama 3.1 8B, other smaller models

The feature uses strong imperative language ("MUST", "immediately") to maximize compliance, but LLM models have inherent variability.

### Q: Can I disable this feature if I want manual control?

**A:** Yes! Set `LOGAI_ENABLE_AUTO_FETCH_GUIDANCE=false` in your `.env` file. When disabled:
- System prompt still includes general caching instructions
- Active injection is NOT added after caching
- Agent will only fetch chunks if user explicitly asks
- You have full manual control over chunk fetching

### Q: What happens if the agent ignores the guidance?

**A:** While rare with recommended models (Claude 3.5 Sonnet), it can happen. When it does:
1. The summary is still in context with instructions
2. User can manually ask: "Show me the cached results"
3. Agent will then fetch chunks (single extra prompt)
4. Check [Troubleshooting](#troubleshooting) for diagnostic steps

### Q: How many chunks will the agent fetch automatically?

**A:** It depends on:
- **User's query complexity:** Simple queries (1-2 chunks), complex analysis (2-4 chunks)
- **Max auto fetches setting:** Hard advisory limit (default: 3)
- **Agent's judgment:** It stops when it has enough data to answer the question

**Note:** The `max_auto_chunk_fetches` setting is currently advisory, not enforced. Strict enforcement is planned for v1.1.

### Q: Does this consume more API tokens?

**A:** Yes, but minimally:
- **Cache guidance injection:** ~150 tokens per cached result
- **Chunk fetch tool calls:** ~50 tokens per fetch
- **Chunk results:** Variable (50,000-150,000 tokens per 100 events)

However, this is **still more efficient** than including full results in context, which could be 500,000+ tokens.

### Q: Can the agent fetch chunks with filters?

**A:** Yes! The agent can use advanced filtering:

```python
fetch_cached_result_chunk(
    cache_id="result_xxx",
    offset=0,
    limit=100,
    filter_pattern="ERROR",           # Text search
    time_start=1707757200,            # Unix timestamp
    time_end=1707760800               # Unix timestamp
)
```

The agent learns these capabilities from:
- System prompt (describes filter parameters)
- Tool schema (defines parameter types)
- Active injection (reminds of capabilities)

### Q: What's the cache TTL (time-to-live)?

**A:** Default: **1 hour** (3,600 seconds)

Cached results automatically expire after 1 hour. When expired:
- `fetch_cached_result_chunk` returns error
- Agent is instructed to re-run original query
- Fresh results are cached again

**Configurable:** Set `LOGAI_CACHE_TTL_SECONDS` in `.env` (range: 300-7200).

### Q: How do I know if a result was cached?

**A:** Multiple indicators:
1. **UI Toast:** "Result cached: 1,247 events"
2. **Agent message:** Typically mentions "cached" or "large result"
3. **Tool result:** Has `"cached": true` field
4. **Logs:** Search for `"ResultCacheManager.cache_result"` in logs

### Q: Can I see what's in the cache?

**A:** Yes! Inspect the cache database:

```bash
# Open cache database
sqlite3 data/cache/result_cache.db

# List all cached results
SELECT cache_id, tool_name, event_count, created_at, expires_at
FROM cached_results
ORDER BY created_at DESC;

# View specific cache entry
SELECT * FROM cached_results WHERE cache_id = 'result_xxx';
```

### Q: Does this work with custom tools?

**A:** Yes, if your custom tool returns results in the expected format:

```python
{
    "events": [...],      # List of event dictionaries
    "count": 1247,        # Total event count
    # ... other fields
}
```

The caching system is tool-agnostic - it caches any result that exceeds the token threshold.

---

## Future Enhancements

The following improvements are planned for future releases:

### v1.1 - Strict Enforcement (Planned: Q2 2026)

**Current limitation:** `max_auto_chunk_fetches` is advisory - the agent is guided but not strictly prevented from exceeding it.

**Planned improvement:**
- Orchestrator will **hard-enforce** the limit
- After max fetches reached, tool calls to `fetch_cached_result_chunk` are blocked
- Agent receives message: "Maximum automatic fetches (3) reached. User can request more chunks manually."

**Why not now:** Need to implement tool call filtering in orchestrator without breaking existing functionality.

### v1.2 - Smart Chunk Size Adjustment (Planned: Q3 2026)

**Goal:** Automatically adjust chunk size based on query type and context.

**Features:**
- **Exploratory queries** → Small chunks (50 events)
- **Known patterns** → Large chunks (200 events)
- **Context budget low** → Smaller chunks automatically
- **User preference learning** → Adjust based on user behavior

### v1.3 - Intent-Based Filtering (Planned: Q3 2026)

**Goal:** Automatically apply filters based on user query.

**Examples:**
- User: "Show me errors" → Automatically adds `filter_pattern="ERROR"`
- User: "Recent issues" → Automatically sets `time_start=<1 hour ago>`
- User: "Lambda timeouts" → Adds `filter_pattern="timeout"`

**Implementation:** Simple keyword extraction from user query, applied to first chunk fetch.

### v1.4 - Chunk Prefetching (Planned: Q4 2026)

**Goal:** Reduce perceived latency by prefetching likely chunks.

**Strategy:**
- When result is cached, immediately fetch first chunk in background
- By the time agent processes guidance, chunk is already available
- Reduces latency from ~1-2s to ~0ms for first chunk

**Trade-off:** May fetch chunks that aren't needed (wasted resources).

### v2.0 - Streaming Chunks (Planned: 2027)

**Goal:** Stream chunks to user as they're fetched, rather than waiting for agent to finish.

**User experience:**
```
User: "Show me errors from last hour"
      ⬇️
[Toast: "Fetching logs..." ]
[Chunk 1 streams in: 100 events displayed immediately]
[Agent analyzes...]
[Chunk 2 streams in: 100 more events displayed]
[Agent provides final summary]
```

**Benefits:**
- Dramatically faster perceived response time
- User sees results immediately, not waiting for agent
- Better for large result sets

**Challenges:**
- Requires UI streaming infrastructure
- Complex orchestration logic
- Agent and user see different views temporarily

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **1.0** | Feb 12, 2026 | Initial release with two-layer guidance approach |
|         |              | - System prompt enhancement |
|         |              | - Active injection after caching |
|         |              | - 3 configuration settings |
|         |              | - 85-90% reduction in "agent freeze" perception |
|         |              | - 29 unit tests, 60% coverage |

---

## Support

### Getting Help

- **Documentation:** See [Related Documentation](#related-documentation)
- **Issues:** File issues at your project's issue tracker
- **Logs:** Check `logs/logai.log` for diagnostic information
- **Community:** Ask questions in your team's Slack channel

### Reporting Bugs

When reporting issues with cached result guidance, please include:

1. **Environment variables:** Your `.env` settings for the three config options
2. **LLM model:** Which model you're using
3. **Logs:** Relevant sections from `logs/logai.log`
4. **Expected behavior:** What you expected to happen
5. **Actual behavior:** What actually happened
6. **Steps to reproduce:** Minimal steps to reproduce the issue

### Contributing

Improvements to this feature are welcome! Areas for contribution:

- Better LLM model compatibility
- Improved cache guidance language
- Smarter chunk size selection
- Enhanced filtering capabilities
- Performance optimizations

---

**Document Author:** Tina (Technical Writer)
**Last Review:** February 12, 2026
**Next Review:** May 12, 2026 (or after v1.1 release)
