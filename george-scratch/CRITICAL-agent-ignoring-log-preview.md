# CRITICAL BUG: Agent Not Seeing Logs from Log Preview

**Date:** February 20, 2026
**Reporter:** User (David)
**Severity:** CRITICAL - Core Feature Broken
**Status:** INVESTIGATING

---

## Problem Description

**User Report:** "For whatever reason the agent seems to be not seeing or ignoring logs provided from the log preview function now."

**Impact:**
- Core feature broken - log preview context not reaching agent
- Agent cannot analyze user-selected logs
- Main workflow blocked for investigating specific logs
- This is a primary use case for the application

---

## Expected Behavior

When user uses "Add to Context" from log preview:
1. ✅ User selects log entries in log preview
2. ✅ User clicks "Add to Context"
3. ✅ Logs are added to context
4. ✅ Agent receives logs in next message
5. ✅ Agent references and analyzes the specific logs

---

## Actual Behavior

❌ Agent does not see or ignores the logs from log preview
❌ Agent may not be receiving them at all
❌ Or agent is receiving them but not recognizing them

---

## Critical Questions

### Question 1: When did this break?
- **Was it working before?** Need to establish baseline
- **Did our TextArea changes affect it?** We reverted those changes
- **Did something else change?** Check recent commits
- **Is this a regression or existing issue?**

### Question 2: Where is the break?
- **Context injection:** Are logs being added to context at all?
- **Context delivery:** Are logs being sent to the agent?
- **Agent recognition:** Is the agent ignoring what it receives?
- **Message ordering:** Are logs arriving before or after user message?

### Question 3: What changed recently?
Check commits since last known working state:
- `5650d73` - Rollback to Static (today)
- `4b9b7bf` - TextArea implementation (reverted)
- `6634e09` - Multi-select log groups
- `6170d18` - Context Viewer enhancements
- `7d7f8c4` - Status footer fix

---

## Investigation Priorities

### Priority 1: Verify Current Behavior (5 min)
1. Check if "Add to Context" button works
2. Check if context appears in context viewer
3. Check if context count updates in status bar
4. Look at actual messages sent to agent

### Priority 2: Check Recent Changes (10 min)
1. Did rollback affect context injection?
2. Did Context Viewer changes affect log preview?
3. Any code paths that changed related to context?

### Priority 3: Trace Context Flow (15 min)
1. Log preview → Add to Context button
2. Context added to orchestrator
3. Context injected into message flow
4. Message sent to agent with context

### Priority 4: Check Agent Instructions (5 min)
1. Are logs formatted correctly for agent?
2. Is agent being told to use the logs?
3. Is there conflicting guidance?

---

## Possible Root Causes

### Hypothesis 1: Context Not Being Added
- Add to Context button broken
- Context storage not working
- Bug in log preview integration

### Hypothesis 2: Context Not Being Delivered
- Message ordering issue
- Context injection not happening
- Wrong message format

### Hypothesis 3: Agent Ignoring Context
- Agent instructions changed
- Prompt formatting issue
- Agent not recognizing log format

### Hypothesis 4: Regression from Recent Changes
- Context Viewer changes broke something
- Multi-select changes interfered
- Rollback had side effects

---

## Files to Investigate

### Log Preview Related
- `src/logai/ui/screens/log_preview.py` - Add to Context button
- `src/logai/ui/widgets/log_preview_modal.py` - Modal that shows logs

### Context Management
- `src/logai/orchestration/orchestrator.py` - Context injection
- `src/logai/ui/screens/chat.py` - Message processing
- Context viewer files (recent changes)

### Recent Commits
Check all files modified in recent commits for context-related code.

---

## Testing Steps

### Manual Test
1. Open log preview for a log group
2. Select some log entries
3. Click "Add to Context"
4. Verify context count increases
5. Ask agent: "What logs do you see in context?"
6. Check if agent references the logs

### Expected Results
- Agent should list the logs
- Agent should reference timestamps
- Agent should analyze the content

### Actual Results
- Document what actually happens
- Capture any error messages
- Note agent's response

---

## User Impact

**Severity:** CRITICAL
- Breaks primary workflow
- Users cannot analyze specific logs
- Core feature non-functional
- Affects all users who use log preview

**Urgency:** CRITICAL
- Must be fixed ASAP
- Blocks main use case
- User is experiencing now

---

## Investigation Tasks

1. **Hans:** Full investigation (30-45 min)
   - Trace context flow end-to-end
   - Check recent changes for regressions
   - Identify exact break point
   - Find root cause
   - Propose fix

2. **Decision Point:**
   - If recent regression: Identify commit and fix
   - If existing bug: Understand why and fix
   - If configuration issue: Adjust and test

3. **Jackie:** Implement fix

4. **Raoul:** Test thoroughly

---

## Related Features

Check if these are also affected:
- Multi-select log groups context
- Manual "Add to Context" from sidebar
- Context viewer display
- Agent memory/conversation history

---

## Next Steps

1. **Immediate:** Hans investigates (starting now)
2. **After investigation:**
   - If quick fix: Implement and test
   - If complex: Design solution
   - If regression: May need to revert something else

---

**Status:** INVESTIGATING
**Priority:** CRITICAL
**Assigned:** Hans

**User is blocked. Need fast resolution.**
