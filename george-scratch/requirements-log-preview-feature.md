# Requirements: Log Group Preview Feature

## Feature Overview

Allow users to quickly preview recent log entries from a log group by double-clicking it in the log groups sidebar. This provides immediate visibility into log content without requiring agent interaction.

## User Story

As a user, when I see a log group in the sidebar, I want to be able to double-click it to see the most recent log entries, so that I can quickly assess what's in the logs before asking the agent specific questions about them.

## Requirements

### Trigger Action
- **Double-click** on any log group name in the log groups sidebar
- Opens a log preview modal/overlay

### Display Method
- **Modal/Overlay window** that appears over the main screen
- Should be dismissible (ESC key, click outside, or close button)
- Size: Large enough to show ~10 entries clearly, but not full-screen
- Should not block access to underlying UI completely (semi-transparent backdrop)

### Data Fetching
- Fetch **most recent 10 log entries** from the selected log group
- Use CloudWatch `filter_log_events` API
- Time range: Default to last 15 minutes (or recent enough to get ~10 entries)
- No user-specified time range in MVP (keep it simple)
- Show loading indicator while fetching

### Log Entry Display Format
- **Compact view** by default:
  - Timestamp (formatted as readable date/time)
  - Message preview (first ~100 characters)
  - Click/expand to see full details
- When expanded:
  - Full message
  - All CloudWatch fields (logStreamName, etc.)
  - Formatted JSON if message is JSON

### User Actions in Preview

#### Primary: Select Specific Entries
- [ ] Checkbox next to each log entry
- [ ] "Add Selected to Context" button (disabled if none selected)
- [ ] "Select All" / "Deselect All" helper buttons
- [ ] Selected count indicator: "3 of 10 selected"

#### Secondary Actions
- [ ] Close button (X in corner)
- [ ] ESC key to close
- [ ] Click backdrop to close

### Context Integration
- When user clicks "Add Selected to Context":
  1. Close the preview modal
  2. Add selected log entries to agent context (via orchestrator)
  3. Show **system message** in chat: "Added X log entries from [log-group-name] to context"
  4. Agent can now reference these logs in subsequent queries

### Error Handling
- If log group has no recent logs: Show message "No log entries found in the last 15 minutes"
- If CloudWatch API error: Show error message with details
- If user is not authenticated: Show authentication error

## Technical Considerations

### UI Components Needed
1. **LogPreviewModal** (new component)
   - Modal overlay container
   - Header with log group name and close button
   - Loading spinner
   - Scrollable log entries list
   - Checkbox controls for selection
   - "Add Selected to Context" action button

2. **LogEntryItem** (new component)
   - Compact view by default
   - Expandable to show full details
   - Checkbox for selection
   - Timestamp + message display

### Integration Points
1. **Log Groups Sidebar**: Add double-click handler
2. **ChatScreen**: Handle modal opening/closing
3. **Orchestrator**: Add method to inject user-selected logs into context
4. **CloudWatch Tools**: Reuse existing `filter_log_events` function

### State Management
- Track which log group is being previewed
- Track which entries are selected (by checkbox)
- Track loading/error states
- Track modal open/closed state

## Success Criteria

1. ✅ User can double-click any log group in sidebar to open preview
2. ✅ Preview shows most recent 10 log entries in compact format
3. ✅ User can select individual entries with checkboxes
4. ✅ User can add selected entries to agent context
5. ✅ System message appears in chat confirming addition
6. ✅ Agent can reference the added logs in subsequent queries
7. ✅ Preview modal is easy to close (ESC, backdrop click, X button)
8. ✅ Loading states and errors are handled gracefully

## Out of Scope (Future Enhancements)

- Custom time range selection
- Pagination to load more than 10 entries
- Search/filter within preview results
- Copy to clipboard
- Export logs to file
- Auto-refresh of preview data
- Streaming/tailing logs in real-time

## User Workflow Example

1. User opens LogAI TUI
2. Presses F1 to show log groups sidebar
3. Sees `/aws/lambda/my-function` in the list
4. **Double-clicks** `/aws/lambda/my-function`
5. Modal appears showing "Loading logs..."
6. After 1-2 seconds, 10 recent log entries appear
7. User scans the entries and sees 3 interesting ones
8. User clicks checkboxes next to those 3 entries
9. User clicks "Add Selected to Context" button
10. Modal closes
11. System message appears in chat: "Added 3 log entries from /aws/lambda/my-function to context"
12. User types: "What do these logs tell us about the errors?"
13. Agent analyzes the 3 logs and provides insights

## Design Questions for Saanvi

1. Should the modal have a maximum height with scrolling, or be sized to content?
2. Should we show log stream name alongside timestamp in compact view?
3. Should the "Add to Context" button be at top or bottom of modal?
4. What's the best way to indicate "expanded" vs "compact" state for entries?
5. Should we limit the message preview length in compact view? (suggested: 100 chars)

## Implementation Notes

- Reuse existing CloudWatch authentication and API client
- Consider caching preview results briefly (30 seconds) to avoid repeated API calls
- Ensure modal is keyboard-navigable (Tab, Space for checkboxes, Enter to expand)
- Add telemetry to track usage of this feature

---

**Created**: 2026-02-18
**Requester**: User
**TPM**: George
**Status**: Ready for Design Phase
