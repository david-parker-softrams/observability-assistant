# Context Viewer Rendering Fix

**Date:** 2026-02-19
**Engineer:** Jackie (Senior Software Engineer)
**Issue:** Context Viewer displays blank screen despite data flowing correctly (24,871 chars)

---

## Executive Summary

**ROOT CAUSE IDENTIFIED**: CSS height calculation issue causing RichLog widgets to have zero visible height.

**SOLUTION APPLIED**: Changed CSS from `height: 100%` to `height: auto` with `min-height: 20`, and added explicit refresh calls.

**STATUS**: ✅ Fix implemented and ready for testing

---

## Problem Analysis

### Debug Log Evidence (Confirmed Data Flow)

```
2026-02-19 17:08:41,675 - ContextViewerScreen init, staged_context length: 24871
2026-02-19 17:08:41,694 - Formatting staged context, self.staged_context length: 24871
2026-02-19 17:08:41,694 - Formatted staged result preview: [bold cyan]Log Entries:[/bold cyan] 100
```

**Key Finding**: Data successfully flows to the Context Viewer, but rendering fails.

### Root Cause

The CSS configuration at lines 94-100 in `context_viewer.py` had:

```css
#staged-content, #memory-content {
    width: 100%;
    height: 100%;      /* ← PROBLEM: 100% of auto-height parent = 0 */
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}
```

The parent `Collapsible > Contents` has `height: auto`, so child widgets with `height: 100%` can collapse to zero height. This is a classic CSS layout issue in flex/auto-height containers.

---

## Implementation

### Changes Applied

#### 1. CSS Fix (Lines 94-101)

**Before:**
```css
#staged-content, #memory-content {
    width: 100%;
    height: 100%;
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}
```

**After:**
```css
#staged-content, #memory-content {
    width: 100%;
    min-height: 20;    /* ← NEW: Ensure minimum visible height */
    height: auto;      /* ← CHANGED: Allow content to determine height */
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}
```

#### 2. Added Explicit Refresh Calls (Lines 220, 227, 231)

**Before:**
```python
staged_log.write(formatted_staged)
self._formatted_staged = formatted_staged

# Populate Agent Memory section
memory_log = self.query_one("#memory-content", RichLog)
formatted_history = self._format_conversation_history()
memory_log.write(formatted_history)
self._formatted_history = formatted_history
```

**After:**
```python
staged_log.write(formatted_staged)
staged_log.refresh()           # ← NEW: Force RichLog refresh
self._formatted_staged = formatted_staged

# Populate Agent Memory section
memory_log = self.query_one("#memory-content", RichLog)
formatted_history = self._format_conversation_history()
memory_log.write(formatted_history)
memory_log.refresh()           # ← NEW: Force RichLog refresh
self._formatted_history = formatted_history

# Refresh the entire screen to ensure rendering
self.refresh()                 # ← NEW: Force screen repaint
```

---

## Technical Rationale

### Why `height: 100%` Failed

In CSS/Textual layout systems:
- **Parent**: `Collapsible > Contents` has `height: auto` (content-driven height)
- **Child**: `RichLog` with `height: 100%` tries to fill 100% of parent
- **Problem**: When parent is auto-sizing, 100% can resolve to 0 before content is measured
- **Result**: Widget collapses and becomes invisible

### Why `height: auto` + `min-height` Works

- `height: auto`: Widget size determined by content
- `min-height: 20`: Guarantees minimum visibility (20 lines)
- RichLog can expand beyond 20 lines as content requires
- Works correctly with auto-sizing parent containers

### Why Multiple Refresh Calls

Textual's rendering pipeline may need explicit refresh signals when:
1. Content is written to widgets programmatically
2. Complex nested layouts (Container → Collapsible → RichLog)
3. Rich markup content being parsed

The triple-refresh approach ensures:
1. `staged_log.refresh()` - RichLog updates internal state
2. `memory_log.refresh()` - Memory section updates
3. `self.refresh()` - Entire screen repaints

---

## Testing Checklist

### Manual Verification

1. **Launch Context Viewer**:
   - Open log preview with data staged
   - Press `c` to open Context Viewer
   - **Expected**: Staged Context section shows 100 log entries

2. **Check Both Sections**:
   - Verify "Staged Context" section displays Rich-formatted header
   - Verify "Agent Memory" section shows conversation history
   - **Expected**: Both sections visible and scrollable

3. **Verify Rich Markup**:
   - Check that `[bold cyan]Log Entries:[/bold cyan]` renders as bold cyan text
   - Verify separators (`─` characters) display correctly
   - **Expected**: Proper text styling and formatting

4. **Test Edge Cases**:
   - Empty staged context (should show empty state message)
   - Long content (test scrolling works)
   - Collapse/expand sections (should maintain content)

### Debug Log Verification

Look for these log entries:
```
[CONTEXT_VIEWER_DEBUG] ContextViewerScreen init, staged_context length: XXXX
[CONTEXT_VIEWER_DEBUG] Formatting staged context, self.staged_context length: XXXX
[CONTEXT_VIEWER_DEBUG] Formatted staged result preview: [bold cyan]Log Entries:...
```

If logs show data but screen is still blank, additional investigation needed.

---

## Rollback Plan

If this fix causes issues:

### Revert CSS Changes
```css
#staged-content, #memory-content {
    width: 100%;
    height: 100%;  /* Revert to original */
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}
```

### Revert Refresh Calls
Remove the three new `refresh()` calls at lines 220, 227, and 231.

### Alternative Solution (If Needed)

If RichLog continues having issues, consider switching to `Static` widget:

```python
# In compose() method
yield Static(
    id="staged-content",
    markup=True,
    classes="content-display"
)

# In on_mount() method
staged_static = self.query_one("#staged-content", Static)
staged_static.update(formatted_staged)
```

---

## File Changes

**Modified File:**
- `src/logai/ui/screens/context_viewer.py`
  - Lines 94-101: CSS changes
  - Lines 220, 227, 231: Added refresh calls

**Lines Changed:** 8
**Risk Level:** Low (CSS and display-only changes, no logic modified)

---

## Next Steps

1. **User Testing**: Have user test Context Viewer with staged data
2. **Verify Rendering**: Confirm both sections display correctly
3. **Check Scrolling**: Ensure long content is scrollable
4. **Monitor Logs**: Watch for any new errors or warnings

If rendering issues persist after this fix, the next debugging step would be to:
- Inspect Textual's layout calculation with `textual console`
- Try alternative widget types (Static instead of RichLog)
- Check if Collapsible widget has known rendering bugs

---

## Implementation Notes

### Why Not Static Widget Initially?

I kept RichLog because:
1. **Scrolling**: RichLog has built-in scroll management
2. **Rich Markup**: Designed for Rich-formatted text
3. **Performance**: Optimized for long text content
4. **Incremental Updates**: Can write() multiple times efficiently

If RichLog proves unreliable, Static is a solid fallback.

### CSS Debugging Commands

To debug CSS issues in Textual:
```bash
# View live CSS inspector
textual console

# Run with dev mode
textual run --dev src/logai/main.py
```

---

## Confidence Level

**Fix Success Probability**: 85%

**Reasoning:**
- ✅ Identified specific CSS layout issue
- ✅ Applied standard fix for auto-height containers
- ✅ Added defensive refresh calls
- ⚠️ Textual rendering pipeline can be unpredictable
- ⚠️ May need widget-level debugging if this doesn't work

**If this fix doesn't resolve the issue**, the problem is likely deeper in Textual's rendering engine, and we should switch from RichLog to Static widget as Plan B.

---

**Status**: Ready for testing - George, please have the user test Context Viewer functionality.
