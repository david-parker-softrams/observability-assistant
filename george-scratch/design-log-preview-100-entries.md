# Design Document: Log Preview "Load Last 100" Button

**Date**: February 19, 2026
**Author**: Saanvi (Senior Software Architect)
**Feature**: Add button to load last 100 log entries in preview modal
**Status**: APPROVED FOR IMPLEMENTATION

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [UI Design Decision](#2-ui-design-decision)
3. [Component Architecture](#3-component-architecture)
4. [Implementation Specification](#4-implementation-specification)
5. [State Management](#5-state-management)
6. [User Interaction Flow](#6-user-interaction-flow)
7. [CSS Specifications](#7-css-specifications)
8. [Error Handling](#8-error-handling)
9. [Testing Requirements](#9-testing-requirements)
10. [Code Examples](#10-code-examples)
11. [Integration Notes](#11-integration-notes)

---

## 1. Executive Summary

### Goal
Add a "Load Last 100" button to the log preview modal that allows users to fetch 100 log entries instead of the default 10, providing more historical context when needed.

### Approach
Following the proven pattern established by the time frame selector, we will:
- Add a reactive property (`current_limit`) to track the entry limit
- Add a new UI control row with the button and entry count display
- Implement a watcher to trigger data refresh when the limit changes
- Toggle button behavior (10 ↔ 100) for a clean user experience

### Risk Assessment
**Low Risk** - This is a straightforward enhancement:
- Datasource already supports configurable limits (no backend changes)
- Pattern is proven (copy from time frame selector)
- Single file modification (`log_preview.py`)
- Backwards compatible (default stays at 10)

### Estimated Effort
- Implementation: 2-3 hours
- Testing: 1-1.5 hours
- Code Review: 30 minutes
- **Total**: ~4-5 hours

---

## 2. UI Design Decision

### Decision: Option A - New Row Below Time Frame Selector

After reviewing the three placement options, I am selecting **Option A: New dedicated row** for the following reasons:

#### Why Option A (Selected)

| Factor | Assessment |
|--------|------------|
| **Visual Hierarchy** | Creates clear separation between fetch controls (time frame, entry limit) and selection controls |
| **Logical Grouping** | Groups "how much data to fetch" controls together above "what to do with data" controls |
| **Screen Real Estate** | Adds only 3 lines of height - acceptable trade-off for clarity |
| **User Workflow** | Natural top-to-bottom flow: choose time range → choose entry count → select entries |
| **Future Extensibility** | Could add more fetch controls later without UI restructuring |

#### Why Not Option B (Action Buttons Area)
- Mixes fetch controls with action buttons (Export/Cancel)
- Semantically incorrect: "Load 100" is a data fetch, not an action on selected items
- Would confuse the user about what the button does

#### Why Not Option C (Within Time Frame Row)
- Time frame row already has 4 buttons + label
- Would make the row too wide or require button size reduction
- Visual clutter concerns on smaller terminals

### UI Mockup (Final Design)

```
┌─────────────────────────────────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-function                            │  ← Header (existing)
├─────────────────────────────────────────────────────────────────┤
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]              │  ← Time frame (existing)
├─────────────────────────────────────────────────────────────────┤
│ [Load Last 100]                              Showing 10 entries │  ← NEW ROW
├─────────────────────────────────────────────────────────────────┤
│ [Select All] [Deselect All]                     0 of 10 selected│  ← Selection (existing)
├─────────────────────────────────────────────────────────────────┤
│ │ Entry 1  │ 2026-02-19 10:45:23.123 │ Log message preview...  │
│ │ Entry 2  │ 2026-02-19 10:45:22.456 │ Another log message...  │
│ │ Entry 3  │ 2026-02-19 10:45:21.789 │ Yet another message...  │
│ │   ...                                                         │
├─────────────────────────────────────────────────────────────────┤
│            [Add Selected to Context]  [Close]                   │  ← Actions (existing)
└─────────────────────────────────────────────────────────────────┘
```

### Button Design Specifications

| Property | Value | Rationale |
|----------|-------|-----------|
| **Label (default)** | "Load Last 100" | Clear, action-oriented, indicates what happens |
| **Label (after 100 loaded)** | "Show Last 10" | Allows user to toggle back to fewer entries |
| **ID** | `load-100-btn` | Consistent with existing button IDs |
| **Variant (default)** | `default` | Not primary action, secondary control |
| **Variant (active/100)** | `primary` | Visual indication that 100 mode is active |
| **Width** | `min-width: 16` | Accommodates "Show Last 10" label |

### Entry Count Display Specifications

| Property | Value | Rationale |
|----------|-------|-----------|
| **ID** | `entry-count-display` | Descriptive, consistent with existing patterns |
| **Format** | "Showing X entries" | Clear, matches user expectations |
| **Alignment** | Right-aligned | Balances button on left, mirrors selection counter |
| **Color** | `$text-muted` | Secondary information, not primary focus |

---

## 3. Component Architecture

### Widget Hierarchy

```
LogPreviewScreen (ModalScreen)
└── Container (id="preview-container")
    ├── Static (id="preview-header")                    ← Existing
    ├── Horizontal (id="timeframe-controls")            ← Existing
    │   ├── Static (classes="timeframe-label")
    │   └── Horizontal (id="timeframe-selector")
    │       └── Button × 4 (classes="timeframe-btn")
    │
    ├── Horizontal (id="entry-limit-controls")          ← NEW
    │   ├── Button (id="load-100-btn")                  ← NEW
    │   └── Static (id="entry-count-display")           ← NEW
    │
    ├── Horizontal (id="selection-controls")            ← Existing
    │   ├── Button (id="select-all-btn")
    │   ├── Button (id="deselect-all-btn")
    │   └── Static (id="selection-counter")
    ├── VerticalScroll (id="log-entries")               ← Existing
    └── Horizontal (id="action-buttons")                ← Existing
        ├── Button (id="add-to-context-btn")
        └── Button (id="close-btn")
```

### New Components Summary

| Component | Type | ID | Purpose |
|-----------|------|-----|---------|
| Container | `Horizontal` | `entry-limit-controls` | Row for entry limit controls |
| Button | `Button` | `load-100-btn` | Toggle between 10/100 entries |
| Display | `Static` | `entry-count-display` | Shows "Showing X entries" |

---

## 4. Implementation Specification

### 4.1 New Constants (After Line 382)

```python
# Fetch parameters
DEFAULT_TIME_RANGE_MINUTES: int = 15
DEFAULT_LIMIT: int = 10
LOAD_MORE_LIMIT: int = 100  # NEW - Limit when "Load Last 100" is active
```

**Design Note**: Using `LOAD_MORE_LIMIT` instead of `LOAD_100_LIMIT` for better semantics if we ever want to change the value.

### 4.2 New Reactive Property (After Line 393)

```python
# Reactive property for time frame selection
selected_time_frame: reactive[str] = reactive("15 min")

# NEW: Reactive property for entry limit
current_limit: reactive[int] = reactive(DEFAULT_LIMIT)
```

**Design Note**: Using `reactive[int]` with `DEFAULT_LIMIT` as default ensures:
- Type safety with the int generic
- Default 10 entries on modal open
- Automatic watcher triggering on changes

### 4.3 Compose Method Addition (After Line 479, Before Line 481)

Insert new UI section between `timeframe-controls` and `selection-controls`:

```python
# Time frame selector
with Horizontal(id="timeframe-controls"):
    # ... existing code ...

# NEW: Entry limit controls
with Horizontal(id="entry-limit-controls"):
    yield Button(
        "Load Last 100",
        id="load-100-btn",
        variant="default",
    )
    yield Static("", id="entry-count-display")

# Selection controls
with Horizontal(id="selection-controls"):
    # ... existing code ...
```

### 4.4 New Methods to Add

#### Method 1: Button Click Handler

```python
@on(Button.Pressed, "#load-100-btn")
def on_load_100_clicked(self, event: Button.Pressed) -> None:
    """
    Handle 'Load Last 100' button click.

    Toggles between DEFAULT_LIMIT (10) and LOAD_MORE_LIMIT (100).
    The watcher handles clearing state and triggering the fetch.
    """
    if self.current_limit == self.DEFAULT_LIMIT:
        self.current_limit = self.LOAD_MORE_LIMIT
    else:
        self.current_limit = self.DEFAULT_LIMIT

    event.stop()
```

#### Method 2: Limit Watcher

```python
def watch_current_limit(self, new_limit: int) -> None:
    """
    Refresh logs when entry limit changes.

    Called automatically by Textual when current_limit changes.
    Clears current state and triggers a new fetch with the new limit.

    Args:
        new_limit: The new entry limit (10 or 100)
    """
    logger.debug(f"Entry limit changed to: {new_limit}")

    # Only refresh if we're already mounted (not during initial compose)
    if not self.is_mounted:
        return

    # Update button visual state
    self._update_limit_button()

    # Clear current state
    self._events.clear()
    self._selected_ids.clear()

    # Trigger refresh (exclusive worker handles concurrency)
    self._fetch_and_display_logs()
```

#### Method 3: Button State Update

```python
def _update_limit_button(self) -> None:
    """Update the limit button's label and variant based on current state."""
    try:
        button = self.query_one("#load-100-btn", Button)
        if self.current_limit == self.LOAD_MORE_LIMIT:
            button.label = "Show Last 10"
            button.variant = "primary"
        else:
            button.label = "Load Last 100"
            button.variant = "default"
    except Exception:
        pass  # Button may not be mounted yet
```

#### Method 4: Entry Count Display Update

```python
def _update_entry_count_display(self) -> None:
    """Update the entry count display to show current number of entries."""
    try:
        display = self.query_one("#entry-count-display", Static)
        total = len(self._events)
        if total > 0:
            display.update(f"Showing {total} entries")
        else:
            display.update("")
    except Exception:
        pass  # Widget may not be mounted yet
```

### 4.5 Modification to _fetch_and_display_logs (Line 631)

Change:
```python
# BEFORE
limit=self.limit,

# AFTER
limit=self.current_limit,
```

### 4.6 Call Entry Count Update (After Line 651)

Add call to update entry count display after fetch completes:

```python
# Update selection counter
self._update_selection_counter()

# NEW: Update entry count display
self._update_entry_count_display()
```

---

## 5. State Management

### Reactive Property Flow

```
User clicks "Load Last 100"
         │
         ▼
on_load_100_clicked() → self.current_limit = 100
         │
         ▼
[Textual reactive system triggers]
         │
         ▼
watch_current_limit(new_limit=100)
         │
         ├─► _update_limit_button()      → Updates button label/variant
         │
         ├─► Clear _events and _selected_ids
         │
         └─► _fetch_and_display_logs()   → Worker fetches data
                      │
                      ▼
              [Data fetched]
                      │
                      ├─► _display_events()           → Shows entries
                      │
                      ├─► _update_selection_counter() → "0 of 100 selected"
                      │
                      └─► _update_entry_count_display() → "Showing 100 entries"
```

### State Variables

| Variable | Type | Purpose | Default |
|----------|------|---------|---------|
| `current_limit` | `reactive[int]` | Current fetch limit | 10 |
| `_events` | `list[dict]` | Fetched log events | `[]` |
| `_selected_ids` | `set[str]` | Selected entry IDs | `set()` |

### State Persistence Rules

| Scenario | `current_limit` Behavior |
|----------|--------------------------|
| Modal opens | Starts at 10 (default) |
| Click "Load Last 100" | Changes to 100 |
| Click "Show Last 10" | Changes back to 10 |
| Change time frame | **Preserves current limit** (stays at 10 or 100) |
| Close and reopen modal | Resets to 10 (new instance) |

**Design Decision**: Limit persists when changing time frame. This is more intuitive - if a user loads 100 entries and then changes to a different time window, they likely still want 100 entries from that new window.

---

## 6. User Interaction Flow

### Primary Flow: Load 100 Entries

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. User opens log preview modal                                  │
│    → Default: 10 entries loaded                                  │
│    → Button shows: "Load Last 100"                               │
│    → Display shows: "Showing 10 entries"                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. User clicks "Load Last 100"                                   │
│    → Loading state: "Loading recent log entries..."              │
│    → Button disabled during fetch? NO - use visual indication    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Fetch completes successfully                                  │
│    → Display updates: "Showing 100 entries"                      │
│    → Button changes: "Show Last 10" (primary variant)            │
│    → Selection counter: "0 of 100 selected"                      │
│    → 100 log entries displayed                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. User can toggle back to 10 entries                            │
│    → Click "Show Last 10"                                        │
│    → Returns to 10 entries display                               │
│    → Button returns to: "Load Last 100" (default variant)        │
└──────────────────────────────────────────────────────────────────┘
```

### Secondary Flow: Change Time Frame While at 100

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. User has 100 entries loaded (from "15 min" time frame)        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. User clicks "1 hour" time frame button                        │
│    → Time frame watcher triggers                                 │
│    → current_limit PRESERVED at 100                              │
│    → Fetch uses: time_range=60min, limit=100                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Result: 100 entries from the last hour displayed              │
│    → User gets expected behavior                                 │
└──────────────────────────────────────────────────────────────────┘
```

### Edge Case Flow: Fewer Than 100 Entries Exist

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. User clicks "Load Last 100"                                   │
│    → But only 47 entries exist in time window                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. Fetch returns 47 entries                                      │
│    → Display shows: "Showing 47 entries" (actual count)          │
│    → Button still shows: "Show Last 10" (limit is 100)           │
│    → No error - this is normal behavior                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. CSS Specifications

### New CSS Rules (Add to DEFAULT_CSS)

```css
#entry-limit-controls {
    height: 3;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
    align: left middle;
    width: 100%;
}

#entry-limit-controls Button {
    min-width: 16;
    margin: 0 1 0 0;
}

#entry-count-display {
    width: 1fr;
    text-align: right;
    padding: 1 1;
    color: $text-muted;
}
```

### CSS Design Rationale

| Property | Value | Rationale |
|----------|-------|-----------|
| `height: 3` | Matches other control rows (timeframe, selection) |
| `background: $surface` | Consistent with adjacent rows |
| `padding: 0 1` | Matches existing control rows |
| `min-width: 16` | Fits "Show Last 10" label (13 chars) with padding |
| `width: 1fr` on display | Pushes display to right, button stays left |
| `text-align: right` | Mirrors selection-counter alignment |
| `color: $text-muted` | Secondary info, same as selection counter |

### CSS Location

Insert after `#timeframe-selector` styles (around line 296) and before `#selection-controls`:

```css
/* Existing */
.timeframe-btn:first-child {
    margin-left: 0;
}

/* NEW: Entry limit controls */
#entry-limit-controls {
    height: 3;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
    align: left middle;
    width: 100%;
}

#entry-limit-controls Button {
    min-width: 16;
    margin: 0 1 0 0;
}

#entry-count-display {
    width: 1fr;
    text-align: right;
    padding: 1 1;
    color: $text-muted;
}

/* Existing */
#selection-controls {
    height: 3;
    ...
}
```

---

## 8. Error Handling

### Fetch Failure Handling

The existing error handling in `_fetch_and_display_logs()` already covers all failure cases:

```python
except Exception as e:
    logger.error(f"Failed to fetch logs for preview: {e}", exc_info=True)
    loading.remove()
    error_message = self._format_error_message(e)
    container.mount(
        Static(
            f"[red]Error loading logs:[/red]\n\n{error_message}",
            classes="error-state",
        )
    )
```

**No additional error handling needed** - existing patterns handle:
- ResourceNotFoundException (log group deleted)
- AccessDenied (permissions)
- ThrottlingException (rate limiting)
- Timeout errors
- Generic exceptions

### Edge Cases and Mitigations

| Edge Case | Handling | Implementation |
|-----------|----------|----------------|
| **Fetch fails** | Show error message, preserve button state | Existing error handler |
| **Fewer than 100 entries** | Display shows actual count | `len(self._events)` used in display |
| **Rapid button clicks** | Queued by exclusive worker | `@work(exclusive=True)` decorator |
| **Click during loading** | New fetch queued | Exclusive worker pattern |
| **Widget not mounted** | Silent pass | try/except in update methods |
| **Zero entries** | Entry count display hidden | `if total > 0` check |

### Button State During Fetch

**Design Decision**: Do NOT disable the button during fetch.

Rationale:
1. The `@work(exclusive=True)` decorator already prevents race conditions
2. Disabling the button creates a less responsive feel
3. The button label change provides sufficient visual feedback
4. If user clicks during fetch, the new request is simply queued

Alternative considered: Disable button and show "Loading..." label. Rejected as over-engineering for this use case.

---

## 9. Testing Requirements

### Unit Tests (For Raoul)

#### Test Group 1: Constants and Initialization

```python
def test_load_more_limit_constant():
    """Verify LOAD_MORE_LIMIT constant is 100."""
    assert LogPreviewScreen.LOAD_MORE_LIMIT == 100

def test_default_limit_constant():
    """Verify DEFAULT_LIMIT constant remains 10."""
    assert LogPreviewScreen.DEFAULT_LIMIT == 10

def test_initial_current_limit_is_default():
    """Verify current_limit starts at DEFAULT_LIMIT."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )
    assert screen.current_limit == LogPreviewScreen.DEFAULT_LIMIT
```

#### Test Group 2: Button Behavior

```python
def test_load_100_button_toggles_limit_10_to_100():
    """Clicking button when at 10 should set limit to 100."""
    # Setup screen at default limit (10)
    # Simulate button click
    # Assert current_limit == 100

def test_load_100_button_toggles_limit_100_to_10():
    """Clicking button when at 100 should set limit back to 10."""
    # Setup screen at LOAD_MORE_LIMIT (100)
    # Simulate button click
    # Assert current_limit == 10

def test_button_label_updates_on_limit_change():
    """Button label should change based on current limit."""
    # When limit is 10: "Load Last 100"
    # When limit is 100: "Show Last 10"

def test_button_variant_updates_on_limit_change():
    """Button variant should change based on current limit."""
    # When limit is 10: variant="default"
    # When limit is 100: variant="primary"
```

#### Test Group 3: Watcher Behavior

```python
def test_watch_current_limit_clears_events():
    """Watcher should clear _events when limit changes."""
    # Setup screen with some events
    # Change current_limit
    # Assert _events is empty

def test_watch_current_limit_clears_selections():
    """Watcher should clear _selected_ids when limit changes."""
    # Setup screen with some selections
    # Change current_limit
    # Assert _selected_ids is empty

def test_watch_current_limit_skips_when_unmounted():
    """Watcher should not fetch when screen is not mounted."""
    # Create unmounted screen
    # Change current_limit
    # Assert _fetch_and_display_logs was NOT called

def test_watch_current_limit_calls_fetch_when_mounted():
    """Watcher should trigger fetch when screen is mounted."""
    # Mock is_mounted to return True
    # Change current_limit
    # Assert _fetch_and_display_logs was called
```

#### Test Group 4: Entry Count Display

```python
def test_entry_count_display_shows_actual_count():
    """Display should show actual number of entries fetched."""
    # Setup screen with 47 events
    # Call _update_entry_count_display()
    # Assert display text is "Showing 47 entries"

def test_entry_count_display_hidden_when_empty():
    """Display should be empty when no events."""
    # Setup screen with 0 events
    # Call _update_entry_count_display()
    # Assert display text is ""

def test_entry_count_display_called_after_fetch():
    """Entry count should update after successful fetch."""
    # Verify _update_entry_count_display is called in _fetch_and_display_logs
```

#### Test Group 5: Integration with Time Frame

```python
def test_limit_persists_on_time_frame_change():
    """Current limit should persist when changing time frame."""
    # Set current_limit to 100
    # Change selected_time_frame
    # Assert current_limit is still 100

def test_fetch_uses_current_limit():
    """Fetch should use current_limit value."""
    # Set current_limit to 100
    # Call _fetch_and_display_logs
    # Assert datasource.fetch_logs was called with limit=100
```

#### Test Group 6: Edge Cases

```python
def test_rapid_limit_changes_handled():
    """Rapid limit changes should not cause race conditions."""
    # Change limit multiple times in quick succession
    # Assert only final state is reflected
    # (exclusive worker handles this automatically)

def test_update_methods_handle_unmounted_widgets():
    """Update methods should not crash if widgets not mounted."""
    # Call _update_limit_button() before widgets mounted
    # Should not raise exception

    # Call _update_entry_count_display() before widgets mounted
    # Should not raise exception
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_load_100_flow():
    """Full integration test: open modal → click load 100 → verify state."""
    # 1. Create and mount screen
    # 2. Verify default 10 entries
    # 3. Click "Load Last 100" button
    # 4. Verify 100 entries loaded
    # 5. Verify button label changed
    # 6. Verify entry count display updated

@pytest.mark.asyncio
async def test_load_100_with_time_frame_change():
    """Integration test: load 100 → change time frame → verify 100 persists."""
    # 1. Load 100 entries
    # 2. Change time frame to "1 hour"
    # 3. Verify fetch uses limit=100
    # 4. Verify entry count display updates
```

### Manual Testing Checklist

- [ ] Open log preview modal - verify 10 entries shown
- [ ] Click "Load Last 100" - verify loading state appears
- [ ] Verify 100 entries displayed (or fewer if < 100 exist)
- [ ] Verify button label changes to "Show Last 10"
- [ ] Verify button variant changes to primary
- [ ] Verify entry count shows "Showing X entries"
- [ ] Click "Show Last 10" - verify returns to 10 entries
- [ ] Test with each time frame option
- [ ] Load 100, then change time frame - verify limit persists
- [ ] Test with log group that has < 100 entries
- [ ] Test with empty log group
- [ ] Test rapid button clicking
- [ ] Verify selection works correctly with 100 entries
- [ ] Verify "Add to Context" works with selected entries

---

## 10. Code Examples

### Complete Method Implementations

#### on_load_100_clicked

```python
@on(Button.Pressed, "#load-100-btn")
def on_load_100_clicked(self, event: Button.Pressed) -> None:
    """
    Handle 'Load Last 100' button click.

    Toggles between DEFAULT_LIMIT (10) and LOAD_MORE_LIMIT (100).
    The watcher automatically handles clearing state and triggering fetch.

    Args:
        event: Button pressed event
    """
    # Toggle between 10 and 100
    if self.current_limit == self.DEFAULT_LIMIT:
        self.current_limit = self.LOAD_MORE_LIMIT
    else:
        self.current_limit = self.DEFAULT_LIMIT

    # Stop propagation to prevent other handlers
    event.stop()
```

#### watch_current_limit

```python
def watch_current_limit(self, new_limit: int) -> None:
    """
    Refresh logs when entry limit changes.

    Called automatically by Textual when current_limit reactive property changes.
    Clears current state and triggers a new fetch with the updated limit.

    Args:
        new_limit: The new entry limit (10 or 100)
    """
    logger.debug(f"Entry limit changed to: {new_limit}")

    # Only refresh if we're already mounted (not during initial compose)
    if not self.is_mounted:
        return

    # Update button visual state
    self._update_limit_button()

    # Clear current state to prepare for new data
    self._events.clear()
    self._selected_ids.clear()

    # Trigger refresh (exclusive worker handles concurrency)
    self._fetch_and_display_logs()
```

#### _update_limit_button

```python
def _update_limit_button(self) -> None:
    """
    Update the limit button's label and variant based on current state.

    When at default (10): Shows "Load Last 100" with default variant
    When at 100: Shows "Show Last 10" with primary variant
    """
    try:
        button = self.query_one("#load-100-btn", Button)
        if self.current_limit == self.LOAD_MORE_LIMIT:
            button.label = "Show Last 10"
            button.variant = "primary"
        else:
            button.label = "Load Last 100"
            button.variant = "default"
    except Exception:
        pass  # Button may not be mounted yet
```

#### _update_entry_count_display

```python
def _update_entry_count_display(self) -> None:
    """
    Update the entry count display to show current number of entries.

    Shows "Showing X entries" where X is the actual count fetched.
    Display is empty when no entries exist.
    """
    try:
        display = self.query_one("#entry-count-display", Static)
        total = len(self._events)
        if total > 0:
            display.update(f"Showing {total} entries")
        else:
            display.update("")
    except Exception:
        pass  # Widget may not be mounted yet
```

### Compose Method Addition

```python
def compose(self) -> ComposeResult:
    """Compose the preview screen layout."""
    with Container(id="preview-container"):
        # Header with log group name
        yield Static(
            f"Log Preview: {self.log_group_name}",
            id="preview-header",
        )

        # Time frame selector
        with Horizontal(id="timeframe-controls"):
            yield Static("Time Frame:", classes="timeframe-label")
            with Horizontal(id="timeframe-selector"):
                for label in self.TIME_FRAME_OPTIONS.keys():
                    variant: Literal["default", "primary"] = (
                        "primary" if label == self.selected_time_frame else "default"
                    )
                    yield Button(label, variant=variant, classes="timeframe-btn")

        # NEW: Entry limit controls
        with Horizontal(id="entry-limit-controls"):
            yield Button(
                "Load Last 100",
                id="load-100-btn",
                variant="default",
            )
            yield Static("", id="entry-count-display")

        # Selection controls
        with Horizontal(id="selection-controls"):
            yield Button("Select All", id="select-all-btn", variant="default")
            yield Button("Deselect All", id="deselect-all-btn", variant="default")
            yield Static("0 of 0 selected", id="selection-counter")

        # Scrollable log entries container
        yield VerticalScroll(id="log-entries")

        # Action buttons
        with Horizontal(id="action-buttons"):
            yield Button(
                "Add Selected to Context",
                id="add-to-context-btn",
                variant="success",
                disabled=True,
            )
            yield Button("Close", id="close-btn", variant="default")
```

---

## 11. Integration Notes

### Compatibility with Existing Features

| Feature | Compatibility | Notes |
|---------|---------------|-------|
| **Time Frame Selector** | Full | Limit persists across time frame changes |
| **Select All/Deselect** | Full | Works with any number of entries |
| **Add to Context** | Full | Works with selected entries regardless of limit |
| **Export** | Full | Not affected by this change |
| **Keyboard Navigation** | Full | Escape still closes modal |

### Files Modified

**Only one file needs modification:**
- `src/logai/ui/screens/log_preview.py`

**No changes to:**
- `src/logai/providers/datasources/cloudwatch.py` (already supports limit parameter)
- Any configuration files
- Any other UI components

### Implementation Order

Jackie should implement in this order:

1. **Constants** - Add `LOAD_MORE_LIMIT = 100` after line 382
2. **Reactive Property** - Add `current_limit: reactive[int]` after line 393
3. **CSS** - Add styles for `#entry-limit-controls` (after line 305)
4. **Compose** - Add new `Horizontal(id="entry-limit-controls")` section (between lines 479-481)
5. **Methods** - Add all four new methods:
   - `on_load_100_clicked()`
   - `watch_current_limit()`
   - `_update_limit_button()`
   - `_update_entry_count_display()`
6. **Fetch Update** - Change line 631 from `self.limit` to `self.current_limit`
7. **Display Update Call** - Add `self._update_entry_count_display()` after line 651

### Code Review Checklist (For Han-Ron)

- [ ] Pattern matches time frame selector implementation?
- [ ] Reactive property properly typed as `reactive[int]`?
- [ ] Watcher has `is_mounted` check to prevent early execution?
- [ ] Button handler calls `event.stop()` to prevent propagation?
- [ ] No datasource changes made (shouldn't be needed)?
- [ ] Error handling in update methods uses try/except pass pattern?
- [ ] CSS follows existing naming conventions?
- [ ] New UI section placed correctly in compose()?
- [ ] Fetch uses `self.current_limit` not `self.limit`?
- [ ] Entry count display called after fetch in success path?

---

## Appendix A: Design Decisions Summary

| Decision | Choice | Alternative Considered | Rationale |
|----------|--------|------------------------|-----------|
| Button Placement | New dedicated row | In action buttons area | Better semantic grouping |
| Button Behavior | Toggle (10↔100) | Two separate buttons | Simpler UI, saves space |
| Limit on Time Change | Preserve limit | Reset to 10 | More intuitive UX |
| Button During Load | Stay enabled | Disable during fetch | Exclusive worker handles race |
| Entry Count Location | Right-aligned in row | Below entries | Mirrors selection counter |
| Constant Name | `LOAD_MORE_LIMIT` | `LOAD_100_LIMIT` | More generic if value changes |

---

## Appendix B: Related Documents

- **Requirements**: `/george-scratch/requirements-log-preview-last-100.md`
- **Investigation Summary**: `/george-scratch/INVESTIGATION-SUMMARY-LOG-PREVIEW.md`
- **Quick Reference**: `/george-scratch/QUICK-REFERENCE-LOAD-100.md`
- **Full Investigation**: `/george-scratch/investigation-log-preview-100-entries.md`

---

**Document Status**: APPROVED FOR IMPLEMENTATION
**Author**: Saanvi (Senior Software Architect)
**Reviewed By**: Pending George (TPM) review
**Implementation Assigned To**: Jackie
**Testing Assigned To**: Raoul
**Code Review Assigned To**: Han-Ron

---

*End of Design Document*
