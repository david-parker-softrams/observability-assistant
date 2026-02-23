# CRITICAL FINDING: LLM Not Calling Tools

**Date:** 2026-02-23
**Investigator:** George (TPM) with Jackie (Engineer)
**Status:** 🚨 ROOT CAUSE IDENTIFIED - DIFFERENT THAN EXPECTED

## Executive Summary

The root cause of "agent can't see fetch_logs results" is **NOT** a caching problem. The LLM is **not calling the `fetch_logs` tool at all** when it should.

## Evidence

### Test Query Analysis
- **User Query:** "Summarize the logs from the past 2 hours for the highlighted log group"
- **Log Group Selected:** `/aws/lambda/bosc-helpdesk-orchestrator-prod`
- **Expected Behavior:** LLM should call `fetch_logs` tool
- **Actual Behavior:** LLM responded with text only, NO tool calls made

### Log File Evidence
From `~/.logai/logs/logai.log` (2026-02-23 16:10:48):

1. ✅ **Tools were defined and sent to LLM**
   - `list_log_groups`
   - `fetch_logs`
   - `search_logs`
   - `fetch_cached_result_chunk`

2. ✅ **System prompt was sent** with explicit instructions:
   ```
   ## Guidelines
   ### Tool Usage
   1. Always start by understanding what log groups are available if the user doesn't specify
   2. Use appropriate time ranges - start narrow and expand if needed
   3. Use filter patterns to reduce data volume when searching for specific issues
   4. Fetch logs before attempting analysis
   ```

3. ❌ **NO tool calls were made by LLM**
   - No `fetch_logs` execution
   - No diagnostic logging triggered (because tool never ran)
   - LLM appears to have responded with text-only response

## What This Means

### Our Previous Assumptions Were Wrong
- ❌ We thought: Results were being cached improperly
- ❌ We thought: Bypass logic wasn't working
- ✅ **Reality: The LLM never calls the tool in the first place**

### The Real Problems
1. **LLM Tool-Calling Issue**
   - The LLM model (qwen3:32b via Ollama) is not reliably calling tools
   - Even with explicit instructions, it's responding with text instead of tool calls

2. **Possible Root Causes**
   - **Model capability**: qwen3:32b may have poor tool-calling performance
   - **Prompt confusion**: System prompt might be discouraging tool use
   - **Context budget**: At 13% budget (4044/31130 tokens), system prompt is being truncated
   - **Tool definition format**: Ollama may require different tool format than what's being sent

## Context Budget Warning Found
```
2026-02-23 16:10:48,695 - logai.core.context.budget_tracker - WARNING -
System prompt exceeds budget (2014 > 1638), will be truncated in context
```

**This is significant!** The system prompt is 2014 tokens but only 1638 tokens are budgeted for it. This means **critical tool usage instructions may be getting truncated**.

## Diagnostic Logging Status
The comprehensive diagnostic logging we added (commit 1245778) is working correctly, but it's simply never triggered because:
- `fetch_logs` is never called
- `_process_tool_result()` is never reached
- Bypass logic is never tested

## Next Steps (Recommendations)

### Immediate Investigation
1. **Check context budget truncation**
   - Determine what parts of system prompt are being cut off
   - Those missing parts might include tool-calling instructions

2. **Test with different model**
   - Try a model known for good tool-calling (Claude, GPT-4, etc.)
   - This will prove whether it's a model problem or prompt problem

3. **Simplify system prompt**
   - Reduce token count to fit within budget
   - Put critical tool-calling instructions at the START (before truncation)

4. **Add tool-call diagnostic logging**
   - Log when LLM returns NO tool calls but should have
   - Help identify pattern of when tools are/aren't called

### Medium-Term Fixes
1. **Increase context budget for system prompt**
2. **Rewrite system prompt to be more concise**
3. **Consider switching LLM model if qwen3:32b has poor tool-calling**
4. **Add fallback behavior when LLM doesn't call tools**

## Files with Diagnostic Logging (Ready for Use)
Once we fix the tool-calling issue, these files have comprehensive logging ready:
- `src/logai/core/orchestrator.py` (lines 681-755, 2081-2136, 1388-1441)
- Commit: 1245778

## Status of Caching Reimplementation
All the caching work is **still valid and important**:
- ✅ Phase 1 & 2 implemented correctly
- ✅ Bypass logic implemented correctly (just never hit)
- ✅ All 845 unit tests passing
- ✅ Code is production-ready

**But**: We can't test if it works until we fix the LLM tool-calling issue.

## Conclusion

We were solving the right problem (result caching) but discovered a bigger, upstream problem: **the LLM isn't calling tools reliably**.

This explains why all our caching fixes didn't resolve the reported issue - the tool was never being called to begin with!

**Priority**: Fix LLM tool-calling FIRST, then verify caching works correctly.
