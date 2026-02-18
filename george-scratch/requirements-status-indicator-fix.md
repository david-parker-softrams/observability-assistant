# Requirements: Fix Status Indicator "Thinking" Display

**Date:** February 13, 2026
**Project:** LogAI - CloudWatch Log Analysis Tool
**Priority:** P0 - Critical UX Issue
**Estimated Effort:** 1-2 hours

---

## Executive Summary

The "thinking" status indicator that shows when the agent is actively working is currently broken. The status is being set in the code but never displayed to users, creating confusion about whether the app is working or idle. This investigation found 5 critical bugs introduced during a recent StatusBar/Footer merge (commit 9825fca).

---

## Problem Statement

### User Report
> "There used to be a 'thinking' status I saw when the agent was actively working on something, but I don't see it anymore. Can we get some kind of indication when the app has engaged the agent and is waiting for response vs when the app and agent are both idle waiting for user input?"

### Current Behavior ❌
- User sends a query
- Screen shows no indication of activity
- Agent works silently in background
- Tools execute with no visible feedback
- Results appear suddenly with no warning
- **User perception:** App is frozen or broken

### Expected Behavior ✅
- User sends a query
- Status shows "Thinking..." or "Working..."
- During tool execution: "Running tool: list_log_groups..."
- Animated spinner or loading indicator
- Status updates in real-time
- Clear distinction between working vs. idle states

---

## Root Cause Analysis

### Historical Context
**Commit 9825fca (Feb 12, 2026)** - "fix: Restore status bar visibility by merging with Footer"
- **Problem being fixed:** StatusBar and Footer both docked to bottom, causing overlay
- **Solution implemented:** Merged both widgets into unified StatusFooter
- **Bug introduced:** During merge, `status` field was added to reactive properties but never included in the `render()` method

### Technical Root Causes

1. **Status Field Not Rendered** (CRITICAL)
   - Location: `src/logai/ui/widgets/status_footer.py` lines 74-147
   - `status` is a reactive property with watch method
   - `render()` method never includes the status field in output
   - Status is set (lines 241, 267, 293 in chat.py) but invisible

2. **LoadingIndicator Timing Issue** (CRITICAL)
   - Location: `src/logai/ui/screens/chat.py` lines 244-255
   - Indicator is mounted and removed almost instantly (0-1ms)
   - No time for user to see it before removal

3. **No Status Updates During Tool Execution** (HIGH)
   - Location: `src/logai/ui/screens/chat.py` lines 226-296
   - Tools execute via orchestrator
   - Tool events fire correctly but don't update status footer
   - Status remains frozen on "Thinking..." throughout tool execution

4. **Tool Events Don't Update Footer** (HIGH)
   - Tool call listeners registered correctly
   - Sidebar updates during tool execution (working correctly)
   - No corresponding updates to status footer

5. **Dead Code** (MEDIUM)
   - Location: `src/logai/ui/widgets/status_bar.py` (140 lines)
   - Deprecated StatusBar still exists but hidden behind StatusFooter
   - Should be removed to avoid confusion

---

## Investigation Summary (by Hans)

### Key Findings

**What Exists and Works:**
- ✅ StatusFooter widget with reactive properties
- ✅ Status being set at appropriate points (query start, agent response, completion)
- ✅ Tool call listeners registered correctly
- ✅ Tool call events firing correctly
- ✅ Sidebar updates during tool execution

**What's Broken:**
- ❌ Status field never included in `render()` output
- ❌ LoadingIndicator removed immediately
- ❌ Status frozen during tool execution
- ❌ No connection between tool events and status footer updates
- ❌ No animation or visual indicators

### Files Analyzed
1. `src/logai/ui/widgets/status_footer.py` (177 lines)
2. `src/logai/ui/widgets/status_bar.py` (140 lines - deprecated)
3. `src/logai/ui/screens/chat.py` (519 lines)
4. `src/logai/ui/widgets/messages.py` (137 lines)
5. `src/logai/core/orchestrator.py` (1400+ lines)

---

## Requirements

### Functional Requirements

#### FR1: Display Status in StatusFooter
**Priority:** P0 - Critical
**Effort:** 10 minutes

- StatusFooter must display the current status message in its rendered output
- Status should be visible to the user at all times
- Status should update reactively when the `status` property changes

**Acceptance Criteria:**
- [ ] Status field appears in StatusFooter render() method
- [ ] When status is set to "Thinking...", user sees it in the UI
- [ ] Status updates are visible within 100ms of being set

#### FR2: Connect Tool Events to Status Updates
**Priority:** P0 - Critical
**Effort:** 15 minutes

- Tool execution events must update the status footer
- Status should show which tool is currently running
- Status should update when tool completes

**Acceptance Criteria:**
- [ ] When tool starts, status shows: "Running tool: {tool_name}..."
- [ ] When tool completes, status shows: "Processing results..."
- [ ] Multiple tools show progress: "Running tool 2/5: {tool_name}..."

#### FR3: Fix LoadingIndicator Timing
**Priority:** P1 - High
**Effort:** 10 minutes

- LoadingIndicator should remain visible for minimum duration
- Indicator should not flash on/off instantly
- Provide smooth user experience

**Acceptance Criteria:**
- [ ] LoadingIndicator visible for at least 200ms
- [ ] No flickering or instant disappear
- [ ] Smooth transitions

#### FR4: Add Animated Spinner
**Priority:** P1 - High
**Effort:** 20 minutes

- Status should include animated visual indicator when working
- Animation should be smooth and non-distracting
- Should work across different terminal types

**Acceptance Criteria:**
- [ ] Spinner animates during "Thinking..." status
- [ ] Spinner animates during tool execution
- [ ] Animation stops when idle
- [ ] Works in both light and dark terminals

#### FR5: Remove Deprecated StatusBar
**Priority:** P2 - Medium
**Effort:** 5 minutes

- Clean up dead code from previous implementation
- Remove deprecated StatusBar widget
- Update any references

**Acceptance Criteria:**
- [ ] `status_bar.py` file deleted
- [ ] No references to StatusBar remain
- [ ] All tests still pass

### Non-Functional Requirements

#### NFR1: Performance
- Status updates must not impact agent performance
- Animations should use minimal CPU
- No noticeable lag when updating status

#### NFR2: Compatibility
- Must work in all terminal types (xterm, iTerm2, Windows Terminal, etc.)
- Graceful degradation for terminals without animation support
- Accessible (screen readers should announce status changes)

#### NFR3: Maintainability
- Clear separation between status logic and rendering
- Well-documented code
- Unit tests for all status update paths

---

## Solution Design

### Architecture

#### Phase 1: Critical Fixes (30 min)

**1. Fix StatusFooter Rendering (10 min)**

Location: `src/logai/ui/widgets/status_footer.py`

Add status field to render() method:

```python
def render(self) -> RenderableType:
    """Render the status footer with context info and status message."""
    # ... existing context info rendering ...

    # Add status message on the left side
    if self.status:
        status_text = Text(self.status, style="dim italic")
        # Include in grid layout
```

**2. Connect Tool Events to Status (15 min)**

Location: `src/logai/ui/screens/chat.py`

Update tool event handlers to update status footer:

```python
def handle_tool_call_event(self, event: ToolCallEvent) -> None:
    """Handle tool call events and update status."""
    # Existing sidebar update
    self.tool_sidebar.handle_tool_event(event)

    # NEW: Update status footer
    if event.status == "running":
        self.footer.status = f"Running tool: {event.tool_name}..."
    elif event.status == "completed":
        self.footer.status = "Processing results..."
    elif event.status == "error":
        self.footer.status = f"Tool error: {event.tool_name}"
```

**3. Fix LoadingIndicator Timing (10 min)**

Location: `src/logai/ui/screens/chat.py`

Add minimum display duration:

```python
async def _handle_query_with_loading(self, query: str) -> None:
    """Handle query with loading indicator."""
    loading_msg = LoadingIndicator("Thinking...")
    self.messages_container.mount(loading_msg)

    # Ensure minimum visible time
    start_time = time.time()

    try:
        await self._process_query(query)
    finally:
        # Wait for minimum duration (200ms)
        elapsed = time.time() - start_time
        if elapsed < 0.2:
            await asyncio.sleep(0.2 - elapsed)

        loading_msg.remove()
```

#### Phase 2: Enhancements (30 min)

**4. Add Animated Spinner (20 min)**

Location: `src/logai/ui/widgets/status_footer.py`

```python
from textual.widgets import Static
from rich.spinner import Spinner

class StatusFooter(Static):
    # Add spinner state
    _spinner_active: bool = False

    def render(self) -> RenderableType:
        if self.status and self._spinner_active:
            spinner = Spinner("dots", text=self.status)
            # Include spinner in layout
        else:
            # Regular status text
```

**5. Tool Progress Counter (10 min)**

Track tool execution count and show progress:

```python
def handle_tool_call_event(self, event: ToolCallEvent) -> None:
    if event.status == "running":
        self._current_tool_index = event.index
        self._total_tools = event.total
        self.footer.status = f"Running tool {event.index}/{event.total}: {event.tool_name}..."
```

#### Phase 3: Cleanup (10 min)

**6. Remove Deprecated StatusBar**
- Delete `src/logai/ui/widgets/status_bar.py`
- Remove imports
- Update tests

**7. Add Integration Tests**
- Test status updates during query processing
- Test tool event handling
- Test LoadingIndicator timing

---

## Implementation Plan

### Phase 1: Critical Fixes (30 minutes)
1. **Fix StatusFooter rendering** (10 min)
   - Assign to: Jackie (Software Engineer)
   - Add status field to render() method
   - Test visibility

2. **Connect tool events** (15 min)
   - Assign to: Jackie
   - Update event handlers in chat.py
   - Add status updates for tool lifecycle

3. **Fix LoadingIndicator** (10 min)
   - Assign to: Jackie
   - Add minimum display duration
   - Test timing

### Phase 2: Enhancements (30 minutes)
4. **Add animated spinner** (20 min)
   - Assign to: Jackie
   - Implement spinner in StatusFooter
   - Test animation

5. **Add tool progress** (10 min)
   - Assign to: Jackie
   - Track and display tool count
   - Test multi-tool scenarios

### Phase 3: Cleanup (10 minutes)
6. **Remove deprecated code** (5 min)
   - Assign to: Jackie
   - Delete StatusBar file
   - Clean up references

7. **Add tests** (15 min)
   - Assign to: Raoul (QA Engineer)
   - Write integration tests
   - Verify all scenarios

### Phase 4: Review & Documentation (20 minutes)
8. **Code review** (10 min)
   - Assign to: Han-Ron (Code Reviewer)
   - Review all changes
   - Approve for commit

9. **Documentation** (10 min)
   - Assign to: Tina (Technical Writer)
   - Update user documentation
   - Document status states

---

## Success Criteria

### Must Have ✅
- [ ] Status message visible in StatusFooter when agent is working
- [ ] "Thinking..." appears when query is submitted
- [ ] Tool execution updates status in real-time
- [ ] LoadingIndicator visible for minimum 200ms
- [ ] All existing tests still pass
- [ ] Code reviewed and approved

### Nice to Have ✨
- [ ] Animated spinner during work
- [ ] Tool progress counter (1/3, 2/3, etc.)
- [ ] Smooth transitions between states
- [ ] Integration tests for status updates

### Future Enhancements 🔮
- [ ] Customizable status messages via config
- [ ] Status history/log viewer
- [ ] Estimated time remaining for long operations
- [ ] Pause/cancel functionality from status bar

---

## Testing Strategy

### Unit Tests
1. **StatusFooter Rendering**
   - Test status field appears in render output
   - Test status updates trigger re-render
   - Test empty status (no display)

2. **Tool Event Handling**
   - Test status updates on tool start
   - Test status updates on tool completion
   - Test status updates on tool error
   - Test multiple tools in sequence

3. **LoadingIndicator Timing**
   - Test minimum display duration enforced
   - Test timing with fast operations
   - Test timing with slow operations

### Integration Tests
1. **End-to-End Query Flow**
   - Submit query
   - Verify "Thinking..." appears
   - Verify tool status updates
   - Verify completion status
   - Verify return to idle

2. **Multi-Tool Scenarios**
   - Query requiring 3+ tools
   - Verify each tool updates status
   - Verify progress counter accuracy

### Manual Testing
1. **Visual Inspection**
   - Watch status footer during various queries
   - Verify smooth animations
   - Check in different terminal types
   - Test in light/dark modes

2. **Performance Testing**
   - Verify no lag during status updates
   - Check CPU usage during animations
   - Test with complex queries

---

## Risks & Mitigation

### Risk 1: Animation Performance
**Risk:** Spinner animation causes performance issues
**Impact:** Medium
**Mitigation:** Use efficient Textual spinner, limit update frequency, make configurable

### Risk 2: Terminal Compatibility
**Risk:** Animations don't work in all terminals
**Impact:** Low
**Mitigation:** Graceful degradation, static indicator as fallback

### Risk 3: Regression in Status Display
**Risk:** Changes break existing context info display
**Impact:** High
**Mitigation:** Thorough testing, careful integration, code review

### Risk 4: Race Conditions
**Risk:** Status updates arrive out of order
**Impact:** Medium
**Mitigation:** Proper async handling, state management, event sequencing

---

## Dependencies

### Code Dependencies
- Textual framework (already installed)
- Rich library for spinner (already installed)
- Asyncio for timing (standard library)

### Task Dependencies
- Must complete Phase 1 before Phase 2
- Tests should be written alongside implementation
- Documentation updated after implementation complete

### External Dependencies
- None

---

## Open Questions

1. **Spinner Style:** ✅ DECIDED - Use `dots2` (Braille pattern, smooth and elegant)
2. **Tool Progress:** Show tool count in status or separate indicator?
3. **Timing:** Is 200ms minimum display time appropriate?
4. **Fallback:** What to show when status is empty/idle?
5. **Configuration:** Should status updates be configurable?

---

## Related Work

### Recent Commits
- `9825fca` - fix: Restore status bar visibility by merging with Footer (introduced bug)
- `12e4f29` - fix: Handle Blank object in StatusFooter (partial fix)
- `3c3fb54` - feat: Add agent guidance for cached results (latest)

### Related Features
- Context Management System (status shows context usage)
- Tool Sidebar (shows tool execution, works correctly)
- Loading indicators (partially broken)

---

## Definition of Done

- [x] Requirements documented (this document)
- [ ] Architecture designed by Saanvi (if needed for complex changes)
- [ ] Implementation completed by Jackie
- [ ] Unit tests written by Raoul
- [ ] Code reviewed by Han-Ron (score 8+/10)
- [ ] Integration tests passing
- [ ] Manual testing completed
- [ ] Documentation updated by Tina
- [ ] Changes committed to git
- [ ] Status verified in production-like environment

---

## Timeline

**Total Estimated Time:** 1-2 hours

- Requirements: ✅ Complete (30 min)
- Architecture: Skip (straightforward fixes)
- Implementation: 70 minutes
  - Phase 1: 30 min (critical fixes)
  - Phase 2: 30 min (enhancements)
  - Phase 3: 10 min (cleanup)
- Testing: 15 minutes
- Review: 10 minutes
- Documentation: 10 minutes

**Target Completion:** Today (February 13, 2026)

---

## Approval

- [ ] User approved requirements
- [ ] Technical approach validated
- [ ] Ready for implementation

---

**Next Steps:**
1. Get user approval on approach
2. Assign Jackie to implementation
3. Assign Raoul to test writing
4. Monitor progress and coordinate team

---

*Document created by George (TPM)*
*Date: February 13, 2026*
