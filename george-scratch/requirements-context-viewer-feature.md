# Feature Request: Context Viewer Overlay

## Overview
Add a feature to display the current agent context in an overlay modal, accessible by clicking "Context" in the status bar. This will help users verify what the agent actually has in its context.

## Business Need
User reports that the agent seems confused about how many log entries are in context. We need visibility into what's actually being sent to the LLM to diagnose whether this is a LogAI issue or an agent reasoning issue.

## Functional Requirements

### FR-1: Context Display Modal
- **Trigger**: Click "Context" label in status bar
- **Display**: Modal overlay showing full current context
- **Content**: Exact text that will be/was sent to the LLM
- **Layout**: Similar to log preview modal (scrollable, readable)

### FR-2: Context Metadata
Display key information:
- Total character count
- Number of log entries (if applicable)
- Timestamp when context was last updated
- Context type (user-selected logs, cache guidance, etc.)

### FR-3: User Actions
- **Close**: ESC key or "Close" button
- **Copy**: Copy full context to clipboard
- **Clear**: Button to clear current context (optional)
- **Refresh**: Show live updates if context changes

### FR-4: Status Bar Integration
- Current behavior: Status bar shows "Context: X chars"
- New behavior: Clicking opens context viewer modal
- Visual feedback: Hover state, cursor pointer

## Technical Requirements

### TR-1: UI Component
- Create new `ContextViewerScreen(ModalScreen)` in `src/logai/ui/screens/`
- Inherit from Textual's `ModalScreen` for consistent modal behavior
- Use `VerticalScroll` container for scrollable content
- Similar styling to `LogPreviewScreen`

### TR-2: Data Source
- Retrieve context from `orchestrator.get_current_context()` (or similar method)
- Display exactly what's in `orchestrator._pending_context_injection`
- Show formatted, human-readable version

### TR-3: Status Bar Click Handler
- Add click handler to `StatusFooter` context label
- Emit custom message (e.g., `ContextViewRequested`)
- `ChatScreen` handles message and opens modal

### TR-4: Context Parsing
- Parse context to extract metadata:
  - Count log entries (look for "USER-SELECTED LOG ENTRIES" format)
  - Count total characters
  - Identify context sections
- Display metadata at top of modal

## User Stories

### US-1: View Current Context
**As a** user
**I want to** see exactly what context the agent has
**So that** I can verify the correct logs were added and understand why the agent responds the way it does

**Acceptance Criteria:**
- Clicking "Context" in status bar opens modal
- Modal shows full context text
- Modal shows metadata (chars, entry count)
- Can close with ESC or button

### US-2: Debug Agent Confusion
**As a** user
**I want to** verify how many log entries are in context
**So that** I can determine if the issue is with LogAI or the LLM

**Acceptance Criteria:**
- Context viewer shows exact entry count
- Can compare displayed count with what agent claims to see
- Can copy context to share for debugging

### US-3: Copy Context for Analysis
**As a** user
**I want to** copy the full context to my clipboard
**So that** I can paste it elsewhere for analysis or bug reports

**Acceptance Criteria:**
- "Copy" button in modal
- Copies full context text
- Shows confirmation message

## Design Mockup (Text-based)

```
┌─────────────────────────────────────────────────────────────┐
│ Context Viewer                                          [X] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Context Metadata:                                           │
│ • Total Size: 22,147 characters                            │
│ • Log Entries: 83 entries from /aws/lambda/my-function    │
│ • Last Updated: 2026-02-19 13:17:37                        │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ USER-SELECTED LOG ENTRIES for analysis:                    │
│                                                             │
│ Log Group: /aws/lambda/my-function                         │
│ Total Entries: 83                                          │
│                                                             │
│ Entry 1 of 83:                                             │
│ {                                                          │
│   "timestamp": 1771521463388,                              │
│   "message": "START RequestId: c16be09d...",               │
│   ...                                                      │
│ }                                                          │
│                                                             │
│ Entry 2 of 83:                                             │
│ ...                                                        │
│                                                             │
│ [Scrollable content...]                                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│           [Copy to Clipboard]  [Close]                      │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Basic Context Viewer (MVP)
1. Create `ContextViewerScreen` modal component
2. Add click handler to status bar "Context" label
3. Retrieve and display context from orchestrator
4. Basic metadata display (character count)
5. Close button and ESC key handling

### Phase 2: Enhanced Features
1. Parse context to extract log entry count
2. Add "Copy to Clipboard" functionality
3. Format display for better readability
4. Add syntax highlighting or JSON formatting

### Phase 3: Advanced Features (Optional)
1. "Clear Context" button
2. Live updates if context changes
3. Search/filter within context
4. Export to file

## Testing Requirements

### Unit Tests
- `test_context_viewer_screen.py`:
  - Test modal opens and closes
  - Test context retrieval from orchestrator
  - Test metadata parsing
  - Test copy functionality

### Integration Tests
- Test clicking status bar opens modal
- Test modal displays correct context
- Test ESC key closes modal
- Test context updates reflect in viewer

### Manual Testing
- Verify clicking "Context" opens modal
- Add log entries, verify they appear in viewer
- Test with empty context
- Test with large context (100+ entries)
- Test copy functionality works

## Success Criteria

1. ✅ Clicking "Context" in status bar opens modal
2. ✅ Modal displays full current context
3. ✅ Metadata shows character count and entry count
4. ✅ Can close with ESC or button
5. ✅ All tests pass
6. ✅ Code review: 9+/10
7. ✅ No performance degradation

## Risks & Mitigations

### Risk 1: Large Context Performance
**Risk:** Very large context (>100KB) may cause UI lag
**Mitigation:** Lazy load content, truncate display with "Show More" button

### Risk 2: Context Format Parsing
**Risk:** Context format may vary, parsing may fail
**Mitigation:** Graceful fallback to raw text display if parsing fails

### Risk 3: UI Complexity
**Risk:** Modal may be too complex or cluttered
**Mitigation:** Start with MVP, iterate based on user feedback

## Open Questions

1. Should we show historical context or only current?
2. Should "Clear Context" be included in MVP or Phase 2?
3. Should we show system prompt in addition to user context?
4. Should we display message history in addition to injected context?

## Dependencies

- Orchestrator must expose `get_current_context()` or similar method
- Status bar component must support click handlers
- May need to refactor context storage for easier retrieval

## Timeline Estimate

- **Phase 1 (MVP)**: 2-3 hours
  - Design: 30 min
  - Implementation: 60 min
  - Testing: 30 min
  - Review: 30 min

- **Phase 2**: 1-2 hours
- **Phase 3**: 2-3 hours (if needed)

**Total MVP**: ~3 hours

## Related Issues

- Context injection bug (just fixed)
- Agent confusion about log entry counts
- Need for debugging visibility

## Notes

This feature will help diagnose whether the current agent confusion is due to:
1. Context not being injected properly (LogAI issue)
2. Agent misinterpreting the context (LLM reasoning issue)
3. Context being truncated or malformed (data issue)

By providing visibility into the exact context, we can definitively identify the root cause.
