# Tool Calls Sidebar - Quick Reference

**Investigation By**: Hans, Code Librarian  
**Date**: February 11, 2026  
**Status**: Ready for Implementation

---

## One-Page Cheat Sheet

### What We Need to Build
A **right-side sidebar** showing recent tool calls (last 10), toggled with `/toggle-tools` command

### Current Architecture
```
Header
├─ VerticalScroll (messages)
├─ Input (user input)
└─ StatusBar (footer)
```

### New Architecture
```
Header
├─ Horizontal
│  ├─ VerticalScroll (messages) [width: 1fr]
│  └─ ToolCallsSidebar [width: 25]
├─ Input
└─ StatusBar
```

---

## Files to Create/Modify

### New File ✨
```
src/logai/ui/widgets/tool_calls_sidebar.py
```

**Minimal Implementation** (100 lines):
```python
from textual.widgets import Static, Tree
from textual.reactive import reactive

class ToolCallsSidebar(Static):
    DEFAULT_CSS = """
    ToolCallsSidebar {
        width: 25;
        background: $panel;
        border: solid $primary;
    }
    """
    
    tool_calls: reactive[list] = reactive([])
    
    def on_mount(self) -> None:
        self.tree = Tree("Tools")
        self.mount(self.tree)
    
    def watch_tool_calls(self, new_calls: list) -> None:
        self.tree.clear()
        for call in new_calls[:10]:
            node = self.tree.root.add(f"📞 {call['name']}")
            node.add(f"Status: {call.get('status', 'pending')}")
    
    def add_tool_call(self, tool_call: dict) -> None:
        self.tool_calls = [tool_call] + self.tool_calls[:9]
```

### Modified Files ✏️

#### 1. `src/logai/ui/screens/chat.py`

**Add to imports:**
```python
from logai.ui.widgets.tool_calls_sidebar import ToolCallsSidebar
from textual.containers import Horizontal
```

**Add to `__init__`:**
```python
self._show_tools_sidebar = False
self._tools_sidebar = None
```

**Update `compose()`:**
```python
def compose(self) -> ComposeResult:
    yield Header()
    yield VerticalScroll(id="messages-container")
    yield Container(ChatInput(), id="input-container")
    yield StatusBar(model=self.settings.current_llm_model)
```

**Add new method:**
```python
def _toggle_tools_sidebar(self) -> None:
    """Toggle the tools sidebar visibility."""
    self._show_tools_sidebar = not self._show_tools_sidebar
    
    try:
        sidebar = self.query_one("#tools-sidebar", ToolCallsSidebar)
        sidebar.remove()
        self._tools_sidebar = None
    except Exception:
        # Mount sidebar
        if self.size.width >= 100:
            self._tools_sidebar = ToolCallsSidebar(id="tools-sidebar")
            header = self.query_one(Header)
            header.parent.mount(self._tools_sidebar, after=header)
```

**Add to `on_mount()`:**
```python
# Register tool call callback
self.orchestrator.register_tool_listener(self._on_tool_call)

def _on_tool_call(self, tool_call_info: dict) -> None:
    """Receive tool call from orchestrator."""
    if self._tools_sidebar and self._show_tools_sidebar:
        self._tools_sidebar.add_tool_call(tool_call_info)
```

#### 2. `src/logai/ui/commands.py`

**Add to `handle_command()` switch:**
```python
elif cmd == "/toggle-tools":
    return "Tools sidebar toggled. Use /toggle-tools to toggle again."
```

**Add to `_show_help()`:**
```python
[cyan]/toggle-tools[/cyan] - Toggle tool calls sidebar visibility
```

#### 3. `src/logai/ui/styles/app.tcss`

**Add at end:**
```css
ToolCallsSidebar {
    width: 25;
    background: $panel;
    border: solid $primary;
    padding: 0 1;
}

ToolCallsSidebar > Tree {
    width: 100%;
}
```

#### 4. `src/logai/core/orchestrator.py` (Optional)

**Add to `__init__`:**
```python
self.tool_listeners: list[Callable] = []

def register_tool_listener(self, callback: Callable) -> None:
    """Register a listener for tool calls."""
    self.tool_listeners.append(callback)

def _notify_tool_call(self, tool_name: str, args: dict, result: dict) -> None:
    """Notify listeners of tool call."""
    for listener in self.tool_listeners:
        try:
            listener({
                'name': tool_name,
                'args': args,
                'result': result,
                'status': 'complete' if result.get('success') else 'error'
            })
        except Exception as e:
            logger.warning(f"Error in tool listener: {e}")
```

**In `_execute_tool_calls()`, after each tool executes:**
```python
self._notify_tool_call(function_name, function_args, result)
```

---

## Testing Checklist

- [ ] App starts without sidebar visible
- [ ] Type `/toggle-tools` → sidebar appears on right
- [ ] Type `/toggle-tools` → sidebar disappears
- [ ] Run a CloudWatch query → sidebar updates with tool calls
- [ ] Sidebar shows tool name, args, status
- [ ] Multiple tools appear in sidebar
- [ ] On narrow terminal (< 100 columns) → sidebar hidden by default
- [ ] No crashes or errors during toggle

---

## Implementation Order

1. Create `tool_calls_sidebar.py` widget (15 min)
2. Modify `chat.py` to mount/unmount sidebar (20 min)
3. Add styles to `app.tcss` (5 min)
4. Add command to `commands.py` (5 min)
5. Add callback to `orchestrator.py` (15 min)
6. Test all scenarios (30 min)

**Total: ~1-1.5 hours for basic version**

---

## Key Points

- ✅ **Non-breaking**: All changes are additive
- ✅ **Optional**: Users can toggle off if they prefer
- ✅ **Simple**: ~300 lines of code total
- ✅ **Responsive**: Hides on small terminals automatically
- ✅ **Async-safe**: Uses Textual reactive pattern

---

## Troubleshooting

**Sidebar not appearing?**
- Check terminal width >= 100 columns
- Check `/toggle-tools` command is recognized
- Verify `ToolCallsSidebar` is imported

**Sidebar not updating?**
- Verify `register_tool_listener` is called in `on_mount()`
- Check `_notify_tool_call` is invoked in orchestrator
- Add logging to debug listener callbacks

**Layout broken?**
- Verify CSS width units are correct (`width: 25` not `width: 25%`)
- Check `VerticalScroll` parent is `Horizontal` container
- Ensure no conflicting CSS rules

---

## Questions for George

1. Should sidebar be visible by default or hidden?
2. Should tool calls persist after session ends?
3. Should sidebar be resizable? (advanced feature)
4. Should we add tool result filtering? (advanced feature)

---

**Document**: Full details in `TUI_ARCHITECTURE_INVESTIGATION.md`  
**Status**: Ready to implement - awaiting George's approval

