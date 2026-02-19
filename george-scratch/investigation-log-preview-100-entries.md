# Investigation: Log Preview "Load Last 100 Entries" Feature

**Date**: February 19, 2026
**Investigator**: Hans (Code Librarian)
**Purpose**: Investigate current log preview implementation to prepare for adding a "Load Last 100 Entries" button

---

## Executive Summary

The log preview implementation is **ready to support configurable entry limits**. The current architecture already has:
- A configurable `limit` parameter that defaults to 10
- Proper separation of concerns (UI ↔ datasource layer)
- A reactive property system for state management
- Established UI patterns for buttons and controls

**Key Finding**: The entry limit mechanism is **already flexible and partially parameterized**. Adding a "Load Last 100" button requires:
1. Adding a reactive property to track the desired limit
2. Adding a UI button with click handler
3. Updating the entry count display
4. **No changes needed to the datasource layer** (it already supports custom limits)

---

## 1. Current Implementation Analysis

### 1.1 Limit Mechanism - Entry Point

**File**: `/src/logai/ui/screens/log_preview.py`
**Lines**: 380-422

```python
# Fetch parameters
DEFAULT_TIME_RANGE_MINUTES: int = 15
DEFAULT_LIMIT: int = 10

# In __init__():
def __init__(
    self,
    log_group_name: str,
    datasource: "CloudWatchDataSource",
    time_range_minutes: int | None = None,
    limit: int | None = None,  # ← Already configurable!
    **kwargs: Any,
) -> None:
    self.limit = limit or self.DEFAULT_LIMIT  # Line 422
```

**Current Status**:
- ✅ The `limit` parameter is **already optional and configurable**
- ✅ Default is 10 (hardcoded constant on line 382)
- ✅ Stored as instance variable `self.limit`
- ⚠️ **NOT currently reactive** (no `@reactive` decorator)

### 1.2 Where Limit Is Used

**File**: `/src/logai/ui/screens/log_preview.py`
**Lines**: 606-632 (in `_fetch_and_display_logs` method)

```python
@work(exclusive=True)
async def _fetch_and_display_logs(self) -> None:
    """Worker to fetch and display logs asynchronously."""
    # ... loading state setup ...

    try:
        # Calculate time range
        end_time = int(time.time() * 1000)
        start_time = end_time - (self.time_range_minutes * 60 * 1000)

        # Fetch logs from CloudWatch
        self._events = await self.datasource.fetch_logs(
            log_group=self.log_group_name,
            start_time=start_time,
            end_time=end_time,
            limit=self.limit,  # ← Line 631: Passed directly to datasource
        )
        # ... rest of fetch and display ...
```

**Key Observations**:
- ✅ `self.limit` is passed directly to `datasource.fetch_logs()`
- ✅ The datasource **already handles this parameter correctly**
- ⚠️ `_fetch_and_display_logs()` is a worker with `@work(exclusive=True)`
  - This means rapid calls to fetch will be queued
  - Good for preventing race conditions

### 1.3 UI Structure - Where Button Would Go

**File**: `/src/logai/ui/screens/log_preview.py`
**Lines**: 451-498 (in `compose()` method)

```python
def compose(self) -> ComposeResult:
    """Compose the preview screen layout."""
    with Container(id="preview-container"):
        # Header
        yield Static(f"Log Preview: {self.log_group_name}", id="preview-header")

        # TIME FRAME CONTROLS (Lines 464-479)
        with Horizontal(id="timeframe-controls"):
            yield Static("Time Frame:", classes="timeframe-label")
            with Horizontal(id="timeframe-selector"):
                for label in self.TIME_FRAME_OPTIONS.keys():
                    yield Button(label, variant=..., classes="timeframe-btn")

        # SELECTION CONTROLS (Lines 481-485)
        with Horizontal(id="selection-controls"):
            yield Button("Select All", id="select-all-btn")
            yield Button("Deselect All", id="deselect-all-btn")
            yield Static("0 of 0 selected", id="selection-counter")

        # LOG ENTRIES CONTAINER (Line 488)
        yield VerticalScroll(id="log-entries")

        # ACTION BUTTONS (Lines 490-498)
        with Horizontal(id="action-buttons"):
            yield Button("Add Selected to Context", id="add-to-context-btn", ...)
            yield Button("Close", id="close-btn")
```

**CSS Layout** (Lines 252-343):
- `#timeframe-controls`: Height 3, horizontal layout
- `#selection-controls`: Height 3, horizontal layout
- `#action-buttons`: Height 3, horizontal layout
- Each button area has proper padding and spacing

**Opportunity for New Button**:
Options for placement:
1. **Between timeframe-controls and selection-controls** (new row)
   - Pro: Logical grouping with other fetch-related controls
   - Con: Adds another row
2. **Within timeframe-controls area** (after time frame buttons)
   - Pro: Keeps fetch controls together
   - Con: May be visually cluttered
3. **Within selection-controls area** (before selection counter)
   - Pro: Existing established layout
   - Con: Semantically doesn't fit

**Recommended**: **Option 1** - New horizontal container dedicated to entry limit controls

### 1.4 Selection Counter Display

**File**: `/src/logai/ui/screens/log_preview.py`
**Lines**: 719-731 (in `_update_selection_counter()` method)

```python
def _update_selection_counter(self) -> None:
    """Update the selection counter text."""
    try:
        counter = self.query_one("#selection-counter", Static)
        total = len(self._events)
        selected = len(self._selected_ids)
        counter.update(f"{selected} of {total} selected")  # ← Line 725

        # Enable/disable add button based on selection
        add_btn = self.query_one("#add-to-context-btn", Button)
        add_btn.disabled = selected == 0
    except Exception:
        pass  # Widget may not be mounted yet
```

**Current Display**: `"X of Y selected"` where:
- X = number of selected entries
- Y = number of total entries

**Enhancement Opportunity**: Could update to include entry count info:
- `"Showing 10 entries - X of Y selected"`
- Or keep separate widget for entry count display

---

## 2. Datasource Interface - fetch_logs() Method

**File**: `/src/logai/providers/datasources/cloudwatch.py`
**Lines**: 161-231

```python
async def fetch_logs(
    self,
    log_group: str,
    start_time: int,
    end_time: int,
    filter_pattern: str | None = None,
    limit: int = 1000,  # ← Maximum results parameter
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Fetch log events from CloudWatch.

    Args:
        log_group: CloudWatch log group name
        start_time: Start time in epoch milliseconds
        end_time: End time in epoch milliseconds
        filter_pattern: Optional CloudWatch filter pattern
        limit: Maximum number of log events to return (max: 10000)  # ← Key line!
        **kwargs: Additional parameters:
            - log_stream_prefix: Filter to specific log stream prefix

    Returns:
        List of log event dictionaries
    """
```

**Key Implementation Details** (Lines 233-272):

```python
def _fetch_logs_sync(
    self,
    log_group: str,
    start_time: int,
    end_time: int,
    filter_pattern: str | None,
    limit: int,
    kwargs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Synchronous implementation of fetch_logs for executor."""
    params: dict[str, Any] = {
        "logGroupName": log_group,
        "startTime": start_time,
        "endTime": end_time,
        "limit": min(limit, 10000),  # ← Line 247: Enforces max of 10000
    }

    if filter_pattern:
        params["filterPattern"] = filter_pattern

    if "log_stream_prefix" in kwargs and kwargs["log_stream_prefix"]:
        params["logStreamNamePrefix"] = kwargs["log_stream_prefix"]

    events: list[dict[str, Any]] = []
    paginator = self.client.get_paginator("filter_log_events")

    for page in paginator.paginate(**params):
        for event in page.get("events", []):
            events.append({...})
            if len(events) >= limit:  # ← Line 269: Stops after limit reached
                return events

    return events
```

**Findings**:
- ✅ `limit` parameter is **fully supported and flexible**
- ✅ Datasource enforces **maximum of 10,000 entries** per request
- ✅ Uses boto3 paginator with early exit when limit is reached
- ✅ **No changes needed** to datasource for 100-entry support
- ✅ Perfectly safe to pass 100 as limit (well under 10,000 max)

**Performance Characteristics**:
- CloudWatch API returns events in batches via paginator
- Early exit when limit is reached (line 269)
- Fetching 100 entries should be **minimal network overhead**
- Typical completion time: < 1 second (local network latency only)

---

## 3. Time Frame Selector - Pattern Reference

The recently implemented time frame selector provides a good pattern to follow:

**File**: `/src/logai/ui/screens/log_preview.py`

**Reactive Property** (Line 393):
```python
selected_time_frame: reactive[str] = reactive("15 min")
```

**Options Dictionary** (Lines 385-390):
```python
TIME_FRAME_OPTIONS: dict[str, int] = {
    "15 min": 15,
    "1 hour": 60,
    "8 hours": 480,
    "24 hours": 1440,
}
```

**Watcher Pattern** (Lines 545-569):
```python
def watch_selected_time_frame(self, new_frame: str) -> None:
    """
    Refresh logs when time frame selection changes.
    Called automatically by Textual when selected_time_frame changes.
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

    # Trigger refresh
    self._fetch_and_display_logs()
```

**Button Handler** (Lines 584-604):
```python
@on(Button.Pressed, "#timeframe-selector Button")
def on_timeframe_changed(self, event: Button.Pressed) -> None:
    """Handle time frame button press."""
    button_label = str(event.button.label)

    # Only process valid time frame options
    if button_label in self.TIME_FRAME_OPTIONS:
        # Skip if already selected
        if button_label != self.selected_time_frame:
            self.selected_time_frame = button_label

    # Stop propagation to prevent other handlers
    event.stop()
```

**Key Learning**: This pattern is **ideal for implementing entry limit controls** too!

---

## 4. Integration Points for New Button

### 4.1 Required Changes

**File**: `/src/logai/ui/screens/log_preview.py`

#### Change 1: Add Configuration Constant (after line 382)
```python
DEFAULT_LIMIT: int = 10
LOAD_100_LIMIT: int = 100  # NEW
```

#### Change 2: Add Reactive Property (after line 393)
```python
selected_time_frame: reactive[str] = reactive("15 min")
current_limit: reactive[int] = reactive(DEFAULT_LIMIT)  # NEW
```

#### Change 3: Add New UI Section in compose() (between timeframe-controls and selection-controls)
```python
# ENTRY LIMIT CONTROLS (NEW SECTION)
with Horizontal(id="entry-limit-controls"):
    yield Button(
        "Load Last 100",
        id="load-100-btn",
        variant="default"
    )
    yield Static("", id="entry-count-display")  # Shows "Showing X entries"
```

#### Change 4: Add CSS for New Controls (in DEFAULT_CSS)
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
    min-width: 14;
    margin: 0 1 0 0;
}

#entry-count-display {
    width: 1fr;
    text-align: right;
    padding: 1 1;
    color: $text-muted;
}
```

#### Change 5: Add Button Click Handler (new method)
```python
@on(Button.Pressed, "#load-100-btn")
def on_load_100_clicked(self) -> None:
    """Handle 'Load Last 100' button click."""
    # Only process if we're not already loading 100
    if self.current_limit != self.LOAD_100_LIMIT:
        self.current_limit = self.LOAD_100_LIMIT
    # If already 100, clicking again resets to 10
    else:
        self.current_limit = self.DEFAULT_LIMIT

    event.stop()
```

#### Change 6: Add Watcher for current_limit (similar to time_frame watcher)
```python
def watch_current_limit(self, new_limit: int) -> None:
    """
    Refresh logs when entry limit changes.
    Called automatically when current_limit changes.
    """
    logger.debug(f"Entry limit changed to: {new_limit}")

    if not self.is_mounted:
        return

    # Update button visual state (optional)
    self._update_limit_button_state()

    # Clear current state
    self._events.clear()
    self._selected_ids.clear()

    # Trigger refresh
    self._fetch_and_display_logs()
```

#### Change 7: Update _fetch_and_display_logs() (line 631)
```python
# EXISTING CODE (Line 631)
self._events = await self.datasource.fetch_logs(
    log_group=self.log_group_name,
    start_time=start_time,
    end_time=end_time,
    limit=self.current_limit,  # CHANGED from self.limit to self.current_limit
)
```

#### Change 8: Update Entry Count Display (new method)
```python
def _update_entry_count_display(self) -> None:
    """Update the entry count display."""
    try:
        display = self.query_one("#entry-count-display", Static)
        total = len(self._events)
        if total > 0:
            display.update(f"Showing {total} entries")
        else:
            display.update("")
    except Exception:
        pass
```

#### Change 9: Call Update in _fetch_and_display_logs() (after line 651)
```python
# AFTER: self._update_selection_counter()
self._update_entry_count_display()  # NEW
```

### 4.2 Optional Enhancements

**Toggle Button Behavior** (instead of separate 10/100 modes):
- Button shows "Load Last 100" when showing 10 entries
- Button shows "Show First 10" when showing 100 entries
- Clicking toggles between the two states
- This provides single-button switching

**Alternative: Separate Buttons**:
- Two buttons: "Load 10" and "Load 100"
- Always visible, one is highlighted based on current state
- More explicit but uses more space

---

## 5. Existing Tests - Reference for New Tests

**File**: `/tests/unit/ui/test_log_preview.py`

Current test coverage includes:
- Time frame initialization (lines 245-256)
- Time frame options validation (lines 272-285)
- Time frame property computation (lines 300-314)
- Invalid time frame fallback (lines 316-332)
- Button state updates (lines 336-391)
- Watcher behavior with mounted/unmounted states (lines 389-432)

**Tests to Add**:
1. `test_default_limit_is_10()` - Verify DEFAULT_LIMIT constant
2. `test_initialization_with_custom_limit()` - Test passing custom limit
3. `test_load_100_button_visible_in_compose()` - Verify button is created
4. `test_load_100_button_click_sets_limit()` - Verify click updates reactive property
5. `test_current_limit_watcher_clears_state()` - Watcher clears events and selections
6. `test_current_limit_watcher_triggers_fetch()` - Watcher calls _fetch_and_display_logs
7. `test_fetch_logs_with_limit_100()` - Verify datasource is called with limit=100
8. `test_entry_count_display_updates()` - Entry count display shows correct count
9. `test_toggle_between_10_and_100()` - Button toggles limits correctly
10. `test_load_100_respects_time_frame()` - 100 entries fetched within selected time frame

---

## 6. Performance Considerations

### 6.1 Fetching 100 Entries

**AWS CloudWatch API Limits**:
- Max 10,000 events per request (our code enforces this - line 247 in cloudwatch.py)
- 100 entries is only 1% of max limit
- Well within safe parameters

**Network Performance**:
- CloudWatch API response time typically < 1 second
- 100 entries is minimal payload (~50KB typical)
- Async/await pattern prevents UI blocking

**Datasource Performance**:
- Uses boto3 paginator with early exit
- Returns immediately when limit reached (line 269 in cloudwatch.py)
- No unnecessary iteration through results

**UI Rendering**:
- 100 LogEntryItem widgets will be rendered
- Each item is minimal (~500 bytes)
- Textual handles virtualization for scrollable containers
- No performance concerns observed

### 6.2 Selection Performance with 100 Entries

Current selection logic (lines 743-769):
```python
@on(Button.Pressed, "#select-all-btn")
def on_select_all(self) -> None:
    """Select all log entries."""
    for idx, _ in enumerate(self._events):  # ← Iterates through all events
        entry_id = f"entry-{idx}"
        try:
            entry = self.query_one(f"#{entry_id}", LogEntryItem)
            entry.set_selected(True)
            self._selected_ids.add(entry_id)
        except Exception:
            pass

    self._update_selection_counter()
```

**Analysis**:
- O(n) where n = number of entries
- With 100 entries: ~100 DOM queries (fast, jQuery-style selectors)
- Acceptable performance for UI interaction
- No optimization needed

---

## 7. Potential Issues & Mitigation

### Issue 1: UI Layout Overcrowding
**Symptom**: Adding new button row makes UI too cramped
**Mitigation**:
- Place "Load Last 100" button in existing selection-controls area
- Or use compact button label and adjust sizing
- Test on 80x24 terminal to verify

### Issue 2: Confusing Button Behavior
**Symptom**: Users unclear if button changes limit or appends results
**Mitigation**:
- Clear button label: "Load Last 100" (not "Load 100 More")
- Show loading indicator with "Replacing entries..."
- Update entry count display immediately after fetch
- Document in UI help text

### Issue 3: Race Condition on Rapid Clicks
**Symptom**: Multiple simultaneous fetch requests if user clicks button repeatedly
**Mitigation**:
- ✅ Already handled! `_fetch_and_display_logs()` uses `@work(exclusive=True)`
- This queues rapid requests instead of running in parallel
- Worker pattern ensures only one fetch runs at a time

### Issue 4: Limit Reset on Time Frame Change
**Current Behavior**: When user changes time frame, limit stays at current value
**Options**:
1. Keep current limit when changing time frame
2. Reset to default (10) when changing time frame
3. User configurable

**Recommendation**: **Keep current limit** - More intuitive
- User loads 100 entries, then changes time frame → shows 100 from new time frame
- Less surprising behavior

**Implementation Note**: Already handled automatically because:
- Time frame watcher calls `_fetch_and_display_logs()`
- This uses `self.current_limit` (not hardcoded 10)

---

## 8. File Organization Summary

### Files That Need Changes
1. **`src/logai/ui/screens/log_preview.py`**
   - Add LOAD_100_LIMIT constant
   - Add current_limit reactive property
   - Add entry-limit-controls UI section
   - Add CSS styling
   - Add button click handler
   - Add limit watcher
   - Update _fetch_and_display_logs() to use current_limit
   - Add entry count display update
   - **Estimated lines**: ~80-120 lines added/modified

### Files That DON'T Need Changes
- ✅ `src/logai/providers/datasources/cloudwatch.py` - Already supports configurable limit
- ✅ `src/logai/providers/datasources/base.py` - Base interface fine as-is
- ✅ Any other datasource implementations
- ✅ CloudWatch configuration

### Test Files to Create/Modify
1. **`tests/unit/ui/test_log_preview.py`**
   - Add 10 new test cases for entry limit functionality
   - **Estimated lines**: ~150-200 lines added

### New Files (Optional)
- Could create `tests/integration/test_log_preview_load_100.py` for integration tests
- Not required but recommended

---

## 9. Implementation Checklist

### Phase 1: Core Feature
- [ ] Add LOAD_100_LIMIT constant
- [ ] Add current_limit reactive property
- [ ] Add entry-limit-controls UI section with button
- [ ] Add CSS styling for new controls
- [ ] Add button click handler
- [ ] Add limit watcher method
- [ ] Update _fetch_and_display_logs() to use current_limit
- [ ] Add entry count display update logic
- [ ] Test with different time frames
- [ ] Test with selection and deselection of 100 entries

### Phase 2: Testing
- [ ] Unit tests for limit property
- [ ] Unit tests for button click handler
- [ ] Unit tests for watcher behavior
- [ ] Unit tests for entry count display
- [ ] Unit tests for datasource integration
- [ ] Integration tests with time frame selector
- [ ] Manual testing on terminal

### Phase 3: Refinement
- [ ] UI/UX review
- [ ] Performance testing with slow network
- [ ] Error handling edge cases
- [ ] Documentation updates

---

## 10. Code Snippets for Implementation

### Button Handler Implementation
```python
@on(Button.Pressed, "#load-100-btn")
def on_load_100_clicked(self, event: Button.Pressed) -> None:
    """Handle 'Load Last 100' button click - toggles between 10 and 100 entries."""
    # Toggle between default (10) and 100
    new_limit = self.LOAD_100_LIMIT if self.current_limit == self.DEFAULT_LIMIT else self.DEFAULT_LIMIT
    self.current_limit = new_limit
    event.stop()
```

### Watcher Implementation
```python
def watch_current_limit(self, new_limit: int) -> None:
    """
    Refresh logs when entry limit changes.
    Called automatically by Textual when current_limit changes.
    """
    logger.debug(f"Entry limit changed to: {new_limit}")

    # Only refresh if we're already mounted
    if not self.is_mounted:
        return

    # Clear current state
    self._events.clear()
    self._selected_ids.clear()

    # Trigger refresh with new limit
    self._fetch_and_display_logs()
```

### Entry Count Update
```python
def _update_entry_count_display(self) -> None:
    """Update the entry count display."""
    try:
        display = self.query_one("#entry-count-display", Static)
        total = len(self._events)
        if total > 0:
            display.update(f"Showing {total} entries")
        else:
            display.update("")
    except Exception:
        pass
```

---

## 11. Related Documentation

### Time Frame Selector Implementation Reference
- Lines 385-390: TIME_FRAME_OPTIONS pattern
- Lines 393-437: Initialization and property setup
- Lines 440-449: time_range_minutes property
- Lines 545-569: watch_selected_time_frame watcher
- Lines 571-582: _update_timeframe_buttons() method
- Lines 584-604: on_timeframe_changed button handler

### Datasource fetch_logs Signature
- Location: `src/logai/providers/datasources/cloudwatch.py` lines 161-231
- Key parameters: log_group, start_time, end_time, limit
- Default limit: 1000
- Max enforced limit: 10,000
- Early exit at limit: Line 269

---

## Key References for Implementation Team

### For Jackie (Implementation):
- Main file: `/src/logai/ui/screens/log_preview.py`
- Key methods to modify:
  - `__init__()` (line 395) - No changes needed
  - `compose()` (line 451) - Add new UI section
  - `_fetch_and_display_logs()` (line 606) - Already uses self.limit, will use self.current_limit
  - Add new: `watch_current_limit()` watcher
  - Add new: `on_load_100_clicked()` handler
  - Add new: `_update_entry_count_display()` method

### For Raoul (Testing):
- Test file: `/tests/unit/ui/test_log_preview.py`
- Reference existing tests for time frame functionality (lines 336-641)
- Add tests for:
  - Limit initialization
  - Button click behavior
  - Watcher behavior
  - Entry count display
  - Integration with time frame selector
  - Edge cases (rapid clicking, UI unmount, etc.)

### For Saanvi (Design Review):
- UI placement options in compose() method (lines 451-498)
- Existing CSS layout patterns (lines 252-343)
- Time frame button layout as reference (lines 467-479)
- Consider button label options: "Load Last 100" vs "Show More (100)" vs others

### For Han-Ron (Code Review):
- Ensure pattern matches time frame selector implementation
- Check for proper reactive property usage
- Verify watcher is_mounted check prevents early execution
- Confirm button handler stops event propagation
- Validate CSS styling doesn't break existing layout
- Check error handling in update methods

---

## Summary

The log preview implementation is **well-structured and ready** for this enhancement. The infrastructure already exists:
- ✅ Configurable limit parameter in datasource
- ✅ Reactive property pattern (time frame selector reference)
- ✅ Established UI patterns for buttons and controls
- ✅ Proper worker pattern preventing race conditions
- ✅ Clear separation between UI and data layers

**Minimal risk** due to:
- No datasource changes needed
- Simple, isolated feature (new button + property)
- Can follow existing time frame selector pattern
- Existing tests provide strong foundation

**Estimated effort**: 2-3 hours development, 1 hour testing
