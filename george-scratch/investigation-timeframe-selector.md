# Investigation Report: Adjustable Time Frame Selector for Log Preview

**Date**: February 18, 2026
**Investigator**: Hans (Code Librarian)
**Status**: Complete
**Target**: Add adjustable time frame selector (15 min, 1 hour, 8 hours, 24 hours) to log preview feature

---

## Executive Summary

The log preview feature currently fetches logs from a hard-coded 15-minute time window. This investigation identified all necessary components to implement an adjustable time frame selector. The implementation is straightforward and requires:

1. Adding a time frame selector dropdown widget to the UI
2. Adding a reactive property to track the selected time frame
3. Implementing a refresh mechanism when time frame changes
4. Minor updates to the state management and initialization

**Estimated Implementation Complexity**: Medium (2-3 hours development)

---

## 1. Current Time Frame Implementation

### 1.1 Hard-Coded Time Range Definition

**File**: `src/logai/ui/screens/log_preview.py`
**Location**: Lines 352-353

```python
class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    """Modal screen for previewing and selecting log entries from a log group."""

    # Fetch parameters
    DEFAULT_TIME_RANGE_MINUTES: int = 15
    DEFAULT_LIMIT: int = 10
```

**Finding**: The time range is defined as a class constant of 15 minutes.

### 1.2 Time Window Calculation

**File**: `src/logai/ui/screens/log_preview.py`
**Location**: Lines 428-430 in `_fetch_and_display_logs()` method

```python
# Calculate time range
end_time = int(time.time() * 1000)
start_time = end_time - (self.time_range_minutes * 60 * 1000)
```

**Finding**:
- Time is calculated in **milliseconds** (epoch ms)
- Formula: `start_time = end_time - (time_range_minutes * 60 * 1000)`
- `time_range_minutes` is multiplied by 60 to convert to seconds, then by 1000 to convert to milliseconds
- Uses current time as `end_time` (most recent logs)

### 1.3 CloudWatch API Parameters

**File**: `src/logai/ui/screens/log_preview.py`
**Location**: Lines 433-438

```python
# Fetch logs from CloudWatch
self._events = await self.datasource.fetch_logs(
    log_group=self.log_group_name,
    start_time=start_time,
    end_time=end_time,
    limit=self.limit,
)
```

**Finding**: The time range is passed to `fetch_logs()` as `start_time` and `end_time` in milliseconds.

### 1.4 CloudWatch DataSource Implementation

**File**: `src/logai/providers/datasources/cloudwatch.py`
**Location**: Lines 161-272

The `fetch_logs()` method signature:

```python
async def fetch_logs(
    self,
    log_group: str,
    start_time: int,
    end_time: int,
    filter_pattern: str | None = None,
    limit: int = 1000,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Fetch log events from CloudWatch.

    Args:
        log_group: CloudWatch log group name (e.g., '/aws/lambda/my-function')
        start_time: Start time in epoch milliseconds
        end_time: End time in epoch milliseconds
        filter_pattern: Optional CloudWatch filter pattern
        limit: Maximum number of log events to return (max: 10000)
        **kwargs: Additional parameters:
            - log_stream_prefix: Filter to specific log stream prefix
    """
```

The synchronous implementation (lines 233-272):

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
        "limit": min(limit, 10000),  # CloudWatch API max per request
    }

    # ... uses boto3 paginator with these params
    paginator = self.client.get_paginator("filter_log_events")
    for page in paginator.paginate(**params):
        # ... processes events
```

**Finding**:
- CloudWatch API (`filter_log_events`) accepts `startTime` and `endTime` in milliseconds
- No hardcoded time window in the data source - it's entirely parameter-driven
- The data source is already flexible and can support any time range

---

## 2. Data Fetching Logic

### 2.1 Fetch Method Flow

```
ClickableLogGroupItem (double-click detected)
    ↓
ChatScreen.on_log_group_preview_requested()
    ↓
ChatScreen.push_screen(LogPreviewScreen(...))
    ↓
LogPreviewScreen.on_mount()
    ↓
LogPreviewScreen._fetch_and_display_logs() [async worker]
    ↓
CloudWatchDataSource.fetch_logs()
    ↓
CloudWatchDataSource._fetch_logs_sync()
    ↓
boto3 client.get_paginator("filter_log_events").paginate()
```

### 2.2 Time Range Parameter Flow

**File**: `src/logai/ui/screens/chat.py` (lines 351-356)

```python
result = await self.app.push_screen(
    LogPreviewScreen(
        log_group_name=event.log_group_name,
        datasource=datasource,
    )
)
```

**Currently**: No time range is passed during initialization, so `DEFAULT_TIME_RANGE_MINUTES` (15) is used.

**Finding**: The caller (ChatScreen) doesn't pass a time range, relying on defaults.

### 2.3 Worker Thread and Async Pattern

**File**: `src/logai/ui/screens/log_preview.py` (lines 415-470)

```python
@work(exclusive=True)
async def _fetch_and_display_logs(self) -> None:
    """Worker to fetch and display logs asynchronously."""
    # ... implementation
```

**Finding**: Uses `@work(exclusive=True)` decorator:
- `exclusive=True` ensures only one fetch runs at a time
- If called multiple times, subsequent calls replace the previous one
- **Perfect for refresh on time frame change!**

---

## 3. UI Structure

### 3.1 Current Layout

The LogPreviewScreen layout (lines 383-409):

```
┌─────────────────────────────────────────┐
│  Log Preview: /aws/lambda/test      [#] │  ← preview-header (height: 3)
├─────────────────────────────────────────┤
│ [Select All] [Deselect All]      0 of 0 │  ← selection-controls (height: 3)
├─────────────────────────────────────────┤
│                                         │
│  ┌─ Log Entry 1                        │
│  │ [✓] 2026-02-18 10:15:42.123         │
│  │     Error processing payment        │
│  │     (click to expand)               │
│  └─────────────────────────────────────┤
│                                         │
│  ┌─ Log Entry 2                        │
│  │ [ ] 2026-02-18 10:14:32.456         │
│  │     Request timeout after 30s       │
│  └─────────────────────────────────────┤
│                                         │  ← log-entries
│  (VerticalScroll container)             │
│                                         │
├─────────────────────────────────────────┤
│  [Add Selected to Context]   [Close]   │  ← action-buttons (height: 3)
└─────────────────────────────────────────┘
```

### 3.2 CSS Structure

**File**: `src/logai/ui/screens/log_preview.py` (lines 252-349)

Key container IDs:
- `#preview-container` (main modal, 90% width, 85% height)
- `#preview-header` (docked top, height: 3)
- `#selection-controls` (docked top, height: 3, horizontal layout)
- `#log-entries` (VerticalScroll, height: 1fr)
- `#action-buttons` (docked bottom, height: 3)

### 3.3 Textual Widgets Available

The project uses **Textual >= 0.47.0**, which includes:
- `Select` - A select input widget with dropdown
- `OptionList` - List-based selection widget
- `RadioButton` - Single choice from multiple options
- `SegmentedButton` - Button group for choices (good for time frames!)

### 3.4 Recommended Placement Options

**Option A: Replace in selection-controls row (RECOMMENDED)**
```
[15 min ▼] [Select All] [Deselect All]      0 of 0 selected
```
Pros:
- Visible and accessible at top
- Doesn't waste vertical space
- Groups logically with other filtering controls

**Option B: Add separate row above selection-controls**
```
Time Frame: [15 min ▼]
[Select All] [Deselect All]      0 of 0 selected
```
Pros:
- Clearer labeling
- Doesn't disrupt existing control layout
- Easier to read

**Option C: Use SegmentedButton in new row (MODERN)**
```
[15 min] [1 hr] [8 hr] [24 hr]
[Select All] [Deselect All]      0 of 0 selected
```
Pros:
- All options visible at once
- No dropdown needed
- More modern UI pattern
- Excellent for small number of choices

**RECOMMENDATION**: Option C (SegmentedButton) - Users can see all time frame options at once without clicking a dropdown. Most intuitive for 4 preset options.

---

## 4. State Management

### 4.1 Current Initialization

**File**: `src/logai/ui/screens/log_preview.py` (lines 355-382)

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
        limit: Maximum entries to fetch (default: 10)
        **kwargs: Additional arguments for Screen
    """
    super().__init__(**kwargs)
    self.log_group_name = log_group_name
    self.datasource = datasource
    self.time_range_minutes = time_range_minutes or self.DEFAULT_TIME_RANGE_MINUTES
    self.limit = limit or self.DEFAULT_LIMIT

    # Track fetched events and selection state
    self._events: list[dict[str, Any]] = []
    self._selected_ids: set[str] = set()
```

**Finding**:
- `time_range_minutes` is already an accepted parameter ✓
- It defaults to `DEFAULT_TIME_RANGE_MINUTES` (15) ✓
- Currently stored as instance variable (not reactive) ⚠️

### 4.2 How Reactive Properties Work in Textual

The project already uses reactive properties:

```python
# From LogEntryItem (line 100)
expanded = reactive(False)

def watch_expanded(self, expanded: bool) -> None:
    """Update CSS class when expanded state changes."""
    if expanded:
        self.add_class("expanded")
    else:
        self.remove_class("expanded")
```

**Pattern**:
1. Define reactive property: `selected_time_frame = reactive("15min")`
2. Define watcher: `watch_selected_time_frame(self, value: str) -> None`
3. Watcher is automatically called when property changes

### 4.3 State Changes Needed

**Current state**:
```python
self.time_range_minutes = time_range_minutes or self.DEFAULT_TIME_RANGE_MINUTES
```

**Needed state**:
```python
# Add reactive property for UI binding
self.selected_time_frame = reactive("15")  # "15", "60", "480", "1440"

# Keep the computed minutes property
self._time_range_map = {
    "15": 15,      # 15 minutes
    "60": 60,      # 1 hour
    "480": 480,    # 8 hours (60 * 8)
    "1440": 1440,  # 24 hours (60 * 24)
}

@property
def time_range_minutes(self) -> int:
    """Get current time range in minutes from selected frame."""
    return self._time_range_map.get(self.selected_time_frame, 15)
```

**Finding**: Need to add reactive property and implement mapping between UI values and minutes.

---

## 5. Refresh/Update Logic

### 5.1 Existing Refresh Pattern

The `_fetch_and_display_logs()` method is already designed for refresh:

```python
@work(exclusive=True)
async def _fetch_and_display_logs(self) -> None:
    """Worker to fetch and display logs asynchronously."""
    container = self.query_one("#log-entries", VerticalScroll)

    # Show loading state
    loading = Static(
        "Loading recent log entries...",
        classes="loading-state",
    )
    container.mount(loading)

    try:
        # ... fetch and display logic
```

**Finding**:
- Uses `exclusive=True` on the worker decorator
- Can be called multiple times; only one executes at a time
- If called while one is running, the new call replaces it
- **Already has built-in refresh capability!**

### 5.2 How to Trigger Refresh on Time Frame Change

```python
# Define watcher method
def watch_selected_time_frame(self, new_value: str) -> None:
    """Refresh logs when time frame changes."""
    self._fetch_and_display_logs()  # Automatically replaces old fetch
```

When `self.selected_time_frame` is updated by button press, watcher automatically calls refresh.

### 5.3 Empty State Message Update

**Current** (line 449-453):
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

**Finding**: Message already uses `self.time_range_minutes`, so it will automatically update when time frame changes. ✓

---

## 6. Integration Points

### 6.1 How Modal is Currently Opened

**File**: `src/logai/ui/screens/chat.py` (lines 340-360)

```python
# When double-click detected on log group
@on(ClickableLogGroupItem.LogGroupPreviewRequested)
def on_log_group_preview_requested(self, event: ClickableLogGroupItem.LogGroupPreviewRequested) -> None:
    """Handle log group preview request."""
    try:
        # Find the CloudWatch tool in the registry
        tool = self.app.tool_registry.get_tool("get_recent_logs")
        if not tool:
            logger.error("Could not find 'get_recent_logs' tool in registry")
            return

        # The tool should have a datasource attribute
        if not hasattr(tool, "datasource"):
            logger.error("Could not access datasource from tool registry")
            return

        datasource = tool.datasource

        # Import LogPreviewScreen here to avoid circular imports
        from logai.ui.screens.log_preview import LogPreviewScreen

        # Show preview modal and await result
        result = await self.app.push_screen(
            LogPreviewScreen(
                log_group_name=event.log_group_name,
                datasource=datasource,
            )
        )

        # If user selected entries, inject them into context
        if result:
            await self._inject_log_entries_to_context(result)

    except Exception as e:
        logger.error(f"Error handling log preview: {e}", exc_info=True)
```

**Finding**:
- No time range passed during initialization
- **Can optionally pass `time_range_minutes` parameter here**
- But better to let user select via UI in the modal

### 6.2 Alternative: Allow Initial Time Frame Selection

**Option A** (Current approach - SELECT IN MODAL):
- User doubles-clicks log group → modal opens with default 15 min
- User can change time frame in modal UI
- Logs refresh automatically

**Option B** (Allow override at open time):
- Modify ChatScreen to pass default: `LogPreviewScreen(..., time_range_minutes=60)`
- Still allows UI override in modal

**RECOMMENDATION**: Keep Option A. The modal UI should be the single source of truth for time frame selection.

---

## 7. Tests to Update/Add

### 7.1 Current Tests

**File**: `tests/unit/ui/test_log_preview.py`

Current test coverage:
- LogEntryItem preview truncation (✓)
- JSON formatting (✓)
- Error message formatting (✓)
- Screen initialization with defaults (✓)
- Screen initialization with custom params (✓)

### 7.2 New Tests Needed

```python
def test_initialization_with_custom_time_range(self):
    """Screen should accept custom time range."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
        time_range_minutes=60,
    )
    assert screen.time_range_minutes == 60

def test_time_range_mapping(self):
    """Time range values should map correctly."""
    datasource = AsyncMock()
    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    # Test mapping
    screen.selected_time_frame = "15"
    assert screen.time_range_minutes == 15

    screen.selected_time_frame = "60"
    assert screen.time_range_minutes == 60

    screen.selected_time_frame = "480"
    assert screen.time_range_minutes == 480

    screen.selected_time_frame = "1440"
    assert screen.time_range_minutes == 1440

@pytest.mark.asyncio
async def test_refresh_on_time_frame_change(self):
    """Changing time frame should trigger logs refresh."""
    datasource = AsyncMock()
    datasource.fetch_logs.return_value = [
        {
            "timestamp": 1708263045123,
            "message": "Test event",
            "log_stream": "stream",
            "event_id": "event123",
        }
    ]

    screen = LogPreviewScreen(
        log_group_name="/aws/lambda/test",
        datasource=datasource,
    )

    # Change time frame
    screen.selected_time_frame = "60"

    # Watcher should have been called
    # (Would need to mock the worker to verify)
```

---

## 8. Implementation Changes Required

### 8.1 LogPreviewScreen Changes

**File**: `src/logai/ui/screens/log_preview.py`

#### 8.1.1 Add Imports

```python
from textual.widgets import Button, Checkbox, Static, SegmentedButton
```

#### 8.1.2 Add Time Frame Mapping

```python
class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    """..."""

    DEFAULT_TIME_RANGE_MINUTES: int = 15
    DEFAULT_LIMIT: int = 10

    # Time frame options mapping: display_label -> minutes
    TIME_FRAME_OPTIONS = {
        "15 min": 15,
        "1 hour": 60,
        "8 hours": 480,
        "24 hours": 1440,
    }
```

#### 8.1.3 Add Reactive Property

```python
class LogPreviewScreen(ModalScreen[dict[str, Any] | None]):
    """..."""

    # Reactive property for time frame selection
    selected_time_frame: reactive[str] = reactive("15 min")
```

#### 8.1.4 Update Compose Method

Add SegmentedButton to the UI. New structure:

```python
def compose(self) -> ComposeResult:
    """Compose the preview screen layout."""
    with Container(id="preview-container"):
        # Header
        yield Static(
            f"Log Preview: {self.log_group_name}",
            id="preview-header",
        )

        # TIME FRAME SELECTOR - NEW
        with Horizontal(id="timeframe-controls"):
            yield Static("Time Frame:", classes="timeframe-label")
            yield SegmentedButton(
                *self.TIME_FRAME_OPTIONS.keys(),
                id="timeframe-selector",
            )

        # Selection controls
        with Horizontal(id="selection-controls"):
            yield Button("Select All", id="select-all-btn", variant="default")
            yield Button("Deselect All", id="deselect-all-btn", variant="default")
            yield Static("0 of 0 selected", id="selection-counter")

        # Rest of compose...
```

#### 8.1.5 Add CSS for New Controls

```css
#timeframe-controls {
    dock: top;
    height: 3;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
}

#timeframe-controls .timeframe-label {
    width: auto;
    padding: 1 1;
    color: $text-muted;
}

#timeframe-selector {
    width: auto;
    margin: 0 1;
}

#timeframe-selector Button {
    min-width: 10;
}
```

#### 8.1.6 Add Watcher Method

```python
def watch_selected_time_frame(self, new_frame: str) -> None:
    """Refresh logs when time frame selection changes."""
    # Clear current events and selection
    self._events.clear()
    self._selected_ids.clear()

    # Trigger refresh
    self._fetch_and_display_logs()
```

#### 8.1.7 Add Event Handler

```python
@on(SegmentedButton.Changed, "#timeframe-selector")
def on_timeframe_changed(self, event: SegmentedButton.Changed) -> None:
    """Handle time frame selection change."""
    self.selected_time_frame = event.control.pressed_button.label if event.control.pressed_button else "15 min"
```

#### 8.1.8 Update Time Calculation

Change the `_fetch_and_display_logs()` method to use current `selected_time_frame`:

```python
# OLD
start_time = end_time - (self.time_range_minutes * 60 * 1000)

# NEW - using time frame map
time_minutes = self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)
start_time = end_time - (time_minutes * 60 * 1000)
```

Or simpler:

```python
start_time = end_time - (self.time_range_minutes * 60 * 1000)

# Where time_range_minutes property is:
@property
def time_range_minutes(self) -> int:
    """Get current time range in minutes."""
    return self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)
```

### 8.2 CSS Adjustments

The new timeframe-controls section adds 3 units of height, so adjust:

```css
#preview-container {
    width: 90%;
    height: 85%;  # May need to be reduced if modal size is constrained
    max-width: 120;
    background: $panel;
    border: thick $primary;
    padding: 1;
}
```

Or the container will expand naturally if there's room.

---

## 9. Potential Challenges & Considerations

### 9.1 Performance Impact

**Challenge**: Fetching 24 hours of logs might be slow or timeout

**Mitigation**:
- CloudWatch API has max 10,000 events per request
- App already has timeout settings (`cloudwatch_read_timeout`, `cloudwatch_connect_timeout`)
- Consider adding a note in UI for large time frames
- Use the existing rate limit retry logic

**Risk Level**: LOW - Already handled by datasource

### 9.2 UI Space

**Challenge**: Adding timeframe selector increases modal height

**Consideration**: Current height is 85% of terminal. With SegmentedButton:
- Header: 3 lines
- Timeframe: 3 lines
- Selection controls: 3 lines
- Log entries: remaining space
- Action buttons: 3 lines

**Solution**: This is acceptable. If needed, can reduce font size or make timeframe selector more compact.

**Risk Level**: LOW - Typical terminal is tall enough

### 9.3 Initial State

**Challenge**: Which time frame should be selected by default?

**Decision**: 15 min (current default)
- Matches existing behavior
- Fast to load
- Users can easily change it

**Implementation**:
```python
selected_time_frame: reactive[str] = reactive("15 min")
```

### 9.4  Segmented Button Behavior

**Challenge**: Need to handle SegmentedButton pressed state correctly

**Finding**: Textual's SegmentedButton has a `pressed_button` property

**Implementation**:
```python
@on(SegmentedButton.Changed, "#timeframe-selector")
def on_timeframe_changed(self, event: SegmentedButton.Changed) -> None:
    button = event.control.pressed_button
    if button:
        self.selected_time_frame = button.label
```

**Risk Level**: LOW - Standard Textual pattern

### 9.5 Work Decorator Interference

**Challenge**: Multiple overlapping fetch requests

**Current Behavior**: `@work(exclusive=True)` ensures only one worker runs
- If `_fetch_and_display_logs()` is called while one is running, the new task replaces it
- This is exactly what we want for refresh!

**Risk Level**: LOW - Already handled

---

## 10. Recommended Implementation Strategy

### Phase 1: Core Implementation (30 min)

1. Add time frame mapping constant
2. Add reactive property `selected_time_frame`
3. Add SegmentedButton to compose()
4. Add watcher method
5. Update time calculation to use reactive property
6. Add CSS for new controls

### Phase 2: Event Handling (15 min)

1. Add SegmentedButton.Changed event handler
2. Test manual time frame selection
3. Verify logs refresh correctly

### Phase 3: Testing (30 min)

1. Update existing tests to work with new default
2. Add time frame mapping tests
3. Add refresh trigger tests
4. Integration test with actual modal

### Phase 4: UI Polish (15 min)

1. Add label to timeframe controls
2. Verify CSS alignment
3. Test with various terminal sizes
4. Add tooltips if desired

**Total Estimated Time**: 1.5-2 hours for implementation + testing

---

## 11. Code Snippets for Implementation

### 11.1 Complete Additions to LogPreviewScreen.__init__()

```python
def __init__(
    self,
    log_group_name: str,
    datasource: "CloudWatchDataSource",
    time_range_minutes: int | None = None,
    limit: int | None = None,
    **kwargs: Any,
) -> None:
    """Initialize log preview screen."""
    super().__init__(**kwargs)
    self.log_group_name = log_group_name
    self.datasource = datasource
    self.limit = limit or self.DEFAULT_LIMIT

    # Track fetched events and selection state
    self._events: list[dict[str, Any]] = []
    self._selected_ids: set[str] = set()

    # Initialize selected time frame
    # If time_range_minutes provided, find matching frame
    if time_range_minutes:
        for frame_label, frame_minutes in self.TIME_FRAME_OPTIONS.items():
            if frame_minutes == time_range_minutes:
                self.selected_time_frame = frame_label
                break
```

### 11.2 Complete Additions to CSS

```css
#timeframe-controls {
    dock: top;
    height: 3;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
    align: middle;
}

#timeframe-controls .timeframe-label {
    width: auto;
    padding: 0 1;
    color: $text-muted;
    text-style: bold;
}

#timeframe-selector {
    width: auto;
    margin: 0 0 0 1;
}

#timeframe-selector Button {
    min-width: 10;
}
```

### 11.3 Time Frame Property

```python
@property
def time_range_minutes(self) -> int:
    """Get current time range in minutes based on selected frame."""
    return self.TIME_FRAME_OPTIONS.get(self.selected_time_frame, 15)
```

### 11.4 Watcher and Event Handler

```python
def watch_selected_time_frame(self, new_frame: str) -> None:
    """Refresh logs when time frame selection changes."""
    logger.debug(f"Time frame changed to: {new_frame}")
    # Clear current state
    self._events.clear()
    self._selected_ids.clear()
    # Refresh logs
    self._fetch_and_display_logs()

@on(SegmentedButton.Changed, "#timeframe-selector")
def on_timeframe_changed(self, event: SegmentedButton.Changed) -> None:
    """Handle time frame selection change."""
    pressed = event.control.pressed_button
    if pressed:
        self.selected_time_frame = pressed.label
```

---

## 12. Files Summary

### Files to Modify

1. **src/logai/ui/screens/log_preview.py** (MAIN)
   - Add TIME_FRAME_OPTIONS constant
   - Add selected_time_frame reactive property
   - Update compose() to include SegmentedButton
   - Add watch_selected_time_frame() watcher
   - Add on_timeframe_changed() event handler
   - Update time calculation in _fetch_and_display_logs()
   - Add CSS for new controls
   - Lines affected: ~80-100 new/modified lines

2. **tests/unit/ui/test_log_preview.py** (TESTS)
   - Add tests for time frame mapping
   - Add tests for refresh trigger
   - Update existing initialization tests
   - Lines affected: ~40-50 new lines

### Files to Review (No Changes)

- src/logai/providers/datasources/cloudwatch.py (Already flexible)
- src/logai/ui/widgets/log_groups_sidebar.py (No changes needed)
- src/logai/ui/screens/chat.py (Can optionally pass time_range_minutes, but not required)

---

## 13. Backward Compatibility

### 13.1 Constructor Compatibility

**Current**: `LogPreviewScreen(log_group_name, datasource)`
**New**: Same signature, just adds new reactive state internally

✅ **Fully backward compatible** - existing calls continue to work

### 13.2 Default Behavior

**Current**: Always 15 minutes
**New**: Always starts with 15 minutes (same as before)

✅ **No behavior change for existing code**

### 13.3 Optional Enhancements

Users can optionally pass `time_range_minutes` parameter:

```python
# Old code still works
LogPreviewScreen(log_group_name, datasource)

# New capability
LogPreviewScreen(log_group_name, datasource, time_range_minutes=60)
```

✅ **Fully additive - no breaking changes**

---

## 14. User Experience Flow

### Current Flow
```
1. User double-clicks log group
2. Modal opens with 15 minutes of logs
3. User selects entries
4. User clicks "Add to Context"
```

### New Flow
```
1. User double-clicks log group
2. Modal opens with 15 minutes of logs
3. User can click [15 min] [1 hour] [8 hours] [24 hours] buttons to change
4. Logs automatically refresh (loading indicator shown)
5. User selects entries
6. User clicks "Add to Context"
```

**Benefits**:
- Intuitive time frame selection
- Immediate visual feedback
- No modal reload needed
- Respects existing selection behavior

---

## 15. Summary & Recommendations

### Key Findings

| Finding | Impact | Priority |
|---------|--------|----------|
| Time format already in milliseconds | No changes needed to datasource | N/A |
| Work decorator with exclusive=True | Perfect for refresh mechanism | HIGH |
| SegmentedButton available in Textual | Best UI choice for 4 options | HIGH |
| Reactive properties already used | Consistent with codebase patterns | HIGH |
| No breaking changes possible | Safe to implement | HIGH |

### Recommended Approach

✅ **Use SegmentedButton with 4 presets**: 15 min, 1 hour, 8 hours, 24 hours
✅ **Make it top control** below header, above selection controls
✅ **Implement auto-refresh** when user selects different time frame
✅ **Keep full backward compatibility** with existing code
✅ **Add comprehensive tests** for new time frame mapping and refresh logic

### Estimated Effort

- **Implementation**: 1.5 - 2 hours
- **Testing**: 1 hour
- **Total**: 2 - 3 hours
- **Risk**: LOW (well-contained, no breaking changes)

### Next Steps

1. ✅ Investigation complete
2. Design review with team (recommend 4 preset buttons)
3. Implementation (follow code snippets provided)
4. Add unit tests
5. Manual testing with different log group sizes
6. Merge and deploy

---

## Appendix: Data Structure Reference

### LogPreviewScreen Constructor Parameters

```python
LogPreviewScreen(
    log_group_name: str,              # Required: "/aws/lambda/my-function"
    datasource: CloudWatchDataSource, # Required: from tool registry
    time_range_minutes: int | None,   # Optional: 15 (default), 60, 480, 1440
    limit: int | None,                # Optional: 10 (default), max 10000
    **kwargs: Any,                    # Passed to ModalScreen
)
```

### CloudWatch fetch_logs Parameters

```python
await datasource.fetch_logs(
    log_group="string",           # e.g., "/aws/lambda/test"
    start_time=1708263045123,     # epoch milliseconds
    end_time=1708263945123,       # epoch milliseconds
    filter_pattern=None,          # optional CloudWatch filter
    limit=10,                     # max 10000
)
```

Returns:
```python
[
    {
        "timestamp": 1708263045123,  # epoch milliseconds
        "message": "string",          # log message
        "log_stream": "string",       # stream name
        "event_id": "string",         # unique event ID
    },
    # ... more events
]
```

---

**Report Completed**: February 18, 2026
**Confidence Level**: HIGH
**Ready for Development**: YES ✅
