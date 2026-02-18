# Requirements: Adjustable Time Frame for Log Preview Feature

## Overview
Enhance the log preview feature to allow users to adjust the time frame for viewing log entries beyond the default 15 minutes.

## Current Behavior
- Users double-click a log group in the sidebar
- System fetches and displays the most recent 10 log entries from the past 15 minutes
- Time frame is hard-coded and not adjustable

## Requested Enhancement
Add a time frame selector that allows users to choose between multiple time windows:
- **15 minutes** (default, current behavior)
- **1 hour**
- **8 hours**
- **24 hours**

## User Stories

### US-1: View Time Frame Options
**As a user**, when I open the log preview modal, **I want to see** the current time frame setting and available options, **so that** I can understand what time window I'm viewing.

### US-2: Change Time Frame
**As a user**, **I want to** easily change the time frame selection, **so that** I can view logs from different time windows without closing and reopening the modal.

### US-3: Retain Default Behavior
**As a user**, **I want** the default time frame to remain 15 minutes, **so that** my existing workflow is not disrupted.

### US-4: See Updated Results
**As a user**, when I change the time frame, **I want** the log entries to automatically refresh with the new time window, **so that** I see relevant logs immediately.

## Functional Requirements

### FR-1: Time Frame Options
The system shall provide exactly four time frame options:
- 15 minutes (default)
- 1 hour
- 8 hours
- 24 hours

### FR-2: UI Control
The system shall display a time frame selector control in the log preview modal that:
- Shows the currently selected time frame
- Allows users to select a different time frame
- Is clearly visible and easily accessible

### FR-3: Automatic Refresh
When the user changes the time frame selection:
- The system shall automatically fetch new log entries for the selected time window
- The system shall update the display with the new results
- The system shall maintain the current log group being viewed

### FR-4: Default Behavior
- The default time frame shall be 15 minutes
- This shall apply when opening any log preview modal

### FR-5: Performance
- Time frame changes should complete within 2 seconds under normal conditions
- The UI should remain responsive during data fetching

## Non-Functional Requirements

### NFR-1: Usability
- The time frame selector should be intuitive and require no documentation
- The control should follow Textual UI conventions and styling

### NFR-2: Consistency
- The time frame selector styling should match the existing log preview modal design
- Button/control behavior should be consistent with other UI elements

### NFR-3: Testing
- All time frame options must be covered by unit tests
- Integration tests should verify correct data fetching for each time window
- Error handling should be tested (e.g., no logs available in time window)

## Technical Considerations

### Data Fetching
- Use CloudWatch Logs API with appropriate time ranges
- Convert time frame selection to milliseconds for timestamp calculations
- Maintain limit of 10 most recent log entries (regardless of time frame)

### UI Implementation Options
The design team should consider:
1. Radio buttons (vertical or horizontal layout)
2. Dropdown/select control
3. Button group (like a segmented control)
4. Tabs

The chosen approach should prioritize:
- Ease of use
- Clear visibility of current selection
- Minimal space consumption in the modal

### State Management
- Time frame selection should be specific to each modal instance
- Consider whether to persist the user's last selection across modal opens (optional enhancement)

## Success Criteria
- [ ] User can see and select all four time frame options
- [ ] Changing time frame automatically refreshes log entries
- [ ] Default remains 15 minutes when opening modal
- [ ] All unit tests pass (target: 100% coverage of new code)
- [ ] No performance degradation compared to current implementation
- [ ] UI follows Textual conventions and matches existing styling
- [ ] Code review approval from Han-Ron
- [ ] QA approval from Raoul

## Out of Scope (Future Enhancements)
- Custom time frame input (user-specified duration)
- Relative time frames (e.g., "last hour" vs. "1:00 PM - 2:00 PM")
- Persisting user's preferred time frame across sessions
- Different time frames for different log groups

## Questions for Design Team
1. What UI control type should we use for time frame selection?
2. Where should the control be positioned in the modal?
3. Should we show a loading indicator when fetching logs for a new time frame?
4. Should we disable the time frame selector while fetching data?

---

**Created**: 2026-02-18
**Author**: George (TPM)
**Status**: Draft - Ready for Design Phase
