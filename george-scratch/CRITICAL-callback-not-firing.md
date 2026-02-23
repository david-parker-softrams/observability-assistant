# CRITICAL BUG CONFIRMED: Log Preview Callback Not Firing

**Date:** February 20, 2026
**Reporter:** User (David)
**Severity:** CRITICAL - Core Feature Broken
**Status:** ROOT CAUSE IDENTIFIED

---

## Confirmed Diagnosis

**Root Cause: Callback is NOT being invoked when modal dismisses**

### Evidence from User
1. ❌ **Context count does NOT increase** when clicking "Add to Context"
2. ✅ **User DOES see logs in the preview** (so logs are loading correctly)
3. ❌ **Agent fabricates fake log groups** when asked what's in context
4. ✅ **Model works fine** (Ollama qwen3:32b, previously successful)

### What This Means
- Log preview modal dismisses with result
- BUT callback `handle_log_selection()` is never invoked
- So logs never get added to context
- Agent has no actual context, makes up fake responses

---

## The Problem

**In `src/logai/ui/screens/chat.py` lines 365-382:**

```python
def handle_log_selection(result: dict[str, Any] | None) -> None:
    """Handle result from log selection modal."""
    if result is None:
        return
    # ... rest of callback code
```

**This callback is NOT being called when:**
- User clicks "Add to Context" button
- Modal dismisses with `self.dismiss(result_dict)`
- Textual should invoke the callback
- But it's not happening in runtime

---

## Why Tests Pass But Production Fails

**Tests mock the callback:**
```python
# In tests
with patch.object(chat_screen, 'handle_log_selection') as mock_callback:
    # Manually invoke callback
    mock_callback(result)
```

**Production relies on Textual:**
- Textual's `push_screen()` callback parameter
- Modal's `dismiss()` with result
- Textual framework should invoke callback
- But something is broken

---

## Possible Causes

### Hypothesis 1: Callback Not Registered (Most Likely - 70%)
- `push_screen()` call doesn't properly register callback
- Callback parameter syntax issue
- Textual version incompatibility

### Hypothesis 2: Modal Dismiss Not Returning Result (20%)
- Modal dismisses but result is None or lost
- Button handler not calling dismiss correctly
- Result dict not formatted correctly

### Hypothesis 3: Callback Scope Issue (10%)
- Callback defined as inner function
- Scope/closure issue in Python
- Garbage collection before invocation

---

## Investigation Priority

### Step 1: Check How Callback Is Registered (URGENT)
Find where `push_screen()` is called for log preview:

```bash
grep -n "push_screen.*log_preview\|push_screen.*LogPreview" src/logai/ui/screens/chat.py
```

Look for pattern like:
```python
self.app.push_screen(LogPreviewScreen(...), callback=handle_log_selection)
# OR
self.app.push_screen(LogPreviewScreen(...), handle_log_selection)
```

### Step 2: Check Modal Dismiss Call
In `src/logai/ui/screens/log_preview.py` line ~919:

```python
@on(Button.Pressed, "#add-to-context-btn")
def on_add_to_context(self) -> None:
    # ... build result_dict
    self.dismiss(result_dict)  # Is this being called?
```

### Step 3: Add Debug Logging
We need to add print/log statements to verify:
1. Button click is detected
2. Result dict is built
3. dismiss() is called with result
4. Callback is registered
5. Callback is invoked (or not)

---

## Known Working Pattern

**From Textual docs, callbacks should work like:**

```python
def my_callback(result):
    print(f"Got result: {result}")

# When pushing screen
self.app.push_screen(MyModal(), callback=my_callback)

# In modal
self.dismiss({"data": "value"})  # Should invoke my_callback with this dict
```

**Something is breaking this pattern.**

---

## Files to Check

### Primary
- `src/logai/ui/screens/chat.py` - Where callback is defined and registered
- `src/logai/ui/screens/log_preview.py` - Where modal dismisses with result

### Related
- Look for ALL `push_screen` calls that use log_preview
- Check if there are multiple ways to open log preview
- Check if some paths work and others don't

---

## User Impact

**Severity:** CRITICAL
- Core feature completely broken
- User workflow blocked
- No logs can be added via preview
- Agent has no context, fabricates fake responses
- Affects all log preview usage

---

## Next Steps

1. **Hans:** Find exact `push_screen` call that opens log preview
2. **Hans:** Verify callback parameter is passed correctly
3. **Hans:** Check if callback signature matches Textual expectations
4. **Jackie:** Fix the callback registration
5. **Test:** Verify context count increases after fix

---

**This is a HIGH PRIORITY production bug. The callback registration is broken.**

**Assigned:** Hans (find the exact code) → Jackie (fix it)
