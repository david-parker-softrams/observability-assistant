# Context Viewer Enhancement - Show Both Staged and Active Context

## Problem

**Current Behavior:**
- Context Viewer shows only `_pending_context_injection` (staged logs waiting to be injected)
- After sending first message, `_pending_context_injection` is cleared (consumed by orchestrator)
- User clicks Context again → sees empty modal (confusing!)

**Root Cause:**
- `orchestrator._pending_context_injection` is a **one-time staging area**, not persistent memory
- Line 486 in `orchestrator.py`: `self._pending_context_injection = None` (clears after use)

## User Request

Show **BOTH** contexts separately:
1. **Staged Context** - What WILL BE injected in the next message (`_pending_context_injection`)
2. **Agent Memory** - What the agent ACTUALLY has in its memory right now (full conversation history)

## Design Requirements

### Two-Section Modal Layout

```
┌─────────────────────────────────────────────────┐
│ View Agent Context                        [Copy] │
├─────────────────────────────────────────────────┤
│                                                   │
│ ▼ Staged Context (0 items)                      │
│   ─────────────────────────────────────────────  │
│   No logs staged for injection                   │
│                                                   │
│ ▼ Agent Memory (24 messages)                    │
│   ─────────────────────────────────────────────  │
│   System: You are LogAI, an observability...    │
│   User: Show me errors in service X              │
│   Assistant: I'll query the logs for...          │
│   Tool Call: query_logs(...)                     │
│   Tool Result: [50 matching entries]             │
│   ...                                            │
│                                                   │
└─────────────────────────────────────────────────┘
```

### Section 1: Staged Context
- **Source:** `orchestrator._pending_context_injection`
- **Show when:** Not None and has content
- **Empty state:** "No logs staged for injection"
- **Format:** Raw text of pending log entries

### Section 2: Agent Memory
- **Source:** `orchestrator.conversation_history` (list of messages)
- **Show:** Full conversation including:
  - System messages
  - User messages
  - Assistant messages
  - Tool calls (formatted)
  - Tool results (formatted)
- **Format:** Structured, readable format with role labels

### Collapsible Sections (Nice-to-Have)
- Each section can be collapsed/expanded independently
- Default state: Both expanded
- Use Textual `Collapsible` widget

### Copy Button Behavior
- Copy BOTH sections to clipboard
- Format with clear section separators:
  ```
  ===== STAGED CONTEXT =====
  [content or "None"]

  ===== AGENT MEMORY =====
  [full conversation history]
  ```

## Data Sources

### Current Access
✅ **Staged Context:** `self.orchestrator._pending_context_injection` (already used)

### Need to Add
❌ **Agent Memory:** Need access to `orchestrator.conversation_history`

**Question for Saanvi:** Should we:
1. Access `orchestrator.conversation_history` directly (already exists)
2. Add a new public getter method like `get_conversation_history()`
3. Add a comprehensive `get_full_context()` method that returns both staged and active context

## Success Criteria

1. ✅ Clicking "Context: X items" opens modal with TWO sections
2. ✅ Staged section shows pending logs (or "None" if empty)
3. ✅ Agent Memory section shows full conversation history
4. ✅ After sending a message:
   - Staged section → empty (expected - consumed)
   - Agent Memory section → shows the conversation including the new exchange
5. ✅ Copy button copies both sections with clear separators
6. ✅ Performance: No hanging with 100+ log entries + long conversation (use RichLog)

## Open Questions for Saanvi

1. **Architecture:** How should ChatScreen access conversation history?
   - Direct access to `orchestrator.conversation_history`?
   - New public API method?
   - Event-based subscription?

2. **Format:** How should we format conversation history for display?
   - JSON dump?
   - Custom formatter (pretty-printed with roles)?
   - Markdown-like format?

3. **Token limits:** Should we truncate very large histories?
   - Show last N messages only?
   - Show full history (let RichLog handle virtual rendering)?
   - Add pagination?

4. **Real-time updates:** Should context update while modal is open?
   - Static snapshot when opened?
   - Live updates if conversation continues?

## Related Files

- `src/logai/ui/screens/context_viewer.py` - Modal implementation
- `src/logai/ui/screens/chat.py` - Handler that opens modal
- `src/logai/core/orchestrator.py` - Data source
- `src/logai/ui/widgets/status_footer.py` - Trigger widget

## Timeline

1. Saanvi: Update design (~15 min)
2. Jackie: Implement two-section modal (~30 min)
3. User testing: Verify behavior
4. Han-Ron: Code review
5. Raoul: Write tests
6. Commit & push
