# CRITICAL BUG REPORT: Chat Text Selection and Markup Rendering

**Date:** February 20, 2026
**Reporter:** User (David)
**Severity:** CRITICAL - Production Issue
**Status:** UNDER INVESTIGATION

---

## Problem Description

After deploying commit `4b9b7bf` (text selection feature), there are TWO critical issues:

### Issue 1: Text Selection Still Doesn't Work
**User Report:** "I still can't cut and paste from the assistant chat log"

**Impact:**
- The primary feature we just shipped doesn't work
- Users still cannot select or copy text from chat
- This was the main user request

### Issue 2: Rich Markup Showing as Plain Text
**User Report:** "Also now the formatting is coming through as text, so I see '[bold cyan]Assistant:[/bold cyan]' instead of the chat just being highlighted in bold cyan"

**Impact:**
- Chat messages now show markup tags instead of formatted text
- Visual regression - messages look broken
- User experience degraded from before the change

---

## Expected Behavior

### Text Selection
✅ User should be able to click and drag to select text
✅ User should be able to copy selected text with Ctrl+C

### Markup Rendering
✅ Rich markup like `[bold cyan]Assistant:[/bold cyan]` should render as:
   - "Assistant:" in bold cyan color
✅ Users should NOT see the markup tags

---

## Actual Behavior

### Text Selection
❌ User cannot select text from chat messages
❌ Text selection doesn't work at all

### Markup Rendering
❌ Markup tags are visible as plain text
❌ Instead of: **Assistant:** (in cyan)
❌ User sees: [bold cyan]Assistant:[/bold cyan]

---

## Investigation Needed

### Question 1: Why doesn't TextArea support text selection in our TUI?
- Textual documentation says TextArea should support selection
- Our automated tests pass
- But live environment doesn't work
- Is there a terminal compatibility issue?
- Is there a Textual version issue?
- Is there a configuration issue?

### Question 2: Why is Rich markup not rendering?
- TextArea documentation says it renders Rich markup
- We're using `TextArea(text=content)` where content has markup
- Static widget was rendering markup correctly before
- Did we miss a configuration option?
- Does TextArea need a different parameter?

### Question 3: Did we test in the wrong environment?
- Our automated tests passed
- But they don't test actual text selection
- They don't test visual rendering
- We need to understand why tests passed but production failed

---

## Technical Context

### What We Changed
**File:** `src/logai/ui/widgets/messages.py`

**Before (Working):**
```python
from textual.widgets import Static

class ChatMessage(Static):
    pass
```

**After (Broken):**
```python
from textual.widgets import TextArea

class ChatMessage(TextArea):
    def __init__(self, content: str = "") -> None:
        super().__init__(text=content, read_only=True, show_line_numbers=False)
```

### Current Implementation
```python
class AssistantMessage(ChatMessage):
    def append_token(self, token: str) -> None:
        self._content += token
        self.text = f"[bold cyan]Assistant:[/bold cyan] {self._content}"
```

---

## Hypotheses

### Hypothesis 1: TextArea Doesn't Support Terminal Text Selection
- Maybe TextArea selection only works with internal focus
- Maybe it requires different terminal capabilities
- Maybe we need a different approach entirely

### Hypothesis 2: TextArea Doesn't Render Rich Markup
- Maybe TextArea only accepts plain text
- Maybe it needs a different parameter (e.g., `rich_text=True`)
- Maybe it needs a different method (not `.text` property)

### Hypothesis 3: We Need a Hybrid Approach
- Maybe we need to strip markup for display
- But keep original formatting somehow
- Or find a different widget that supports both

---

## Investigation Tasks

1. **Check Textual Documentation:**
   - Does TextArea support Rich markup rendering?
   - Does TextArea support text selection in terminals?
   - What parameters are available?

2. **Check Our Implementation:**
   - Are we using TextArea correctly?
   - Did we miss a configuration option?
   - Is there a different method for setting rich content?

3. **Research Alternatives:**
   - Is there a different widget that supports both?
   - Can we combine multiple widgets?
   - Do we need a custom widget?

4. **Test in Isolation:**
   - Create minimal reproducer
   - Test TextArea with Rich markup
   - Test TextArea text selection
   - Understand actual capabilities

---

## Rollback Consideration

**Question:** Should we rollback immediately?

**Considerations:**
- ❌ Feature doesn't work (text selection)
- ❌ Visual regression (markup showing)
- ✅ But app is still functional
- ✅ Users can still use the app (just can't copy text)

**Recommendation:** Investigate first (15-30 min), rollback if no quick fix

---

## User Impact

**Severity:** HIGH
- Core feature broken (text selection doesn't work)
- Visual quality degraded (markup showing as text)
- Affects all users
- Affects all chat messages

**Urgency:** HIGH
- User reported immediately
- Issue is very visible
- Degrades user experience

---

## Next Steps

1. **Hans:** Investigate immediately (15-30 min)
   - Check Textual docs
   - Test TextArea capabilities
   - Find root cause
   - Propose solution

2. **Decision Point:**
   - If quick fix available: Implement and test
   - If no quick fix: Rollback and redesign

3. **Jackie:** Implement fix (if found)

4. **User:** Test fix in live environment

---

## Lessons Learned (Preliminary)

❌ **Automated tests insufficient** - They passed but didn't catch this
❌ **Manual testing critical** - Should have tested before push
❌ **Assumption failure** - We assumed TextArea would "just work"

**Process Improvement Needed:**
- Must test in live environment before push
- Automated tests must include actual capability validation
- Document assumptions and validate them

---

**Status:** INVESTIGATING
**Priority:** CRITICAL
**Assigned:** Hans (investigation)
