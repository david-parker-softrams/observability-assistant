# Cache Fetch Tool - Sidebar Display Behavior

**Question:** When the agent pulls from the cache, will that show as a tool call in the side pane?

**Answer:** ✅ **YES** - Cache fetch operations will appear in the tool calls sidebar.

---

## How It Works

### 1. Tool Registration

The `FetchCachedResultTool` is registered in the tool registry like any other tool:

```python
# From src/logai/cli.py line 362-367
ToolRegistry.register(
    FetchCachedResultTool(
        result_cache=result_cache,
        metrics_collector=metrics_collector,
    )
)
```

**Tool Name:** `fetch_cached_result_chunk`

---

### 2. Tool Execution Flow

When the LLM decides to fetch cached results, the orchestrator tracks it like any other tool call:

```python
# From src/logai/core/orchestrator.py line 1318-1337
# 1. Create PENDING record
record = ToolCallRecord(
    id=tool_call_id,
    name=function_name,  # "fetch_cached_result_chunk"
    arguments=function_args,
    status=ToolCallStatus.PENDING,
)
self._notify_tool_call(record)  # ← Sends to sidebar

# 2. Update to RUNNING
record.status = ToolCallStatus.RUNNING
self._notify_tool_call(record)  # ← Updates sidebar

# 3. Execute tool
result = await self.tool_registry.execute(function_name, **function_args)

# 4. Update to SUCCESS
record.status = ToolCallStatus.SUCCESS
record.result = result
record.completed_at = datetime.now()
self._notify_tool_call(record)  # ← Final update to sidebar
```

---

### 3. Sidebar Display

The tool call will appear in the right-hand sidebar with:

**Display Format:**
```
✓ fetch_cached_result_chunk
├─ Status: success
├─ Time: 17:56:13
├─ Duration: 19ms
├─ Args: cache_id=result_953cb27301cbbd58, offset=0, limit=100
└─ Result: Found 100 events
   ├─ [17:44:49] {"name":"App3 Imp"...}
   ├─ [17:44:18] {"name":"App3 Imp"...}
   ├─ [17:25:10] {"name":"App3 Imp"...}
   ├─ [17:13:11] {"name":"App3 Imp"...}
   ├─ [17:04:49] {"name":"App3 Imp"...}
   └─ ▶ Show 95 more (collapsed)
```

**Components:**
- ✓ - Success icon (or ⏳ for running, ✗ for error)
- Tool name: `fetch_cached_result_chunk`
- Status: `pending` → `running` → `success`/`error`
- Duration: Time taken to fetch from SQLite cache (typically <50ms)
- Arguments: All parameters passed (cache_id, offset, limit, filters)
- Result: Formatted event list with expandable nodes

---

### 4. Result Display Logic

From `src/logai/ui/widgets/tool_sidebar.py`:

```python
# Line 257-289: _add_log_events_node
def _add_log_events_node(parent_node, events):
    """Add log events with expandable list for large datasets."""

    # Show summary
    result_node = parent_node.add(f"Result: Found {len(events)} events")

    # Show first 5 events
    preview_count = min(5, len(events))
    for i in range(preview_count):
        event = events[i]
        self._add_single_event(result_node, event)

    # Add expandable node for remaining events
    if len(events) > preview_count:
        remaining = len(events) - preview_count
        more_node = result_node.add(
            f"▶ Show {remaining} more",
            expand=False,  # Collapsed by default
        )
```

**Key Features:**
- First 5 events shown by default
- Remaining events hidden behind "▶ Show N more" (expandable)
- Full messages displayed (no truncation)
- Timestamps formatted as HH:MM:SS

---

## Example Workflow

### User Query:
```
"Search for errors in ECS logs for the past 48 hours"
```

### What Appears in Sidebar:

**1. Initial Search Tool**
```
✓ search_logs
├─ Status: success
├─ Time: 17:35:07
├─ Duration: 1250ms
├─ Args: log_group_patterns=["/aws/ecs/"], search_pattern="ERROR", start_time="48h ago"
└─ Result: Cached (100 events)
```

**2. Cache Fetch Tool (triggered by LLM)**
```
✓ fetch_cached_result_chunk
├─ Status: success
├─ Time: 17:56:12
├─ Duration: 19ms
├─ Args: cache_id=result_953cb27301cbbd58, offset=0, limit=100
└─ Result: Found 100 events
   ├─ [01:11:04] {"name":"App3 Imp","err":{"message":"Unexpected token..."}}
   ├─ [01:08:58] {"name":"App3 Imp","err":{"message":"Unexpected token..."}}
   ├─ [18:25:10] {"name":"App3 Imp","err":{"message":"Obfuscated SSN..."}}
   ├─ [18:13:11] {"name":"App3 Imp","err":{"message":"Obfuscated SSN..."}}
   ├─ [17:44:49] {"name":"App3 Imp","msg":"SES Error"}}
   └─ ▶ Show 95 more
```

---

## Why This Is Useful

### Visibility Benefits

1. **Transparency** - User sees exactly when cache is being used vs fresh queries
2. **Performance Insight** - Cache fetches are fast (10-50ms) vs fresh queries (500-5000ms)
3. **Debugging** - Can see cache_id values and verify they're correct (23 chars)
4. **Data Validation** - Can expand events to verify correct data was cached

### Performance Comparison

**Fresh CloudWatch Query:**
```
✓ search_logs
├─ Duration: 2847ms  ← Slow (network + AWS API)
└─ Result: Found 100 events
```

**Cache Fetch:**
```
✓ fetch_cached_result_chunk
├─ Duration: 19ms  ← Fast (local SQLite)
└─ Result: Found 100 events
```

**Speedup:** 149x faster! 🚀

---

## Additional Sidebar Features

### Status Icons
- ◯ (pending) - Tool queued but not started
- ⏳ (running) - Tool currently executing
- ✓ (success) - Tool completed successfully
- ✗ (error) - Tool failed

### Error Display
If cache fetch fails (e.g., expired, corrupted):
```
✗ fetch_cached_result_chunk
├─ Status: error
├─ Time: 18:05:22
├─ Duration: 12ms
├─ Args: cache_id=result_abc123def456789a, offset=0, limit=100
└─ Error: Cache miss: No entry found for cache_id result_abc123def456789a
```

### Expandable Results
- Click "▶ Show N more" to expand remaining events
- All messages shown without truncation
- JSON is pretty-printed for readability

---

## Configuration

The sidebar shows up to **20 most recent tool calls** (configurable):

```python
# From src/logai/ui/widgets/tool_sidebar.py line 66
MAX_DISPLAYED_CALLS = 20
```

Older tool calls are automatically removed (FIFO) when the limit is reached.

---

## Summary

✅ **Cache fetch operations are fully visible in the tool calls sidebar**

- Shows as `fetch_cached_result_chunk` tool
- Displays all arguments (cache_id, offset, limit, filters)
- Shows execution time (typically 10-50ms)
- Displays first 5 events with expandable "Show more"
- Updates in real-time (pending → running → success)
- Provides clear performance comparison vs fresh queries

This transparency helps users understand when the cache is working and provides valuable debugging information for cache-related issues.
