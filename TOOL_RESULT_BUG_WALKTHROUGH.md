# Code Walkthrough: The Tool Result Visibility Bug

This document provides a step-by-step code walkthrough showing exactly where the bug occurs.

## Setup: User asks to analyze logs

```
User: "Find errors in the /aws/lambda/my-function logs"
```

## Iteration 1: Agent calls tool

### Step 1: Initial message building (lines 1010-1050)

```python
# orchestrator.py lines 1010-1050

# Add user message to history
self.conversation_history.append({"role": "user", "content": user_message})

# Build system prompt with context injection BEFORE the loop
system_prompt = self._get_system_prompt()  # Line 1018
pending_injection = self._get_pending_context_injection()  # Line 1019

# If there's user-provided context, merge it
if pending_injection:
    system_prompt = system_prompt + "\n\n---\n\n" + pending_injection  # Line 1027

# Create messages array BEFORE the tool loop
messages = [{"role": "system", "content": system_prompt}]  # Line 1030
if self.conversation_history:
    messages.extend(self.conversation_history)  # Line 1034

# Result:
# messages = [
#   {"role": "system", "content": "System prompt (large)"},
#   {"role": "user", "content": "Find errors in logs"}
# ]
```

### Step 2: First LLM call (line 1063-1071)

```python
# orchestrator.py lines 1063-1071

llm_result = await self.llm_provider.chat(
    messages=messages, tools=tools, stream=False
)

response = llm_result

# Response has:
# - content: "I'll fetch the logs for you"
# - tool_calls: [{"id": "call_1", "function": {"name": "fetch_logs", "arguments": "..."}}]
# - finish_reason: "tool_calls"
```

### Step 3: Tool execution (lines 1076-1107)

```python
# orchestrator.py lines 1076-1107

# Execute the tool
tool_results = await self._execute_tool_calls(response.tool_calls)

# Inside _execute_tool_calls:
# Line 1652: result = await self.tool_registry.execute("fetch_logs", ...)
#
# fetch_logs returns:
# {
#   "success": True,
#   "events": [
#     "2026-02-23T10:15:22Z ERROR: Database connection timeout",
#     "2026-02-23T10:15:23Z ERROR: Retry attempt 1/3",
#     ... (many more events)
#   ],
#   "count": 500
# }

# Line 1662: processed_result = await self._process_tool_result(tool_result, "fetch_logs")

# >>> THIS IS WHERE THE BUG STARTS <<<
```

## THE BUG LOCATION: _process_tool_result()

### Step 4: Result caching check (lines 528-677)

```python
# orchestrator.py lines 528-677

async def _process_tool_result(self, tool_result, tool_name):
    result_data = tool_result["result"]

    # Skip processing if caching disabled
    if not self.settings.enable_result_caching:
        return tool_result  # ← Would work fine if we returned here

    # Check if result should be cached
    should_cache, token_count = self.budget_tracker.should_cache_result(
        result_data,
        threshold=self.settings.cache_large_results_threshold,
    )

    # Line 565-566: Check max_result_tokens limit
    max_allowed = self.settings.max_result_tokens  # typically 10000
    force_cache_due_to_size = token_count > max_allowed

    if force_cache_due_to_size:
        logger.info(f"Result exceeds max_result_tokens: {token_count} > {max_allowed}")
        should_cache = True  # ← FORCE CACHING FOR LARGE RESULTS

    if should_cache:  # ← 500 log events = ~8000 tokens, likely > 10000
        try:
            # Line 596-600: Cache the result
            summary = await self.result_cache.cache_result(
                tool_name=tool_name,
                query_params=query_params,
                result=result_data,
            )

            # >>> THE PROBLEM LINE 605-610 <<<
            if summary.total_events > 0:
                self._pending_cache_guidance = {
                    "cache_id": summary.cache_id,
                    "tool_name": tool_name,
                    "total_events": summary.total_events,  # 500 events cached
                }

            # Line 619: Return SUMMARY instead of full result
            modified_result = summary.to_context_dict()
            #
            # This returns something like:
            # {
            #   "success": True,
            #   "cache_id": "cache_12345",
            #   "total_events": 500,  # Total cached
            #   "sample_events": ["ERROR: ...", "ERROR: ..."],  # Only 2-5 samples!
            #   "note": "Full result cached. Use fetch_cached_result_chunk to retrieve events."
            # }

            return {
                "tool_call_id": tool_call_id,
                "result": modified_result,  # ← RETURNS SUMMARY, NOT FULL RESULT
            }
        except Exception as e:
            # Fall through if caching fails
            self.budget_tracker.add_result_tokens(token_count)
            return tool_result  # Fall back to full result
```

So at this point:
- Tool returned 500 full log events
- But `_process_tool_result()` cached it and returned a summary with only 2-5 sample events
- `_pending_cache_guidance` was set with instructions to fetch chunks

### Step 5: Tool result added to messages (lines 1100-1107)

```python
# orchestrator.py lines 1100-1107

# Add assistant message with tool calls
assistant_message = {
    "role": "assistant",
    "content": "I'll fetch the logs for you",
    "tool_calls": response.tool_calls,
}
self.conversation_history.append(assistant_message)
messages.append(assistant_message)

# Add tool results
for tool_result in tool_results:  # tool_results contains the SUMMARIZED result
    tool_message = {
        "role": "tool",
        "tool_call_id": tool_result["tool_call_id"],
        "content": json.dumps(tool_result["result"]),  # ← Contains SUMMARY!
    }
    self.conversation_history.append(tool_message)
    messages.append(tool_message)

# Now messages contains:
# [
#   {"role": "system", "content": "System prompt"},
#   {"role": "user", "content": "Find errors in logs"},
#   {"role": "assistant", "content": "I'll fetch the logs", "tool_calls": [...]},
#   {"role": "tool", "tool_call_id": "call_1", "content": '{"cache_id": "...", "sample_events": [...]...}'} ← SUMMARY
# ]
```

## Iteration 2: The Agent's Confused Response

### Step 6: Context injection on second iteration (lines 1016-1034)

Wait! The loop goes back to the top. Let's look at what happens:

```python
# orchestrator.py lines 1016-1034

# This happens AGAIN at the start of each iteration? NO!
# Actually, this code is OUTSIDE the while loop (lines 1016-1034)
# so it only runs ONCE before the loop starts.

# BUT we need to trace what happens on the SECOND LLM call...
```

Let me check the second iteration more carefully:

```python
# orchestrator.py lines 1058-1063 (second iteration)

while iteration < max_iterations:
    iteration += 1  # iteration = 2

    try:
        # Line 1063: Call LLM again
        llm_result = await self.llm_provider.chat(
            messages=messages,  # Same messages array, now with tool result
            tools=tools,
            stream=False
        )
```

WAIT! On the second call, `_get_pending_context_injection()` is called AGAIN! Let me check where:

Actually, NO. The system prompt is only built once before the loop. Let me trace what actually happens with the `_pending_cache_guidance`:

### Step 7: Cache guidance gets merged in (SOMEWHERE)

Looking at the code... wait, I need to find where `_pending_cache_guidance` gets used.

It's set at line 606, but where is it used?

Let me search...

Looking at `_get_pending_context_injection()` (lines 449-493):

```python
# orchestrator.py lines 449-493

def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    injections = []

    # Include cache guidance if available (lines 454-481)
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None  # Clear after use
        cache_guidance = f"""SYSTEM INSTRUCTION: The previous tool call returned a large result...

You MUST now fetch chunks to show the user actual log events:

STEP 1: Fetch first chunk
Call fetch_cached_result_chunk with these parameters:
- cache_id: {guidance["cache_id"]}
- offset: 0
- limit: {self.settings.initial_chunk_size}
...
"""
        injections.append(cache_guidance)

    # Include user-selected log entries if available
    if self._pending_context_injection:
        injection = self._pending_context_injection
        self._pending_context_injection = None
        injections.append(injection)

    if injections:
        return "\n\n---\n\n".join(injections)
    return None
```

So `_get_pending_cache_guidance` becomes part of the injection!

But wait... this is only called ONCE before the loop (line 1019). So how does it affect the second LLM call?

OH! I see it now. Let me trace more carefully:

1. **First LLM call** (line 1063): Messages = [system (with merged context injection from line 1019), user, ...]
2. **Tool execution and caching** (lines 1076-1107): `_pending_cache_guidance` is SET
3. **Back to loop start** (line 1058): `iteration += 1`, go to top of while loop
4. **Line 1063 again**: Call LLM AGAIN

But the system prompt is built OUTSIDE the loop, so the second LLM call doesn't get new cache guidance merged into system prompt!

Hmm, this means my theory was partially wrong. Let me reconsider...

Actually, wait. Looking back at the code flow:

The first call to `_get_pending_context_injection()` at line 1019 clears it after use. So even if cache guidance is set during tool execution, it wouldn't be included because the injection was already consumed!

Unless... let me check if the system prompt is rebuilt somehow...

Actually, I need to look at the actual problem more carefully. The issue is:

1. Agent gets SUMMARY of results (not full logs)
2. Agent sees instruction to "fetch chunks using fetch_cached_result_chunk"
3. Agent says "I don't see any logs yet, let me fetch the chunks"
4. Instead of analyzing what it received, it tries to fetch more

The real problem is that the agent receives a SUMMARY instead of the full result, and the summary + cache guidance confuses it into thinking it needs to fetch more instead of analyzing what it has.

---

## The Core Problem

**In _process_tool_result() (lines 528-677)**:

When large results are cached:
1. Full result (500 events) → Cached
2. Summary returned (2-5 sample events + cache_id)
3. Cache guidance set
4. Agent receives summary in tool message

**The Agent's View**:
```
Tool returned: {
  "cache_id": "...",
  "sample_events": [...2-5 events...],
  "note": "Use fetch_cached_result_chunk to retrieve"
}

System says: "You MUST fetch chunks to show user actual log events"
```

Agent thinks: "I only have samples, I need to fetch chunks"
Agent never thinks: "I should analyze what was in those sample events"

Result: Agent responds as if no logs were found!

---

## The Fix

The solution is to ensure the agent gets the FULL result, not a cached summary with fetch instructions.

Options:
1. Don't cache tool results (simple but defeats caching)
2. Return full result to agent, cache internally for future use
3. Use different caching strategy that doesn't involve fetch instructions
