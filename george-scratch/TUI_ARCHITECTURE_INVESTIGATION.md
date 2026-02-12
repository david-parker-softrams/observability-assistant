# TUI Architecture Investigation: Tool Calls Sidebar Implementation

**Investigator**: Hans  
**Date**: February 11, 2026  
**Status**: Complete  
**Objective**: Understand current TUI architecture and plan tool calls sidebar addition

---

## Executive Summary

The LogAI application uses **Textual 0.47.0+** (a Python TUI framework) to provide a modern terminal interface for CloudWatch log analysis. The current architecture is straightforward:

- **Single screen design** (ChatScreen) with vertical layout (Header → Messages → Input → StatusBar)
- **Tool calls are tracked** in the orchestrator but not visually displayed
- **Command system** uses slash commands (/help, /cache, /clear, etc.)
- **No persistent state** beyond conversation history
- **No sidebar** currently exists

Adding a tool calls sidebar is feasible with minimal changes to the existing architecture.

---

## 1. TUI Framework & Architecture

### Framework Details
- **Library**: **Textual** (TUI framework for Python)
- **Version**: ≥0.47.0 (from pyproject.toml)
- **Additional UI Library**: Rich (for markup/styling)
- **Language**: Python 3.11+

### Textual Capabilities
Textual provides:
- ✅ Widget system (composable UI components)
- ✅ CSS-like styling (TCSS - Textual CSS)
- ✅ Reactive updates (automatic re-renders on state changes)
- ✅ Container layouts (Horizontal, Vertical, Grid)
- ✅ Event handling system
- ✅ Action binding system (Ctrl+X, etc.)
- ✅ Focus management
- ✅ Docking (fixed position widgets)

### Main App Entry Point
**File**: `src/logai/ui/app.py`

```python
class LogAIApp(App[None]):
    """LogAI Terminal User Interface application."""
    
    TITLE = "LogAI - CloudWatch Assistant"
    CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"
    
    def on_mount(self) -> None:
        """Mount the chat screen when app starts."""
        await self.push_screen(
            ChatScreen(orchestrator=self.orchestrator, cache_manager=self.cache_manager)
        )
```

**Key Points**:
- Main app is `LogAIApp` (inherits from `App`)
- Uses push_screen pattern (screens are managed in a stack)
- Currently only has one screen: `ChatScreen`
- App-level CSS is at `src/logai/ui/styles/app.tcss`

### Layout System

**Current Layout Structure** (from `ChatScreen.compose()`):

```
┌─────────────────────────────────────────────┐
│  Header (title bar)                         │
├─────────────────────────────────────────────┤
│  VerticalScroll #messages-container         │
│  (displays user/assistant/system messages)  │
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│  Container #input-container                 │
│  - ChatInput widget (user input)            │
├─────────────────────────────────────────────┤
│  StatusBar (dock: bottom) - 1 line          │
│  Shows: Status | Cache Stats | Model       │
└─────────────────────────────────────────────┘
```

**Current CSS Layout**:
- **Vertical layout** (top-to-bottom)
- Messages container: `height: 1fr` (flexible, fills space)
- Input container: `height: auto` (minimal space)
- Status bar: `height: 1` (fixed 1 line), `dock: bottom` (always visible)

---

## 2. Tool Execution Flow

### Where Tool Calls Are Initiated
**File**: `src/logai/core/orchestrator.py`

The `LLMOrchestrator` class manages the conversation loop:

```python
class LLMOrchestrator:
    """Coordinates LLM interactions with tool execution."""
    
    async def chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Stream response with automatic tool calling."""
        
        # Main loop (up to max_tool_iterations times)
        while iteration < max_iterations:
            # 1. Get LLM response
            response = await self.llm_provider.chat(messages=messages, tools=tools)
            
            # 2. Check if LLM wants tools
            if response.has_tool_calls():
                # 3. Execute tools
                tool_results = await self._execute_tool_calls(response.tool_calls)
                
                # 4. Add results to conversation
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls  # <-- STORED HERE
                })
```

### Tool Call Data Structure

**Tool calls are structured as**:
```python
tool_calls = [
    {
        "id": "call_abc123",
        "function": {
            "name": "get_log_events",
            "arguments": '{"log_group": "/aws/lambda/func", ...}'
        }
    }
]
```

**Tool results are stored as**:
```python
tool_results = [
    {
        "tool_call_id": "call_abc123",
        "result": {
            "success": True,
            "count": 42,
            "events": [...]
        }
    }
]
```

### How Tool Calls Are Tracked

1. **In orchestrator**: Tool calls stored in `conversation_history` as part of assistant messages
2. **Method**: `_execute_tool_calls()` (line 787) executes them sequentially
3. **In UI**: Currently NOT displayed or tracked in the UI layer

### Critical Methods
- `_execute_tool_calls()` - Executes tool calls and returns results
- `_analyze_tool_results()` - Checks for empty results, errors (retry logic)
- `_chat_stream()` - Main conversation loop (streaming)
- `_chat_complete()` - Non-streaming variant

---

## 3. Command System

### Current Implementation
**File**: `src/logai/ui/commands.py`

```python
class CommandHandler:
    """Handles special slash commands in the chat."""
    
    def is_command(self, message: str) -> bool:
        """Check if a message is a command."""
        return message.strip().startswith("/")
    
    async def handle_command(self, command: str) -> str:
        """Handle a special command."""
        command = command.strip()
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == "/help":
            return self._show_help()
        elif cmd == "/clear":
            return self._clear_history()
        elif cmd == "/cache":
            # ... subcommands: status, clear
        # ... more commands
```

### Available Commands
- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/cache status` - Show cache stats
- `/cache clear` - Clear cache
- `/model` - Show LLM model
- `/config` - Show configuration
- `/quit` or `/exit` - Information about quitting

### Command Routing Flow

```python
# In ChatScreen.on_input_submitted()
message = event.value.strip()

if self.command_handler.is_command(message):
    response = await self.command_handler.handle_command(message)
    system_msg = SystemMessage(response)
    messages_container.mount(system_msg)
else:
    # Process with LLM
    self._process_message(message)
```

### How to Add New Commands

To add a new command (e.g., `/toggle-tools`):

1. **Add handler method** in `CommandHandler`:
```python
elif cmd == "/toggle-tools":
    return await self._toggle_tools_sidebar()

async def _toggle_tools_sidebar(self) -> str:
    """Toggle the tools sidebar visibility."""
    # Implementation
    return "Tools sidebar toggled"
```

2. **Add help text** in `_show_help()`:
```python
[cyan]/toggle-tools[/cyan] - Toggle tool calls sidebar visibility
```

3. **That's it!** The routing is handled automatically by the switch statement

---

## 4. State Management

### Current State Management
**Issue**: LogAI currently has **minimal state management**

**Current state**:
- `orchestrator.conversation_history` - List of messages (in-memory)
- `cache_manager` - Cache state (in SQLite)
- `status_bar.status` - UI status (reactive)
- `status_bar.cache_hits/misses` - Cache stats (reactive)

### Reactive Updates
Textual uses **reactive attributes** for reactive UI updates:

```python
class StatusBar(Static):
    status: reactive[str] = reactive("Ready")
    cache_hits: reactive[int] = reactive(0)
    cache_misses: reactive[int] = reactive(0)
    
    def watch_status(self, new_status: str) -> None:
        """Called automatically when status changes."""
        self.update_display()
```

### Where to Store "Sidebar Visible" State

**Option 1: In ChatScreen (Simple, Recommended)**
```python
class ChatScreen(Screen[None]):
    def __init__(self, orchestrator, cache_manager):
        super().__init__()
        self._show_tools_sidebar = False  # <-- Add here
        # ...
    
    def _toggle_tools_sidebar(self) -> None:
        self._show_tools_sidebar = not self._show_tools_sidebar
        # Update layout
```

**Option 2: In LogAIApp (Global)**
```python
class LogAIApp(App[None]):
    def __init__(self, orchestrator, cache_manager):
        super().__init__()
        self.show_tools_sidebar = False  # <-- Add here
```

**Recommendation**: Store in `ChatScreen` since it's screen-specific.

### Persistence Across Sessions

Currently, NO state is persisted across sessions. To add persistence:

1. Save state to a JSON file in settings directory
2. Load on app startup
3. Update on state changes

Example:
```python
# In ChatScreen.on_mount()
config_file = Path.home() / ".logai" / "ui_state.json"
if config_file.exists():
    config = json.loads(config_file.read_text())
    self._show_tools_sidebar = config.get("show_tools_sidebar", False)
```

---

## 5. Layout Considerations

### Proposed Sidebar Layout

**Option A: Right Sidebar (Recommended)**
```
┌──────────────────────────────┬────────────────┐
│ Header                       │ TOOLS SIDEBAR  │
│                              │ (collapsible)  │
├──────────────────────────────┤                │
│                              │ Recent Tools:  │
│ Messages                     │ • list_logs... │
│ (chat history)               │ • get_events.. │
│                              │ • describe_... │
│                              │                │
│                              │ Execution:     │
│                              │ • Status       │
│                              │ • Duration     │
│                              │ • Args         │
├──────────────────────────────┤                │
│ Input Box                    │                │
├──────────────────────────────┴────────────────┤
│ Status Bar                                    │
└─────────────────────────────────────────────┘
```

**Option B: Left Sidebar**
```
┌────────────────┬──────────────────────────────┐
│ TOOLS          │ Header                       │
│ SIDEBAR        │                              │
│ (collapsible)  ├──────────────────────────────┤
│ Recent Tools:  │                              │
│ • list_logs... │ Messages                     │
│ • get_events.. │ (chat history)               │
│ • describe_... │                              │
│                │                              │
│ Execution:     │                              │
│ • Status       │                              │
│ • Duration     │                              │
│ • Args         ├──────────────────────────────┤
│                │ Input Box                    │
├────────────────┼──────────────────────────────┤
│         Status Bar (full width)               │
└──────────────────────────────────────────────┘
```

**Recommendation**: **Right Sidebar** is better because:
1. Natural left-to-right reading flow keeps chat in view
2. Easier to collapse without losing message context
3. More screen space for messages on wider terminals

### Responsive Behavior

For small terminals (< 120 columns):
1. Sidebar should collapse to icon/indicator
2. Show full sidebar on demand (modal/overlay)
3. Or hide completely on very small screens

Implementation:
```python
class ChatScreen(Screen[None]):
    def on_resize(self) -> None:
        """Handle terminal resize."""
        width = self.size.width
        if width < 80:
            self._auto_hide_sidebar()  # Hide on tiny terminals
        elif width < 120:
            self._collapse_sidebar()   # Show icons only
```

### Key Layout Files

**Files that need modification**:
1. `src/logai/ui/screens/chat.py` - Add sidebar widget
2. `src/logai/ui/styles/app.tcss` - Add sidebar styles
3. `src/logai/ui/widgets/` - Create new `tool_calls_sidebar.py`

---

## 6. Current Components Inventory

### Existing Widgets
| Widget | Location | Purpose |
|--------|----------|---------|
| `Header` | Textual built-in | Title bar |
| `VerticalScroll` | Textual built-in | Scrollable messages container |
| `Container` | Textual built-in | Input container |
| `ChatInput` | `widgets/input_box.py` | User message input |
| `UserMessage` | `widgets/messages.py` | Display user messages |
| `AssistantMessage` | `widgets/messages.py` | Display AI responses |
| `SystemMessage` | `widgets/messages.py` | Display system notifications |
| `LoadingIndicator` | `widgets/messages.py` | Animated "Thinking..." |
| `ErrorMessage` | `widgets/messages.py` | Display error messages |
| `StatusBar` | `widgets/status_bar.py` | Bottom status line |

### Textual Built-in Widgets Available
- `Static` - Basic container
- `Container` - Layout container (Vertical/Horizontal)
- `Button` - Clickable button
- `Input` - Text input
- `TextArea` - Multi-line text (for rich code display)
- `Tree` - Tree view (perfect for tool hierarchy!)
- `Select` - Dropdown selector
- `DataTable` - Tabular display
- `RichLog` - Log output display

---

## 7. Key Files Overview

### Architecture Files
```
src/logai/
├── ui/
│   ├── app.py                    # Main Textual app (LogAIApp)
│   ├── commands.py               # Slash command handler
│   ├── screens/
│   │   └── chat.py              # Main chat screen (ChatScreen)
│   ├── widgets/
│   │   ├── input_box.py         # ChatInput widget
│   │   ├── messages.py          # Message display widgets
│   │   └── status_bar.py        # Status bar widget
│   └── styles/
│       └── app.tcss             # TCSS styling
├── core/
│   ├── orchestrator.py          # Tool call execution (LLMOrchestrator)
│   ├── tools/
│   │   └── registry.py          # Tool registry
│   └── ...
└── ...
```

### Files That Need Changes

1. **`src/logai/ui/screens/chat.py`** (Required)
   - Add tools sidebar widget to layout
   - Add toggle command handler
   - Track tool calls and update sidebar

2. **`src/logai/ui/widgets/tool_calls_sidebar.py`** (New)
   - Create new sidebar widget
   - Display recent tool calls
   - Show execution details

3. **`src/logai/ui/styles/app.tcss`** (Required)
   - Add sidebar styles
   - Update layout constraints
   - Add responsive rules

4. **`src/logai/ui/commands.py`** (Optional)
   - Add `/toggle-tools` command
   - Add help text

5. **`src/logai/core/orchestrator.py`** (No changes needed)
   - Tool call tracking already exists
   - Just expose via API/callback

---

## 8. Technical Challenges & Solutions

### Challenge 1: Getting Tool Calls to UI Layer

**Problem**: Tool calls are executed in orchestrator, but UI has no visibility

**Solutions**:

**A. Polling (Simple)**
```python
# In ChatScreen
while processing:
    tool_calls = self.orchestrator.get_recent_tool_calls(limit=5)
    self._update_sidebar(tool_calls)
    await asyncio.sleep(0.5)  # Poll every 500ms
```
- ✅ Simple to implement
- ❌ Inefficient, creates noise

**B. Callback/Observer Pattern (Recommended)**
```python
# In LLMOrchestrator
class LLMOrchestrator:
    def __init__(self, ...):
        self.tool_call_listeners: list[Callable] = []
    
    def register_tool_listener(self, callback: Callable) -> None:
        self.tool_call_listeners.append(callback)
    
    async def _execute_tool_calls(self, tool_calls):
        for tool_call in tool_calls:
            # ... execute ...
            for listener in self.tool_call_listeners:
                listener(tool_call, result)  # Notify UI
```

**C. Reactive State (Most Textual-like)**
```python
# In ChatScreen - use reactive source of truth
class ChatScreen(Screen[None]):
    recent_tool_calls: reactive[list] = reactive([])
    
    def on_mount(self):
        # Subscribe to orchestrator updates
        self.orchestrator.subscribe_to_tools(self._on_tool_call)
    
    def _on_tool_call(self, tool_call_data):
        self.recent_tool_calls = [tool_call_data] + self.recent_tool_calls[:10]
```

**Recommendation**: Use **Option C (Reactive State)** as it's most idiomatic to Textual.

### Challenge 2: Layout Switching (Show/Hide Sidebar)

**Problem**: Textual doesn't have built-in show/hide, only mount/remove

**Solution**: Dynamic layout in compose() or manual mount/remove

```python
class ChatScreen(Screen[None]):
    def __init__(self, ...):
        self._show_sidebar = False
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        # Conditional layout based on state
        if self._show_sidebar:
            # Horizontal layout: messages + sidebar
            with Horizontal():
                yield VerticalScroll(id="messages-container")
                yield ToolCallsSidebar(id="tools-sidebar")
        else:
            # Just messages
            yield VerticalScroll(id="messages-container")
        
        yield Container(ChatInput(), id="input-container")
        yield StatusBar(...)
    
    def _toggle_sidebar(self) -> None:
        self._show_sidebar = not self._show_sidebar
        self.recompose()  # Rebuild layout
```

**Issue**: `recompose()` is heavy - better to use mount/remove:

```python
def _toggle_sidebar(self) -> None:
    self._show_sidebar = not self._show_sidebar
    try:
        sidebar = self.query_one("#tools-sidebar")
        sidebar.remove()
    except NoMatches:
        # Not mounted, add it
        messages = self.query_one("#messages-container")
        sidebar = ToolCallsSidebar(id="tools-sidebar")
        messages.parent.mount(sidebar, before=messages)  # Mount next to messages
```

### Challenge 3: Keeping Track of Tool Calls

**Problem**: Tool calls execute asynchronously, messages stream in real-time

**Solution**: Implement a thread-safe queue in orchestrator

```python
class LLMOrchestrator:
    def __init__(self, ...):
        self.recent_tool_calls: asyncio.Queue = asyncio.Queue(maxsize=50)
    
    async def _execute_tool_calls(self, tool_calls):
        for tool_call in tool_calls:
            result = await self.tool_registry.execute(...)
            
            # Add to queue for UI
            await self.recent_tool_calls.put({
                'name': tool_call['function']['name'],
                'args': json.loads(tool_call['function']['arguments']),
                'result': result,
                'timestamp': datetime.now()
            })
```

### Challenge 4: Responsive Sidebar on Small Terminals

**Problem**: Sidebar takes ~20% width, leaving only 80% for messages

**Solution**: Hidden by default on small screens, toggle-able

```python
def _should_show_sidebar(self) -> bool:
    """Determine if sidebar should be visible."""
    width = self.size.width
    if width < 100:
        return self._show_sidebar and width >= 80
    return self._show_sidebar
```

### Challenge 5: CSS Constraints

**Problem**: Need to partition space between messages and sidebar

**Solution**: Use Textual's layout system

```css
#chat-container {
    layout: horizontal;
}

#messages-container {
    width: 1fr;  /* Take remaining space */
    height: 1fr;
}

#tools-sidebar {
    width: 25;   /* Fixed 25 columns */
    height: 1fr;
    background: $panel;
    border: solid $primary;
}
```

---

## 9. Implementation Roadmap

### Phase 1: Basic Sidebar (1-2 hours)
1. ✅ Create `ToolCallsSidebar` widget
2. ✅ Add basic styling
3. ✅ Mount sidebar in ChatScreen
4. ✅ Add `/toggle-tools` command
5. ✅ Display hardcoded sample tool calls

### Phase 2: Connect to Orchestrator (1-2 hours)
1. ✅ Add tool call callback to LLMOrchestrator
2. ✅ Register callback in ChatScreen
3. ✅ Update sidebar with real tool calls
4. ✅ Show tool name, args, result

### Phase 3: Polish (1 hour)
1. ✅ Responsive sizing
2. ✅ Scrolling for many tools
3. ✅ Collapsible tool details
4. ✅ Persist sidebar state
5. ✅ Error handling

### Phase 4: Advanced (Optional)
1. ✅ Tool execution timing
2. ✅ Tool result search
3. ✅ Tool call filtering
4. ✅ Copy tool results to input

---

## 10. Proposed Sidebar Widget Code Structure

### File: `src/logai/ui/widgets/tool_calls_sidebar.py`

```python
from textual.widgets import Static, Tree
from textual.reactive import reactive

class ToolCallsSidebar(Static):
    """Sidebar showing recent tool calls and their results."""
    
    DEFAULT_CSS = """
    ToolCallsSidebar {
        width: 25;
        background: $panel;
        border: solid $primary;
        padding: 0 1;
    }
    
    ToolCallsSidebar > Tree {
        width: 100%;
        height: 100%;
    }
    """
    
    # Reactive list of tool calls
    tool_calls: reactive[list] = reactive([])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tree = Tree("Tools", data=None)
    
    def on_mount(self) -> None:
        """Mount the tree widget."""
        self.mount(self.tree)
    
    def watch_tool_calls(self, new_calls: list) -> None:
        """Update tree when tool calls change."""
        self.tree.clear()
        for call in new_calls[:10]:  # Show last 10
            label = f"📞 {call['name']}"
            node = self.tree.root.add(label, data=call)
            # Add details as children
            node.add(f"Args: {call['args']}")
            node.add(f"Status: {call.get('status', 'pending')}")
    
    def add_tool_call(self, tool_call: dict) -> None:
        """Add a tool call to the sidebar."""
        self.tool_calls = [tool_call] + self.tool_calls[:9]
```

### Integration in ChatScreen

```python
class ChatScreen(Screen[None]):
    def __init__(self, orchestrator, cache_manager):
        # ...
        self._show_tools_sidebar = False
        self._tools_sidebar = None
    
    def on_mount(self) -> None:
        # Register to receive tool call updates
        self.orchestrator.register_tool_listener(self._on_tool_call)
    
    def _on_tool_call(self, tool_call_info: dict) -> None:
        """Callback when a tool is called."""
        if self._tools_sidebar:
            self._tools_sidebar.add_tool_call(tool_call_info)
    
    async def _handle_toggle_tools_command(self) -> str:
        """Toggle tools sidebar visibility."""
        self._show_tools_sidebar = not self._show_tools_sidebar
        
        if self._show_tools_sidebar and not self._tools_sidebar:
            # Mount sidebar
            self._tools_sidebar = ToolCallsSidebar(id="tools-sidebar")
            messages = self.query_one("#messages-container")
            # Mount after header, before messages
            messages.parent.mount(self._tools_sidebar, before=messages)
        
        elif not self._show_tools_sidebar and self._tools_sidebar:
            # Unmount sidebar
            self._tools_sidebar.remove()
            self._tools_sidebar = None
        
        return f"Tools sidebar {'shown' if self._show_tools_sidebar else 'hidden'}."
```

---

## 11. Summary of Changes Required

### New Files
- `src/logai/ui/widgets/tool_calls_sidebar.py` - Sidebar widget

### Modified Files
1. `src/logai/ui/screens/chat.py` - Add sidebar integration
2. `src/logai/ui/styles/app.tcss` - Add sidebar styles
3. `src/logai/ui/commands.py` - Add `/toggle-tools` command (optional)
4. `src/logai/core/orchestrator.py` - Add tool call callback mechanism

### Dependencies Added
- None (Textual already includes Tree, Static widgets)

### Estimated Effort
- **Phase 1 (Basic)**: 2-3 hours
- **Phase 2 (Connected)**: 1-2 hours
- **Phase 3 (Polish)**: 1-2 hours
- **Total**: 4-7 hours for complete implementation

---

## 12. Testing Strategy

### Unit Tests
```python
# tests/unit/test_tool_calls_sidebar.py
def test_sidebar_creation():
    sidebar = ToolCallsSidebar()
    assert sidebar.id == "tools-sidebar"

def test_add_tool_call():
    sidebar = ToolCallsSidebar()
    sidebar.add_tool_call({
        'name': 'get_logs',
        'args': {...},
        'result': {...}
    })
    assert len(sidebar.tool_calls) == 1
```

### Integration Tests
```python
# tests/integration/test_chat_with_sidebar.py
async def test_toggle_tools_sidebar():
    chat_screen = ChatScreen(orchestrator, cache_manager)
    # Mount and test toggle
    # Verify sidebar appears/disappears
```

### Manual Testing
1. Start app, verify no sidebar by default
2. Type `/toggle-tools` - sidebar should appear
3. Type `/toggle-tools` again - sidebar should disappear
4. Run a query that calls tools - observe sidebar updating
5. Try on different terminal widths

---

## Conclusion

The LogAI TUI is well-architected for adding a tool calls sidebar:

1. **Simple current design** = easy to extend
2. **Textual framework** provides all necessary widgets
3. **Tool execution already tracked** in orchestrator
4. **Callback pattern** can connect orchestrator → UI
5. **Reactive system** handles dynamic updates efficiently

The main implementation challenge is connecting the async tool execution to the UI layer, but this can be solved cleanly with a callback/observer pattern.

**Recommended approach**: 
- Add callback mechanism to orchestrator
- Create ToolCallsSidebar widget
- Integrate into ChatScreen layout
- Add toggle command

This maintains the current clean architecture while adding valuable observability.

---

## References

- Textual Documentation: https://textual.textualize.io/
- Current implementation: `src/logai/ui/` directory
- Tool execution: `src/logai/core/orchestrator.py`

