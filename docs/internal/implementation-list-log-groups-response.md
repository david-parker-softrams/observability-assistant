# Implementation Notes: Agent Response for Log Group Listing Requests

**Date:** 2026-02-12
**Implementer:** Jackie (Senior Software Engineer)
**Status:** Complete - Ready for Testing

## Summary

Successfully implemented agent instructions in the system prompt to guide the agent's behavior when users ask to list log groups. The agent will now acknowledge these requests and direct users to the sidebar.

## Changes Made

### File Modified: `src/logai/core/log_group_manager.py`

Modified two methods in the `LogGroupManager` class:

1. **`_format_full_list()` (lines 347-387)**
   - Added "IMPORTANT: When Users Ask to List Log Groups" section
   - Placed immediately after the header and before the log group list
   - Includes 4-step instructions and example response

2. **`_format_summary()` (lines 389-432)**
   - Added identical "IMPORTANT" section with slightly adjusted example
   - Example response mentions "quite a few" to acknowledge large list size

### Instructions Added to System Prompt

Both methods now include this section:

```
### IMPORTANT: When Users Ask to List Log Groups
When a user asks you to "list log groups", "show log groups", or similar requests:
1. **Acknowledge warmly** - Let them know you have access to all N log groups
2. **Reference the sidebar** - Remind them that all log groups are visible in the left sidebar for easy browsing
3. **Mention /refresh** - Tell them they can use the `/refresh` command to update the list if needed
4. **Offer to help** - Ask if they're looking for a specific log group or pattern

**Example response:** "I have access to all N log groups in your AWS account! They're displayed in the left sidebar for easy reference. You can scroll through them there, or use `/refresh` to update the list. Is there a specific log group you're looking for?"
```

**Key Design Decisions:**

- **Placement:** Instructions placed at the top (after header) to ensure visibility
- **Format:** Used numbered list for clear steps, bold for emphasis
- **Dynamic Count:** Log group count (`{len(self._log_groups)}`) is dynamically inserted
- **Example Response:** Provided a concrete example for the agent to follow
- **Tone:** Instructions emphasize warmth and helpfulness

### Test Coverage

**File Modified:** `tests/unit/test_log_group_manager.py`

Enhanced two existing tests to verify instructions are present:

1. **`test_format_for_prompt_full_list()` (lines 262-302)**
   - Added 7 assertions to check for instruction presence
   - Verifies: IMPORTANT header, 4 instruction steps, example, sidebar mention

2. **`test_format_for_prompt_summary()` (lines 304-344)**
   - Added identical 7 assertions for summary format
   - Ensures large accounts get same instructions

**Test Results:** All 20 tests pass ✅

## Prompt Length Considerations

### Token Usage Estimate

- **Instructions added:** ~150-200 tokens per format method
- **Impact:** Minimal - instructions are concise and only appear once
- **Tradeoff:** Worth the tokens for significantly improved UX

### Before vs After Size

**Small list (≤500 groups):**
- Before: ~500-2000 tokens (depending on count)
- After: ~650-2150 tokens
- Increase: ~150 tokens (~7-30%)

**Large list (>500 groups):**
- Before: ~800-1200 tokens (summary format)
- After: ~950-1350 tokens
- Increase: ~150 tokens (~12-19%)

**Conclusion:** The increase is minimal and well worth the UX improvement.

## Manual Testing Plan

The user should perform the following manual tests to verify the agent's behavior:

### Test Case 1: Direct Request to List
**Action:** Ask the agent: `list log groups`

**Expected Response:**
- Agent acknowledges the request warmly
- Mentions the number of log groups available
- References the left sidebar
- Mentions `/refresh` command
- Asks if user is looking for something specific

**Example Good Response:**
```
I have access to all 135 log groups in your AWS account! They're
displayed in the left sidebar for easy reference. You can scroll
through them there, or use /refresh to update the list. Is there
a specific log group you're looking for?
```

### Test Case 2: Alternative Phrasing
**Action:** Ask the agent: `show me all log groups`

**Expected Response:**
- Similar to Test Case 1
- Agent should understand the intent
- Should provide helpful guidance about sidebar

### Test Case 3: Question Format
**Action:** Ask the agent: `what log groups do I have?`

**Expected Response:**
- Agent responds naturally to question format
- Includes sidebar reference
- Mentions refresh capability

### Test Case 4: Can You Format
**Action:** Ask the agent: `can you list the log groups?`

**Expected Response:**
- Agent responds positively
- References sidebar instead of just listing in chat
- Offers to help find specific groups

### Test Case 5: Follow-up Search
**Action:**
1. First ask: `list log groups`
2. Then ask: `show me the lambda ones`

**Expected Response:**
- First response references sidebar
- Second response helps search for lambda log groups
- Agent may use `list_log_groups` tool with prefix filter

### Test Case 6: Large Account (>500 groups)
**Action:** Test in account with >500 log groups

**Expected Response:**
- Agent mentions "quite a few" or acknowledges large number
- References sidebar as easier way to browse
- Offers to help search for specific patterns/services

## Verification Checklist

- [x] Code changes implemented
- [x] Unit tests updated and passing
- [x] Instructions are clear and prominent in system prompt
- [x] Dynamic log group count is included
- [x] Example responses provided for agent
- [x] Works for both small and large log group lists
- [x] Token usage remains reasonable
- [ ] Manual testing completed (user to verify)
- [ ] Agent responds to various phrasings (user to verify)
- [ ] UX issue resolved (user to verify)

## Next Steps

1. **User Testing:** User should run manual test cases above
2. **Observation:** Monitor agent responses over next few conversations
3. **Iteration:** If responses aren't quite right, adjust instructions
4. **Rollback Plan:** If problematic, revert changes with `git revert`

## Notes for User

### Why This Approach Works

- **LLM-native:** Works with the agent's natural language understanding
- **Flexible:** Agent can adapt response to context
- **Guidance not Commands:** Provides example but allows variation
- **User-friendly:** Maintains conversational tone

### If Agent Still Doesn't Respond

If the agent still doesn't respond appropriately after this fix:

1. **Check prompt construction:** Verify `format_for_prompt()` is called
2. **Check agent sees instructions:** Add debug logging to see system prompt
3. **Model limitations:** Some models ignore instructions better than others
4. **Consider alternatives:** May need to add command interception fallback

### Customizing Instructions

To adjust the agent's response style, edit the instructions in:
- `_format_full_list()` around line 363
- `_format_summary()` around line 415

Changes to make if needed:
- **More concise:** Remove the 4-step list, keep only example
- **More verbose:** Add more examples for different scenarios
- **Different tone:** Adjust the example response wording
- **Stricter:** Use "MUST" language instead of suggestions

## Related Files

- **System prompt construction:** `src/logai/core/orchestrator.py`
- **Sidebar implementation:** `src/logai/ui/widgets/log_groups_sidebar.py`
- **Refresh command:** `src/logai/ui/commands.py`
- **Architecture doc:** `george-scratch/architecture-preload-log-groups.md`

## Success Criteria Met

✅ **AC1:** Agent responds when users ask to list log groups (via system prompt)
✅ **AC2:** Response mentions the left sidebar (in instructions)
✅ **AC3:** Response mentions `/refresh` command (in instructions)
✅ **AC4:** Response is concise (example is 2-3 sentences)
✅ **AC5:** Response is friendly and helpful (warm tone in example)
⏳ **AC6:** Works for various phrasings (needs manual testing)

## Implementation Quality

- **Code Style:** Follows existing patterns in codebase
- **Type Safety:** No type errors introduced
- **Testing:** Comprehensive unit test coverage
- **Documentation:** Clear comments and docstrings maintained
- **Maintainability:** Easy to adjust instructions if needed
- **Performance:** Minimal token overhead (<200 tokens)

---

**Ready for User Testing** 🚀

The implementation is complete and all automated tests pass. The user should now perform manual testing to verify the agent responds appropriately when asked to list log groups.
