# Requirements: Remove Log Group Name Truncation

**Date:** 2026-02-12
**Requestor:** David Parker
**Priority:** High (Usability Issue)
**Status:** New

## Problem Statement

The log groups sidebar currently truncates long log group names with ellipsis (`...`) in the middle to fit within the 28-column sidebar width. This prevents users from:
1. Seeing the full log group name at a glance
2. Easily copying/pasting full log group names into the chat

**Example of current behavior:**
```
/aws/lambda/very-lon...function-name
```

**User expectation:**
```
/aws/lambda/very-long-service-function-name
```

## Requirements

### Functional Requirements

**FR1: Display Full Log Group Names**
- The sidebar MUST display complete log group names without truncation
- All characters of the log group name MUST be visible

**FR2: Enable Easy Copy/Paste**
- Users MUST be able to copy full log group names from the sidebar
- Names should be easily selectable and copyable in the terminal

**FR3: Handle Long Names Gracefully**
- The sidebar should handle log group names of any length
- Long names should wrap to multiple lines OR
- The sidebar should allow horizontal scrolling

### Design Constraints

**DC1: Maintain Readability**
- The solution must maintain readability of the log group list
- Users should still be able to scan the list quickly

**DC2: Preserve Existing Functionality**
- Toggle behavior (`/logs` command) must continue to work
- Auto-update on `/refresh` must continue to work
- Sidebar width and visibility settings must remain unchanged

**DC3: Textual Framework Limitations**
- Solution must work within Textual's widget capabilities
- Must support terminal copy/paste operations

## Proposed Solutions

### Option 1: Multi-line Wrapping (Recommended)
- Display each log group name with word wrapping enabled
- Long names wrap to multiple lines within the 28-column sidebar
- Preserves sidebar width and layout
- **Pros:** Easy to implement, maintains layout, all names fully visible
- **Cons:** Very long names take more vertical space

### Option 2: Increase Sidebar Width
- Increase sidebar from 28 columns to 40-50 columns
- Reduces truncation for most log group names
- **Pros:** Most names fit on one line
- **Cons:** Reduces chat area width, some names still truncated

### Option 3: Dynamic Width Sidebar
- Sidebar width adjusts based on longest log group name
- **Pros:** All names fit perfectly
- **Cons:** Complex to implement, inconsistent layout, can overtake chat area

### Option 4: Horizontal Scrolling
- Fixed 28-column sidebar with horizontal scroll for long names
- **Pros:** Maintains vertical compactness
- **Cons:** Hidden content, harder to discover, poor UX

## Recommendation

**Use Option 1: Multi-line Wrapping**

This is the simplest solution that fully addresses the user's needs:
- Full names are always visible
- Easy to copy/paste
- Maintains sidebar width and layout
- Works within Textual's capabilities

## Implementation Notes

### Files to Modify

1. **`src/logai/ui/widgets/log_groups_sidebar.py`**
   - Remove `_truncate_name()` method (lines 166-192)
   - Update `_render_log_groups()` to not call `_truncate_name()`
   - Enable word wrapping on Label widgets or use Text with wrapping

2. **`tests/unit/test_log_groups_sidebar.py`**
   - Remove `TestLogGroupsSidebarTruncation` class (truncation tests)
   - Update tests that expect truncated names

3. **`tests/integration/test_log_groups_sidebar_integration.py`**
   - Update any tests that verify truncation behavior

### Technical Approach

**Current Code (to be removed):**
```python
truncated = self._truncate_name(name, max_width=26)
self.mount(Label(truncated))
```

**New Code (proposed):**
```python
# Option A: Use Label with word_wrap
label = Label(name)
label.styles.text_overflow = "wrap"
self.mount(label)

# Option B: Use Text widget with wrapping
from textual.widgets import Static
static = Static(name)
static.styles.overflow_x = "hidden"
static.styles.overflow_y = "auto"
self.mount(static)
```

### Textual Styling

Add CSS rules to enable wrapping:
```python
LogGroupsSidebar.STYLES = """
LogGroupsSidebar > Label {
    width: 100%;
    overflow: wrap;
}
"""
```

## Acceptance Criteria

**AC1:** No log group names are truncated with ellipsis
**AC2:** All characters of all log group names are visible in the sidebar
**AC3:** Long names wrap to multiple lines within the 28-column sidebar
**AC4:** Users can copy/paste full log group names from the sidebar
**AC5:** Sidebar toggle and refresh functionality continues to work
**AC6:** All existing tests pass (except truncation-specific tests)
**AC7:** New tests verify full names are displayed

## Testing Requirements

1. **Unit Tests:** Verify no truncation occurs, wrapping behavior works
2. **Integration Tests:** Verify layout with very long log group names
3. **Manual Tests:**
   - Test with log group names > 50 characters
   - Verify copy/paste functionality in terminal
   - Verify scrolling with many long names

## Non-Goals

- Changing the sidebar width (remains 28 columns)
- Adding horizontal scrolling
- Adding collapsible groups or trees
- Filtering or searching log group names

## References

- Original architecture: `george-scratch/architecture-log-groups-sidebar.md`
- Current implementation: `src/logai/ui/widgets/log_groups_sidebar.py`
- Textual documentation: https://textual.textualize.io/
