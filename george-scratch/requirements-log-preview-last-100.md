# Requirements: Log Preview - Pull Last 100 Entries Button

**Date**: February 19, 2026
**Feature**: Add button to log preview overlay to fetch last 100 entries
**Priority**: Medium
**Status**: In Progress

---

## Overview

Add a button to the log preview modal that allows users to fetch the last 100 log entries. Currently, the log preview fetches 10 entries by default. This enhancement will allow users to see more context when needed.

---

## User Story

**As a** user viewing logs in the preview modal
**I want** a button to fetch the last 100 entries
**So that** I can see more historical context without changing the default behavior

---

## Requirements

### Functional Requirements

1. **Default Behavior**
   - Log preview should continue to fetch **10 entries by default** when opened
   - No change to existing default behavior

2. **New Button**
   - Add a "Load Last 100" button (or similar label) to the log preview UI
   - Button should be clearly visible and accessible
   - Button should fetch the last 100 entries when clicked

3. **Button Behavior**
   - Clicking the button should fetch the last 100 entries from the selected time frame
   - Should replace the current entries in the view (not append)
   - Should show a loading indicator while fetching
   - Should handle errors gracefully with user feedback

4. **Visual Feedback**
   - Show loading state while fetching
   - Indicate how many entries are currently displayed (e.g., "Showing 10 entries" or "Showing 100 entries")
   - Button should be disabled during fetch operation

5. **Integration with Existing Features**
   - Should work with the existing time frame selector (15 min, 1 hour, 8 hours, 24 hours)
   - Should work with existing log selection and export features
   - Should respect the current log group being viewed

### Non-Functional Requirements

1. **Performance**
   - Fetching 100 entries should complete within reasonable time (< 5 seconds typical)
   - Should not block the UI during fetch

2. **Usability**
   - Button should be intuitive and easy to find
   - Label should clearly indicate what the button does
   - Should be consistent with existing UI patterns in the application

3. **Testing**
   - Unit tests for new functionality
   - Integration tests with time frame selector
   - Edge case testing (no logs, errors, etc.)

---

## User Interface

### Proposed Button Placement

Options (Saanvi to decide):
1. **Next to time frame selector** - Logical grouping with other controls
2. **In the action buttons area** - Near Export Selected/Cancel buttons
3. **Below the header** - Separate row for fetch controls

### Proposed Label Options

- "Load Last 100" (clear and direct)
- "Show More (100)" (indicates expansion)
- "Fetch 100 Entries" (explicit about action)
- "Last 100 Entries" (concise)

### Entry Count Display

- Show current count somewhere visible: "Showing X entries"
- Update after fetch: "Showing 10 entries" → "Showing 100 entries"

---

## Technical Considerations

### Current Implementation

The log preview currently:
- Fetches logs in `_fetch_and_display_logs()` method
- Uses `time_range_minutes` property to determine time window
- Has a time frame selector with reactive updates
- Default fetch limit is likely hardcoded to 10

### Implementation Approach

1. **Add max_results parameter**
   - Add a reactive property for max_results (default: 10)
   - Modify fetch method to use max_results parameter
   - Pass max_results to the datasource fetch call

2. **Add button to UI**
   - Add button in compose() method
   - Wire up button click handler
   - Update button state during fetch

3. **Add entry count display**
   - Show current count in the UI
   - Update after each fetch

4. **Handle button click**
   - Set max_results to 100
   - Call fetch method
   - Update UI with results

---

## Acceptance Criteria

- [ ] Log preview opens with default 10 entries (existing behavior preserved)
- [ ] "Load Last 100" button is visible and accessible in the UI
- [ ] Clicking the button fetches the last 100 entries from the selected time frame
- [ ] Loading indicator shows while fetching
- [ ] Entry count display shows "Showing X entries" and updates correctly
- [ ] Button is disabled during fetch operation
- [ ] Works correctly with all time frame options (15 min, 1 hour, 8 hours, 24 hours)
- [ ] Existing features (selection, export) work correctly with 100 entries
- [ ] Error handling works correctly (shows error message to user)
- [ ] Unit tests added and passing
- [ ] Integration tests added and passing
- [ ] Code review approved
- [ ] QA testing approved

---

## Out of Scope

- Arbitrary entry count input (user specifying custom number like 50, 200, etc.)
- Pagination or "load more" functionality
- Changing the default from 10 to another number
- Fetching more than 100 entries

---

## Dependencies

- Existing log preview implementation (`src/logai/ui/screens/log_preview.py`)
- CloudWatch datasource implementation
- Time frame selector feature (recently implemented)

---

## Risks & Mitigations

### Risk: Fetching 100 entries is too slow
**Mitigation**: Show loading indicator, consider adding timeout handling

### Risk: UI becomes cluttered with additional button
**Mitigation**: Saanvi will design clean placement that fits existing layout

### Risk: Breaking existing functionality
**Mitigation**: Comprehensive testing, preserve default behavior

---

## Timeline Estimate

- Investigation: 30 minutes
- Design: 30-45 minutes
- Implementation: 1-2 hours
- Testing: 1 hour
- Code Review: 30 minutes
- QA: 30 minutes
- Documentation: 30 minutes

**Total**: ~4-6 hours

---

## Notes

- This is an enhancement to the recently implemented time frame selector feature
- Should follow the same patterns and conventions established in that implementation
- User explicitly requested default of 10 with button to load 100
- Keep it simple - don't over-engineer with complex pagination or infinite scroll

---

**Next Steps**:
1. Hans investigates current implementation
2. Saanvi creates design document
3. Jackie implements feature
4. Han-Ron reviews code
5. Raoul writes and runs tests
6. Tina documents the feature
