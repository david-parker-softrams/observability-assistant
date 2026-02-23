# Multi-Select Log Groups Feature - Requirements

**Date:** February 20, 2026
**Feature Owner:** User
**Status:** Requirements Gathered

---

## Feature Overview

Enable users to select multiple log groups in the sidebar and have the agent automatically be aware of which groups are selected, allowing natural language queries like "search these for errors" without needing to say "selected" or "highlighted".

---

## User Story

**As a user**, I want to be able to select one or more log groups by clicking on them in the sidebar, so that I can tell the agent to perform operations on just those specific groups without having to list them all out or say "selected groups".

---

## Functional Requirements

### FR1: Single Selection
- **Action:** User clicks on a log group
- **Behavior:** Log group becomes highlighted/selected
- **Visual:** Selected state with distinct styling (e.g., background color change)

### FR2: Multi-Selection
- **Action:** User holds Ctrl/Cmd and clicks on another log group
- **Behavior:** Adds the log group to the current selection without deselecting others
- **Visual:** Multiple log groups show selected state simultaneously

### FR3: Preserve Double-Click Preview
- **Action:** User double-clicks on a log group
- **Behavior:** Opens the preview modal showing last 10 messages (existing functionality)
- **Requirement:** This MUST continue to work - double-click should not select the group

### FR4: Selection Persistence
- **Behavior:** Selected groups remain selected until user starts a new selection without Ctrl
- **Deselection:** Clicking on a selected group (without Ctrl) deselects all others and makes only that group selected
- **Clearing:** Starting a fresh single-click selection clears previous selection

### FR5: Agent Awareness
- **Behavior:** Agent automatically knows which log groups are currently selected
- **Natural Language:** User can say "search these for errors" or "check these groups" without explicitly saying "selected" or "highlighted"
- **Context Injection:** Selected group information should be injected into agent context in a way that makes it clear to the agent

### FR6: Visual Feedback - Selection Counter
- **Location:** Sidebar header (top of log groups panel)
- **Display:** Show count like "3 selected" or "1 group selected"
- **Visibility:** Only show when at least one group is selected
- **Update:** Counter updates in real-time as selection changes

---

## Non-Functional Requirements

### NFR1: Performance
- Selection/deselection should be instant (< 50ms response time)
- No lag when selecting multiple groups

### NFR2: Accessibility
- Keyboard navigation support (arrow keys + space to select)
- Screen reader compatible selection announcements

### NFR3: Visual Design
- Clear distinction between selected and unselected states
- Consistent with existing UI design patterns
- Not intrusive or overwhelming

---

## User Experience Requirements

### UX1: Intuitive Interaction
- Standard OS selection patterns (click, ctrl-click, double-click)
- Behavior should match user expectations from other applications

### UX2: Clear Feedback
- Immediate visual response to all selection actions
- Selection counter provides at-a-glance information

### UX3: Natural Agent Interaction
- User shouldn't need to learn special syntax
- Agent responses should reference selected groups naturally
- If no groups selected, agent should operate normally (current behavior)

---

## Technical Considerations

### Current Implementation Context
- **File:** `src/logai/ui/widgets/log_groups_sidebar.py`
- **Widget:** `LogGroupsSidebar` contains the log groups list
- **Current Interaction:** Double-click opens preview modal
- **Framework:** Textual (TUI framework)

### Integration Points
1. **Agent Context:** Need to inject selected groups into agent's context
2. **Chat Screen:** Agent needs to query current selection when processing user messages
3. **Status Indicator:** Sidebar header needs to show selection count
4. **Event Handling:** Distinguish between single-click, ctrl-click, and double-click

---

## Success Criteria

1. ✅ User can select single log group with one click
2. ✅ User can select multiple log groups with Ctrl-click
3. ✅ Double-click preview continues to work without selecting
4. ✅ Selection persists until user starts new selection
5. ✅ Agent automatically knows which groups are selected
6. ✅ User can say "search these" and agent knows what "these" refers to
7. ✅ Selection counter visible in sidebar header
8. ✅ Visual distinction between selected/unselected groups
9. ✅ No performance degradation with selection

---

## Example Usage Scenarios

### Scenario 1: Basic Single Selection
```
1. User clicks on "api-gateway" log group
2. Group highlights with selected state
3. Sidebar header shows "1 selected"
4. User types: "Show me any errors in the last hour"
5. Agent searches only the api-gateway group
```

### Scenario 2: Multi-Selection
```
1. User clicks on "api-gateway" (selected)
2. User Ctrl-clicks on "auth-service" (both selected)
3. User Ctrl-clicks on "database" (all three selected)
4. Sidebar header shows "3 selected"
5. User types: "Are there any 500 errors in these logs?"
6. Agent searches all three groups
```

### Scenario 3: Preview Still Works
```
1. User has "api-gateway" selected
2. User double-clicks "auth-service"
3. Preview modal opens showing last 10 messages from auth-service
4. Selection state unchanged (api-gateway still selected)
```

### Scenario 4: Change Selection
```
1. User has 3 groups selected
2. User clicks (without Ctrl) on a different group
3. Previous selection clears
4. New group becomes the only selected one
5. Counter updates to "1 selected"
```

---

## Questions for Design Phase

1. **Visual Design:** What color/styling should indicate selected state?
2. **Keyboard Support:** Should we support Shift-click for range selection?
3. **Deselection:** Should clicking a selected group (without Ctrl) deselect it, or make it the only selection?
4. **Empty Selection:** Should there be a way to clear all selections? (e.g., Escape key)
5. **Agent Context Format:** How should selected groups be injected into agent context? As a system message? User message?
6. **Selection Limit:** Should there be a maximum number of selectable groups?
7. **Counter Position:** Exactly where in the sidebar header should the counter appear?

---

## Out of Scope (Future Enhancements)

- Select All functionality
- Shift-click for range selection
- Right-click context menu for selected groups
- Bulk operations UI (e.g., "Export Selected")
- Save/load selection sets
- Selection history

---

**Requirements Status:** ✅ COMPLETE
**Ready for Design:** YES
**Next Step:** Saanvi to create detailed design document
