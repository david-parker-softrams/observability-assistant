# Requirements: Add Footer Widget to Display Key Bindings

**Date:** February 12, 2026
**TPM:** George
**Priority:** High
**Complexity:** Low (no architecture needed)

---

## Problem Statement

The sidebar resize keyboard shortcuts (F1-F4) are implemented and working, but they are not visible in the TUI footer. The bindings are configured with `show=True` in `ChatScreen.BINDINGS`, but there is no `Footer` widget to display them.

Currently, the `ChatScreen` uses a custom `StatusBar` widget that only shows:
- Connection status
- Cache statistics
- Model name

The `StatusBar` does not display key bindings. Textual's built-in `Footer` widget is needed to show the bindings.

---

## Current State

**File:** `src/logai/ui/screens/chat.py`

**Existing bindings (lines 44-48):**
```python
BINDINGS = [
    Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
    Binding("f2", "expand_left_sidebar", "Logs ▶", show=True),
    Binding("f3", "shrink_right_sidebar", "◀ Tools", show=True),
    Binding("f4", "expand_right_sidebar", "Tools ▶", show=True),
]
```

**Existing compose method (lines 122-146):**
```python
def compose(self) -> ComposeResult:
    """Compose the chat screen layout."""
    yield Header()

    # ... sidebars and main content ...

    yield Container(ChatInput(), id="input-container")
    yield StatusBar(model=self.settings.current_llm_model)
    # ❌ NO Footer widget!
```

---

## Requirements

### Functional Requirements

1. **Add Footer Widget**
   - Import `Footer` from `textual.widgets`
   - Yield `Footer()` in the `compose()` method
   - Footer should appear at the bottom of the screen

2. **Display Key Bindings**
   - F1-F4 bindings should be visible in the footer
   - Format: `F1 ◀ Logs │ F2 Logs ▶ │ F3 ◀ Tools │ F4 Tools ▶`
   - Should auto-update based on `BINDINGS` class attribute

3. **Preserve StatusBar**
   - Keep the existing `StatusBar` widget
   - StatusBar should appear above Footer
   - Both widgets docked to bottom

### Visual Layout

**Before:**
```
┌──────────────────────────────────┐
│ Header                           │
├──────────────────────────────────┤
│                                  │
│ Sidebars + Main Content          │
│                                  │
├──────────────────────────────────┤
│ Chat Input                       │
├──────────────────────────────────┤
│ Status: Ready | Cache | Model    │ ← StatusBar only
└──────────────────────────────────┘
```

**After:**
```
┌──────────────────────────────────┐
│ Header                           │
├──────────────────────────────────┤
│                                  │
│ Sidebars + Main Content          │
│                                  │
├──────────────────────────────────┤
│ Chat Input                       │
├──────────────────────────────────┤
│ Status: Ready | Cache | Model    │ ← StatusBar
├──────────────────────────────────┤
│ F1 ◀ Logs │ F2 Logs ▶ │ F3...   │ ← Footer (NEW)
└──────────────────────────────────┘
```

### Non-Functional Requirements

1. **No Breaking Changes**
   - StatusBar functionality must remain unchanged
   - Existing status updates must still work

2. **Minimal Code Changes**
   - Only modify `chat.py` compose method
   - Add one import statement
   - Add one yield statement

3. **Textual Best Practices**
   - Use built-in `Footer` widget (no custom implementation)
   - Let Textual handle binding display automatically

---

## Implementation Details

### Changes Required

**File:** `src/logai/ui/screens/chat.py`

**Change 1: Add import (line ~12)**
```python
from textual.widgets import Header, Input, Footer  # Add Footer
```

**Change 2: Yield Footer in compose() (after StatusBar, line ~147)**
```python
def compose(self) -> ComposeResult:
    """Compose the chat screen layout."""
    yield Header()

    # ... existing sidebars and content ...

    yield Container(ChatInput(), id="input-container")
    yield StatusBar(model=self.settings.current_llm_model)
    yield Footer()  # ← ADD THIS LINE
```

That's it! The `Footer` widget will automatically:
- Read bindings from `ChatScreen.BINDINGS`
- Display only bindings with `show=True`
- Format them nicely with separators
- Update if bindings change

---

## Testing Requirements

### Manual Testing

1. **Start LogAI**
   ```bash
   logai
   ```

2. **Verify Footer Appears**
   - [ ] Footer is visible at the bottom of the screen
   - [ ] Footer shows: `F1 ◀ Logs │ F2 Logs ▶ │ F3 ◀ Tools │ F4 Tools ▶`
   - [ ] StatusBar is still visible above Footer

3. **Verify Bindings Work**
   - [ ] Press F1 - left sidebar shrinks, toast shows width
   - [ ] Press F2 - left sidebar expands, toast shows width
   - [ ] Press F3 - right sidebar shrinks, toast shows width
   - [ ] Press F4 - right sidebar expands, toast shows width

4. **Verify StatusBar Unchanged**
   - [ ] Status shows "Ready"
   - [ ] Cache stats appear and update
   - [ ] Model name is displayed

### Edge Cases

- [ ] Footer displays correctly on narrow terminals (80 cols)
- [ ] Footer displays correctly on wide terminals (200+ cols)
- [ ] Both StatusBar and Footer are visible simultaneously
- [ ] No layout issues or overlaps

---

## Acceptance Criteria

✅ **Complete when:**

1. Footer widget is added to ChatScreen
2. F1-F4 key bindings are visible in footer
3. StatusBar remains functional and visible
4. Manual testing passes
5. No visual regressions

---

## Estimated Effort

**Total Time:** 10 minutes

- Add import: 1 min
- Add Footer to compose: 1 min
- Manual testing: 5 min
- Verification: 3 min

---

## Notes

- This is a trivial fix (one line of code)
- No architecture review needed (Saanvi not required)
- No code review needed (Han-Ron not required)
- No QA needed (Raoul not required)
- No documentation update needed (footer is self-explanatory)
- Just Jackie to implement and test

---

**Ready for Implementation:** ✅
**Assigned To:** Jackie (Software Engineer)
