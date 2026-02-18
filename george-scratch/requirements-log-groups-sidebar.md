# Requirements: Log Groups Sidebar in TUI

**Date:** February 12, 2026
**Requested By:** David Parker
**TPM:** George
**Target:** Saanvi (Software Architect)

---

## User Requirements

### Primary Requirements

1. **Left Sidebar Display**
   - Show complete list of CloudWatch log groups in a left sidebar
   - Sidebar should be visible by default at startup
   - Should display all log groups loaded by LogGroupManager
   - Should be a clean, readable list format

2. **User Toggle Control**
   - User can hide/show the sidebar at will
   - Needs a toggle mechanism (slash command and/or keybinding)
   - Toggle state persists during the session
   - Sidebar remembers its state (open/closed)

3. **Configuration Setting**
   - New .env setting to control default visibility
   - `LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE` (default: true)
   - If set to false, sidebar is hidden by default at startup
   - User can still toggle it open during session

4. **Dynamic Updates**
   - When `/refresh` command is executed, sidebar updates with new list
   - Updates happen automatically (no user action needed)
   - Should show count update (e.g., "135 log groups")

---

## Functional Requirements

### FR-1: Sidebar Widget

**Component:** Left sidebar showing log groups

**Layout:**
```
┌─────────────┬────────────────────────┬──────────────┐
│ Log Groups  │   Chat Messages        │ Tool Calls   │
│ (left)      │   (center)             │ (right)      │
│             │                        │              │
│ /aws/lambda │ User: Show errors      │ ◯ pending    │
│ /aws/ecs    │ Agent: Let me check... │ ✓ success    │
│ /aws/api    │                        │              │
│ ...         │                        │              │
└─────────────┴────────────────────────┴──────────────┘
```

**Specifications:**
- Width: 25-30 columns (configurable if needed)
- Position: Far left of screen
- Height: Full height
- Title: "Log Groups (135)" - shows count
- Content: Scrollable list of log group names
- Style: Match existing sidebar style (like tool sidebar)

### FR-2: Toggle Mechanism

**Options:**
1. Slash command: `/logs` or `/sidebar-logs` or `/log-groups`
2. Keybinding: `Ctrl+L` or similar
3. Both (recommended)

**Behavior:**
- Toggle between visible/hidden
- Smooth transition (not jarring)
- Other sidebars/chat adjust layout accordingly
- State persists during session (not across restarts - that's .env setting)

### FR-3: Configuration Setting

**New Environment Variable:**
```bash
# .env.example
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true  # Show log groups sidebar by default (true/false)
```

**Behavior:**
- `true` (default): Sidebar visible at startup
- `false`: Sidebar hidden at startup (can be toggled open by user)
- Validated as boolean
- Documented in configuration guide

### FR-4: Dynamic Updates

**When LogGroupManager refreshes:**
1. Sidebar automatically updates with new list
2. Count in title updates (e.g., "Log Groups (142)" if 7 new)
3. Scroll position maintained if possible
4. No user action required

**Integration Points:**
- LogGroupManager calls sidebar update method after refresh
- Sidebar subscribes to manager updates (callback pattern)

---

## Non-Functional Requirements

### NFR-1: Performance
- Rendering 1000+ log groups should be smooth
- Scrolling should be responsive
- Updates should not block UI

### NFR-2: Usability
- Log group names should be fully visible (or truncated with ellipsis)
- Clear visual separation from chat area
- Easy to scan/read
- Scroll bar visible when content exceeds height

### NFR-3: Consistency
- Match existing UI design patterns (like tool sidebar)
- Use consistent colors, borders, styling
- Similar toggle behavior to tool sidebar (`/tools` command)

### NFR-4: Accessibility
- Keyboard navigation within sidebar (arrow keys)
- Clear visual indicators for selected/focused items
- Works well with screen readers (if Textual supports this)

---

## Technical Considerations

### Existing UI Structure

We already have a **right sidebar** for tool execution (ToolCallsSidebar). Now we're adding a **left sidebar** for log groups.

**Current Layout:**
```
┌────────────────────────────┬──────────────┐
│   Chat Messages            │ Tool Calls   │
│   (main area)              │ (right 28col)│
└────────────────────────────┴──────────────┘
```

**New Layout:**
```
┌─────────────┬────────────────────────┬──────────────┐
│ Log Groups  │   Chat Messages        │ Tool Calls   │
│ (left 28col)│   (center)             │ (right 28col)│
└─────────────┴────────────────────────┴──────────────┘
```

### Components to Create/Modify

1. **New Widget:** `src/logai/ui/widgets/log_groups_sidebar.py`
   - Similar to ToolCallsSidebar
   - Displays scrollable list
   - Updates on manager refresh

2. **Modify ChatScreen:** `src/logai/ui/screens/chat.py`
   - Add left sidebar to layout
   - Handle toggle state
   - Adjust horizontal layout (left sidebar + chat + right sidebar)

3. **Modify Settings:** `src/logai/config/settings.py`
   - Add `log_groups_sidebar_visible: bool = True`

4. **Modify Commands:** `src/logai/ui/commands.py`
   - Add `/logs` or similar toggle command

5. **Update .env.example**
   - Add new setting with documentation

### Integration with LogGroupManager

**Sidebar needs to:**
1. Get initial log group list from manager at startup
2. Subscribe to manager updates (when `/refresh` is called)
3. Update display when new list arrives

**Manager needs to:**
- Support callback registration for sidebar updates
- Call sidebar update method after successful refresh

### Layout Management

**Textual Layout Considerations:**
- Use Horizontal container with conditional rendering
- Sidebars use fixed widths (25-30 columns each)
- Chat area uses remaining space (1fr)
- Handle responsive behavior if terminal is narrow

**Example Layout Code:**
```python
with Horizontal():
    if self.log_groups_sidebar_visible:
        yield LogGroupsSidebar(id="log-groups-sidebar")
    yield VerticalScroll(id="messages-container")  # 1fr
    if self.tool_sidebar_visible:
        yield ToolCallsSidebar(id="tool-sidebar")
```

### State Management

**Toggle State:**
- Store in ChatScreen instance variable
- Update on toggle command
- Trigger layout refresh when toggled

**Default Visibility:**
- Read from settings at ChatScreen initialization
- Respect user's .env configuration

---

## Design Questions for Saanvi

1. **Widget Design:**
   - Should we subclass Tree (like ToolCallsSidebar) or use ListView?
   - How to handle very long log group names (truncate? wrap? tooltip?)
   - Should log groups be grouped/organized (by prefix like /aws/lambda, /aws/ecs)?

2. **Toggle Command:**
   - Command name: `/logs`, `/sidebar-logs`, `/log-groups`, `/toggle-logs`?
   - Keybinding: `Ctrl+L`, `Ctrl+G`, or other?
   - Should toggle affect both sidebars or just log groups sidebar?

3. **Layout Strategy:**
   - Fixed widths for both sidebars or proportional?
   - What if terminal is too narrow for both sidebars? Hide one? Overlay?
   - Should sidebars be resizable (drag to resize)?

4. **Update Mechanism:**
   - Callback pattern (manager → sidebar)?
   - Event system (manager emits event, sidebar listens)?
   - Direct method call from refresh command?

5. **Sidebar Width:**
   - 25 columns? 30 columns? Configurable?
   - Same as tool sidebar (28) for consistency?

6. **Visual Design:**
   - Simple list (like file explorer)?
   - Grouped by prefix (expandable tree)?
   - Search/filter capability?
   - Highlight/select capability?

7. **State Persistence:**
   - Toggle state persists during session only (not across restarts)?
   - Should scroll position persist after refresh?

---

## User Experience Flow

### Scenario 1: Default Startup
```
1. User starts LogAI
2. App loads log groups (progress indicator)
3. Chat screen appears with:
   - Left sidebar showing all 135 log groups
   - Chat area in center
   - Tool sidebar on right (if enabled)
4. User can see log groups at a glance
```

### Scenario 2: Toggle Sidebar
```
1. User types /logs (or presses Ctrl+L)
2. Left sidebar hides
3. Chat area expands to use the space
4. User types /logs again
5. Left sidebar reappears
```

### Scenario 3: Refresh Updates
```
1. User creates new log group in AWS
2. User types /refresh
3. Progress indicator shown
4. Log group list updates in sidebar
5. Title shows new count: "Log Groups (136)"
6. User sees new log group in list
```

### Scenario 4: Hidden by Default
```
1. User sets LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=false in .env
2. User starts LogAI
3. Chat screen appears without left sidebar
4. User types /logs to open it
5. Sidebar appears with log groups
```

---

## Success Criteria

Feature is successful if:

1. ✅ Left sidebar displays all log groups at startup
2. ✅ Sidebar is visible by default (unless configured otherwise)
3. ✅ User can toggle sidebar with command/keybinding
4. ✅ .env setting controls default visibility
5. ✅ Sidebar updates automatically on /refresh
6. ✅ Layout works with 0, 1, or 2 sidebars visible
7. ✅ Performance is good with 1000+ log groups
8. ✅ Matches existing UI style and patterns

---

## Out of Scope

- Search/filter functionality in sidebar (can be added later)
- Click to insert log group name into chat (can be added later)
- Drag-to-resize sidebar width (fixed width for now)
- Custom grouping/organization (simple list for now)
- Persistent toggle state across restarts (use .env for that)

---

## Priority

**High** - Significantly improves usability, user is waiting to test

---

## Notes

- We already have experience with ToolCallsSidebar (right side)
- Should follow similar patterns for consistency
- LogGroupManager integration point already exists (can add callbacks)
- Textual layout system supports multiple sidebars

---

**Ready for Saanvi's architectural design.**
