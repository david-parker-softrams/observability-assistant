# LogAI Agent Self-Direction Investigation
## "That didn't produce any output, let me try something similar" - Bug Analysis

**Investigation Date**: February 11, 2026  
**Investigator**: Hans (Code Librarian)  
**Status**: ✅ Complete - Root Cause Identified

---

## Executive Summary

The bug where the agent says "That didn't produce any output, let me try something similar" but **never actually executes** the suggested action has been identified. This is a **system prompt and conversation flow design issue**, not a technical bug in the code.

### Root Causes (Ranked by Severity)

1. **🔴 CRITICAL**: System prompt does not instruct the agent to **automatically retry** when tools produce empty output
2. **🔴 CRITICAL**: Conversation loop terminates after agent produces text, regardless of whether it was just a statement of intent
3. **🟠 HIGH**: No feedback mechanism when tools return empty results (e.g., `count: 0`)
4. **🟡 MEDIUM**: System prompt encourages the agent to be concise, which may discourage it from acting on its own intent
5. **🟡 MEDIUM**: The agent is trained to respond to the user, not to self-direct actions

---

## Key Files Involved

### 1. **Agent Behavior & Conversation Management**
- **File**: `/src/logai/core/orchestrator.py`
- **Lines**: 31-64 (System Prompt), 143-222 (Conversation Loop)
- **Responsibility**: Controls the core conversation flow and tool execution loop

### 2. **LLM Providers (Tool Response Handling)**
- **Files**:
  - `/src/logai/providers/llm/github_copilot_provider.py` (lines 228-514)
  - `/src/logai/providers/llm/litellm_provider.py` (lines 139-225)
- **Responsibility**: Parse tool calls and return responses to the orchestrator

### 3. **Tool Execution**
- **File**: `/src/logai/core/tools/registry.py`
- **File**: `/src/logai/core/tools/cloudwatch_tools.py` (lines 210-520)
- **Responsibility**: Execute tools and return results (empty or not)

### 4. **UI/Chat Interface**
- **File**: `/src/logai/ui/screens/chat.py` (lines 139-206)
- **Responsibility**: Display agent responses and handle streaming

---

## Current System Prompt Analysis

### Current Prompt (lines 32-64 in orchestrator.py)

```python
SYSTEM_PROMPT = """You are an expert observability assistant helping DevOps engineers and SREs analyze logs and troubleshoot issues.

## Your Capabilities
You have access to tools to fetch and analyze logs from AWS CloudWatch...

## Guidelines

### Tool Usage
1. Always start by understanding what log groups are available if the user doesn't specify
2. Use appropriate time ranges - start narrow and expand if needed
3. Use filter patterns to reduce data volume when searching for specific issues
4. Fetch logs before attempting analysis

### Response Style
1. Be concise but thorough
2. Highlight important findings (errors, patterns, anomalies)
3. Provide actionable recommendations when possible
4. Use code blocks for log excerpts
5. Summarize large result sets

### Error Handling
1. If a log group doesn't exist, suggest alternatives
2. If no logs found, suggest adjusting time range or filters
3. Explain any limitations clearly
```

### The Problem with the Current Prompt

❌ **Missing Instructions for Empty Results**
- No guidance on what to do when tools return empty output (0 logs found)
- No instruction to **automatically retry** with different parameters
- No requirement to **execute** alternative actions vs. just mentioning them

❌ **Response-Oriented, Not Action-Oriented**
- Focus is on "providing recommendations" not "taking action"
- Agent is trained to report findings, not self-direct further tool calls
- The phrase "suggest adjusting..." implies human action, not agent action

❌ **No Loop-Back Guidance**
- No instruction for the agent to call tools again if the first attempt yielded no data
- No indication that multiple tool calls in sequence are encouraged for empty results
- The "Tool Usage" section assumes successful first-time data retrieval

---

## Conversation Flow Analysis

### How It Currently Works

```
┌─────────────────────────────────────────────────────────────────┐
│ USER: "Show me errors from the API service in the last hour"    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ LLM Response │
                    │ (with tools) │
                    └──────┬──────┘
                           │
                    ┌──────▼──────────────────────────────┐
                    │ Tool Call:                           │
                    │ fetch_logs(                          │
                    │   log_group="/aws/api-service",     │
                    │   start_time="1h ago",              │
                    │   filter_pattern="ERROR"            │
                    │ )                                    │
                    └──────┬──────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ Tool Result: │
                    │ count: 0     │ ◄─── EMPTY RESULT!
                    │ events: []   │
                    └──────┬──────┘
                           │
     ┌─────────────────────▼────────────────────────┐
     │ LLM processes result and generates response: │
     │ "No errors found. Let me try a broader       │
     │  search across all services..."              │ ◄─ Agent states intent
     │                                              │    but doesn't act!
     └─────────────────────┬────────────────────────┘
                           │
                    ┌──────▼──────────────┐
                    │ Response has NO     │
                    │ tool_calls (just    │
                    │ text content)       │
                    │                     │
                    │ has_tool_calls() =  │
                    │ FALSE ❌            │
                    └──────┬──────────────┘
                           │
                    ┌──────▼──────────────────────────┐
                    │ Orchestrator terminates loop     │
                    │ (line 202-207 in orchestrator)   │
                    │                                  │
                    │ Returns response to user ✗       │
                    └──────────────────────────────────┘
                           │
                    ┌──────▼──────────────┐
                    │ USER SEES:          │
                    │ "No errors found.   │
                    │  Let me try a       │
                    │  broader search..." │
                    │                     │
                    │ But no action taken!│
                    └─────────────────────┘
```

### The Critical Code Section

**File**: `/src/logai/core/orchestrator.py`, lines 200-212

```python
# No tool calls - we have the final response
if response.content:
    self.conversation_history.append(
        {"role": "assistant", "content": response.content}
    )
    return response.content  # ◄─── EXITS HERE
else:
    # Empty response, shouldn't happen but handle gracefully
    error_msg = "Received empty response from LLM"
    self.conversation_history.append({"role": "assistant", "content": error_msg})
    return error_msg
```

**The Problem**: 
- When the LLM returns a response with **text but NO tool calls**, the loop exits
- The orchestrator **never checks** if the agent's text indicates it's about to retry
- The agent is not instructed to **include a tool call** if it intends to take action

---

## Tool Execution and Empty Results

### What Happens When Tools Return 0 Results

**Example Tool Response** (from `fetch_logs` in cloudwatch_tools.py, lines 269-284):

```python
result = {
    "success": True,
    "log_group": log_group,
    "events": [],           # ◄─── EMPTY!
    "count": 0,             # ◄─── ZERO RESULTS
    "time_range": {...},
    "filter_pattern": filter_pattern,
    "sanitization": {...},
}
```

**What Gets Passed to LLM**:

```json
{
  "tool_call_id": "call_123",
  "content": {
    "success": true,
    "log_group": "/aws/api-service",
    "events": [],
    "count": 0,
    ...
  }
}
```

**Current System Prompt has NO guidance on:**
- ✗ Checking the `count` field in tool results
- ✗ Automatically modifying parameters when `count: 0`
- ✗ Calling tools again with different parameters
- ✗ Setting expectations that empty results require action

---

## Why the Agent Says "Let me try..." But Doesn't Act

### Theory 1: Training on Human Interaction Patterns

The agent is likely trained on data where it responds to users. When it says "Let me try something similar," it's **expecting the user to ask it to proceed**. The system prompt doesn't indicate:

```
❌ The agent should automatically take action on its stated intent
❌ The agent has implicit permission to retry with different parameters
❌ The agent should not wait for user confirmation to execute stated actions
```

### Theory 2: Prompt Encourages Reporting Over Acting

The "Response Style" section emphasizes:
- ✓ Be concise
- ✓ Provide recommendations
- ✓ Explain limitations

But NOT:
- ✗ Automatically retry when data is empty
- ✗ Persist in tool execution until you have meaningful data
- ✗ Use tool calls liberally to gather information before responding

### Theory 3: Ambiguous Intent Recognition

When the agent says: "That didn't produce any output. Let me try something similar..."

The LLM does NOT generate a tool call in the response because:
1. The agent's training includes conditional language ("let me try")
2. The system prompt doesn't require immediate action on stated intent
3. There's no explicit instruction: "If you state an intention to try a tool, you MUST include a tool call"

---

## Detailed Code Flow

### Orchestrator Conversation Loop (lines 164-222)

```python
async def _chat_complete(self, user_message: str) -> str:
    # Add user message to history
    self.conversation_history.append({"role": "user", "content": user_message})
    
    # Get available tools
    tools = self.tool_registry.to_function_definitions()
    
    # Execute conversation loop with tool calling
    iteration = 0
    while iteration < self.MAX_TOOL_ITERATIONS:  # ◄─── MAX = 10
        iteration += 1
        
        try:
            # Get LLM response
            response = await self.llm_provider.chat(
                messages=messages, tools=tools, stream=False
            )
            
            # Check if LLM wants to use tools
            if response.has_tool_calls():  # ◄─── ONLY if tool calls present
                # Execute tool calls
                tool_results = await self._execute_tool_calls(response.tool_calls)
                
                # Add assistant message with tool calls to history
                self.conversation_history.append(assistant_message)
                
                # Add tool results to conversation
                for tool_result in tool_results:
                    self.conversation_history.append(tool_message)
                
                # Continue loop - LLM will process tool results
                continue  # ◄─── LOOP CONTINUES
            
            # No tool calls - we have the final response
            if response.content:
                self.conversation_history.append(
                    {"role": "assistant", "content": response.content}
                )
                return response.content  # ◄─── LOOP EXITS HERE ❌
            else:
                return "Received empty response from LLM"
        
        except Exception as e:
            raise OrchestratorError(...)
    
    # Hit max iterations
    return f"Maximum tool iterations ({self.MAX_TOOL_ITERATIONS}) exceeded."
```

**Key Insight**: 
- The loop only continues if `response.has_tool_calls()` is TRUE
- When the agent produces text without tool calls, the loop exits **immediately**
- There is NO check to see if the text contains language like "let me try" or "let me attempt"

---

## System Prompt Recommendations

### What the Prompt Currently Says (Tool Usage)

```
1. Always start by understanding what log groups are available if the user doesn't specify
2. Use appropriate time ranges - start narrow and expand if needed
3. Use filter patterns to reduce data volume when searching for specific issues
4. Fetch logs before attempting analysis
```

### What's Missing

```
❌ "If a tool call returns zero results (count: 0), you MUST NOT stop"
❌ "If no logs are found, immediately try adjusting time range or filters"
❌ "Do not mention intentions ('Let me try...') - EXECUTE the tool call instead"
❌ "Continue attempting to fetch data until you have results or have tried at least 3 different approaches"
❌ "When returning results to the user, include all the tools you used and their parameters"
```

---

## Patterns That Cause the Agent to Stop

### Pattern 1: Statement of Intent Without Tool Call

```
Agent: "That didn't produce any output. Let me try a broader time range..."
Result: ❌ No tool call generated
Reason: Agent is trained to respond; statement of intent without action
```

### Pattern 2: Empty Result Processing

```
Tool returns: {"count": 0, "events": []}
Agent thinks: "This means my search was too specific"
Agent says: "No results found. Let me try..."
Result: ❌ Agent produces text without tool call
Reason: No prompt instruction to retry automatically
```

### Pattern 3: Polite/Cautious Language

```
Agent: "Perhaps I should try searching with a different filter..."
Result: ❌ No tool call
Reason: Polite conditional language not interpreted as action directive
```

---

## Real-World Scenario Breakdown

### User Request
```
"Show me all the database connection errors in the last 2 hours"
```

### Agent Execution Flow

1. **First Tool Call**:
   - `fetch_logs(log_group="/aws/rds", start_time="2h ago", filter_pattern="connection.*error")`
   - Result: `count: 0` (no logs found)

2. **Agent Response** (without system prompt guidance):
   - Generates: "No connection errors found in the last 2 hours. Let me try searching with a broader filter..."
   - **Has tool_calls**: NO ❌
   - **Orchestrator action**: Return response to user

3. **User Sees**:
   ```
   Agent: "No connection errors found in the last 2 hours. 
           Let me try searching with a broader filter..."
   ```
   
4. **Agent Never Executes**:
   - New fetch with broader filter
   - Different time range
   - Alternative log group
   - Any follow-up action

---

## Solution Areas to Fix

### 1. System Prompt Enhancement (Priority: CRITICAL)

**Add explicit handling for empty results**:

```python
SYSTEM_PROMPT = """You are an expert observability assistant...

## Response to Empty Results (NO LOGS FOUND)

IMPORTANT: If a tool returns zero results (count: 0), you must NOT reply to the user yet.
Instead, you MUST immediately attempt again with modified parameters:

1. If the filter was specific, try a broader filter
2. If the time range was narrow, expand it (e.g., 1 hour → 4 hours)
3. If a specific log group had no results, try searching across multiple log groups
4. Try up to 3 different parameter combinations before reporting "no logs found" to user

When executing follow-up tool calls, DO NOT add conversational text first.
Include the tool call in the same response.
"""
```

### 2. Conversation Loop Enhancement (Priority: HIGH)

**Add detection for conditional language**:

```python
# After getting response with NO tool_calls but HAS content:
if not response.has_tool_calls() and response.content:
    # Check if the response contains language indicating intent to retry
    intent_keywords = ["let me try", "let me attempt", "try a different", 
                       "let me search", "let me check", "try again", 
                       "broader", "narrower", "different approach"]
    
    response_lower = response.content.lower()
    if any(keyword in response_lower for keyword in intent_keywords):
        # Agent stated an intention - prompt it to include tool call
        # Add to history and ask for tool call
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        messages.append({
            "role": "user", 
            "content": "Please execute the tools needed for your stated action now."
        })
        # Continue loop to get tool calls
        continue  # ◄─── CRITICAL: Loop continues instead of exiting
```

### 3. Tool Result Analysis (Priority: HIGH)

**After receiving tool results, analyze them**:

```python
async def _should_retry_tool_calls(
    self, 
    tool_results: list[dict[str, Any]]
) -> bool:
    """
    Analyze tool results to determine if retry is needed.
    
    Returns True if any tool returned zero results.
    """
    for result in tool_results:
        result_data = result.get("result", {})
        if isinstance(result_data, dict):
            count = result_data.get("count", 0)
            if count == 0:
                return True
    return False
```

### 4. Explicit Retry Instruction (Priority: HIGH)

**Add to system prompt**:

```
## Handling Empty Tool Results

When a tool returns zero results:
- NEVER reply to the user about the lack of results immediately
- INSTEAD, generate a NEW tool call with modified parameters
- Example: If filter_pattern="ERROR" returns 0 results, 
  try filter_pattern="WARN" or remove the filter entirely
- Keep retrying until you either:
  a) Find results (count > 0), or
  b) Have tried at least 3 different parameter combinations
```

---

## Testing the Bug

### How to Reproduce

1. Start LogAI with GitHub Copilot provider
2. Ask a query that will return 0 logs initially:
   ```
   "Show me warnings from /aws/lambda/non-existent-function in the last 30 minutes"
   ```

3. Expected behavior: Agent retries with different parameters
4. Actual behavior: Agent says it will retry but doesn't

### Current Test Coverage

**File**: `/tests/unit/test_orchestrator.py`

The tests DO NOT cover:
- ❌ Empty tool results (count: 0)
- ❌ Multiple tool calls in sequence
- ❌ Retry behavior after empty results
- ❌ Agent response without tool calls after empty result

---

## Summary of Issues

| Issue | Location | Severity | Impact |
|-------|----------|----------|--------|
| System prompt doesn't mention empty result handling | orchestrator.py:32-64 | CRITICAL | Agent doesn't know to retry |
| Conversation loop exits when agent produces text without tool calls | orchestrator.py:202-207 | CRITICAL | Agent can't self-correct |
| No detection of "intent to retry" language | orchestrator.py:200-212 | HIGH | Agent statements go unexecuted |
| Tool results not analyzed for empty data | orchestrator.py:319-372 | HIGH | No feedback loop for empty results |
| System prompt emphasizes "suggestions" over "actions" | orchestrator.py:32-64 | HIGH | Agent trained to report, not act |

---

## Recommended Fix Priority

### Phase 1 (IMMEDIATE) - System Prompt Fix
**Effort**: 30 minutes | **Impact**: HIGH
- Enhance system prompt with explicit empty-result handling
- Add instruction to keep retrying until results or 3 attempts
- Remove ambiguous "suggest" language, replace with "execute"

### Phase 2 (SHORT-TERM) - Intent Detection
**Effort**: 2 hours | **Impact**: MEDIUM
- Add keyword detection for retry intent
- Automatically prompt for tool calls when intent is detected
- Test with multiple intent patterns

### Phase 3 (MEDIUM-TERM) - Retry Logic
**Effort**: 4 hours | **Impact**: MEDIUM
- Implement automatic parameter variation on empty results
- Track retry attempts to prevent infinite loops
- Add logging for retry decisions

### Phase 4 (OPTIONAL) - Testing
**Effort**: 3 hours | **Impact**: MEDIUM
- Add test cases for empty result handling
- Test multi-attempt scenarios
- Integration tests with mock CloudWatch

---

## Files to Modify

1. **`src/logai/core/orchestrator.py`**
   - Update SYSTEM_PROMPT (lines 32-64)
   - Enhance _chat_complete() (lines 143-222)
   - Add intent detection logic
   - Possibly add result analysis method

2. **`tests/unit/test_orchestrator.py`**
   - Add test_empty_result_retry
   - Add test_intent_detection
   - Add test_multiple_tool_calls_sequence

3. **(Optional) `src/logai/core/tools/cloudwatch_tools.py`**
   - Add retry metadata to tool results
   - Suggest parameter variations for empty results

---

## Conclusion

The "That didn't produce any output, let me try something similar" bug is **not a technical bug in tool execution or API communication**. It's a **system design issue** where:

1. The system prompt doesn't instruct the agent to retry on empty results
2. The conversation loop exits when the agent produces text without tool calls
3. The agent is trained to respond/report rather than self-direct actions
4. There's no mechanism to detect and act on the agent's stated intentions

The fix requires **enhancing the system prompt, improving intent detection, and adjusting the conversation loop logic** to support true agent self-direction.

