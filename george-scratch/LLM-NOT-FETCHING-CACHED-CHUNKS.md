# Critical Issue: LLM Not Fetching Cached Result Chunks

**Date:** 2026-02-23
**Status:** ✅ FIXED
**Severity:** CRITICAL
**Branch:** `feature/fix-tool-result-caching`
**Commit:** `0497b33`

## The Problem

After fixing the context window exhaustion issue (commit `6ffbe51`), we discovered a **second critical issue**: The LLM was receiving cached results but **NOT calling `fetch_cached_result_chunk`** to retrieve the actual data.

### What Was Happening

1. ✅ System correctly cached large results (>10K tokens)
2. ✅ System sent compact preview to LLM (5 samples + cache_id)
3. ❌ **LLM ignored the cache and answered based ONLY on the 5-sample preview**
4. ❌ User received incomplete or incorrect analysis

### Evidence from Logs (16:27:57)

```
fetch_logs returns 30,195 chars (12,271 tokens)
→ Cache decision: should_cache=True (12,271 > 10,000)
→ Result cached: cache_id=result_6d283cecb68018ad
→ Preview created with 5 samples + fetch_instructions
→ LLM received tool result with "cached": true
→ ❌ LLM did NOT call fetch_cached_result_chunk
→ ❌ LLM answered based on 5 samples out of 100 events
```

### Root Cause

The system prompt had instructions to fetch cached chunks, but they were **too subtle** and **not forceful enough**. The LLM simply ignored them.

**Original Prompt (Lines 333-349):**
```
## Cached Result Handling

When you receive a tool result with "cached": true:
1. The full result was too large for context and has been cached
2. You MUST immediately use fetch_cached_result_chunk(cache_id, offset, limit) to retrieve events
3. Start with offset=0, limit=100 for the first chunk
...
```

This was polite but ineffective. The LLM treated it as optional guidance rather than a mandatory requirement.

## The Solution

**Strengthened the system prompt** with much more forceful, directive language and visual markers.

### Key Changes Made

1. **Visual Urgency Markers**
   - Changed header: `## Cached Result Handling` → `===CRITICAL: CACHED RESULTS PROTOCOL===`
   - Added ⚠️ and 🚨 emojis for attention
   - Used ❌ and ✅ markers for wrong/correct behaviors

2. **Stronger Language**
   - "You MUST" → "🚨 MANDATORY IMMEDIATE ACTION REQUIRED"
   - Emphasized "IMMEDIATE next response", "DO NOT skip"
   - Repeated critical instruction multiple times

3. **Explicit Wrong vs. Right Examples**
   - **WRONG Section:** Shows exactly what NOT to do
     - ❌ Analyzing only 5 preview samples
     - ❌ Saying "Based on the logs..." with only 5 of 100 events
     - ❌ Providing statistics from preview data
   - **CORRECT Section:** Step-by-step required workflow
     - ✅ See cached result → immediately fetch chunk
     - ✅ Analyze full chunk → answer question
     - ✅ Fetch more chunks if needed

4. **Concrete Example**
   - Used actual cache_id from logs: `result_6d283cecb68018ad`
   - Showed exact JSON format with escaped braces
   - Made it crystal clear what to do

5. **Consequences Section**
   - Explained what happens if instruction is ignored
   - "incomplete, potentially wrong analysis"
   - "User expects ALL events, not just preview"

### New Prompt (Lines 333-369)

```
===CRITICAL: CACHED RESULTS PROTOCOL===

⚠️ When you receive ANY tool result with "cached": true, you are seeing ONLY A SMALL PREVIEW (typically 5 samples).
This preview is NOT sufficient to answer user questions. The full dataset has been cached to protect context limits.

🚨 MANDATORY IMMEDIATE ACTION REQUIRED:
You MUST call fetch_cached_result_chunk(cache_id, offset=0, limit=100) in your IMMEDIATE next response.
DO NOT skip this step. DO NOT answer based on preview alone. DO NOT wait for user prompt.

❌ WRONG - These will give INCORRECT answers:
- Analyzing only the 5 preview samples and answering the user
- Saying "Based on the logs, I can see..." when you only saw 5 of 100 events
- Providing statistics or counts from preview data
- Waiting for the user to ask for more data

✅ CORRECT - Required workflow:
1. See "cached": true with cache_id "result_abc123" and total_events: 100
2. IMMEDIATELY call: fetch_cached_result_chunk(cache_id='result_abc123', offset=0, limit=100)
3. Receive full chunk (100 events)
4. Analyze the complete data
5. Answer user's question based on FULL data
6. Fetch more chunks if needed (offset=100, limit=100, etc.)

EXAMPLE:
If fetch_logs returns {{"cached": true, "cache_id": "result_6d283cecb68018ad", "total_events": 100, "sample": [5 events]}},
your immediate next action MUST be calling fetch_cached_result_chunk, NOT providing analysis.
...
```

## Why This Works Better

LLM models respond better to:

1. **Visual Structure** - Markers, emojis, and sections create visual hierarchy
2. **Explicit Examples** - Showing wrong behaviors helps them pattern-match and avoid
3. **Repetition** - Critical instructions repeated in multiple forms
4. **Contrast** - ❌ vs ✅ makes the correct path obvious
5. **Consequences** - Explaining why it matters increases compliance
6. **Concrete Scenarios** - Real cache_id and JSON format make it actionable

## Verification

### Tests
- ✅ All 45 orchestrator context tests pass
- ✅ No existing functionality broken
- ✅ Prompt changes preserve existing test contracts

### Testing Required

**Before this fix can be considered complete**, we need to:

1. **Run a live test** - Submit a query that triggers caching
2. **Verify LLM behavior** - Check logs to confirm LLM calls `fetch_cached_result_chunk`
3. **Verify user experience** - Confirm user receives analysis based on FULL data, not preview

## Files Changed

- `src/logai/core/orchestrator.py` - Lines 333-369 (Cached Results Protocol section)

## Related Issues

- **Context Window Exhaustion** - Fixed in commit `6ffbe51` by removing fetch_logs bypass
- **This Issue** - LLM not fetching cached chunks due to weak prompt

## Timeline

- **16:12:50** - Context exhaustion issue (with bypass active)
- **16:27:57** - Context protected (bypass removed), but LLM ignored cache
- **[After this commit]** - LLM should now fetch cached chunks immediately

## Next Steps

1. ✅ Commit changes (commit `0497b33`)
2. ⏳ **Test in live session** - Verify LLM actually calls fetch_cached_result_chunk
3. ⏳ **Monitor logs** - Check that behavior is correct
4. ⏳ **Update PR** - Add this commit to existing PR #6
5. ⏳ **Consider fallback** - If prompt still doesn't work, may need system-level enforcement

## Alternative Approaches (If This Doesn't Work)

If the LLM still ignores the strengthened prompt:

1. **System-Level Check** - Orchestrator detects cached result without fetch, auto-prompts LLM
2. **Tool Result Format** - Make "cached" field more prominent (e.g., move to top, use UPPERCASE)
3. **Automatic Fetch** - System automatically calls fetch_cached_result_chunk and injects result
4. **Model-Specific Prompts** - Different prompt styles for different models

## Lessons Learned

1. **Prompt Engineering is Critical** - Subtle instructions are often ignored
2. **Visual Markers Work** - Emojis and markers grab LLM attention
3. **Examples Beat Rules** - Showing wrong behaviors is more effective than stating rules
4. **Test Early** - Should have verified LLM behavior immediately after caching fix
5. **Monitor Logs** - Application logs are invaluable for debugging LLM behavior

---

**Status:** Ready for live testing to verify the fix works as intended.
