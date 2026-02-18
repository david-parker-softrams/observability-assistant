# Requirements: Agent Response for Log Group Listing Requests

**Date:** 2026-02-12
**Requestor:** David Parker
**Priority:** High (User Experience Issue)
**Status:** New

## Problem Statement

When users ask the agent to "list log groups" or similar queries, the agent currently provides no response. This is confusing because:
1. The agent has access to log groups (pre-loaded at startup)
2. The log groups are visible in the left sidebar
3. Users don't know why they're getting no response

This creates a poor user experience where the agent appears unresponsive.

## Root Cause

The agent has access to the complete list of log groups in its system prompt, but when users explicitly ask to list them:
- The agent may not be invoking the `list_log_groups` tool (since it already knows the list)
- The agent is not providing any verbal response to acknowledge the request
- Users are left confused about whether their request was understood

## Requirements

### Functional Requirements

**FR1: Agent Must Acknowledge List Requests**
- When a user asks to list log groups, the agent MUST provide a response
- The response must be helpful and guide the user to the sidebar

**FR2: Agent Should Reference the Sidebar**
- The agent should remind users that log groups are visible in the left sidebar
- The agent should explain that this is a better way to view log groups (always visible, scrollable)

**FR3: Agent Should Mention Refresh Option**
- The agent should inform users about the `/refresh` command
- Explain that `/refresh` updates both the agent's context and the sidebar

**FR4: Agent May Still Use the Tool**
- If the sidebar is hidden or unavailable, the agent may invoke `list_log_groups` tool
- If the user specifically asks for a "fresh" list, the agent should suggest `/refresh`

### Non-Functional Requirements

**NFR1: Response Should Be Concise**
- Don't overwhelm users with lengthy explanations
- 2-3 sentences maximum

**NFR2: Response Should Be Helpful**
- Guide users to the most efficient workflow
- Be friendly and informative

**NFR3: Response Should Be Consistent**
- Similar queries should get similar responses
- Maintain the agent's conversational tone

## Proposed Solutions

### Option 1: Update System Prompt (Recommended)
Add instructions to the agent's system prompt that tell it:
- When users ask about log groups, acknowledge the request
- Reference the sidebar as the primary way to view log groups
- Mention `/refresh` for updating the list

**Pros:**
- Simple to implement
- Works for all similar queries
- Maintains agent autonomy

**Cons:**
- Relies on LLM following instructions
- May not be 100% consistent

### Option 2: Command Interception
Create a `/list-log-groups` command that shows a message

**Pros:**
- 100% consistent
- Guaranteed response

**Cons:**
- Requires users to use slash command instead of natural language
- Less flexible than natural conversation

### Option 3: Tool Response Modification
Modify the `list_log_groups` tool to return a message about the sidebar

**Pros:**
- Works when tool is invoked
- Provides context in tool result

**Cons:**
- Only works if agent invokes the tool
- Doesn't help if agent doesn't invoke it

## Recommendation

**Use Option 1: Update System Prompt**

This is the most natural and flexible solution. We should add clear instructions to the agent's system prompt that guide its behavior when users ask about log groups.

### Proposed System Prompt Addition

Add to the agent's system prompt (in the LogGroupManager context section):

```
IMPORTANT: When users ask you to list or show log groups:
1. Acknowledge their request warmly
2. Remind them that all log groups are visible in the left sidebar (toggle with /logs)
3. Mention that they can use /refresh to update the list if needed
4. If the list is very large (>500 groups), offer to help them search for specific patterns

Example response: "I have access to all [N] log groups in your AWS account, and they're displayed in the left sidebar for easy reference! You can scroll through them there, or use /refresh if you need to update the list. Is there a specific log group you're looking for?"
```

## Implementation Notes

### Files to Modify

**Option 1 (Recommended):**
1. **`src/logai/core/log_group_manager.py`**
   - Update `format_log_groups_for_prompt()` method
   - Add instructions for agent behavior regarding log group queries
   - Include example responses

**Option 2 (Alternative):**
1. **`src/logai/ui/commands.py`**
   - Add `/list-log-groups` command handler
   - Display message about sidebar

**Option 3 (Alternative):**
1. **`src/logai/tools/aws/cloudwatch_logs.py`**
   - Modify `list_log_groups` tool implementation
   - Add sidebar reference in tool response

### Testing Requirements

1. **Manual Testing:**
   - Ask agent: "list log groups"
   - Ask agent: "show me all log groups"
   - Ask agent: "what log groups do I have?"
   - Ask agent: "can you list the log groups?"

2. **Verify Responses:**
   - Agent acknowledges request ✓
   - Agent mentions sidebar ✓
   - Agent mentions `/refresh` ✓
   - Response is concise and helpful ✓

## Example Responses

**Good Response 1:**
```
I have access to all 135 log groups in your AWS account! They're displayed
in the left sidebar for easy reference - you can scroll through them there.
If you need to refresh the list, just use the /refresh command. Is there a
specific log group you're looking for?
```

**Good Response 2:**
```
You can see all available log groups in the left sidebar on the screen!
There are currently 42 log groups loaded. If you need to update this list,
use /refresh. Would you like help finding a specific log group?
```

**Good Response 3:**
```
All log groups are visible in the left sidebar (toggle with /logs if hidden).
I have 287 groups loaded. Use /refresh to update the list. Looking for
something specific?
```

## Acceptance Criteria

**AC1:** Agent responds when users ask to list log groups
**AC2:** Response mentions the left sidebar
**AC3:** Response mentions `/refresh` command
**AC4:** Response is concise (2-4 sentences)
**AC5:** Response is friendly and helpful
**AC6:** Works for various phrasings ("list log groups", "show log groups", etc.)

## Non-Goals

- Creating a new slash command (users should use natural language)
- Preventing the agent from using the `list_log_groups` tool
- Forcing the agent to always give the same response
- Adding new UI elements

## References

- Log group pre-loading feature: `george-scratch/architecture-preload-log-groups.md`
- System prompt location: `src/logai/core/orchestrator.py` (system prompt construction)
- Log group formatting: `src/logai/core/log_group_manager.py`
