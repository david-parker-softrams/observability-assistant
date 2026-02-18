# Investigation: Large Log Query Results & Agent Context Window Overflow

**Investigation Date:** February 12, 2026
**Investigator:** Hans (Code Librarian)
**Status:** Complete

---

## Executive Summary

The current implementation **does NOT have any mechanisms to handle context window overflow** when CloudWatch queries return large amounts of data. Large query results are directly serialized to JSON and stuffed into the LLM's message history without any truncation, chunking, or pagination. This creates a critical bottleneck:

1. **CloudWatch queries can return up to 1,000 log events** per tool call
2. **Each log event** contains full message text (can be several KB each)
3. **Results are converted to JSON** and stored in conversation history **without size limits**
4. **All previous messages remain in the context** during the conversation loop
5. **Models have hard context limits** (e.g., Claude 3.5 Sonnet: 200K tokens)

### Problem Chain
```
User Query → CloudWatch Query (1,000 events) → JSON Serialization
    ↓
Tool Result Message (hundreds of KB) → Conversation History
    ↓
Next LLM Call (includes ALL previous messages)
    ↓
Context Window Overflow ✗
```

---

## 1. Current Architecture

### 1.1 Data Flow: CloudWatch Query → Agent

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Input                                  │
│                    "Find error logs"                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│            LLMOrchestrator.chat() / chat_stream()               │
│  - Adds user message to conversation_history                    │
│  - Calls LLM with all history + system prompt                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              LLM Response (with tool_calls)                      │
│  - fetch_logs(log_group, start_time, filter_pattern, limit)    │
│  - search_logs(log_group_patterns, search_pattern, limit)      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         Orchestrator._execute_tool_calls()                       │
│  - Executes tool from ToolRegistry                              │
│  - Tool execution occurs (CloudWatch query)                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│      CloudWatchDataSource.fetch_logs() / search_logs()          │
│  - Queries CloudWatch API (paginated)                           │
│  - Returns list[dict] with log events                           │
│  - Max 1,000 events per call                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         FetchLogsTool.execute() / SearchLogsTool.execute()      │
│  - Sanitizes logs (removes PII)                                 │
│  - Returns dict with:                                           │
│    - success: bool                                              │
│    - events: list[dict] (all 1,000 events!)                    │
│    - count: int                                                 │
│    - metadata: various fields                                   │
│    - sanitization: redaction summary                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│    Orchestrator._execute_tool_calls() [result handling]         │
│  - Wraps result in {"tool_call_id": "...", "result": {...}}    │
│  - Serializes to JSON:                                          │
│      json.dumps(tool_result["result"])                          │
│  - Creates tool_message with full JSON as "content"             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│      Conversation History Management (CRITICAL ISSUE)           │
│  - self.conversation_history.append(assistant_message)          │
│  - self.conversation_history.append(tool_message)               │
│  - messages.append(tool_message)  # For next LLM call           │
│  ⚠️  NO SIZE LIMIT CHECKING                                     │
│  ⚠️  NO TRUNCATION                                              │
│  ⚠️  NO CHUNKING                                                │
│  ⚠️  Entire history sent to LLM on next iteration               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│      Next LLM Call                                               │
│  - Messages list includes:                                      │
│    1. System prompt (large - contains log group context)        │
│    2. All previous user messages                                │
│    3. All previous assistant responses                          │
│    4. ALL previous tool results (including HUGE JSON)           │
│    5. New user message/system prompt injection                  │
│  ⚠️  No token counting before sending                           │
│  ⚠️  LLM might refuse or truncate                               │
│  ✗  CONTEXT OVERFLOW HERE                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Query Result Sizes

From the tool definitions in `cloudwatch_tools.py`:

**FetchLogsTool:**
```python
"limit": {
    "type": "integer",
    "description": "Maximum number of log events to return (default: 100, max: 1000)",
    "minimum": 1,
    "maximum": 1000,  # ← UP TO 1,000 events per call!
}
```

**SearchLogsTool:**
```python
"limit": {
    "type": "integer",
    "description": "Maximum total number of log events to return (default: 100, max: 1000)",
    "minimum": 1,
    "maximum": 1000,  # ← UP TO 1,000 events per call!
}
```

**Example Large Result:**
- 1,000 log events × ~500 bytes per event = ~500 KB of log data
- + JSON overhead (field names, quotes, escaping) = ~600-700 KB total
- JSON serialization in tool message: `json.dumps(result)` = ~700 KB string
- In conversation history: stored as-is

### 1.3 Where Results Are Serialized

**File:** `src/logai/core/orchestrator.py` (Lines 513-521)

```python
# Add tool results as separate messages
for tool_result in tool_results:
    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),  # ← FULL JSON, NO LIMIT
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)
```

This pattern appears **twice** in the file:
- Line 513-521 (in `_chat_complete()`)
- Line 761-769 (in `_chat_stream()`)

**Key Issue:** The entire result dictionary is JSON-serialized with no size checks or truncation.

---

## 2. Configuration & Limits

### 2.1 Settings (No Result Size Limits)

**File:** `src/logai/config/settings.py`

Current settings related to size/tokens:

```python
max_tool_iterations: int = Field(
    default=10,
    description="Maximum number of tool calls allowed in a single conversation turn. Prevents infinite loops.",
    ge=1,
    le=100,
)

cache_max_size_mb: int = Field(
    default=500,
    description="Maximum cache size in megabytes",
    gt=0,
    le=10000,
)
```

**Missing:**
- ❌ `max_result_size_bytes` or `max_result_size_mb`
- ❌ `max_context_size_tokens`
- ❌ `result_truncation_threshold`
- ❌ `enable_result_chunking`
- ❌ Token counting configuration

### 2.2 LLM Provider Token Limits

**File:** `src/logai/providers/llm/`

Models have hard token limits but are not enforced:

- **Claude 3.5 Sonnet** (anthropic): 200K tokens
- **GPT-4 Turbo** (openai): 128K tokens
- **Claude Opus 4.5** (github-copilot): 200K tokens (estimated)
- **Llama 3.1** (ollama): 8K-128K depending on variant

**Current Implementation:**
- Providers accept `max_tokens` parameter for *output* only
- No input token counting implemented
- No context window validation before sending requests

---

## 3. Problem Areas & Bottlenecks

### 3.1 No Size Checking

**Issue:** Tool results are added to messages without any size validation.

**Location:** `orchestrator.py:513-521` and `766-768`

```python
# This happens regardless of result size:
tool_message: dict[str, Any] = {
    "role": "tool",
    "tool_call_id": tool_result["tool_call_id"],
    "content": json.dumps(tool_result["result"]),  # Could be 700+ KB
}
self.conversation_history.append(tool_message)
messages.append(tool_message)
```

**Impact:** A single large query result can consume 25-50% of context window (200K tokens).

### 3.2 All History Retained

**Issue:** Entire conversation history is always included in the next LLM call.

**Location:** `orchestrator.py:453-461` (in `_chat_complete`)

```python
# Prepare messages with system prompt
messages = [
    {"role": "system", "content": self._get_system_prompt()}
] + self.conversation_history  # ← Everything, every time

# Check for pending context injection
pending_injection = self._get_pending_context_injection()
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})
```

**Impact:**
- After 2-3 tool calls, history becomes massive
- Conversation loop multiplies context usage
- Streaming responses also add accumulated history

### 3.3 No Pagination or Chunking

**Issue:** When large results come back, they're not split into manageable chunks.

**Current Behavior:**
- Tool returns all 1,000 events at once
- Results are passed to LLM as single large message
- No mechanism to process results incrementally

### 3.4 JSON Serialization Overhead

**Issue:** Full nested result objects are serialized to JSON strings.

**Example result structure:**
```python
{
    "success": True,
    "log_group": "/aws/lambda/my-function",
    "events": [
        {
            "timestamp": 1707748800000,
            "message": "START RequestId: abc123...",  # Can be long
            "log_stream": "2024/02/12/[$LATEST]xyz",
            "event_id": "..."
        },
        # ... 999 more events
    ],
    "count": 1000,
    "time_range": {"start": ..., "end": ...},
    "filter_pattern": "ERROR",
    "sanitization": {
        "enabled": True,
        "redactions": [...],  # List of all redactions
        "summary": {...}
    }
}
```

**Impact:**
- JSON field names repeated 1,000+ times
- Deep nesting adds overhead
- Stringified timestamps and numbers take extra space

### 3.5 Error Messages Don't Help

**Issue:** When context overflows, users get cryptic errors from LLM providers.

**Potential Errors:**
- `InvalidRequestError: Message too large`
- `RateLimitError: Request timeout`
- Truncated responses from LLM
- Tool calling fails due to corrupted context

---

## 4. Existing Mechanisms

### 4.1 Tool Result Limits (Only for UI Display)

**File:** `src/logai/ui/widgets/tool_sidebar.py` (Lines 237-255)

The UI truncates results **only for display**, not for context:

```python
# Show first 10 log group names with full names
preview_count = min(10, len(log_groups))
for i in range(preview_count):
    group = log_groups[i]
    name = group.get("name", str(group))
    result_node.add_leaf(f"  • {name}")

# Add expandable node for remaining items
if len(log_groups) > preview_count:
    remaining = len(log_groups) - preview_count
    more_node = result_node.add(
        f"▶ Show {remaining} more",
        expand=False,  # Collapsed by default
    )
```

**Key Point:** This is UI-only truncation. The **full result is still passed to the agent**.

### 4.2 Cache Management

**File:** `src/logai/cache/` (manager.py, sqlite_store.py)

Cache has size limits but is **separate from context window**:
- `cache_max_size_mb`: 500 MB default
- TTL-based eviction
- LRU eviction

**Limitation:** Cache doesn't prevent large results from being added to context.

### 4.3 PII Sanitization (Reduces Size Slightly)

**File:** `src/logai/core/sanitizer.py`

Sanitization removes PII but doesn't significantly reduce result size:
- Replaces actual values with placeholders
- Could *increase* size if placeholders are longer
- Not designed for context window management

### 4.4 Retry Logic (Can Worsen Problem)

**File:** `src/logai/core/orchestrator.py` (Lines 138-206)

The retry logic can make context overflow worse:
- On empty results, adds **more tool calls**
- Each retry adds more messages to history
- Retry prompts add additional context

**Example Scenario:**
1. First query: 500 KB result
2. Empty result retry: Adds another system prompt (~2 KB) + another attempt
3. Third attempt: History now has ~600 KB
4. Fourth attempt with broader search: Another 800 KB result
5. Total context: ~1.4 MB in history, plus system prompt, plus new query

---

## 5. Code Examples: The Problem in Action

### 5.1 Full Result Path Without Limits

**Step 1: Tool execution returns large result**
```python
# In FetchLogsTool.execute() (cloudwatch_tools.py:210)
events = await self.datasource.fetch_logs(
    log_group=log_group,
    start_time=start_time,
    end_time=end_time,
    filter_pattern=filter_pattern,
    limit=limit,  # Could be 1,000!
)

result = {
    "success": True,
    "log_group": log_group,
    "events": sanitized_events,  # 1,000 events, 500+ KB
    "count": len(sanitized_events),  # 1,000
    "time_range": {...},
    "filter_pattern": filter_pattern,
    "sanitization": {...},
}

return result  # Returns as dict
```

**Step 2: Orchestrator receives result**
```python
# In Orchestrator._execute_tool_calls() (orchestrator.py:974)
result = await self.tool_registry.execute(function_name, **function_args)

# result is the full dict from above, now ~500+ KB
results.append({"tool_call_id": tool_call_id, "result": result})
```

**Step 3: Result is serialized to JSON with no limits**
```python
# In Orchestrator._chat_complete() (orchestrator.py:513-521)
for tool_result in tool_results:
    # tool_result["result"] is still the full 500+ KB dict
    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),  # ← NOW 600+ KB string
    }
    self.conversation_history.append(tool_message)  # ← Stored forever
    messages.append(tool_message)  # ← Sent to LLM immediately
```

**Step 4: Full history sent to LLM**
```python
# In Orchestrator._chat_complete() (orchestrator.py:725-726)
llm_result = await self.llm_provider.chat(
    messages=messages,  # ← Includes ALL previous messages + new 600+ KB result
    tools=tools,
    stream=False
)
# If context is 200K tokens and this request is already at 180K+ tokens,
# LLM fails or truncates
```

### 5.2 No Token Counting

Current implementation doesn't count tokens:
```python
# This happens WITHOUT ANY TOKEN COUNT CHECK:
messages.append(tool_message)

# Just send it, hope for the best:
llm_result = await self.llm_provider.chat(messages=messages, tools=tools)
```

### 5.3 No Result Chunking

Tool results are never split:
```python
# All 1,000 events sent as single message:
"events": [
    {"timestamp": ..., "message": "..."},  # Event 1
    {"timestamp": ..., "message": "..."},  # Event 2
    # ... 998 more ...
    {"timestamp": ..., "message": "..."},  # Event 1000
]

# To properly handle this, we'd need:
# - Split into chunks (e.g., 100 events per chunk)
# - Process each chunk separately
# - Let LLM synthesize across chunks
# BUT THIS DOESN'T EXIST YET
```

---

## 6. Configuration Gaps

### 6.1 Missing Settings

Should exist in `config/settings.py`:

```python
# Result size management
max_result_size_bytes: int = Field(
    default=50000,  # 50 KB per result
    description="Maximum size of individual tool results in bytes"
)

max_result_size_mb: int = Field(
    default=5,  # 5 MB total per conversation
    description="Maximum total size of all tool results in a conversation"
)

# Context window management
max_context_tokens: int = Field(
    default=180000,  # Leave 20K for response
    description="Maximum context tokens to use (model limit - safety margin)"
)

enable_result_truncation: bool = Field(
    default=True,
    description="Truncate large results to fit context window"
)

result_truncation_lines: int = Field(
    default=100,
    description="Number of lines to show before truncation"
)

# Chunking/pagination
enable_result_chunking: bool = Field(
    default=False,
    description="Split large results into chunks for incremental processing"
)

max_events_per_result: int = Field(
    default=100,
    description="Maximum number of log events per result message"
)
```

### 6.2 Missing Token Counting

Should exist in `providers/llm/`:

```python
# Track token usage
class TokenCounter:
    @staticmethod
    def count_tokens(text: str, model: str) -> int:
        """Estimate token count for text."""
        # Could use tiktoken for OpenAI models
        # Implement estimate for other models
        pass

    @staticmethod
    def count_message_tokens(messages: list, model: str) -> int:
        """Count total tokens in message list."""
        pass

    @staticmethod
    async def validate_context_size(
        messages: list,
        model: str,
        safety_margin: int = 20000
    ) -> tuple[bool, int, int]:
        """Check if messages fit in context window."""
        # Returns (fits, current_tokens, max_tokens)
        pass
```

---

## 7. Error Scenarios

### 7.1 Scenario: Multiple Large Queries

```
User: "Search for all errors in the last 7 days"
LLM: "I'll search for errors"
  → search_logs() returns 1,000 errors (600 KB)
  → Context now: system_prompt + user_msg + assistant_msg + result = ~800 KB

User: "Now search for warnings"
LLM: "I'll also search for warnings"
  → search_logs() returns 1,000 warnings (600 KB)
  → Context now: ~1.4 MB (previous + system + assistant + new result)

User: "Show me patterns"
LLM: "Let me analyze..."
  → Context is now at limit, LLM's context window is exceeded ✗
```

### 7.2 Scenario: Retry Loop Explosion

```
User: "Find RequestId 12345"
LLM: fetch_logs(filter_pattern="12345")
  → Returns 0 results
  → Retry triggered (empty result detection)

LLM: "Expanding search..." + system prompt for retry
  → fetch_logs(filter_pattern="RequestId") [broader]
  → Returns 900 results (550 KB)
  → Context: ~800 KB

LLM: "Still searching..." + another retry prompt
  → search_logs() across multiple groups
  → Returns 1,000 results (600 KB)
  → Context: ~1.4 MB

At 4th attempt: Context overflow → Failure
```

### 7.3 Scenario: Token Limit Enforcement

What happens when result doesn't fit:

```python
# No validation, so this happens:
messages = [system, user1, assistant1, result1_600kb, user2, ...]
# Try to send to LLM with 200K token limit

# Possible outcomes:
1. LLM returns: "Request too large" (InvalidRequestError)
2. LLM truncates silently → partial analysis
3. Request times out → 429 rate limit
4. Message gets split incorrectly → malformed JSON
```

---

## 8. Specific File Issues

### 8.1 orchestrator.py - Lines 513-521 & 761-769

**Issue:** Tool results added to history without any size limit

```python
# CURRENT (NO LIMITS):
for tool_result in tool_results:
    tool_message: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),  # ← NO SIZE CHECK
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)

# SHOULD BE (PSEUDOCODE):
for tool_result in tool_results:
    result_json = json.dumps(tool_result["result"])

    # Check size
    if len(result_json.encode('utf-8')) > max_result_size:
        result_json = truncate_or_chunk_result(result_json)

    # Check context window
    if context_would_overflow(messages, result_json):
        # Option 1: Truncate result
        # Option 2: Split into chunks
        # Option 3: Summarize result
        # Option 4: Reject with error
        pass

    tool_message = {"role": "tool", "tool_call_id": ..., "content": result_json}
    self.conversation_history.append(tool_message)
    messages.append(tool_message)
```

### 8.2 cloudwatch_tools.py - Lines 200-204

**Issue:** Tools allow up to 1,000 results per call

```python
# fetch_logs parameter:
"limit": {
    "type": "integer",
    "description": "Maximum number of log events to return (default: 100, max: 1000)",
    "minimum": 1,
    "maximum": 1000,  # ← This can generate 500+ KB results
}

# Current default (100) is better than max (1000)
# But should be lower for context-aware systems
```

### 8.3 settings.py - Missing Sections

**Issue:** No configuration for result size management

```python
# MISSING entirely:
max_result_size_bytes
max_context_tokens
enable_result_truncation
enable_result_chunking
max_events_per_result
```

---

## 9. Flow Diagram: Where Overflow Occurs

```
CloudWatch API
    ↓
fetch_logs(limit=1000)  [No size limit]
    ↓
Returns: list[1000 dict] ~500-600 KB
    ↓
Tool wraps in result dict ~600-700 KB
    ↓
Orchestrator serializes to JSON ~700+ KB string
    ↓
Added to conversation_history (persisted)
    ↓
Added to messages list (sent to LLM) ← OVERFLOW RISK HERE
    ↓
LLMProvider.chat(messages=...)
    ↓
No token count check before sending ✗
    ↓
LLM receives oversized context → FAILS
```

---

## 10. Summary: Key Findings

| Aspect | Status | Details |
|--------|--------|---------|
| **Query Result Limits** | ❌ No limits | Up to 1,000 events per query (500+ KB) |
| **Result Truncation** | ⚠️ UI only | Sidebar truncates for display, not context |
| **Result Chunking** | ❌ Not implemented | All results sent as single message |
| **Context Window Validation** | ❌ Not implemented | No token counting before sending |
| **History Management** | ❌ Unlimited | All messages kept forever in history |
| **Retry Safety** | ⚠️ Can worsen | Retry logic can increase context usage |
| **Size Configuration** | ❌ Missing | No settings for result size limits |
| **Error Handling** | ⚠️ Silent failures | LLM errors not caught gracefully |
| **Token Counting** | ❌ Not implemented | No per-provider token estimation |
| **Message Filtering** | ❌ Not implemented | Old messages never pruned from history |

---

## 11. Recommendations (High-Level)

To resolve this issue, we need:

### Phase 1: Detection & Limits
- [ ] Add token counting for all LLM providers
- [ ] Add result size limits to settings
- [ ] Validate context before sending to LLM
- [ ] Reject oversized results with clear error messages

### Phase 2: Truncation
- [ ] Truncate large results to fit context window
- [ ] Show user that results were truncated
- [ ] Provide way to request specific subset of results

### Phase 3: Chunking
- [ ] Split large results into smaller chunks
- [ ] Process chunks sequentially or in parallel
- [ ] Let LLM synthesize across chunks

### Phase 4: History Management
- [ ] Implement sliding window for conversation history
- [ ] Archive old messages (not in active context)
- [ ] Allow user to start new conversation turn

### Phase 5: Smart Defaults
- [ ] Lower default query limits (100 instead of 1,000)
- [ ] Implement adaptive limits based on context
- [ ] Better retry strategies that don't compound context

---

## Appendix: File References

### Core Files with Issues
1. `src/logai/core/orchestrator.py` (Lines 513-521, 761-769)
   - Tool result handling without size limits

2. `src/logai/config/settings.py` (Missing sections)
   - No result size configuration
   - No token limit settings

3. `src/logai/core/tools/cloudwatch_tools.py` (Lines 200-204, 387-390)
   - Tool parameters allow up to 1,000 results

4. `src/logai/providers/llm/base.py` (No token counting)
   - LLMResponse class has no size info
   - No token counting utilities

### Related Files
- `src/logai/providers/datasources/cloudwatch.py` (Lines 244, 266)
- `src/logai/ui/widgets/tool_sidebar.py` (Lines 237-255) - UI truncation only
- `src/logai/cache/` - Cache management (separate from context)

---

**End of Investigation Report**
