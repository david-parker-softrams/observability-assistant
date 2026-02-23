# Investigation: Context Viewer Modal Text Selection Issue

**Date:** February 20, 2026
**Investigator:** Hans (Code Librarian)
**Framework:** Textual 7.5.0
**Status:** Complete ✓

---

## Executive Summary

Users cannot select or copy text from the Context Viewer modal using the mouse. The root cause differs from the chat window: **RichLog widgets do not support mouse-based text selection even when placed in scrollable containers**, unlike Static widgets which have the technical capability but are blocked by event interception.

**Severity:** MEDIUM - Blocks user workflow for copying context (workaround: "Copy All" button exists)

**Recommendation:** Replace `RichLog` widgets with `TextArea` in `read_only=True` mode to enable native text selection with full keyboard and mouse support, while preserving Rich markup via preprocessing.

---

## Current Implementation Details

### 1. Context Viewer Modal Architecture

**Location:** `src/logai/ui/screens/context_viewer.py` (lines 1-525)

**Modal Screen Class:** `ContextViewerScreen(ModalScreen[None])`

**Purpose:** Displays two independent sections of agent context:
- **Staged Context:** Logs waiting to be injected (pending_context_injection)
- **Agent Memory:** Full conversation history the agent has in memory

### 2. Container Hierarchy

```
ContextViewerScreen (ModalScreen)
│
├─ Container (#context-container, lines 174-215)
│  ├─ Static (header: "Context Viewer", line 176)
│  │   CSS: height 3, background: $primary, bold text
│  │
│  └─ Horizontal (#sections-container, line 179)
│     │   CSS: layout horizontal, overflow hidden, height 1fr
│     │
│     ├─ Collapsible (Staged Context, lines 182-194)
│     │  │   Title: "Staged Context ({staged_count} items)"
│     │  │   collapsed: False (expanded by default)
│     │  │
│     │  └─ VerticalScroll (#staged-scroll, line 187)
│     │     │   CSS: width 1fr, height 1fr, scrollbar-gutter stable
│     │     │
│     │     └─ RichLog (#staged-content, lines 188-194)
│     │         Parameters:
│     │         - wrap=True (enable text wrapping)
│     │         - highlight=False (no syntax highlighting)
│     │         - markup=True (enable Rich markup)
│     │         - auto_scroll=False (don't auto-scroll to bottom)
│     │
│     └─ Collapsible (Agent Memory, lines 198-210)
│         │   Title: "Agent Memory (Full Context: {memory_count} messages)"
│         │   collapsed: False (expanded by default)
│         │
│         └─ VerticalScroll (#memory-scroll, line 203)
│             │   CSS: width 1fr, height 1fr, scrollbar-gutter stable
│             │
│             └─ RichLog (#memory-content, lines 204-210)
│                 Parameters:
│                 - wrap=True (enable text wrapping)
│                 - highlight=False (no syntax highlighting)
│                 - markup=True (enable Rich markup)
│                 - auto_scroll=False (don't auto-scroll to bottom)
│
└─ Horizontal (#action-buttons, lines 213-215)
   ├─ Button ("Copy All", id="copy-all-btn", variant="primary")
   │   Handler: on_copy_all_pressed() (lines 364-389)
   │   Functionality: Copies both sections combined to clipboard
   │
   └─ Button ("Close", id="close-btn", variant="default")
       Handler: on_close_pressed() (line 415-417)
```

### 3. RichLog Widget Analysis

**RichLog Specifications (from Textual 7.5.0):**
- **Base Class:** Widget
- **Purpose:** Display read-only formatted logging output
- **Focusable:** YES (`can_focus=True`)
- **Selectable:** Technically YES (`allow_select=True` property), but BROKEN in practice
- **Text Selection Capabilities:**
  - ✗ NO mouse text selection (even outside scrollable containers)
  - ✗ NO keyboard text selection (Shift+Arrow keys don't work)
  - ✗ NO `selected_text` property
  - ✗ NO `get_text_range()` method
  - ✗ NO native copy support (Ctrl+C doesn't work)
- **Rich Markup Support:** ✓ YES - Supports Textual Rich markup (colors, styles, bold, etc.)
- **Line Operations:** ✓ YES - write(), write_line(), clear() methods
- **Container Interaction:** Not event-blocking like Static (VerticalScroll), but selection simply doesn't work

**Why RichLog Selection Doesn't Work:**
RichLog is designed for **display-only logging output**. Its `allow_select` property is architectural artifact, not functional. The widget:
1. Has `can_focus=True` to enable keyboard navigation (Tab, etc.)
2. Does NOT implement text selection handlers
3. Does NOT implement clipboard copy handlers
4. Is optimized for fast append operations, not interactive selection

### 4. Existing Copy Functionality

**Copy All Button (lines 364-389):**
- Handler: `on_copy_all_pressed(self) -> None`
- Functionality:
  ```
  1. Get staged context item count: self._get_staged_item_count()
  2. Get agent memory message count: len(self.conversation_history)
  3. Build combined content with headers and sections
  4. Call _copy_to_clipboard(combined_content, "All context")
  ```
- Output Format:
  ```
  ================================================================
  CONTEXT VIEWER SNAPSHOT
  Timestamp: YYYY-MM-DD HH:MM:SS
  ================================================================

  ===== STAGED CONTEXT (N items) =====
  [formatted staged context...]


  ===== AGENT MEMORY (M messages) =====
  [formatted conversation history...]
  ```

**Clipboard Mechanism (lines 391-412):**
- Uses `pyperclip` library
- Fallback if pyperclip unavailable: shows warning notification
- Shows user notification: "{section_name} copied to clipboard!" (3s timeout)

**Cached Formatting (lines 168-170, 220-232):**
- `_formatted_staged`: Cached formatted staged context (populated in `on_mount`)
- `_formatted_history`: Cached formatted conversation history (populated in `on_mount`)
- Purpose: Avoid re-formatting on every Copy All click

### 5. Text Formatting

**Staged Context Formatting (lines 254-284):**
- Header with metadata (if available):
  - Entry count: `[bold cyan]Log Entries:[/bold cyan] {entry_count}`
  - Log group: `[bold cyan]Log Group:[/bold cyan] {log_group}`
  - Size: `[bold cyan]Size:[/bold cyan] {chars:,} chars (~{tokens:,} tokens)`
- Separator: 50-character dashed line
- Empty state: Helpful message explaining when logs are staged

**Conversation History Formatting (lines 286-362):**
- System messages: `[bold cyan][System][/bold cyan] {content}`
- User messages: `[bold green][User][/bold green] {content}`
- Assistant messages: `[bold magenta][Assistant][/bold magenta] {content}`
  - Tool calls indented: `  [bold yellow][Tool Call][/bold yellow] {name}({args})`
- Tool results: `[bold blue][Tool Result][/bold blue] ({tool_id_short}) {content}`
- Messages separated by `\n\n`

### 6. CSS Styling

**Context Container (#context-container, lines 50-58):**
```css
#context-container {
    width: 90%;
    height: 85%;
    max-width: 120;
    background: $panel;
    border: thick $primary;
    padding: 0;
    layout: vertical;
}
```

**Collapsible Sections (lines 76-95):**
```css
Collapsible {
    width: 1fr;
    height: 1fr;
    margin: 0 0 1 0;
    border: solid $surface-darken-2;
}

Collapsible > CollapsibleTitle {
    background: $primary-darken-2;
    color: $text;
    padding: 0 1;
}

Collapsible > Contents {
    padding: 0;
    background: $panel;
    height: 1fr;
    max-height: 40;
}
```

**Scroll Containers (lines 98-102):**
```css
#staged-scroll, #memory-scroll {
    width: 1fr;
    height: 1fr;
    scrollbar-gutter: stable;
}
```

**RichLog Content (lines 104-112):**
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

---

## Root Cause Analysis

### Why Text Selection Doesn't Work in Context Viewer Modal

**The Problem:**
Users expect to be able to:
1. Click in a section (Staged Context or Agent Memory)
2. Drag to select text (triple-click to select line, etc.)
3. Copy selected text (Ctrl+C or mouse copy)
4. Paste into editor or share

**Current Behavior:**
- Click in section: Focus moves to RichLog (visual indicator)
- Mouse drag: Nothing happens (selection doesn't activate)
- Ctrl+C: Nothing happens (no selection to copy)
- Workaround: Click "Copy All" button

**Why RichLog Selection Fails:**

1. **RichLog Design Philosophy:**
   - Built for fast append operations (logging/monitoring)
   - Optimized for read-only display
   - NOT optimized for interactive text selection
   - `allow_select` property is non-functional (architectural artifact)

2. **Comparison: RichLog vs TextArea (text selection capability)**

| Feature | RichLog | TextArea | Static |
|---------|---------|----------|--------|
| Widget Purpose | Logging display | Text editing | Generic layout |
| Focusable | ✓ YES | ✓ YES | ✗ NO |
| Mouse Selection | ✗ NO | ✓ YES (full) | ✗ NO (blocked by container) |
| Keyboard Selection | ✗ NO | ✓ YES (Shift+Arrows, Ctrl+A) | ✗ NO |
| `selected_text` Property | ✗ NO | ✓ YES | ✗ NO |
| `get_text_range()` Method | ✗ NO | ✓ YES | ✗ NO |
| Native Copy (Ctrl+C) | ✗ NO | ✓ YES | ✗ NO |
| Rich Markup Support | ✓ YES | ✗ NO | ✓ YES |
| `read_only` Mode | N/A (always read-only) | ✓ YES (disables edit, keeps selection) | N/A |
| Container Event Interception | Not affected (no selection logic) | Works fine (selection active in all containers) | ✗ YES (blocked by VerticalScroll) |

3. **Technical Root Cause:**
   RichLog does not implement mouse/keyboard event handlers for text selection. It only implements:
   - Focus navigation (Tab, Shift+Tab)
   - Widget lifecycle (on_mount, on_blur, etc.)
   - Rendering pipeline

   It delegates ALL selection-related events to the underlying rendering engine, which has no support for tracking selection state.

### Comparison with Chat Window Issue

**Chat Window (Static in VerticalScroll):**
- Root Cause: Event interception by container
- Static widget HAS text selection logic (allow_select property)
- VerticalScroll intercepts mouse events for scrolling, preventing text selection events from reaching Static
- Fix: Replace Static with TextArea (which is selection-agnostic to container events)

**Context Modal (RichLog in VerticalScroll):**
- Root Cause: RichLog doesn't implement text selection logic at all
- RichLog widget lacks text selection logic (allow_select is non-functional)
- VerticalScroll is irrelevant - selection doesn't work in RichLog regardless of container
- Fix: Replace RichLog with TextArea (which implements full text selection logic)

---

## Solution Evaluation

### Option A: Replace RichLog with TextArea (read_only=True) ✓ RECOMMENDED

**Approach:**
1. Replace all `RichLog` widgets with `TextArea(read_only=True)`
2. Preprocess Rich markup in formatted content → plain text with ANSI codes
3. Enable syntax highlighting with appropriate language mode

**Pros:**
- ✓ Full mouse text selection support (click, drag, triple-click)
- ✓ Full keyboard text selection (Shift+Arrow keys, Ctrl+A, etc.)
- ✓ Native copy support (Ctrl+C works)
- ✓ Native text selection indicators (highlighting)
- ✓ Works in all containers (not affected by VerticalScroll)
- ✓ Consistent with chat window fix
- ✓ Battle-tested Textual pattern
- ✓ read_only mode prevents accidental editing while preserving selection
- ✓ Soft wrap support (same as RichLog's wrap=True)

**Cons:**
- ✗ Rich markup rendering lost (colors, styles, bold text)
- ✗ Some information density loss (ANSI codes less readable than colors)
- ✗ Requires preprocessing step to convert Rich markup to plain text
- ✗ Slightly higher memory usage (TextArea for display purposes)

**Markup Conversion Strategy:**
```
[bold cyan]Log Entries:[/bold cyan] 42  →  Log Entries: 42
[bold green][User][/bold green] Hello  →  [User] Hello
[bold magenta][Assistant][/bold magenta] Response  →  [Assistant] Response
```

Can use Textual's `strip_meta_escape` or simple regex to remove markup tags while preserving content.

**Implementation Complexity:** LOW-MEDIUM
- Time: 2-3 hours
- Risk: LOW (TextArea is standard widget, easily reversible)
- Testing: Unit tests + manual verification of selection behavior

---

### Option B: Keep RichLog + Add Section-Level Copy Buttons

**Approach:**
1. Keep RichLog widgets as-is
2. Add "Copy Section" buttons for Staged Context and Agent Memory sections
3. Users click button instead of selecting text

**Pros:**
- ✓ Preserves Rich markup rendering
- ✓ Simple to implement (just add buttons)
- ✓ Minimal code changes
- ✓ Familiar pattern (Copy All button already exists)

**Cons:**
- ✗ Doesn't solve selection problem (users still can't select/copy manually)
- ✗ Additional UI clutter (more buttons)
- ✗ Requires extra clicks (button click per section instead of Ctrl+A + Ctrl+C)
- ✗ Less intuitive (users expect text selection to work)
- ✗ Doesn't match user expectations from other text applications

**Why Not Recommended:**
This is a band-aid fix that doesn't address the root issue. Users will still be frustrated that they can't select text like in any other text viewer application.

---

### Option C: Hybrid Approach (TextArea for Content, Static for Headers)

**Approach:**
1. Keep Static headers (formatted metadata)
2. Replace RichLog with TextArea for content sections
3. Headers display Rich markup, content displays plain text with syntax highlighting

**Pros:**
- ✓ Partial Rich markup preservation (headers still formatted)
- ✓ Full text selection in content sections
- ✓ Cleaner visual separation

**Cons:**
- ✗ Inconsistent rendering (headers formatted, content plain)
- ✗ More complex implementation (manage two widget types)
- ✗ Headers still can't be selected or copied
- ✗ Doesn't match user expectations (why are some sections non-selectable?)

**Why Not Recommended:**
Adds complexity without sufficient benefit. Option A is cleaner and more complete.

---

## Recommended Solution: TextArea Replacement

### Implementation Details

**Step 1: Modify Context Viewer Screen (context_viewer.py)**

Replace in `compose()` method (lines 187-194 and 203-210):

**Before (RichLog):**
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

**After (TextArea):**
```python
with VerticalScroll(id="staged-scroll"):
    yield TextArea(
        id="staged-content",
        text="",  # Will be populated in on_mount
        read_only=True,
        soft_wrap=True,
        show_line_numbers=False,
        show_cursor=False,
    )
```

**Step 2: Update on_mount() Method (lines 217-243)**

Replace Rich markup with ANSI codes or plain text:

**Before:**
```python
async def on_mount(self) -> None:
    """Populate sections with content asynchronously."""
    try:
        staged_log = self.query_one("#staged-content", RichLog)
        formatted_staged = self._format_staged_context()
        staged_log.write(formatted_staged)  # RichLog.write() method
        staged_log.refresh()
        self._formatted_staged = formatted_staged
        # ...
```

**After:**
```python
async def on_mount(self) -> None:
    """Populate sections with content asynchronously."""
    try:
        staged_textarea = self.query_one("#staged-content", TextArea)
        formatted_staged = self._format_staged_context()
        # Remove Rich markup and convert to plain text
        clean_staged = self._strip_rich_markup(formatted_staged)
        staged_textarea.text = clean_staged  # TextArea.text property
        self._formatted_staged = formatted_staged
        # ...
```

**Step 3: Add Markup Stripping Utility (new method)**

```python
def _strip_rich_markup(self, text: str) -> str:
    """
    Remove Rich markup tags from text.

    Converts [bold cyan]text[/bold cyan] → text
    Removes all formatting but preserves content.

    Args:
        text: Text with Rich markup

    Returns:
        Plain text without markup
    """
    import re
    # Remove opening tags like [bold cyan], [bold], etc.
    text = re.sub(r'\[[\w\s\-]*\]', '', text)
    # Remove closing tags like [/bold], [/cyan], etc.
    text = re.sub(r'\[/[\w\s\-]*\]', '', text)
    return text
```

**Step 4: Import TextArea**

Add to imports (line 15):
```python
from textual.widgets import Button, Collapsible, RichLog, Static, TextArea
```

### Changes Summary

| File | Lines | Change | Reason |
|------|-------|--------|--------|
| context_viewer.py | 15 | Add TextArea to imports | Enable TextArea widget usage |
| context_viewer.py | 188-194 | Replace RichLog with TextArea (#staged-content) | Enable mouse/keyboard text selection |
| context_viewer.py | 204-210 | Replace RichLog with TextArea (#memory-content) | Enable mouse/keyboard text selection |
| context_viewer.py | 221-224 | Update on_mount for staged section | Use TextArea.text instead of RichLog.write |
| context_viewer.py | 228-231 | Update on_mount for memory section | Use TextArea.text instead of RichLog.write |
| context_viewer.py | NEW | Add _strip_rich_markup() method | Convert Rich markup to plain text |
| context_viewer.py | 364-389 | No changes needed to on_copy_all_pressed | Copy All button still works (uses formatted_staged/history) |

**Total Code Changes:** ~40 lines (similar to chat window fix)

### CSS Updates Needed

**Current CSS (lines 104-112) for RichLog:**
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

**Updated CSS for TextArea:**
```css
#staged-content, #memory-content {
    width: 100%;
    min-height: 20;
    height: 1fr;  /* TextArea needs explicit height */
    border: none;
    background: $panel;
    scrollbar-gutter: stable;
}

/* TextArea specific styling to match RichLog appearance */
#staged-content:focus, #memory-content:focus {
    border: solid $primary;  /* Show border on focus */
}
```

### Behavior Changes for Users

| Behavior | Before (RichLog) | After (TextArea) | Impact |
|----------|------------------|------------------|--------|
| Click in section | Focus moves to RichLog | Focus moves to TextArea | Same |
| Mouse drag to select | Nothing happens | Text gets selected (highlighted) | ✓ Fixed |
| Triple-click | Nothing happens | Entire line selected | ✓ New feature |
| Ctrl+A | Nothing happens | All text selected | ✓ New feature |
| Shift+Arrow keys | Nothing happens | Text selected from cursor | ✓ New feature |
| Ctrl+C | Nothing happens | Selected text copied | ✓ Fixed (with selection) |
| Rich markup colors | ✓ Visible (cyan, green, magenta, etc.) | ✗ Lost (plain text, but still readable) | Minor loss |
| Text wrapping | ✓ YES (wrap=True) | ✓ YES (soft_wrap=True) | Same |
| Copy All button | ✓ Works (preserves formatted content) | ✓ Works (uses cached formatted content) | Same |

---

## Testing Strategy

### Unit Tests to Add

**Test File:** `tests/unit/ui/screens/test_context_viewer_text_selection.py`

**Test Cases:**

1. **Basic Text Selection**
   ```python
   def test_textarea_allows_text_selection():
       """Verify TextArea widget supports text selection."""
       # Mount context viewer
       # Simulate mouse selection (drag from position X to Y)
       # Assert selected_text property contains expected text
   ```

2. **Copy Functionality**
   ```python
   def test_copy_all_button_copies_both_sections():
       """Verify Copy All button copies both sections to clipboard."""
       # Mount context viewer with test data
       # Click Copy All button
       # Assert clipboard contains both sections with headers
   ```

3. **Rich Markup Stripping**
   ```python
   def test_strip_rich_markup_removes_formatting():
       """Verify Rich markup is properly stripped from displayed content."""
       screen = ContextViewerScreen(...)
       marked_text = "[bold cyan]Log Entries:[/bold cyan] 42"
       clean_text = screen._strip_rich_markup(marked_text)
       assert clean_text == "Log Entries: 42"
   ```

4. **Keyboard Selection**
   ```python
   def test_keyboard_selection_with_shift_arrows():
       """Verify Shift+Arrow keys work for text selection."""
       # Mount context viewer
       # Simulate Shift+Right Arrow keys
       # Assert selected_text property updates
   ```

5. **Container Interaction**
   ```python
   def test_textarea_selection_works_in_vertical_scroll():
       """Verify TextArea selection works inside VerticalScroll container."""
       # Unlike Static widgets, TextArea should work fine in VerticalScroll
       # Mount context viewer with VerticalScroll container
       # Verify text selection works despite container
   ```

### Integration Tests to Update

**Files to Verify:**
- `tests/integration/test_context_modal_callback.py` - Verify modal still opens/closes
- `tests/integration/test_context_management_e2e.py` - Verify Copy All button still works

### Manual Testing Checklist

- [ ] Modal opens and displays without errors
- [ ] Staged Context section displays text
- [ ] Agent Memory section displays text
- [ ] Can click-drag to select text in Staged Context
- [ ] Can click-drag to select text in Agent Memory
- [ ] Triple-click selects entire line
- [ ] Ctrl+A selects all text in current section
- [ ] Shift+Arrow keys select text
- [ ] Ctrl+C copies selected text (paste to verify)
- [ ] Copy All button still works and copies both sections
- [ ] Close button dismisses modal
- [ ] Escape key dismisses modal
- [ ] Text wrapping still works (long lines break correctly)
- [ ] Collapsible sections still collapse/expand
- [ ] Modal scrolls when content exceeds viewport

---

## Risk Assessment

### Risk Level: LOW

**Why Low Risk:**
1. TextArea is a standard Textual widget (well-tested)
2. Similar to chat window fix (proven approach)
3. Easily reversible if issues arise
4. Copy All button unchanged (fallback if selection fails)
5. No breaking changes to API or data structures

### Potential Issues & Mitigations

| Issue | Probability | Mitigation |
|-------|-------------|-----------|
| TextArea memory overhead | Low | Monitor with large contexts, optimize if needed |
| Rich markup loss reduces readability | Medium | Test with users, may reconsider based on feedback |
| Keyboard shortcuts conflict | Low | TextArea bindings don't conflict with modal bindings |
| Selection performance lag with large text | Low | TextArea is optimized for text operations |
| CSS styling needs adjustment | Low | Update CSS rules for TextArea widget type |

### Rollback Plan

If issues arise after implementation:
1. Revert context_viewer.py to previous version (RichLog)
2. Users still have Copy All button as workaround
3. No database or state changes to revert

---

## Complexity & Effort Estimation

| Task | Effort | Priority |
|------|--------|----------|
| Modify context_viewer.py (replace RichLog with TextArea) | 1 hour | HIGH |
| Add _strip_rich_markup() utility method | 0.5 hours | HIGH |
| Update on_mount() for TextArea operations | 0.5 hours | HIGH |
| Update CSS for TextArea styling | 0.5 hours | MEDIUM |
| Add unit tests for text selection | 1.5 hours | HIGH |
| Manual testing & verification | 1 hour | HIGH |
| Documentation updates | 0.5 hours | LOW |
| **TOTAL** | **5.5 hours** | |

**Team Timeline (assuming dedicated work):**
- Single developer: 5-6 hours (with breaks)
- Two developers: 3-4 hours (parallel testing)
- AI agent: ~30 minutes (see: supercharged timelines)

---

## Next Steps

1. **Approval:** Confirm this approach aligns with project goals
2. **Implementation:** Modify context_viewer.py as outlined
3. **Testing:** Run unit tests and manual testing checklist
4. **Code Review:** Have team review changes
5. **Documentation:** Update user-facing docs about new selection features
6. **Deployment:** Release with chat window fix (combined improvement)

---

## Appendices

### A. Widget Comparison Matrix

| Aspect | Static | RichLog | TextArea |
|--------|--------|---------|----------|
| **Display** | | | |
| Base class | Widget | Widget | Widget |
| Read-only | YES | YES | YES (via read_only=True) |
| Editable | NO | NO | YES (via read_only=False) |
| **Text Selection** | | | |
| Mouse selection | ✗ (blocked by container) | ✗ (not implemented) | ✓ WORKS |
| Keyboard selection | ✗ (blocked by container) | ✗ (not implemented) | ✓ WORKS |
| selected_text property | ✗ | ✗ | ✓ YES |
| **Clipboard** | | | |
| Native copy (Ctrl+C) | ✗ | ✗ | ✓ YES |
| Programmatic copy | ✓ (via pyperclip) | ✓ (via pyperclip) | ✓ (via selection + Ctrl+C) |
| **Formatting** | | | |
| Rich markup | ✓ YES | ✓ YES | ✗ NO (plain text) |
| Syntax highlighting | ✗ NO | ✗ NO | ✓ YES (multiple languages) |
| **Container Behavior** | | | |
| Works in VerticalScroll | ✗ (event interception) | ✓ (but no selection) | ✓ WORKS |
| Works in Horizontal | ✓ YES | ✓ YES | ✓ YES |
| **Performance** | | | |
| Large text (10MB) | ✓ Good | ✓ Good | ⚠ Caution (investigate if needed) |
| Append operations | ✓ Good | ✓ Excellent | ⚠ Acceptable (not optimized for logging) |

### B. File References

**Main Implementation:**
- `/Users/David.Parker/src/observability-assistant/src/logai/ui/screens/context_viewer.py` (525 lines)

**Related Files (for context):**
- `/Users/David.Parker/src/observability-assistant/src/logai/ui/widgets/messages.py` (137 lines) - Chat window using Static (similar issue)
- `/Users/David.Parker/src/observability-assistant/src/logai/ui/screens/chat.py` (819 lines) - Chat screen container

**Test Files:**
- `/Users/David.Parker/src/observability-assistant/tests/integration/test_context_modal_callback.py`
- `/Users/David.Parker/src/observability-assistant/tests/integration/test_context_management_e2e.py`

**Styling:**
- `/Users/David.Parker/src/observability-assistant/src/logai/ui/styles/app.tcss` - Global CSS

### C. External References

**Textual Documentation:**
- TextArea widget: https://textual.textualize.io/widgets/text_area/
- RichLog widget: https://textual.textualize.io/widgets/rich_log/
- Text selection: https://textual.textualize.io/guide/input/#text-selection

---

**Investigation Complete:** February 20, 2026
**Recommendation:** Proceed with Option A (TextArea replacement)
**Next Action:** Await approval and implementation assignment
