# Design Document: Context Viewer Modal Feature

**Document Version:** 1.0
**Author:** Saanvi (Senior Software Architect)
**Date:** February 19, 2026
**Status:** Ready for Implementation

---

## Executive Summary

This design document specifies the implementation of a **Context Viewer Modal** feature for the LogAI observability assistant. The feature enables users to view the exact context the AI agent has in memory by clicking the "Context" label in the status bar. This provides critical debugging visibility to diagnose whether agent confusion stems from LogAI issues or LLM reasoning issues.

### Key Design Decisions
1. **Modal over inline display** - Provides full-screen context viewing without disrupting chat flow
2. **Click handler over dedicated button** - Leverages existing status bar real estate, follows established patterns
3. **Direct orchestrator access** - Uses `_pending_context_injection` directly rather than adding new API methods
4. **Callback pattern for modal** - Follows the recently-fixed pattern from `LogPreviewScreen`

### Estimated Implementation Time
- **MVP (Phase 1-3):** ~2 hours
- **Enhanced Features (Phase 4-5):** ~1 hour
- **Total:** ~3 hours

---

## 1. Architecture Design

### 1.1 Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ChatScreen                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Main Content Area                            │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │   │
│  │  │ Log Groups   │  │   Messages Container │  │   Tool Sidebar   │  │   │
│  │  │   Sidebar    │  │                      │  │                  │  │   │
│  │  └──────────────┘  └──────────────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        StatusFooter                                  │   │
│  │   [F1] ◀ Logs  [F2] Logs ▶  ...  │ Context: 25.5K/32K (80%) │ Model │   │
│  │                                    ▲                                 │   │
│  │                                    │ CLICK                           │   │
│  └────────────────────────────────────┼─────────────────────────────────┘   │
└───────────────────────────────────────┼─────────────────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────┐
                    │       ContextViewerScreen             │
                    │         (ModalScreen)                 │
                    │  ┌─────────────────────────────────┐  │
                    │  │      Context Metadata           │  │
                    │  │  • Size: 22,147 chars          │  │
                    │  │  • Entries: 83 logs            │  │
                    │  │  • Updated: 13:17:37           │  │
                    │  ├─────────────────────────────────┤  │
                    │  │      Context Content            │  │
                    │  │   (VerticalScroll)              │  │
                    │  │   USER-SELECTED LOG ENTRIES...  │  │
                    │  │   ...                           │  │
                    │  ├─────────────────────────────────┤  │
                    │  │  [Copy to Clipboard]  [Close]   │  │
                    │  └─────────────────────────────────┘  │
                    └───────────────────────────────────────┘
```

### 1.2 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                        │
└──────────────────────────────────────────────────────────────────────────────┘

1. USER CLICK
   StatusFooter (Context label)
        │
        ▼ [Click Event]
        │
2. MESSAGE EMISSION
   StatusFooter.post_message(ContextViewRequested())
        │
        ▼ [Message bubbles up]
        │
3. MESSAGE HANDLING
   ChatScreen.on_context_view_requested()
        │
        ├──▶ orchestrator._pending_context_injection  ──┐
        │                                                │
        ├──▶ orchestrator.conversation_history ─────────┤
        │                                                │
        └──▶ orchestrator.budget_tracker.get_usage() ───┤
                                                        │
                                                        ▼
4. MODAL CREATION                              ┌────────────────────┐
   ContextViewerScreen(                        │   Context Data     │
       context_text=...,                       │  ┌──────────────┐  │
       metadata=ContextMetadata(...)           │  │ pending_ctx  │  │
   )                                           │  │ history      │  │
        │                                      │  │ budget_info  │  │
        ▼                                      │  └──────────────┘  │
5. MODAL DISPLAY                               └────────────────────┘
   app.push_screen(modal, callback)
        │
        ▼
6. USER INTERACTION
   - View content
   - Copy to clipboard
   - Close (ESC or button)
        │
        ▼
7. MODAL DISMISS
   callback(None)  # No data returned for context viewer
```

### 1.3 New Files to Create

| File | Purpose |
|------|---------|
| `src/logai/ui/screens/context_viewer.py` | New `ContextViewerScreen` modal component |
| `tests/unit/ui/test_context_viewer.py` | Unit tests for the context viewer |

### 1.4 Files to Modify

| File | Modifications |
|------|---------------|
| `src/logai/ui/widgets/status_footer.py` | Add clickable context label, emit `ContextViewRequested` message |
| `src/logai/ui/widgets/messages.py` | Add `ContextViewRequested` message class |
| `src/logai/ui/screens/chat.py` | Handle `ContextViewRequested`, open modal with callback |
| `src/logai/ui/screens/__init__.py` | Export `ContextViewerScreen` |

### 1.5 Dependencies

```
ContextViewerScreen
    ├── textual.screen.ModalScreen
    ├── textual.containers.VerticalScroll, Container, Horizontal
    ├── textual.widgets.Static, Button
    └── textual.binding.Binding

StatusFooter (modifications)
    └── textual.widgets.Static (with on_click handler)

ChatScreen (modifications)
    └── LLMOrchestrator (for context access)
```

---

## 2. Component Design

### 2.1 ContextViewerScreen (New Component)

**File Location:** `src/logai/ui/screens/context_viewer.py`

#### 2.1.1 Class Structure

```python
"""Context viewer modal screen for displaying agent context."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

logger = logging.getLogger(__name__)


@dataclass
class ContextMetadata:
    """Metadata about the current context."""

    total_chars: int
    total_tokens: int
    entry_count: int | None  # None if unable to parse
    log_group: str | None    # None if no log group found
    last_updated: datetime
    context_type: str        # "user-selected-logs", "cache-guidance", "empty", "unknown"


class ContextViewerScreen(ModalScreen[None]):
    """
    Modal screen for viewing the current agent context.

    Displays:
    - Context metadata (size, entry count, log group)
    - Full context text in scrollable container
    - Copy to clipboard functionality
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("c", "copy", "Copy", show=True),
    ]

    DEFAULT_CSS = """
    ContextViewerScreen {
        align: center middle;
    }

    #context-container {
        width: 90%;
        height: 85%;
        max-width: 120;
        background: $panel;
        border: thick $primary;
        padding: 0;
        layout: vertical;
    }

    #context-header {
        height: 3;
        background: $primary;
        color: $text;
        padding: 1 2;
        text-style: bold;
        width: 100%;
    }

    #metadata-section {
        height: auto;
        padding: 1 2;
        background: $surface;
        border-bottom: solid $surface-darken-2;
    }

    .metadata-row {
        height: auto;
        padding: 0 0 0 1;
        color: $text-muted;
    }

    .metadata-label {
        color: $accent;
        text-style: bold;
    }

    #context-content {
        height: 1fr;
        background: $panel;
        padding: 1 2;
    }

    #context-text {
        width: 100%;
        height: auto;
    }

    .empty-context {
        color: $text-muted;
        text-style: italic;
        text-align: center;
        padding: 4;
    }

    #action-buttons {
        height: 3;
        layout: horizontal;
        align: center middle;
        padding: 0 1;
        background: $surface;
    }

    #action-buttons Button {
        margin: 0 1;
    }

    #copy-btn {
        background: $accent;
    }
    """

    def __init__(
        self,
        context_text: str | None,
        metadata: ContextMetadata,
        **kwargs: Any,
    ) -> None:
        """
        Initialize context viewer screen.

        Args:
            context_text: The full context text (None if no context)
            metadata: Parsed metadata about the context
            **kwargs: Additional arguments for ModalScreen
        """
        super().__init__(**kwargs)
        self.context_text = context_text or ""
        self.metadata = metadata
        self._copy_confirmed = False

    def compose(self) -> ComposeResult:
        """Compose the context viewer layout."""
        with Container(id="context-container"):
            # Header
            yield Static("Context Viewer", id="context-header")

            # Metadata section
            with Container(id="metadata-section"):
                yield Static(self._format_metadata(), id="metadata-display")

            # Scrollable content
            with VerticalScroll(id="context-content"):
                if self.context_text:
                    yield Static(self.context_text, id="context-text")
                else:
                    yield Static(
                        "No context currently injected.\n\n"
                        "Context is added when you:\n"
                        "• Select log entries from the log preview\n"
                        "• Use tools that return cached results\n\n"
                        "Try double-clicking a log group in the sidebar\n"
                        "and selecting some entries to add to context.",
                        classes="empty-context",
                    )

            # Action buttons
            with Horizontal(id="action-buttons"):
                yield Button(
                    "Copy to Clipboard",
                    id="copy-btn",
                    variant="primary",
                    disabled=not self.context_text,
                )
                yield Button("Close", id="close-btn", variant="default")

    def _format_metadata(self) -> str:
        """Format metadata for display."""
        lines = []

        # Size information
        lines.append(f"[bold cyan]Total Size:[/bold cyan] {self.metadata.total_chars:,} characters")

        # Token count
        if self.metadata.total_tokens > 0:
            lines.append(f"[bold cyan]Estimated Tokens:[/bold cyan] ~{self.metadata.total_tokens:,}")

        # Entry count (if parseable)
        if self.metadata.entry_count is not None:
            lines.append(f"[bold cyan]Log Entries:[/bold cyan] {self.metadata.entry_count}")

        # Log group (if found)
        if self.metadata.log_group:
            lines.append(f"[bold cyan]Log Group:[/bold cyan] {self.metadata.log_group}")

        # Context type
        type_display = self._get_type_display(self.metadata.context_type)
        lines.append(f"[bold cyan]Context Type:[/bold cyan] {type_display}")

        # Last updated
        time_str = self.metadata.last_updated.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[bold cyan]Last Updated:[/bold cyan] {time_str}")

        return "\n".join(lines)

    def _get_type_display(self, context_type: str) -> str:
        """Get human-readable context type."""
        type_map = {
            "user-selected-logs": "User-Selected Log Entries",
            "cache-guidance": "Cached Result Guidance",
            "mixed": "Mixed (Logs + Cache)",
            "empty": "Empty (No Context)",
            "unknown": "Unknown Format",
        }
        return type_map.get(context_type, context_type)

    @on(Button.Pressed, "#copy-btn")
    def on_copy_pressed(self) -> None:
        """Copy context to clipboard."""
        if self.context_text:
            try:
                import pyperclip
                pyperclip.copy(self.context_text)
                self.notify("Context copied to clipboard!", severity="information", timeout=3)
                self._copy_confirmed = True
            except ImportError:
                # pyperclip not available, try alternative
                self._copy_via_app()
            except Exception as e:
                logger.warning(f"Failed to copy to clipboard: {e}")
                self.notify(
                    f"Failed to copy: {str(e)}",
                    severity="error",
                    timeout=5,
                )

    def _copy_via_app(self) -> None:
        """Attempt to copy via app clipboard if available."""
        try:
            # Textual apps may have clipboard access
            if hasattr(self.app, "copy_to_clipboard"):
                self.app.copy_to_clipboard(self.context_text)
                self.notify("Context copied to clipboard!", severity="information", timeout=3)
            else:
                self.notify(
                    "Clipboard not available. Context shown above for manual copy.",
                    severity="warning",
                    timeout=5,
                )
        except Exception as e:
            logger.warning(f"App clipboard failed: {e}")
            self.notify(
                "Clipboard not available in this environment.",
                severity="warning",
                timeout=5,
            )

    @on(Button.Pressed, "#close-btn")
    def on_close_pressed(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Handle escape key - close modal."""
        self.dismiss(None)

    def action_copy(self) -> None:
        """Handle 'c' key - copy to clipboard."""
        self.on_copy_pressed()


class ContextParser:
    """Utility class for parsing context text to extract metadata."""

    # Regex patterns for extracting metadata
    ENTRY_COUNT_PATTERN = re.compile(r"Entry Count:\s*(\d+)", re.IGNORECASE)
    TOTAL_ENTRIES_PATTERN = re.compile(r"Total Entries:\s*(\d+)", re.IGNORECASE)
    LOG_GROUP_PATTERN = re.compile(r"Log Group:\s*([^\n]+)", re.IGNORECASE)
    ENTRY_N_OF_M_PATTERN = re.compile(r"Entry \d+ of (\d+):", re.IGNORECASE)

    @classmethod
    def parse(cls, context_text: str | None) -> ContextMetadata:
        """
        Parse context text to extract metadata.

        Args:
            context_text: Raw context text

        Returns:
            ContextMetadata with parsed values
        """
        if not context_text:
            return ContextMetadata(
                total_chars=0,
                total_tokens=0,
                entry_count=None,
                log_group=None,
                last_updated=datetime.now(),
                context_type="empty",
            )

        # Calculate basic metrics
        total_chars = len(context_text)
        # Rough token estimate: ~4 chars per token for English text
        total_tokens = total_chars // 4

        # Determine context type
        context_type = cls._detect_context_type(context_text)

        # Extract entry count
        entry_count = cls._extract_entry_count(context_text)

        # Extract log group
        log_group = cls._extract_log_group(context_text)

        return ContextMetadata(
            total_chars=total_chars,
            total_tokens=total_tokens,
            entry_count=entry_count,
            log_group=log_group,
            last_updated=datetime.now(),
            context_type=context_type,
        )

    @classmethod
    def _detect_context_type(cls, text: str) -> str:
        """Detect the type of context."""
        has_user_logs = "USER-SELECTED LOG ENTRIES" in text
        has_cache_guidance = "CACHED RESULT INFORMATION" in text or "cache_id" in text.lower()

        if has_user_logs and has_cache_guidance:
            return "mixed"
        elif has_user_logs:
            return "user-selected-logs"
        elif has_cache_guidance:
            return "cache-guidance"
        else:
            return "unknown"

    @classmethod
    def _extract_entry_count(cls, text: str) -> int | None:
        """Extract log entry count from context text."""
        # Try "Entry Count: X" format first
        match = cls.ENTRY_COUNT_PATTERN.search(text)
        if match:
            return int(match.group(1))

        # Try "Total Entries: X" format
        match = cls.TOTAL_ENTRIES_PATTERN.search(text)
        if match:
            return int(match.group(1))

        # Try "Entry N of M:" format (look for highest M)
        matches = cls.ENTRY_N_OF_M_PATTERN.findall(text)
        if matches:
            return max(int(m) for m in matches)

        # Fallback: count JSON objects in array (rough estimate)
        # Look for patterns like {"timestamp": which indicate log entries
        entry_markers = text.count('"timestamp":')
        if entry_markers > 0:
            return entry_markers

        return None

    @classmethod
    def _extract_log_group(cls, text: str) -> str | None:
        """Extract log group name from context text."""
        match = cls.LOG_GROUP_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        return None
```

### 2.2 StatusFooter Modifications

**File:** `src/logai/ui/widgets/status_footer.py`

#### 2.2.1 Changes Required

```python
# Add import at top
from textual.message import Message

# Add inside StatusFooter class:

class ContextViewRequested(Message):
    """Emitted when user clicks the context label to view context."""
    pass

# Modify _render_status_context() to wrap context info in clickable Static
# OR add a new clickable widget for context display

# Add click handler method:
def on_context_click(self, event: Click) -> None:
    """Handle click on context label."""
    self.post_message(self.ContextViewRequested())
```

#### 2.2.2 Implementation Approach

Since `StatusFooter` uses a single `Static` widget for the status/context display, we have two options:

**Option A (Recommended): Add separate clickable widget for context**
```python
# In compose(), replace single Static with:
yield Static(self._render_status_only(), id="status-display")
yield ContextLabel(id="context-label")  # New clickable widget
```

**Option B: Make entire status bar clickable and detect region**
- More complex, requires hit-testing
- Not recommended

We'll use **Option A** for cleaner separation.

#### 2.2.3 New ContextLabel Widget

```python
class ContextLabel(Static):
    """Clickable label displaying context usage."""

    DEFAULT_CSS = """
    ContextLabel {
        width: auto;
        height: 1;
        padding: 0 1;
    }

    ContextLabel:hover {
        background: $surface-lighten-1;
        cursor: pointer;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("Context: --", **kwargs)

    def on_click(self) -> None:
        """Handle click - emit request to view context."""
        self.post_message(StatusFooter.ContextViewRequested())

    def update_display(
        self,
        utilization_pct: float,
        used_tokens: int,
        total_tokens: int,
    ) -> None:
        """Update the context display."""
        # ... formatting logic from existing _render_status_context ...
```

### 2.3 ChatScreen Modifications

**File:** `src/logai/ui/screens/chat.py`

#### 2.3.1 New Handler Method

```python
# Add import at top
from logai.ui.screens.context_viewer import ContextViewerScreen, ContextParser

# Add handler method in ChatScreen class:

@on(StatusFooter.ContextViewRequested)
async def on_context_view_requested(
    self, event: StatusFooter.ContextViewRequested
) -> None:
    """
    Handle request to view context from status bar click.

    Args:
        event: Context view request event
    """
    try:
        # Get current context from orchestrator
        context_text = self.orchestrator._pending_context_injection

        # Parse metadata
        metadata = ContextParser.parse(context_text)

        # Update metadata with actual token count from budget tracker
        if hasattr(self.orchestrator, "budget_tracker"):
            usage = self.orchestrator.budget_tracker.get_usage()
            metadata.total_tokens = usage.total_tokens

        # Define callback (follows pattern from log preview fix)
        async def handle_context_viewer_close(result: None) -> None:
            """Handle context viewer modal close."""
            logger.debug("Context viewer modal closed")

        # Show modal with callback
        self.app.push_screen(
            ContextViewerScreen(
                context_text=context_text,
                metadata=metadata,
            ),
            handle_context_viewer_close,
        )

    except Exception as e:
        logger.error(f"Failed to open context viewer: {e}", exc_info=True)
        self.notify(
            f"Failed to open context viewer: {str(e)}",
            severity="error",
            timeout=5,
        )
```

### 2.4 Messages Module Update

**File:** `src/logai/ui/widgets/messages.py`

```python
# Add at end of file:

from textual.message import Message

class ContextViewRequested(Message):
    """Message emitted when user requests to view the agent context."""
    pass
```

**Note:** Alternatively, define this in `status_footer.py` as a nested class for better cohesion.

---

## 3. UI/UX Design

### 3.1 Modal Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Context Viewer                                              [X] │
├─────────────────────────────────────────────────────────────────┤
│ Total Size: 22,147 characters                                   │
│ Estimated Tokens: ~5,537                                        │
│ Log Entries: 83                                                 │
│ Log Group: /aws/lambda/my-function                             │
│ Context Type: User-Selected Log Entries                         │
│ Last Updated: 2026-02-19 13:17:37                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ USER-SELECTED LOG ENTRIES for analysis:                        │
│                                                                 │
│ Log Group: /aws/lambda/my-function                             │
│ Entry Count: 83                                                │
│                                                                 │
│ The user has specifically selected these log entries for       │
│ your analysis:                                                  │
│                                                                 │
│ ```json                                                         │
│ [                                                               │
│   {                                                             │
│     "timestamp": "2026-02-19 13:15:23.388",                    │
│     "message": "START RequestId: c16be09d...",                 │
│     "log_stream": "2026/02/19/[$LATEST]abc123"                 │
│   },                                                            │
│   ...                                                           │
│ ]                                                               │
│ ```                                                             │
│                                                                 │
│ [Scrollable - more content below...]                           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│              [Copy to Clipboard]      [Close]                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Empty State

```
┌─────────────────────────────────────────────────────────────────┐
│ Context Viewer                                              [X] │
├─────────────────────────────────────────────────────────────────┤
│ Total Size: 0 characters                                        │
│ Context Type: Empty (No Context)                                │
│ Last Updated: 2026-02-19 13:17:37                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                                                                 │
│           No context currently injected.                        │
│                                                                 │
│           Context is added when you:                            │
│           • Select log entries from the log preview             │
│           • Use tools that return cached results                │
│                                                                 │
│           Try double-clicking a log group in the sidebar        │
│           and selecting some entries to add to context.         │
│                                                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│              [Copy to Clipboard]      [Close]                   │
│                  (disabled)                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Styling Details

| Element | Style |
|---------|-------|
| Modal border | `thick $primary` (blue) |
| Header background | `$primary` (blue) |
| Metadata section | `$surface` (slightly darker) |
| Metadata labels | `$accent` (cyan), bold |
| Content area | `$panel` (default background) |
| Button bar | `$surface` |
| Copy button | `$accent` (cyan) primary variant |
| Close button | Default variant |
| Hover on context label | `$surface-lighten-1`, cursor: pointer |

### 3.4 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `ESC` | Close modal |
| `C` | Copy context to clipboard |

---

## 4. Data Parsing Strategy

### 4.1 Context Text Format Recognition

The context can have several formats:

#### Format 1: User-Selected Log Entries
```
USER-SELECTED LOG ENTRIES for analysis:

Log Group: /aws/lambda/my-function
Entry Count: 83

The user has specifically selected these log entries for your analysis:

```json
[
  {"timestamp": "...", "message": "...", "log_stream": "..."},
  ...
]
```
```

#### Format 2: Cache Guidance
```
SYSTEM INSTRUCTION: The previous tool call returned a large result...

CACHED RESULT INFORMATION:
- Cache ID: abc123
- Total events cached: 150
```

#### Format 3: Mixed (Both)
```
[Cache guidance section]

---

[User-selected logs section]
```

### 4.2 Parsing Implementation

```python
class ContextParser:
    """Utility class for parsing context text."""

    @classmethod
    def parse(cls, context_text: str | None) -> ContextMetadata:
        """Parse context text to extract metadata."""

        if not context_text:
            return cls._empty_metadata()

        return ContextMetadata(
            total_chars=len(context_text),
            total_tokens=len(context_text) // 4,  # Rough estimate
            entry_count=cls._extract_entry_count(context_text),
            log_group=cls._extract_log_group(context_text),
            last_updated=datetime.now(),
            context_type=cls._detect_type(context_text),
        )

    @classmethod
    def _extract_entry_count(cls, text: str) -> int | None:
        """Extract entry count using multiple strategies."""

        # Strategy 1: Look for "Entry Count: X"
        match = re.search(r"Entry Count:\s*(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Strategy 2: Look for "Total Entries: X"
        match = re.search(r"Total Entries:\s*(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Strategy 3: Count "timestamp" occurrences in JSON
        count = text.count('"timestamp":')
        if count > 0:
            return count

        return None  # Unable to determine
```

### 4.3 Graceful Fallbacks

| Scenario | Fallback Behavior |
|----------|-------------------|
| No entry count found | Display "Entry count: Unknown" |
| No log group found | Omit log group line |
| Malformed JSON | Show raw text, note parsing failure |
| Very large context | Display with warning about size |

---

## 5. Error Handling

### 5.1 Error Scenarios and Responses

| Error | User Impact | Handling |
|-------|-------------|----------|
| Empty context | No data to display | Show helpful empty state message |
| Malformed context | Parsing fails | Show raw text with "Unable to parse metadata" note |
| Large context (>100KB) | Potential UI lag | Display with size warning, consider lazy loading |
| Orchestrator access error | Cannot retrieve context | Show error notification, log details |
| Clipboard copy fails | Cannot copy | Show alternative message with instructions |

### 5.2 Error Handling Code

```python
async def on_context_view_requested(self, event: StatusFooter.ContextViewRequested) -> None:
    """Handle context view request with comprehensive error handling."""
    try:
        # Attempt to get context
        context_text = self._get_context_safely()
        metadata = ContextParser.parse(context_text)

        # Validate context size
        if metadata.total_chars > 100_000:
            self.notify(
                "Warning: Large context may display slowly",
                severity="warning",
                timeout=3,
            )

        # Show modal
        self.app.push_screen(
            ContextViewerScreen(context_text=context_text, metadata=metadata),
            self._handle_context_viewer_close,
        )

    except AttributeError as e:
        logger.error(f"Orchestrator missing expected attribute: {e}")
        self.notify(
            "Context viewer not available - orchestrator not initialized",
            severity="error",
            timeout=5,
        )
    except Exception as e:
        logger.error(f"Failed to open context viewer: {e}", exc_info=True)
        self.notify(
            f"Failed to open context viewer: {str(e)}",
            severity="error",
            timeout=5,
        )

def _get_context_safely(self) -> str | None:
    """Safely retrieve context with error handling."""
    try:
        return self.orchestrator._pending_context_injection
    except Exception:
        return None
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File:** `tests/unit/ui/test_context_viewer.py`

```python
"""Unit tests for context viewer feature."""

class TestContextMetadata:
    """Tests for ContextMetadata dataclass."""

    def test_metadata_creation(self):
        """Test basic metadata creation."""

    def test_metadata_with_none_values(self):
        """Test metadata handles None values."""


class TestContextParser:
    """Tests for ContextParser utility."""

    def test_parse_empty_context(self):
        """Parser handles None/empty context."""

    def test_parse_user_selected_logs(self):
        """Parser extracts data from user-selected logs format."""

    def test_parse_cache_guidance(self):
        """Parser extracts data from cache guidance format."""

    def test_parse_mixed_context(self):
        """Parser handles mixed context types."""

    def test_extract_entry_count_entry_count_format(self):
        """Extract count from 'Entry Count: X' format."""

    def test_extract_entry_count_total_entries_format(self):
        """Extract count from 'Total Entries: X' format."""

    def test_extract_entry_count_timestamp_counting(self):
        """Extract count by counting timestamp occurrences."""

    def test_extract_entry_count_unparseable(self):
        """Return None for unparseable context."""

    def test_extract_log_group(self):
        """Extract log group name from context."""

    def test_detect_context_type_user_logs(self):
        """Detect user-selected-logs type."""

    def test_detect_context_type_cache_guidance(self):
        """Detect cache-guidance type."""

    def test_detect_context_type_mixed(self):
        """Detect mixed context type."""

    def test_detect_context_type_unknown(self):
        """Return unknown for unrecognized format."""


class TestContextViewerScreen:
    """Tests for ContextViewerScreen modal."""

    def test_initialization_with_context(self):
        """Screen initializes with context text and metadata."""

    def test_initialization_without_context(self):
        """Screen handles None context gracefully."""

    def test_compose_with_context(self):
        """Compose generates correct widgets when context exists."""

    def test_compose_without_context(self):
        """Compose generates empty state when no context."""

    def test_format_metadata_all_fields(self):
        """Metadata formatting includes all fields."""

    def test_format_metadata_partial_fields(self):
        """Metadata formatting handles missing fields."""

    def test_action_close(self):
        """ESC key closes modal."""

    def test_close_button_click(self):
        """Close button dismisses modal."""

    def test_copy_button_disabled_when_empty(self):
        """Copy button is disabled when no context."""

    def test_copy_button_enabled_when_context_exists(self):
        """Copy button is enabled when context exists."""


class TestStatusFooterContextClick:
    """Tests for StatusFooter context click functionality."""

    def test_context_label_click_emits_message(self):
        """Click on context label emits ContextViewRequested."""

    def test_context_label_hover_style(self):
        """Context label shows hover state."""


class TestChatScreenContextHandler:
    """Tests for ChatScreen context view handling."""

    def test_handler_opens_modal(self):
        """Handler opens ContextViewerScreen modal."""

    def test_handler_passes_correct_context(self):
        """Handler passes orchestrator context to modal."""

    def test_handler_uses_callback_pattern(self):
        """Handler uses callback pattern (2 args to push_screen)."""

    def test_handler_handles_missing_orchestrator(self):
        """Handler handles missing orchestrator gracefully."""

    def test_handler_handles_orchestrator_error(self):
        """Handler handles orchestrator access error."""
```

### 6.2 Integration Tests

**File:** `tests/integration/test_context_viewer_integration.py`

```python
"""Integration tests for context viewer feature."""

class TestContextViewerIntegration:
    """End-to-end tests for context viewer."""

    @pytest.mark.asyncio
    async def test_click_status_bar_opens_modal(self):
        """Clicking context in status bar opens modal."""

    @pytest.mark.asyncio
    async def test_modal_displays_injected_context(self):
        """Modal displays context after log injection."""

    @pytest.mark.asyncio
    async def test_modal_displays_empty_state_initially(self):
        """Modal displays empty state before any context."""

    @pytest.mark.asyncio
    async def test_modal_updates_after_context_change(self):
        """Opening modal again shows updated context."""

    @pytest.mark.asyncio
    async def test_copy_functionality(self):
        """Copy button copies context to clipboard."""

    @pytest.mark.asyncio
    async def test_escape_closes_modal(self):
        """ESC key closes the modal."""
```

### 6.3 Manual Testing Scenarios

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Empty context | 1. Start app fresh<br>2. Click context label | Empty state message displayed |
| With user-selected logs | 1. Double-click log group<br>2. Select entries<br>3. Click context label | Context shown with entry count |
| Large context | 1. Select 100 entries<br>2. Click context label | Context displayed, may show size warning |
| Copy functionality | 1. Open context viewer<br>2. Click Copy | Notification confirms copy |
| Keyboard shortcuts | 1. Open viewer<br>2. Press ESC<br>3. Reopen<br>4. Press C | ESC closes, C copies |
| Hover effect | Hover over context label | Visual feedback (background change) |

---

## 7. Implementation Phases

### Phase 1: Create ContextViewerScreen Modal (45 min)

**Tasks:**
1. Create `src/logai/ui/screens/context_viewer.py`
2. Implement `ContextMetadata` dataclass
3. Implement `ContextParser` utility class
4. Implement `ContextViewerScreen` modal
   - `compose()` method
   - Metadata display
   - Scrollable content area
   - Action buttons
5. Add CSS styling
6. Implement close functionality (ESC, button)

**Definition of Done:**
- [ ] Modal can be instantiated with context text and metadata
- [ ] Modal displays metadata section
- [ ] Modal displays context in scrollable container
- [ ] Modal displays empty state when no context
- [ ] Close button and ESC key dismiss modal

### Phase 2: Add Status Bar Click Handler (30 min)

**Tasks:**
1. Modify `StatusFooter` to add clickable context label
2. Add `ContextViewRequested` message class
3. Implement click handler that emits message
4. Add hover styling for visual feedback
5. Update `__init__.py` exports if needed

**Definition of Done:**
- [ ] Context label in status bar is clickable
- [ ] Click emits `ContextViewRequested` message
- [ ] Hover shows visual feedback
- [ ] Status bar still displays context usage correctly

### Phase 3: Integrate with ChatScreen (30 min)

**Tasks:**
1. Add message handler `on_context_view_requested`
2. Retrieve context from orchestrator
3. Parse metadata using `ContextParser`
4. Open modal with callback pattern
5. Add error handling
6. Update `__init__.py` exports

**Definition of Done:**
- [ ] Clicking context label opens modal
- [ ] Modal displays current orchestrator context
- [ ] Modal displays parsed metadata
- [ ] Errors are handled gracefully with notifications
- [ ] Callback pattern matches log preview pattern

### Phase 4: Add Metadata Parsing (20 min)

**Tasks:**
1. Implement entry count extraction (multiple formats)
2. Implement log group extraction
3. Implement context type detection
4. Add fallback handling for unparseable context
5. Connect to budget tracker for accurate token count

**Definition of Done:**
- [ ] Entry count extracted from various formats
- [ ] Log group name extracted
- [ ] Context type correctly detected
- [ ] Unparseable content handled gracefully

### Phase 5: Implement Copy Functionality (15 min)

**Tasks:**
1. Add pyperclip or alternative clipboard handling
2. Implement copy button handler
3. Add keyboard shortcut (C key)
4. Add success/error notifications
5. Handle clipboard unavailable scenario

**Definition of Done:**
- [ ] Copy button copies context to clipboard
- [ ] 'C' key copies context
- [ ] Success notification shown
- [ ] Error handled gracefully if clipboard unavailable

### Phase 6: Testing & Documentation (30 min)

**Tasks:**
1. Write unit tests for `ContextParser`
2. Write unit tests for `ContextViewerScreen`
3. Write unit tests for click handler
4. Write integration tests
5. Update module `__init__.py` exports
6. Add docstrings and inline comments

**Definition of Done:**
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Code coverage adequate
- [ ] Documentation complete

---

## 8. Open Questions & Recommendations

### Q1: Should we show historical context or only current?

**Recommendation: Only current (MVP)**

**Rationale:**
- The `_pending_context_injection` field only holds current pending context
- Historical context would require significant changes to orchestrator
- MVP should focus on solving the immediate debugging need
- Can add history view in future iteration

**Implementation:** Show only `_pending_context_injection`

### Q2: Should we show system prompt in addition to user context?

**Recommendation: No (MVP)**

**Rationale:**
- System prompt is large (~2KB) and mostly static
- User's primary concern is injected context (logs)
- System prompt adds visual noise
- Can be added as optional "Show System Prompt" toggle later

**Implementation:** Only show injected context, not system prompt

### Q3: Should we display message history in addition to injected context?

**Recommendation: No (MVP)**

**Rationale:**
- Message history is visible in the chat panel
- Context viewer focuses on "hidden" context (injected logs)
- Displaying history would be redundant
- Consider as Phase 2 enhancement with "Show Full Context" option

**Implementation:** Only show `_pending_context_injection`

### Q4: How to handle context that's too large to display?

**Recommendation: Display with warning, lazy loading in Phase 2**

**Rationale:**
- Most contexts will be under 50KB (parseable)
- Very large contexts (>100KB) rare but possible
- Initial implementation: show warning, display anyway
- Phase 2: implement virtual scrolling or truncation with "Load More"

**Implementation:**
```python
if metadata.total_chars > 100_000:
    self.notify("Warning: Large context may display slowly", severity="warning")
# Display anyway - let Textual's VerticalScroll handle it
```

---

## 9. Alternative Approaches Considered

### 9.1 Modal vs Inline Display

| Approach | Pros | Cons |
|----------|------|------|
| **Modal (Chosen)** | Full screen space, follows existing patterns, clear focus | Blocks main UI temporarily |
| Inline Sidebar | Always visible, no mode switch | Limited space, competes with other sidebars |
| Split View | View while chatting | Complex layout changes, screen real estate |

**Decision:** Modal aligns with existing patterns (`LogPreviewScreen`) and provides sufficient space for long contexts.

### 9.2 Click Handler vs Dedicated Button

| Approach | Pros | Cons |
|----------|------|------|
| **Click Handler (Chosen)** | No additional UI element, leverages existing label | Discoverability lower |
| Dedicated Button | More discoverable | Uses precious footer space |
| Context Menu | Right-click familiar | Not standard in TUI |

**Decision:** Click handler reuses existing UI element. Hover state provides discoverability hint.

### 9.3 Direct Orchestrator Access vs New API Method

| Approach | Pros | Cons |
|----------|------|------|
| **Direct Access (Chosen)** | No orchestrator changes needed, quick to implement | Accesses "private" attribute |
| New `get_current_context()` | Clean API, encapsulation | More changes, review required |
| Event-based | Loosely coupled | Over-engineering for this use case |

**Decision:** Direct access to `_pending_context_injection` is acceptable for UI<->Orchestrator communication in same process. Document the coupling.

---

## 10. Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large context causes UI lag | Medium | Low | Add size warning, consider lazy loading in Phase 2 |
| Context format changes break parsing | Low | Medium | Parser returns graceful defaults, raw text always displayed |
| Clipboard not available in all terminals | Medium | Low | Multiple fallback methods, helpful error message |
| Users don't discover click behavior | Medium | Low | Hover effect provides hint, can add tooltip in future |
| Breaking changes to orchestrator | Low | High | Keep coupling minimal, document dependency |

---

## 11. Success Criteria

| Criteria | Measurement | Target |
|----------|-------------|--------|
| Feature completeness | All MVP tasks done | 100% |
| Test coverage | Unit test coverage | >80% |
| Performance | Modal open time | <200ms |
| Usability | Users can view context | Yes |
| Usability | Users can determine entry count | Yes |
| Code quality | Code review score | 9+/10 |
| No regressions | Existing tests pass | 100% |

---

## 12. Appendix

### A. Sample Context Formats

#### A.1 User-Selected Log Entries Format
```
USER-SELECTED LOG ENTRIES for analysis:

Log Group: /aws/lambda/my-function
Entry Count: 83

The user has specifically selected these log entries for your analysis:

```json
[
  {
    "timestamp": "2026-02-19 13:15:23.388",
    "message": "START RequestId: c16be09d-xxxx-xxxx-xxxx-xxxxxxxxxxxx Version: $LATEST",
    "log_stream": "2026/02/19/[$LATEST]abc123"
  },
  {
    "timestamp": "2026-02-19 13:15:23.456",
    "message": "Processing event: {\"key\": \"value\"}",
    "log_stream": "2026/02/19/[$LATEST]abc123"
  }
]
```

YOU MUST analyze these 83 log entries. Do NOT ask for a log group to search.
```

#### A.2 Cache Guidance Format
```
SYSTEM INSTRUCTION: The previous tool call returned a large result that was automatically cached.

CACHED RESULT INFORMATION:
- Cache ID: abc123def456
- Total events cached: 150

You MUST now fetch chunks to show the user actual log events:

STEP 1: Fetch first chunk
Call fetch_cached_result_chunk with these parameters:
- cache_id: abc123def456 (use this exact value)
- offset: 0
- limit: 50

DO NOT just acknowledge the cache - fetch and show the user actual events.
```

### B. File Change Summary

| File | Type | Changes |
|------|------|---------|
| `src/logai/ui/screens/context_viewer.py` | New | Full implementation |
| `src/logai/ui/screens/__init__.py` | Modify | Add export |
| `src/logai/ui/widgets/status_footer.py` | Modify | Add click handler |
| `src/logai/ui/screens/chat.py` | Modify | Add handler |
| `tests/unit/ui/test_context_viewer.py` | New | Unit tests |
| `tests/integration/test_context_viewer_integration.py` | New | Integration tests |

---

**Document prepared by:** Saanvi, Senior Software Architect
**Review requested from:** George (TPM), Jackie (Implementation)
**Next steps:** Implementation by Jackie per Phase breakdown
