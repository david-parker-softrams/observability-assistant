# Requirements: Pre-load CloudWatch Log Groups at Startup

**Date:** February 12, 2026  
**Requested By:** David Parker  
**TPM:** George  
**Target:** Sally (Software Architect)

---

## User Requirements

### Primary Requirements

1. **Automatic Log Group Discovery at Startup**
   - When LogAI starts, it should automatically fetch ALL CloudWatch log groups from the linked AWS account
   - This should happen BEFORE the agent is initialized
   - This should NOT engage the LLM agent
   - Must not be limited to 50 log groups (need full pagination)
   - Should fetch all log groups visible in the account with current credentials

2. **Agent Context Initialization**
   - The complete list of log groups should be provided to the agent in its initial system prompt
   - Agent should be instructed to use this list as a reference
   - Agent can still lookup log groups dynamically if specifically directed by the user
   - Agent should defer to the pre-loaded list for general queries

3. **User-Triggered Refresh**
   - User should be able to update/refresh the log group list at any time
   - This refresh should bypass the agent (direct command, not LLM query)
   - Once refreshed, the updated list should be given to the agent
   - Agent should be instructed to update its working log group list

---

## Functional Requirements

### FR-1: Startup Log Group Loading

**When:** Application startup, after AWS credentials are loaded, before chat screen appears

**What:**
1. Connect to AWS CloudWatch Logs
2. Fetch ALL log groups using pagination (handle 1000s of groups)
3. Store the complete list in memory
4. Display progress to user (e.g., "Loading log groups..." with count)
5. Handle errors gracefully (AWS connection issues, permission errors)

**Success Criteria:**
- All log groups are fetched (no 50-item limit)
- Handles pagination automatically
- Completes in reasonable time (< 30 seconds for 1000s of groups)
- User sees progress feedback

### FR-2: Agent System Prompt Enhancement

**When:** Agent initialization, before first user query

**What:**
1. Format the complete log group list for inclusion in system prompt
2. Add instructions to agent:
   - "You have been provided with a complete list of available log groups"
   - "Use this list as your primary reference for log groups"
   - "You may still call list_log_groups if user specifically requests a fresh lookup"
   - "For general queries, defer to the provided list"
3. Include the list in structured format (e.g., bullet list, JSON array)

**Success Criteria:**
- Agent has full log group context from start
- Agent doesn't unnecessarily call list_log_groups for every query
- Agent can still lookup if needed

### FR-3: User Refresh Command

**When:** User types a command to refresh the log group list

**What:**
1. New slash command (e.g., `/refresh` or `/refresh-logs`)
2. Command bypasses agent, directly calls AWS CloudWatch
3. Fetches complete updated list with pagination
4. Shows progress to user ("Refreshing log groups...")
5. Updates the in-memory list
6. Sends updated list to agent with instruction to update its context
7. Confirms to user ("Updated: Found X log groups")

**Success Criteria:**
- Command works without agent involvement
- Agent receives updated list
- User gets confirmation
- Takes < 30 seconds for large accounts

---

## Non-Functional Requirements

### NFR-1: Performance
- Startup log group fetch should not delay app launch by more than 10 seconds for typical accounts
- Should show progress indicator during fetch
- Should handle 5000+ log groups efficiently

### NFR-2: Error Handling
- Graceful degradation if AWS connection fails at startup
- Clear error messages to user
- Allow app to continue even if log group fetch fails (agent can still use list_log_groups tool)

### NFR-3: User Experience
- Progress indicators during long operations
- Clear feedback on success/failure
- Non-blocking UI (app should remain responsive)

### NFR-4: Resource Usage
- Minimal memory footprint (even with 1000s of log groups)
- Efficient pagination (don't load all at once if streaming is better)

---

## Technical Considerations

### AWS API Pagination
- `describe_log_groups` API returns max 50 groups per call
- Must handle `nextToken` for pagination
- Accounts may have 1000s of log groups

### System Prompt Size
- LLM system prompts have token limits
- May need to format log group list efficiently
- Consider truncation or summarization for very large lists (>1000 groups)
- Or provide count + sample, with note that full list is available

### Agent Context Management
- How to update agent's context mid-conversation?
- Does orchestrator support context updates?
- Should we restart conversation after refresh?

### UI/UX Flow
1. **Startup:**
   ```
   LogAI v0.1.0
   ⏳ Loading log groups from AWS... (45 found)
   ✓ Found 123 log groups
   ✓ Agent initialized with log group list
   ```

2. **Refresh Command:**
   ```
   User> /refresh
   ⏳ Refreshing log groups from AWS... (52 found)
   ✓ Updated: Found 135 log groups (+12 new)
   ✓ Agent context updated
   ```

---

## Existing System Context

### Current Behavior
- Agent calls `list_log_groups` tool for every query that needs log groups
- Each call limited to 50 groups (or user-specified limit)
- No startup pre-loading
- Agent has no initial context about available log groups

### Components Involved
1. **CloudWatch DataSource** (`src/logai/providers/datasources/cloudwatch.py`)
   - Has `list_log_groups()` method
   - Handles pagination already (check implementation)

2. **Orchestrator** (`src/logai/core/orchestrator.py`)
   - Manages agent and system prompt
   - Would need to accept pre-loaded log groups
   - Would need method to update context

3. **CLI/Main** (`src/logai/cli.py`, `src/logai/ui/app.py`)
   - Entry points for application
   - Where startup logic would be added

4. **UI Commands** (`src/logai/ui/commands.py`)
   - Where `/refresh` command would be added

5. **Tool Registry** (`src/logai/core/tools/`)
   - `list_log_groups` tool exists
   - Agent should still be able to use it

---

## Design Questions for Sally

1. **System Prompt Strategy:**
   - How should we format the log group list in the system prompt?
   - What if there are 2000+ log groups? Include all or summarize?
   - Should we include metadata (creation date, size) or just names?

2. **Context Update Mechanism:**
   - How to update agent context mid-conversation after `/refresh`?
   - Should we restart the conversation or inject a new system message?
   - How to ensure agent "forgets" old list and uses new one?

3. **Error Handling:**
   - What if startup fetch fails? Start with empty list? Retry?
   - What if refresh fails? Keep old list or clear it?

4. **State Management:**
   - Where to store the log group list? In orchestrator? Separate manager?
   - Should it be part of application state or orchestrator state?

5. **Progress Feedback:**
   - How to show progress during startup and refresh?
   - Should we stream updates ("50 found... 100 found...")?

6. **Command Design:**
   - Command name: `/refresh`, `/refresh-logs`, `/update-log-groups`?
   - Should command take arguments (e.g., `/refresh --prefix /aws/lambda`)?

7. **Tool Interaction:**
   - Should agent still have access to `list_log_groups` tool?
   - How to prevent redundant calls if list is already loaded?
   - When should agent use tool vs pre-loaded list?

---

## Success Criteria

**Feature is successful if:**

1. ✅ All log groups are loaded at startup (no pagination limit)
2. ✅ Agent has log group context from first query
3. ✅ Agent reduces unnecessary `list_log_groups` calls
4. ✅ User can refresh list with simple command
5. ✅ Refresh updates agent's working context
6. ✅ Startup delay is acceptable (< 10 seconds typical)
7. ✅ Error handling is graceful
8. ✅ User gets clear feedback on progress/status

---

## Out of Scope

- Automatic periodic refresh (only manual via command)
- Filtering log groups at startup (fetch all, user can filter via agent)
- Caching log groups to disk (in-memory only for this feature)
- Real-time log group discovery (only at startup and manual refresh)

---

## Priority

**High** - Significant UX improvement, reduces API calls, improves agent performance

---

## Notes

- This should be transparent to the user (happens automatically)
- Should work with all AWS authentication methods (profile, keys)
- Should respect AWS region settings
- Should handle rate limiting if user has many log groups

---

**Ready for Sally's architectural design.**
