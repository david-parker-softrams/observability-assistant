# Design Document: Improved Cache LLM Instruction System

**Document Status:** DRAFT
**Version:** 1.0
**Author:** Saanvi (Senior Software Architect)
**Date:** 2026-02-13
**Reviewer:** George (Technical Project Manager)

---

## Executive Summary

This document presents a comprehensive architectural solution to ensure the LLM **reliably and autonomously** handles cached query results. The core problem is that the LLM ignores instructions to iterate through cached data chunks when answering follow-up questions, leading to incomplete and incorrect answers.

Our solution employs a **multi-layered instruction architecture** that makes cache operations impossible to ignore through:
1. **Imperative system prompt rules** (not suggestions)
2. **Stateful cache context tracking** in the orchestrator
3. **Explicit decision algorithms** embedded in prompts
4. **Enhanced context injection** with mandatory action requirements

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Root Cause Analysis](#2-root-cause-analysis)
3. [Detailed Design](#3-detailed-design)
   - 3.1 [System Prompt Enhancement](#31-system-prompt-enhancement)
   - 3.2 [Context Injection Enhancement](#32-context-injection-enhancement)
   - 3.3 [Cached Result Summary Enhancement](#33-cached-result-summary-enhancement)
   - 3.4 [Follow-Up Question Detection](#34-follow-up-question-detection)
   - 3.5 [Progress Indication System](#35-progress-indication-system)
4. [Prompt Engineering Strategy](#4-prompt-engineering-strategy)
5. [Example Scenarios](#5-example-scenarios)
6. [Implementation Plan](#6-implementation-plan)
7. [Acceptance Criteria](#7-acceptance-criteria)
8. [Risk Analysis](#8-risk-analysis)
9. [Appendix: Complete Prompt Templates](#appendix-complete-prompt-templates)

---

## 1. Architecture Overview

### 1.1 Current State

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CURRENT FLOW (Broken)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User: "Show me errors in the last hour"                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────┐                                           │
│   │   search_logs tool   │ → Returns 432 events                      │
│   └─────────────────────┘                                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────┐                                           │
│   │   Result too large   │ → Cached automatically                    │
│   │   (cached: true)     │                                           │
│   └─────────────────────┘                                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  LLM receives SUMMARY with:                   │                  │
│   │  - cache_id: result_953cb27301cbbd58         │                   │
│   │  - total_events: 432                          │                  │
│   │  - sample_events: [5 events]                  │                  │
│   │  - instructions: "Use fetch_cached_result..." │   ← IGNORED!    │
│   └─────────────────────────────────────────────┘                   │
│              │                                                       │
│              ▼                                                       │
│   User: "How many of those are SSN errors?"                         │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  LLM answers using ONLY 5 sample events      │   ← WRONG!       │
│   │  "Looking at the samples, I see 0 SSN..."    │                  │
│   └─────────────────────────────────────────────┘                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Target State

```
┌─────────────────────────────────────────────────────────────────────┐
│                          TARGET FLOW (Fixed)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User: "Show me errors in the last hour"                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────┐                                           │
│   │   search_logs tool   │ → Returns 432 events                      │
│   └─────────────────────┘                                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────┐                                           │
│   │   Result too large   │ → Cached automatically                    │
│   │   (cached: true)     │                                           │
│   └─────────────────────┘                                           │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  ENHANCED INJECTION with MANDATORY rules     │                  │
│   │  + Cache context tracked in orchestrator     │                  │
│   └─────────────────────────────────────────────┘                   │
│              │                                                       │
│              ▼                                                       │
│   User: "How many of those are SSN errors?"                         │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  Follow-up question detector recognizes      │                  │
│   │  reference to cached data                    │                  │
│   └─────────────────────────────────────────────┘                   │
│              │                                                       │
│              ▼                                                       │
│   ┌─────────────────────────────────────────────┐                   │
│   │  LLM MUST iterate through ALL chunks:        │                  │
│   │                                               │                  │
│   │  Chunk 1 (0-99):   Count SSN → 12 found      │                  │
│   │  Chunk 2 (100-199): Count SSN → 8 found      │                  │
│   │  Chunk 3 (200-299): Count SSN → 15 found     │                  │
│   │  Chunk 4 (300-399): Count SSN → 9 found      │                  │
│   │  Chunk 5 (400-432): Count SSN → 3 found      │                  │
│   │                                               │                  │
│   │  "I analyzed all 432 events and found        │                  │
│   │   47 SSN-related errors."                    │   ← CORRECT!     │
│   └─────────────────────────────────────────────┘                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPONENT ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         ORCHESTRATOR                               │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │   │
│  │  │ System Prompt    │  │ Cache Context   │  │ Context         │   │   │
│  │  │ (Enhanced)       │  │ Tracker (NEW)   │  │ Injector        │   │   │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘   │   │
│  │           │                    │                    │             │   │
│  │           ▼                    ▼                    ▼             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │              ACTIVE CACHE DATASET STATE                      │ │   │
│  │  │  - current_cache_id: str | None                             │ │   │
│  │  │  - total_events: int                                        │ │   │
│  │  │  - chunks_fetched: Set[int]                                 │ │   │
│  │  │  - last_cache_timestamp: float                              │ │   │
│  │  │  - pending_iteration: bool                                  │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         RESULT CACHE                              │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │   │
│  │  │ CachedResult    │  │ Chunk Fetcher   │  │ Filter Engine   │   │   │
│  │  │ Summary         │  │                 │  │                 │   │   │
│  │  │ (Enhanced)      │  │                 │  │                 │   │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                              LLM                                   │   │
│  │  Receives:                                                         │   │
│  │  1. Enhanced system prompt with MANDATORY cache rules             │   │
│  │  2. Context injection after cached results                        │   │
│  │  3. Follow-up context injection with iteration guidance           │   │
│  │  4. Progress reporting expectations                               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Root Cause Analysis

### 2.1 Why the LLM Ignores Cache Instructions

After analyzing the current implementation, I've identified five root causes:

| # | Root Cause | Current Behavior | Impact |
|---|------------|------------------|--------|
| 1 | **Passive Language** | "Use fetch_cached_result_chunk to retrieve..." | LLM treats as optional suggestion |
| 2 | **No Follow-Up Context** | No reminder of cached data on follow-up questions | LLM forgets cached dataset exists |
| 3 | **No Decision Algorithm** | No explicit rules for WHEN to iterate all chunks | LLM makes ad-hoc decisions |
| 4 | **Sample Events Too Prominent** | 5 sample events are "good enough" | LLM satisfices with samples |
| 5 | **No State Tracking** | Orchestrator doesn't track active cache | Can't inject follow-up guidance |

### 2.2 Evidence from Requirements Document

From `CACHE_VERIFICATION.md`:
```
2026-02-13 17:56:12,997 - Tool: fetch_cached_result_chunk called with cache_id=result_953cb27301cbbd58
```

The cache **works** - the LLM **can** fetch chunks. The problem is it doesn't **know when** it should do a complete iteration.

### 2.3 Key Insight

The LLM is not broken - it's **under-instructed**. The solution is not technical fixes but **better prompt engineering** combined with **stateful context management**.

---

## 3. Detailed Design

### 3.1 System Prompt Enhancement

**Current Location:** `orchestrator.py` lines 284-300

**Current (Ineffective):**
```python
## Cached Result Handling

When you receive a tool result with "cached": true:
1. The full result was too large for context and has been cached
2. You MUST immediately use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve events
3. Start with offset=0, limit=100 for the first chunk
4. Analyze the chunk and decide if more data is needed to answer the user's question
5. Fetch additional chunks if necessary (increment offset by limit)
6. DO NOT wait for the user to ask - proceed automatically with chunk fetching
```

**Problem:** Uses "should" language, no iteration algorithm, no follow-up detection rules.

**Proposed (Imperative):**

```python
## MANDATORY CACHE HANDLING RULES

### CRITICAL: These rules are NON-NEGOTIABLE. Violation causes incorrect answers.

### RULE 1: CACHED RESULT RECEPTION
When you receive a tool result with `"cached": true`:

YOU MUST IMMEDIATELY call `fetch_cached_result_chunk` with:
- cache_id: <exact value from result>
- offset: 0
- limit: 100

DO NOT:
- Respond to the user before fetching at least one chunk
- Use sample_events for analysis (samples are for preview only)
- Wait for user to ask for more data

### RULE 2: FOLLOW-UP QUESTION DETECTION
A question is a FOLLOW-UP ABOUT CACHED DATA if ANY of these are true:
- Contains reference words: "those", "these", "them", "the errors", "the logs", "the results"
- Asks for counts/aggregations: "how many", "count", "total", "breakdown"
- Requests filtering: "which ones", "find all", "show me the X ones"
- Time proximity: Asked within 5 minutes of last cache operation

When you detect a follow-up question about cached data:
- DO NOT execute a new search_logs or query_metrics call
- USE the existing cache (it IS the current dataset)
- FETCH chunks as needed to answer the question

### RULE 3: COMPLETE DATASET ITERATION (CRITICAL)
Some questions REQUIRE analyzing ALL cached events. You MUST iterate ALL chunks when:
- Question asks "how many" or "count"
- Question asks for "all" of something
- Question asks for "breakdown" or "distribution"
- Question involves aggregation (sum, average, unique values)

ITERATION ALGORITHM:
```
total_events = <from cached result summary>
chunk_size = 100
total_chunks = ceiling(total_events / chunk_size)

for offset in range(0, total_events, chunk_size):
    chunk = fetch_cached_result_chunk(cache_id, offset, chunk_size)
    # Process chunk, extract counts/data
    # DISCARD raw events from memory after processing
    # KEEP only: running totals, unique values, matched IDs

Report: "Analyzed X of Y total events. Found Z matching criteria."
```

### RULE 4: CONTEXT MEMORY MANAGEMENT
After processing each chunk:
1. Extract needed information (counts, matches, unique values)
2. FORGET the raw event data (do not keep in working memory)
3. Proceed to next chunk
4. You can ALWAYS re-fetch a chunk if needed for details

This allows you to process 10,000+ events without context overflow.

### RULE 5: RESULT ACCURACY REQUIREMENT
NEVER answer questions about cached data quantities without:
- Fetching ALL relevant chunks
- Processing EVERY event in those chunks
- Reporting how many events were analyzed

Example correct answer: "I analyzed all 432 cached events and found 47 SSN-related errors."
Example WRONG answer: "Based on the 5 sample events, I see no SSN errors."
```

### 3.2 Context Injection Enhancement

**Current Location:** `orchestrator.py` lines 440-463

**Current (Passive):**
```python
return f"""SYSTEM INSTRUCTION: The previous tool call returned a large result that was automatically cached.

CACHED RESULT INFORMATION:
- Cache ID: {guidance["cache_id"]}
- Total events cached: {guidance["total_events"]}

You MUST now fetch chunks to show the user actual log events:
...
```

**Proposed (Imperative with Algorithm):**

```python
def _get_cache_immediate_action_injection(self, guidance: dict) -> str:
    """Generate mandatory immediate action injection after cache creation."""

    total_events = guidance["total_events"]
    chunk_size = self.settings.initial_chunk_size
    total_chunks = (total_events + chunk_size - 1) // chunk_size  # ceiling division

    return f"""
###############################################################################
#                    MANDATORY IMMEDIATE ACTION REQUIRED                       #
###############################################################################

A large result ({total_events} events) has been cached. You MUST act NOW.

CACHE DETAILS:
- Cache ID: {guidance["cache_id"]}
- Total Events: {total_events}
- Chunk Size: {chunk_size}
- Total Chunks: {total_chunks}

REQUIRED IMMEDIATE ACTION:
Execute this tool call NOW (do not respond to user first):

```
fetch_cached_result_chunk(
    cache_id="{guidance["cache_id"]}",
    offset=0,
    limit={chunk_size}
)
```

After fetching, you may respond to the user with initial findings.

REMEMBER: Sample events in the summary are for PREVIEW ONLY.
You MUST fetch chunks for any real analysis.

###############################################################################
"""
```

### 3.3 Cached Result Summary Enhancement

**Current Location:** `result_cache.py` lines 32-63

**Current `to_context_dict()` Output:**
```python
{
    "cached": True,
    "cache_id": "result_xxx",
    "summary": {
        "total_events": 432,
        "time_range": {...},
        "sample_events": [...],  # 5 samples
        "event_statistics": {...}
    },
    "original_query": {...},
    "cache_info": {...},
    "instructions": "This result was cached because..."  # Single passive sentence
}
```

**Problem:** `sample_events` are too prominent, instructions are weak.

**Proposed `to_context_dict()` Output:**

```python
def to_context_dict(self) -> dict[str, Any]:
    """
    Convert to dict suitable for LLM context.

    IMPORTANT: Structure designed to guide LLM behavior:
    - Warning appears FIRST
    - Sample events are de-emphasized
    - Iteration guidance is explicit
    """
    total_chunks = (self.total_events + 99) // 100  # ceiling division with chunk_size=100

    return {
        # WARNING appears first to catch attention
        "WARNING": "This is a SUMMARY only. You MUST fetch chunks for analysis.",

        "cached": True,
        "cache_id": self.cache_id,

        # Core metadata
        "dataset": {
            "total_events": self.total_events,
            "time_range": self.time_range,
            "statistics": self.event_statistics,  # Renamed from event_statistics
        },

        # Iteration guidance (NEW)
        "iteration_info": {
            "chunk_size": 100,
            "total_chunks": total_chunks,
            "fetch_command": f"fetch_cached_result_chunk(cache_id='{self.cache_id}', offset=0, limit=100)",
            "iteration_required_for": [
                "counting events",
                "finding all matches",
                "calculating breakdowns",
                "any question with 'how many'"
            ]
        },

        # Samples de-emphasized and marked as preview
        "preview_only": {
            "note": "These samples are for PREVIEW only. Do NOT use for counting or analysis.",
            "sample_events": self.sample_events[:3],  # Reduced from 5 to 3
        },

        # Original query for context
        "original_query": {
            "tool": self.original_tool,
            "parameters": self.original_query,
        },

        # Cache metadata
        "cache_metadata": {
            "cached_at": self.cached_at,
            "expires_in_seconds": max(0, self.expires_at - int(time.time())),
        },

        # Explicit mandatory instruction (replaces weak "instructions" field)
        "MANDATORY_ACTION": (
            f"To analyze this data, you MUST call fetch_cached_result_chunk() "
            f"with cache_id='{self.cache_id}'. For counting/aggregation questions, "
            f"iterate ALL {total_chunks} chunks."
        ),
    }
```

### 3.4 Follow-Up Question Detection

This is a critical new capability. We need to help the LLM recognize when a question references cached data.

**Design: Orchestrator-Level Cache Context State**

Add new state tracking to `LLMOrchestrator`:

```python
@dataclass
class ActiveCacheContext:
    """Tracks the currently active cached dataset for follow-up detection."""

    cache_id: str
    total_events: int
    created_at: float  # Unix timestamp
    tool_name: str
    query_description: str  # Human-readable description of what was queried
    chunks_fetched: set[int] = field(default_factory=set)  # Offsets of fetched chunks

    def is_recent(self, max_age_seconds: float = 300) -> bool:
        """Check if cache is recent enough to be relevant (default 5 minutes)."""
        return (time.time() - self.created_at) < max_age_seconds

    def chunks_remaining(self, chunk_size: int = 100) -> int:
        """Calculate how many chunks haven't been fetched yet."""
        total_chunks = (self.total_events + chunk_size - 1) // chunk_size
        return total_chunks - len(self.chunks_fetched)


class LLMOrchestrator:
    def __init__(self, ...):
        # ... existing init ...

        # NEW: Active cache context tracking
        self._active_cache: ActiveCacheContext | None = None
```

**Design: Follow-Up Context Injection**

When the user asks a question and there's an active cache, inject guidance:

```python
def _get_follow_up_cache_injection(self, user_message: str) -> str | None:
    """
    Generate context injection if user question appears to reference cached data.

    Returns injection string or None if no active cache or not a follow-up.
    """
    if not self._active_cache or not self._active_cache.is_recent():
        return None

    # Heuristic detection of follow-up patterns
    follow_up_indicators = [
        # Reference pronouns
        "those", "these", "them", "that", "it",
        # Implicit references
        "the errors", "the logs", "the results", "the events",
        "the data", "the output",
        # Aggregation keywords (strong indicator)
        "how many", "count", "total", "breakdown", "distribution",
        "unique", "distinct", "summarize", "aggregate",
        # Filtering requests
        "which ones", "find all", "show me", "filter",
        "containing", "matching", "with"
    ]

    message_lower = user_message.lower()
    is_follow_up = any(indicator in message_lower for indicator in follow_up_indicators)

    # Also check for aggregation patterns (very strong signal)
    requires_iteration = any(kw in message_lower for kw in [
        "how many", "count", "total", "all", "every", "each",
        "breakdown", "distribution", "unique", "summarize"
    ])

    if not is_follow_up:
        return None

    cache = self._active_cache
    chunk_size = self.settings.initial_chunk_size
    total_chunks = (cache.total_events + chunk_size - 1) // chunk_size
    chunks_remaining = cache.chunks_remaining(chunk_size)

    injection = f"""
###############################################################################
#                 ACTIVE CACHED DATASET DETECTED                              #
###############################################################################

This question appears to reference a recent cached dataset:
- Cache ID: {cache.cache_id}
- Total Events: {cache.total_events}
- Original Query: {cache.query_description}
- Chunks Already Fetched: {len(cache.chunks_fetched)} of {total_chunks}
- Chunks Remaining: {chunks_remaining}

"""

    if requires_iteration:
        injection += f"""
YOUR QUESTION REQUIRES COMPLETE DATASET ITERATION.

You asked about "{user_message[:100]}..." which requires analyzing ALL events.

MANDATORY: Execute this iteration loop:
1. Start at offset=0 if not already fetched
2. For each chunk: extract relevant counts/data, then DISCARD raw events
3. Continue until offset >= {cache.total_events}
4. Report: "Analyzed all {cache.total_events} events. Found X matching [criteria]."

DO NOT:
- Answer based on samples or partial data
- Execute a new search_logs query (use the cached data)
- Stop iteration before processing all chunks

EXAMPLE ITERATION:
```
# You should call fetch_cached_result_chunk multiple times:
fetch_cached_result_chunk("{cache.cache_id}", offset=0, limit={chunk_size})
# Process, count, then continue...
fetch_cached_result_chunk("{cache.cache_id}", offset={chunk_size}, limit={chunk_size})
# Process, count, then continue...
# ... repeat until offset >= {cache.total_events}
```
"""
    else:
        injection += f"""
This appears to be a follow-up question. Use the cached data:
- DO NOT execute a new search_logs query
- FETCH chunks from cache_id: {cache.cache_id}
- The cache IS your current dataset
"""

    injection += """
###############################################################################
"""

    return injection
```

**Integration Point:**

In `_chat_complete()` and `_chat_stream()`, after preparing messages:

```python
# Check for follow-up cache injection
follow_up_injection = self._get_follow_up_cache_injection(user_message)
if follow_up_injection:
    messages.append({"role": "system", "content": follow_up_injection})
```

### 3.5 Progress Indication System

**Design:** Instruct LLM to report progress during multi-chunk iteration.

**System Prompt Addition:**

```
### RULE 6: PROGRESS REPORTING
When iterating through multiple chunks, report progress to the user:

FORMAT:
"Analyzing cached events... [chunk X of Y]"
"Processing events {offset} to {offset + count}... ({running_total} matches so far)"

After completion:
"Analysis complete: Processed {total} events across {chunks} chunks."

This keeps the user informed during long operations.
```

**UX Consideration:** The LLM should emit these as intermediate responses, not tool calls. This requires no code changes - just clear instruction.

---

## 4. Prompt Engineering Strategy

### 4.1 Principles Applied

| Principle | Application |
|-----------|-------------|
| **Imperative Language** | "You MUST", "DO NOT", "REQUIRED" instead of "you should", "consider" |
| **Visual Hierarchy** | `#####` borders for critical sections, ALL CAPS for keywords |
| **Explicit Algorithms** | Provide pseudo-code that LLM can follow step-by-step |
| **Negative Examples** | Show what NOT to do (wrong answers) |
| **Structural Guidance** | JSON structure guides attention (WARNING first, samples last) |
| **Repetition** | Key rules appear in system prompt, injection, AND result summary |
| **Consequences** | "Violation causes incorrect answers" makes stakes clear |

### 4.2 Why This Works

LLMs respond better to:
1. **Clear structure** - Numbered rules, labeled sections
2. **Explicit commands** - "Call X now" vs "you might want to call X"
3. **Algorithms** - Step-by-step procedures reduce ambiguity
4. **Examples** - Concrete examples beat abstract descriptions
5. **Repetition** - Critical rules repeated across multiple injection points

### 4.3 Token Budget Consideration

| Component | Estimated Tokens | Notes |
|-----------|------------------|-------|
| Enhanced system prompt | ~800 | Up from ~300 |
| Cache injection | ~400 | Up from ~200 |
| Follow-up injection | ~350 | New |
| Result summary | ~250 | Slightly larger |
| **Total overhead** | ~1,800 | Acceptable for 200K context window |

---

## 5. Example Scenarios

### Scenario 1: Initial Query with Cached Result

**User:** "Show me all errors in /aws/lambda/payment-service from the last hour"

**System Flow:**
1. `search_logs` tool returns 432 events
2. Result exceeds threshold, cached automatically
3. LLM receives enhanced summary with `MANDATORY_ACTION`
4. Context injection fires: "MANDATORY IMMEDIATE ACTION REQUIRED"
5. LLM calls `fetch_cached_result_chunk(cache_id, offset=0, limit=100)`
6. LLM presents initial findings to user

**LLM Response:**
```
I found 432 error events in the last hour. Let me show you the initial findings:

[First 100 events analysis]
- 45 timeout errors
- 32 connection refused
- 23 null pointer exceptions

The errors span from 14:00 to 15:00 UTC. Would you like me to analyze all 432 events
for a complete breakdown, or focus on a specific error type?
```

### Scenario 2: Follow-Up Counting Question

**User:** "How many of those are SSN validation errors?"

**System Flow:**
1. Follow-up detector recognizes "those" + "how many"
2. `_active_cache` exists with cache_id and 432 events
3. Follow-up injection fires with iteration requirement
4. LLM recognizes MUST iterate all chunks
5. LLM executes iteration loop:

**LLM Response:**
```
Let me analyze all 432 cached events for SSN validation errors...

Processing chunk 1 (events 0-99)... found 12 SSN errors
Processing chunk 2 (events 100-199)... found 8 SSN errors
Processing chunk 3 (events 200-299)... found 15 SSN errors
Processing chunk 4 (events 300-399)... found 9 SSN errors
Processing chunk 5 (events 400-432)... found 3 SSN errors

**Analysis Complete:** Out of 432 total error events, I found **47 SSN validation errors** (10.9%).

Common patterns in SSN errors:
- "Invalid SSN format" - 28 occurrences
- "SSN checksum failed" - 15 occurrences
- "SSN field null" - 4 occurrences

Would you like to see specific examples of these errors?
```

### Scenario 3: Different User Asks New Question

**User:** "Actually, show me metrics for the checkout service instead"

**System Flow:**
1. Follow-up detector: No reference words, different topic
2. No follow-up injection
3. LLM correctly uses `query_metrics` tool (new query)
4. Previous cache remains available if user returns to it

### Scenario 4: Context-Efficient Large Dataset

**User:** "Count all unique error messages in the results"

**System Flow:**
1. Follow-up detector recognizes "all" + "count" + "results"
2. Iteration required for unique values
3. LLM iterates with memory management:

**LLM Internal Process:**
```
Chunk 1: Extract unique messages → ["msg1", "msg2", ...], discard raw events
Chunk 2: Add new unique messages → ["msg3", ...], discard raw events
Chunk 3: Add new unique messages → [...], discard raw events
... continue until all chunks processed
Report unique count
```

**LLM Response:**
```
Analyzed all 432 events. Found **67 unique error messages**.

Top 10 most frequent:
1. "Connection timeout" - 89 occurrences
2. "Service unavailable" - 67 occurrences
...
```

---

## 6. Implementation Plan

### 6.1 Phase 1: Core Prompt Changes (Day 1)

**Files to modify:**

| File | Changes | Priority |
|------|---------|----------|
| `orchestrator.py` | Enhanced system prompt (lines 284-300) | P0 |
| `orchestrator.py` | Enhanced context injection (lines 440-463) | P0 |
| `result_cache.py` | Enhanced `to_context_dict()` (lines 32-63) | P0 |

**Estimated effort:** 2-3 hours

### 6.2 Phase 2: State Tracking (Day 1-2)

**Files to modify:**

| File | Changes | Priority |
|------|---------|----------|
| `orchestrator.py` | Add `ActiveCacheContext` dataclass | P0 |
| `orchestrator.py` | Add `_active_cache` state tracking | P0 |
| `orchestrator.py` | Update `_process_tool_result()` to set cache state | P0 |
| `orchestrator.py` | Add `_get_follow_up_cache_injection()` method | P0 |
| `orchestrator.py` | Integrate injection in `_chat_complete()` and `_chat_stream()` | P0 |

**Estimated effort:** 3-4 hours

### 6.3 Phase 3: Testing & Validation (Day 2)

**Test cases to add:**

| Test | Description |
|------|-------------|
| `test_follow_up_detection_reference_words` | "those", "these", etc. trigger injection |
| `test_follow_up_detection_aggregation` | "how many" triggers iteration requirement |
| `test_cache_state_tracking` | Active cache is tracked and updated |
| `test_cache_state_expiry` | Old cache doesn't trigger false follow-ups |
| `test_iteration_guidance_in_injection` | Algorithm appears in injection |
| `test_result_summary_structure` | WARNING first, samples minimized |

**Estimated effort:** 2-3 hours

### 6.4 Dependency Graph

```
┌────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION ORDER                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Phase 1 (No dependencies)                                    │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  1.1 Enhanced System Prompt                              │  │
│   │  1.2 Enhanced Context Injection                          │  │
│   │  1.3 Enhanced Result Summary                             │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│   Phase 2 (Depends on Phase 1)                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  2.1 ActiveCacheContext Dataclass                        │  │
│   │  2.2 State Tracking in Orchestrator                      │  │
│   │  2.3 Follow-Up Injection Logic                           │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│   Phase 3 (Depends on Phase 2)                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  3.1 Unit Tests                                          │  │
│   │  3.2 Integration Tests                                   │  │
│   │  3.3 Manual E2E Validation                               │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Acceptance Criteria

### 7.1 Functional Requirements

| ID | Requirement | Verification Method |
|----|-------------|---------------------|
| AC-1 | LLM fetches at least one chunk immediately after cached result | Tool sidebar shows `fetch_cached_result_chunk` |
| AC-2 | LLM recognizes "how many of those" as follow-up | Logs show follow-up injection |
| AC-3 | LLM iterates ALL chunks when counting | Logs show sequential fetch calls |
| AC-4 | LLM reports accurate count after full iteration | Manual verification |
| AC-5 | LLM does NOT use samples for counting questions | Response says "analyzed X events" not "based on samples" |
| AC-6 | New queries use query tools, not cache | Logs show `search_logs`, not `fetch_cached_result_chunk` |

### 7.2 Test Scenarios for Validation

**Scenario A: Basic Counting**
```
1. User: "Show me errors from the last hour" → 432 events cached
2. User: "How many are SSN errors?"
3. Expected: LLM iterates all 5 chunks, reports "47 SSN errors out of 432"
4. Verify: Tool sidebar shows 5 fetch calls with increasing offsets
```

**Scenario B: Unique Value Counting**
```
1. User: "Show me errors" → 200 events cached
2. User: "What are the unique error types?"
3. Expected: LLM iterates all chunks, builds unique set, reports count
4. Verify: Response includes "analyzed 200 events"
```

**Scenario C: New Query Detection**
```
1. User: "Show me errors" → Cached
2. User: "Show me metrics for checkout service"
3. Expected: LLM uses query_metrics, NOT fetch_cached_result_chunk
4. Verify: Tool sidebar shows query_metrics call
```

### 7.3 Non-Functional Requirements

| ID | Requirement | Target | Verification |
|----|-------------|--------|--------------|
| NFR-1 | Prompt overhead | <2000 tokens | Token counting |
| NFR-2 | Follow-up detection latency | <10ms | Timing logs |
| NFR-3 | No false positives for new queries | 0% | Test suite |
| NFR-4 | Context doesn't overflow during iteration | <100K tokens | Budget tracker |

---

## 8. Risk Analysis

### 8.1 Identified Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM still ignores instructions | Medium | High | Multiple injection points, visual emphasis, test thoroughly |
| False positive follow-up detection | Low | Medium | Conservative heuristics, allow override via new query keywords |
| Token budget exceeded by injections | Low | Medium | Keep injections focused, measure during testing |
| Iteration takes too long for user | Medium | Medium | Progress reporting, allow user interrupt |
| Cache expires during iteration | Low | Low | Graceful error handling already exists |

### 8.2 Risk Mitigation Details

**Risk: LLM Still Ignores Instructions**

Even with enhanced prompts, LLMs can be unpredictable. Mitigations:

1. **Multi-layer redundancy**: Rules appear in system prompt, injection, AND result summary
2. **Visual emphasis**: `#####` borders, ALL CAPS, "MANDATORY" language
3. **Structured JSON**: WARNING appears first in result summary
4. **Testing**: Extensive test scenarios to catch edge cases
5. **Monitoring**: Log whether LLM calls fetch tool after cached result

**Risk: False Positive Follow-Up Detection**

User might say "How many log groups are there?" which contains "how many" but isn't about cached data.

Mitigation:
1. **Require reference word + aggregation**: Both must be present
2. **Topic detection**: If message mentions different service/resource, skip injection
3. **Time decay**: Cache context expires after 5 minutes
4. **User can override**: "Run a new query for..." bypasses cache

### 8.3 Contingency Plan

If the enhanced prompts don't achieve >90% compliance:

1. **Escalation**: Add a "retry nudge" similar to intent detection
   - After LLM response, check if it answered counting question without fetching chunks
   - Inject: "You answered a counting question using only samples. This is INCORRECT. Please iterate all chunks and provide accurate count."

2. **Structural enforcement**: Modify tool execution to auto-trigger chunk fetch
   - If tool returns cached=true, orchestrator auto-calls fetch_cached_result_chunk
   - Result appears in context as if LLM called it

3. **UI indicator**: Add "Data Coverage" indicator
   - Show "Analyzed: 5 of 432 events" when LLM only sees samples
   - User can see incompleteness and prompt LLM to continue

---

## Appendix: Complete Prompt Templates

### A.1 Enhanced System Prompt Section

```python
CACHE_HANDLING_PROMPT = """
## MANDATORY CACHE HANDLING RULES

### CRITICAL: These rules are NON-NEGOTIABLE. Violation causes INCORRECT answers.

### RULE 1: CACHED RESULT RECEPTION
When you receive a tool result with `"cached": true`:

YOU MUST IMMEDIATELY call `fetch_cached_result_chunk` with:
- cache_id: <exact value from result>
- offset: 0
- limit: 100

DO NOT:
- Respond to the user before fetching at least one chunk
- Use sample_events for analysis (samples are for PREVIEW ONLY)
- Wait for user to ask for more data

### RULE 2: FOLLOW-UP QUESTION DETECTION
A question is a FOLLOW-UP ABOUT CACHED DATA if ANY of these are true:
- Contains reference words: "those", "these", "them", "the errors", "the logs", "the results"
- Asks for counts/aggregations: "how many", "count", "total", "breakdown"
- Requests filtering: "which ones", "find all", "show me the X ones"

When you detect a follow-up question about cached data:
- DO NOT execute a new search_logs or query_metrics call
- USE the existing cache (it IS your current dataset)
- FETCH chunks as needed to answer the question completely

### RULE 3: COMPLETE DATASET ITERATION (MOST CRITICAL)
Some questions REQUIRE analyzing ALL cached events. You MUST iterate ALL chunks when:
- Question asks "how many" or "count"
- Question asks for "all" of something
- Question asks for "breakdown" or "distribution"
- Question involves aggregation (sum, average, unique values)

ITERATION ALGORITHM:
```
total_events = <from cached result summary>
chunk_size = 100
current_offset = 0
running_results = {} # Your counters/aggregators

while current_offset < total_events:
    chunk = fetch_cached_result_chunk(cache_id, current_offset, chunk_size)
    # Process chunk: update running_results
    # DISCARD raw events from memory (keep only running_results)
    current_offset += chunk_size

report("Analyzed {total_events} events. Found {running_results}.")
```

### RULE 4: CONTEXT MEMORY MANAGEMENT
After processing each chunk:
1. Extract needed information (counts, matches, unique values)
2. FORGET the raw event data (do not keep in working memory)
3. KEEP only: running totals, unique value sets, matched event IDs
4. Proceed to next chunk

This allows processing 10,000+ events without context overflow.

### RULE 5: RESULT ACCURACY REQUIREMENT
NEVER answer questions about cached data quantities without:
- Fetching ALL relevant chunks
- Processing EVERY event in those chunks
- Reporting exact count of events analyzed

CORRECT: "I analyzed all 432 cached events and found 47 SSN-related errors."
WRONG: "Based on the 5 sample events, I don't see any SSN errors."

### RULE 6: PROGRESS REPORTING
When iterating through multiple chunks, report progress:

"Analyzing cached events..."
"Processed events 0-99: found 12 matches so far"
"Processed events 100-199: found 8 more (20 total)"
...
"Analysis complete: Processed 432 events, found 47 total matches."

The fetch_cached_result_chunk tool supports:
- offset: Starting index (0-based)
- limit: Number of events (max 200, default 100)
- filter_pattern: Text to search for (case-insensitive)
- time_start/time_end: Unix timestamps to filter by time range
"""
```

### A.2 Immediate Action Injection Template

```python
IMMEDIATE_ACTION_TEMPLATE = """
###############################################################################
#                    MANDATORY IMMEDIATE ACTION REQUIRED                       #
###############################################################################

A large result ({total_events} events) has been cached.

CACHE DETAILS:
- Cache ID: {cache_id}
- Total Events: {total_events}
- Chunk Size: {chunk_size}
- Total Chunks Needed: {total_chunks}

REQUIRED IMMEDIATE ACTION - Execute NOW before responding to user:

```
fetch_cached_result_chunk(
    cache_id="{cache_id}",
    offset=0,
    limit={chunk_size}
)
```

After fetching initial chunk, you may respond to the user with findings.

REMEMBER:
- Sample events in summary are for PREVIEW ONLY
- You MUST fetch chunks for ANY real analysis
- For counting questions, iterate ALL {total_chunks} chunks

###############################################################################
"""
```

### A.3 Follow-Up Detection Injection Template

```python
FOLLOW_UP_TEMPLATE = """
###############################################################################
#                    ACTIVE CACHED DATASET DETECTED                           #
###############################################################################

Your question appears to reference a cached dataset:

CACHE CONTEXT:
- Cache ID: {cache_id}
- Total Events: {total_events}
- Original Query: {query_description}
- Cache Age: {age_seconds} seconds
- Chunks Already Fetched: {chunks_fetched_count} of {total_chunks}

{iteration_guidance}

IMPORTANT:
- DO NOT execute a new search_logs or query_metrics
- USE fetch_cached_result_chunk to access the data
- The cache IS your current dataset

###############################################################################
"""

ITERATION_GUIDANCE_TEMPLATE = """
YOUR QUESTION REQUIRES COMPLETE ITERATION.

You asked: "{user_question_snippet}..."

This requires analyzing ALL {total_events} events to give an accurate answer.

EXECUTE THIS LOOP:
```
for offset in [0, 100, 200, ..., until >= {total_events}]:
    chunk = fetch_cached_result_chunk("{cache_id}", offset, 100)
    # Process chunk, update running totals
    # DISCARD raw events after processing
```

REPORT FORMAT:
"Analyzed all {total_events} events. Found X matching [criteria]."

DO NOT:
- Answer based on samples or partial data
- Stop iteration early
- Say "based on the available data" (get ALL data)
"""
```

---

## Document Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Author | Saanvi (Senior Software Architect) | Draft Complete | 2026-02-13 |
| Reviewer | George (Technical Project Manager) | Pending Review | |
| Approver | User (Product Owner) | Pending Approval | |

---

**END OF DESIGN DOCUMENT**
