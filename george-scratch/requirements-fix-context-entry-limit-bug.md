# Requirements: Fix Context Entry Limit Bug

**Date:** February 19, 2026
**Priority:** HIGH
**Type:** Bug Fix
**Context:** After fixing context visibility, user reports only 10 entries added when selecting 100

## Problem Statement

User reports:
1. Clicked "Load Last 100" button
2. Clicked "Select All" button
3. Clicked "Add to Context" button
4. Asked agent to summarize logs in context
5. Agent's response indicated only 10 logs in context (not 100)

**Expected:** All 100 selected entries should be added to context

**Actual:** Only 10 entries appear to be in context

## Investigation Needed

Need to determine where the 100 entries are being reduced to 10:

### Possible Failure Points

1. **Log Preview Modal (log_preview.py)**
   - Line 742-746: Fetch may not be getting 100 entries
   - Line 862-873: "Select All" may not be selecting all 100
   - Line 893-897: Gathering selected events may be limited

2. **Chat Screen (chat.py)**
   - Line 379: Received entries may already be limited to 10
   - Line 405-442: Formatting may truncate to 10 entries

3. **Orchestrator (orchestrator.py)**
   - Line 446: Context injection may have size limit
   - Line 483-485: Context retrieval may truncate

4. **LLM Provider**
   - Message size limits may truncate context
   - Token limits may cut off context

## Debugging Approach

### Step 1: Add Debug Logging

Add logging at each step to trace the count:

**log_preview.py line 746:**
```python
self._events = await self.datasource.fetch_logs(...)
logger.info(f"[DEBUG] Fetched {len(self._events)} events with limit={self.current_limit}")
```

**log_preview.py line 897:**
```python
selected_events.append(event)
logger.info(f"[DEBUG] Gathering selected events: {len(selected_events)} so far")
```

**log_preview.py line 904:**
```python
self.dismiss(result)
logger.info(f"[DEBUG] Dismissing with {len(selected_events)} selected events")
```

**chat.py line 380:**
```python
entries = result["selected_entries"]
logger.info(f"[DEBUG] Received {len(entries)} entries from log preview")
```

**chat.py line 383:**
```python
context_message = self._format_log_entries_for_context(log_group, entries)
logger.info(f"[DEBUG] Formatted context message length: {len(context_message)} chars")
logger.info(f"[DEBUG] Context message preview: {context_message[:500]}...")
```

**chat.py line 386:**
```python
self.orchestrator.inject_context_update(context_message)
logger.info(f"[DEBUG] Injected context to orchestrator")
```

### Step 2: Check Message Construction

In orchestrator.py, verify the full context message reaches the LLM:

**orchestrator.py line 1022 (after context injection):**
```python
if pending_injection:
    logger.info(f"[DEBUG] Adding context injection: {len(pending_injection)} chars")
    logger.info(f"[DEBUG] Context preview: {pending_injection[:500]}...")
    messages.append({"role": "system", "content": pending_injection})
```

### Step 3: Verify LLM Receives Full Message

Check that the final messages array sent to LLM contains all 100 entries:

**orchestrator.py line 1044 (before LLM call):**
```python
logger.info(f"[DEBUG] Sending {len(messages)} messages to LLM")
for i, msg in enumerate(messages):
    logger.info(f"[DEBUG] Message {i}: role={msg['role']}, length={len(msg['content'])} chars")
```

## Hypothesis

Based on code review, the most likely causes are:

1. **CloudWatch fetch limit** (25% probability)
   - The datasource.fetch_logs() may have a hard limit of 10
   - Check CloudWatchDataSource implementation

2. **UI state issue** (20% probability)
   - self._events may only have 10 entries despite current_limit=100
   - The fetch may not have completed before Select All was clicked

3. **Context message truncation** (15% probability)
   - JSON formatting of 100 entries may exceed some limit
   - Message may be silently truncated

4. **LLM token limit** (10% probability)
   - 100 log entries may exceed context window
   - LLM may only see first 10 due to truncation

5. **Select All bug** (10% probability)
   - Select All may have a hidden limit
   - Not all 100 entry IDs added to self._selected_ids

6. **Agent interpretation** (20% probability)
   - All 100 entries ARE in context
   - Agent is only analyzing/mentioning first 10 in summary

## Requirements

### REQ-1: Add Debug Logging (CRITICAL)

Add comprehensive logging at all points in the data flow to trace where the 100 entries become 10.

**Acceptance Criteria:**
- Logging added at 7+ key points
- Each log shows the count of entries at that point
- Logs include enough context to identify the failure point

### REQ-2: Reproduce and Diagnose (CRITICAL)

Have user reproduce the issue with debug logging enabled and capture logs.

**Acceptance Criteria:**
- User follows exact same steps (Load 100, Select All, Add to Context)
- Debug logs captured showing entry counts at each step
- Identify exact point where 100 becomes 10

### REQ-3: Implement Fix (CRITICAL)

Based on diagnosis, implement appropriate fix:

**If CloudWatch limit:** Update datasource to handle pagination or increase limit
**If UI state:** Fix timing issue or state management
**If truncation:** Implement chunking or increase limits
**If LLM limit:** Add smart truncation with user warning
**If Select All:** Fix selection logic
**If agent interpretation:** Improve system prompt or add explicit count

### REQ-4: Verify Fix

Test with same scenario and verify all 100 entries reach the agent.

**Acceptance Criteria:**
- User can load 100 entries
- User can select all 100 entries
- All 100 entries appear in agent context
- Agent acknowledges seeing all 100 entries

## Success Criteria

1. **Diagnosis:** Identify exact failure point in data flow
2. **Fix:** Implement solution that addresses root cause
3. **Verification:** User confirms all 100 entries reach agent
4. **Testing:** Automated test added to prevent regression
5. **Documentation:** Update docs if user-facing behavior changes

## Timeline

1. **Add Debug Logging:** 15-20 minutes (Jackie)
2. **User Reproduction:** 5 minutes (User with debug build)
3. **Diagnosis:** 10-15 minutes (Hans analyzing logs)
4. **Implementation:** 20-30 minutes (Jackie, depends on root cause)
5. **Testing:** 15 minutes (Raoul)
6. **Verification:** 5 minutes (User)

**Total:** ~70-90 minutes

## Notes

- This is likely a simple bug with a clear fix once diagnosed
- Debug logging is key to finding the exact failure point
- The code flow looks correct on inspection, so the bug is subtle
- Most likely issue is either CloudWatch fetch limit or UI timing

---

**Next Steps:**
1. Jackie adds debug logging
2. Build and deploy to user
3. User reproduces issue
4. Analyze debug logs to find failure point
5. Implement fix based on diagnosis
