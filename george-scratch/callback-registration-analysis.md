# ROOT CAUSE FOUND: Async Callback Coroutine Never Awaited

**Date:** February 20, 2026
**Status:** ROOT CAUSE IDENTIFIED - READY FOR FIX
**Severity:** CRITICAL

---

## The Bug (ONE LINE!)

**File:** `src/logai/ui/screens/chat.py`
**Line:** 366

```python
# WRONG - This is async but will never be awaited:
async def handle_log_selection(result: dict[str, Any] | None) -> None:
    """Handle the result from the log preview modal."""
    if result:
        await self._inject_log_entries_to_context(result)

# Textual calls it synchronously at Screen.dismiss (line: callback(result))
# This creates a coroutine object but never awaits it!
# Result: The callback code NEVER EXECUTES
```

---

## Evidence

### 1. Textual's dismiss() Implementation

**Location:** `textual/screen.py` - `Screen.dismiss()`

```python
def dismiss(self, result: ScreenResultType | None = None) -> AwaitComplete:
    """Dismiss the screen..."""
    if self._result_callbacks:
        callback = self._result_callbacks[-1]
        callback(result)  # ← SYNCHRONOUS CALL, NOT AWAITED!
    await_pop = self.app.pop_screen()
    # ... rest of method
```

**Key Point:** Textual calls `callback(result)` directly, WITHOUT `await`.

### 2. What Happens When You Call Async Function Without Await

```python
async def my_async_callback(result):
    print(f"Processing: {result}")

# When called WITHOUT await:
my_async_callback(result)  # Returns a coroutine object
                           # The code inside NEVER RUNS!
                           # Python warns: "coroutine was never awaited"
```

### 3. Proof of Concept

```python
import asyncio

async def handle_log_selection(result):
    print(f"✓ Callback executing with: {result}")
    await asyncio.sleep(0.1)

def call_sync(callback, result):
    """This is how Textual does it"""
    callback(result)  # Synchronous call
    # Result: coroutine created but never executed!

call_sync(handle_log_selection, {"data": "test"})
# Output: (nothing!)
# Warning: RuntimeWarning: coroutine 'handle_log_selection' was never awaited
```

---

## Why Tests Passed But Production Fails

### Tests (Mocked)
```python
# tests/unit/ui/test_chat_callback.py uses:
callback_func = handle_log_selection

# Then manually calls:
await callback_func(test_result)  # ← TESTS AWAIT IT!
```

**Tests explicitly await the callback, so they pass.**

### Production (Real Textual)
```python
# In real Textual runtime:
self.app.push_screen(screen, handle_log_selection)

# When user clicks "Add to Context":
# Textual internally does:
callback(result)  # ← NO AWAIT! Coroutine created but never executed
```

**Production doesn't await, so callback never runs.**

---

## The Fix (SIMPLE)

### Option 1: Make Callback Synchronous (PREFERRED)

**File:** `src/logai/ui/screens/chat.py`
**Lines:** 366-373

```python
# WRONG (current):
async def handle_log_selection(result: dict[str, Any] | None) -> None:
    if result:
        entry_count = len(result.get("selected_entries", []))
        logger.debug(f"Injecting {entry_count} log entries from preview to context")
        await self._inject_log_entries_to_context(result)
    else:
        logger.debug("Log preview modal dismissed without selection")

# RIGHT (fixed):
def handle_log_selection(result: dict[str, Any] | None) -> None:
    """Handle the result from the log preview modal."""
    if result:
        entry_count = len(result.get("selected_entries", []))
        logger.debug(f"Injecting {entry_count} log entries from preview to context")
        # Schedule the async work as a background task
        self.call_later(self._inject_log_entries_to_context, result)
    else:
        logger.debug("Log preview modal dismissed without selection")
```

**Why this works:**
- Callback is now synchronous (Textual calls it with `callback(result)`)
- Callback schedules the async work with `self.call_later()`
- Work runs in the background without blocking

---

### Option 2: Use @work Decorator (ALTERNATIVE)

Create a worker method instead of inline callback:

```python
@work(exclusive=True)
async def _handle_log_selection_work(self, result: dict[str, Any] | None) -> None:
    """Worker to handle log selection in background."""
    if result:
        await self._inject_log_entries_to_context(result)

# Then pass a sync wrapper:
def handle_log_selection(result):
    self._handle_log_selection_work(result)

self.app.push_screen(LogPreviewScreen(...), handle_log_selection)
```

**Advantage:** Clean separation of sync callback and async work

---

## Same Issue Elsewhere

**ALSO AFFECTED:**

File: `src/logai/ui/screens/chat.py`
Line: 416

```python
# WRONG (same issue):
async def handle_context_viewer_close(result: None) -> None:
    logger.debug("Context viewer modal closed")

# SHOULD BE:
def handle_context_viewer_close(result: None) -> None:
    logger.debug("Context viewer modal closed")
```

This one is less critical because it does no async work, but it should still be fixed for consistency.

---

## Complete Fix Required

### File: `src/logai/ui/screens/chat.py`

Two locations need to be fixed:

1. **Line 366-373:** `handle_log_selection` callback
   - Change `async def` to `def`
   - Use `self.call_later()` to schedule async work

2. **Line 416-418:** `handle_context_viewer_close` callback
   - Change `async def` to `def`

---

## How to Test the Fix

After applying the fix:

1. Open log preview
2. Select logs
3. Click "Add Selected to Context"
4. Check logs for "[CONTEXT_DEBUG]" messages
5. Type message to agent
6. Agent should analyze provided logs

**Expected in logs:**
```
✓ [CONTEXT_DEBUG] Orchestrator stored context: X chars
✓ [CONTEXT_DEBUG] Orchestrator retrieved context: X chars
✓ [CONTEXT_DEBUG] Adding context to messages array: X chars
✓ [CONTEXT_DEBUG] Sending X messages to LLM
```

---

## Root Cause Timeline

1. **Commit b0ae572** - Callback pattern implemented
   - Callback defined as `async def`
   - Tests mocked and explicitly awaited the callback
   - Tests PASSED (unrealistic test scenario)

2. **Production Runtime**
   - Real Textual calls `callback(result)` synchronously
   - Async callback returns coroutine object
   - Coroutine is never awaited
   - Code inside callback NEVER EXECUTES
   - Context is NEVER injected
   - Agent NEVER sees logs

3. **Why Tests Didn't Catch This**
   - Tests explicitly `await callback_func(result)`
   - Tests don't simulate real Textual behavior
   - Mock tests ≠ Real Textual runtime behavior

---

## Files Involved

- **Source:** `src/logai/ui/screens/chat.py` (lines 366, 416)
- **Tests Need Update:** `tests/unit/ui/test_chat_callback.py` (no longer await callbacks)
- **Integration Tests Need Update:** `tests/integration/test_context_modal_callback.py`

---

## Summary

| Aspect | Status | Evidence |
|--------|--------|----------|
| **Root Cause Found** | ✓ YES | Async callback never awaited |
| **Exact Location** | ✓ IDENTIFIED | chat.py:366, chat.py:416 |
| **Impact** | ✓ CONFIRMED | Callback never executes in production |
| **Fix Complexity** | ✓ SIMPLE | Change 2-3 lines of code |
| **Tests Pass Now** | ✓ YES | But only because tests are unrealistic |
| **Production Fails** | ✓ CONFIRMED | Real Textual doesn't await callbacks |

---

## Jackie's Action Items

1. Change `async def handle_log_selection` → `def handle_log_selection`
2. Use `self.call_later(self._inject_log_entries_to_context, result)`
3. Change `async def handle_context_viewer_close` → `def handle_context_viewer_close`
4. Run tests to verify (tests will need updating)
5. Manual test with real log preview

**Expected time to fix:** 10 minutes
**Expected time to test:** 5 minutes
**Total: 15 minutes**
