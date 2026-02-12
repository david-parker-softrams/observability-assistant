# Bug Fix: Tool Call Sidebar Integration

## Problem
Tool calls were not appearing in the sidebar when users asked questions that triggered tool usage (e.g., "list all logs").

## Root Cause
The `_on_tool_call_event()` method in `ChatScreen` (line 277-287) was incorrectly using `call_from_thread()` to marshal the callback to the UI thread. This method is designed for calling from a **different thread** into the Textual event loop.

However, the orchestrator's `_execute_tool_calls()` runs as an **async function in the SAME event loop** as the UI (not a separate thread). Using `call_from_thread()` in this scenario caused the callbacks to either:
- Be queued incorrectly
- Not execute at all
- Execute but fail silently

## The Fix
**File**: `src/logai/ui/screens/chat.py`  
**Method**: `_on_tool_call_event()`  
**Change**: Call `on_tool_call()` directly instead of using `call_from_thread()`

### Before
```python
def _on_tool_call_event(self, record: ToolCallRecord) -> None:
    # Use call_from_thread to safely update UI from orchestrator thread
    try:
        self.call_from_thread(self.on_tool_call, record)  # ❌ WRONG!
    except Exception as e:
        logger.warning(f"Failed to update tool sidebar: {e}", exc_info=True)
```

### After
```python
def _on_tool_call_event(self, record: ToolCallRecord) -> None:
    """
    Handler for tool call events from orchestrator.

    Since the orchestrator runs in the same async event loop as the UI,
    we can call on_tool_call() directly without thread marshalling.
    """
    try:
        # Orchestrator runs in same event loop, so we can call directly
        self.on_tool_call(record)  # ✅ CORRECT!
    except Exception as e:
        logger.warning(f"Failed to update tool sidebar: {e}", exc_info=True)
```

## Code Flow (Verified)

1. **User asks question** → `ChatScreen._process_message()`
2. **Orchestrator processes** → `LLMOrchestrator._chat_stream()` or `_chat_complete()`
3. **LLM requests tools** → `LLMOrchestrator._execute_tool_calls()`
4. **Tool execution stages** → Orchestrator creates `ToolCallRecord` with statuses:
   - `PENDING` (line 901-907)
   - `RUNNING` (line 909-911)
   - `SUCCESS` (line 916-920) or `ERROR` (line 937-946, 961-966)
5. **Notifications sent** → `orchestrator._notify_tool_call(record)` (line 343-354)
6. **Listeners invoked** → Calls `ChatScreen._on_tool_call_event(record)` (line 277)
7. **UI updates** → Calls `ChatScreen.on_tool_call(record)` (line 248)
8. **Sidebar updates** → Calls `ToolCallsSidebar.update_tool_call(record)` (line 271)
9. **Tree rebuilds** → `ToolCallsSidebar._rebuild_tree()` (line 107)

All of this happens in the **same async event loop**, so no thread marshalling is needed.

## Testing Required

### Manual Testing
1. Start logai: `export LOGAI_LLM_PROVIDER=github-copilot && logai`
2. Verify sidebar is visible on the right with "TOOL CALLS" header ✅
3. Ask: "List all log groups"
4. **Expected**: Tool calls appear in sidebar showing:
   - Tool name (e.g., `list_log_groups`)
   - Status icon (⏳ running, ✓ success, ✗ error)
   - Timestamp
   - Duration (when complete)
   - Arguments summary
   - Result summary

### Queries to Test
- "List all log groups" → Should show `list_log_groups` tool
- "Show me errors from the last hour" → Should show `query_logs` tool
- "What log groups exist?" → Should show `list_log_groups` tool

## Files Modified
- `src/logai/ui/screens/chat.py` - Fixed `_on_tool_call_event()` method

## Additional Changes Made
- Added documentation comments explaining why direct call is correct
- Removed debug logging (kept clean for production)

## Verification
- ✅ Listener is registered in `ChatScreen.on_mount()` (line 96)
- ✅ Orchestrator calls `_notify_tool_call()` at all tool execution stages
- ✅ Event flow is entirely within single async event loop
- ✅ No threading involved in the orchestrator execution path
- ✅ `call_from_thread()` removed from the callback path

## Notes for Future
If the orchestrator is ever moved to a separate thread (e.g., for CPU-intensive operations), this would need to be revisited and `call_from_thread()` would be the correct approach. However, with the current async/await architecture, direct calls are correct.

---

**Status**: ✅ Fix implemented and ready for testing  
**Reviewer**: Billy (Code Review)  
**Implementer**: Jackie (Senior Software Engineer)
