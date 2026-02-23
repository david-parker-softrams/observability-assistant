# CRITICAL UX BUG: "Add to Context" Feature Broken - Complete Investigation

**Date:** February 19, 2026
**Severity:** CRITICAL
**Root Cause:** Missing system prompt guidance for user-provided logs
**Status:** Identified & Fully Documented

---

## EXECUTIVE SUMMARY

The "Add to Context" button works perfectly at collecting and transmitting logs to the agent, but **the agent ignores them** because the system prompt never teaches the agent to expect or prioritize context logs.

### The Problem
- User adds logs via "Add to Context" ✓ Works
- User sees confirmation: "Added N entries to context" ✓ Accurate
- User asks: "Analyze these logs"
- Agent responds: "I need to search for logs. Let me list available log groups..."
- User confused: "But I just gave you logs!" ✗ BROKEN UX

### The Paradox
**The data flow is 100% working.** Logs reach the agent perfectly formatted. The only problem is the agent's instructions (system prompt) don't tell it to check for or prioritize user-provided logs.

---

## COMPLETE DATA FLOW (All Steps Work)

### Step 1: UI Captures Selection ✓
**File:** `src/logai/ui/screens/log_preview.py:889-904`
- LogPreviewScreen.on_add_to_context()
- Collects selected entries from checkboxes
- Creates result dict with log_group_name and selected_entries

### Step 2: Chat Screen Injects to Orchestrator ✓
**File:** `src/logai/ui/screens/chat.py:351-360, 370-442`
- ChatScreen receives the result from push_screen
- Calls _inject_log_entries_to_context(result)
- Formats entries using _format_log_entries_for_context()
- Calls orchestrator.inject_context_update(context_message)

### Step 3: Orchestrator Stores Context ✓
**File:** `src/logai/core/orchestrator.py:423-433`
```python
def inject_context_update(self, context_message: str) -> None:
    self._pending_context_injection = context_message  # Stored!
```

### Step 4: Orchestrator Retrieves Context on Next Message ✓
**File:** `src/logai/core/orchestrator.py:1007-1009`
```python
pending_injection = self._get_pending_context_injection()
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})
```

### Step 5: Context Appended to Messages Array ✓
**File:** `src/logai/core/orchestrator.py:1030-1032`
```python
llm_result = await self.llm_provider.chat(
    messages=messages,  # ← Includes context logs!
    tools=tools,
    stream=False
)
```

### Step 6: LLM Receives All Messages Including Context ✓
Final message array sent to LLM:
```json
[
  {"role": "system", "content": "You are an expert observability assistant..."},
  {"role": "user", "content": "Look at the logs in context and categorize them"},
  {"role": "system", "content": "USER-SELECTED LOG ENTRIES for analysis:\nLog Group: my-app-logs\nEntry Count: 3\n[JSON entries...]"}
]
```

✓✓✓ **LOGS SUCCESSFULLY DELIVERED TO LLM** ✓✓✓

### Step 7: Agent Ignores Logs ✗
Agent reads system prompt which says:
- "Always start by understanding what log groups are available"
- "Fetch logs before attempting analysis"

Agent thinks: "User wants logs analyzed, I should fetch them" (ignoring that they're already in context)

**Result:** Agent responds with "Let me list available log groups" instead of analyzing provided logs.

---

## ROOT CAUSE ANALYSIS

### PRIMARY CAUSE: System Prompt Missing Context Guidance
**File:** `src/logai/core/orchestrator.py:220-304`

**Current system prompt sections:**
1. ✓ "Your Capabilities" - tells about tools
2. ✓ "Guidelines" - tells about tool usage
3. ✓ "Error Handling" - tells about error scenarios
4. ✓ "Self-Direction & Persistence" - tells about retries
5. ✓ "Cached Result Handling" - tells about cached logs
6. ✓ "Context" - shows current time
7. **✗ MISSING: "User-Provided Log Entries"** - tells about context logs!

**What's missing from system prompt:**
```
## User-Provided Log Entries

When logs are provided in your context:
1. Look for sections marked "USER-SELECTED LOG ENTRIES for analysis"
2. PRIORITIZE: Analyze provided logs FIRST before using tools
3. Only use tools if user asks for additional logs
4. Do NOT ignore provided logs and ask to search
```

### SECONDARY CAUSE: Message Format is Too Passive
**File:** `src/logai/ui/screens/chat.py:431-442`

Current message:
```
USER-SELECTED LOG ENTRIES for analysis:
...
Please analyze these logs and provide insights based on the user's next question.
```

This is polite but too passive. Agent reads it as a suggestion, not a directive.

### TERTIARY CAUSE: Agent's Tool-First Philosophy
The system prompt emphasizes tool usage over context:
- "Always start by understanding what log groups are available"
- "Fetch logs before attempting analysis"

But says nothing about:
- "If logs are provided in context, analyze them first"
- "Skip tool fetching if appropriate logs are available"

---

## EVIDENCE: Data Flow is Working

### Evidence 1: Context Injection is Called
```python
# orchestrator.py:433
def inject_context_update(self, context_message: str) -> None:
    self._pending_context_injection = context_message
```
✓ Context stored successfully

### Evidence 2: Retrieval Works
```python
# orchestrator.py:470-473
if self._pending_context_injection:
    injection = self._pending_context_injection
    self._pending_context_injection = None  # Clear after use
    injections.append(injection)
```
✓ Context retrieved and cleared properly

### Evidence 3: Appended to Messages
```python
# orchestrator.py:1008-1009
if pending_injection:
    messages.append({"role": "system", "content": pending_injection})
```
✓ Context added to message array

### Evidence 4: Sent to LLM
```python
# orchestrator.py:1030-1032
llm_result = await self.llm_provider.chat(
    messages=messages,
    tools=tools,
    stream=False
)
```
✓ Messages including context sent to LLM

**CONCLUSION:** All data flow works perfectly. Agent receives the logs but doesn't know what to do with them.

---

## RECOMMENDED FIXES

### FIX 1: Add Context Guidance Section to System Prompt (CRITICAL)

**Priority:** MUST DO FIRST
**Effort:** 5-10 minutes
**Impact:** HIGH - Fixes core issue

**File:** `src/logai/core/orchestrator.py`
**Location:** After line 300 (before "## Context" section)

**Add this section:**
```python
## User-Provided Log Entries

Users can provide log entries directly through the "Add to Context" feature in the log preview pane.
When you receive entries in your context:

1. **RECOGNITION**: Look for sections marked "USER-SELECTED LOG ENTRIES for analysis"
2. **PRIORITY**: ALWAYS analyze provided logs FIRST before making tool calls
3. **ANALYSIS**: Provide detailed insights, categorization, or answers based on the provided logs
4. **TOOL USAGE**: Only use tools if:
   - User explicitly asks for additional logs beyond what was provided
   - You need to correlate with different log groups
   - The provided logs are insufficient to answer the question

**CRITICAL**: Do NOT ignore provided logs and ask to search for log groups.
If logs appear in "USER-SELECTED LOG ENTRIES", analyze them first.
```

### FIX 2: Make Context Message More Commanding (HIGH)

**Priority:** SHOULD DO SOON
**Effort:** 5 minutes
**Impact:** MEDIUM - Reinforces Fix 1

**File:** `src/logai/ui/screens/chat.py`
**Location:** Lines 431-442 (_format_log_entries_for_context method)

**Current:**
```python
return f"""USER-SELECTED LOG ENTRIES for analysis:

Log Group: {log_group}
Entry Count: {len(entries)}

The user has specifically selected these log entries for your analysis:

```json
{json.dumps(formatted_entries, indent=2)}
```

Please analyze these logs and provide insights based on the user's next question."""
```

**New:**
```python
return f"""⚠️  CRITICAL: USER-PROVIDED LOG ENTRIES - ANALYZE IMMEDIATELY ⚠️

Log Group: {log_group}
Entry Count: {len(entries)}

THE USER HAS DIRECTLY PROVIDED THESE LOG ENTRIES FOR ANALYSIS.

YOU MUST analyze these logs and respond to the user's question based on them:

```json
{json.dumps(formatted_entries, indent=2)}
```

**MANDATORY DIRECTIVES:**
- Analyze and respond about these specific logs
- Do NOT ask for a log group to search
- Do NOT fetch different logs unless specifically requested by user
- Provide insights directly from these provided entries"""
```

### FIX 3: Add Context-First Detection (OPTIONAL/MEDIUM)

**Priority:** NICE TO HAVE
**Effort:** 15-20 minutes
**Impact:** LOW-MEDIUM - Extra safety net

Could add pre-processing in orchestrator to detect when:
- Context logs were just provided
- User is asking for analysis (not fetching)
- Tools should be skipped

Example check:
```python
analysis_keywords = ["analyze", "categorize", "explain", "look at", "read", "review"]
if has_context_logs and any(kw in user_message.lower() for kw in analysis_keywords):
    # Skip tool suggestion, go straight to context analysis
```

### FIX 4: Update Tool Descriptions (OPTIONAL/LOW)

**Priority:** NICE TO HAVE
**Effort:** 10 minutes
**Impact:** LOW - Clarification only

Add to each tool's description in registry:
```
"Note: Use this tool only if user-provided logs in context are insufficient.
Always analyze provided logs first before fetching."
```

---

## IMPLEMENTATION PLAN

1. **Fix 1 (CRITICAL):** Add system prompt section - 5 min
2. **Fix 2 (HIGH):** Update context message format - 5 min
3. **Testing:** Verify agent analyzes context logs - 10 min
4. **Fix 3 (OPTIONAL):** Add detection logic - 15 min
5. **Fix 4 (OPTIONAL):** Update tool descriptions - 10 min

**Total Critical Path:** ~20 minutes for Fixes 1-2 + testing

---

## VERIFICATION STEPS

After implementing Fix 1 and Fix 2, test:

1. **Add logs to context**
   - Open log preview
   - Select some entries
   - Click "Add to Context"
   - See: "Added N entries from LOG_GROUP to context"

2. **Ask agent to analyze**
   - Type: "Look at the logs in context and categorize them"
   - Expected: Agent analyzes provided logs immediately
   - Should NOT see: "Let me search for logs..." or "I need a log group..."

3. **Ask for different logs**
   - After analyzing context logs, ask for a different log group
   - Expected: Agent uses tools to fetch from different group
   - Should work: Tools only used when context insufficient

---

## SUMMARY

| Component | Status | Why | Fix |
|-----------|--------|-----|-----|
| UI Button | ✓ Works | Code correct | None |
| Formatting | ✓ Works | Code correct | Enhance message text |
| Storage | ✓ Works | Code correct | None |
| Retrieval | ✓ Works | Code correct | None |
| LLM Delivery | ✓ Works | Code correct | None |
| Agent Recognition | ✗ BROKEN | Missing prompt section | Add prompt section |
| Agent Prioritization | ✗ BROKEN | No context-first instruction | Add prompt section |

**Root Issue:** 99% system prompt issue, 1% UX messaging
**Solution:** Add ~20 lines to system prompt + improve message tone
**Effort:** 20 minutes
**Impact:** Restores full "Add to Context" UX flow

---

## NEXT ACTIONS FOR GEORGE

1. Review this analysis for accuracy
2. Approve fixes (should be straightforward - just adding documentation to system prompt)
3. Implement Fix 1 and Fix 2
4. Test the scenario from problem statement
5. Deploy
6. Monitor user feedback

The bug is simple to understand and the fix is straightforward. The infrastructure is working perfectly - the agent just needs to be told what to do with the information it's receiving.
