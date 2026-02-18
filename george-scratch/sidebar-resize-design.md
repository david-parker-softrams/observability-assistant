# Sidebar Resize Keyboard Shortcuts - Design Document

**Author**: Saanvi (Senior Software Architect)
**Date**: February 12, 2026
**Status**: Ready for Implementation
**Version**: 1.0
**Phase**: 1 (keyboard shortcuts only; Phase 2 will add config persistence)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Proposed Keyboard Shortcuts](#3-proposed-keyboard-shortcuts)
4. [Technical Architecture](#4-technical-architecture)
5. [Implementation Details](#5-implementation-details)
6. [Visual Feedback System](#6-visual-feedback-system)
7. [Edge Cases & Considerations](#7-edge-cases--considerations)
8. [Files to Modify](#8-files-to-modify)
9. [Testing Strategy](#9-testing-strategy)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. Executive Summary

### Feature Overview

Add keyboard shortcuts to dynamically resize both sidebars in the LogAI TUI:
- **Left sidebar**: `LogGroupsSidebar` (displays CloudWatch log groups)
- **Right sidebar**: `ToolCallsSidebar` (displays agent tool calls)

### User Value

| Problem | Solution |
|---------|----------|
| Sidebar widths are fixed at 28 columns | Users can resize to fit their needs |
| Different content needs different widths | Wider for long log group names, narrower for simple tool lists |
| Screen real estate varies by terminal | Users can optimize layout for their terminal size |
| No way to adjust without code changes | Intuitive keyboard shortcuts for instant adjustment |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Discrete steps (not pixel-drag)** | Consistent with TUI paradigm; easier to implement; keyboard-friendly |
| **Step sizes: 24→26→28→30→32→35** | Respects existing min/max constraints; 6 discrete positions |
| **Separate controls per sidebar** | Users may want left wide, right narrow (or vice versa) |
| **Visual feedback via toast/status** | Confirms resize action; shows current width |
| **No mouse resize (Phase 1)** | Keeps scope manageable; can add in future phase |

---

## 2. Current State Analysis

### Existing Sidebar Dimensions

Both sidebars currently define the same constraints in their `DEFAULT_CSS`:

```python
# LogGroupsSidebar (left)
width: 28;
min-width: 24;
max-width: 35;

# ToolCallsSidebar (right)
width: 28;
min-width: 24;
max-width: 35;
```

### Current Key Bindings

From `app.py`:
```python
BINDINGS = [
    Binding("ctrl+c", "quit", "Quit", priority=True),
    Binding("ctrl+q", "quit", "Quit"),
]
```

No sidebar-related key bindings exist currently. The `/logs` and `/tools` commands toggle visibility but don't resize.

### Textual Framework Capabilities

Textual v7.5.0 supports:
- `Binding()` for key bindings with descriptions
- `action_*` methods for handling bound keys
- `widget.styles.width` for dynamic width changes
- Reactive properties for auto-refresh on changes
- Toast notifications via `self.notify()` for visual feedback

---

## 3. Proposed Keyboard Shortcuts

### Primary Recommendation: Bracket Keys

| Action | Key Binding | Rationale |
|--------|-------------|-----------|
| **Shrink left sidebar** | `ctrl+[` | `[` visually suggests "left"; Ctrl modifier avoids conflicts |
| **Expand left sidebar** | `ctrl+]` | `]` pairs with `[`; intuitive expand direction |
| **Shrink right sidebar** | `ctrl+shift+[` or `alt+[` | Shift/Alt modifier distinguishes from left sidebar |
| **Expand right sidebar** | `ctrl+shift+]` or `alt+]` | Consistent pairing |

### Alternative Options Considered

| Option | Keys | Pros | Cons |
|--------|------|------|------|
| **Arrow keys** | `ctrl+left/right` | Intuitive direction | May conflict with text editing |
| **H/L keys (vim-style)** | `ctrl+h/l` | Familiar to vim users | Not intuitive for non-vim users |
| **Number keys** | `1-6` for sizes | Direct size selection | Uses too many keys; not intuitive |
| **Plus/Minus** | `ctrl++/-` | Universal resize convention | Hard to distinguish left vs right |

### Recommended Final Bindings

After analyzing terminal compatibility and ergonomics:

```python
BINDINGS = [
    # Left sidebar (Log Groups)
    Binding("ctrl+left", "shrink_left_sidebar", "Shrink Logs", show=False),
    Binding("ctrl+right", "expand_left_sidebar", "Expand Logs", show=False),

    # Right sidebar (Tool Calls)
    Binding("ctrl+shift+left", "shrink_right_sidebar", "Shrink Tools", show=False),
    Binding("ctrl+shift+right", "expand_right_sidebar", "Expand Tools", show=False),
]
```

**Rationale for Arrow Keys**:
1. **Directional intuition**: Left arrow = shrink (less space), Right arrow = expand (more space)
2. **Modifier distinction**: Ctrl = left sidebar, Ctrl+Shift = right sidebar
3. **Discoverability**: Arrow keys are universal; users will try them
4. **Terminal compatibility**: Works in most terminal emulators

**Alternative if Arrow Keys Conflict**:
```python
# Fallback using bracket keys
Binding("ctrl+[", "shrink_left_sidebar", "Shrink Logs"),
Binding("ctrl+]", "expand_left_sidebar", "Expand Logs"),
Binding("alt+[", "shrink_right_sidebar", "Shrink Tools"),
Binding("alt+]", "expand_right_sidebar", "Expand Tools"),
```

---

## 4. Technical Architecture

### 4.1 Width Step Configuration

Define discrete width steps that respect min/max constraints:

```python
# Constants for sidebar resize
SIDEBAR_WIDTH_STEPS = [24, 26, 28, 30, 32, 35]  # Min to max in discrete steps
DEFAULT_SIDEBAR_WIDTH = 28  # Current default
```

**Step rationale**:
- **24**: Minimum - compact view, may truncate content
- **26**: Slightly more room
- **28**: Default - balanced for most content
- **30**: Comfortable width for medium content
- **32**: Wide - shows more detail
- **35**: Maximum - full detail, takes significant screen space

### 4.2 State Management

Sidebar widths will be managed in `ChatScreen`:

```python
class ChatScreen(Screen[None]):
    def __init__(self, ...):
        # ... existing init ...

        # Sidebar width state (indexes into SIDEBAR_WIDTH_STEPS)
        self._left_sidebar_width_index: int = 2   # 28 (default)
        self._right_sidebar_width_index: int = 2  # 28 (default)
```

### 4.3 Component Interaction

```
┌─────────────────┐     key press      ┌─────────────────┐
│   User presses  │ ─────────────────► │   ChatScreen    │
│   Ctrl+Right    │                    │  action_expand_ │
└─────────────────┘                    │  left_sidebar() │
                                       └────────┬────────┘
                                                │
                                                │ update styles.width
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │ LogGroupsSidebar│
                                       │ (width changes) │
                                       └────────┬────────┘
                                                │
                                                │ notify()
                                                ▼
                                       ┌─────────────────┐
                                       │  Toast/Status   │
                                       │  "Logs: 30 cols"│
                                       └─────────────────┘
```

### 4.4 Width Update Flow

```python
def _resize_sidebar(
    self,
    sidebar_id: str,
    direction: Literal["expand", "shrink"]
) -> bool:
    """
    Resize a sidebar by one step.

    Args:
        sidebar_id: "left" or "right"
        direction: "expand" or "shrink"

    Returns:
        True if resize occurred, False if at limit
    """
    # Get current index
    if sidebar_id == "left":
        current_index = self._left_sidebar_width_index
        sidebar = self._log_groups_sidebar
    else:
        current_index = self._right_sidebar_width_index
        sidebar = self._tool_sidebar

    # Calculate new index
    if direction == "expand":
        new_index = min(current_index + 1, len(SIDEBAR_WIDTH_STEPS) - 1)
    else:
        new_index = max(current_index - 1, 0)

    # Check if change occurred
    if new_index == current_index:
        return False  # At limit

    # Update state
    if sidebar_id == "left":
        self._left_sidebar_width_index = new_index
    else:
        self._right_sidebar_width_index = new_index

    # Apply new width
    new_width = SIDEBAR_WIDTH_STEPS[new_index]
    if sidebar and sidebar.display:
        sidebar.styles.width = new_width

    return True
```

---

## 5. Implementation Details

### 5.1 Key Binding Registration

Add bindings to `ChatScreen` (not `LogAIApp`) since the sidebars are owned by the screen:

```python
class ChatScreen(Screen[None]):
    """Main chat screen with resizable sidebars."""

    BINDINGS = [
        # Left sidebar resize
        Binding("ctrl+left", "shrink_left_sidebar", "Shrink left sidebar", show=False),
        Binding("ctrl+right", "expand_left_sidebar", "Expand left sidebar", show=False),

        # Right sidebar resize
        Binding("ctrl+shift+left", "shrink_right_sidebar", "Shrink right sidebar", show=False),
        Binding("ctrl+shift+right", "expand_right_sidebar", "Expand right sidebar", show=False),
    ]
```

**Note**: `show=False` hides these from the default footer since they're discoverable via `/help`.

### 5.2 Action Methods

```python
def action_shrink_left_sidebar(self) -> None:
    """Shrink the left (log groups) sidebar."""
    if not self._log_groups_sidebar_visible:
        self.notify("Log groups sidebar is hidden", severity="warning")
        return

    if self._resize_sidebar("left", "shrink"):
        width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
        self.notify(f"Log groups: {width} columns")
    else:
        self.notify("Log groups sidebar at minimum width", severity="warning")

def action_expand_left_sidebar(self) -> None:
    """Expand the left (log groups) sidebar."""
    if not self._log_groups_sidebar_visible:
        self.notify("Log groups sidebar is hidden", severity="warning")
        return

    if self._resize_sidebar("left", "expand"):
        width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
        self.notify(f"Log groups: {width} columns")
    else:
        self.notify("Log groups sidebar at maximum width", severity="warning")

def action_shrink_right_sidebar(self) -> None:
    """Shrink the right (tool calls) sidebar."""
    if not self._tool_sidebar_visible:
        self.notify("Tool calls sidebar is hidden", severity="warning")
        return

    if self._resize_sidebar("right", "shrink"):
        width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
        self.notify(f"Tool calls: {width} columns")
    else:
        self.notify("Tool calls sidebar at minimum width", severity="warning")

def action_expand_right_sidebar(self) -> None:
    """Expand the right (tool calls) sidebar."""
    if not self._tool_sidebar_visible:
        self.notify("Tool calls sidebar is hidden", severity="warning")
        return

    if self._resize_sidebar("right", "expand"):
        width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
        self.notify(f"Tool calls: {width} columns")
    else:
        self.notify("Tool calls sidebar at maximum width", severity="warning")
```

### 5.3 Core Resize Logic

```python
# Constants at module level
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28

def _resize_sidebar(
    self,
    sidebar_id: Literal["left", "right"],
    direction: Literal["expand", "shrink"]
) -> bool:
    """
    Resize a sidebar by one step in the given direction.

    Args:
        sidebar_id: Which sidebar to resize
        direction: Direction to resize

    Returns:
        True if resize happened, False if already at limit
    """
    # Get current state
    if sidebar_id == "left":
        current_index = self._left_sidebar_width_index
        sidebar = self._log_groups_sidebar
    else:
        current_index = self._right_sidebar_width_index
        sidebar = self._tool_sidebar

    # Calculate new index
    max_index = len(SIDEBAR_WIDTH_STEPS) - 1
    if direction == "expand":
        new_index = min(current_index + 1, max_index)
    else:  # shrink
        new_index = max(current_index - 1, 0)

    # Check if at limit
    if new_index == current_index:
        return False

    # Update state
    if sidebar_id == "left":
        self._left_sidebar_width_index = new_index
    else:
        self._right_sidebar_width_index = new_index

    # Apply width to widget
    new_width = SIDEBAR_WIDTH_STEPS[new_index]
    if sidebar:
        sidebar.styles.width = new_width

    return True
```

### 5.4 Width Restoration on Toggle

When a sidebar is hidden and re-shown, it should restore its last width:

```python
def toggle_sidebar(self) -> None:
    """Toggle the tools sidebar visibility."""
    self._tool_sidebar_visible = not self._tool_sidebar_visible

    if self._tool_sidebar:
        self._tool_sidebar.display = self._tool_sidebar_visible

        if self._tool_sidebar_visible:
            # Restore saved width
            width = SIDEBAR_WIDTH_STEPS[self._right_sidebar_width_index]
            self._tool_sidebar.styles.width = width

            # Refresh display when showing
            for record in self._recent_tool_calls:
                self._tool_sidebar.update_tool_call(record)

def toggle_log_groups_sidebar(self) -> None:
    """Toggle the log groups sidebar visibility."""
    self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible

    if self._log_groups_sidebar:
        self._log_groups_sidebar.display = self._log_groups_sidebar_visible

        if self._log_groups_sidebar_visible:
            # Restore saved width
            width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
            self._log_groups_sidebar.styles.width = width

            # Refresh display
            self._log_groups_sidebar.refresh_display()
```

---

## 6. Visual Feedback System

### 6.1 Toast Notifications

Use Textual's built-in `notify()` for transient feedback:

```python
# Success feedback
self.notify(f"Log groups: {width} columns")

# At-limit warning
self.notify("Log groups sidebar at minimum width", severity="warning")

# Hidden sidebar warning
self.notify("Log groups sidebar is hidden", severity="warning")
```

Toast notifications:
- Auto-dismiss after ~3 seconds
- Stack if multiple appear
- Don't interrupt workflow
- Provide clear feedback

### 6.2 Help Text Update

Update the `/help` command to document the new shortcuts:

```python
def _show_help(self) -> str:
    """Show help message with available commands."""
    return """[bold]Available Commands:[/bold]

[cyan]/help[/cyan] - Show this help message
[cyan]/clear[/cyan] - Clear conversation history
[cyan]/refresh[/cyan] - Refresh the log groups list from AWS
[cyan]/logs[/cyan] - Toggle log groups sidebar (left)
[cyan]/tools[/cyan] - Toggle tool calls sidebar (right)
[cyan]/cache status[/cyan] - Show cache statistics
[cyan]/cache clear[/cyan] - Clear the cache
[cyan]/model[/cyan] - Show current LLM model
[cyan]/config[/cyan] - Show current configuration
[cyan]/quit[/cyan] or [cyan]/exit[/cyan] - Exit the application (or use Ctrl+C)

[bold]Keyboard Shortcuts:[/bold]
[cyan]Ctrl+Left/Right[/cyan] - Resize log groups sidebar (left)
[cyan]Ctrl+Shift+Left/Right[/cyan] - Resize tool calls sidebar (right)

[bold]Usage Tips:[/bold]
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
- Log groups are pre-loaded at startup - use /refresh to update
- Responses are streamed in real-time
- PII sanitization is enabled by default
"""
```

### 6.3 Status Bar Enhancement (Optional)

For additional visibility, the status bar could show current sidebar widths:

```
Status: Ready | Cache: 5 hits (83%) | Logs: 30 | Tools: 28 | Model: claude-3.5
```

**Note**: This is optional for Phase 1. Can be added if users request persistent width indicators.

---

## 7. Edge Cases & Considerations

### 7.1 Hidden Sidebar Resize Attempt

**Scenario**: User presses Ctrl+Right when log groups sidebar is hidden.

**Handling**:
```python
if not self._log_groups_sidebar_visible:
    self.notify("Log groups sidebar is hidden. Use /logs to show it.", severity="warning")
    return
```

**Rationale**: Don't silently ignore; inform user what to do.

### 7.2 Terminal Too Narrow for Both Sidebars

**Scenario**: User expands both sidebars to 35 cols each (70 cols total) on a 100-col terminal.

**Handling**: Let Textual's layout handle overflow. The main content area will shrink but remain functional. Both sidebars are docked, so they take priority.

**Future Enhancement**: Add logic to prevent total sidebar width exceeding 60% of terminal width.

### 7.3 Resize During Streaming Response

**Scenario**: User resizes sidebar while LLM response is streaming.

**Handling**: This should work fine. Textual re-renders on style changes. No special handling needed.

### 7.4 Key Binding Conflicts

**Scenario**: Ctrl+Left/Right may conflict with text editing in the input field.

**Testing Required**: Verify that:
1. When input is focused, Ctrl+Left/Right may move cursor by word
2. When input is not focused, they resize sidebar

**Mitigation**: If conflicts occur, use bracket keys instead or add `priority=True` to bindings.

### 7.5 Width Persistence Across Toggles

**Scenario**: User sets width to 32, hides sidebar, shows it again.

**Handling**: Width state is preserved in `_left_sidebar_width_index` and `_right_sidebar_width_index`. The `toggle_*` methods restore the saved width.

### 7.6 Initial Width on Mount

**Scenario**: App starts with sidebars at default width.

**Handling**: The CSS `width: 28` handles initial render. The `_*_width_index` variables start at `2` (index of 28) to match.

---

## 8. Files to Modify

### 8.1 Primary Changes

| File | Changes |
|------|---------|
| `src/logai/ui/screens/chat.py` | Add BINDINGS, action methods, resize logic, state variables |
| `src/logai/ui/commands.py` | Update help text with new keyboard shortcuts |

### 8.2 No Changes Required

| File | Reason |
|------|--------|
| `src/logai/ui/widgets/log_groups_sidebar.py` | Width controlled via `styles.width` from parent |
| `src/logai/ui/widgets/tool_sidebar.py` | Width controlled via `styles.width` from parent |
| `src/logai/ui/styles/app.tcss` | No CSS changes needed; dynamic styles override |
| `src/logai/ui/app.py` | Bindings are screen-level, not app-level |

### 8.3 Detailed Change Specification

#### `src/logai/ui/screens/chat.py`

**Add imports**:
```python
from typing import Literal
from textual.binding import Binding
```

**Add module-level constants** (after imports):
```python
# Sidebar resize configuration
SIDEBAR_WIDTH_STEPS: list[int] = [24, 26, 28, 30, 32, 35]
DEFAULT_SIDEBAR_WIDTH_INDEX: int = 2  # Index of 28 (default)
```

**Add class-level BINDINGS**:
```python
class ChatScreen(Screen[None]):
    """Main chat screen."""

    BINDINGS = [
        Binding("ctrl+left", "shrink_left_sidebar", "Shrink left sidebar", show=False),
        Binding("ctrl+right", "expand_left_sidebar", "Expand left sidebar", show=False),
        Binding("ctrl+shift+left", "shrink_right_sidebar", "Shrink right sidebar", show=False),
        Binding("ctrl+shift+right", "expand_right_sidebar", "Expand right sidebar", show=False),
    ]

    # ... rest of DEFAULT_CSS ...
```

**Add instance variables in `__init__`**:
```python
def __init__(self, ...):
    # ... existing init ...

    # Sidebar width state (indexes into SIDEBAR_WIDTH_STEPS)
    self._left_sidebar_width_index: int = DEFAULT_SIDEBAR_WIDTH_INDEX
    self._right_sidebar_width_index: int = DEFAULT_SIDEBAR_WIDTH_INDEX
```

**Add new methods** (before `on_tool_call`):
```python
# Sidebar resize methods
def _resize_sidebar(
    self,
    sidebar_id: Literal["left", "right"],
    direction: Literal["expand", "shrink"]
) -> bool:
    """..."""
    # Implementation as shown in section 5.3

def action_shrink_left_sidebar(self) -> None:
    """..."""
    # Implementation as shown in section 5.2

def action_expand_left_sidebar(self) -> None:
    """..."""

def action_shrink_right_sidebar(self) -> None:
    """..."""

def action_expand_right_sidebar(self) -> None:
    """..."""
```

**Modify `toggle_sidebar`** and **`toggle_log_groups_sidebar`**:
- Add width restoration logic as shown in section 5.4

#### `src/logai/ui/commands.py`

**Modify `_show_help`**:
- Add keyboard shortcuts section as shown in section 6.2

---

## 9. Testing Strategy

### 9.1 Unit Tests

**File**: `tests/unit/ui/screens/test_chat_resize.py`

```python
import pytest
from logai.ui.screens.chat import (
    ChatScreen,
    SIDEBAR_WIDTH_STEPS,
    DEFAULT_SIDEBAR_WIDTH_INDEX
)


class TestSidebarResize:
    """Tests for sidebar resize functionality."""

    def test_width_steps_valid(self):
        """Width steps should be sorted and within bounds."""
        assert SIDEBAR_WIDTH_STEPS == sorted(SIDEBAR_WIDTH_STEPS)
        assert SIDEBAR_WIDTH_STEPS[0] >= 24  # min-width
        assert SIDEBAR_WIDTH_STEPS[-1] <= 35  # max-width

    def test_default_index_valid(self):
        """Default index should point to 28."""
        assert SIDEBAR_WIDTH_STEPS[DEFAULT_SIDEBAR_WIDTH_INDEX] == 28

    def test_resize_expands_from_default(self):
        """Expanding from default should increase width."""
        # Requires mocked ChatScreen
        pass

    def test_resize_shrinks_from_default(self):
        """Shrinking from default should decrease width."""
        pass

    def test_resize_stops_at_max(self):
        """Cannot expand beyond maximum width."""
        pass

    def test_resize_stops_at_min(self):
        """Cannot shrink below minimum width."""
        pass

    def test_resize_hidden_sidebar_warns(self):
        """Resizing hidden sidebar should show warning."""
        pass
```

### 9.2 Integration Tests

**File**: `tests/integration/ui/test_sidebar_resize_integration.py`

```python
import pytest
from textual.pilot import Pilot


class TestSidebarResizeIntegration:
    """Integration tests for sidebar resize with full app."""

    @pytest.mark.asyncio
    async def test_ctrl_right_expands_left_sidebar(self, app):
        """Ctrl+Right should expand left sidebar."""
        async with app.run_test() as pilot:
            sidebar = app.query_one("#log-groups-sidebar")
            initial_width = sidebar.styles.width

            await pilot.press("ctrl+right")

            # Width should have increased
            assert sidebar.styles.width > initial_width

    @pytest.mark.asyncio
    async def test_ctrl_left_shrinks_left_sidebar(self, app):
        """Ctrl+Left should shrink left sidebar."""
        pass

    @pytest.mark.asyncio
    async def test_keyboard_shortcuts_show_toast(self, app):
        """Resize actions should show toast notification."""
        pass
```

### 9.3 Manual Testing Checklist

| Test Case | Steps | Expected Result |
|-----------|-------|-----------------|
| **Expand left sidebar** | Press Ctrl+Right | Left sidebar expands, toast shows new width |
| **Shrink left sidebar** | Press Ctrl+Left | Left sidebar shrinks, toast shows new width |
| **Expand right sidebar** | Press Ctrl+Shift+Right | Right sidebar expands |
| **Shrink right sidebar** | Press Ctrl+Shift+Left | Right sidebar shrinks |
| **At maximum** | Expand to 35, press expand again | Toast: "at maximum width" |
| **At minimum** | Shrink to 24, press shrink again | Toast: "at minimum width" |
| **Hidden sidebar** | Hide left sidebar, press Ctrl+Right | Toast: "sidebar is hidden" |
| **Width preserved** | Resize to 30, toggle off, toggle on | Width restored to 30 |
| **Help text** | Type /help | Shows new keyboard shortcuts |
| **Both sidebars** | Expand both to max | Chat area shrinks but remains usable |
| **During streaming** | Resize while response streams | No crash, resize works |

### 9.4 Terminal Compatibility Testing

Test on:
- [ ] macOS Terminal.app
- [ ] iTerm2
- [ ] VS Code integrated terminal
- [ ] Linux (gnome-terminal, konsole)
- [ ] Windows Terminal (if applicable)

Verify Ctrl+Arrow keys work as expected in each.

---

## 10. Implementation Checklist

### For Jackie (Developer)

```markdown
## Phase 1 Implementation Checklist

### Setup
- [ ] Read this design document fully
- [ ] Understand current sidebar implementation in chat.py

### Code Changes

#### chat.py
- [ ] Add `from typing import Literal` import
- [ ] Add `from textual.binding import Binding` import
- [ ] Add `SIDEBAR_WIDTH_STEPS` constant
- [ ] Add `DEFAULT_SIDEBAR_WIDTH_INDEX` constant
- [ ] Add `BINDINGS` class attribute with 4 bindings
- [ ] Add `_left_sidebar_width_index` instance variable
- [ ] Add `_right_sidebar_width_index` instance variable
- [ ] Implement `_resize_sidebar()` method
- [ ] Implement `action_shrink_left_sidebar()` method
- [ ] Implement `action_expand_left_sidebar()` method
- [ ] Implement `action_shrink_right_sidebar()` method
- [ ] Implement `action_expand_right_sidebar()` method
- [ ] Update `toggle_sidebar()` to restore width
- [ ] Update `toggle_log_groups_sidebar()` to restore width

#### commands.py
- [ ] Update `_show_help()` with keyboard shortcuts section

### Testing
- [ ] Run manual test checklist (section 9.3)
- [ ] Verify toast notifications appear
- [ ] Verify width limits are respected
- [ ] Verify width persists across toggle

### Documentation
- [ ] Update any user-facing docs if needed
```

### Estimated Time

| Task | Time |
|------|------|
| Core resize logic | 30 min |
| Action methods | 30 min |
| Toggle width restoration | 15 min |
| Help text update | 10 min |
| Unit tests | 30 min |
| Integration tests | 30 min |
| Manual testing | 30 min |
| **Total** | **~3 hours** |

---

## Appendix A: Alternative Key Binding Options

If Ctrl+Arrow conflicts occur in testing, here are fallback options:

### Option A: Bracket Keys
```python
Binding("ctrl+[", "shrink_left_sidebar", ...),
Binding("ctrl+]", "expand_left_sidebar", ...),
Binding("alt+[", "shrink_right_sidebar", ...),
Binding("alt+]", "expand_right_sidebar", ...),
```

### Option B: Letter Keys
```python
Binding("ctrl+h", "shrink_left_sidebar", ...),  # h = left in vim
Binding("ctrl+l", "expand_left_sidebar", ...),  # l = right in vim
Binding("alt+h", "shrink_right_sidebar", ...),
Binding("alt+l", "expand_right_sidebar", ...),
```

### Option C: Function Keys
```python
Binding("f1", "shrink_left_sidebar", ...),
Binding("f2", "expand_left_sidebar", ...),
Binding("f3", "shrink_right_sidebar", ...),
Binding("f4", "expand_right_sidebar", ...),
```

---

## Appendix B: Phase 2 Preview (Config Persistence)

Phase 2 will add persistence of sidebar widths to configuration. Preview:

```python
# settings.py additions
left_sidebar_width: int = 28
right_sidebar_width: int = 28

# chat.py: Load on init
self._left_sidebar_width_index = SIDEBAR_WIDTH_STEPS.index(
    self.settings.left_sidebar_width
)

# chat.py: Save on change
def _resize_sidebar(self, ...):
    # ... resize logic ...
    # Persist to settings
    self.settings.left_sidebar_width = new_width
    self.settings.save()
```

This design document covers Phase 1 only. Phase 2 persistence will be designed separately.

---

**Document End**

*Prepared by Saanvi, Senior Software Architect*
*For questions, please contact the TPM (George)*
