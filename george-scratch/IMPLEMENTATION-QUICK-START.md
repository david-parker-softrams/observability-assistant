# Text Selection Fix: Implementation Quick Start Guide

**Framework:** Textual 7.5.0
**Date:** February 20, 2026
**Status:** Ready to Implement

---

## TL;DR

Replace `Static` and `RichLog` widgets with `TextArea(read_only=True)` to enable text selection and copying.

| Component | Current Widget | New Widget | File | Est. Time |
|-----------|----------------|-----------|------|-----------|
| Chat Messages | Static | TextArea(read_only=True) | `src/logai/ui/widgets/messages.py` | 1.5-2 hrs |
| Context Modal | RichLog | TextArea(read_only=True) | `src/logai/ui/screens/context_viewer.py` | 5-6 hrs |

---

## Why This Works

```
OLD: Static/RichLog → VerticalScroll intercepts events → No text selection
NEW: TextArea → Selection logic independent of container → Works perfectly
```

TextArea's selection logic doesn't depend on getting through container events. It works in ANY container.

---

## Chat Window Implementation (1.5-2 hours)

### Changes Required

**File:** `src/logai/ui/widgets/messages.py`

```python
# 1. Update imports (line 3)
from textual.widgets import Static, TextArea

# 2. Change base class from Static to TextArea (example for UserMessage)
class UserMessage(ChatMessage):
    DEFAULT_CSS = """
    UserMessage {
        background: $primary;
        color: $text;
        padding: 1 2;
        margin: 1 0 1 4;
        border: solid $primary-darken-2;
    }
    """

    def __init__(self, content: str) -> None:
        # OLD: super().__init__(f"[bold]You:[/bold] {content}")
        # NEW: Use TextArea with formatted text
        formatted = f"You: {content}"
        super().__init__(formatted)
        # ... rest of init
```

**Step-by-Step:**
1. Change parent class: `ChatMessage(TextArea)` instead of `ChatMessage(Static)`
2. Update `__init__` in each message class to work with TextArea
3. Each class sets `read_only=True`
4. Content is plain text (Rich markup will be lost - acceptable trade-off)

### Testing

```bash
# After implementation:
pytest tests/unit/ui/test_messages.py -v
pytest tests/integration/test_chat_*.py -v

# Manual test:
# - Open chat window
# - Try Ctrl+A to select all
# - Try Ctrl+C to copy
# - Try Shift+Arrow keys to select
# - Try triple-click to select line
```

---

## Context Modal Implementation (5-6 hours)

### Changes Required

**File:** `src/logai/ui/screens/context_viewer.py`

**Step 1: Update imports (line 15)**
```python
from textual.widgets import Button, Collapsible, RichLog, Static, TextArea
```

**Step 2: Replace RichLog in compose() method**

**Before (lines 187-194):**
```python
with VerticalScroll(id="staged-scroll"):
    yield RichLog(
        id="staged-content",
        wrap=True,
        highlight=False,
        markup=True,
        auto_scroll=False,
    )
```

**After:**
```python
with VerticalScroll(id="staged-scroll"):
    yield TextArea(
        id="staged-content",
        text="",
        read_only=True,
        soft_wrap=True,
        show_line_numbers=False,
        show_cursor=False,
    )
```

Do the same for Agent Memory section (lines 203-210).

**Step 3: Add markup stripping utility (new method)**
```python
def _strip_rich_markup(self, text: str) -> str:
    """Remove Rich markup tags from text."""
    import re
    text = re.sub(r'\[[\w\s\-]*\]', '', text)
    text = re.sub(r'\[/[\w\s\-]*\]', '', text)
    return text
```

**Step 4: Update on_mount() method (lines 217-243)**

**Before:**
```python
staged_log = self.query_one("#staged-content", RichLog)
formatted_staged = self._format_staged_context()
staged_log.write(formatted_staged)  # RichLog method
staged_log.refresh()
```

**After:**
```python
staged_textarea = self.query_one("#staged-content", TextArea)
formatted_staged = self._format_staged_context()
clean_staged = self._strip_rich_markup(formatted_staged)
staged_textarea.text = clean_staged  # TextArea property
# No need for refresh() with TextArea
```

Do the same for Agent Memory section.

**Step 5: Update CSS (optional, but recommended)**

**Before (lines 104-112):**
```css
#staged-content, #memory-content {
    width: 100%;
    min-height: 20;
    height: auto;
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}
```

**After:**
```css
#staged-content, #memory-content {
    width: 100%;
    min-height: 20;
    height: 1fr;
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}

#staged-content:focus, #memory-content:focus {
    border: solid $primary;
}
```

### Testing Checklist

```bash
# Run existing tests
pytest tests/integration/test_context_modal_callback.py -v
pytest tests/integration/test_context_management_e2e.py -v

# Add new test file: tests/unit/ui/screens/test_context_viewer_text_selection.py
pytest tests/unit/ui/screens/test_context_viewer_text_selection.py -v
```

**Manual Testing (14-item checklist):**
- [ ] Modal opens and displays without errors
- [ ] Staged Context section displays text
- [ ] Agent Memory section displays text
- [ ] Can click-drag to select text in Staged Context
- [ ] Can click-drag to select text in Agent Memory
- [ ] Triple-click selects entire line
- [ ] Ctrl+A selects all text in current section
- [ ] Shift+Arrow keys select text
- [ ] Ctrl+C copies selected text (paste to verify)
- [ ] Copy All button still works
- [ ] Close button dismisses modal
- [ ] Escape key dismisses modal
- [ ] Text wrapping still works
- [ ] Collapsible sections still collapse/expand

---

## Common Pitfalls to Avoid

### ❌ DON'T
```python
# Don't forget to set read_only=True
textarea = TextArea()  # WRONG: Allows editing

# Don't mix RichLog and TextArea methods
richlog.write(text)  # Works for RichLog, NOT for TextArea
textarea.write(text)  # Method doesn't exist for TextArea

# Don't forget to import TextArea
from textual.widgets import Static  # WRONG: Missing TextArea
from textual.widgets import Static, TextArea  # Correct
```

### ✅ DO
```python
# Always set read_only=True for display-only use
textarea = TextArea(text="content", read_only=True)

# Use TextArea.text property, not .write()
textarea.text = "new content"

# Import everything you use
from textual.widgets import Button, Collapsible, Static, TextArea
```

---

## Before & After Examples

### Chat Window

**Before (Static widget):**
```
User: Hello, can you help me?
[User tries to select text... nothing happens]
```

**After (TextArea):**
```
User: Hello, can you help me?
[User selects text by dragging]
[User presses Ctrl+C]
✓ Text copied to clipboard
```

### Context Modal

**Before (RichLog widget):**
```
Staged Context (5 items)
[User tries to select text... nothing happens]
[User clicks "Copy All" button to get text]
```

**After (TextArea):**
```
Staged Context (5 items)
[User selects text by dragging]
[User presses Ctrl+C]
✓ Text copied to clipboard
[OR: User clicks "Copy All" for entire modal]
```

---

## Performance Considerations

### TextArea Performance
- **Small texts (< 10KB):** Excellent, no issues
- **Medium texts (10KB - 1MB):** Good, no noticeable lag
- **Large texts (> 1MB):** May have slight lag, acceptable for most use cases

### Optimization if Needed
```python
# Option 1: Show loading indicator while loading large text
async def on_mount(self):
    textarea = self.query_one("#content", TextArea)
    # Load text in background
    textarea.text = await self._load_large_text()
    self.refresh()

# Option 2: Paginate large content
# If modal shows > 10MB text, consider splitting into pages
```

For LogAI context modal, typical sizes:
- Staged context: < 100KB (rarely > 1MB)
- Conversation history: < 500KB per session
- **Conclusion:** Performance not a concern

---

## Rollback Instructions

If something goes wrong:

**Chat Window:**
```bash
git checkout src/logai/ui/widgets/messages.py
```

**Context Modal:**
```bash
git checkout src/logai/ui/screens/context_viewer.py
```

The changes are completely isolated and reversible.

---

## Key Resources

### Investigation Reports
- Chat investigation: `george-scratch/investigation-chat-text-selection.md` (700 lines)
- Modal investigation: `george-scratch/investigation-context-modal-text-selection.md` (726 lines)
- Summary: `george-scratch/BOTH-INVESTIGATIONS-SUMMARY.md` (375 lines)
- This guide: `george-scratch/IMPLEMENTATION-QUICK-START.md`

### Textual Documentation
- TextArea widget: https://textual.textualize.io/widgets/text_area/
- RichLog widget: https://textual.textualize.io/widgets/rich_log/
- Static widget: https://textual.textualize.io/widgets/static/

---

## Getting Help

### If TextArea doesn't work as expected:
1. Check Textual version: `python -c "import textual; print(textual.__version__)"`
   - Should be 7.5.0 or higher
2. Review investigation reports for details
3. Check the manual testing checklist
4. Post questions with specific error messages

### If markup stripping breaks something:
1. Test regex: `_strip_rich_markup("[bold cyan]text[/bold cyan]")` should give "text"
2. Review formatting methods: `_format_staged_context()`, `_format_conversation_history()`
3. Adjust regex if needed for custom markup patterns

---

## Success Criteria

✅ **Chat Window Fixed:**
- Mouse text selection works
- Keyboard text selection works (Shift+Arrows, Ctrl+A)
- Ctrl+C copies selected text
- All existing tests pass
- No regressions

✅ **Context Modal Fixed:**
- Mouse text selection works in both sections
- Keyboard text selection works (Shift+Arrows, Ctrl+A)
- Ctrl+C copies selected text
- Copy All button still works
- All existing tests pass
- No regressions

✅ **Both Components:**
- Users report improved experience
- Copy functionality works as expected
- No performance degradation
- CSS styling remains clean

---

## Timeline

- **Chat Window:** 1.5-2 hours (can do first)
- **Context Modal:** 5-6 hours (can do in parallel or after)
- **Combined:** 5-6 hours if parallel, 7-8 hours if sequential

**Recommended:** Do chat first (simpler), then modal (more comprehensive testing).

---

## Questions?

Refer to investigation reports for detailed explanations:
1. **Why did this happen?** → See root cause analysis
2. **Why TextArea?** → See solution evaluation section
3. **How to implement?** → See implementation code map
4. **What about Rich markup?** → See trade-offs section
5. **Is it safe?** → See risk assessment section

---

**Ready to implement!** 🚀

**Next Step:** Assign to developer/agent with access to this guide + investigation reports.
