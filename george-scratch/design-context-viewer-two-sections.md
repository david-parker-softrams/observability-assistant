# Design Document: Context Viewer Enhancement - Two-Section Modal

**Author:** Saanvi (Senior Software Architect)
**Date:** 2026-02-19
**Status:** Ready for Implementation
**Assignee:** Jackie (Implementation)

---

## 1. Executive Summary

This design enhances the Context Viewer modal to display **two distinct sections**:

1. **Staged Context** - Logs waiting to be injected (`_pending_context_injection`)
2. **Agent Memory** - Full conversation history the agent has in memory

The goal is to give users visibility into **what the agent will see next** versus **what the agent currently knows**, which is critical for debugging and understanding agent behavior.

---

## 2. Architecture Decisions

### 2.1 Data Access Strategy

**Decision: Direct property access with new public getter method**

I recommend adding a simple public method to the orchestrator rather than accessing `conversation_history` directly:

```python
# In orchestrator.py - add this method
def get_conversation_history(self) -> list[dict[str, Any]]:
    """
    Get a copy of the current conversation history.

    Returns:
        Copy of conversation history messages (system, user, assistant, tool messages).
        Returns a copy to prevent external mutation.
    """
    return list(self.conversation_history)
```

**Rationale:**
- `conversation_history` is already a public attribute (no underscore), so accessing it directly is acceptable
- Adding a getter method provides encapsulation and returns a copy, preventing accidental mutation
- Avoids complex event-based subscriptions that add unnecessary complexity for a simple "read current state" operation
- Follows the existing pattern of direct orchestrator access in `ChatScreen`

**Alternative Considered - Event-based subscription:**
- Rejected because the modal is a snapshot viewer, not a live dashboard
- Adding pub/sub complexity for a read-only modal is over-engineering

### 2.2 Snapshot vs Live Updates

**Decision: Static snapshot when modal opens**

**Rationale:**
- The Context Viewer is for **inspection**, not monitoring
- Live updates would cause visual instability and confuse users
- Conversation typically pauses while modal is open (user is reading)
- Matches mental model: "Show me what the agent has RIGHT NOW"

**Implementation:**
- Capture both `_pending_context_injection` and `conversation_history` when modal opens
- Data is immutable for the lifetime of the modal
- User can close and reopen to get fresh snapshot

---

## 3. UI/UX Design

### 3.1 Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│ Context Viewer                                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ▼ Staged Context (0 items)                           [Copy]  │
│   ────────────────────────────────────────────────────────   │
│   No logs staged for injection.                              │
│   Logs are staged when you select entries from the           │
│   log preview and will be consumed on the next message.      │
│                                                              │
│ ▼ Agent Memory (12 messages)                         [Copy]  │
│   ────────────────────────────────────────────────────────   │
│   [System] You are an expert observability assistant...      │
│   [User] Show me errors from the auth service                │
│   [Assistant] I'll query the logs for errors...              │
│   [Tool Call] query_logs(log_group="/aws/lambda/auth"...)    │
│   [Tool Result] {"count": 47, "events": [...]}               │
│   [Assistant] I found 47 error entries. Here's the analysis: │
│   ...                                                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│         [Copy All]                            [Close]        │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Widget Selection

**Collapsible Sections:** Use Textual's `Collapsible` widget for each section
- Allows users to focus on one section at a time
- Both expanded by default
- Header shows item count (e.g., "Staged Context (3 items)")

**Content Display:** Use `RichLog` widget for content
- Already proven performant with large content (from current implementation)
- Virtual rendering handles 1000+ message histories
- No wrapping/truncation issues

**Section Copy Buttons:** Individual copy buttons per section
- More useful than copying both sections together
- Users typically want either staged OR memory, not both

### 3.3 Empty State Handling

**Staged Context (empty):**
```
No logs staged for injection.

Logs are staged when you:
• Select entries from the log preview (double-click a log group)
• Receive cache guidance from large tool results

Staged logs will be consumed on your next message to the agent.
```

**Agent Memory (empty):**
```
No conversation history yet.

Start a conversation by typing a message below.
The agent's memory will include:
• System instructions
• Your messages
• Agent responses
• Tool calls and results
```

### 3.4 Collapsible Section CSS

```css
/* Section headers should be visually distinct */
Collapsible > CollapsibleTitle {
    background: $primary-darken-2;
    color: $text;
    padding: 0 1;
}

/* Content area styling */
Collapsible > Contents {
    padding: 0;
    background: $panel;
}

/* Copy button alignment within header */
.section-copy-btn {
    dock: right;
    width: auto;
    margin-right: 1;
}
```

---

## 4. Data Formatting

### 4.1 Conversation History Display Format

Each message in the conversation history should be displayed with clear role identification:

```python
def _format_conversation_message(self, msg: dict[str, Any]) -> str:
    """Format a single conversation message for display."""
    role = msg.get("role", "unknown")
    content = msg.get("content", "")

    # Format based on role
    if role == "system":
        return f"[bold cyan][System][/bold cyan] {self._truncate_content(content, 500)}"

    elif role == "user":
        return f"[bold green][User][/bold green] {content}"

    elif role == "assistant":
        # Check for tool calls
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            lines = [f"[bold magenta][Assistant][/bold magenta] {content}" if content else ""]
            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "unknown")
                args = func.get("arguments", "{}")
                # Parse and pretty-print args if valid JSON
                try:
                    args_dict = json.loads(args) if isinstance(args, str) else args
                    args_str = json.dumps(args_dict, indent=2)
                except:
                    args_str = str(args)
                lines.append(f"  [bold yellow][Tool Call][/bold yellow] {name}({args_str})")
            return "\n".join(filter(None, lines))
        return f"[bold magenta][Assistant][/bold magenta] {content}"

    elif role == "tool":
        tool_call_id = msg.get("tool_call_id", "")
        content_preview = self._truncate_content(content, 200)
        return f"[bold blue][Tool Result][/bold blue] ({tool_call_id[:8]}...) {content_preview}"

    else:
        return f"[dim][{role}][/dim] {content}"
```

### 4.2 Content Truncation Strategy

**Decision: Show everything, let RichLog handle virtualization**

- Do NOT truncate conversation history
- RichLog only renders visible content (virtual scrolling)
- Users can scroll to see full history
- For extremely large tool results (>2000 chars), show preview with "[truncated]" indicator

**Implementation:**
```python
def _truncate_content(self, content: str, max_length: int = 2000) -> str:
    """Truncate content for display with indicator."""
    if len(content) <= max_length:
        return content
    return content[:max_length] + f"\n[dim]... ({len(content) - max_length} more chars)[/dim]"
```

### 4.3 Staged Context Format

The staged context is already formatted text. Display as-is, but add metadata header:

```python
def _format_staged_context(self) -> str:
    """Format staged context for display."""
    if not self.staged_context:
        return self._empty_staged_message()

    # Parse metadata for header
    metadata = ContextParser.parse(self.staged_context)
    header_lines = []
    if metadata.entry_count:
        header_lines.append(f"Log Entries: {metadata.entry_count}")
    if metadata.log_group:
        header_lines.append(f"Log Group: {metadata.log_group}")
    if metadata.total_chars:
        header_lines.append(f"Size: {metadata.total_chars:,} chars (~{metadata.total_tokens:,} tokens)")

    header = "\n".join(header_lines) if header_lines else ""
    separator = "\n" + "─" * 50 + "\n" if header else ""

    return header + separator + self.staged_context
```

---

## 5. Performance Considerations

### 5.1 Large Conversation Histories

**Problem:** Conversation history can grow to 100+ messages with tool calls and results.

**Solution:**
1. Use `RichLog` widget (already implemented in current version)
2. RichLog uses virtual rendering - only visible lines are rendered
3. Writing content: Use `log_widget.write(formatted_content)` which streams efficiently

### 5.2 Memory Management

**Problem:** Copying large histories could cause memory spikes.

**Solution:**
1. Format content lazily when section is expanded
2. Cache formatted content for copy operation
3. Clear cached content when modal closes

### 5.3 Modal Load Time

**Problem:** Formatting large history on modal open could cause delay.

**Solution:**
1. Show modal immediately with loading state
2. Format and populate content in `on_mount()` async handler
3. Use existing pattern from current `ContextViewerScreen.on_mount()`

---

## 6. Copy Functionality

### 6.1 Copy Behavior

**Per-Section Copy Buttons:**
- Each section header has a small copy button
- Copies only that section's content

**Copy All Button (Footer):**
- Copies both sections with clear separators
- Format:

```
===== STAGED CONTEXT =====
[timestamp: 2026-02-19 10:30:45]

[staged content or "None"]

===== AGENT MEMORY =====
[message count: 12]

[formatted conversation history]
```

### 6.2 Copy Implementation

Use existing `pyperclip` pattern from current implementation:

```python
def _copy_to_clipboard(self, content: str, section_name: str) -> None:
    """Copy content to clipboard with user feedback."""
    try:
        import pyperclip
        pyperclip.copy(content)
        self.notify(f"{section_name} copied to clipboard!", severity="information", timeout=3)
    except ImportError:
        self.notify(
            "Clipboard not available. Content shown above for manual copy.",
            severity="warning",
            timeout=5,
        )
    except Exception as e:
        self.notify(f"Failed to copy: {str(e)}", severity="error", timeout=5)
```

---

## 7. Implementation Details

### 7.1 New Files/Changes

**Modified Files:**

1. **`src/logai/core/orchestrator.py`**
   - Add `get_conversation_history()` method (5 lines)

2. **`src/logai/ui/screens/context_viewer.py`**
   - Major refactor to support two sections
   - Add `Collapsible` widgets
   - Add conversation history formatting
   - Update copy functionality

3. **`src/logai/ui/screens/chat.py`**
   - Update `on_context_view_requested()` to pass both data sources

### 7.2 Class Structure

```python
@dataclass
class ContextViewerData:
    """Data container for context viewer modal."""
    staged_context: str | None
    conversation_history: list[dict[str, Any]]
    metadata: ContextMetadata  # Existing class


class ContextViewerScreen(ModalScreen[None]):
    """Enhanced modal with two-section layout."""

    def __init__(
        self,
        staged_context: str | None,
        conversation_history: list[dict[str, Any]],
        metadata: ContextMetadata,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.staged_context = staged_context or ""
        self.conversation_history = conversation_history
        self.metadata = metadata

        # Cached formatted content for copy operations
        self._formatted_staged: str | None = None
        self._formatted_history: str | None = None
```

### 7.3 Widget Hierarchy

```
ContextViewerScreen
├── Container (id="context-container")
│   ├── Static (id="context-header")  # "Context Viewer"
│   │
│   ├── VerticalScroll (id="sections-container")
│   │   ├── Collapsible (id="staged-section")
│   │   │   ├── CollapsibleTitle: "Staged Context (N items) [Copy]"
│   │   │   └── Contents
│   │   │       └── RichLog (id="staged-content")
│   │   │
│   │   └── Collapsible (id="memory-section")
│   │       ├── CollapsibleTitle: "Agent Memory (N messages) [Copy]"
│   │       └── Contents
│   │           └── RichLog (id="memory-content")
│   │
│   └── Horizontal (id="action-buttons")
│       ├── Button (id="copy-all-btn")
│       └── Button (id="close-btn")
```

---

## 8. Edge Cases

### 8.1 Empty States

| Staged Context | Agent Memory | Display Behavior |
|----------------|--------------|------------------|
| Empty | Empty | Both sections show helpful empty state messages |
| Has content | Empty | Staged shows content, Memory shows "Start a conversation..." |
| Empty | Has content | Staged shows "No logs staged...", Memory shows history |
| Has content | Has content | Both sections show content (default case) |

### 8.2 Very Long Tool Results

Tool results in conversation history can be extremely large (JSON with 100s of events).

**Handling:**
- Truncate tool result display to 2000 chars in formatted view
- Show `[truncated - X chars total]` indicator
- Full content still available via per-section copy button

### 8.3 Special Message Types

Handle all message types from orchestrator:

| Role | Example | Display Format |
|------|---------|----------------|
| `system` | System prompt | `[System] You are an expert...` |
| `user` | User query | `[User] Show me errors...` |
| `assistant` | Agent response | `[Assistant] I'll query...` |
| `assistant` (with tool_calls) | Tool invocation | `[Assistant]\n  [Tool Call] query_logs(...)` |
| `tool` | Tool result | `[Tool Result] (id) {...}` |

### 8.4 Malformed Messages

If a message lacks expected fields, display gracefully:

```python
role = msg.get("role", "unknown")
content = msg.get("content", "[no content]")
```

---

## 9. Testing Considerations

**Unit Tests:**
- `test_format_conversation_message()` for each role type
- `test_truncate_content()` with boundary cases
- `test_format_staged_context()` with metadata extraction

**Integration Tests:**
- Modal opens with empty states
- Modal opens with populated data
- Copy buttons work for each section
- Collapsible expand/collapse works

**Performance Tests:**
- Open modal with 100+ message history
- Scroll through large content without lag
- Copy large content without hanging

---

## 10. Implementation Steps for Jackie

### Step 1: Add Orchestrator Method (5 min)
Add `get_conversation_history()` to `orchestrator.py`

### Step 2: Update Modal Constructor (10 min)
- Update `ContextViewerScreen.__init__()` to accept conversation history
- Update `ChatScreen.on_context_view_requested()` to pass both data sources

### Step 3: Refactor Modal Layout (30 min)
- Replace single content area with two `Collapsible` sections
- Each section contains a `RichLog` widget
- Add per-section copy buttons to headers

### Step 4: Implement Formatters (20 min)
- `_format_staged_context()` - add metadata header
- `_format_conversation_message()` - role-based formatting
- `_format_conversation_history()` - iterate and format all messages

### Step 5: Update Copy Functionality (10 min)
- Per-section copy buttons
- "Copy All" button with separators

### Step 6: Handle Empty States (10 min)
- Helpful messages for empty staged context
- Helpful messages for empty conversation history

### Step 7: CSS Polish (15 min)
- Style collapsible headers
- Ensure proper spacing and colors
- Match existing modal aesthetic

### Step 8: Test & Debug (20 min)
- Test with empty states
- Test with populated data
- Test copy functionality
- Test performance with large history

**Total Estimated Time:** ~2 hours

---

## 11. Open Questions - RESOLVED

### Q1: How should ChatScreen access conversation history?
**Answer:** Add `get_conversation_history()` public method to orchestrator. Returns a copy of the list.

### Q2: What format should we use for displaying conversation history?
**Answer:** Role-tagged format with Rich markup. `[Role] Content` with color coding per role type.

### Q3: Should we truncate large histories?
**Answer:** No. Use RichLog's virtual rendering to handle large histories. Only truncate individual tool results >2000 chars for readability.

### Q4: Static snapshot or live updates?
**Answer:** Static snapshot captured when modal opens. User can close/reopen for fresh data.

---

## 12. Future Enhancements (Out of Scope)

- **Search within history:** Add search box to filter messages
- **Message timestamps:** Show when each message was sent
- **Token breakdown:** Show per-message token counts
- **Export to file:** Save full history to JSON/text file
- **Message highlighting:** Click message to see it in main chat

---

## Appendix A: Message Structure Reference

From `orchestrator.py`, conversation history messages have this structure:

```python
# User message
{"role": "user", "content": "Show me errors..."}

# Assistant message (plain)
{"role": "assistant", "content": "I found 47 errors..."}

# Assistant message (with tool calls)
{
    "role": "assistant",
    "content": "",  # Often empty when making tool calls
    "tool_calls": [
        {
            "id": "call_abc123",
            "function": {
                "name": "query_logs",
                "arguments": "{\"log_group\": \"/aws/lambda/auth\", ...}"
            }
        }
    ]
}

# Tool result message
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": "{\"count\": 47, \"events\": [...]}"  # JSON string
}

# System message (injected context)
{"role": "system", "content": "USER-SELECTED LOG ENTRIES..."}
```

---

## Appendix B: Collapsible Widget API

```python
from textual.widgets import Collapsible

# Basic usage
Collapsible(
    RichLog(id="content"),
    title="Section Title",
    collapsed=False,  # Start expanded
    id="section-id"
)

# Access title programmatically
collapsible.title = "Updated Title (5 items)"

# Check/set collapsed state
if collapsible.collapsed:
    collapsible.collapsed = False
```

---

**End of Design Document**
