# Requirements: Fix Context Message Ordering

**Date:** February 19, 2026
**Priority:** CRITICAL
**Type:** Bug Fix (Message Ordering)
**Context:** Second attempt to fix context visibility bug

## Problem Statement

User reports that after our first fix (commit d6703d0), the "Add to Context" feature STILL doesn't work. The agent still says it can't see logs in context.

**Root Cause Identified:** Message ordering issue. The LLM receives messages in this order:
1. System prompt (with our new instructions)
2. User message: "Analyze these logs"
3. Context injection: "Here are the logs: [data]"

The LLM processes the user's request BEFORE seeing the actual log data, so it decides it needs to search for logs.

**Location:** `src/logai/core/orchestrator.py` lines 1015-1022

## Current Code (BROKEN)

```python
# Prepare messages with system prompt
messages = [
    {"role": "system", "content": self._get_system_prompt()}
] + self.conversation_history  # <-- User message is here

# Check for pending context injection
pending_injection = self._get_pending_context_injection()
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})  # <-- Context AFTER user message
```

## Required Fix

Reorder messages so context injection appears BEFORE the user's latest message, but AFTER the conversation history (excluding the latest message).

**New Order Should Be:**
1. System prompt
2. Conversation history (excluding latest user message)
3. **Context injection** ← Move here
4. Latest user message

This way the LLM sees the log data BEFORE processing the user's request to analyze it.

## Implementation Requirements

### REQ-1: Reorder Message Construction (CRITICAL)

**Approach:**
1. Build messages array with system prompt
2. Add conversation history EXCEPT the last message (if it's a user message)
3. Check for and add pending context injection
4. Add the last user message

**Pseudo-code:**
```python
messages = [{"role": "system", "content": self._get_system_prompt()}]

# Split conversation history
if self.conversation_history and self.conversation_history[-1]["role"] == "user":
    # Separate last user message
    history_before_last = self.conversation_history[:-1]
    last_user_message = self.conversation_history[-1]

    messages.extend(history_before_last)

    # Add context injection BEFORE last user message
    pending_injection = self._get_pending_context_injection()
    if pending_injection:
        messages.append({"role": "system", "content": pending_injection})

    messages.append(last_user_message)
else:
    # No user message at end, proceed normally
    messages.extend(self.conversation_history)
    pending_injection = self._get_pending_context_injection()
    if pending_injection:
        messages.append({"role": "system", "content": pending_injection})
```

**Acceptance Criteria:**
- Context injection appears BEFORE latest user message
- Conversation history is preserved in correct order
- Edge cases handled (empty history, no context, assistant message last)
- All existing tests still pass

### REQ-2: Handle Edge Cases

1. **Empty conversation history**: Just system prompt + context + user message
2. **No context injection**: Work exactly as before
3. **Last message is assistant**: Don't try to move it, append context at end
4. **Multiple user messages**: Only the LATEST one should come after context

### REQ-3: Preserve Existing Behavior

- Don't break tool calling flow
- Don't break context clearing (line 1012)
- Don't break budget tracking
- Don't break conversation history management

## Testing Requirements

### Unit Tests to Update

1. **test_orchestrator_context.py**: Update expectations for message ordering
   - Test that context appears before user message
   - Test edge cases

2. **test_context_visibility_bug_fix.py**: The 17 tests we just created
   - These might need updates if they check message order
   - Verify they all still pass

### Manual Test Scenario (USER'S EXACT SCENARIO)

1. Start application
2. Open log preview pane
3. Select some log entries
4. Click "Add to context"
5. Ask: "Review the logs in context"
6. **EXPECTED**: Agent sees logs and analyzes them
7. **EXPECTED**: Agent does NOT say "I can't see logs in context"
8. **FAIL IF**: Agent still can't see the logs

### Verification

After fix, the message array sent to LLM should look like:
```
[
  {"role": "system", "content": "SYSTEM_PROMPT with instructions..."},
  {"role": "system", "content": "USER-SELECTED LOG ENTRIES: [log data]"},  # Context BEFORE user message
  {"role": "user", "content": "Review the logs in context"}  # User message AFTER context
]
```

## Why Our First Fix Failed

Our first fix (commit d6703d0) was correct in principle:
- ✅ System prompt told agent to look for user-provided logs
- ✅ Message tone was commanding
- ✅ Infrastructure worked perfectly

**BUT** we didn't realize the logs appeared AFTER the user's message, so the LLM processed the request without seeing the data first.

It's like asking someone "What's in this box?" but handing them the box AFTER they answer. Of course they say "I don't know - I don't have the box yet!"

## Success Criteria

1. **Functional**: Agent analyzes provided context logs without asking to search
2. **User Validation**: User confirms the fix works in their environment
3. **Testing**: All existing tests pass + new message order tests
4. **Review**: Code review score ≥ 9/10
5. **No Regressions**: Tool calling, context clearing, history management all work

## Timeline

1. **Requirements**: ✅ Complete
2. **Implementation**: 20-30 minutes (Jackie)
3. **Testing**: 15-20 minutes (Raoul - update tests + manual verification)
4. **Code Review**: 10-15 minutes (Han-Ron)
5. **Deploy**: 5 minutes

**Total**: ~60-75 minutes

## Notes

This is a subtle but critical bug. The infrastructure was perfect, the prompt was perfect, but the MESSAGE ORDER was wrong. This is why the user still experienced the bug after our "fix".

Hans identified this as the #2 most likely cause (25% probability), but it's actually the definitive root cause now that we've examined the code at lines 1015-1022.

---

**Ready for Jackie to implement the message reordering fix.**
