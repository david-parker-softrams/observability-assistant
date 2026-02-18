# Design Document: Adjustable Time Frame Selector for Log Preview

**Document ID**: DD-2026-02-18-TIMEFRAME
**Author**: Saanvi (Senior Software Architect)
**Date**: February 18, 2026
**Status**: APPROVED FOR IMPLEMENTATION
**Version**: 1.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [UI Design Specification](#3-ui-design-specification)
4. [Technical Design](#4-technical-design)
5. [Implementation Plan](#5-implementation-plan)
6. [Code Specifications](#6-code-specifications)
7. [Data Structures](#7-data-structures)
8. [Testing Strategy](#8-testing-strategy)
9. [Edge Cases & Error Handling](#9-edge-cases--error-handling)
10. [Backward Compatibility](#10-backward-compatibility)
11. [Future Enhancements](#11-future-enhancements)
12. [Appendix](#12-appendix)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides the complete technical design for implementing an adjustable time frame selector in the Log Preview modal. The feature allows users to choose from four preset time windows (15 minutes, 1 hour, 8 hours, 24 hours) when previewing CloudWatch log entries.

### 1.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **SegmentedButton UI** | All 4 options visible at once; no dropdown needed; modern UX pattern |
| **Reactive Property** | Follows existing codebase patterns; automatic UI binding |
| **Exclusive Worker** | Built-in debouncing; prevents concurrent fetches |
| **In-Modal Selection** | Single source of truth; no external state dependencies |

### 1.3 Implementation Summary

- **Files Modified**: 2 (log_preview.py, test_log_preview.py)
- **New Lines**: ~120
- **Modified Lines**: ~30
- **Estimated Effort**: 2-3 hours
- **Risk Level**: LOW

---

## 2. Architecture Overview

### 2.1 High-Level Component Interaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          LogPreviewScreen                                │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Reactive State                                                       ││
│  │   selected_time_frame: str = "15 min"                               ││
│  │   ↓ (watch method triggers on change)                               ││
│  │   watch_selected_time_frame() → _fetch_and_display_logs()           ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────┐    ┌─────────────────────┐    ┌──────────────────┐  │
│  │ SegmentedButton│───▶│ Event Handler       │───▶│ CloudWatch       │  │
│  │ [15min][1hr]   │    │ on_timeframe_changed│    │ DataSource       │  │
│  │ [8hr][24hr]    │    │ updates reactive    │    │ fetch_logs()     │  │
│  └────────────────┘    │ property            │    └──────────────────┘  │
│                        └─────────────────────┘                          │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ @work(exclusive=True) _fetch_and_display_logs()                     ││
│  │   - Shows loading indicator                                          ││
│  │   - Calculates time range from selected_time_frame                   ││
│  │   - Fetches from CloudWatch                                          ││
│  │   - Displays results or empty/error state                            ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow When Time Frame Changes

```
User Action                    System Response
───────────                    ───────────────

1. User clicks                 SegmentedButton.Changed event fires
   [1 hour] button
        │
        ▼
2. Event handler              on_timeframe_changed() receives event
   processes event            extracts button label "1 hour"
        │
        ▼
3. Reactive property          self.selected_time_frame = "1 hour"
   updated                    (triggers watch method automatically)
        │
        ▼
4. Watch method               watch_selected_time_frame() called
   executes                   - Clears _events list
                              - Clears _selected_ids set
                              - Calls _fetch_and_display_logs()
        │
        ▼
5. Worker starts              @work(exclusive=True) ensures:
   (exclusive)                - Previous fetch cancelled if running
                              - Only one fetch at a time
        │
        ▼
6. Clear container            Remove existing LogEntryItem widgets
   show loading               Mount "Loading..." Static widget
        │
        ▼
7. Calculate times            end_time = now (milliseconds)
                              start_time = end_time - (60 * 60 * 1000)
                              (1 hour = 60 minutes)
        │
        ▼
8. Fetch from                 await datasource.fetch_logs(
   CloudWatch                     log_group=...,
                                  start_time=...,
                                  end_time=...,
                                  limit=10
                              )
        │
        ▼
9. Display results            Remove loading indicator
                              Mount LogEntryItem widgets OR
                              Mount empty/error state
        │
        ▼
10. Update counter            "0 of N selected"
```

### 2.3 State Management Approach

```python
# State is managed entirely within LogPreviewScreen

class LogPreviewScreen(ModalScreen):

    # REACTIVE STATE (automatically triggers watchers)
    selected_time_frame: reactive[str] = reactive("15 min")

    # DERIVED STATE (computed from reactive)
    @property
    def time_range_minutes(self) -> int:
        return TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)

    # MUTABLE STATE (updated by business logic)
    _events: list[dict]       # Fetched log events
    _selected_ids: set[str]   # User's selections
```

**State Transitions**:

| Trigger | State Change | Side Effect |
|---------|--------------|-------------|
| Modal opens | selected_time_frame = "15 min" | Initial fetch |
| User clicks time button | selected_time_frame = new value | Refresh fetch |
| Fetch completes | _events = results | UI updates |
| User toggles checkbox | _selected_ids add/remove | Counter updates |

---

## 3. UI Design Specification

### 3.1 Control Type: SegmentedButton

**Selection Rationale**:

| UI Option | Pros | Cons | Decision |
|-----------|------|------|----------|
| Dropdown/Select | Compact | Hidden options, requires click | REJECTED |
| RadioButtons | Clear selection | Takes vertical space | REJECTED |
| Tabs | Clear indication | Not semantically correct | REJECTED |
| **SegmentedButton** | All visible, one click, modern | Horizontal space | **SELECTED** |

### 3.2 Modal Layout (Updated)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Log Preview: /aws/lambda/my-function                                   │  ← preview-header
├─────────────────────────────────────────────────────────────────────────┤
│  Time Frame:  [ 15 min ][ 1 hour ][ 8 hours ][ 24 hours ]              │  ← timeframe-controls (NEW)
├─────────────────────────────────────────────────────────────────────────┤
│  [Select All] [Deselect All]                          0 of 5 selected   │  ← selection-controls
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ [✓] 2026-02-18 14:32:15.123                                        │ │
│  │     Error processing payment request for order #12345...            │ │
│  │     (click to expand)                                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │  ← log-entries
│  │ [ ] 2026-02-18 14:31:45.789                                        │ │     (VerticalScroll)
│  │     Request timeout after 30s waiting for downstream...             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ... (scrollable)                                                        │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│              [Add Selected to Context]         [Close]                  │  ← action-buttons
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Visual Design

#### 3.3.1 Time Frame Controls Container

```
#timeframe-controls
├── Static "Time Frame:" (label)
└── SegmentedButton
    ├── Button "15 min" (default selected)
    ├── Button "1 hour"
    ├── Button "8 hours"
    └── Button "24 hours"
```

#### 3.3.2 Button States

| State | Visual Appearance |
|-------|-------------------|
| **Normal** | Standard button background |
| **Selected/Pressed** | Highlighted background (primary color) |
| **Hover** | Slightly lighter background |
| **Disabled** | Grayed out (during loading) |

#### 3.3.3 Color Scheme (Textual Variables)

- Label text: `$text-muted`
- Button background (normal): `$surface`
- Button background (selected): `$primary`
- Button text: `$text`
- Container background: `$surface`

### 3.4 Interaction Behavior

#### 3.4.1 Click Flow

1. User clicks unselected time frame button
2. Button visually activates (highlighted)
3. Previously selected button deactivates
4. Log entries area shows "Loading recent log entries..."
5. New logs appear after fetch completes
6. Selection counter resets to "0 of N selected"

#### 3.4.2 Keyboard Navigation

- Tab: Focus moves to SegmentedButton
- Arrow Left/Right: Navigate between buttons
- Enter/Space: Activate focused button

### 3.5 Loading States

#### 3.5.1 During Fetch

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Time Frame:  [ 15 min ][●1 hour ][ 8 hours ][ 24 hours ]              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                                                                          │
│                    Loading recent log entries...                         │
│                                                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3.5.2 Loading Message Text

The loading message is already implemented as a Static widget with text:
```
"Loading recent log entries..."
```

No changes needed - this is already displayed during fetches.

#### 3.5.3 Time Frame Buttons During Loading

**Design Decision**: Buttons remain **enabled** during loading.

**Rationale**:
- The `@work(exclusive=True)` decorator handles concurrent requests by cancelling the previous one
- Users can change their mind mid-fetch without issues
- Simpler implementation, no need to track loading state for button enablement
- Consistent with existing modal behavior

---

## 4. Technical Design

### 4.1 Code Structure and File Organization

```
src/logai/ui/screens/
└── log_preview.py              # MODIFY - add time frame functionality
    ├── LogEntryItem            # NO CHANGES
    └── LogPreviewScreen        # MODIFY
        ├── TIME_FRAME_OPTIONS  # ADD - constant mapping
        ├── selected_time_frame # ADD - reactive property
        ├── time_range_minutes  # MODIFY - change to computed property
        ├── compose()           # MODIFY - add SegmentedButton
        ├── watch_selected_time_frame()  # ADD - watcher method
        ├── on_timeframe_changed()       # ADD - event handler
        └── DEFAULT_CSS         # MODIFY - add new styles

tests/unit/ui/
└── test_log_preview.py         # MODIFY - add new tests
    └── TestLogPreviewScreen
        ├── test_time_frame_options_mapping()     # ADD
        ├── test_default_time_frame()             # ADD
        ├── test_time_range_minutes_property()    # ADD
        └── test_initialization_preserves_custom_range()  # ADD
```

### 4.2 New Classes/Methods

| Item | Type | Purpose |
|------|------|---------|
| `TIME_FRAME_OPTIONS` | Class Constant | Maps display labels to minutes |
| `selected_time_frame` | Reactive Property | Tracks current selection |
| `time_range_minutes` | Computed Property | Returns minutes from selection |
| `watch_selected_time_frame()` | Watcher Method | Triggers refresh on change |
| `on_timeframe_changed()` | Event Handler | Handles button press |
| `_clear_log_entries()` | Helper Method | Clears container before refresh |

### 4.3 Reactive Property Implementation

```python
from textual.reactive import reactive

class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    # Class-level reactive property declaration
    selected_time_frame: reactive[str] = reactive("15 min")

    def watch_selected_time_frame(self, new_frame: str) -> None:
        """Called automatically when selected_time_frame changes."""
        # Don't trigger on initial mount (handled by on_mount)
        if self.is_mounted:
            self._clear_and_refresh()
```

**Important**: The reactive property is declared at class level, not in `__init__`.

### 4.4 Event Handling Approach

```python
from textual import on
from textual.widgets import Button

@on(Button.Pressed, "#timeframe-selector Button")
def on_timeframe_changed(self, event: Button.Pressed) -> None:
    """Handle time frame button press."""
    button_label = str(event.button.label)
    if button_label in self.TIME_FRAME_OPTIONS:
        self.selected_time_frame = button_label
```

**Note**: We use `Button.Pressed` on buttons within the SegmentedButton container rather than `SegmentedButton.Changed`, as this provides cleaner access to the button label.

### 4.5 Time Frame to Minutes Mapping

```python
TIME_FRAME_OPTIONS: dict[str, int] = {
    "15 min": 15,
    "1 hour": 60,
    "8 hours": 480,    # 60 * 8
    "24 hours": 1440,  # 60 * 24
}
```

**Key Points**:
- Dictionary preserves insertion order (Python 3.7+)
- Keys are display labels (used in UI)
- Values are minutes (used in calculation)
- Default is "15 min" (first key)

---

## 5. Implementation Plan

### 5.1 Phase-by-Phase Breakdown

#### Phase 1: Core Data Structures (15 minutes)

**Tasks**:
1. Add `TIME_FRAME_OPTIONS` class constant
2. Change `time_range_minutes` from instance variable to computed property
3. Add `selected_time_frame` reactive property declaration
4. Update `__init__` to handle initial time frame

**Files**: `log_preview.py`

**Dependencies**: None

**Testing**: Unit tests for mapping and property

#### Phase 2: UI Components (20 minutes)

**Tasks**:
1. Add import for container (if needed)
2. Create `#timeframe-controls` Horizontal container
3. Add "Time Frame:" Static label
4. Add SegmentedButton with 4 buttons
5. Add CSS styles for new components

**Files**: `log_preview.py`

**Dependencies**: Phase 1

**Testing**: Visual inspection (manual)

#### Phase 3: Event Handling (20 minutes)

**Tasks**:
1. Implement `watch_selected_time_frame()` watcher
2. Implement `on_timeframe_changed()` event handler
3. Implement `_clear_log_entries()` helper
4. Ensure proper container clearing before refresh

**Files**: `log_preview.py`

**Dependencies**: Phase 1, Phase 2

**Testing**: Manual click testing, then unit tests

#### Phase 4: Testing & Polish (45 minutes)

**Tasks**:
1. Add unit tests for time frame mapping
2. Add unit tests for default behavior
3. Add unit tests for property computation
4. Test edge cases (rapid switching, errors)
5. Verify loading states work correctly
6. Test keyboard navigation

**Files**: `test_log_preview.py`

**Dependencies**: Phases 1-3

**Testing**: pytest run

### 5.2 Dependencies Diagram

```
Phase 1 ─────┬─────▶ Phase 2 ─────┬─────▶ Phase 3 ─────▶ Phase 4
(Data)       │       (UI)         │       (Events)       (Tests)
             │                    │
             └────────────────────┘
           Can be done in parallel
           (CSS can be added early)
```

### 5.3 Estimated Effort Per Phase

| Phase | Task | Estimate | Cumulative |
|-------|------|----------|------------|
| 1 | Core Data Structures | 15 min | 15 min |
| 2 | UI Components | 20 min | 35 min |
| 3 | Event Handling | 20 min | 55 min |
| 4 | Testing & Polish | 45 min | 100 min |
| - | Buffer | 20 min | 120 min |
| **Total** | | | **2 hours** |

---

## 6. Code Specifications

### 6.1 Imports (Additions)

```python
# No new imports required!
# Button is already imported
# reactive is already imported
# Horizontal is already imported
```

### 6.2 Class Constants

```python
class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    """Modal screen for previewing and selecting log entries from a log group."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
    ]

    # Fetch parameters
    DEFAULT_TIME_RANGE_MINUTES: int = 15
    DEFAULT_LIMIT: int = 10

    # ADD: Time frame options for selector
    TIME_FRAME_OPTIONS: dict[str, int] = {
        "15 min": 15,
        "1 hour": 60,
        "8 hours": 480,
        "24 hours": 1440,
    }
```

### 6.3 Reactive Property Declaration

```python
class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    # ... existing code ...

    # ADD: Reactive property for time frame selection
    # Declared at class level, not in __init__
    selected_time_frame: reactive[str] = reactive("15 min")
```

### 6.4 Property Definition

```python
    @property
    def time_range_minutes(self) -> int:
        """
        Get current time range in minutes based on selected frame.

        Returns:
            Number of minutes for the selected time frame.
            Defaults to 15 if selection is invalid.
        """
        return self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)
```

### 6.5 Updated `__init__` Method

```python
    def __init__(
        self,
        log_group_name: str,
        datasource: "CloudWatchDataSource",
        time_range_minutes: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize log preview screen.

        Args:
            log_group_name: CloudWatch log group to preview
            datasource: CloudWatch data source for fetching logs
            time_range_minutes: Minutes of history to fetch (default: 15)
                               If provided, sets initial time frame selection.
            limit: Maximum entries to fetch (default: 10)
            **kwargs: Additional arguments for Screen
        """
        super().__init__(**kwargs)
        self.log_group_name = log_group_name
        self.datasource = datasource
        self.limit = limit or self.DEFAULT_LIMIT

        # Track fetched events and selection state
        self._events: list[dict[str, Any]] = []
        self._selected_ids: set[str] = set()

        # Set initial time frame if custom value provided
        if time_range_minutes:
            # Find matching time frame option
            for label, minutes in self.TIME_FRAME_OPTIONS.items():
                if minutes == time_range_minutes:
                    self.selected_time_frame = label
                    break
            # If no exact match, use closest or default (keeps "15 min")
```

### 6.6 Updated `compose` Method

```python
    def compose(self) -> ComposeResult:
        """Compose the preview screen layout."""
        with Container(id="preview-container"):
            # Header with log group name
            yield Static(
                f"Log Preview: {self.log_group_name}",
                id="preview-header",
            )

            # ADD: Time frame selector
            with Horizontal(id="timeframe-controls"):
                yield Static("Time Frame:", classes="timeframe-label")
                with Horizontal(id="timeframe-selector"):
                    for label in self.TIME_FRAME_OPTIONS.keys():
                        variant = "primary" if label == self.selected_time_frame else "default"
                        yield Button(label, variant=variant, classes="timeframe-btn")

            # Selection controls (existing)
            with Horizontal(id="selection-controls"):
                yield Button("Select All", id="select-all-btn", variant="default")
                yield Button("Deselect All", id="deselect-all-btn", variant="default")
                yield Static("0 of 0 selected", id="selection-counter")

            # Scrollable log entries container (existing)
            yield VerticalScroll(id="log-entries")

            # Action buttons (existing)
            with Horizontal(id="action-buttons"):
                yield Button(
                    "Add Selected to Context",
                    id="add-to-context-btn",
                    variant="success",
                    disabled=True,
                )
                yield Button("Close", id="close-btn", variant="default")
```

### 6.7 Watcher Method

```python
    def watch_selected_time_frame(self, new_frame: str) -> None:
        """
        Refresh logs when time frame selection changes.

        Called automatically by Textual when selected_time_frame changes.
        Clears current state and triggers a new fetch.

        Args:
            new_frame: The newly selected time frame label
        """
        logger.debug(f"Time frame changed to: {new_frame}")

        # Only refresh if we're already mounted (not during initial compose)
        if not self.is_mounted:
            return

        # Update button visual states
        self._update_timeframe_buttons()

        # Clear current state
        self._events.clear()
        self._selected_ids.clear()

        # Trigger refresh (exclusive worker handles concurrency)
        self._fetch_and_display_logs()
```

### 6.8 Event Handler

```python
    @on(Button.Pressed, "#timeframe-selector Button")
    def on_timeframe_changed(self, event: Button.Pressed) -> None:
        """
        Handle time frame button press.

        Updates the selected_time_frame reactive property, which
        triggers the watcher to refresh the log display.

        Args:
            event: Button pressed event
        """
        button_label = str(event.button.label)

        # Only process valid time frame options
        if button_label in self.TIME_FRAME_OPTIONS:
            # Skip if already selected
            if button_label != self.selected_time_frame:
                self.selected_time_frame = button_label

        # Stop propagation to prevent other handlers
        event.stop()
```

### 6.9 Helper Methods

```python
    def _update_timeframe_buttons(self) -> None:
        """Update time frame button visual states to reflect selection."""
        try:
            selector = self.query_one("#timeframe-selector", Horizontal)
            for button in selector.query(Button):
                label = str(button.label)
                if label == self.selected_time_frame:
                    button.variant = "primary"
                else:
                    button.variant = "default"
        except Exception:
            pass  # Buttons may not be mounted yet

    def _clear_log_entries(self) -> None:
        """Clear all log entry widgets from the container."""
        try:
            container = self.query_one("#log-entries", VerticalScroll)
            container.remove_children()
        except Exception:
            pass  # Container may not be mounted yet
```

### 6.10 Updated `_fetch_and_display_logs` Method

Only one line changes - the beginning of the method now clears the container:

```python
    @work(exclusive=True)
    async def _fetch_and_display_logs(self) -> None:
        """Worker to fetch and display logs asynchronously."""
        container = self.query_one("#log-entries", VerticalScroll)

        # ADD: Clear existing entries before loading new ones
        await container.remove_children()

        # Show loading state
        loading = Static(
            "Loading recent log entries...",
            classes="loading-state",
        )
        await container.mount(loading)

        # ... rest of method unchanged ...
```

### 6.11 CSS Additions

Add to `DEFAULT_CSS`:

```css
    #timeframe-controls {
        dock: top;
        height: 3;
        layout: horizontal;
        padding: 0 1;
        background: $surface;
        align: left middle;
    }

    .timeframe-label {
        width: auto;
        padding: 0 1 0 0;
        color: $text-muted;
        text-style: bold;
    }

    #timeframe-selector {
        width: auto;
        layout: horizontal;
        height: auto;
    }

    .timeframe-btn {
        min-width: 10;
        margin: 0 0 0 1;
    }

    .timeframe-btn:first-child {
        margin-left: 0;
    }
```

---

## 7. Data Structures

### 7.1 TIME_FRAME_OPTIONS Mapping

```python
TIME_FRAME_OPTIONS: dict[str, int] = {
    "15 min": 15,      # 15 minutes (default)
    "1 hour": 60,      # 60 minutes
    "8 hours": 480,    # 8 * 60 = 480 minutes
    "24 hours": 1440,  # 24 * 60 = 1440 minutes
}
```

**Type**: `dict[str, int]`
**Key**: Display label (shown in UI)
**Value**: Duration in minutes

### 7.2 State Variables

| Variable | Type | Initial Value | Purpose |
|----------|------|---------------|---------|
| `selected_time_frame` | `str` | `"15 min"` | Currently selected time frame label |
| `_events` | `list[dict[str, Any]]` | `[]` | Fetched log events |
| `_selected_ids` | `set[str]` | `set()` | Entry IDs selected by user |

### 7.3 Event Payloads

#### Button.Pressed Event

```python
# Accessing button information
event.button.label  # Text label of pressed button (e.g., "1 hour")
event.button.variant  # "default" or "primary"
```

#### Internal State After Time Frame Change

```python
# State snapshot after selecting "1 hour"
{
    "selected_time_frame": "1 hour",
    "time_range_minutes": 60,  # computed property
    "_events": [],  # cleared, will be populated by fetch
    "_selected_ids": set(),  # cleared
}
```

### 7.4 CloudWatch API Parameters

```python
# Parameters sent to fetch_logs()
{
    "log_group": "/aws/lambda/my-function",
    "start_time": 1708263045123,  # epoch ms (end_time - time_range_minutes * 60 * 1000)
    "end_time": 1708266645123,    # epoch ms (current time)
    "limit": 10,
}
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

#### 8.1.1 Test Time Frame Options Mapping

```python
def test_time_frame_options_mapping():
    """TIME_FRAME_OPTIONS should map labels to correct minutes."""
    assert LogPreviewScreen.TIME_FRAME_OPTIONS["15 min"] == 15
    assert LogPreviewScreen.TIME_FRAME_OPTIONS["1 hour"] == 60
    assert LogPreviewScreen.TIME_FRAME_OPTIONS["8 hours"] == 480
    assert LogPreviewScreen.TIME_FRAME_OPTIONS["24 hours"] == 1440
```

#### 8.1.2 Test Default Time Frame

```python
def test_default_time_frame():
    """Default time frame should be 15 min."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    assert screen.selected_time_frame == "15 min"
    assert screen.time_range_minutes == 15
```

#### 8.1.3 Test Time Range Minutes Property

```python
def test_time_range_minutes_property():
    """time_range_minutes should compute from selected_time_frame."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    # Test each time frame option
    screen.selected_time_frame = "15 min"
    assert screen.time_range_minutes == 15

    screen.selected_time_frame = "1 hour"
    assert screen.time_range_minutes == 60

    screen.selected_time_frame = "8 hours"
    assert screen.time_range_minutes == 480

    screen.selected_time_frame = "24 hours"
    assert screen.time_range_minutes == 1440
```

#### 8.1.4 Test Invalid Time Frame Fallback

```python
def test_invalid_time_frame_fallback():
    """Invalid time frame should fall back to 15 minutes."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    # Force invalid value (shouldn't happen in practice)
    screen.selected_time_frame = "invalid"
    assert screen.time_range_minutes == 15  # Fallback to default
```

#### 8.1.5 Test Custom Initial Time Range

```python
def test_initialization_with_matching_time_range():
    """Passing time_range_minutes that matches an option should set selection."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
        time_range_minutes=60,
    )

    # Should match "1 hour" option
    assert screen.selected_time_frame == "1 hour"
    assert screen.time_range_minutes == 60
```

#### 8.1.6 Test Initialization Backward Compatibility

```python
def test_initialization_backward_compatible():
    """Existing initialization pattern should still work."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    # Original assertions from existing test
    assert screen.log_group_name == "/aws/lambda/test"
    assert screen.datasource == datasource
    assert screen.time_range_minutes == LogPreviewScreen.DEFAULT_TIME_RANGE_MINUTES
    assert screen.limit == LogPreviewScreen.DEFAULT_LIMIT
```

### 8.2 Edge Cases to Cover

| Edge Case | Test Description | Expected Behavior |
|-----------|------------------|-------------------|
| Invalid selection | Set invalid value programmatically | Falls back to 15 min |
| Rapid switching | Click multiple buttons quickly | Only last selection processes |
| Same button click | Click already-selected button | No-op, no refresh |
| Initial mount | Watcher during compose | Should not double-fetch |

### 8.3 Integration Test Scenarios

#### Scenario 1: Full User Flow

```
Given: User opens log preview modal
When: User clicks "1 hour" button
Then:
  - "1 hour" button shows selected state
  - Loading indicator appears
  - Logs are fetched with 60-minute time range
  - Results display after fetch completes
  - Selection counter shows "0 of N selected"
```

#### Scenario 2: Sequential Time Frame Changes

```
Given: Modal showing 15-minute logs
When: User clicks "1 hour", then "8 hours", then "15 min"
Then:
  - Each click triggers refresh
  - Final state shows 15-minute logs
  - Only one fetch in progress at any time
```

#### Scenario 3: Time Frame with No Logs

```
Given: Log group with sparse activity
When: User selects "15 min" (no logs in window)
Then:
  - Empty state message displays
  - Message mentions the selected time frame
  - User can select different time frame
```

### 8.4 Mocking Approach for CloudWatch Calls

```python
@pytest.fixture
def mock_datasource():
    """Create mock CloudWatch datasource."""
    datasource = AsyncMock()
    datasource.fetch_logs.return_value = [
        {
            "timestamp": 1708263045123,
            "message": "Test log event 1",
            "log_stream": "2026/02/18/[$LATEST]abc123",
            "event_id": "event-001",
        },
        {
            "timestamp": 1708263044000,
            "message": "Test log event 2",
            "log_stream": "2026/02/18/[$LATEST]abc123",
            "event_id": "event-002",
        },
    ]
    return datasource


@pytest.mark.asyncio
async def test_fetch_uses_correct_time_range(mock_datasource):
    """fetch_logs should receive correct time range parameters."""
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=mock_datasource,
    )

    # Change time frame
    screen.selected_time_frame = "1 hour"

    # Would need to mount screen and run worker
    # Then verify:
    mock_datasource.fetch_logs.assert_called_with(
        log_group="/aws/lambda/test",
        start_time=ANY,  # end_time - 60*60*1000
        end_time=ANY,
        limit=10,
    )

    # Verify time range calculation
    call_args = mock_datasource.fetch_logs.call_args
    start_time = call_args.kwargs["start_time"]
    end_time = call_args.kwargs["end_time"]

    # Should be approximately 60 minutes (in milliseconds)
    time_diff_minutes = (end_time - start_time) / (60 * 1000)
    assert 59.9 < time_diff_minutes < 60.1
```

---

## 9. Edge Cases & Error Handling

### 9.1 No Logs Found in Time Frame

**Scenario**: User selects a time frame with no log activity.

**Current Behavior** (already implemented):
```python
container.mount(
    Static(
        f"No log entries found in the last {self.time_range_minutes} minutes.\n\n"
        "The log group may have no recent activity,\n"
        "or logs may be outside this time window.",
        classes="empty-state",
    )
)
```

**Enhancement**: The message already uses `self.time_range_minutes`, which will now be computed from `selected_time_frame`. The message will correctly show "60 minutes" when "1 hour" is selected.

**Optional UX Enhancement**: Consider updating the message for longer time frames:

```python
def _get_time_description(self) -> str:
    """Get human-readable time description for messages."""
    if self.time_range_minutes == 15:
        return "15 minutes"
    elif self.time_range_minutes == 60:
        return "1 hour"
    elif self.time_range_minutes == 480:
        return "8 hours"
    elif self.time_range_minutes == 1440:
        return "24 hours"
    else:
        return f"{self.time_range_minutes} minutes"
```

### 9.2 CloudWatch API Errors During Refresh

**Scenario**: CloudWatch returns an error when fetching with new time frame.

**Current Behavior** (already implemented):
- Errors are caught in `_fetch_and_display_logs`
- User-friendly error messages are displayed via `_format_error_message`
- Error state widget replaces loading indicator

**No Changes Needed**: Error handling already works correctly.

### 9.3 Rapid Time Frame Switching

**Scenario**: User clicks multiple time frame buttons in quick succession.

**Handled By**: `@work(exclusive=True)` decorator

**Behavior**:
1. First click starts fetch worker
2. Second click (while first is running) cancels first worker
3. New worker starts for second selection
4. Only the final selection's results display

**Code Path**:
```python
@work(exclusive=True)  # Key: exclusive=True
async def _fetch_and_display_logs(self) -> None:
    # Only one instance runs at a time
    # Previous instance is cancelled when new one starts
```

**Test Scenario**:
```python
async def test_rapid_switching_only_processes_last():
    """Rapid time frame changes should only show final selection's results."""
    # Click 15 min → 1 hour → 8 hours → 24 hours rapidly
    # Only 24 hours fetch should complete
    # No UI glitches or errors
```

### 9.4 Loading State Management

**Scenario**: Ensure loading indicator appears/disappears correctly.

**Current Flow**:
1. `_fetch_and_display_logs` called
2. Container cleared (via `remove_children()`)
3. Loading Static mounted
4. Fetch executes
5. Loading Static removed
6. Results or empty/error state mounted

**Edge Case**: Worker cancelled mid-fetch

**Handling**: When `@work(exclusive=True)` cancels a worker:
- The `await` in the cancelled worker raises `CancelledError`
- The new worker starts fresh with its own loading indicator
- No zombie loading indicators

**Recommendation**: Add explicit cleanup in case of cancellation:

```python
@work(exclusive=True)
async def _fetch_and_display_logs(self) -> None:
    container = self.query_one("#log-entries", VerticalScroll)

    # Clear any existing content
    await container.remove_children()

    loading = Static("Loading recent log entries...", classes="loading-state")

    try:
        await container.mount(loading)

        # ... fetch logic ...

    except asyncio.CancelledError:
        # Worker was cancelled (e.g., time frame changed again)
        # Clean up is handled by next worker
        raise
    finally:
        # Ensure loading is removed even on error
        try:
            loading.remove()
        except Exception:
            pass  # May already be removed or not mounted
```

### 9.5 Button State Synchronization

**Scenario**: Ensure button visual state matches `selected_time_frame`.

**Implementation**: `_update_timeframe_buttons()` synchronizes button variants:

```python
def _update_timeframe_buttons(self) -> None:
    """Update time frame button visual states to reflect selection."""
    try:
        selector = self.query_one("#timeframe-selector", Horizontal)
        for button in selector.query(Button):
            if str(button.label) == self.selected_time_frame:
                button.variant = "primary"
            else:
                button.variant = "default"
    except Exception:
        pass
```

**Called From**: `watch_selected_time_frame()`

---

## 10. Backward Compatibility

### 10.1 API Compatibility

| Usage Pattern | Before | After | Compatible? |
|---------------|--------|-------|-------------|
| Default init | `LogPreviewScreen(name, ds)` | Same | YES |
| With limit | `LogPreviewScreen(name, ds, limit=20)` | Same | YES |
| With time_range | `LogPreviewScreen(name, ds, time_range_minutes=30)` | Same (picks closest) | YES |
| Access time_range | `screen.time_range_minutes` | Same (now property) | YES |

### 10.2 Default Behavior Unchanged

- Modal opens with 15-minute time frame (same as before)
- Initial fetch uses 15 minutes (same as before)
- User can close modal without changing time frame (same experience)

### 10.3 No Breaking Changes

| Component | Change Type | Impact |
|-----------|-------------|--------|
| Constructor signature | No change | None |
| Return type | No change | None |
| Public methods | No change | None |
| Event handling | Addition only | None |

### 10.4 Migration Considerations

**None Required**. This is a purely additive change:
- Existing code continues to work without modification
- New functionality is opt-in (user clicks time frame buttons)
- No database migrations
- No configuration changes

---

## 11. Future Enhancements

### 11.1 Potential Follow-up Features

| Enhancement | Description | Complexity | Priority |
|-------------|-------------|------------|----------|
| Custom time frame | User-specified duration (e.g., "45 minutes") | Medium | Low |
| Absolute time range | Start/end datetime pickers | High | Low |
| Persist preference | Remember user's last selection | Low | Medium |
| Per-group preference | Different defaults per log group | Medium | Low |
| Time zone display | Show times in user's timezone | Low | Low |

### 11.2 Custom Time Frame Design (Future)

If custom time frames are needed later, consider:

```python
TIME_FRAME_OPTIONS: dict[str, int] = {
    "15 min": 15,
    "1 hour": 60,
    "8 hours": 480,
    "24 hours": 1440,
    "Custom...": -1,  # Special value triggers input dialog
}
```

With input validation:
- Minimum: 5 minutes
- Maximum: 7 days (10080 minutes)
- CloudWatch API supports up to 14 days

### 11.3 Extensibility Considerations

**Adding New Preset Time Frames**:

To add a new option (e.g., "4 hours"):

```python
TIME_FRAME_OPTIONS: dict[str, int] = {
    "15 min": 15,
    "1 hour": 60,
    "4 hours": 240,   # ADD THIS LINE
    "8 hours": 480,
    "24 hours": 1440,
}
```

No other code changes needed - the UI auto-generates buttons from dictionary keys.

**Changing Default Time Frame**:

```python
# Change reactive default
selected_time_frame: reactive[str] = reactive("1 hour")  # Was "15 min"

# Update DEFAULT_TIME_RANGE_MINUTES for backward compat
DEFAULT_TIME_RANGE_MINUTES: int = 60  # Was 15
```

---

## 12. Appendix

### 12.1 Complete File Diff Preview

```diff
--- a/src/logai/ui/screens/log_preview.py
+++ b/src/logai/ui/screens/log_preview.py
@@ -348,6 +348,14 @@ class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
     # Fetch parameters
     DEFAULT_TIME_RANGE_MINUTES: int = 15
     DEFAULT_LIMIT: int = 10
+
+    # Time frame options for selector
+    TIME_FRAME_OPTIONS: dict[str, int] = {
+        "15 min": 15,
+        "1 hour": 60,
+        "8 hours": 480,
+        "24 hours": 1440,
+    }
+
+    # Reactive property for time frame selection
+    selected_time_frame: reactive[str] = reactive("15 min")

     def __init__(
         ...
-        self.time_range_minutes = time_range_minutes or self.DEFAULT_TIME_RANGE_MINUTES
+
+        # Set initial time frame if custom value provided
+        if time_range_minutes:
+            for label, minutes in self.TIME_FRAME_OPTIONS.items():
+                if minutes == time_range_minutes:
+                    self.selected_time_frame = label
+                    break
+
+    @property
+    def time_range_minutes(self) -> int:
+        """Get current time range in minutes based on selected frame."""
+        return self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)
```

### 12.2 CSS Reference

```css
/* Time frame controls - full CSS block */
#timeframe-controls {
    dock: top;
    height: 3;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
    align: left middle;
}

.timeframe-label {
    width: auto;
    padding: 0 1 0 0;
    color: $text-muted;
    text-style: bold;
}

#timeframe-selector {
    width: auto;
    layout: horizontal;
    height: auto;
}

.timeframe-btn {
    min-width: 10;
    margin: 0 0 0 1;
}

.timeframe-btn:first-child {
    margin-left: 0;
}
```

### 12.3 CloudWatch API Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `logGroupName` | string | Log group to query |
| `startTime` | long | Start of time range (epoch ms) |
| `endTime` | long | End of time range (epoch ms) |
| `limit` | int | Max events to return (max 10000) |
| `filterPattern` | string | CloudWatch filter pattern (optional) |

**Time Calculation Formula**:
```python
end_time = int(time.time() * 1000)  # Current time in ms
start_time = end_time - (time_range_minutes * 60 * 1000)  # Subtract minutes as ms
```

### 12.4 Checklist for Implementation

```
[ ] Phase 1: Core Data Structures
    [ ] Add TIME_FRAME_OPTIONS constant
    [ ] Add selected_time_frame reactive property
    [ ] Change time_range_minutes to computed property
    [ ] Update __init__ for initial time frame

[ ] Phase 2: UI Components
    [ ] Add #timeframe-controls Horizontal
    [ ] Add "Time Frame:" label
    [ ] Add time frame buttons
    [ ] Add CSS styles

[ ] Phase 3: Event Handling
    [ ] Implement watch_selected_time_frame
    [ ] Implement on_timeframe_changed
    [ ] Implement _update_timeframe_buttons
    [ ] Update _fetch_and_display_logs to clear container

[ ] Phase 4: Testing
    [ ] Add test_time_frame_options_mapping
    [ ] Add test_default_time_frame
    [ ] Add test_time_range_minutes_property
    [ ] Add test_invalid_time_frame_fallback
    [ ] Add test_initialization_with_matching_time_range
    [ ] Verify existing tests pass
    [ ] Manual testing complete
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-18 | Saanvi | Initial design document |

---

**End of Design Document**
