# Investigation: "Add to Context" Button Bug

**Issue:** User reported that the "Add to Context" button in the log preview modal may not be working correctly. When users select logs, click "Add to Context", then ask the agent a question, the agent cannot answer as if the logs weren't in context.

**Investigation Date:** February 19, 2026

---

## 1. Expected Behavior

### Step-by-Step Flow (Happy Path)

1. **User Initiates Preview**
   - User double-clicks a log group in the left sidebar
   - LogGroupPreviewRequested event is emitted
   - ChatScreen receives event and opens LogPreviewScreen modal

2. **User Selects Logs**
   - LogPreviewScreen displays recent log entries from CloudWatch
   - User checks checkbox(es) for entries they want to add
   - "Add Selected to Context" button becomes enabled when entries are selected

3. **User Clicks "Add to Context"**
   - LogPreviewScreen.on_add_to_context() is called (line 890)
   - Collects all selected entries into a list
   - Calls self.dismiss(result) with result dict containing:
     - `log_group_name`: Name of the log group
     - `selected_entries`: List of selected log events

4. **ChatScreen Processes Result**
   - on_log_group_preview_requested() receives result (line 359-360)
   - Calls await _inject_log_entries_to_context(result) (line 360)

5. **Entries Formatted for Context**
   - _format_log_entries_for_context() formats entries (line 405-442)
   - Creates a formatted string with:
     - Log group name
     - Entry count
     - Formatted JSON with timestamp, message, log_stream for each entry
   - Returns context message as a string

6. **Context Injected into Orchestrator**
   - orchestrator.inject_context_update(context_message) called (line 386)
   - Message stored in self._pending_context_injection (orchestrator line 433)
   - System message shown in UI: "Added X log entries from {group} to context" (line 391-394)

7. **Context Passed to Agent on Next Message**
   - User asks a question about the logs
   - ChatScreen._process_message() is called
   - Orchestrator.chat_stream() is called
   - Inside _chat_complete() (line 971+):
     - Pending context injection is retrieved (line 999)
     - Added as system message (line 1001)
     - Sent to LLM as part of messages list (line 1022)
   - Agent receives logs in context and analyzes them

### Expected Result
The agent can immediately answer questions about the selected logs because they are included in the system context of the next LLM call.

---

## 2. Current Implementation

### Location: src/logai/ui/screens/log_preview.py

**Button Handler (line 889-904):**
```python
@on(Button.Pressed, "#add-to-context-btn")
def on_add_to_context(self) -> None:
    """Add selected entries to context and close modal."""
    # Gather selected events
    selected_events = []
    for idx, event in enumerate(self._events):
        entry_id = f"entry-{idx}"
        if entry_id in self._selected_ids:
            selected_events.append(event)

    # Return result and dismiss
    result = {
        "log_group_name": self.log_group_name,
        "selected_entries": selected_events,
    }
    self.dismiss(result)
```

**Status:**
- ✅ Button handler is implemented
- ✅ Correctly gathers selected events
- ✅ Dismisses modal with result

### Location: src/logai/ui/screens/chat.py

**Handler for Preview Result (line 322-368):**
```python
@on(ClickableLogGroupItem.LogGroupPreviewRequested)
async def on_log_group_preview_requested(
    self, event: ClickableLogGroupItem.LogGroupPreviewRequested
) -> None:
    """Handle request to preview logs from a log group."""
    try:
        # Get datasource from tool registry via orchestrator
        tool = self.orchestrator.tool_registry.get("list_log_groups")
        if tool is None or not hasattr(tool, "datasource"):
            self.notify("Preview feature not available - datasource not found", ...)
            return

        datasource = tool.datasource

        # Show preview modal and await result
        result = await self.app.push_screen(LogPreviewScreen(...))

        # If user selected entries, inject them into context
        if result:
            await self._inject_log_entries_to_context(result)

    except Exception as e:
        logger.error(f"Failed to open log preview: {e}", exc_info=True)
```

**Status:**
- ✅ Event handler registered correctly
- ✅ Modal is pushed and awaited
- ✅ Calls _inject_log_entries_to_context() when result is non-None

**Injection Method (line 370-403):**
```python
async def _inject_log_entries_to_context(self, result: dict[str, Any]) -> None:
    """Inject selected log entries into agent context."""
    try:
        log_group = result["log_group_name"]
        entries = result["selected_entries"]
        count = len(entries)

        # Format entries for context
        context_message = self._format_log_entries_for_context(log_group, entries)

        # Inject via orchestrator
        self.orchestrator.inject_context_update(context_message)

        # Show system message in chat
        messages_container = self.query_one("#messages-container", VerticalScroll)
        entry_word = "entry" if count == 1 else "entries"
        system_msg = SystemMessage(
            f"Added {count} log {entry_word} from {log_group} to context"
        )
        messages_container.mount(system_msg)
        messages_container.scroll_end(animate=False)

    except Exception as e:
        logger.error(f"Failed to inject log entries to context: {e}", exc_info=True)
        self.notify(f"Failed to add logs to context: {str(e)}", ...)
```

**Status:**
- ✅ Extracts log group name and entries
- ✅ Calls _format_log_entries_for_context()
- ✅ Calls orchestrator.inject_context_update()
- ✅ Shows UI feedback message

**Format Method (line 405-442):**
```python
def _format_log_entries_for_context(self, log_group: str, entries: list[dict[str, Any]]) -> str:
    """Format log entries for agent context injection."""
    formatted_entries = []
    for entry in entries:
        # Format timestamp for readability
        timestamp_ms = entry.get("timestamp", 0)
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        formatted_entries.append(
            {
                "timestamp": formatted_time,
                "message": entry.get("message", ""),
                "log_stream": entry.get("log_stream", ""),
            }
        )

    return f"""USER-SELECTED LOG ENTRIES for analysis:

Log Group: {log_group}
Entry Count: {len(entries)}

The user has specifically selected these log entries for your analysis:

```json
{json.dumps(formatted_entries, indent=2)}
```

Please analyze these logs and provide insights based on the user's next question."""
```

**Status:**
- ✅ Formats entries with proper timestamp conversion
- ✅ Creates well-formatted context message
- ✅ Returns complete string with instructions

### Location: src/logai/core/orchestrator.py

**Context Injection API (line 423-433):**
```python
def inject_context_update(self, context_message: str) -> None:
    """
    Inject a context update to be included in the next LLM call.

    This is used to update the agent's knowledge mid-conversation,
    such as after a /refresh command updates the log group list.

    Args:
        context_message: Message to inject as system context
    """
    self._pending_context_injection = context_message
```

**Status:**
- ✅ Simple storage in instance variable
- ✅ Ready to be retrieved on next call

**Context Retrieval (line 435-470):**
```python
def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    # Check for cache guidance first (higher priority)
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None  # Clear after use

        return f"""SYSTEM INSTRUCTION: The previous tool call returned a large result..."""

    # Fall back to regular context injection (e.g., /refresh updates)
    injection = self._pending_context_injection
    self._pending_context_injection = None
    return injection
```

**Status:**
- ✅ Returns the stored injection
- ✅ Clears it after retrieval (so not used twice)
- ⚠️ **POTENTIAL ISSUE:** Cache guidance has higher priority!

**Usage in Chat Loop (line 999-1001):**
```python
# Check for pending context injection
pending_injection = self._get_pending_context_injection()
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})
```

**Status:**
- ✅ Called on each chat iteration
- ✅ Appended as system message
- ✅ Sent to LLM

---

## 3. Code Analysis - Complete Flow with Line Numbers

### Flow Diagram (Sequential)

```
USER ACTION
    ↓
LogPreviewScreen.on_add_to_context() [line 890]
    ↓
    Collect selected entries → result dict
    ↓
    self.dismiss(result) [line 904]
    ↓
ChatScreen.on_log_group_preview_requested() [line 323]
    ↓
    Awaits LogPreviewScreen result [line 351]
    ↓
    if result: [line 359]
    ↓
    await _inject_log_entries_to_context(result) [line 360]
    ↓
ChatScreen._inject_log_entries_to_context() [line 370]
    ↓
    Extract entries [line 378-380]
    ↓
    Format: _format_log_entries_for_context() [line 383]
    ↓
    orchestrator.inject_context_update(context_message) [line 386]
    ↓
LLMOrchestrator.inject_context_update() [line 423]
    ↓
    Store in self._pending_context_injection [line 433]
    ↓
    [UI feedback message shown] [line 391-394]
    ↓
USER ASKS A QUESTION
    ↓
LLMOrchestrator._chat_complete() [line 971]
    ↓
    pending_injection = self._get_pending_context_injection() [line 999]
    ↓
    if pending_injection: messages.append(...) [line 1000-1001]
    ↓
    Send messages to LLM [line 1022]
    ↓
AGENT RECEIVES CONTEXT & RESPONDS
```

---

## 4. Flow Diagram - Data Flow from Button to Agent

```
[Log Preview Modal]
    │
    └─> User selects entries & clicks "Add to Context"
        │
        └─> on_add_to_context() [log_preview.py:890]
            │
            └─> Build result dict:
                {
                  "log_group_name": string,
                  "selected_entries": list[dict]
                }
            │
            └─> self.dismiss(result)
                │
                ├─> Result returns to awaiting code
                ├─> (chat.py:351 - the push_screen() await)
                │
                └─> on_log_group_preview_requested() [chat.py:323]
                    │
                    └─> if result: _inject_log_entries_to_context(result)
                        │
                        ├─> Format entries [chat.py:383]
                        │   └─> _format_log_entries_for_context()
                        │       Returns formatted context string
                        │
                        ├─> orchestrator.inject_context_update(msg) [chat.py:386]
                        │   └─> Stores in _pending_context_injection
                        │
                        └─> Show UI message [chat.py:391-394]

[Chat Screen - Waiting for user input]
    │
    └─> User types question about logs
        │
        └─> on_input_submitted() [chat.py:207]
        └─> _process_message(user_message) [chat.py:243]
            │
            └─> orchestrator.chat_stream(user_message) [chat.py:283]
                │
                └─> _chat_complete(user_message) [orchestrator.py:971]
                    │
                    ├─> conversation_history.append(user_message) [line 988]
                    │
                    ├─> Build messages list [line 994-996]
                    │   messages = [system_prompt] + conversation_history
                    │
                    ├─> pending_injection = _get_pending_context_injection() [line 999]
                    │   └─> Returns _pending_context_injection
                    │       └─> CLEARS _pending_context_injection [line 469]
                    │
                    ├─> if pending_injection: messages.append(...) [line 1000-1001]
                    │   └─> Adds formatted log entries as system message
                    │
                    └─> Send messages to LLM [line 1022]
                        └─> Agent receives logs in context!
                            └─> Agent analyzes and responds
```

---

## 5. Root Cause Analysis

### Verdict: ✅ IMPLEMENTATION APPEARS CORRECT

After thorough code inspection, **the "Add to Context" feature appears to be correctly implemented**. The flow is:

1. **Button clicks correctly** → gathers selected entries ✅
2. **Modal dismisses with result** → returns to chat screen ✅
3. **Chat screen receives result** → processes it correctly ✅
4. **Formatting is proper** → creates well-structured context message ✅
5. **Orchestrator stores injection** → saves to _pending_context_injection ✅
6. **On next user message** → retrieves and injects context ✅
7. **LLM receives context** → should have logs available ✅

### However, Found ONE Potential Issue:

**Priority/Race Condition in _get_pending_context_injection() [line 435-470]:**

```python
def _get_pending_context_injection(self) -> str | None:
    # Check for cache guidance first (HIGHER PRIORITY)
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None
        return f"""SYSTEM INSTRUCTION: The previous tool call..."""

    # Fall back to regular context injection
    injection = self._pending_context_injection
    self._pending_context_injection = None
    return injection
```

**ISSUE:** If `_pending_cache_guidance` is set AND `enable_auto_fetch_guidance` is True, the user-injected log entries will be **IGNORED** because cache guidance takes priority!

**Scenario that triggers this:**
1. User clicks "Add to Context" on some log entries
2. A tool call (like query_logs) returns a large cached result
3. Both `_pending_context_injection` AND `_pending_cache_guidance` are set
4. When _get_pending_context_injection() is called:
   - It checks cache guidance FIRST
   - Returns cache guidance instead of user's context injection
   - User-selected logs are NEVER injected!

---

## 6. Evidence - Code Snippets

### Evidence 1: User Context Injection Works (Happy Path)

**From chat.py line 386:**
```python
self.orchestrator.inject_context_update(context_message)
```

**From orchestrator.py line 433:**
```python
self._pending_context_injection = context_message
```

Storage is correct. ✅

### Evidence 2: Retrieval Logic

**From orchestrator.py line 999:**
```python
pending_injection = self._get_pending_context_injection()
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})
```

Retrieval and usage is correct. ✅

### Evidence 3: The Priority Bug

**From orchestrator.py line 438-465:**
```python
def _get_pending_context_injection(self) -> str | None:
    # ⚠️ CACHE GUIDANCE IS CHECKED FIRST!
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None  # ← This clears it
        return f"""SYSTEM INSTRUCTION: ..."""  # ← But returns cache guidance

    # Only reached if cache guidance wasn't set
    injection = self._pending_context_injection
    self._pending_context_injection = None
    return injection
```

**The Problem:** If both are set, only cache guidance is returned!

---

## 7. Impact Assessment

### Severity: **MEDIUM**

**Complete Failure?** No
- If user adds logs to context AND no tool calls happen before they ask a question → **WORKS** ✅
- If user adds logs to context AND a tool call with cached results happens → **FAILS** ❌

**Partial Failure?** Yes
- Works when lucky (no cached results in between)
- Fails when tool calls generate cached results
- Especially problematic if user is actively using "Add to Context" feature

### Likelihood of Triggering Bug:

**HIGH** if:
- User adds logs with "Add to Context"
- Then asks a question that triggers a tool call (query_logs, etc.)
- That tool call returns a large result that gets cached
- User's selected logs are lost
- Agent responds without knowledge of the selected logs

**LOW** if:
- User adds logs
- User asks simple follow-up without triggering tools
- Or caching is disabled

---

## 8. Recommended Fix

### Solution 1: **Both Injections Should Be Included (BEST)**

**Modify orchestrator.py line 435-470:**

```python
def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    injections = []

    # Include cache guidance if available
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None  # Clear after use
        cache_guidance = f"""SYSTEM INSTRUCTION: The previous tool call returned..."""
        injections.append(cache_guidance)

    # Include user-selected log entries if available
    if self._pending_context_injection:
        injection = self._pending_context_injection
        self._pending_context_injection = None
        injections.append(injection)

    # Return combined injections or None if empty
    if injections:
        return "\n\n---\n\n".join(injections)
    return None
```

**Advantages:**
- Both features work together seamlessly
- No data loss
- Maintains priority through ordering (cache guidance first, then user context)
- Simple and maintainable

### Solution 2: **User Injections Take Priority**

**Alternative fix (not recommended):** Put user injections first in the if statement.

**Problem:** Loses cache fetch guidance potentially.

### Solution 3: **Separate Injection Points**

**Alternative fix:** Handle cache guidance separately from user injections.

**Problem:** More complex refactoring needed.

---

## 9. Testing Strategy

### Unit Tests Needed:

#### Test 1: Cache Guidance Should Not Override User Context
```python
def test_user_context_not_overridden_by_cache_guidance():
    """User-injected context should be preserved even if cache guidance exists."""
    orchestrator = LLMOrchestrator(...)

    # Set both injections
    orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}
    orchestrator.inject_context_update("USER SELECTED LOGS: ...")

    # Get injection
    result = orchestrator._get_pending_context_injection()

    # Should include BOTH
    assert "SYSTEM INSTRUCTION" in result  # Cache guidance
    assert "USER-SELECTED LOG ENTRIES" in result  # User context
    assert "USER SELECTED LOGS" in result  # From inject_context_update()
```

#### Test 2: User Context Alone
```python
def test_user_context_injected_when_no_cache():
    """User-injected context should work when no cache guidance exists."""
    orchestrator = LLMOrchestrator(...)

    orchestrator.inject_context_update("MY LOG ENTRIES: ...")

    result = orchestrator._get_pending_context_injection()

    assert result == "MY LOG ENTRIES: ..."
```

#### Test 3: Cache Guidance Alone
```python
def test_cache_guidance_injected_when_no_user_context():
    """Cache guidance should work when user hasn't injected context."""
    orchestrator = LLMOrchestrator(...)

    orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}

    result = orchestrator._get_pending_context_injection()

    assert "SYSTEM INSTRUCTION" in result
    assert "fetch chunks" in result.lower()
```

### Integration Tests:

#### Test 4: Full Flow - Add to Context Then Query
```python
@pytest.mark.asyncio
async def test_add_to_context_flow():
    """Test complete flow from log selection to agent response."""
    # 1. Create orchestrator with mocked LLM
    # 2. Call inject_context_update() with log entries
    # 3. Call chat() with user question
    # 4. Verify LLM received logs in context messages
    # 5. Verify agent's response references the logs
```

#### Test 5: Context Survives Tool Calls
```python
@pytest.mark.asyncio
async def test_user_context_survives_tool_calls():
    """User-injected context should persist through tool calls."""
    # 1. Inject user context
    # 2. Ask question that triggers tool call
    # 3. Mock tool to return cached result
    # 4. Agent processes results
    # 5. Verify user context was still included somewhere
```

### Manual Test Steps:

1. **Basic Test:**
   - Open LogAI
   - Double-click a log group
   - Select some log entries
   - Click "Add Selected to Context"
   - Verify message shows in chat
   - Ask a question about the logs
   - Agent should reference the logs ✅

2. **Edge Case Test:**
   - Open LogAI
   - Add to context with some logs
   - Ask a question (this might trigger a tool call with caching)
   - Ask a follow-up question about YOUR selected logs
   - Agent should still remember the selected logs ⚠️

3. **With Caching:**
   - Enable result caching
   - Add to context with some logs
   - Ask a question that definitely triggers tool call
   - The tool call returns large results (gets cached)
   - Ask another question
   - Verify user-selected logs are still available ⚠️

---

## 10. Summary

### What Works ✅
- Button correctly gathers selected entries
- Chat screen correctly receives dismiss result
- Entries are properly formatted for context
- Orchestrator correctly stores the injection
- Context is added to messages sent to LLM

### What's Broken ❌
- **Priority bug in _get_pending_context_injection():**
  - Cache guidance takes precedence
  - User-injected context is lost if both exist
  - Manifests when tool calls generate cached results after "Add to Context"

### Fix Recommendation
**COMBINE both injections instead of choosing one:**

Modify `orchestrator.py` line 435-470 to:
1. Include cache guidance if available
2. Also include user-injected context if available
3. Return combined string or None

### Impact of Fix
- **No breaking changes** - only adds context, doesn't remove anything
- **Solves the reported bug** - user logs stay in context through tool calls
- **Maintains cache guidance feature** - both features work together
- **Simple to implement** - ~10 line change

---

## Appendix: File Locations

| Component | File | Key Lines |
|-----------|------|-----------|
| Button Handler | `src/logai/ui/screens/log_preview.py` | 889-904 |
| Event Handler | `src/logai/ui/screens/chat.py` | 322-368 |
| Injection Method | `src/logai/ui/screens/chat.py` | 370-403 |
| Format Method | `src/logai/ui/screens/chat.py` | 405-442 |
| API Call | `src/logai/core/orchestrator.py` | 423-433 |
| **BUG LOCATION** | `src/logai/core/orchestrator.py` | 435-470 |
| Usage | `src/logai/core/orchestrator.py` | 999-1001 |

---

## Appendix: Configuration Check

The bug manifests specifically when:
- `enable_auto_fetch_guidance = True` (default)
- A large tool result is cached (happens automatically)
- User-injected context exists simultaneously

To temporarily work around:
```python
# In settings, set:
enable_auto_fetch_guidance = False
```

This prevents cache guidance from taking priority, allowing user context through. **NOT a proper fix**, just a workaround.
