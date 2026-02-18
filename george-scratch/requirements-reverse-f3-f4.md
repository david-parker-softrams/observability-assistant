# Requirements: Reverse F3/F4 Key Functions

**Date:** February 12, 2026
**TPM:** George
**Priority:** Low
**Complexity:** Trivial

---

## Problem Statement

The current key bindings for the right sidebar are:
- **F3**: Shrink right sidebar (◀ Tools)
- **F4**: Expand right sidebar (Tools ▶)

User wants the logic reversed:
- **F3**: Expand right sidebar (keep label "◀ Tools")
- **F4**: Shrink right sidebar (keep label "Tools ▶")

The **display labels in the footer should remain unchanged**, only the functions should swap.

---

## Current State

**File:** `src/logai/ui/screens/chat.py`

**Current bindings (lines 44-48):**
```python
BINDINGS = [
    Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
    Binding("f2", "expand_left_sidebar", "Logs ▶", show=True),
    Binding("f3", "shrink_right_sidebar", "◀ Tools", show=True),  # Currently shrinks
    Binding("f4", "expand_right_sidebar", "Tools ▶", show=True),  # Currently expands
]
```

**Current behavior:**
- F3 → calls `action_shrink_right_sidebar()` → sidebar gets narrower
- F4 → calls `action_expand_right_sidebar()` → sidebar gets wider

---

## Requirements

### Functional Requirements

1. **Swap F3 and F4 Functions**
   - F3 should call `expand_right_sidebar` action (make wider)
   - F4 should call `shrink_right_sidebar` action (make narrower)

2. **Keep Display Labels Unchanged**
   - F3 still shows as "◀ Tools" in footer
   - F4 still shows as "Tools ▶" in footer

3. **Left Sidebar Unchanged**
   - F1 and F2 remain as-is (F1 shrinks, F2 expands)

### Expected Behavior After Change

| Key | Current Behavior | New Behavior | Footer Label |
|-----|------------------|--------------|--------------|
| F1 | Shrink left | Shrink left (no change) | ◀ Logs |
| F2 | Expand left | Expand left (no change) | Logs ▶ |
| F3 | Shrink right | **Expand right** | ◀ Tools |
| F4 | Expand right | **Shrink right** | Tools ▶ |

---

## Implementation Details

### Changes Required

**File:** `src/logai/ui/screens/chat.py`

**Change: Swap action names for F3 and F4 (lines 47-48)**

```python
# Before:
BINDINGS = [
    Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
    Binding("f2", "expand_left_sidebar", "Logs ▶", show=True),
    Binding("f3", "shrink_right_sidebar", "◀ Tools", show=True),  # ← Shrinks
    Binding("f4", "expand_right_sidebar", "Tools ▶", show=True),  # ← Expands
]

# After:
BINDINGS = [
    Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
    Binding("f2", "expand_left_sidebar", "Logs ▶", show=True),
    Binding("f3", "expand_right_sidebar", "◀ Tools", show=True),  # ← Now expands
    Binding("f4", "shrink_right_sidebar", "Tools ▶", show=True),  # ← Now shrinks
]
```

**That's it!** Just swap the action names. The action methods themselves don't need any changes.

---

## Testing Requirements

### Manual Testing

1. **Start LogAI**
   ```bash
   logai
   ```

2. **Verify Footer Labels Unchanged**
   - [ ] Footer shows: `F1 ◀ Logs │ F2 Logs ▶ │ F3 ◀ Tools │ F4 Tools ▶`
   - [ ] Labels are exactly the same as before

3. **Test F3 (Should Now Expand)**
   - [ ] Right sidebar starts at 28 columns
   - [ ] Press F3
   - [ ] Right sidebar expands to 30
   - [ ] Toast shows: "Tool calls: 30 columns"
   - [ ] Press F3 again, expands to 32, then 35, etc.

4. **Test F4 (Should Now Shrink)**
   - [ ] Right sidebar at some width > 24
   - [ ] Press F4
   - [ ] Right sidebar shrinks (width decreases)
   - [ ] Toast shows: "Tool calls: [new width] columns"
   - [ ] Keep pressing F4 until reaches 24
   - [ ] At 24, toast shows: "Tool calls sidebar at minimum width"

5. **Test F3 at Maximum**
   - [ ] Expand right sidebar to 70 with F3
   - [ ] Press F3 again
   - [ ] Toast shows: "Tool calls sidebar at maximum width"

6. **Test F4 at Minimum**
   - [ ] Shrink right sidebar to 24 with F4
   - [ ] Press F4 again
   - [ ] Toast shows: "Tool calls sidebar at minimum width"

7. **Verify Left Sidebar Unchanged**
   - [ ] F1 still shrinks left sidebar
   - [ ] F2 still expands left sidebar
   - [ ] No change in behavior

### Edge Cases

- [ ] Hidden sidebar: Hide right sidebar, press F3/F4 → warns "sidebar is hidden"
- [ ] Rapid key presses: Press F3 multiple times quickly → smooth expansion
- [ ] Toggle after resize: Expand to 50, hide sidebar, show sidebar → width preserved

---

## Acceptance Criteria

✅ **Complete when:**

1. F3 expands the right sidebar (makes it wider)
2. F4 shrinks the right sidebar (makes it narrower)
3. Footer labels remain "◀ Tools" and "Tools ▶"
4. F1 and F2 behavior unchanged
5. Manual testing passes
6. Toast notifications show correct widths

---

## Files to Modify

1. `src/logai/ui/screens/chat.py` - Swap action names in BINDINGS (lines 47-48)

---

## Estimated Effort

**Total Time:** 5 minutes

- Change bindings: 1 min
- Manual testing: 4 min

---

## Notes

- This is a one-line change (swap two action names)
- No architecture review needed
- No code review needed (trivial change)
- No QA needed
- No documentation update needed
- Just Jackie to implement and test

---

**Ready for Implementation:** ✅
**Assigned To:** Jackie (Software Engineer)
