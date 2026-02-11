# Agent Self-Direction Bug - Quick Reference

## The Problem
Agent says: "That didn't produce any output, let me try something similar"  
But then: **Nothing happens** ❌

## Root Cause (In One Sentence)
The **system prompt doesn't instruct the agent to automatically retry on empty results**, and the **conversation loop exits immediately when the agent produces text without tool calls**.

## Critical Code Locations

### 1. Where the Loop Exits (CRITICAL)
**File**: `src/logai/core/orchestrator.py` lines 200-212

```python
# No tool calls - we have the final response
if response.content:
    return response.content  # ◄─── EXITS HERE, even if agent said "let me try..."
```

### 2. The System Prompt (CRITICAL)
**File**: `src/logai/core/orchestrator.py` lines 32-64

Missing sections:
- ❌ How to handle empty results (count: 0)
- ❌ When to automatically retry
- ❌ How many retries before reporting "no results" to user

### 3. Empty Results From Tools
**File**: `src/logai/core/tools/cloudwatch_tools.py`

Tools return: `{"success": true, "count": 0, "events": []}`  
But prompt gives no guidance on what to do with this.

## Why It Happens

```
Tool returns 0 results
    ↓
LLM sees count: 0
    ↓
LLM thinks "I should try different parameters"
    ↓
LLM outputs: "No results found. Let me try..."
    ↓
LLM does NOT include tool_call in response (no instruction to)
    ↓
Orchestrator sees: text content, NO tool_calls
    ↓
Orchestrator: "Response has no tool calls, return it to user"
    ↓
User sees message but no action ❌
```

## The 3 Critical Problems

| Problem | File | Lines | Fix |
|---------|------|-------|-----|
| Loop exits on text without tool calls | orchestrator.py | 200-212 | Check for intent keywords, continue loop |
| Prompt doesn't mention empty results | orchestrator.py | 32-64 | Add empty-result handling section |
| No retry instruction | orchestrator.py | 32-64 | Add "automatically retry if count: 0" |

## Quick Fixes

### Fix 1: Update System Prompt (5 min)
Add this to SYSTEM_PROMPT:

```python
## CRITICAL: Handling Empty Results

If a tool returns zero results (count: 0):
1. DO NOT reply to the user yet
2. DO NOT mention your intent - EXECUTE the tool call instead
3. Immediately retry with different parameters:
   - Broader filter patterns
   - Longer time ranges
   - Different log groups
4. Continue until results found or 3 attempts made
5. Only then tell user "no logs found"
```

### Fix 2: Detect Intent Keywords (2 hours)
In orchestrator.py `_chat_complete()`:

```python
if not response.has_tool_calls() and response.content:
    keywords = ["let me try", "let me search", "try again", 
                "broader", "try different", "let me attempt"]
    if any(kw in response.content.lower() for kw in keywords):
        # Agent stated intent, ask it to execute
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": "Execute those tools now."})
        continue  # Loop continues instead of returning
```

### Fix 3: Analyze Tool Results (1 hour)
After executing tools, check if any returned 0 results and log it:

```python
def _has_empty_results(self, tool_results: list[dict]) -> bool:
    for result in tool_results:
        if result.get("result", {}).get("count") == 0:
            return True
    return False
```

## Testing

### Reproduce the Bug
```
User: "Show me errors from /aws/api-service in the last 1 hour"
Tool returns: count: 0
Expected: Agent retries with broader filter or time range
Actual: Agent says "Let me try..." but returns message to user
```

### Test After Fix
```
Same query
Tool returns: count: 0
Agent should: Automatically try again with different params
User should see: Agent eventually returns results or "no logs found after 3 attempts"
```

## Files to Change

1. **`src/logai/core/orchestrator.py`** (MAIN FIX)
   - Lines 32-64: Update SYSTEM_PROMPT
   - Lines 200-212: Add intent detection
   - Possibly add helper method for retry logic

2. **`tests/unit/test_orchestrator.py`** (ADD TESTS)
   - Test empty result retry behavior
   - Test intent keyword detection
   - Test multi-call sequences

## Implementation Order

1. **Step 1** (5 min): Update system prompt with empty-result guidance
2. **Step 2** (30 min): Add intent keyword detection to conversation loop  
3. **Step 3** (1 hour): Test with actual queries
4. **Step 4** (2 hours): Add unit tests for new behavior
5. **Step 5** (30 min): Add logging and documentation

## Why Current Tests Don't Catch This

`tests/unit/test_orchestrator.py` tests:
- ✓ Simple responses without tools
- ✓ Tool calls that work
- ✓ Multiple tool calls in one response
- ✗ Empty results (count: 0) - NOT TESTED
- ✗ Agent response without tool calls after empty result - NOT TESTED
- ✗ Retry behavior - NOT TESTED

## Verification Checklist

After implementing fixes:

- [ ] System prompt explicitly mentions empty result handling
- [ ] System prompt instructs automatic retries
- [ ] Conversation loop detects "let me try" and continues
- [ ] Agent automatically retries on count: 0
- [ ] Tests added for empty result scenarios
- [ ] Manual testing confirms behavior
- [ ] Logging shows retry attempts

