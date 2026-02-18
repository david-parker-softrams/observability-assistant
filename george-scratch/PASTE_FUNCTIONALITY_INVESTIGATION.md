# Copy/Paste Functionality Investigation Report

## Executive Summary

The user cannot paste text from external applications into the LogAI TUI input box because **Textual uses an internal clipboard by default**, not the system clipboard. Text copied from external applications (browser, editor, etc.) is not accessible to the Textual app.

## Root Cause

### The Problem: Internal Clipboard Only

Textual maintains its own **internal clipboard** (`self.app.clipboard`) that only contains text copied within the Textual application itself. As documented in the Textual source code:

```python
@property
def clipboard(self) -> str:
    """The value of the local clipboard.

    Note, that this only contains text copied in the app, and not
    text copied from elsewhere in the OS.
    """
    return self._clipboard
```

When a user:
1. Copies text from an external app (e.g., browser, VS Code)
2. Tries to paste into LogAI with `Ctrl+V`
3. The paste action executes but reads from Textual's empty internal clipboard
4. Result: Nothing is pasted

### How Textual's Clipboard Works

**Internal Operations (Currently Working):**
- `Ctrl+C` / `Cmd+C`: Copy selected text within Textual → internal clipboard
- `Ctrl+X`: Cut selected text within Textual → internal clipboard
- `Ctrl+V`: Paste from internal clipboard

**System Clipboard Operations (Not Working):**
- Text copied from outside Textual is NOT accessible
- Text copied within Textual is NOT copied to system clipboard (by default)

### Why This Happens

Textual cannot directly access the system clipboard because:
1. Terminal applications run in a sandboxed environment
2. Direct OS clipboard access would require platform-specific code (macOS, Windows, Linux)
3. Different terminals handle clipboard differently
4. Security and portability concerns

## The Solution: OSC 52 Escape Sequences

### What is OSC 52?

OSC 52 (Operating System Command 52) is a terminal escape sequence that allows terminal applications to interact with the system clipboard. Modern terminal emulators support this.

### Current Implementation Status

**Writing to System Clipboard (Already Implemented):**
Textual already has `copy_to_clipboard()` method that uses OSC 52:

```python
def copy_to_clipboard(self, text: str) -> None:
    """Copy text to the clipboard.

    !!! note

        This does not work on macOS Terminal, but will work on most other terminals.

    Args:
        text: Text you wish to copy to the clipboard.
    """
    self._clipboard = text
    if self._driver is None:
        return
    import base64

    base64_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    self._driver.write(f"\x1b]52;c;{base64_text}\a")
```

**Reading from System Clipboard (NOT Implemented):**
- Textual does NOT currently read from the system clipboard
- The `action_paste()` only reads from internal clipboard
- This is the core issue

## Terminal Support for OSC 52

### Supported Terminals ✅
- **iTerm2** (macOS) - Full support
- **kitty** - Full support
- **WezTerm** - Full support
- **Windows Terminal** - Full support
- **Alacritty** - Full support
- **tmux** (with proper config) - Full support
- **VS Code integrated terminal** - Partial support

### Limited/No Support ❌
- **macOS Terminal.app** - OSC 52 write only (can't read)
- **Some older terminal emulators**

## Keyboard Shortcuts Summary

### Currently Working in LogAI
| Shortcut | Action | Works? | Notes |
|----------|--------|--------|-------|
| `Ctrl+V` | Paste from internal clipboard | ✅ | Only pastes text copied within LogAI |
| `Ctrl+C` | ~~Copy~~ / **Quit App** | ❌ | App binding overrides copy action! |
| `Cmd+C` | Copy (macOS) | ✅ | To internal clipboard only |
| `Ctrl+X` | Cut | ✅ | To internal clipboard only |

### Additional Issue: Ctrl+C Binding Conflict

In `src/logai/ui/app.py:27`:
```python
Binding("ctrl+c", "quit", "Quit", priority=True),
```

This **priority binding** overrides the Input widget's `Ctrl+C` copy action, preventing users from copying text with `Ctrl+C`.

## Recommended Solutions

### Option 1: Use Terminal's Native Paste (Recommended for MVP)

**No code changes needed!** Document that users should use their terminal's native paste:

**For Most Terminals:**
- Right-click in the input field → Paste
- Terminal menu → Edit → Paste

**For iTerm2/kitty/WezTerm:**
- `Cmd+V` should work (bypasses Textual and sends paste directly)

**Pros:**
- Zero implementation effort
- Works immediately
- Familiar to terminal users

**Cons:**
- Not intuitive for users expecting `Ctrl+V`
- Different across terminals
- Requires user documentation

### Option 2: Implement Bracketed Paste Mode (Recommended for Long-term)

Textual already enables bracketed paste mode, which means the terminal sends paste events. We need to:

1. **Handle the Paste Event to Use System Clipboard**

Create a custom Input widget that reads from system clipboard on paste:

```python
# In src/logai/ui/widgets/input_box.py

from textual.widgets import Input
from textual import events

class ChatInput(Input):
    """Enhanced input widget with system clipboard support."""

    def _on_paste(self, event: events.Paste) -> None:
        """Handle paste event with system clipboard text."""
        # event.text contains the actual pasted text from the system clipboard!
        # This is sent by the terminal via bracketed paste mode
        if event.text:
            start, end = self.selection
            self.replace(event.text, start, end)
            event.prevent_default()  # Prevent default handling
```

**Wait - Actually Check Current Implementation:**

Looking at the current `ChatInput` in `input_box.py:6-46`, it simply extends `Input` without overriding paste behavior. The base `Input` class should already handle paste events correctly via bracketed paste mode!

**This means the paste functionality SHOULD already work if:**
1. The terminal supports bracketed paste mode (most modern terminals do)
2. The user uses the terminal's paste command (Cmd+V on Mac, Ctrl+Shift+V on Linux)

### Option 3: Fix the Ctrl+C Binding Conflict

The app-level `Ctrl+C` binding is blocking the copy functionality. Consider:

1. **Remove priority flag:**
```python
# In src/logai/ui/app.py
Binding("ctrl+c", "quit", "Quit", priority=False),  # Changed from True
```

2. **Or use a different quit shortcut:**
```python
Binding("ctrl+q", "quit", "Quit"),  # Common alternative
```

This would allow `Ctrl+C` to work for copying text in the input field.

## Testing Required

To verify paste functionality:

1. **Test with bracketed paste:**
   - Copy text from browser
   - Use `Cmd+V` (Mac) or `Ctrl+Shift+V` (Linux) in LogAI input
   - Check if text appears

2. **Test terminal compatibility:**
   - iTerm2 (Mac)
   - Terminal.app (Mac)
   - Windows Terminal
   - VS Code terminal

3. **Test the Ctrl+C conflict:**
   - Try selecting text in input and pressing `Ctrl+C`
   - Currently quits the app instead of copying

## Implementation Recommendation

### Immediate (Next Sprint):

1. **Add user documentation** explaining paste shortcuts:
   ```markdown
   ## Copy/Paste in LogAI

   To paste text into LogAI:
   - **Mac**: Use Cmd+V or right-click → Paste
   - **Linux**: Use Ctrl+Shift+V or right-click → Paste
   - **Windows**: Use Ctrl+V or right-click → Paste

   Note: Ctrl+V may not work in all terminals. Use your terminal's
   native paste command if needed.
   ```

2. **Fix the Ctrl+C conflict** - Change to `Ctrl+Q` for quit:
   ```python
   # src/logai/ui/app.py
   BINDINGS = [
       Binding("ctrl+q", "quit", "Quit", priority=True),  # Changed from ctrl+c
   ]
   ```

3. **Update the input placeholder** to show quit shortcut:
   ```python
   # src/logai/ui/widgets/input_box.py
   super().__init__(
       placeholder="Type your message (Enter to send, Ctrl+Q to quit)..."
   )
   ```

### Medium-term Enhancement:

Investigate if we need custom paste handling, or if the current implementation already works correctly with bracketed paste mode. **Hypothesis: It may already work!**

Test this hypothesis by:
1. Running LogAI in iTerm2
2. Copying text from browser
3. Pressing `Cmd+V` (not `Ctrl+V`)
4. See if text appears

## Code Changes Needed

### Change 1: Fix Quit Shortcut
**File:** `src/logai/ui/app.py:27`

```python
# Before
Binding("ctrl+c", "quit", "Quit", priority=True),

# After
Binding("ctrl+q", "quit", "Quit", priority=True),
```

### Change 2: Update Input Placeholder
**File:** `src/logai/ui/widgets/input_box.py:20`

```python
# Before
super().__init__(placeholder="Type your message (Enter to send, Ctrl+C to quit)...")

# After
super().__init__(placeholder="Type your message (Enter to send, Ctrl+Q to quit)...")
```

### Change 3: Add System Message on Startup
**File:** `src/logai/ui/screens/chat.py:172-177`

```python
# Add after welcome message
welcome = SystemMessage(
    "Welcome to LogAI! Ask me about your AWS CloudWatch logs.\n"
    "Type /help for available commands.\n"
    "Tip: Use Cmd+V (Mac) or Ctrl+Shift+V (Linux) to paste."
)
```

## Terminal Requirements

For paste to work, the terminal must support:
1. **Bracketed Paste Mode** - Most modern terminals ✅
2. **OSC 52** (for advanced clipboard integration) - Many modern terminals ✅

**Widely Supported Terminals:**
- iTerm2, kitty, WezTerm, Windows Terminal, Alacritty, tmux

**Limited Support:**
- macOS Terminal.app (bracketed paste works, OSC 52 limited)

## Conclusion

**Root Cause:** Textual uses an internal clipboard. System clipboard paste requires terminal support for bracketed paste mode.

**Good News:** Most modern terminals already support this, and LogAI likely already supports paste via terminal native shortcuts (Cmd+V on Mac).

**Action Items:**
1. Test paste with `Cmd+V` in iTerm2/modern terminals
2. Fix the `Ctrl+C` → `Ctrl+Q` conflict
3. Update documentation with paste instructions
4. Add startup tip about paste shortcuts

**No major code changes needed** - primarily documentation and fixing the quit shortcut conflict.
