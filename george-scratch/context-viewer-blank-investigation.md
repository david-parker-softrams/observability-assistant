# Context Viewer Blank Bug Investigation

**Date**: 2026-02-19
**Investigator**: Jackie (Senior Software Engineer)
**Status**: Debug Logging Added - Ready for Testing

## Bug Report Summary

**Issue**: Context Viewer modal shows up blank even after user adds logs to context.

**Expected Behavior**: After adding logs but BEFORE sending a message, the "Staged Context" section should display the selected logs.

**Actual Behavior**: Modal opens with empty "Staged Context" section.

---

## Investigation Phase 1: Code Analysis

### Data Flow Trace

I traced the complete data flow from log selection to context viewer display:

```
1. User selects logs in preview → "Add to context" clicked
2. chat.py:_inject_log_entries_to_context() (line 424)
   → Formats logs into context_message
   → Calls orchestrator.inject_context_update(context_message) (line 443)

3. orchestrator.py:inject_context_update() (line 436)
   → Stores in self._pending_context_injection (line 446)
   → Already has debug log at line 447

4. User clicks "Context" in status bar
5. chat.py:on_context_view_requested() (line 379)
   → Reads staged_context = orchestrator._pending_context_injection (line 388)
   → Passes to ContextViewerScreen constructor (line 408)

6. context_viewer.py:ContextViewerScreen.__init__() (line 135)
   → Stores as self.staged_context (line 152)

7. context_viewer.py:on_mount() (line 203)
   → Calls _format_staged_context() (line 208)
   → Writes to RichLog widget (line 209)
```

### Potential Issues Identified

#### Issue 1: Direct Access to Private Variable
**Location**: `chat.py` line 388

The code directly accesses the orchestrator's private `_pending_context_injection` variable:
```python
staged_context = self.orchestrator._pending_context_injection
```

**Risk**: This bypasses any encapsulation and could be reading stale or cleared data.

**Note**: The orchestrator has a method `_get_pending_context_injection()` (line 449) that retrieves **and clears** the context. However, this method is NOT being used by the Context Viewer, which is correct - we want to **peek** at staged context, not consume it.

#### Issue 2: Async Timing Issue
**Location**: Between `inject_context_update()` and `on_context_view_requested()`

**Observation**: Both methods appear to run in the UI event loop, so there shouldn't be a race condition. However, if there's any intermediate code that clears `_pending_context_injection`, it would cause the blank display.

**Question**: Is there any code path between lines 443 and 388 that might clear or modify `_pending_context_injection`?

#### Issue 3: Widget Initialization
**Location**: `context_viewer.py` line 152

The constructor converts `None` to empty string:
```python
self.staged_context = staged_context or ""
```

This means if `staged_context` is `None`, it becomes `""`, and `_format_staged_context()` will show the empty state message. This is correct behavior, but we need to verify that `staged_context` is actually set when passed to the constructor.

---

## Investigation Phase 2: Debug Logging Added

I've added comprehensive debug logging at all critical points in the data flow:

### 1. After Context Injection (chat.py:443)
```python
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] After inject_context_update, _pending_context_injection length: {len(self.orchestrator._pending_context_injection) if self.orchestrator._pending_context_injection else 0}"
)
```

### 2. When Opening Context Viewer (chat.py:388)
```python
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] Opening Context Viewer, staged_context length: {len(staged_context) if staged_context else 0}"
)
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] staged_context preview: {staged_context[:200] if staged_context else 'None'}"
)
```

### 3. ContextViewerScreen Initialization (context_viewer.py:152)
```python
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] ContextViewerScreen init, staged_context length: {len(staged_context or '')}"
)
```

### 4. Formatting Staged Context (context_viewer.py:208)
```python
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] Formatting staged context, self.staged_context length: {len(self.staged_context)}"
)
logger.info(
    f"[CONTEXT_VIEWER_DEBUG] Formatted staged result preview: {formatted_staged[:200]}"
)
```

### Existing Debug Logs
The orchestrator already has `[CONTEXT_DEBUG]` logs at:
- Line 447: When storing context
- Line 487: When retrieving context
- Lines 1032-1070: When adding context to message arrays

---

## Next Steps: Testing Protocol

### Test Scenario
1. Start the application: `python -m logai`
2. Open log preview (double-click any log group)
3. Select some logs and click "Add to context"
4. Monitor logs in real-time: `tail -f ~/.logai/logs/logai.log | grep -E "(CONTEXT_VIEWER_DEBUG|CONTEXT_DEBUG)"`
5. Click "Context" in the status bar
6. Observe the debug output to identify where data is lost

### Expected Debug Output (Success Case)
```
[CONTEXT_DEBUG] Orchestrator stored context: 1234 chars
[CONTEXT_VIEWER_DEBUG] After inject_context_update, _pending_context_injection length: 1234
[CONTEXT_VIEWER_DEBUG] Opening Context Viewer, staged_context length: 1234
[CONTEXT_VIEWER_DEBUG] staged_context preview: USER-SELECTED LOG ENTRIES...
[CONTEXT_VIEWER_DEBUG] ContextViewerScreen init, staged_context length: 1234
[CONTEXT_VIEWER_DEBUG] Formatting staged context, self.staged_context length: 1234
[CONTEXT_VIEWER_DEBUG] Formatted staged result preview: [bold cyan]Log Entries:[/bold cyan]...
```

### Failure Indicators
- If "After inject_context_update" shows 0 length → Problem in `inject_context_update()`
- If "Opening Context Viewer" shows 0 but previous was non-zero → Context cleared between injection and view
- If "ContextViewerScreen init" shows 0 but previous was non-zero → Problem passing parameter
- If "Formatting" shows 0 but init was non-zero → Problem in instance variable storage

---

## Preliminary Root Cause Hypotheses

### Hypothesis A: Context Cleared Prematurely
**Likelihood**: Medium

The `_get_pending_context_injection()` method (orchestrator.py:449) clears the context when called. If this is being called anywhere between context injection and viewer opening, it would explain the blank display.

**Evidence Needed**: Check if `_get_pending_context_injection()` is called when user hasn't sent a message yet.

### Hypothesis B: Async Event Ordering
**Likelihood**: Low

If there's an async timing issue where the context viewer opens before the context injection completes, this could cause the blank display.

**Evidence Needed**: Debug logs will show if injection happens after viewer opens.

### Hypothesis C: Object Reference Issue
**Likelihood**: Low

If `self.orchestrator` in `chat.py` is a different instance than the one being updated, this would cause the issue.

**Evidence Needed**: Add object ID logging to verify same instance.

### Hypothesis D: None vs Empty String
**Likelihood**: Medium

If `staged_context` is being set to `None` instead of empty string somewhere in the chain, and then the empty string conversion at line 152 makes it truly empty.

**Evidence Needed**: Debug logs will show the exact value at each step.

---

## Proposed Fixes (To Be Determined After Testing)

### If Root Cause is A (Premature Clearing):
Create a separate "peek" method that doesn't clear:
```python
def peek_pending_context_injection(self) -> str | None:
    """Peek at pending context without consuming it."""
    return self._pending_context_injection
```

Update chat.py line 388:
```python
staged_context = self.orchestrator.peek_pending_context_injection()
```

### If Root Cause is B (Async Timing):
Add proper async/await coordination:
```python
await self.orchestrator.inject_context_update(context_message)
```

### If Root Cause is C (Instance Mismatch):
Verify orchestrator instance is correctly passed and shared.

### If Root Cause is D (None Handling):
Add explicit None checks and logging at each step.

---

## Action Items

- [x] Add debug logging at all data flow points
- [ ] Run test scenario and capture logs
- [ ] Analyze log output to identify where data is lost
- [ ] Determine root cause from evidence
- [ ] Implement appropriate fix
- [ ] Verify fix with same test scenario
- [ ] Remove debug logging or convert to debug level

---

## Status

**Current Status**: Debug logging added, ready for testing

**Awaiting**: Test execution to capture logs and identify root cause

**Next Reviewer**: George (TPM) - please run test scenario and provide log output for analysis
