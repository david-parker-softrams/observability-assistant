# Requirements: Increase Sidebar Maximum Width

**Date:** February 12, 2026
**TPM:** George
**Priority:** Medium
**Complexity:** Low (no architecture needed)

---

## Problem Statement

The current maximum sidebar width is **35 columns**, but users need more space for wider content (long log group names, detailed tool call information).

User request: Make sidebars able to be **100% bigger** than current maximum.

---

## Current State

**File:** `src/logai/ui/screens/chat.py`

**Current width configuration (lines 37-38):**
```python
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28 (default)
```

**Current constraints:**
- Minimum: 24 columns
- Default: 28 columns
- Maximum: 35 columns
- Step count: 6 steps

**Current CSS constraints (in both sidebar widgets):**
```css
width: 28;
min-width: 24;
max-width: 35;
```

---

## Requirements

### Functional Requirements

1. **Double Maximum Width**
   - Current max: 35 columns
   - New max: 70 columns (100% increase)

2. **Add More Width Steps**
   - Keep current steps: [24, 26, 28, 30, 32, 35]
   - Add larger steps: [40, 45, 50, 55, 60, 65, 70]
   - Total: 13 steps instead of 6

3. **Preserve Default**
   - Default width remains 28 columns
   - Default index updates to match new step array

4. **Update CSS Constraints**
   - Both sidebar widgets need `max-width: 70` in CSS
   - Update `LogGroupsSidebar` DEFAULT_CSS
   - Update `ToolCallsSidebar` DEFAULT_CSS

### Proposed Width Steps

```python
SIDEBAR_WIDTH_STEPS: list[int] = [
    24, 26, 28, 30, 32, 35,  # Original steps (small to default+)
    40, 45, 50, 55, 60, 65, 70  # New steps (medium to large)
]
```

**Step progression:**
- 24-35: Original steps (increments of 2-3)
- 35-70: New steps (increments of 5)
- Total range: 46 columns (24 to 70)

### Visual Impact

**Small (24 cols):**
```
┌─────────────────────┐
│ LOG GROUPS (15)     │
│ /aws/lambda/short   │
│ /app/api            │
└─────────────────────┘
```

**Default (28 cols):**
```
┌───────────────────────────┐
│ LOG GROUPS (15)           │
│ /aws/lambda/my-function   │
│ /app/api/production       │
└───────────────────────────┘
```

**Medium (50 cols):**
```
┌─────────────────────────────────────────────────┐
│ LOG GROUPS (15)                                 │
│ /aws/lambda/my-really-long-function-name        │
│ /app/api/production/service-name                │
└─────────────────────────────────────────────────┘
```

**Large (70 cols):**
```
┌───────────────────────────────────────────────────────────────────┐
│ LOG GROUPS (15)                                                   │
│ /aws/lambda/my-really-really-long-function-name-with-environment  │
│ /app/api/production/service-name/with-additional-context          │
└───────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### Changes Required

**File 1:** `src/logai/ui/screens/chat.py`

**Change: Update width steps (lines 37-38)**
```python
# Before:
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28 (default)

# After:
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28 (still default)
```

**File 2:** `src/logai/ui/widgets/log_groups_sidebar.py`

**Change: Update max-width in CSS**
```python
# Find DEFAULT_CSS, update max-width:
DEFAULT_CSS = """
    LogGroupsSidebar {
        # ... other styles ...
        width: 28;
        min-width: 24;
        max-width: 70;  # Changed from 35 to 70
    }
"""
```

**File 3:** `src/logai/ui/widgets/tool_sidebar.py`

**Change: Update max-width in CSS**
```python
# Find DEFAULT_CSS, update max-width:
DEFAULT_CSS = """
    ToolCallsSidebar {
        # ... other styles ...
        width: 28;
        min-width: 24;
        max-width: 70;  # Changed from 35 to 70
    }
"""
```

---

## Testing Requirements

### Automated Testing

**Update existing tests:**
- Tests that check `SIDEBAR_WIDTH_STEPS[-1]` will need updating
- Tests that verify max width of 35 should now expect 70
- No new tests needed, just update assertions

### Manual Testing

1. **Start LogAI**
   ```bash
   logai
   ```

2. **Test Expanding Left Sidebar**
   - [ ] Press F2 repeatedly to expand left sidebar
   - [ ] Verify it goes from 28 → 30 → 32 → 35 → 40 → 45 → 50 → 55 → 60 → 65 → 70
   - [ ] At 70, pressing F2 shows toast: "at maximum width"
   - [ ] Toast shows correct width at each step

3. **Test Expanding Right Sidebar**
   - [ ] Press F4 repeatedly to expand right sidebar
   - [ ] Verify same progression as left sidebar
   - [ ] Toast messages appear correctly

4. **Test Shrinking from Max**
   - [ ] Expand to 70
   - [ ] Press F1 (or F3 for right) repeatedly
   - [ ] Verify it shrinks: 70 → 65 → 60 → 55 → 50 → 45 → 40 → 35 → 32 → 30 → 28 → 26 → 24
   - [ ] At 24, shows "at minimum width"

5. **Test Large Widths Are Usable**
   - [ ] Expand left sidebar to 70
   - [ ] Verify log group names display fully (no wrapping if shorter than 70)
   - [ ] Verify content is readable
   - [ ] Expand right sidebar to 70
   - [ ] Verify tool call details are readable

6. **Test Both at Maximum**
   - [ ] Expand both sidebars to 70 each (140 cols total)
   - [ ] On a 200-col terminal: verify layout works
   - [ ] On a 100-col terminal: verify chat area shrinks but remains functional
   - [ ] Verify no visual glitches or overlaps

### Edge Cases

- [ ] **Narrow terminal (80 cols):** Expand sidebar to 70, verify chat area has at least 10 cols
- [ ] **Wide terminal (300 cols):** Both sidebars at 70, verify layout looks good
- [ ] **Toggle after resize:** Expand to 70, toggle off, toggle on → width preserved at 70
- [ ] **Multiple resize operations:** Rapid F2 presses don't cause issues

---

## Acceptance Criteria

✅ **Complete when:**

1. `SIDEBAR_WIDTH_STEPS` includes steps up to 70
2. Both sidebar widgets have `max-width: 70` in CSS
3. Default width remains 28 (index 2)
4. F2/F4 can expand sidebars to 70 columns
5. Toast notifications show correct widths
6. Manual testing passes
7. No visual regressions

---

## Files to Modify

1. `src/logai/ui/screens/chat.py` - Update SIDEBAR_WIDTH_STEPS
2. `src/logai/ui/widgets/log_groups_sidebar.py` - Update max-width to 70
3. `src/logai/ui/widgets/tool_sidebar.py` - Update max-width to 70

---

## Estimated Effort

**Total Time:** 15 minutes

- Update width steps: 2 min
- Update CSS in both widgets: 3 min
- Manual testing: 10 min

---

## Notes

- This is a simple configuration change
- No architecture review needed (Saanvi not required)
- No code review needed (Han-Ron not required) - trivial config change
- No QA needed (Raoul not required)
- No documentation update needed (users discover via F-keys)
- Just Jackie to implement and test

---

**Ready for Implementation:** ✅
**Assigned To:** Jackie (Software Engineer)
