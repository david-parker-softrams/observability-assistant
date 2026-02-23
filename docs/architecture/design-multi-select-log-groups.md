# Multi-Select Log Groups Feature - Comprehensive Design Document

**Author**: Saanvi (Senior Software Architect)
**Date**: February 20, 2026
**Status**: Ready for Implementation
**Version**: 1.0
**Requirements**: `george-scratch/requirements-multi-select-log-groups.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [UI/UX Design](#3-uiux-design)
4. [Event Handling Design](#4-event-handling-design)
5. [Selection State Management](#5-selection-state-management)
6. [Agent Integration Design](#6-agent-integration-design)
7. [Technical Implementation Details](#7-technical-implementation-details)
8. [Testing Strategy](#8-testing-strategy)
9. [Implementation Plan](#9-implementation-plan)
10. [Questions & Decisions](#10-questions--decisions)
11. [Appendix: Event Flow Diagrams](#11-appendix-event-flow-diagrams)

---

## 1. Executive Summary

### Feature Overview

The Multi-Select Log Groups feature enables users to select one or more log groups in the sidebar using standard OS selection patterns (click, Ctrl/Cmd-click). The agent will automatically be aware of which groups are selected, allowing natural language queries like "search these for errors" without explicit references to "selected" or "highlighted" groups.

### User Value Proposition

| Problem | Solution |
|---------|----------|
| Users must type out full log group names | Click to select, agent knows the target |
| Searching multiple groups requires listing them all | Ctrl-click to multi-select, say "search these" |
| No visual indicator of focus | Clear selected state with counter |
| Agent doesn't know user's intent | Context injection makes agent aware of selection |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single-click selects** | Standard OS behavior - intuitive |
| **Ctrl/Cmd-click for multi-select** | Universal selection pattern users expect |
| **Double-click preserved for preview** | Existing functionality must not break |
| **Selection counter in header** | At-a-glance feedback without clutter |
| **Context injection via system message** | Proven pattern in existing codebase |
| **Selection state in sidebar widget** | Keeps state close to UI, simple architecture |
| **300ms click delay for double-click detection** | Standard OS timing, prevents false triggers |

### Files to Modify

| File | Changes |
|------|---------|
| `src/logai/ui/widgets/log_groups_sidebar.py` | Selection state, click handling, CSS, counter |
| `src/logai/ui/screens/chat.py` | Query selection before sending to orchestrator |
| `src/logai/core/orchestrator.py` | Updated system prompt for selected groups context |

### New Components

| Component | Purpose |
|-----------|---------|
| `SelectableLogGroupItem` | Enhanced widget replacing `ClickableLogGroupItem` |
| Selection counter label | Shows "N selected" in sidebar header |

---

## 2. Architecture Overview

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ChatScreen                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  _process_message()                                                    │  │
│  │     │                                                                  │  │
│  │     ├──► Query sidebar for selected groups                            │  │
│  │     │                                                                  │  │
│  │     ├──► Format selection context                                     │  │
│  │     │                                                                  │  │
│  │     └──► orchestrator.inject_context_update(selection_context)        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                               │
│                              ▼                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  LogGroupsSidebar                                                      │  │
│  │     │                                                                  │  │
│  │     ├── _selected_groups: set[str]        ◄─── Selection state        │  │
│  │     │                                                                  │  │
│  │     ├── get_selected_groups() -> list[str] ◄─── Public API            │  │
│  │     │                                                                  │  │
│  │     ├── SelectableLogGroupItem (per log group)                        │  │
│  │     │      │                                                          │  │
│  │     │      ├── on_click() ──► Selection logic                         │  │
│  │     │      │                                                          │  │
│  │     │      └── on_click() ──► Double-click detection ──► Preview      │  │
│  │     │                                                                  │  │
│  │     └── Selection counter label ("3 selected")                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                              │                                               │
│                              ▼                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  LLMOrchestrator                                                       │  │
│  │     │                                                                  │  │
│  │     ├── inject_context_update(context)   ◄─── Receives selection      │  │
│  │     │                                                                  │  │
│  │     └── System prompt includes selected groups when present            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
User clicks log group
        │
        ▼
┌─────────────────────────────┐
│ SelectableLogGroupItem      │
│ on_click() handler          │
└─────────────┬───────────────┘
              │
              ▼
     ┌────────────────────┐
     │ Double-click check │
     │ (300ms threshold)  │
     └────────┬───────────┘
              │
     ┌────────┴────────┐
     │                 │
     ▼                 ▼
  Single           Double
   Click            Click
     │                 │
     ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Post message:│  │ Post message:│
│ LogGroup     │  │ LogGroup     │
│ Selected     │  │ Preview      │
│              │  │ Requested    │
└──────┬───────┘  └──────────────┘
       │               (existing)
       ▼
┌─────────────────────────────┐
│ LogGroupsSidebar            │
│ on_log_group_selected()     │
│                             │
│ - Check Ctrl/Cmd key        │
│ - Update _selected_groups   │
│ - Update item styling       │
│ - Update counter            │
└─────────────────────────────┘
```

### 2.3 Message Flow for Agent Context

```
User types message and presses Enter
              │
              ▼
┌─────────────────────────────────┐
│ ChatScreen.on_input_submitted() │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ ChatScreen._process_message()   │
│                                 │
│ 1. Get selected groups from     │
│    sidebar                      │
│                                 │
│ 2. If groups selected:          │
│    Format context message       │
│    Call inject_context_update() │
│                                 │
│ 3. Call orchestrator.chat()     │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ LLMOrchestrator                 │
│                                 │
│ - _get_pending_context_injection│
│   retrieves selection context   │
│                                 │
│ - Inserts as system message     │
│   before user message           │
│                                 │
│ - Agent sees selected groups    │
│   in context                    │
└─────────────────────────────────┘
```

---

## 3. UI/UX Design

### 3.1 Visual Layout

```
┌──────────────────────────────┐
│  LOG GROUPS (47)             │  ← Existing title with count
│  ────────────────────────    │
│  3 selected                  │  ← NEW: Selection counter
│                              │
│  /aws/lambda/api-service     │  ← Normal (unselected)
│  /aws/lambda/auth-handler    │  ← SELECTED (highlighted)
│  /aws/lambda/billing         │  ← SELECTED (highlighted)
│  /aws/lambda/notifications   │  ← SELECTED (highlighted)
│  /aws/rds/production-db      │  ← Normal (unselected)
│  /ecs/web-frontend           │  ← Normal (unselected)
│  ...                         │
│                              │
└──────────────────────────────┘
```

### 3.2 Selection Counter Specifications

| Property | Value | Rationale |
|----------|-------|-----------|
| **Location** | Below title, above list | Clear visual separation |
| **Format** | "N selected" or "1 group selected" | Grammatically correct |
| **Visibility** | Only when selection > 0 | Don't clutter when empty |
| **Color** | `$accent` (cyan/blue) | Stand out but not distracting |
| **Font style** | Italic | Differentiates from title |

### 3.3 Selected State Styling

```css
/* Selected log group item */
LogGroupsSidebar .log-group-item.selected {
    background: $primary-lighten-3;    /* Subtle highlight */
    color: $text;
    text-style: bold;
}

/* Hover over selected item */
LogGroupsSidebar .log-group-item.selected:hover {
    background: $primary-lighten-2;    /* Slightly darker on hover */
}

/* Selection counter */
LogGroupsSidebar .selection-counter {
    color: $accent;
    text-style: italic;
    padding: 0 0 1 0;
    height: auto;
}
```

### 3.4 Color Scheme Alignment

The existing app uses these semantic colors (from Textual defaults):

| Token | Usage |
|-------|-------|
| `$panel` | Sidebar background |
| `$surface` | Hover state |
| `$primary` | Borders and accents |
| `$primary-lighten-3` | Selected state background |
| `$accent` | Counter text |
| `$text` | Normal text |
| `$text-muted` | Dimmed/secondary text |

### 3.5 User Interaction Flows

#### Flow 1: Single Selection

```
1. User clicks "api-gateway" log group
2. Group highlights with selected styling
3. Counter shows "1 group selected"
4. Previous selection (if any) is cleared
```

#### Flow 2: Multi-Selection

```
1. User clicks "api-gateway" (selected)
2. User Ctrl-clicks "auth-service" (both selected)
3. User Ctrl-clicks "database" (3 selected)
4. Counter shows "3 selected"
```

#### Flow 3: Deselection via New Selection

```
1. User has 3 groups selected
2. User clicks (without Ctrl) on "billing"
3. Previous 3 selections are cleared
4. Only "billing" is now selected
5. Counter shows "1 group selected"
```

#### Flow 4: Toggle Selection with Ctrl-Click

```
1. User has "api-gateway" selected
2. User Ctrl-clicks "api-gateway" again
3. "api-gateway" is deselected
4. Counter disappears (0 selected)
```

#### Flow 5: Preview Preserved

```
1. User has "api-gateway" selected
2. User double-clicks "auth-service"
3. Preview modal opens for "auth-service"
4. Selection state unchanged ("api-gateway" still selected)
5. Modal closes, "api-gateway" still highlighted
```

### 3.6 Edge Cases and Error States

| Scenario | Behavior |
|----------|----------|
| **0 groups selected** | Counter hidden, all items normal style |
| **All groups selected** | Counter shows "N selected", all highlighted |
| **Log groups refresh** | Selection cleared (groups may have changed) |
| **Sidebar toggle off/on** | Selection preserved |
| **Rapid clicking** | Debounced to prevent UI jitter |

---

## 4. Event Handling Design

### 4.1 Click Event Architecture

The challenge is distinguishing between:
- **Single click** → Select the item
- **Ctrl/Cmd + click** → Add to selection
- **Double click** → Open preview (existing behavior)

#### Current Implementation Analysis

Looking at the existing `ClickableLogGroupItem`:

```python
# Current: Only handles double-click for preview
def on_click(self, event: Click) -> None:
    if event.button != 1:
        return

    current_time = time.time()
    time_since_last = current_time - self._last_click_time

    if time_since_last < self.DOUBLE_CLICK_THRESHOLD:  # 0.5s
        # Double-click: emit preview request
        self.post_message(self.LogGroupPreviewRequested(self.log_group_name))
        self._last_click_time = 0.0
    else:
        # Single click: just record time
        self._last_click_time = current_time
```

### 4.2 New Click Handling Strategy

We need to delay single-click action to distinguish from double-click:

```python
class SelectableLogGroupItem(Label):
    """Log group item with selection and preview support."""

    # Timing constants
    DOUBLE_CLICK_THRESHOLD: float = 0.3  # 300ms - standard OS timing
    SINGLE_CLICK_DELAY: float = 0.35     # Slightly longer to ensure double detected

    class LogGroupSelected(Message):
        """Emitted on single/ctrl-click to select."""
        def __init__(self, log_group_name: str, add_to_selection: bool) -> None:
            super().__init__()
            self.log_group_name = log_group_name
            self.add_to_selection = add_to_selection  # True if Ctrl/Cmd held

    class LogGroupPreviewRequested(Message):
        """Emitted on double-click for preview (existing)."""
        def __init__(self, log_group_name: str) -> None:
            super().__init__()
            self.log_group_name = log_group_name
```

### 4.3 Click Detection State Machine

```
                         ┌──────────────────────────┐
                         │                          │
                         │       IDLE STATE         │
                         │   _last_click_time = 0   │
                         │   _pending_select = None │
                         │                          │
                         └────────────┬─────────────┘
                                      │
                                      │ Click event received
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │                          │
                         │   CHECK DOUBLE-CLICK     │
                         │   time_since_last < 0.3s?│
                         │                          │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │ YES (< 0.3s)                      │ NO (>= 0.3s)
                    │                                   │
                    ▼                                   ▼
         ┌──────────────────────┐           ┌──────────────────────┐
         │                      │           │                      │
         │   DOUBLE-CLICK       │           │   POTENTIAL SINGLE   │
         │                      │           │                      │
         │ 1. Cancel pending    │           │ 1. Record click time │
         │    single-click      │           │ 2. Capture Ctrl state│
         │ 2. Emit Preview      │           │ 3. Schedule delayed  │
         │    Requested         │           │    single-click      │
         │ 3. Reset state       │           │    action (0.35s)    │
         │                      │           │                      │
         └──────────────────────┘           └──────────────────────┘
                                                       │
                                                       │ After 0.35s
                                                       │ (if no 2nd click)
                                                       │
                                                       ▼
                                            ┌──────────────────────┐
                                            │                      │
                                            │   SINGLE-CLICK       │
                                            │                      │
                                            │ Emit LogGroupSelected│
                                            │ with ctrl_held flag  │
                                            │                      │
                                            └──────────────────────┘
```

### 4.4 Modifier Key Detection

Textual's `Click` event provides access to modifier keys:

```python
def on_click(self, event: Click) -> None:
    # Detect Ctrl (Linux/Windows) or Cmd (Mac)
    ctrl_held = event.ctrl or event.meta

    # ... rest of click handling
```

### 4.5 Implementation Code

```python
import asyncio
from textual.events import Click

class SelectableLogGroupItem(Label):
    """Log group item supporting selection and double-click preview."""

    DOUBLE_CLICK_THRESHOLD: float = 0.3
    SINGLE_CLICK_DELAY: float = 0.35

    class LogGroupSelected(Message):
        """Emitted when user selects (single-click) a log group."""
        def __init__(self, log_group_name: str, add_to_selection: bool) -> None:
            super().__init__()
            self.log_group_name = log_group_name
            self.add_to_selection = add_to_selection

    class LogGroupPreviewRequested(Message):
        """Emitted when user double-clicks to preview."""
        def __init__(self, log_group_name: str) -> None:
            super().__init__()
            self.log_group_name = log_group_name

    def __init__(self, log_group_name: str, **kwargs) -> None:
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name
        self._last_click_time: float = 0.0
        self._pending_select_task: asyncio.Task | None = None
        self._pending_ctrl_state: bool = False

    def on_click(self, event: Click) -> None:
        """Handle click with double-click detection."""
        if event.button != 1:  # Only left mouse button
            return

        current_time = time.time()
        time_since_last = current_time - self._last_click_time
        ctrl_held = event.ctrl or event.meta

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            # Double-click detected
            self._cancel_pending_select()
            self.post_message(self.LogGroupPreviewRequested(self.log_group_name))
            self._last_click_time = 0.0  # Reset
        else:
            # Potential single-click - schedule delayed action
            self._last_click_time = current_time
            self._pending_ctrl_state = ctrl_held
            self._schedule_single_click()

    def _schedule_single_click(self) -> None:
        """Schedule a delayed single-click action."""
        self._cancel_pending_select()
        self._pending_select_task = asyncio.create_task(
            self._delayed_single_click()
        )

    async def _delayed_single_click(self) -> None:
        """Execute single-click after delay (if not cancelled by double-click)."""
        await asyncio.sleep(self.SINGLE_CLICK_DELAY)
        self.post_message(
            self.LogGroupSelected(
                self.log_group_name,
                add_to_selection=self._pending_ctrl_state
            )
        )
        self._pending_select_task = None

    def _cancel_pending_select(self) -> None:
        """Cancel any pending single-click action."""
        if self._pending_select_task and not self._pending_select_task.done():
            self._pending_select_task.cancel()
            self._pending_select_task = None
```

### 4.6 Why 300ms/350ms Timing?

| Platform | Standard Double-Click Timing |
|----------|------------------------------|
| Windows | 200-500ms (default ~400ms) |
| macOS | ~300ms |
| Linux (GTK) | 250-400ms |

Using 300ms threshold with 350ms delay provides:
- Comfortable double-click window
- Minimal perceived lag on single-click (350ms is barely noticeable)
- Consistent cross-platform behavior

---

## 5. Selection State Management

### 5.1 State Location

Selection state lives in `LogGroupsSidebar`:

```python
class LogGroupsSidebar(Static):
    """Sidebar with multi-select support."""

    def __init__(self, log_group_manager: "LogGroupManager | None" = None, **kwargs):
        super().__init__(**kwargs)
        self._log_group_manager = log_group_manager
        self._selected_groups: set[str] = set()  # NEW: Selection state
        # ... existing code
```

### 5.2 Selection State API

```python
class LogGroupsSidebar(Static):
    """Extended with selection methods."""

    def get_selected_groups(self) -> list[str]:
        """
        Get currently selected log group names.

        Returns:
            List of selected log group names (sorted alphabetically)
        """
        return sorted(self._selected_groups)

    def select_group(self, name: str, add_to_selection: bool = False) -> None:
        """
        Select a log group.

        Args:
            name: Log group name to select
            add_to_selection: If True, add to current selection (Ctrl-click)
                             If False, replace current selection (regular click)
        """
        if not add_to_selection:
            # Clear previous selection
            self._clear_selection_styling()
            self._selected_groups.clear()

        if name in self._selected_groups:
            # Toggle off if Ctrl-clicking selected item
            if add_to_selection:
                self._selected_groups.remove(name)
        else:
            self._selected_groups.add(name)

        self._update_selection_styling()
        self._update_selection_counter()

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._clear_selection_styling()
        self._selected_groups.clear()
        self._update_selection_counter()

    def has_selection(self) -> bool:
        """Check if any groups are selected."""
        return len(self._selected_groups) > 0

    @property
    def selection_count(self) -> int:
        """Get number of selected groups."""
        return len(self._selected_groups)
```

### 5.3 Selection Persistence Across Sidebar Toggle

When sidebar is hidden and shown again, selection should be preserved:

```python
# In ChatScreen.toggle_log_groups_sidebar():
def toggle_log_groups_sidebar(self) -> None:
    """Toggle the log groups sidebar visibility."""
    self._log_groups_sidebar_visible = not self._log_groups_sidebar_visible

    if self._log_groups_sidebar:
        self._log_groups_sidebar.display = self._log_groups_sidebar_visible

        if self._log_groups_sidebar_visible:
            # Restore width
            width = SIDEBAR_WIDTH_STEPS[self._left_sidebar_width_index]
            self._log_groups_sidebar.styles.width = width

            # Refresh display (selection is preserved in _selected_groups)
            self._log_groups_sidebar.refresh_display()
```

### 5.4 Selection Clear on Refresh

When log groups are refreshed, selection should be cleared (groups may have changed):

```python
# In LogGroupsSidebar._on_log_groups_updated():
def _on_log_groups_updated(self) -> None:
    """Handle log group updates from the manager."""
    try:
        # Clear selection - log groups may have changed
        self.clear_selection()

        # Repopulate list
        self._populate_log_groups()
    except Exception as e:
        logger.warning(f"Failed to update log groups sidebar: {e}", exc_info=True)
```

---

## 6. Agent Integration Design

### 6.1 Context Injection Strategy

The selected groups will be injected into the agent's context using the existing `inject_context_update()` pattern. This happens **before** each user message is sent.

### 6.2 Context Format

```python
SELECTED_GROUPS_CONTEXT_TEMPLATE = """USER HAS SELECTED THE FOLLOWING LOG GROUPS:

The user has explicitly selected {count} log group(s) in the sidebar. When they refer to "these logs", "selected groups", "these", or make requests without specifying a log group, they are referring to:

{group_list}

INSTRUCTIONS:
1. When the user says "search these", "check these logs", "look at these", etc. - use the above log groups
2. When the user asks about "errors", "issues", etc. without specifying a group - search the selected groups
3. If the user explicitly names a different log group, use that instead
4. You do NOT need to ask which log groups to search - the user has already told you by selecting them

Selected groups are: {group_names}
"""
```

Example rendered context:

```
USER HAS SELECTED THE FOLLOWING LOG GROUPS:

The user has explicitly selected 3 log group(s) in the sidebar. When they refer to "these logs", "selected groups", "these", or make requests without specifying a log group, they are referring to:

- /aws/lambda/api-gateway
- /aws/lambda/auth-service
- /aws/lambda/billing

INSTRUCTIONS:
1. When the user says "search these", "check these logs", "look at these", etc. - use the above log groups
2. When the user asks about "errors", "issues", etc. without specifying a group - search the selected groups
3. If the user explicitly names a different log group, use that instead
4. You do NOT need to ask which log groups to search - the user has already told you by selecting them

Selected groups are: /aws/lambda/api-gateway, /aws/lambda/auth-service, /aws/lambda/billing
```

### 6.3 Integration Point: ChatScreen._process_message()

```python
# In chat.py, modify _process_message():

@work(exclusive=True)
async def _process_message(self, user_message: str) -> None:
    """Process a message with the LLM orchestrator."""
    messages_container = self.query_one("#messages-container", VerticalScroll)
    status_footer = self.query_one(StatusFooter)

    try:
        # NEW: Inject selected groups context if any are selected
        if self._log_groups_sidebar and self._log_groups_sidebar.has_selection():
            selected_groups = self._log_groups_sidebar.get_selected_groups()
            context = self._format_selected_groups_context(selected_groups)
            self.orchestrator.inject_context_update(context)

        # Update status
        status_footer.set_status("Thinking...")

        # ... rest of existing code
```

### 6.4 Context Formatting Method

```python
# In chat.py, add new method:

def _format_selected_groups_context(self, selected_groups: list[str]) -> str:
    """
    Format selected log groups for agent context injection.

    Args:
        selected_groups: List of selected log group names

    Returns:
        Formatted context string for agent
    """
    count = len(selected_groups)
    group_list = "\n".join(f"- {name}" for name in selected_groups)
    group_names = ", ".join(selected_groups)

    return f"""USER HAS SELECTED THE FOLLOWING LOG GROUPS:

The user has explicitly selected {count} log group(s) in the sidebar. When they refer to "these logs", "selected groups", "these", or make requests without specifying a log group, they are referring to:

{group_list}

INSTRUCTIONS:
1. When the user says "search these", "check these logs", "look at these", etc. - use the above log groups
2. When the user asks about "errors", "issues", etc. without specifying a group - search the selected groups
3. If the user explicitly names a different log group, use that instead
4. You do NOT need to ask which log groups to search - the user has already told you by selecting them

Selected groups: {group_names}
"""
```

### 6.5 System Prompt Update (Optional Enhancement)

We could also add guidance to the base system prompt to make the agent more aware of this feature:

```python
# Add to SYSTEM_PROMPT in orchestrator.py:

## User Log Group Selection

Users can select one or more log groups in the sidebar. When log groups are selected:
- A system message will tell you which groups are selected
- Use these groups when the user says "these", "selected", or doesn't specify a group
- The user's selection takes precedence over asking them which groups to search
```

### 6.6 Agent Response Examples

**User message**: "Search these for errors in the last hour"

**Agent behavior**:
1. Sees context injection with selected groups
2. Calls `query_logs` for each selected group (or batch if supported)
3. Responds with findings from the selected groups

**User message**: "Are there any timeouts?"

**Agent behavior**:
1. Sees selected groups in context
2. Searches those groups for timeout patterns
3. Doesn't ask "which log groups?" - already knows from selection

---

## 7. Technical Implementation Details

### 7.1 Modified LogGroupsSidebar Widget

```python
# src/logai/ui/widgets/log_groups_sidebar.py

"""Log groups sidebar widget with multi-select support."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.widgets import Label, Static

if TYPE_CHECKING:
    from logai.core.log_group_manager import LogGroupManager

logger = logging.getLogger(__name__)


class SelectableLogGroupItem(Label):
    """
    Selectable log group label with double-click preview support.

    Handles:
    - Single click: Select this group (or add to selection with Ctrl)
    - Double click: Open preview modal
    """

    DOUBLE_CLICK_THRESHOLD: float = 0.3
    SINGLE_CLICK_DELAY: float = 0.35

    class LogGroupSelected(Message):
        """Emitted when user single-clicks to select."""
        def __init__(self, log_group_name: str, add_to_selection: bool) -> None:
            super().__init__()
            self.log_group_name = log_group_name
            self.add_to_selection = add_to_selection

    class LogGroupPreviewRequested(Message):
        """Emitted when user double-clicks to preview."""
        def __init__(self, log_group_name: str) -> None:
            super().__init__()
            self.log_group_name = log_group_name

    def __init__(self, log_group_name: str, **kwargs: Any) -> None:
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name
        self._last_click_time: float = 0.0
        self._pending_select_task: asyncio.Task | None = None
        self._pending_ctrl_state: bool = False

    def on_click(self, event: Click) -> None:
        """Handle click events with double-click detection."""
        if event.button != 1:
            return

        current_time = time.time()
        time_since_last = current_time - self._last_click_time
        ctrl_held = event.ctrl or event.meta

        if time_since_last < self.DOUBLE_CLICK_THRESHOLD:
            # Double-click detected
            self._cancel_pending_select()
            self.post_message(self.LogGroupPreviewRequested(self.log_group_name))
            self._last_click_time = 0.0
        else:
            # Potential single-click
            self._last_click_time = current_time
            self._pending_ctrl_state = ctrl_held
            self._schedule_single_click()

    def _schedule_single_click(self) -> None:
        """Schedule delayed single-click action."""
        self._cancel_pending_select()
        self._pending_select_task = asyncio.create_task(
            self._delayed_single_click()
        )

    async def _delayed_single_click(self) -> None:
        """Execute single-click after delay."""
        try:
            await asyncio.sleep(self.SINGLE_CLICK_DELAY)
            self.post_message(
                self.LogGroupSelected(
                    self.log_group_name,
                    add_to_selection=self._pending_ctrl_state
                )
            )
        except asyncio.CancelledError:
            pass  # Cancelled by double-click
        finally:
            self._pending_select_task = None

    def _cancel_pending_select(self) -> None:
        """Cancel pending single-click."""
        if self._pending_select_task and not self._pending_select_task.done():
            self._pending_select_task.cancel()
            self._pending_select_task = None


class LogGroupsSidebar(Static):
    """Sidebar showing log groups with multi-select support."""

    DEFAULT_CSS = """
    LogGroupsSidebar {
        width: 28;
        min-width: 24;
        max-width: 70;
        height: 1fr;
        background: $panel;
        border-right: solid $primary;
        padding: 0 1;
    }

    LogGroupsSidebar .sidebar-title {
        text-style: bold;
        color: $text;
        padding: 1 0;
        width: 100%;
    }

    LogGroupsSidebar .selection-counter {
        color: $accent;
        text-style: italic;
        padding: 0 0 1 0;
        height: auto;
    }

    LogGroupsSidebar .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
        text-align: center;
    }

    LogGroupsSidebar #log-groups-scroll {
        width: 100%;
        height: 1fr;
        padding: 0;
    }

    LogGroupsSidebar .log-group-item {
        width: 100%;
        height: auto;
        padding: 0;
        color: $text;
    }

    LogGroupsSidebar .log-group-item:hover {
        background: $surface;
    }

    LogGroupsSidebar .log-group-item.selected {
        background: $primary-lighten-3;
        text-style: bold;
    }

    LogGroupsSidebar .log-group-item.selected:hover {
        background: $primary-lighten-2;
    }
    """

    def __init__(
        self,
        log_group_manager: "LogGroupManager | None" = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._log_group_manager = log_group_manager
        self._selected_groups: set[str] = set()
        self._title_label: Static | None = None
        self._selection_counter: Static | None = None
        self._scroll_container: VerticalScroll | None = None
        self._empty_state: Static | None = None

    def compose(self) -> ComposeResult:
        """Compose the sidebar layout."""
        count = self._get_count()
        yield Static(f"LOG GROUPS ({count})", id="sidebar-title", classes="sidebar-title")

        # Selection counter (hidden by default)
        yield Static("", id="selection-counter", classes="selection-counter")

        yield Static(
            "No log groups loaded.\nUse /refresh to load.",
            id="empty-state",
            classes="empty-state",
        )

        yield VerticalScroll(id="log-groups-scroll")

    def on_mount(self) -> None:
        """Set up the sidebar when mounted."""
        self._title_label = self.query_one("#sidebar-title", Static)
        self._selection_counter = self.query_one("#selection-counter", Static)
        self._scroll_container = self.query_one("#log-groups-scroll", VerticalScroll)
        self._empty_state = self.query_one("#empty-state", Static)

        # Hide counter initially
        self._selection_counter.display = False

        if self._log_group_manager:
            self._log_group_manager.register_update_callback(self._on_log_groups_updated)

        self._populate_log_groups()

    # ... (rest of existing methods: on_unmount, _on_log_groups_updated, etc.)

    # === NEW: Selection Methods ===

    def get_selected_groups(self) -> list[str]:
        """Get currently selected log group names."""
        return sorted(self._selected_groups)

    def has_selection(self) -> bool:
        """Check if any groups are selected."""
        return len(self._selected_groups) > 0

    @property
    def selection_count(self) -> int:
        """Get number of selected groups."""
        return len(self._selected_groups)

    def select_group(self, name: str, add_to_selection: bool = False) -> None:
        """Select a log group."""
        if not add_to_selection:
            self._clear_selection_styling()
            self._selected_groups.clear()

        if name in self._selected_groups:
            if add_to_selection:
                self._selected_groups.remove(name)
        else:
            self._selected_groups.add(name)

        self._update_selection_styling()
        self._update_selection_counter()

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._clear_selection_styling()
        self._selected_groups.clear()
        self._update_selection_counter()

    def _clear_selection_styling(self) -> None:
        """Remove selected class from all items."""
        if self._scroll_container:
            for item in self._scroll_container.query(".log-group-item"):
                item.remove_class("selected")

    def _update_selection_styling(self) -> None:
        """Update visual styling based on selection state."""
        if self._scroll_container:
            for item in self._scroll_container.query(SelectableLogGroupItem):
                if item.log_group_name in self._selected_groups:
                    item.add_class("selected")
                else:
                    item.remove_class("selected")

    def _update_selection_counter(self) -> None:
        """Update the selection counter display."""
        if not self._selection_counter:
            return

        count = len(self._selected_groups)
        if count == 0:
            self._selection_counter.display = False
        else:
            text = "1 group selected" if count == 1 else f"{count} selected"
            self._selection_counter.update(text)
            self._selection_counter.display = True

    # === Event Handlers ===

    def on_selectable_log_group_item_log_group_selected(
        self, event: SelectableLogGroupItem.LogGroupSelected
    ) -> None:
        """Handle log group selection."""
        self.select_group(event.log_group_name, event.add_to_selection)
```

### 7.2 Updated ChatScreen Integration

```python
# In src/logai/ui/screens/chat.py

# Add import
from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem, LogGroupsSidebar

# Update event handler registration
@on(SelectableLogGroupItem.LogGroupPreviewRequested)
async def on_log_group_preview_requested(
    self, event: SelectableLogGroupItem.LogGroupPreviewRequested
) -> None:
    """Handle request to preview logs from a log group."""
    # ... existing preview code (unchanged)

# Modify _process_message:
@work(exclusive=True)
async def _process_message(self, user_message: str) -> None:
    """Process a message with the LLM orchestrator."""
    messages_container = self.query_one("#messages-container", VerticalScroll)
    status_footer = self.query_one(StatusFooter)

    try:
        # NEW: Inject selected groups context if any are selected
        if self._log_groups_sidebar and self._log_groups_sidebar.has_selection():
            selected_groups = self._log_groups_sidebar.get_selected_groups()
            selection_context = self._format_selected_groups_context(selected_groups)
            self.orchestrator.inject_context_update(selection_context)
            logger.debug(f"Injected {len(selected_groups)} selected groups into context")

        # ... rest of existing code unchanged
```

### 7.3 CSS Theming Considerations

The CSS uses Textual's semantic color tokens. Here's what they typically resolve to:

| Token | Light Theme | Dark Theme |
|-------|-------------|------------|
| `$primary` | Blue | Blue |
| `$primary-lighten-3` | Light blue | Lighter blue |
| `$accent` | Cyan | Cyan |
| `$surface` | Light gray | Dark gray |
| `$panel` | White | Dark gray |
| `$text` | Black | White |

The selected state will be clearly visible in both light and dark themes.

---

## 8. Testing Strategy

### 8.1 Unit Tests

**File**: `tests/unit/ui/widgets/test_log_groups_sidebar_selection.py`

```python
import pytest
import asyncio
from unittest.mock import Mock, patch
from logai.ui.widgets.log_groups_sidebar import (
    SelectableLogGroupItem,
    LogGroupsSidebar,
)


class TestSelectableLogGroupItem:
    """Tests for SelectableLogGroupItem click handling."""

    def test_single_click_emits_selected_message(self):
        """Test that single click eventually emits LogGroupSelected."""
        # Test with mocked asyncio
        pass

    def test_double_click_emits_preview_message(self):
        """Test that double click emits LogGroupPreviewRequested."""
        pass

    def test_ctrl_click_sets_add_to_selection_true(self):
        """Test Ctrl modifier is captured correctly."""
        pass

    def test_double_click_cancels_pending_single_click(self):
        """Test that double-click prevents single-click action."""
        pass

    def test_timing_threshold_constants(self):
        """Verify timing constants are reasonable."""
        item = SelectableLogGroupItem("test-group")
        assert item.DOUBLE_CLICK_THRESHOLD == 0.3
        assert item.SINGLE_CLICK_DELAY == 0.35
        assert item.SINGLE_CLICK_DELAY > item.DOUBLE_CLICK_THRESHOLD


class TestLogGroupsSidebarSelection:
    """Tests for LogGroupsSidebar selection state management."""

    def test_initial_selection_empty(self):
        """Test that selection starts empty."""
        sidebar = LogGroupsSidebar()
        assert sidebar.get_selected_groups() == []
        assert not sidebar.has_selection()
        assert sidebar.selection_count == 0

    def test_select_single_group(self):
        """Test selecting a single group."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/aws/lambda/test")

        assert sidebar.has_selection()
        assert sidebar.selection_count == 1
        assert "/aws/lambda/test" in sidebar.get_selected_groups()

    def test_select_multiple_groups_with_add(self):
        """Test multi-select with add_to_selection=True."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/aws/lambda/test1")
        sidebar.select_group("/aws/lambda/test2", add_to_selection=True)
        sidebar.select_group("/aws/lambda/test3", add_to_selection=True)

        assert sidebar.selection_count == 3
        assert len(sidebar.get_selected_groups()) == 3

    def test_select_without_add_clears_previous(self):
        """Test that selecting without add clears previous selection."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/aws/lambda/test1")
        sidebar.select_group("/aws/lambda/test2", add_to_selection=True)

        # Now select without add
        sidebar.select_group("/aws/lambda/test3", add_to_selection=False)

        assert sidebar.selection_count == 1
        assert sidebar.get_selected_groups() == ["/aws/lambda/test3"]

    def test_toggle_selection_with_ctrl(self):
        """Test that Ctrl-clicking selected item deselects it."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/aws/lambda/test")
        assert sidebar.selection_count == 1

        # Ctrl-click same item
        sidebar.select_group("/aws/lambda/test", add_to_selection=True)
        assert sidebar.selection_count == 0

    def test_clear_selection(self):
        """Test clear_selection empties the set."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/aws/lambda/test1")
        sidebar.select_group("/aws/lambda/test2", add_to_selection=True)

        sidebar.clear_selection()

        assert not sidebar.has_selection()
        assert sidebar.selection_count == 0

    def test_get_selected_groups_returns_sorted(self):
        """Test that get_selected_groups returns sorted list."""
        sidebar = LogGroupsSidebar()
        sidebar.select_group("/zzz/last")
        sidebar.select_group("/aaa/first", add_to_selection=True)
        sidebar.select_group("/mmm/middle", add_to_selection=True)

        result = sidebar.get_selected_groups()
        assert result == ["/aaa/first", "/mmm/middle", "/zzz/last"]


class TestSelectionContextFormatting:
    """Tests for context injection formatting."""

    def test_format_single_group(self):
        """Test context format with single group."""
        from logai.ui.screens.chat import ChatScreen

        # Would need mocking/fixtures for full test
        pass

    def test_format_multiple_groups(self):
        """Test context format with multiple groups."""
        pass
```

### 8.2 Integration Tests

**File**: `tests/integration/ui/test_log_groups_multi_select.py`

```python
import pytest
from textual.pilot import Pilot


class TestMultiSelectIntegration:
    """Integration tests for multi-select feature."""

    @pytest.mark.asyncio
    async def test_click_selects_group(self):
        """Test clicking a log group selects it."""
        pass

    @pytest.mark.asyncio
    async def test_ctrl_click_adds_to_selection(self):
        """Test Ctrl+click adds to existing selection."""
        pass

    @pytest.mark.asyncio
    async def test_double_click_opens_preview(self):
        """Test double-click still opens preview modal."""
        pass

    @pytest.mark.asyncio
    async def test_selection_counter_updates(self):
        """Test selection counter shows correct count."""
        pass

    @pytest.mark.asyncio
    async def test_selected_groups_injected_to_agent(self):
        """Test that selected groups appear in agent context."""
        pass
```

### 8.3 Manual Test Scenarios

| # | Scenario | Steps | Expected Result |
|---|----------|-------|-----------------|
| 1 | **Single select** | Click on a log group | Group highlights, counter shows "1 group selected" |
| 2 | **Multi-select** | Click group A, Ctrl-click group B | Both highlighted, counter shows "2 selected" |
| 3 | **Replace selection** | Select A+B, then click C (no Ctrl) | Only C highlighted, counter shows "1 group selected" |
| 4 | **Toggle off** | Ctrl-click a selected group | Group deselects, counter updates |
| 5 | **Preview preserved** | Select A, double-click B | Preview opens for B, A stays selected |
| 6 | **Agent awareness** | Select groups, type "search these for errors" | Agent searches selected groups without asking |
| 7 | **Counter grammar** | Select exactly 1 group | Counter shows "1 group selected" (not "1 selected") |
| 8 | **Counter hidden** | Deselect all groups | Counter disappears |
| 9 | **Refresh clears** | Select groups, run /refresh | Selection cleared |
| 10 | **Toggle sidebar** | Select groups, hide/show sidebar | Selection preserved |

### 8.4 Edge Case Tests

| Edge Case | Test |
|-----------|------|
| **Click timing edge** | Click at exactly 300ms boundary |
| **Rapid double-click** | Two clicks within 50ms |
| **Slow double-click** | Two clicks at 400ms apart (should be two singles) |
| **Triple-click** | Three rapid clicks |
| **Ctrl held then released** | Press Ctrl, click, release Ctrl before delay |
| **Many groups selected** | Select 20+ groups |
| **Empty sidebar** | Attempt selection with no log groups |
| **Very long group name** | Selection with 200+ char name |

---

## 9. Implementation Plan

### 9.1 Task Breakdown

#### Phase 1: Click Handler Infrastructure (1-2 hours)

**Tasks:**
- [ ] Create `SelectableLogGroupItem` class with click handling
- [ ] Implement double-click detection with timing
- [ ] Implement delayed single-click emission
- [ ] Add `LogGroupSelected` message class
- [ ] Test click detection logic in isolation

**Deliverable:** Click detection that distinguishes single/double/ctrl-click

#### Phase 2: Selection State Management (1-2 hours)

**Tasks:**
- [ ] Add `_selected_groups: set[str]` to `LogGroupsSidebar`
- [ ] Implement `select_group()`, `clear_selection()`, `get_selected_groups()`
- [ ] Add selection counter to sidebar compose
- [ ] Implement counter update logic
- [ ] Wire up `on_selectable_log_group_item_log_group_selected` handler

**Deliverable:** Working selection state with counter display

#### Phase 3: Visual Styling (30 min - 1 hour)

**Tasks:**
- [ ] Add `.selected` CSS class for highlighted state
- [ ] Add `.selection-counter` CSS styling
- [ ] Implement `_update_selection_styling()` method
- [ ] Test in both light and dark themes

**Deliverable:** Clear visual feedback for selected state

#### Phase 4: Agent Context Integration (1-2 hours)

**Tasks:**
- [ ] Add `_format_selected_groups_context()` to ChatScreen
- [ ] Modify `_process_message()` to inject context
- [ ] Test context appears in agent messages
- [ ] Verify agent responds correctly to "these" references

**Deliverable:** Agent is aware of selection and responds appropriately

#### Phase 5: Testing & Polish (1-2 hours)

**Tasks:**
- [ ] Write unit tests for selection logic
- [ ] Write unit tests for click handling
- [ ] Run manual test scenarios
- [ ] Fix any edge cases discovered
- [ ] Code review and cleanup

**Deliverable:** Fully tested, production-ready feature

### 9.2 Task Dependencies

```
Phase 1: Click Handler
    │
    ▼
Phase 2: Selection State ──► Phase 3: Visual Styling
    │
    ▼
Phase 4: Agent Integration
    │
    ▼
Phase 5: Testing & Polish
```

### 9.3 Estimated Timeline

| Phase | Estimated Time | Cumulative |
|-------|----------------|------------|
| Phase 1 | 1-2 hours | 1-2 hours |
| Phase 2 | 1-2 hours | 2-4 hours |
| Phase 3 | 0.5-1 hour | 2.5-5 hours |
| Phase 4 | 1-2 hours | 3.5-7 hours |
| Phase 5 | 1-2 hours | 4.5-9 hours |

**Total estimate: 5-9 hours** (including buffer for unexpected issues)

### 9.4 Implementation Checklist for Jackie

```markdown
## Phase 1 Checklist
- [ ] In `log_groups_sidebar.py`:
  - [ ] Rename `ClickableLogGroupItem` to `SelectableLogGroupItem` (or create new)
  - [ ] Add timing constants (DOUBLE_CLICK_THRESHOLD, SINGLE_CLICK_DELAY)
  - [ ] Add `LogGroupSelected` message class
  - [ ] Implement `on_click()` with double-click detection
  - [ ] Implement `_schedule_single_click()` with asyncio.Task
  - [ ] Implement `_cancel_pending_select()`
  - [ ] Add `_pending_select_task` and `_pending_ctrl_state` attributes

## Phase 2 Checklist
- [ ] In `log_groups_sidebar.py`:
  - [ ] Add `_selected_groups: set[str]` to `__init__`
  - [ ] Add `_selection_counter: Static` reference
  - [ ] Add selection counter to `compose()`
  - [ ] Implement `get_selected_groups() -> list[str]`
  - [ ] Implement `has_selection() -> bool`
  - [ ] Implement `selection_count` property
  - [ ] Implement `select_group(name, add_to_selection)`
  - [ ] Implement `clear_selection()`
  - [ ] Implement `_update_selection_counter()`
  - [ ] Add `on_selectable_log_group_item_log_group_selected()` handler

## Phase 3 Checklist
- [ ] In `log_groups_sidebar.py` DEFAULT_CSS:
  - [ ] Add `.selection-counter` styling
  - [ ] Add `.log-group-item.selected` styling
  - [ ] Add `.log-group-item.selected:hover` styling
- [ ] Implement `_clear_selection_styling()`
- [ ] Implement `_update_selection_styling()`
- [ ] Update `_populate_log_groups()` to use `SelectableLogGroupItem`

## Phase 4 Checklist
- [ ] In `chat.py`:
  - [ ] Update import to `SelectableLogGroupItem`
  - [ ] Add `_format_selected_groups_context()` method
  - [ ] Modify `_process_message()` to inject selection context
  - [ ] Update event handler decorator if class name changed
- [ ] Test agent response to "search these"

## Phase 5 Checklist
- [ ] Create `tests/unit/ui/widgets/test_log_groups_sidebar_selection.py`
- [ ] Write tests for click detection
- [ ] Write tests for selection state
- [ ] Run manual test scenarios (see Section 8.3)
- [ ] Fix any issues found
- [ ] Update `__init__.py` exports if needed
```

---

## 10. Questions & Decisions

### 10.1 Design Questions Requiring User Input

| Question | Options | Recommendation | Decision |
|----------|---------|----------------|----------|
| **Q1: Shift-click for range selection?** | Yes / No | No (keep simple for v1) | **OUT OF SCOPE** per requirements |
| **Q2: Click selected group behavior?** | Deselect it / Make only selection | Make only selection | Standard OS behavior |
| **Q3: Clear selection shortcut?** | Escape key / Click empty area / None | Escape key | **DEFER** - nice to have |
| **Q4: Selection limit?** | 5 / 10 / Unlimited | Unlimited | No practical reason to limit |
| **Q5: Persist selection across sessions?** | Yes / No | No | Session-only per requirements |

### 10.2 Trade-offs Made

| Trade-off | Chosen | Alternative | Rationale |
|-----------|--------|-------------|-----------|
| **Click delay (350ms)** | Slight delay on single-click | No delay but lose double-click | Preserving preview is critical requirement |
| **State in widget vs. app** | Widget (`LogGroupsSidebar`) | `ChatScreen` | Keeps UI state close to UI logic |
| **Context injection** | Every message | Only when referenced | Simple, consistent, no NLU needed |
| **Selection cleared on refresh** | Yes | Preserve with validation | Safe default, groups may change |

### 10.3 Alternative Approaches Considered

#### Alternative 1: Checkbox Column
Instead of click-to-select, add checkboxes next to each log group.

**Pros:**
- Very explicit, no ambiguity
- Standard form pattern

**Cons:**
- Takes horizontal space
- More visual clutter
- Less elegant than selection highlighting
- Requires more significant UI changes

**Decision:** Rejected - highlighting is cleaner and more standard for this context.

#### Alternative 2: Separate "Selection Mode"
Add a toggle to enter "selection mode" where clicks select instead of preview.

**Pros:**
- No timing complexity
- Clear mode indication

**Cons:**
- Extra cognitive load (what mode am I in?)
- More clicks to accomplish selection
- Less discoverable

**Decision:** Rejected - timing-based detection is more intuitive.

#### Alternative 3: Right-click for Preview
Move preview to right-click, single-click for select.

**Pros:**
- No timing needed
- Standard context menu pattern

**Cons:**
- Breaking change for existing users
- Right-click has other conventions (context menus)
- May not work well on touchpads

**Decision:** Rejected - must preserve existing double-click behavior.

### 10.4 Open Questions for Future Consideration

1. **Keyboard navigation**: Should we add arrow key navigation with Space to select? (NFR2 mentions this - defer to v2)

2. **Bulk actions**: Should there be a "Search Selected" button? (Out of scope per requirements)

3. **Visual indicator in chat**: Should we show selected groups in the chat input area as well?

---

## 11. Appendix: Event Flow Diagrams

### 11.1 Complete Click Event Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            USER CLICKS LOG GROUP                             │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     SelectableLogGroupItem.on_click()                        │
│                                                                              │
│  1. Check event.button == 1 (left click)                                     │
│  2. Calculate time_since_last_click                                          │
│  3. Capture ctrl_held = event.ctrl or event.meta                             │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
         time_since_last < 0.3s              time_since_last >= 0.3s
            (DOUBLE-CLICK)                      (POTENTIAL SINGLE)
                    │                                   │
                    ▼                                   ▼
┌──────────────────────────────┐       ┌──────────────────────────────────────┐
│                              │       │                                      │
│  1. Cancel pending task      │       │  1. Record _last_click_time          │
│  2. Reset _last_click_time   │       │  2. Store _pending_ctrl_state        │
│  3. Post LogGroupPreview     │       │  3. Schedule asyncio.Task            │
│     Requested message        │       │     └─ awaits 0.35s                  │
│                              │       │     └─ posts LogGroupSelected        │
└──────────────────────────────┘       │        if not cancelled              │
            │                          │                                      │
            ▼                          └──────────────────────────────────────┘
┌──────────────────────────────┐                        │
│                              │                        │ After 0.35s (if no
│  ChatScreen handles:         │                        │ second click)
│  on_log_group_preview_       │                        │
│  requested()                 │                        ▼
│                              │       ┌──────────────────────────────────────┐
│  Opens LogPreviewScreen      │       │                                      │
│  modal                       │       │  LogGroupSelected message posted     │
│                              │       │  with:                               │
└──────────────────────────────┘       │  - log_group_name                    │
                                       │  - add_to_selection (from ctrl)      │
                                       │                                      │
                                       └──────────────────────────────────────┘
                                                        │
                                                        ▼
                               ┌──────────────────────────────────────────────┐
                               │                                              │
                               │  LogGroupsSidebar.on_selectable_log_group_   │
                               │  item_log_group_selected()                   │
                               │                                              │
                               │  Calls select_group(name, add_to_selection)  │
                               │                                              │
                               └──────────────────────────────────────────────┘
                                                        │
                                                        ▼
                               ┌──────────────────────────────────────────────┐
                               │                                              │
                               │  LogGroupsSidebar.select_group()             │
                               │                                              │
                               │  if not add_to_selection:                    │
                               │      clear previous selections               │
                               │                                              │
                               │  if name in _selected_groups and add:        │
                               │      remove (toggle off)                     │
                               │  else:                                       │
                               │      add to _selected_groups                 │
                               │                                              │
                               │  update styling and counter                  │
                               │                                              │
                               └──────────────────────────────────────────────┘
```

### 11.2 Agent Context Injection Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         USER SUBMITS MESSAGE                                  │
│                    "search these for errors"                                  │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ChatScreen.on_input_submitted()                          │
│                                                                              │
│  1. Check if message is command (starts with /)                              │
│  2. If not command, call _process_message(message)                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ChatScreen._process_message()                            │
│                                                                              │
│  # Check for selections                                                      │
│  if self._log_groups_sidebar.has_selection():                                │
│      groups = self._log_groups_sidebar.get_selected_groups()                 │
│      # Returns: ["/aws/lambda/api", "/aws/lambda/auth", ...]                 │
│                                                                              │
│      context = self._format_selected_groups_context(groups)                  │
│      # Returns formatted context string                                      │
│                                                                              │
│      self.orchestrator.inject_context_update(context)                        │
│      # Stores in orchestrator._pending_context_injection                     │
│                                                                              │
│  # Continue with normal message processing...                                │
│  async for token in self.orchestrator.chat_stream(user_message):             │
│      ...                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     LLMOrchestrator.chat_stream()                            │
│                                                                              │
│  # Build messages array                                                      │
│  messages = [{"role": "system", "content": system_prompt}]                   │
│                                                                              │
│  # Get pending injection (includes selected groups)                          │
│  pending_injection = self._get_pending_context_injection()                   │
│  # Returns: "USER HAS SELECTED THE FOLLOWING LOG GROUPS:..."                 │
│                                                                              │
│  # Insert as system message before user message                              │
│  if pending_injection:                                                       │
│      messages.append({"role": "system", "content": pending_injection})       │
│                                                                              │
│  messages.append({"role": "user", "content": "search these for errors"})     │
│                                                                              │
│  # Send to LLM                                                               │
│  response = await self.llm_provider.chat(messages, tools, stream=True)       │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            LLM RECEIVES                                       │
│                                                                              │
│  [System] You are an expert observability assistant...                       │
│                                                                              │
│  [System] USER HAS SELECTED THE FOLLOWING LOG GROUPS:                        │
│           The user has explicitly selected 2 log group(s)...                 │
│           - /aws/lambda/api-gateway                                          │
│           - /aws/lambda/auth-service                                         │
│           ...                                                                │
│                                                                              │
│  [User] search these for errors                                              │
│                                                                              │
│  LLM understands "these" = selected groups                                   │
│  LLM calls query_logs for each selected group                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 20, 2026 | Saanvi | Initial design document |

---

**End of Design Document**
