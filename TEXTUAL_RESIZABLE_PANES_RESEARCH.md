# Textual TUI Framework: Resizable Panes Research Report

**Date**: February 12, 2026
**Researcher**: Hans (Code Librarian)
**Target Framework**: Textual 7.5.0
**Current Spec**: `textual>=0.47.0` (project uses 7.5.0)

---

## Executive Summary

**Direct Answer**: Textual 7.5.0 **DOES NOT** have built-in support for draggable/resizable panes or splitters.

The framework provides:
- ✅ Fixed-width docked sidebars
- ✅ Flexible container sizing with CSS
- ✅ Min/max width constraints
- ❌ No native splitter widgets
- ❌ No drag-to-resize functionality
- ❌ No resizable pane containers

---

## 1. Current Textual Layout Architecture

### Available Container Types (Textual 7.5.0)

```
textual.containers:
├── Container (base class)
├── Horizontal (side-by-side layout)
├── Vertical (stacked layout)
├── HorizontalScroll (scrollable horizontal)
├── VerticalScroll (scrollable vertical)
├── HorizontalGroup (grouped items)
├── VerticalGroup (grouped items)
├── Grid (grid layout system)
├── ScrollableContainer (scrollable container)
└── ... positioning helpers (Center, Middle, Right)
```

### Current LogAI UI Structure

**File**: `/src/logai/ui/screens/chat.py`

```python
Horizontal(id="main-content"):
    ├── LogGroupsSidebar (left, docked)
    │   └── width: 28, min-width: 24, max-width: 35
    ├── VerticalScroll (messages, flexible center)
    │   └── width: 1fr (flexible)
    └── ToolCallsSidebar (right, docked)
        └── width: 28, min-width: 24, max-width: 35
```

**CSS Approach Used**:
```css
#log-groups-sidebar {
    dock: left;
    width: 28;
    min-width: 24;
    max-width: 35;
}

#tools-sidebar {
    dock: right;
    width: 28;
    min-width: 24;
    max-width: 35;
}
```

---

## 2. Research Findings

### What Textual CAN Do (Current Version)

1. **Fixed-Width Docked Containers**
   - Using `dock: left` / `dock: right` CSS properties
   - Define fixed widths and constraints
   - Currently implemented in logai

2. **Flexible Sizing**
   - Use `width: 1fr` for flexible layouts
   - Container width/height properties
   - Min/max constraints work

3. **Mouse Events**
   - Textual supports `MouseDown`, `MouseMove`, `MouseUp` events
   - Can theoretically build custom resizing logic

### What Textual CANNOT Do (Native Support)

1. **Splitter Widgets**
   - No `Split` or `Splitter` widget exists
   - Not in containers module
   - Not planned in current roadmap

2. **Drag-to-Resize**
   - No built-in drag handle functionality
   - No visual divider for resizing
   - Would require custom implementation

3. **Resizable Container Pattern**
   - No native resizable pane pattern
   - TabbedContent exists but doesn't support resizing

---

## 3. Exploration of Textual Roadmap

**Roadmap Status**: No splitters/resizable panes mentioned

The official Textual roadmap includes:
- Accessibility features
- Command palette
- Themes and configuration
- Various widgets (DataTable, TextArea, etc.)
- Form widgets
- Image support
- Plots and charts

**NOT Included**:
- Split containers
- Resizable panes
- Draggable splitters

---

## 4. Implementation Alternatives

### Option A: Keyboard Shortcuts (Recommended for MVP)

**Advantages**:
- ✅ Works with current Textual version
- ✅ Non-intrusive UI
- ✅ No custom code needed
- ✅ Familiar to power users

**Implementation**:
```python
# Add to ChatScreen
BINDINGS = [
    Binding("ctrl+left", "resize_sidebar(\"left\", \"-1\")", "Shrink left"),
    Binding("ctrl+right", "resize_sidebar(\"left\", \"+1\")", "Grow left"),
    Binding("ctrl+shift+left", "resize_sidebar(\"right\", \"+1\")", "Grow right"),
    Binding("ctrl+shift+right", "resize_sidebar(\"right\", \"-1\")", "Shrink right"),
]

async def action_resize_sidebar(self, side: str, direction: str) -> None:
    """Resize sidebar using keyboard shortcuts."""
    # Update CSS width property dynamically
```

### Option B: Custom Splitter Widget (Complex)

**Advantages**:
- 🟡 Native drag-to-resize feel
- 🟡 More intuitive for GUI users

**Disadvantages**:
- ❌ Requires significant custom code
- ❌ Must handle mouse events manually
- ❌ Must manage layout recalculation
- ❌ Fragile and hard to maintain
- ❌ TUI frameworks aren't optimized for this

**Complexity**: HIGH (~300-500 lines of code)

**Estimated Implementation Time**: 2-3 days

### Option C: Toggle + Fixed Widths (Current Approach)

**Current State in logai**:
- Sidebars can be toggled on/off via commands
- Fixed widths with min/max constraints
- Simple and maintainable

**Enhancement Path**:
```python
# Add discrete sizing modes
SIDEBAR_WIDTHS = {
    "compact": 24,
    "normal": 28,
    "wide": 35,
}

# Toggle between sizes with command/binding
async def action_toggle_sidebar_width(self) -> None:
    """Cycle through sidebar width presets."""
    current_width = self._tool_sidebar.styles.width
    # Cycle to next width in SIDEBAR_WIDTHS
```

### Option D: Configuration-Based Sizing

**File**: `.env` or `config.toml`
```toml
[ui]
left_sidebar_width = 28
right_sidebar_width = 28
```

**Load at startup and apply via CSS**

---

## 5. Future Textual Versions

**Checking Textual 7.5.0 Latest Release** (as of Feb 12, 2026):
- No mention of splitter functionality
- Focus on DataTable improvements
- No planned split/splitter widgets in roadmap

**Future Possibility**: Could be added in v8.x or later, but:
- No current development tracked
- Would require significant architectural work
- Terminal UIs don't typically prioritize this

---

## 6. Current Codebase Analysis

### Sidebar Implementation Details

**LogGroupsSidebar** (`/src/logai/ui/widgets/log_groups_sidebar.py`):
- Lines 25-32: CSS styling with fixed width
- Docked to left automatically via CSS
- Uses `VerticalScroll` for content

**ToolCallsSidebar** (`/src/logai/ui/widgets/tool_sidebar.py`):
- Lines 24-62: CSS styling with fixed width
- Docked to right automatically via CSS
- Uses `Tree` widget for hierarchical display

**ChatScreen** (`/src/logai/ui/screens/chat.py`):
- Lines 38-68: Layout composition
- Lines 270-292: Toggle sidebar visibility (already implemented!)

### Toggle Functionality Already Present

```python
def toggle_sidebar(self) -> None:
    """Toggle the tools sidebar visibility."""
    self._tool_sidebar_visible = not self._tool_sidebar_visible
    if self._tool_sidebar:
        self._tool_sidebar.display = self._tool_sidebar_visible

def toggle_log_groups_sidebar(self) -> None:
    """Toggle the log groups sidebar visibility."""
    self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible
    if self._log_groups_sidebar:
        self._log_groups_sidebar.display = self._log_groups_sidebar_visible
```

---

## 7. Recommendations

### Recommendation 1: Keyboard Shortcuts (BEST - MVP)

**For immediate implementation:**

1. Add keyboard bindings to resize sidebars in discrete steps
2. Update CSS width properties dynamically
3. Provide user feedback in status bar

**Effort**: 1-2 hours
**Maintainability**: HIGH
**User Experience**: Good for power users

**Commands**:
```
Ctrl+< : Shrink left sidebar
Ctrl+> : Expand left sidebar
Ctrl+[ : Shrink right sidebar
Ctrl+] : Expand right sidebar
```

### Recommendation 2: Configuration File

**Add to `pyproject.toml` or `.env`:**
```ini
LOGAI_LEFT_SIDEBAR_WIDTH=28
LOGAI_RIGHT_SIDEBAR_WIDTH=28
```

**Benefits**:
- ✅ Persistent across sessions
- ✅ Easy to customize
- ✅ No runtime performance impact
- ✅ Works immediately with current Textual

### Recommendation 3: Discrete Size Presets

**Don't build drag-to-resize, offer "size modes" instead:**
```
Compact (24) → Normal (28) → Wide (35) → Hidden (0)
```

**Command**: `/sidebar-width compact|normal|wide|hidden`

### Recommendation 4: Future Planning

**If drag-to-resize becomes critical:**
1. Monitor Textual releases for splitter support
2. Consider upgrading when available (v8.x or later)
3. For now, accept keyboard-driven approach as standard for TUI

---

## 8. Summary Table

| Feature | Textual 7.5.0 | LogAI Current | Effort to Add |
|---------|---------------|---------------|---------------|
| Fixed-width sidebars | ✅ Yes | ✅ Yes | N/A |
| Toggle visibility | ✅ Yes | ✅ Yes | N/A |
| Keyboard resize | ✅ Possible | ❌ No | 1-2 hrs |
| Drag-to-resize | ❌ No | ❌ No | 2-3 days |
| Size presets | ✅ Possible | ❌ No | 1 hr |
| Config persistence | ✅ Yes | ❌ No | 1-2 hrs |
| Native splitter | ❌ No | N/A | Future version |

---

## 9. Code Examples

### Example: Keyboard-Driven Resizing

```python
from textual.binding import Binding

class ChatScreen(Screen[None]):
    BINDINGS = [
        # ... existing bindings
        Binding("ctrl+comma", "shrink_left_sidebar", "Shrink left sidebar"),
        Binding("ctrl+period", "grow_left_sidebar", "Expand left sidebar"),
        Binding("ctrl+bracketleft", "shrink_right_sidebar", "Shrink right sidebar"),
        Binding("ctrl+bracketright", "grow_right_sidebar", "Expand right sidebar"),
    ]

    SIDEBAR_WIDTH_STEPS = [24, 26, 28, 30, 32, 35]

    def __init__(self, ...):
        super().__init__()
        self._left_sidebar_width_idx = 2  # Start at 28
        self._right_sidebar_width_idx = 2

    async def action_grow_left_sidebar(self) -> None:
        """Increase left sidebar width."""
        if self._left_sidebar_width_idx < len(self.SIDEBAR_WIDTH_STEPS) - 1:
            self._left_sidebar_width_idx += 1
            width = self.SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_idx]
            if self._log_groups_sidebar:
                self._log_groups_sidebar.styles.width = width

    async def action_shrink_left_sidebar(self) -> None:
        """Decrease left sidebar width."""
        if self._left_sidebar_width_idx > 0:
            self._left_sidebar_width_idx -= 1
            width = self.SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_idx]
            if self._log_groups_sidebar:
                self._log_groups_sidebar.styles.width = width

    # Similar for right sidebar...
```

---

## Conclusion

**Direct Answer to George's Question:**

> "Does Textual have built-in support for draggable/resizable panes?"

**NO.** Textual 7.5.0 does not have this feature.

**What to do instead:**

1. **For MVP**: Use keyboard shortcuts to adjust sidebar widths in steps
2. **For UX**: Add size presets (Compact/Normal/Wide)
3. **For persistence**: Add configuration file support
4. **For future**: Monitor Textual roadmap, but don't expect native splitters soon

**Current implementation is good** - it has toggle visibility already. The next logical enhancement is keyboard-driven sizing adjustments, not drag-to-resize.
