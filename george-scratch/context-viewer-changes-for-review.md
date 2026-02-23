# Context Viewer Changes - Ready for Code Review

**Date:** February 20, 2026
**Reviewer:** Han-Ron
**Status:** Awaiting Review

---

## Summary

This review covers three related enhancements to the Context Viewer feature:

1. **Truncation Removal** - Remove artificial content limits, show full system prompts and tool results
2. **Full Context View** - Include system prompt in Agent Memory section (not just conversation)
3. **Independent Scrolling** - Make each section independently scrollable with side-by-side layout

All changes have been user-tested and verified working correctly.

---

## Files Modified

1. **`src/logai/ui/screens/context_viewer.py`** - Major changes (UI layout, CSS, truncation removal)
2. **`src/logai/core/orchestrator.py`** - New method added (get_full_context_snapshot)
3. **`src/logai/ui/screens/chat.py`** - Minor change (call new method) + debug logs

---

## Change Details

### 1. Truncation Removal (context_viewer.py)

**Problem:** System prompts truncated at 500 chars, tool results at 2000 chars, showing non-clickable "... X more characters"

**Solution:** Removed `_truncate_content()` method and all calls to it

**Lines Changed:**
- Line 336: Removed truncation call for system messages
- Line 367: Removed truncation call for tool results
- Lines 362-376 (deleted): Removed entire `_truncate_content()` method

**Impact:**
- Simpler code (19 lines removed)
- Better data visibility (no artificial limits)
- RichLog's native scrolling handles long content

---

### 2. Full Context View (orchestrator.py + chat.py)

**Problem:** Agent Memory only showed conversation history, not the system prompt

**Solution:** Added new method to get complete context snapshot including system prompt

**New Method (orchestrator.py, lines 1890-1913):**
```python
def get_full_context_snapshot(self) -> list[dict[str, Any]]:
    """
    Get a snapshot of the full context that would be sent to the LLM.

    Includes:
    - System prompt (always prepended)
    - Full conversation history (user, assistant, tool messages)
    """
    messages = []
    messages.append({"role": "system", "content": self._get_system_prompt()})
    messages.extend(self.conversation_history)
    return messages
```

**Chat Screen Change (chat.py, line 397):**
```python
# OLD:
conversation_history = self.orchestrator.get_conversation_history()

# NEW:
conversation_history = self.orchestrator.get_full_context_snapshot()
```

**Impact:**
- User can see complete agent context including system prompt
- Better transparency into what the agent knows
- Helpful for debugging and understanding agent behavior

---

### 3. Independent Scrolling (context_viewer.py)

**Problem:** Individual sections not scrollable, only outer modal scrolled

**Solution:** Wrap each RichLog in VerticalScroll, use side-by-side layout, fix CSS heights

**Structural Changes:**
- Line 182: Changed `VerticalScroll` → `Horizontal` for side-by-side layout
- Lines 190-197: Wrapped Staged Context RichLog in `VerticalScroll(id="staged-scroll")`
- Lines 206-213: Wrapped Agent Memory RichLog in `VerticalScroll(id="memory-scroll")`

**CSS Changes:**
- Lines 69-74: Updated `#sections-container` (added horizontal layout, overflow hidden, height 1fr)
- Lines 77-82: Updated `Collapsible` (added width/height 1fr)
- Lines 90-95: Updated `Collapsible > Contents` (changed height auto → 1fr)
- Lines 97-102: Added new scroll container styling for independent scrolling

**Impact:**
- Each section independently scrollable
- Better UX - user feedback: "I prefer the side-by-side presentation"
- All content accessible via scrolling

---

## Debug Logs

**Note:** The following debug logs were added during investigation and should be reviewed for removal before commit:

**In chat.py:**
- Lines 389-393: `[CONTEXT_VIEWER_DEBUG]` logs for staged context
- Lines 450-452: `[CONTEXT_VIEWER_DEBUG]` log after inject_context_update

**In context_viewer.py:**
- Lines 167-169: `[CONTEXT_VIEWER_DEBUG]` log in __init__
- Lines 226-230: `[CONTEXT_VIEWER_DEBUG]` logs in on_mount

**Review Question:** Should these be removed, or kept for production debugging?

---

## Testing

### User Testing - ✅ PASSED
- Tested truncation removal: Full system prompt visible
- Tested independent scrolling: Both sections scroll independently
- User feedback: Positive ("Ah, that looks good", "I prefer the side-by-side presentation")

### Existing Tests - ✅ PASSED
- All 33 existing tests still pass
- No regressions detected

### Manual Testing Scenarios
1. ✅ Open Context Viewer with no context → Shows empty state messages
2. ✅ Add logs to context → Staged Context section populates
3. ✅ Send message → Agent Memory shows system prompt + conversation
4. ✅ Long system prompt → Scrollable within Agent Memory section
5. ✅ Multiple staged logs → Scrollable within Staged Context section

---

## Code Quality Concerns to Review

### 1. CSS Height Strategy
- Changed from `height: auto` to `height: 1fr` in multiple places
- Does this work correctly across different terminal sizes?
- Any edge cases where content might be cut off?

### 2. RichLog Widget Refresh Calls
- Added explicit `refresh()` calls after writing content (lines 232, 239)
- Are these necessary? Could they cause performance issues?

### 3. Horizontal Layout
- Changed from vertical stacked to side-by-side horizontal layout
- How does this look on narrow terminals?
- Should we have a minimum width requirement?

### 4. Debug Logs
- Multiple `[CONTEXT_VIEWER_DEBUG]` logs added
- Should these be removed before commit?
- Or kept with lower log level for production?

### 5. New Public Method
- `get_full_context_snapshot()` added to orchestrator
- Is the method name clear?
- Should it be private (with underscore)?
- Is the return type annotation correct?

### 6. RichLog CSS Changes
- Changed `height: 100%` to `height: auto` with `min-height: 20`
- Does `min-height: 20` make sense? What unit is this?
- Could this cause layout issues?

---

## Review Checklist

Please review for:

- [ ] **Code correctness** - Logic errors, edge cases
- [ ] **Textual framework usage** - Proper widget/CSS patterns
- [ ] **Performance** - Any potential performance issues
- [ ] **Maintainability** - Code clarity, documentation
- [ ] **Testing coverage** - Are new tests needed?
- [ ] **Debug logs** - Should they be removed/kept/modified?
- [ ] **Edge cases** - Narrow terminals, empty content, very long content
- [ ] **Breaking changes** - Any API changes that affect other code?

---

## Metrics

| Metric | Value |
|--------|-------|
| **Files Modified** | 3 |
| **Lines Added** | ~70 |
| **Lines Removed** | ~20 |
| **Net Lines Changed** | +50 |
| **New Methods** | 1 |
| **Deleted Methods** | 1 |
| **CSS Properties Changed** | ~10 |
| **Risk Level** | Medium (UI layout changes) |

---

## Related Documentation

- `george-scratch/context-viewer-scrolling-fix.md` - Scrolling fix details
- `george-scratch/end-of-day-summary-2026-02-19.md` - Previous session context
- `george-scratch/full-context-implementation.md` - Full context view implementation (from yesterday)

---

## Questions for Reviewer

1. Should debug logs be removed or kept (with different log level)?
2. Is `height: 1fr` the right approach for all the CSS changes?
3. Does the horizontal layout need responsive handling for narrow terminals?
4. Should `get_full_context_snapshot()` be a private method?
5. Are additional tests needed for the new functionality?
6. Any security/privacy concerns with showing full system prompt?

---

**Ready for Review:** Yes
**Priority:** Medium
**Estimated Review Time:** 30-45 minutes
