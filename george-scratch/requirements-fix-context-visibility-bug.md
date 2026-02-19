# Requirements: Fix Context Visibility Bug

**Date:** February 19, 2026
**Priority:** CRITICAL
**Type:** Bug Fix (UX)
**Estimated Time:** 20 minutes implementation + 10 minutes testing

## Problem Statement

Users click "Add to Context" to provide logs to the AI agent, but when they ask the agent to analyze the logs, the agent responds "I need a log group to search" instead of analyzing the provided logs.

**Root Cause:** The agent's system prompt never mentions that user-provided logs might exist in context or that they should be prioritized over tool calls.

**Investigation:** Hans completed comprehensive investigation (2 hours). Found that 13/14 components work perfectly - logs ARE reaching the agent. Only the system prompt needs updating.

## User Impact

- **Current Behavior:** Feature appears broken, undermines user confidence
- **Expected Behavior:** Agent immediately analyzes provided logs without asking to search
- **Severity:** HIGH - Core feature appears non-functional to users

## Requirements

### REQ-1: Update System Prompt (CRITICAL)
**File:** `src/logai/core/orchestrator.py`
**Location:** After line 300 (end of SYSTEM_PROMPT)

Add new section to system prompt that:
1. Explains that users can provide log entries via "Add to Context"
2. Teaches agent to recognize the "USER-SELECTED LOG ENTRIES" prefix
3. Instructs agent to ALWAYS analyze provided logs FIRST before using tools
4. Explicitly states: "Do NOT ignore provided logs and ask to search"

**Acceptance Criteria:**
- System prompt includes "User-Provided Log Entries" section
- Agent knows to look for "USER-SELECTED LOG ENTRIES" marker
- Agent prioritizes context logs over tool calls
- Instructions are clear and unambiguous

### REQ-2: Strengthen Context Message Tone (HIGH)
**File:** `src/logai/ui/screens/chat.py`
**Location:** Lines 431-442 (context injection message)

Change message tone from suggestive to commanding:
- **Current:** "Please analyze these logs and provide insights..."
- **New:** "YOU MUST analyze these logs. Do NOT ask for a log group to search."

**Acceptance Criteria:**
- Message is more commanding and explicit
- Message reinforces the system prompt instructions
- Tone prevents agent from ignoring context

## Testing Requirements

### Manual Test Scenario
1. Open log preview pane
2. Select 3-5 log entries
3. Click "Add to Context"
4. Verify UI shows "Added X entries to context"
5. Ask agent: "Categorize these logs"
6. **Expected:** Agent analyzes provided logs without tool calls
7. **Expected:** Agent mentions specific log content in response
8. **Fail Condition:** Agent asks "Which log group should I search?"

### Edge Cases to Test
1. Empty log selection (should show error, not add to context)
2. Single log entry
3. Large number of log entries (100+)
4. Multiple "Add to Context" operations in same conversation
5. Asking different questions about same context logs

## Non-Requirements

- ❌ Do NOT change the data flow infrastructure (it works perfectly)
- ❌ Do NOT modify log formatting or storage
- ❌ Do NOT change the UI for "Add to Context" button
- ❌ Do NOT add new features beyond fixing the bug

## Success Criteria

1. **Functional:** Agent analyzes provided context logs without asking to search
2. **User Experience:** Feature works as users expect
3. **Code Quality:** Changes are minimal, focused, and well-documented
4. **Testing:** All manual test scenarios pass
5. **Review:** Code review score ≥ 9/10
6. **No Regressions:** All existing tests still pass

## Technical Constraints

- Changes must be minimal (system prompt + message tone only)
- Must not break existing functionality
- Must maintain current context injection infrastructure
- Must work with all LLM providers

## Reference Documents

- `CONTEXT_BUG_EXECUTIVE_BRIEF.txt` - Executive summary
- `CONTEXT_BUG_CODE_MAP.txt` - Exact code locations and changes
- `CONTEXT_UX_BUG_INVESTIGATION.md` - Complete investigation (Hans)

## Timeline

1. **Requirements:** ✅ Complete
2. **Implementation:** 20 minutes (Jackie)
3. **Testing:** 10 minutes (Raoul + manual)
4. **Code Review:** 5 minutes (Han-Ron)
5. **Deploy:** 5 minutes

**Total:** ~40 minutes end-to-end

## Approval

Ready for implementation: ✅ YES
Investigation complete: ✅ YES
Requirements clear: ✅ YES
Risk level: LOW (prompt changes only)

---

**Next Steps:**
1. Hand to Jackie for implementation
2. Raoul tests with scenarios above
3. Han-Ron reviews code
4. Commit and deploy
