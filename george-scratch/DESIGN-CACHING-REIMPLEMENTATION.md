# Design Document: Caching System Reimplementation

**Document Status:** READY FOR REVIEW
**Version:** 1.0
**Author:** Saanvi (Senior Software Architect)
**Date:** Feb 23, 2026
**Reviewer:** George (Technical Project Manager)

---

## Executive Summary

This design document addresses the reimplementation of the result caching system that was disabled in commit 9ff9993 due to a critical result visibility bug. The agent was unable to properly see and analyze tool results when caching was active, responding as if no data had been received.

### Key Decisions

1. **Result Delivery: Option A (Separate Message Timing)** - Deliver the full tool result first, then inject cache guidance as a separate system message. This is the cleanest solution that preserves the agent's ability to see and analyze results immediately.

2. **Data Structure: Reduce to 5 keys** - Simplify `CachedResultSummary.to_context_dict()` from the current structure to a cleaner 5-key format optimized for LLM comprehension.

3. **Sample Selection: Intelligent Algorithm** - Replace "first N events" with a diversity-aware algorithm that selects representative samples across time, log levels, and content.

4. **Statistics: Structured Fields First** - Use structured log level fields when available, with text heuristics as fallback, and include confidence indicators.

5. **Chunk Fetch Limit: Per-Cache-ID Tracking** - Track fetches per cache_id within a conversation turn, resetting on new user messages.

### Timeline: 2-3 Days

| Phase | Duration | Focus |
|-------|----------|-------|
| Phase 1 | 4-6 hours | Result delivery mechanism fix |
| Phase 2 | 4-6 hours | Known issues fixes |
| Phase 3 | 4-6 hours | Testing and validation |

---

## Table of Contents

1. [Result Delivery Solution](#1-result-delivery-solution-critical)
2. [Data Structure Redesign](#2-data-structure-redesign)
3. [Sample Event Selection Algorithm](#3-sample-event-selection-algorithm)
4. [Statistics Calculation Design](#4-statistics-calculation-design)
5. [Chunk Fetch Limit Enforcement](#5-chunk-fetch-limit-enforcement)
6. [Implementation Plan](#6-implementation-plan)
7. [Testing Strategy](#7-testing-strategy)
8. [Risk Assessment](#8-risk-assessment)
9. [Configuration Changes](#9-configuration-changes)
10. [Database Schema](#10-database-schema)

---

## 1. Result Delivery Solution (CRITICAL)

### 1.1 Problem Analysis

The current bug occurs because cache guidance is merged into the system context **before** the agent has a chance to process the tool result. The message flow creates confusion:

```
CURRENT (BROKEN) FLOW:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Tool returns large result (500 events)                       │
│ 2. System caches result, returns SUMMARY (5 sample events)      │
│ 3. _pending_cache_guidance is set                               │
│ 4. On next LLM call, guidance merged into system prompt         │
│ 5. Agent sees:                                                  │
│    - System prompt: "FETCH CHUNKS using cache_id..."            │
│    - Tool result: Summary with only 5 events                    │
│ 6. Agent gets confused: "What data? I only see 5 events!"       │
│ 7. Agent responds as if no logs were found                      │
└─────────────────────────────────────────────────────────────────┘
```

The core issue: **The agent sees instructions to fetch data before understanding what data it has.**

### 1.2 Option Evaluation

#### Option A: Separate Message Timing (RECOMMENDED)

**Concept:** Deliver the full summarized result first, then inject guidance as a subsequent system message.

```
OPTION A FLOW:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Tool returns large result (500 events)                       │
│ 2. System caches result                                         │
│ 3. Return ENHANCED tool result with clear "here's what you got" │
│ 4. Agent processes tool result (sees 5 samples, understands     │
│    this is a preview of 500 total events)                       │
│ 5. Agent responds with initial analysis                         │
│ 6. IF user asks follow-up question:                             │
│    - Inject guidance: "Use cache_id to fetch more"              │
│ 7. Agent fetches chunks as needed                               │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Agent sees complete result first (no confusion)
- Clear separation: result vs. instructions
- Matches natural human workflow (see data, then decide to get more)
- Preserves two-layer guidance philosophy (baseline + explicit trigger)
- Simpler state management

**Cons:**
- Agent might not immediately fetch chunks (mitigated by clear guidance in result)
- Requires waiting for follow-up for guidance injection

**Mitigations:**
- Include clear "next steps" in the tool result itself
- System prompt baseline explains cached result handling
- Active injection only on follow-up questions requiring full dataset

#### Option B: Smart Summarization (Embedded Instructions)

**Concept:** Embed fetch instructions directly within the tool result.

```json
{
  "status": "CACHED_RESULT",
  "message": "Retrieved 500 log events. Showing 5 samples below.",
  "samples": [...],
  "cache_id": "result_abc123",
  "next_step": "To analyze all 500 events, call fetch_cached_result_chunk(cache_id='result_abc123', offset=0, limit=100)"
}
```

**Pros:**
- Single message, compact
- Instructions co-located with data

**Cons:**
- Agent might fixate on instructions instead of analyzing samples
- Instructions compete with data for attention
- Current bug suggests this approach already fails (we have instructions in `guidance` field)
- No clear trigger point for imperative action

**Verdict:** Not recommended. This is essentially what we have today with the `guidance` field, and it's not working.

#### Option C: Progressive Delivery (Escalating Intervention)

**Concept:** Start with summary only, inject guidance if agent doesn't fetch.

```
OPTION C FLOW:
┌─────────────────────────────────────────────────────────────────┐
│ 1. Tool returns summary (no explicit fetch instruction)         │
│ 2. Agent responds based on samples                              │
│ 3. System detects: Agent didn't fetch chunks                    │
│ 4. IF user asks follow-up needing full data:                    │
│    - Inject STRONG guidance: "You MUST fetch chunks NOW"        │
│ 5. Agent fetches (hopefully)                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:**
- Minimal intervention for capable agents
- Escalating approach respects agent autonomy

**Cons:**
- Complex state tracking (did agent fetch? did it not?)
- First response might be wrong (based only on samples)
- User sees incomplete answer before agent corrects
- More code complexity

**Verdict:** Too complex for the benefit. The first response being potentially wrong is a significant UX issue.

### 1.3 Recommendation: Option A with Enhancements

I recommend **Option A (Separate Message Timing)** with the following enhancements:

1. **Enhanced Tool Result:** The cached result summary should clearly communicate:
   - "This is a PREVIEW of X events"
   - "Sample events are for initial understanding"
   - "Full dataset available via cache_id"

2. **Baseline System Prompt:** Keep the existing system prompt section (lines 284-300) that explains cached results.

3. **Follow-Up Injection:** Only inject explicit fetch guidance when:
   - User asks a follow-up question
   - Question requires full dataset (counting, aggregation, "all of")
   - Active cache exists and is recent (< 5 minutes old)

4. **No Immediate Injection:** Remove the `_pending_cache_guidance` mechanism that injects guidance immediately after caching.

### 1.4 Message Flow Diagrams

#### Scenario 1: Initial Query with Large Result

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INITIAL QUERY - LARGE RESULT                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER: "Show me errors in /aws/lambda/my-function from the last hour"       │
│                                                                              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ASSISTANT (tool_call): search_logs(log_group="/aws/lambda/...",     │    │
│  │                                    filter="ERROR", time="1h")       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ TOOL RESULT (cached):                                               │    │
│  │ {                                                                    │    │
│  │   "preview": {                                                       │    │
│  │     "note": "Showing 5 of 432 total events",                        │    │
│  │     "events": [event1, event2, event3, event4, event5]              │    │
│  │   },                                                                 │    │
│  │   "cache_id": "result_abc123def456789",                             │    │
│  │   "total_events": 432,                                               │    │
│  │   "statistics": {"ERROR": 432},                                      │    │
│  │   "how_to_get_more": "fetch_cached_result_chunk(cache_id=...)"      │    │
│  │ }                                                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│           │ Agent sees CLEAR result with preview                            │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ASSISTANT: "I found 432 error events in the last hour. Here's       │    │
│  │ what I see in the preview:                                          │    │
│  │                                                                      │    │
│  │ - Connection timeout errors (2 in preview)                          │    │
│  │ - Database connection failures (1 in preview)                       │    │
│  │ - API gateway 5xx responses (2 in preview)                          │    │
│  │                                                                      │    │
│  │ Would you like me to analyze all 432 events to give you a complete │    │
│  │ breakdown of error types and frequencies?"                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  [No injection needed - agent understood the result and offered to help]    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Scenario 2: Follow-Up Question Requiring Full Dataset

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FOLLOW-UP REQUIRING FULL DATASET                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER: "Yes, how many are timeout errors?"                                  │
│                                                                              │
│           │ Follow-up detector recognizes:                                  │
│           │ - "how many" = aggregation question                             │
│           │ - Active cache exists (432 events, cache_id=result_abc123...)   │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ SYSTEM INJECTION (added to messages):                                │    │
│  │ "This question requires analyzing all cached events.                 │    │
│  │  Active cache: result_abc123def456789 (432 events)                   │    │
│  │  Use fetch_cached_result_chunk to iterate through all chunks.        │    │
│  │  Do NOT answer based on the preview samples alone."                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ASSISTANT (tool_calls):                                              │    │
│  │   fetch_cached_result_chunk(cache_id="result_abc123...", offset=0)  │    │
│  │   fetch_cached_result_chunk(cache_id="result_abc123...", offset=100)│    │
│  │   fetch_cached_result_chunk(cache_id="result_abc123...", offset=200)│    │
│  │   ... (continues until all 432 processed)                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ASSISTANT: "I analyzed all 432 error events. Here's the breakdown:  │    │
│  │                                                                      │    │
│  │ Timeout Errors: 156 (36%)                                           │    │
│  │ - Connection timeout: 89                                             │    │
│  │ - Read timeout: 67                                                   │    │
│  │                                                                      │    │
│  │ Database Errors: 128 (30%)                                          │    │
│  │ ..."                                                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Scenario 3: New Query (No Follow-Up Injection)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     NEW QUERY - NO INJECTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER: "Now show me metrics for the payment service"                        │
│                                                                              │
│           │ Follow-up detector:                                             │
│           │ - No reference words ("those", "them", "the errors")           │
│           │ - Different topic (metrics, not logs)                           │
│           │ - No aggregation of previous data                               │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ NO INJECTION - This is a new query                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ASSISTANT (tool_call): query_metrics(...)                           │    │
│  │ [Agent correctly uses metrics tool, not cache]                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.5 Implementation Details

#### 1.5.1 Remove Immediate Cache Guidance Injection

**File:** `src/logai/core/orchestrator.py`

Remove or disable the `_pending_cache_guidance` mechanism. The guidance should NOT be injected immediately after caching.

```python
# BEFORE (current code - problematic):
# After caching, immediately set pending guidance
self._pending_cache_guidance = {
    "cache_id": summary.cache_id,
    "total_events": summary.total_events,
}

# AFTER (new approach):
# Just track the active cache for follow-up detection
self._active_cache = ActiveCacheContext(
    cache_id=summary.cache_id,
    total_events=summary.total_events,
    created_at=time.time(),
    tool_name=tool_name,
)
# No immediate injection - let the enhanced tool result speak for itself
```

#### 1.5.2 Enhance Tool Result Clarity

The cached result should be so clear that the agent understands:
1. It received a preview (not the full data)
2. Full data is available
3. How to get the full data

This is addressed in Section 2 (Data Structure Redesign).

#### 1.5.3 Add Follow-Up Detection and Injection

**New method in orchestrator.py:**

```python
@dataclass
class ActiveCacheContext:
    """Tracks active cached dataset for follow-up detection."""
    cache_id: str
    total_events: int
    created_at: float
    tool_name: str
    chunks_fetched: int = 0  # Track for limit enforcement

    def is_recent(self, max_age_seconds: float = 300) -> bool:
        """Check if cache is recent enough (default 5 minutes)."""
        return (time.time() - self.created_at) < max_age_seconds


def _should_inject_cache_guidance(self, user_message: str) -> bool:
    """
    Determine if cache guidance should be injected for this message.

    Returns True if:
    - Active cache exists and is recent
    - Message appears to be a follow-up about cached data
    - Message requires full dataset analysis
    """
    if not self._active_cache or not self._active_cache.is_recent():
        return False

    message_lower = user_message.lower()

    # Check for aggregation keywords (strong signal)
    aggregation_keywords = [
        "how many", "count", "total", "all", "every",
        "breakdown", "distribution", "summarize", "analyze all"
    ]
    has_aggregation = any(kw in message_lower for kw in aggregation_keywords)

    # Check for reference words
    reference_words = [
        "those", "these", "them", "that data", "the errors",
        "the logs", "the results", "the events"
    ]
    has_reference = any(ref in message_lower for ref in reference_words)

    return has_aggregation or has_reference


def _get_follow_up_cache_injection(self, user_message: str) -> str | None:
    """Generate injection for follow-up questions about cached data."""
    if not self._should_inject_cache_guidance(user_message):
        return None

    cache = self._active_cache
    chunk_size = self.settings.initial_chunk_size
    total_chunks = (cache.total_events + chunk_size - 1) // chunk_size

    return f"""
CACHED DATA CONTEXT:
You have an active cached dataset from a previous query:
- Cache ID: {cache.cache_id}
- Total Events: {cache.total_events}
- Chunks Available: {total_chunks} (at {chunk_size} events each)

The user's question requires analyzing the full dataset.
Use fetch_cached_result_chunk(cache_id="{cache.cache_id}", offset=0, limit={chunk_size})
to retrieve and analyze all events. Iterate through all chunks for accurate counts.

Do NOT answer based only on preview samples.
"""
```

---

## 2. Data Structure Redesign

### 2.1 Current Structure Analysis

The current `CachedResultSummary.to_context_dict()` returns:

```python
{
    "cached": True,                    # Key 1: Boolean flag
    "cache_id": "result_abc123...",    # Key 2: ID for fetching
    "summary": {                        # Key 3: Nested summary
        "total_events": 500,
        "time_range": {...},
        "statistics": {...},
        "sample_events": [...]
    },
    "metadata": {                       # Key 4: Nested metadata
        "cached_at": ...,
        "expires_in_seconds": ...,
        "original_query": {...}
    },
    "guidance": "This is a summary..." # Key 5: Text instructions
}
```

**Issues:**
- Nested structures add cognitive load for LLMs
- `guidance` field is passive and ignored
- `metadata` contains rarely-needed info at top level
- No clear "this is what you have" vs "this is how to get more" separation

### 2.2 Proposed Structure (5 Keys)

```python
{
    # Key 1: What you received
    "result_type": "cached_preview",

    # Key 2: What's available
    "full_dataset": {
        "total_events": 500,
        "cache_id": "result_abc123def456789",
        "statistics": {"ERROR": 45, "WARN": 120, "INFO": 335},
        "time_range": {"start": 1707750000000, "end": 1707753600000}
    },

    # Key 3: Preview events (clearly marked as samples)
    "preview_events": [
        {"timestamp": ..., "message": "..."},  # First event
        {"timestamp": ..., "message": "..."},  # Middle event 1
        {"timestamp": ..., "message": "..."},  # Middle event 2
        {"timestamp": ..., "message": "..."},  # Middle event 3
        {"timestamp": ..., "message": "..."}   # Last event
    ],

    # Key 4: How to get more (clear, actionable)
    "fetch_more": {
        "tool": "fetch_cached_result_chunk",
        "example": "fetch_cached_result_chunk(cache_id='result_abc123def456789', offset=0, limit=100)",
        "total_chunks": 5
    },

    # Key 5: Expiration info (important for agent decision-making)
    "expires_in_seconds": 3540
}
```

### 2.3 Key Changes Explained

| Old Key | New Key | Rationale |
|---------|---------|-----------|
| `cached: true` | `result_type: "cached_preview"` | More descriptive, self-documenting |
| `cache_id` (top level) | Moved into `full_dataset` | Grouped with related info |
| `summary.total_events` | `full_dataset.total_events` | Clearer naming |
| `summary.sample_events` | `preview_events` | "Preview" signals incompleteness |
| `guidance` (text blob) | `fetch_more` (structured) | Actionable, parseable |
| `metadata.original_query` | Removed | Agent doesn't need this |
| `metadata.cached_at` | Removed | Not useful for decisions |

### 2.4 Implementation

**File:** `src/logai/core/context/result_cache.py`

```python
def to_context_dict(self) -> dict[str, Any]:
    """
    Convert to dict optimized for LLM comprehension.

    Design principles:
    - 5 top-level keys maximum
    - Clear "what you have" vs "how to get more" separation
    - Preview events clearly marked as samples
    - Actionable fetch instructions
    """
    chunk_size = 100  # Could be made configurable
    total_chunks = (self.total_events + chunk_size - 1) // chunk_size

    return {
        # What type of result this is
        "result_type": "cached_preview",

        # Full dataset information
        "full_dataset": {
            "total_events": self.total_events,
            "cache_id": self.cache_id,
            "statistics": self.event_statistics,
            "time_range": self.time_range,
        },

        # Preview events (clearly samples)
        "preview_events": self.sample_events,

        # How to fetch more data
        "fetch_more": {
            "tool": "fetch_cached_result_chunk",
            "example": f"fetch_cached_result_chunk(cache_id='{self.cache_id}', offset=0, limit={chunk_size})",
            "total_chunks": total_chunks,
            "chunk_size": chunk_size,
        },

        # Time until expiration
        "expires_in_seconds": max(0, self.expires_at - int(time.time())),
    }
```

---

## 3. Sample Event Selection Algorithm

### 3.1 Current Implementation

The current `_sample_events()` method uses a simple strategy:
- First event
- Evenly distributed middle events
- Last event

```python
def _sample_events(self, events, count=5):
    if len(events) <= count:
        return events

    sampled = [events[0]]  # First
    step = len(events) // (count - 1)
    for i in range(1, count - 1):
        sampled.append(events[i * step])
    sampled.append(events[-1])  # Last

    return sampled[:count]
```

**Issues:**
- No diversity by log level (all samples might be INFO)
- No prioritization of interesting events (errors, warnings)
- Purely positional selection

### 3.2 Proposed Algorithm: Diversity-Aware Sampling

**Goals:**
1. Include variety of log levels (ERROR > WARN > INFO > DEBUG)
2. Cover time range (first, middle, last)
3. Prioritize "interesting" events (errors, exceptions)
4. Configurable sample count (3-10)

**Algorithm:**

```
INPUT: events (list), count (int, default 5)
OUTPUT: sampled_events (list)

ALGORITHM: diversity_sample(events, count)
  1. CATEGORIZE events by log level:
     - errors = events containing ERROR/EXCEPTION/FATAL
     - warnings = events containing WARN
     - info = events containing INFO
     - other = remaining events

  2. ALLOCATE slots by priority:
     - If errors exist: allocate min(2, count/2) slots to errors
     - If warnings exist: allocate min(2, remaining/2) slots to warnings
     - Fill remaining slots from info/other

  3. WITHIN each category, select for time diversity:
     - Always include earliest event in category
     - Always include latest event in category
     - Fill middle slots with evenly distributed events

  4. SORT final selection by timestamp

  5. RETURN sampled_events

EXAMPLE (count=5, events=500):
  - 45 errors, 120 warnings, 335 info
  - Allocation: 2 errors, 2 warnings, 1 info
  - Selection:
    - errors: first error, last error
    - warnings: first warning, last warning
    - info: middle info event
  - Result: 5 diverse, representative samples
```

### 3.3 Implementation

**File:** `src/logai/core/context/result_cache.py`

```python
def _sample_events_diverse(
    self,
    events: list[dict[str, Any]],
    count: int | None = None
) -> list[dict[str, Any]]:
    """
    Sample representative events with diversity awareness.

    Strategy:
    1. Categorize by log level (ERROR > WARN > INFO > other)
    2. Allocate slots proportionally with priority to errors/warnings
    3. Within each category, select for time diversity

    Args:
        events: List of event dictionaries
        count: Number of samples (defaults to self.sample_event_count)

    Returns:
        List of diverse, representative sample events
    """
    if count is None:
        count = self.sample_event_count

    if len(events) <= count:
        return events

    # Categorize events by log level
    errors: list[dict] = []
    warnings: list[dict] = []
    info: list[dict] = []
    other: list[dict] = []

    error_patterns = ["ERROR", "EXCEPTION", "FATAL", "CRITICAL"]
    warn_patterns = ["WARN", "WARNING"]
    info_patterns = ["INFO"]

    for event in events:
        message = event.get("message", "").upper()
        level = event.get("level", event.get("log_level", "")).upper()
        combined = f"{level} {message}"

        if any(p in combined for p in error_patterns):
            errors.append(event)
        elif any(p in combined for p in warn_patterns):
            warnings.append(event)
        elif any(p in combined for p in info_patterns):
            info.append(event)
        else:
            other.append(event)

    # Allocate slots (prioritize errors and warnings)
    sampled: list[dict] = []
    remaining = count

    # Errors get priority (up to 40% of slots, min 1 if any exist)
    if errors and remaining > 0:
        error_slots = max(1, min(len(errors), remaining * 2 // 5))
        sampled.extend(self._select_time_diverse(errors, error_slots))
        remaining -= len(sampled)

    # Warnings get second priority (up to 30% of remaining)
    if warnings and remaining > 0:
        warn_slots = max(1, min(len(warnings), remaining * 3 // 10 + 1))
        sampled.extend(self._select_time_diverse(warnings, warn_slots))
        remaining = count - len(sampled)

    # Fill remaining with info and other
    if remaining > 0:
        rest = info + other
        if rest:
            sampled.extend(self._select_time_diverse(rest, remaining))

    # Sort by timestamp for chronological presentation
    sampled.sort(key=lambda e: e.get("timestamp", 0))

    return sampled[:count]


def _select_time_diverse(
    self,
    events: list[dict[str, Any]],
    count: int
) -> list[dict[str, Any]]:
    """
    Select events with time diversity (first, distributed middle, last).

    Args:
        events: List of events (should be pre-filtered by category)
        count: Number to select

    Returns:
        Time-diverse selection of events
    """
    if len(events) <= count:
        return events

    # Sort by timestamp first
    sorted_events = sorted(events, key=lambda e: e.get("timestamp", 0))

    selected = []

    # Always include first
    selected.append(sorted_events[0])

    # Add evenly distributed middle events
    if count > 2:
        step = len(sorted_events) // (count - 1)
        for i in range(1, count - 1):
            idx = min(i * step, len(sorted_events) - 1)
            if sorted_events[idx] not in selected:
                selected.append(sorted_events[idx])

    # Always include last
    if sorted_events[-1] not in selected:
        selected.append(sorted_events[-1])

    return selected[:count]
```

### 3.4 Configuration

**File:** `src/logai/config/settings.py`

The setting `cache_sample_event_count` already exists (default: 5, range: 3-10). No changes needed.

---

## 4. Statistics Calculation Design

### 4.1 Current Implementation

The current implementation tries structured fields first, falls back to text heuristics:

```python
def _extract_event_statistics(self, events):
    level_field = self._detect_level_field(events)
    if level_field:
        return self._count_by_structured_field(events, level_field)
    else:
        return self._count_by_text_heuristics(events)
```

**Issues:**
- No confidence indicator (user doesn't know if stats are reliable)
- Text heuristics can produce false positives
- No indication of which method was used

### 4.2 Proposed Enhancement: Confidence Indicators

Add a confidence indicator to statistics:

```python
{
    "statistics": {
        "ERROR": 45,
        "WARN": 120,
        "INFO": 335,
        "_confidence": "high",  # "high" = structured fields, "estimated" = heuristics
        "_method": "structured_field:level"  # or "text_heuristics"
    }
}
```

### 4.3 Implementation

**File:** `src/logai/core/context/result_cache.py`

```python
def _extract_event_statistics(
    self,
    events: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Extract statistics from events with confidence indicator.

    Uses structured log level fields when available (high confidence),
    falls back to text heuristics (estimated confidence).

    Args:
        events: List of event dictionaries

    Returns:
        Statistics dictionary with counts and confidence metadata
    """
    if not events:
        return {"_confidence": "none", "_method": "no_events"}

    # Try to detect structured log level field
    level_field = self._detect_level_field(events)

    if level_field:
        stats = self._count_by_structured_field(events, level_field)
        stats["_confidence"] = "high"
        stats["_method"] = f"structured_field:{level_field}"
        logger.debug(f"Statistics from structured field '{level_field}' (high confidence)")
    else:
        stats = self._count_by_text_heuristics(events)
        stats["_confidence"] = "estimated"
        stats["_method"] = "text_heuristics"
        logger.debug("Statistics from text heuristics (estimated confidence)")

    return stats
```

### 4.4 Improved Text Heuristics

The current text heuristics are reasonable but could be improved to reduce false positives:

```python
def _count_by_text_heuristics(
    self,
    events: list[dict[str, Any]]
) -> dict[str, int]:
    """
    Count events by text heuristics (fallback method).

    Uses careful pattern matching to avoid false positives like
    "No errors found" being counted as an error.
    """
    stats: dict[str, int] = {}

    # Patterns that indicate actual log levels (not mentions)
    # Format: (patterns_list, category_name)
    level_patterns = [
        # Errors: Look for log-level prefixes, not just the word
        (
            [
                r"^\[?ERROR\]?[:\s]",      # [ERROR]: or ERROR:
                r"^\[?ERR\]?[:\s]",        # [ERR]: or ERR:
                r"\bERROR\s+\d{4}",        # ERROR 2024 (error with date)
                r"level[\"']?\s*[:=]\s*[\"']?error",  # level: error
                r"\"level\"\s*:\s*\"ERROR\"",  # JSON: "level": "ERROR"
            ],
            "ERROR"
        ),
        (
            [
                r"^\[?WARN(?:ING)?\]?[:\s]",
                r"\bWARN(?:ING)?\s+\d{4}",
                r"level[\"']?\s*[:=]\s*[\"']?warn",
            ],
            "WARN"
        ),
        (
            [
                r"^\[?INFO\]?[:\s]",
                r"\bINFO\s+\d{4}",
                r"level[\"']?\s*[:=]\s*[\"']?info",
            ],
            "INFO"
        ),
        (
            [
                r"^\[?DEBUG\]?[:\s]",
                r"\bDEBUG\s+\d{4}",
                r"level[\"']?\s*[:=]\s*[\"']?debug",
            ],
            "DEBUG"
        ),
    ]

    import re

    for event in events:
        message = event.get("message", "")
        categorized = False

        for patterns, category in level_patterns:
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    stats[category] = stats.get(category, 0) + 1
                    categorized = True
                    break
            if categorized:
                break

        if not categorized:
            stats["OTHER"] = stats.get("OTHER", 0) + 1

    return stats
```

---

## 5. Chunk Fetch Limit Enforcement

### 5.1 Current State

The setting `max_auto_chunk_fetches` (default: 3) exists but is advisory only. There's no actual enforcement - agents can make unlimited fetch calls.

### 5.2 Proposed Design

**Tracking Scope:** Per cache_id, per conversation turn

**Reset Trigger:** New user message

**Enforcement Point:** In `FetchCachedResultTool.execute()` or orchestrator's tool execution

**Behavior When Exceeded:**
- Return warning (not error) so agent can complete
- Include clear message about limit
- Log for monitoring

### 5.3 Implementation

#### 5.3.1 Add Tracking to Orchestrator

**File:** `src/logai/core/orchestrator.py`

```python
@dataclass
class ActiveCacheContext:
    """Tracks active cached dataset for follow-up detection and limit enforcement."""
    cache_id: str
    total_events: int
    created_at: float
    tool_name: str
    chunks_fetched: int = 0  # NEW: Track fetch count

    def is_recent(self, max_age_seconds: float = 300) -> bool:
        return (time.time() - self.created_at) < max_age_seconds

    def increment_fetch_count(self) -> int:
        """Increment and return new fetch count."""
        self.chunks_fetched += 1
        return self.chunks_fetched

    def is_over_limit(self, max_fetches: int) -> bool:
        """Check if fetch count exceeds limit."""
        return self.chunks_fetched >= max_fetches


class LLMOrchestrator:
    def __init__(self, ...):
        # ... existing init ...
        self._active_cache: ActiveCacheContext | None = None

    def _reset_cache_fetch_count(self) -> None:
        """Reset fetch count on new user message."""
        if self._active_cache:
            self._active_cache.chunks_fetched = 0
```

#### 5.3.2 Enforce in Tool Execution

**Option A: Enforce in Orchestrator (Recommended)**

Check limit before executing `fetch_cached_result_chunk`:

```python
async def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
    """Execute a tool with limit enforcement for cache fetches."""

    # Check fetch limit for cache operations
    if tool_name == "fetch_cached_result_chunk":
        cache_id = arguments.get("cache_id")

        if self._active_cache and self._active_cache.cache_id == cache_id:
            fetch_count = self._active_cache.increment_fetch_count()
            max_fetches = self.settings.max_auto_chunk_fetches

            if fetch_count > max_fetches:
                logger.warning(
                    f"Chunk fetch limit exceeded: {fetch_count}/{max_fetches} "
                    f"for cache_id={cache_id}"
                )

                # Return warning, not error (let agent complete)
                return {
                    "success": True,
                    "warning": f"Fetch limit reached ({max_fetches} chunks per turn). "
                               f"Consider summarizing current data or asking user "
                               f"if more detail is needed.",
                    "fetch_count": fetch_count,
                    "limit": max_fetches,
                    "events": [],  # Empty to signal limit
                    "limit_exceeded": True,
                }

    # Execute tool normally
    return await tool.execute(**arguments)
```

**Option B: Enforce in Tool Itself**

Pass limit info to tool and let it enforce. Less clean but more encapsulated.

### 5.4 User Feedback

When limit is reached, the tool result should clearly explain:

```json
{
    "success": true,
    "warning": "Chunk fetch limit reached (3 chunks per conversation turn). You have analyzed 300 of 500 events. To continue analysis, summarize your findings and ask the user if they need more detail.",
    "events": [],
    "limit_exceeded": true,
    "analyzed_so_far": 300,
    "total_available": 500
}
```

### 5.5 Reset Behavior

The fetch count resets when:
1. User sends a new message (new turn)
2. Cache expires
3. New cache is created (different cache_id)

This is implemented in the orchestrator's message handling:

```python
async def process_message(self, user_message: str) -> str:
    """Process user message."""
    # Reset fetch count for new turn
    self._reset_cache_fetch_count()

    # ... rest of processing
```

---

## 6. Implementation Plan

### 6.1 Phase 1: Result Delivery Fix (4-6 hours)

**Priority:** P0 (Critical)

#### Task 1.1: Remove Immediate Cache Guidance Injection (1 hour)

**File:** `src/logai/core/orchestrator.py`

**Changes:**
- Remove `_pending_cache_guidance` usage
- Add `_active_cache: ActiveCacheContext | None` attribute
- Update `_process_tool_result()` to set `_active_cache` instead of `_pending_cache_guidance`

**Before:**
```python
self._pending_cache_guidance = {"cache_id": ..., "total_events": ...}
```

**After:**
```python
self._active_cache = ActiveCacheContext(
    cache_id=summary.cache_id,
    total_events=summary.total_events,
    created_at=time.time(),
    tool_name=tool_name,
)
```

#### Task 1.2: Add Follow-Up Detection (2 hours)

**File:** `src/logai/core/orchestrator.py`

**Changes:**
- Add `ActiveCacheContext` dataclass
- Add `_should_inject_cache_guidance()` method
- Add `_get_follow_up_cache_injection()` method
- Integrate injection into `_chat_complete()` and `_chat_stream()`

#### Task 1.3: Update Data Structure (1.5 hours)

**File:** `src/logai/core/context/result_cache.py`

**Changes:**
- Rewrite `CachedResultSummary.to_context_dict()` with new 5-key structure
- Update any code that depends on the old structure

#### Task 1.4: Update Tests for Phase 1 (1.5 hours)

**Files:**
- `tests/unit/core/context/test_result_cache.py`
- `tests/unit/core/test_orchestrator_context.py` (if exists)

**Changes:**
- Update assertions for new data structure
- Add tests for follow-up detection
- Add tests for injection logic

### 6.2 Phase 2: Known Issues Fixes (4-6 hours)

**Priority:** P1 (High)

#### Task 2.1: Implement Diverse Sample Selection (1.5 hours)

**File:** `src/logai/core/context/result_cache.py`

**Changes:**
- Replace `_sample_events()` with `_sample_events_diverse()`
- Add `_select_time_diverse()` helper method
- Update `cache_result()` to use new sampling

#### Task 2.2: Add Statistics Confidence Indicators (1 hour)

**File:** `src/logai/core/context/result_cache.py`

**Changes:**
- Update `_extract_event_statistics()` to add confidence metadata
- Optionally improve text heuristics regex patterns

#### Task 2.3: Implement Chunk Fetch Limit Enforcement (1.5 hours)

**File:** `src/logai/core/orchestrator.py`

**Changes:**
- Add `chunks_fetched` tracking to `ActiveCacheContext`
- Add limit check in tool execution path
- Add `_reset_cache_fetch_count()` method
- Call reset on new user message

#### Task 2.4: Update Tests for Phase 2 (2 hours)

**Files:**
- `tests/unit/core/context/test_result_cache.py`
- `tests/unit/tools/test_fetch_cached_result.py`

**Changes:**
- Add tests for diverse sampling
- Add tests for statistics confidence
- Add tests for fetch limit enforcement

### 6.3 Phase 3: Testing and Validation (4-6 hours)

**Priority:** P1 (High)

#### Task 3.1: Integration Testing (2 hours)

**Manual testing scenarios:**
1. Large result caching and preview display
2. Follow-up question with aggregation
3. New query (no injection)
4. Fetch limit enforcement
5. Cache expiration handling

#### Task 3.2: End-to-End Agent Testing (2 hours)

**Test with real agent:**
1. "Show me errors from last hour" → Large result cached
2. "How many are timeout errors?" → Agent should fetch all chunks
3. "Show me metrics instead" → Should NOT use cache
4. Verify no "agent freeze" behavior

#### Task 3.3: Documentation Updates (1 hour)

**Files:**
- `docs/user-guide/cached-results.md` - Update for new behavior
- `docs/architecture/design-cache-llm.md` - Mark as superseded or update

#### Task 3.4: Code Review and Polish (1 hour)

- Review all changes
- Ensure consistent code style
- Add logging for debugging
- Update comments

### 6.4 Implementation Summary Table

| Task | File(s) | Estimated Time | Dependencies |
|------|---------|----------------|--------------|
| 1.1 Remove immediate injection | orchestrator.py | 1h | None |
| 1.2 Add follow-up detection | orchestrator.py | 2h | 1.1 |
| 1.3 Update data structure | result_cache.py | 1.5h | None |
| 1.4 Phase 1 tests | test_*.py | 1.5h | 1.1-1.3 |
| 2.1 Diverse sampling | result_cache.py | 1.5h | None |
| 2.2 Stats confidence | result_cache.py | 1h | None |
| 2.3 Fetch limit enforcement | orchestrator.py | 1.5h | 1.1 |
| 2.4 Phase 2 tests | test_*.py | 2h | 2.1-2.3 |
| 3.1 Integration testing | - | 2h | Phase 1-2 |
| 3.2 E2E agent testing | - | 2h | Phase 1-2 |
| 3.3 Documentation | docs/*.md | 1h | Phase 1-2 |
| 3.4 Code review | - | 1h | All |

**Total: 17-19 hours (2-3 days)**

---

## 7. Testing Strategy

### 7.1 Unit Tests

#### 7.1.1 New Tests Required

**File:** `tests/unit/core/context/test_result_cache.py`

```python
class TestDiverseSampling:
    """Tests for diversity-aware sample selection."""

    def test_sample_prioritizes_errors(self):
        """Errors should be included even if they're rare."""

    def test_sample_includes_time_range(self):
        """Samples should span the full time range."""

    def test_sample_handles_no_errors(self):
        """Should work when no errors exist."""

    def test_sample_respects_count_setting(self):
        """Sample count should match configuration."""


class TestStatisticsConfidence:
    """Tests for statistics confidence indicators."""

    def test_structured_field_high_confidence(self):
        """Stats from structured fields should be high confidence."""

    def test_heuristics_estimated_confidence(self):
        """Stats from text heuristics should be estimated confidence."""

    def test_no_events_none_confidence(self):
        """Empty events should indicate no confidence."""


class TestNewDataStructure:
    """Tests for the new 5-key data structure."""

    def test_to_context_dict_keys(self):
        """Should have exactly 5 top-level keys."""

    def test_to_context_dict_result_type(self):
        """result_type should be 'cached_preview'."""

    def test_to_context_dict_fetch_more(self):
        """fetch_more should contain actionable instructions."""
```

**File:** `tests/unit/core/test_orchestrator_cache.py` (new file)

```python
class TestFollowUpDetection:
    """Tests for follow-up question detection."""

    def test_detects_how_many(self):
        """'How many' should trigger injection."""

    def test_detects_reference_words(self):
        """'those', 'them' should trigger injection."""

    def test_ignores_new_topics(self):
        """New topics should NOT trigger injection."""

    def test_respects_cache_age(self):
        """Old caches should NOT trigger injection."""


class TestFetchLimitEnforcement:
    """Tests for chunk fetch limit enforcement."""

    def test_tracks_fetch_count(self):
        """Fetch count should increment."""

    def test_warns_at_limit(self):
        """Should warn when limit reached."""

    def test_resets_on_new_message(self):
        """Count should reset on new user message."""
```

#### 7.1.2 Updated Tests

Existing tests that need updates:

**File:** `tests/unit/core/context/test_result_cache.py`

- `TestCachedResultSummary.test_to_context_dict()` - Update for new structure
- `TestResultCacheManager.test_cache_result_sample_events()` - Update for diverse sampling

### 7.2 Integration Tests

#### 7.2.1 End-to-End Scenarios

```python
class TestCachingIntegration:
    """Integration tests for the full caching flow."""

    @pytest.mark.asyncio
    async def test_large_result_shows_preview(self):
        """Large results should show preview with clear instructions."""
        # 1. Execute search that returns 500+ events
        # 2. Verify result is cached
        # 3. Verify agent receives preview structure
        # 4. Verify agent can understand what it received

    @pytest.mark.asyncio
    async def test_follow_up_triggers_chunk_fetch(self):
        """Follow-up questions should trigger chunk fetching."""
        # 1. Cache a large result
        # 2. Send follow-up: "How many are errors?"
        # 3. Verify injection was added
        # 4. Verify agent fetches chunks

    @pytest.mark.asyncio
    async def test_new_query_no_injection(self):
        """New queries should NOT use cached data."""
        # 1. Cache a large result
        # 2. Send new query: "Show me metrics"
        # 3. Verify NO injection
        # 4. Verify agent uses appropriate tool

    @pytest.mark.asyncio
    async def test_fetch_limit_enforcement(self):
        """Fetch limit should be enforced."""
        # 1. Cache large result
        # 2. Trigger multiple chunk fetches
        # 3. Verify warning at limit
        # 4. Verify count resets on new message
```

### 7.3 Edge Cases

| Edge Case | Expected Behavior | Test Coverage |
|-----------|-------------------|---------------|
| Empty result (0 events) | No caching, return empty | Unit test |
| Small result (< threshold) | No caching, return full | Unit test |
| All events same log level | Samples all same level | Unit test |
| No timestamps in events | Sampling still works | Unit test |
| Cache expires mid-conversation | Graceful error, hint to re-query | Integration |
| Multiple caches in one conversation | Latest cache used for injection | Integration |
| User asks about OLD cache | No injection (>5 min old) | Unit test |

### 7.4 Performance Tests

| Test | Target | Method |
|------|--------|--------|
| Cache storage latency | <50ms | Time `cache_result()` |
| Sample selection | <10ms for 10k events | Time `_sample_events_diverse()` |
| Statistics extraction | <20ms for 10k events | Time `_extract_event_statistics()` |
| Follow-up detection | <5ms | Time `_should_inject_cache_guidance()` |

---

## 8. Risk Assessment

### 8.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Agent still ignores guidance | Medium | High | Multiple injection points, testing |
| False positive follow-up detection | Low | Medium | Conservative keyword matching |
| New data structure breaks clients | Low | High | No external API changes |
| Statistics confidence confuses LLM | Low | Low | Clear naming, documentation |
| Fetch limit too restrictive | Medium | Medium | Make configurable, warn don't block |
| Performance regression | Low | Medium | Performance tests, profiling |

### 8.2 Detailed Mitigations

#### Risk: Agent Still Ignores Guidance

**Likelihood:** Medium - LLMs are unpredictable

**Mitigations:**
1. **Clear data structure:** New format makes it obvious what agent received
2. **Explicit follow-up injection:** Strong language when iteration required
3. **System prompt baseline:** Persistent knowledge about cached results
4. **Testing:** Extensive testing with real agent

**Contingency:** If agent still fails:
- Add retry nudge (detect wrong answer, re-inject stronger guidance)
- Add UI indicator showing data coverage

#### Risk: False Positive Follow-Up Detection

**Likelihood:** Low - Conservative keyword matching

**Mitigations:**
1. **Time-limited:** Only inject if cache < 5 minutes old
2. **Keyword combination:** Require aggregation keyword OR reference word
3. **Topic detection:** Could add topic similarity check (future)

**Contingency:** If too many false positives:
- Increase time limit strictness
- Require BOTH aggregation AND reference word

#### Risk: Fetch Limit Too Restrictive

**Likelihood:** Medium - Default of 3 might not be enough

**Mitigations:**
1. **Warning not error:** Agent can still complete analysis
2. **Configurable:** User can increase `max_auto_chunk_fetches`
3. **Per-turn reset:** New messages reset count

**Contingency:** Increase default to 5 if 3 proves insufficient

### 8.3 Rollback Plan

If the reimplementation fails or causes issues:

1. **Immediate:** Re-enable full result delivery (disable caching)
   - Set `enable_result_caching = False`
   - This is already the current state (commit 9ff9993)

2. **Short-term:** Revert specific changes
   - Each phase can be reverted independently
   - Keep git commits small and focused

3. **Communication:** Alert team if rollback needed
   - Update George (TPM)
   - Document what failed and why

---

## 9. Configuration Changes

### 9.1 New Settings

No new settings required. All functionality uses existing settings:

| Setting | Current Default | Purpose |
|---------|-----------------|---------|
| `enable_result_caching` | True (but disabled) | Master switch |
| `cache_sample_event_count` | 5 | Number of preview events |
| `max_auto_chunk_fetches` | 3 | Limit per conversation turn |
| `initial_chunk_size` | 100 | Events per chunk |

### 9.2 Setting Modifications

Consider updating these defaults based on testing:

| Setting | Current | Proposed | Rationale |
|---------|---------|----------|-----------|
| `max_auto_chunk_fetches` | 3 | 5 | 3 might be too restrictive |
| `cache_sample_event_count` | 5 | 5 | Good balance (no change) |

### 9.3 New Internal Constants

Add to `result_cache.py`:

```python
# Follow-up detection
CACHE_RELEVANCE_SECONDS = 300  # 5 minutes
AGGREGATION_KEYWORDS = ["how many", "count", "total", ...]
REFERENCE_WORDS = ["those", "these", "them", ...]
```

---

## 10. Database Schema

### 10.1 Current Schema

```sql
CREATE TABLE cached_results (
    cache_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    query_params TEXT NOT NULL,
    result_data TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    data_size_bytes INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    last_accessed INTEGER NOT NULL,
    access_count INTEGER DEFAULT 0
);
```

### 10.2 Schema Changes

**No schema changes required.**

The current schema supports all needed functionality. The changes are all in the application layer:
- How we summarize/present data (Python code)
- How we track fetch counts (in-memory, per session)
- How we detect follow-up questions (Python code)

### 10.3 Migration

Not applicable - no schema changes.

---

## Appendices

### Appendix A: Code Examples

#### A.1 New Data Structure Example

```json
{
    "result_type": "cached_preview",
    "full_dataset": {
        "total_events": 432,
        "cache_id": "result_abc123def456789",
        "statistics": {
            "ERROR": 45,
            "WARN": 87,
            "INFO": 300,
            "_confidence": "high",
            "_method": "structured_field:level"
        },
        "time_range": {
            "start": 1707750000000,
            "end": 1707753600000,
            "span_ms": 3600000
        }
    },
    "preview_events": [
        {"timestamp": 1707750000000, "level": "ERROR", "message": "Connection timeout to database"},
        {"timestamp": 1707751200000, "level": "ERROR", "message": "API rate limit exceeded"},
        {"timestamp": 1707752400000, "level": "WARN", "message": "High memory usage detected"},
        {"timestamp": 1707753000000, "level": "INFO", "message": "Request processed successfully"},
        {"timestamp": 1707753600000, "level": "ERROR", "message": "Service unavailable"}
    ],
    "fetch_more": {
        "tool": "fetch_cached_result_chunk",
        "example": "fetch_cached_result_chunk(cache_id='result_abc123def456789', offset=0, limit=100)",
        "total_chunks": 5,
        "chunk_size": 100
    },
    "expires_in_seconds": 3540
}
```

#### A.2 Follow-Up Injection Example

```
CACHED DATA CONTEXT:
You have an active cached dataset from a previous query:
- Cache ID: result_abc123def456789
- Total Events: 432
- Chunks Available: 5 (at 100 events each)

The user's question requires analyzing the full dataset.
Use fetch_cached_result_chunk(cache_id="result_abc123def456789", offset=0, limit=100)
to retrieve and analyze all events. Iterate through all chunks for accurate counts.

Do NOT answer based only on preview samples.
```

### Appendix B: File Change Summary

| File | Lines Changed | Type of Change |
|------|---------------|----------------|
| `src/logai/core/context/result_cache.py` | ~150 | Modify |
| `src/logai/core/orchestrator.py` | ~100 | Modify |
| `tests/unit/core/context/test_result_cache.py` | ~100 | Modify + Add |
| `tests/unit/core/test_orchestrator_cache.py` | ~150 | New file |
| `docs/user-guide/cached-results.md` | ~50 | Update |

### Appendix C: Preserved Bug Fixes

All critical bug fixes from commits Feb 12-20 will be preserved:

| Commit | Bug | Fix Preserved |
|--------|-----|---------------|
| 59e4274 | Cache ID truncation | Yes - validation logic unchanged |
| 620defd | User context loss | Yes - context merging preserved |
| 81767b4 | Race conditions | Yes - lock-based init unchanged |
| c7103b2 | JSON corruption | Yes - validation on startup |
| b0b8ad7 | TTL off-by-one | Yes - comparison logic unchanged |

---

## Document Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Author | Saanvi (Senior Software Architect) | Complete | Feb 23, 2026 |
| Reviewer | George (Technical Project Manager) | Pending Review | |
| Implementer | Jackie (Software Engineer) | Pending | |

---

**End of Design Document**
