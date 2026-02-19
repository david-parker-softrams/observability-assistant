# Quick Reference: Load Last 100 Entries Feature

## One-Liner
Add a button to toggle between showing 10 or 100 log entries in the preview modal. Datasource already supports it. Just add UI + reactive property.

---

## What Changed & What Didn't

### Changed (What We Need to Do)
```python
# 1 NEW CONSTANT
LOAD_100_LIMIT: int = 100

# 1 NEW REACTIVE PROPERTY
current_limit: reactive[int] = reactive(DEFAULT_LIMIT)

# 1 NEW UI SECTION
with Horizontal(id="entry-limit-controls"):
    yield Button("Load Last 100", id="load-100-btn")
    yield Static("", id="entry-count-display")

# 1 NEW BUTTON HANDLER
@on(Button.Pressed, "#load-100-btn")
def on_load_100_clicked(self, event):
    new_limit = self.LOAD_100_LIMIT if self.current_limit == self.DEFAULT_LIMIT else self.DEFAULT_LIMIT
    self.current_limit = new_limit

# 1 NEW WATCHER
def watch_current_limit(self, new_limit: int):
    if not self.is_mounted: return
    self._events.clear()
    self._selected_ids.clear()
    self._fetch_and_display_logs()

# 1 CHANGE: USE new limit instead of old
limit=self.current_limit,  # was: self.limit

# 1 NEW DISPLAY UPDATE METHOD
def _update_entry_count_display(self):
    display = self.query_one("#entry-count-display", Static)
    total = len(self._events)
    if total > 0:
        display.update(f"Showing {total} entries")
```

### NOT Changed (Already Works!)
- ✅ `CloudWatchDataSource.fetch_logs()` - Already handles limit=100 perfectly
- ✅ No boto3 changes needed
- ✅ No configuration changes
- ✅ No database changes
- ✅ No API changes

---

## File Locations

```
MODIFY:
  src/logai/ui/screens/log_preview.py
    - Add constants (after line 382)
    - Add reactive property (after line 393)
    - Add UI section in compose() (between lines 479-481)
    - Add CSS styling
    - Add button handler
    - Add watcher
    - Add display update method
    - Update fetch call (line 631)

ADD TESTS:
  tests/unit/ui/test_log_preview.py
    - 9-10 new test cases
    - Follow pattern from lines 336-641
```

---

## Files That DON'T Need Changes

- `src/logai/providers/datasources/cloudwatch.py` ✓
- `src/logai/providers/datasources/base.py` ✓
- Any configuration files ✓
- Any other screens or widgets ✓

---

## Testing Checklist (For Raoul)

```python
def test_default_limit_is_10():
    """Verify DEFAULT_LIMIT constant"""

def test_load_100_button_visible():
    """Button exists in UI"""

def test_load_100_button_click():
    """Click updates reactive property"""

def test_current_limit_watcher():
    """Watcher clears state and fetches"""

def test_entry_count_display():
    """Display shows 'Showing X entries'"""

def test_toggle_10_100():
    """Clicking toggles between limits"""

def test_fetch_with_limit_100():
    """Datasource called with limit=100"""

def test_with_time_frame_selector():
    """Works with time frame changes"""

def test_rapid_clicks():
    """No race conditions on rapid clicks"""

def test_limit_persists_on_timeframe():
    """Limit stays when changing time frame"""
```

---

## Code Pattern (Copy from Time Frame Selector)

Time frame selector (already works, use as template):
- **Lines 385-390**: `TIME_FRAME_OPTIONS` dictionary
- **Line 393**: `selected_time_frame: reactive[str]`
- **Lines 545-569**: `watch_selected_time_frame()` method
- **Lines 584-604**: `on_timeframe_changed()` handler

For entry limit, create same pattern with:
- Single constant: `LOAD_100_LIMIT = 100`
- Reactive property: `current_limit: reactive[int]`
- Watcher method: `watch_current_limit()`
- Button handler: `on_load_100_clicked()`

---

## UI Placement Options

**RECOMMENDED (Option A)**: New row between timeframe-controls and selection-controls
```
┌─────────────────────┐
│ Header              │
├─────────────────────┤
│ [15 min] [1h] ...   │  ← Time frame
├─────────────────────┤
│ [Load 100] Showing  │  ← NEW
├─────────────────────┤
│ [Select] [Deselect] │  ← Selection
├─────────────────────┤
│ Log entries here    │
├─────────────────────┤
│ [Add] [Close]       │  ← Actions
└─────────────────────┘
```

---

## No-Brainer Facts

1. **Already Safe**: Uses `@work(exclusive=True)` - prevents race conditions
2. **Already Tested**: CloudWatch datasource proven to handle 100 entries
3. **Already Performant**: 100 << 10,000 (AWS limit) - no issues
4. **Already Isolated**: Only touches `log_preview.py` - no dependencies
5. **Already Compatible**: Doesn't break existing 10-entry behavior
6. **Already Scalable**: Pattern can extend to other limits later

---

## Status: Ready to Code

- ✅ Requirements understood
- ✅ Codebase reviewed
- ✅ Patterns identified
- ✅ Implementation plan documented
- ✅ Tests planned
- ✅ No blockers identified
- ✅ Jackie can start immediately

---

**From**: Hans (Code Librarian)
**Date**: February 19, 2026
**Confidence**: Very High
**Risk**: Very Low
**Effort**: 2-3 hours

See full investigation: `/george-scratch/investigation-log-preview-100-entries.md`
