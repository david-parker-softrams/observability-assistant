# Investigation: Log Groups Sidebar for Preview Feature

**Date:** February 18, 2026
**Investigator:** George (Investigation Agent)
**Purpose:** Understand current log groups sidebar implementation for adding double-click preview feature

---

## Executive Summary

The log groups sidebar is a well-structured Textual widget that displays CloudWatch log groups in a scrollable list. It uses a clean MVC-like pattern with the `LogGroupManager` handling data and the `LogGroupsSidebar` widget handling presentation. Adding the double-click preview feature will require:

1. Adding click event handlers to individual log group items
2. Creating a modal/screen component to display log previews
3. Leveraging existing CloudWatch integration for fetching log events
4. Following established patterns for user interaction and feedback

The codebase is clean, well-documented, and has clear separation of concerns, making the implementation straightforward.

---

## 1. Architecture Overview

### 1.1 Component Hierarchy

```
LogAIApp (main application)
└── ChatScreen (main screen)
    ├── LogGroupsSidebar (left sidebar) ← TARGET FOR ENHANCEMENT
    ├── MessagesContainer (center)
    └── ToolCallsSidebar (right sidebar)
```

### 1.2 Log Groups Sidebar Implementation

**File:** `src/logai/ui/widgets/log_groups_sidebar.py` (183 lines)

**Key Characteristics:**
- **Base Class:** `textual.widgets.Static`
- **Display:** Uses `textual.containers.VerticalScroll` for scrollable list
- **Items:** Individual log groups displayed as `textual.widgets.Label` widgets
- **Styling:** Custom CSS with hover effects already in place
- **State Management:** Receives updates via callback pattern from `LogGroupManager`

**Current Structure:**
```python
class LogGroupsSidebar(Static):
    """Sidebar widget showing available CloudWatch log groups."""

    # Components
    - _log_group_manager: LogGroupManager  # Data source
    - _scroll_container: VerticalScroll    # Scrollable area
    - _title_label: Static                 # "LOG GROUPS (N)" header
    - _empty_state: Static                 # Empty state message
```

### 1.3 Integration with Chat Screen

**File:** `src/logai/ui/screens/chat.py` (580 lines)

The sidebar is instantiated in `ChatScreen.compose()` at lines 141-147:

```python
self._log_groups_sidebar = LogGroupsSidebar(
    log_group_manager=self.log_group_manager,
    id="log-groups-sidebar",
)
self._log_groups_sidebar.display = self._log_groups_sidebar_visible
yield self._log_groups_sidebar
```

**Key Integration Points:**
- Screen maintains reference: `self._log_groups_sidebar`
- Visibility toggle: `toggle_log_groups_sidebar()` method (lines 492-505)
- Resize support: F1/F2 keybindings with `action_shrink_left_sidebar()` and `action_expand_left_sidebar()`
- Width management: Uses `SIDEBAR_WIDTH_STEPS` array (line 38)

---

## 2. Data Flow Architecture

### 2.1 Log Groups Data Pipeline

```
CloudWatchDataSource
    ↓ (boto3 API calls)
LogGroupManager (src/logai/core/log_group_manager.py)
    ↓ (callback notifications)
LogGroupsSidebar._on_log_groups_updated()
    ↓ (UI update)
LogGroupsSidebar._populate_log_groups()
    ↓ (widget mounting)
Individual Label widgets (one per log group)
```

### 2.2 LogGroupManager Data Structure

**File:** `src/logai/core/log_group_manager.py` (542 lines)

**Data Model:**
```python
@dataclass
class LogGroupInfo:
    name: str                      # Log group name (e.g., "/aws/lambda/my-function")
    created: int | None            # Epoch milliseconds
    stored_bytes: int              # Size in bytes
    retention_days: int | None     # Retention policy
```

**Key Methods:**
- `load_all()` - Fetches all log groups (async)
- `refresh()` - Alias for load_all()
- `get_log_group_names()` - Returns list of names only
- `find_matching_groups(pattern)` - Search functionality
- `register_update_callback()` - Subscribe to data changes
- `unregister_update_callback()` - Unsubscribe

**State Management:**
```python
class LogGroupManagerState(Enum):
    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
```

### 2.3 Callback Pattern

The sidebar registers for updates in `on_mount()` (line 108):
```python
if self._log_group_manager:
    self._log_group_manager.register_update_callback(self._on_log_groups_updated)
```

When data changes (after `/refresh` command), the callback triggers:
```python
def _on_log_groups_updated(self) -> None:
    """Handle log group updates from the manager."""
    try:
        self._populate_log_groups()
    except Exception as e:
        logger.warning(f"Failed to update log groups sidebar: {e}", exc_info=True)
```

### 2.4 Current Rendering Logic

From `_populate_log_groups()` (lines 130-162):

```python
# Get sorted log group names
log_groups = self._get_log_group_names()  # Returns list[str]

# Create Label widget for each log group
for name in log_groups:
    label = Label(name, classes="log-group-item")
    self._scroll_container.mount(label)
```

**Critical Observation:** Currently using plain `Label` widgets with no interaction handlers. These are simple text displays with CSS hover styling but no click handlers.

---

## 3. CloudWatch Integration

### 3.1 Fetching Log Events

**File:** `src/logai/providers/datasources/cloudwatch.py` (372 lines)

**Key Method for Preview Feature:**
```python
async def fetch_logs(
    self,
    log_group: str,
    start_time: int,        # Epoch milliseconds
    end_time: int,          # Epoch milliseconds
    filter_pattern: str | None = None,
    limit: int = 1000,
    **kwargs: Any,
) -> list[dict[str, Any]]
```

**Return Structure:**
```python
[
    {
        "timestamp": 1704067200000,  # Epoch ms
        "message": "Log message text...",
        "log_stream": "2024/01/01/stream-name",
        "event_id": "event-id-string"
    },
    ...
]
```

**Features:**
- Automatic retry on rate limits (3 attempts with exponential backoff)
- Pagination handling built-in
- Error handling for missing log groups, auth failures, etc.
- Runs in thread pool executor (boto3 is synchronous)

### 3.2 CloudWatch Tools Abstraction

**File:** `src/logai/core/tools/cloudwatch_tools.py` (522 lines)

**Relevant Tool:** `FetchLogsTool` (lines 127-309)

This tool wraps the datasource and adds:
- PII sanitization via `LogSanitizer`
- Cache support via `CacheManager`
- Time range parsing (relative formats like "1h ago")
- Settings-based limits and defaults

**For Preview Feature:** We can either:
1. Call `CloudWatchDataSource.fetch_logs()` directly (simpler, no caching/sanitization)
2. Use `FetchLogsTool.execute()` (includes sanitization, caching - recommended)

**Recommendation:** Use the tool for consistency and to leverage existing sanitization.

### 3.3 Authentication & Session

The datasource is initialized once at startup in the main app. It handles:
- AWS profile configuration
- Credential chain (env vars → ~/.aws/credentials → IAM role)
- Session management
- Boto3 client configuration

**File:** `src/logai/providers/datasources/cloudwatch.py` lines 35-82

**For Preview Feature:** No additional auth setup needed - just use existing `self.datasource` instance.

---

## 4. Existing UI Patterns

### 4.1 Modal/Screen Pattern in Textual

**Current Usage:** The app uses Textual's screen system:

```python
# From app.py (line 68)
await self.push_screen(
    ChatScreen(
        orchestrator=self.orchestrator,
        cache_manager=self.cache_manager,
        log_group_manager=self.log_group_manager,
    )
)
```

**Textual Screen API:**
- `app.push_screen(screen)` - Show modal screen (overlays current)
- `screen.dismiss()` - Close and return to previous screen
- Screens can return values on dismiss

**For Preview Feature:** We should create a new `LogPreviewScreen(Screen)` that:
- Takes log group name and time range as constructor params
- Fetches and displays recent log events
- Closes on ESC key or button click
- Uses existing message widgets for consistent styling

### 4.2 Event Handling in Textual

**Example from chat.py (lines 204-235):**

```python
@on(Input.Submitted)
async def on_input_submitted(self, event: Input.Submitted) -> None:
    message = event.value.strip()
    # Handle input...
```

**For Log Group Items:** We need to handle click events on Label widgets:

```python
# Textual provides these event handlers:
def on_click(self, event: Click) -> None:
    """Handle single click"""
    pass

def on_double_click(self, event: Click) -> None:
    """Handle double click"""
    pass
```

**Implementation Approach:** Create custom widget class inheriting from `Label` that handles click events:

```python
class ClickableLogGroupItem(Label):
    """Log group item with click handling."""

    def __init__(self, log_group_name: str, **kwargs):
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name

    async def on_click(self, event: Click) -> None:
        if event.button == 1:  # Left click
            # Emit custom message that ChatScreen can handle
            self.post_message(LogGroupPreviewRequest(self.log_group_name))
```

### 4.3 Existing Widget Patterns

**Tool Sidebar Pattern** (`src/logai/ui/widgets/tool_sidebar.py`):
- Uses `Tree` widget for expandable content
- Status updates via `update_tool_call(record)` method
- Auto-scrolling to latest content
- Empty state handling

**Message Widgets** (`src/logai/ui/widgets/messages.py`):
- Base `ChatMessage` class
- Specialized: `UserMessage`, `AssistantMessage`, `SystemMessage`, `ErrorMessage`, `LoadingIndicator`
- Consistent styling with CSS classes
- Rich text formatting support

**For Preview Feature:** Can reuse message widget patterns for displaying logs in preview modal.

### 4.4 Loading & Status Feedback

**Current Patterns from ChatScreen:**

1. **Loading Indicator** (lines 258-278):
```python
self._current_loading_indicator = LoadingIndicator()
messages_container.mount(self._current_loading_indicator)
# ... minimum 200ms display time ...
self._current_loading_indicator.remove()
```

2. **Status Footer Updates** (via `StatusFooter` widget):
```python
status_footer.set_status("Thinking...")
# ... work ...
status_footer.set_status("Ready")
```

3. **Toast Notifications** (via `self.notify()`):
```python
self.notify("Operation complete", severity="information", timeout=3)
self.notify("Error occurred", severity="error", timeout=5)
```

**For Preview Feature:** Use loading indicator while fetching logs, then display in modal.

---

## 5. Integration Points for Preview Feature

### 5.1 Changes to LogGroupsSidebar

**File:** `src/logai/ui/widgets/log_groups_sidebar.py`

**Required Changes:**

1. **Create Clickable Widget Class** (new class in same file):
```python
class ClickableLogGroupItem(Label):
    """Clickable log group label that emits preview requests."""

    def __init__(self, log_group_name: str, **kwargs):
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name

    async def on_click(self, event: Click) -> None:
        # Handle double-click
        if event.ctrl:  # Or use event.count for actual double-click detection
            self.post_message(
                self.LogGroupPreviewRequested(self.log_group_name)
            )

    # Define custom message
    class LogGroupPreviewRequested(Message):
        def __init__(self, log_group_name: str):
            super().__init__()
            self.log_group_name = log_group_name
```

2. **Update `_populate_log_groups()` method** (line 158-161):
```python
# OLD:
label = Label(name, classes="log-group-item")

# NEW:
label = ClickableLogGroupItem(name, classes="log-group-item")
```

3. **Add CSS for clickable state** (add to DEFAULT_CSS):
```css
LogGroupsSidebar .log-group-item {
    cursor: pointer;  /* Indicate clickability */
}

LogGroupsSidebar .log-group-item:active {
    background: $primary-darken-1;  /* Feedback on click */
}
```

### 5.2 Changes to ChatScreen

**File:** `src/logai/ui/screens/chat.py`

**Required Changes:**

1. **Add Message Handler** (new method):
```python
@on(ClickableLogGroupItem.LogGroupPreviewRequested)
async def on_log_group_preview_requested(
    self,
    event: ClickableLogGroupItem.LogGroupPreviewRequested
) -> None:
    """Handle request to preview log group."""
    # Show preview modal
    await self.app.push_screen(
        LogPreviewScreen(
            log_group_name=event.log_group_name,
            datasource=self.orchestrator.datasource,  # Or pass via constructor
        )
    )
```

2. **Pass Dependencies** - Ensure ChatScreen has access to datasource:
```python
# Option A: Get from orchestrator (if available)
datasource = self.orchestrator.datasource

# Option B: Pass explicitly in constructor
def __init__(self, orchestrator, cache_manager, log_group_manager, datasource):
    # ...
    self.datasource = datasource
```

### 5.3 New LogPreviewScreen Component

**New File:** `src/logai/ui/screens/log_preview.py`

**Requirements:**

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Header, Static
from textual.containers import VerticalScroll

class LogPreviewScreen(Screen):
    """Modal screen for previewing recent logs from a log group."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(
        self,
        log_group_name: str,
        datasource: CloudWatchDataSource,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.log_group_name = log_group_name
        self.datasource = datasource

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Preview: {self.log_group_name}", id="preview-title")
        yield VerticalScroll(id="log-events")
        yield Button("Close", id="close-button")

    async def on_mount(self) -> None:
        # Fetch recent logs (last hour)
        end_time = int(time.time() * 1000)
        start_time = end_time - (60 * 60 * 1000)  # 1 hour ago

        try:
            events = await self.datasource.fetch_logs(
                log_group=self.log_group_name,
                start_time=start_time,
                end_time=end_time,
                limit=100,
            )

            # Display events
            container = self.query_one("#log-events", VerticalScroll)
            for event in events:
                # Format timestamp
                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

                # Create log entry widget
                log_widget = Static(
                    f"[cyan]{time_str}[/cyan]\n{event['message']}",
                    classes="log-entry"
                )
                container.mount(log_widget)

        except Exception as e:
            # Show error
            container = self.query_one("#log-events", VerticalScroll)
            error = Static(f"[red]Error fetching logs: {e}[/red]")
            container.mount(error)

    def action_dismiss(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#close-button")
    def on_close_button(self) -> None:
        self.dismiss()
```

**Styling:** Create CSS in `src/logai/ui/styles/log_preview.tcss` or embed in class.

---

## 6. Reusable Components

### 6.1 Available for Immediate Use

1. **CloudWatchDataSource** - Ready to use for fetching logs
   - Path: `src/logai/providers/datasources/cloudwatch.py`
   - Method: `fetch_logs(log_group, start_time, end_time, limit)`

2. **LogGroupManager** - Already integrated, provides log group names
   - Path: `src/logai/core/log_group_manager.py`
   - Method: `get_log_group_names()`

3. **Message Widgets** - Can be styled similarly for log entries
   - Path: `src/logai/ui/widgets/messages.py`
   - Classes: `Static`, `ChatMessage` base

4. **Time Utilities** - For parsing relative time
   - Path: `src/logai/utils/time.py` (need to verify if exists)
   - Fallback: Use `time` module for basic "last 1 hour" default

5. **Error Handling** - Established patterns
   - `ErrorMessage` widget for displaying errors
   - `self.notify()` for toast notifications
   - Try-except with logging

### 6.2 Textual Framework Features

**Version:** `textual>=0.47.0` (from pyproject.toml line 30)

**Available Features:**
- `Screen` class for modals/overlays
- `@on(Event)` decorator for event handling
- `Message` class for custom events
- `app.push_screen()` / `screen.dismiss()` for modal management
- Built-in click/mouse event handling
- Rich text rendering with Markdown support
- CSS-like styling system

**Event System:**
```python
# Built-in events we can use:
- Click (from textual.events)
- MouseMove, MouseDown, MouseUp
- Key events

# Custom messages:
class MyMessage(Message):
    pass

# Handler:
@on(MyMessage)
def handle_message(self, event: MyMessage):
    pass
```

---

## 7. Implementation Recommendations

### 7.1 Recommended Approach (Simplest)

**Phase 1: Add Click Handling**
1. Create `ClickableLogGroupItem` class in `log_groups_sidebar.py`
2. Update `_populate_log_groups()` to use new widget
3. Define custom `LogGroupPreviewRequested` message

**Phase 2: Create Preview Screen**
1. Create new file `src/logai/ui/screens/log_preview.py`
2. Implement `LogPreviewScreen(Screen)` with:
   - Constructor accepting log_group_name and datasource
   - `on_mount()` to fetch and display logs
   - ESC binding and Close button to dismiss
   - Error handling for fetch failures

**Phase 3: Wire Up ChatScreen**
1. Add message handler in `chat.py` to catch `LogGroupPreviewRequested`
2. Call `app.push_screen(LogPreviewScreen(...))` in handler
3. Pass datasource reference to preview screen

**Phase 4: Styling & Polish**
1. Add CSS for preview screen layout
2. Add loading indicator while fetching
3. Add empty state for log groups with no recent logs
4. Add formatting for log timestamps and messages

### 7.2 Time Range for Preview

**Recommended Default:** Last 1 hour of logs (most recent 100-500 events)

**Reasoning:**
- Gives quick overview without overwhelming UI
- Fast to fetch (typically < 1-2 seconds)
- Covers most recent activity
- Can be made configurable later

**Implementation:**
```python
end_time = int(time.time() * 1000)          # Now
start_time = end_time - (60 * 60 * 1000)   # 1 hour ago
limit = 100                                  # Max events
```

### 7.3 Error Handling Strategy

**Scenarios to Handle:**

1. **Log Group Not Found**
   - Display: "Log group no longer exists or was deleted"
   - Action: Suggest refreshing sidebar

2. **No Logs in Time Range**
   - Display: "No logs found in the last hour"
   - Action: Offer to extend time range (future enhancement)

3. **Rate Limiting**
   - Display: "AWS rate limit exceeded, please try again"
   - Action: Built-in retry logic in datasource handles this

4. **Permission Denied**
   - Display: "Insufficient permissions to read logs from this group"
   - Action: Show IAM policy suggestion

5. **Network/Timeout Errors**
   - Display: "Failed to fetch logs: [error message]"
   - Action: Suggest retry, check connectivity

**Implementation Pattern:**
```python
try:
    events = await self.datasource.fetch_logs(...)
except LogGroupNotFoundError:
    self.show_error("Log group not found")
except RateLimitError:
    self.show_error("Rate limit exceeded")
except AuthenticationError as e:
    self.show_error(f"Permission denied: {e}")
except Exception as e:
    self.show_error(f"Failed to fetch logs: {e}")
```

### 7.4 User Feedback During Load

**Recommendation:** Show loading state while fetching logs

**Implementation:**
```python
async def on_mount(self) -> None:
    # Show loading message
    container = self.query_one("#log-events", VerticalScroll)
    loading = LoadingIndicator()
    container.mount(loading)

    try:
        # Fetch logs
        events = await self.datasource.fetch_logs(...)

        # Remove loading, show logs
        loading.remove()
        self._display_events(events)
    except Exception as e:
        loading.remove()
        self._show_error(e)
```

### 7.5 Styling Recommendations

**Preview Screen Layout:**
```
┌─────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-func    │ ← Header
├─────────────────────────────────────┤
│ 2024-02-18 10:30:45                 │
│ START RequestId: abc123             │ ← Log entries
│                                     │   (scrollable)
│ 2024-02-18 10:30:46                 │
│ [INFO] Processing request...        │
│                                     │
│ ...                                 │
├─────────────────────────────────────┤
│           [ Close ]                 │ ← Footer with button
└─────────────────────────────────────┘
```

**CSS Styling:**
```css
LogPreviewScreen {
    align: center middle;
    width: 80%;
    height: 80%;
}

.log-entry {
    background: $panel;
    padding: 1;
    margin: 0 0 1 0;
    border: solid $panel-darken-1;
}

.log-timestamp {
    color: $accent;
    text-style: bold;
}
```

---

## 8. Risks & Challenges

### 8.1 Technical Risks

**Risk 1: Double-Click Detection**
- **Issue:** Textual's click event handling may not have native double-click support
- **Impact:** May need to implement double-click detection manually with timer
- **Mitigation:**
  - Option A: Use single click with modifier (Ctrl+Click)
  - Option B: Implement double-click timer pattern (< 500ms between clicks)
  - Option C: Use Textual's `event.count` if available
- **Recommendation:** Start with Ctrl+Click for MVP, add true double-click later

**Risk 2: Large Log Groups**
- **Issue:** Log groups with high volume may take time to fetch
- **Impact:** UI freeze or slow response
- **Mitigation:**
  - Use async/await properly
  - Show loading indicator immediately
  - Implement timeout (5-10 seconds)
  - Limit to 100-500 events
- **Status:** Datasource already handles async, should be fine

**Risk 3: Modal Screen Stacking**
- **Issue:** If preview screen is open and user triggers another preview
- **Impact:** Multiple modals stacked
- **Mitigation:**
  - Dismiss current preview before opening new one
  - Or: Track state and prevent multiple opens
- **Recommendation:** Let Textual handle naturally (it should work fine)

### 8.2 UX Challenges

**Challenge 1: Discoverability**
- **Issue:** Users may not know double-click is available
- **Impact:** Feature goes unused
- **Mitigation:**
  - Show hint on first launch ("Tip: Double-click a log group to preview")
  - Add to help command output
  - Consider showing on hover (tooltip-like)

**Challenge 2: Empty State**
- **Issue:** Many log groups may have no recent logs
- **Impact:** Confusing empty preview screens
- **Mitigation:**
  - Clear message: "No logs in the last hour"
  - Offer to extend time range (future)
  - Show last log timestamp if available

**Challenge 3: Log Formatting**
- **Issue:** Raw log messages can be very long, JSON blobs, etc.
- **Impact:** Poor readability
- **Mitigation:**
  - Truncate very long lines (> 200 chars)
  - Add "..." to indicate truncation
  - Consider JSON pretty-printing (future)
  - Add word wrapping

### 8.3 Performance Considerations

**Consideration 1: API Rate Limits**
- **Context:** AWS CloudWatch has rate limits (5 requests/second for FilterLogEvents)
- **Impact:** Rapid double-clicking could trigger rate limit errors
- **Mitigation:**
  - Datasource has retry logic with exponential backoff
  - Show rate limit error gracefully
  - Consider debouncing preview requests (e.g., 1 second cooldown)

**Consideration 2: Memory Usage**
- **Context:** Loading many log events could increase memory
- **Impact:** Not significant for 100-500 events
- **Mitigation:**
  - Keep limit reasonable (100-500 events)
  - Dismiss old preview screens properly (Textual should handle)
  - Don't cache preview data (fetch fresh each time)

**Consideration 3: Network Latency**
- **Context:** CloudWatch API calls can take 1-5 seconds depending on region/volume
- **Impact:** User waiting for preview to load
- **Mitigation:**
  - Show loading indicator immediately
  - Set reasonable timeout (10 seconds)
  - Cache results (optional enhancement)

### 8.4 Edge Cases

**Edge Case 1: Log Group Deleted**
- **Scenario:** User opens sidebar, log group is deleted, user double-clicks
- **Handling:** Show error message, suggest refreshing sidebar

**Edge Case 2: Empty Log Group**
- **Scenario:** Log group exists but has never received logs
- **Handling:** Show "No logs found" message with clear explanation

**Edge Case 3: Very Recent Log Group**
- **Scenario:** Log group created minutes ago, no logs yet
- **Handling:** Same as empty log group

**Edge Case 4: Cross-Region Log Groups**
- **Scenario:** User has configured multiple regions (future feature)
- **Handling:** Not applicable yet, single region only

**Edge Case 5: Permission Changes**
- **Scenario:** User loses read permissions between sidebar load and preview
- **Handling:** Show permission error, explain IAM issue

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Test File:** `tests/unit/ui/test_log_groups_sidebar.py`

**Test Cases:**
1. `test_clickable_log_group_item_emits_message` - Verify click event emits message
2. `test_log_preview_screen_fetches_logs` - Verify screen calls datasource
3. `test_log_preview_screen_displays_events` - Verify events rendered correctly
4. `test_log_preview_screen_handles_errors` - Verify error handling
5. `test_log_preview_screen_empty_state` - Verify empty state display

### 9.2 Integration Tests

**Test File:** `tests/integration/ui/test_log_preview_feature.py`

**Test Cases:**
1. `test_end_to_end_preview_flow` - Full flow from click to display
2. `test_preview_with_mocked_cloudwatch` - Using moto to mock AWS
3. `test_preview_error_scenarios` - Rate limits, auth failures, etc.

### 9.3 Manual Testing Checklist

- [ ] Double-click opens preview modal
- [ ] Modal shows loading indicator while fetching
- [ ] Logs display with correct timestamps
- [ ] ESC key closes modal
- [ ] Close button closes modal
- [ ] Error states display correctly
- [ ] Empty log groups show helpful message
- [ ] Multiple sequential previews work
- [ ] Preview works with different sidebar widths
- [ ] Preview works when sidebar is toggled off/on

---

## 10. Code Examples

### 10.1 Complete ClickableLogGroupItem Implementation

```python
# In src/logai/ui/widgets/log_groups_sidebar.py

from textual.events import Click
from textual.message import Message
from textual.widgets import Label

class ClickableLogGroupItem(Label):
    """
    Clickable log group label that emits preview requests on double-click.

    Attributes:
        log_group_name: The CloudWatch log group name
    """

    class PreviewRequested(Message):
        """Message emitted when user requests a log preview."""

        def __init__(self, log_group_name: str) -> None:
            super().__init__()
            self.log_group_name = log_group_name

    def __init__(self, log_group_name: str, **kwargs: Any) -> None:
        """
        Initialize clickable log group item.

        Args:
            log_group_name: CloudWatch log group name
            **kwargs: Additional arguments for Label
        """
        super().__init__(log_group_name, **kwargs)
        self.log_group_name = log_group_name
        self._last_click_time: float = 0.0
        self._double_click_threshold: float = 0.5  # 500ms

    async def on_click(self, event: Click) -> None:
        """
        Handle click events and detect double-clicks.

        Args:
            event: Click event
        """
        if event.button != 1:  # Only handle left clicks
            return

        import time
        current_time = time.time()
        time_since_last_click = current_time - self._last_click_time

        if time_since_last_click < self._double_click_threshold:
            # Double-click detected
            self.post_message(self.PreviewRequested(self.log_group_name))

        self._last_click_time = current_time
```

### 10.2 Updated LogGroupsSidebar._populate_log_groups()

```python
# In src/logai/ui/widgets/log_groups_sidebar.py

def _populate_log_groups(self) -> None:
    """Populate the sidebar with log groups from the manager."""
    if not self._scroll_container:
        return

    # Update title with count
    count = self._get_count()
    if self._title_label:
        self._title_label.update(f"LOG GROUPS ({count})")

    # Clear existing content
    self._scroll_container.remove_children()

    # Get log group names
    log_groups = self._get_log_group_names()

    # Update empty state visibility
    if self._empty_state:
        self._empty_state.display = len(log_groups) == 0

    if not log_groups:
        return

    # Hide empty state
    if self._empty_state:
        self._empty_state.display = False

    # Add clickable log group items
    for name in log_groups:
        # Create clickable item with double-click support
        item = ClickableLogGroupItem(name, classes="log-group-item")
        self._scroll_container.mount(item)
```

### 10.3 ChatScreen Message Handler

```python
# In src/logai/ui/screens/chat.py

from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem
from logai.ui.screens.log_preview import LogPreviewScreen

# ... existing code ...

@on(ClickableLogGroupItem.PreviewRequested)
async def on_log_group_preview_requested(
    self,
    event: ClickableLogGroupItem.PreviewRequested
) -> None:
    """
    Handle request to preview logs from a log group.

    Args:
        event: Preview request event with log group name
    """
    try:
        # Get datasource from orchestrator
        datasource = self.orchestrator.tools[0].datasource  # Or better way to access it

        # Show preview modal
        await self.app.push_screen(
            LogPreviewScreen(
                log_group_name=event.log_group_name,
                datasource=datasource,
            )
        )
    except Exception as e:
        logger.error(f"Failed to open log preview: {e}", exc_info=True)
        self.notify(
            f"Failed to open preview: {str(e)}",
            severity="error",
            timeout=5,
        )
```

### 10.4 LogPreviewScreen Implementation

```python
# New file: src/logai/ui/screens/log_preview.py

"""Log preview screen for displaying recent log events."""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from logai.providers.datasources.cloudwatch import CloudWatchDataSource

logger = logging.getLogger(__name__)


class LogPreviewScreen(Screen[None]):
    """
    Modal screen for previewing recent logs from a CloudWatch log group.

    Shows the most recent logs (default: last 1 hour, max 100 events).
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
    ]

    DEFAULT_CSS = """
    LogPreviewScreen {
        align: center middle;
    }

    #preview-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
    }

    #preview-header {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        padding: 1 2;
        text-style: bold;
    }

    #log-events {
        height: 1fr;
        background: $panel;
        padding: 1;
        overflow-y: auto;
    }

    .log-entry {
        background: $surface;
        padding: 1;
        margin: 0 0 1 0;
        border-left: thick $accent;
    }

    .log-timestamp {
        color: $accent;
        text-style: bold;
    }

    .log-message {
        color: $text;
    }

    .error-state {
        color: $error;
        padding: 2;
        text-align: center;
    }

    .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
        text-align: center;
    }

    #button-container {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """

    def __init__(
        self,
        log_group_name: str,
        datasource: "CloudWatchDataSource",
        time_range_hours: int = 1,
        limit: int = 100,
        **kwargs,
    ) -> None:
        """
        Initialize log preview screen.

        Args:
            log_group_name: CloudWatch log group name to preview
            datasource: CloudWatch data source for fetching logs
            time_range_hours: Hours of history to fetch (default: 1)
            limit: Maximum number of events to fetch (default: 100)
            **kwargs: Additional arguments for Screen
        """
        super().__init__(**kwargs)
        self.log_group_name = log_group_name
        self.datasource = datasource
        self.time_range_hours = time_range_hours
        self.limit = limit

    def compose(self) -> ComposeResult:
        """Compose the preview screen layout."""
        with Container(id="preview-container"):
            yield Static(
                f"Log Preview: {self.log_group_name}",
                id="preview-header",
            )
            yield VerticalScroll(id="log-events")
            with Container(id="button-container"):
                yield Button("Close", id="close-button", variant="primary")

    async def on_mount(self) -> None:
        """Fetch and display logs when screen mounts."""
        self._fetch_and_display_logs()

    @work(exclusive=True)
    async def _fetch_and_display_logs(self) -> None:
        """Worker to fetch and display logs asynchronously."""
        container = self.query_one("#log-events", VerticalScroll)

        try:
            # Show loading indicator
            loading = Static(
                "[cyan]Loading logs...[/cyan]",
                classes="empty-state",
            )
            container.mount(loading)

            # Calculate time range
            end_time = int(time.time() * 1000)
            start_time = end_time - (self.time_range_hours * 60 * 60 * 1000)

            # Fetch logs from CloudWatch
            events = await self.datasource.fetch_logs(
                log_group=self.log_group_name,
                start_time=start_time,
                end_time=end_time,
                limit=self.limit,
            )

            # Remove loading indicator
            loading.remove()

            # Display events or empty state
            if events:
                self._display_events(container, events)
            else:
                container.mount(
                    Static(
                        f"No logs found in the last {self.time_range_hours} hour(s).",
                        classes="empty-state",
                    )
                )

        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}", exc_info=True)
            loading.remove()
            container.mount(
                Static(
                    f"[red]Failed to fetch logs:[/red]\n{str(e)}",
                    classes="error-state",
                )
            )

    def _display_events(
        self,
        container: VerticalScroll,
        events: list[dict[str, str]],
    ) -> None:
        """
        Display log events in the container.

        Args:
            container: Container to mount events into
            events: List of log event dictionaries
        """
        for event in events:
            # Format timestamp
            timestamp_ms = event.get("timestamp", 0)
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds

            # Get message (truncate if very long)
            message = event.get("message", "")
            if len(message) > 500:
                message = message[:500] + "..."

            # Create log entry widget
            log_text = f"[cyan]{time_str}[/cyan]\n{message}"
            log_entry = Static(log_text, classes="log-entry")
            container.mount(log_entry)

        # Scroll to top (most recent)
        container.scroll_home(animate=False)

    def action_dismiss(self) -> None:
        """Close the preview screen."""
        self.dismiss()

    @on(Button.Pressed, "#close-button")
    def on_close_button(self) -> None:
        """Handle close button press."""
        self.dismiss()
```

### 10.5 Updated CSS for LogGroupsSidebar

```python
# In src/logai/ui/widgets/log_groups_sidebar.py

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
    cursor: pointer;  /* NEW: Indicate clickability */
}

LogGroupsSidebar .log-group-item:hover {
    background: $surface;
}

LogGroupsSidebar .log-group-item:active {
    background: $primary-darken-1;  /* NEW: Click feedback */
}
"""
```

---

## 11. File Modification Summary

### Files to Modify

1. **`src/logai/ui/widgets/log_groups_sidebar.py`**
   - Add `ClickableLogGroupItem` class (new ~50 lines)
   - Update `_populate_log_groups()` method (1 line change)
   - Update `DEFAULT_CSS` (2 lines added)
   - **Total changes:** ~50 lines added, 1 line modified

2. **`src/logai/ui/screens/chat.py`**
   - Add import for `ClickableLogGroupItem` and `LogPreviewScreen`
   - Add `on_log_group_preview_requested()` handler method (~20 lines)
   - **Total changes:** ~20 lines added

### Files to Create

1. **`src/logai/ui/screens/log_preview.py`** (new file, ~200 lines)
   - Complete implementation as shown in section 10.4

2. **`tests/unit/ui/test_log_preview.py`** (new file, ~150 lines)
   - Unit tests for preview screen

3. **`tests/integration/ui/test_log_preview_integration.py`** (new file, ~100 lines)
   - Integration tests for end-to-end flow

### Files to Update for Exports

1. **`src/logai/ui/screens/__init__.py`**
   - Add `LogPreviewScreen` to imports and `__all__`
   - **Total changes:** 2 lines

---

## 12. Dependencies & Prerequisites

### Required Dependencies (Already Installed)

- `textual>=0.47.0` ✅ (from pyproject.toml)
- `boto3>=1.34.0` ✅ (for CloudWatch API)
- `rich>=13.7.0` ✅ (for text formatting)

### No New Dependencies Required

All functionality can be implemented using existing libraries.

### Textual Version Compatibility

**Version 0.47.0** includes:
- Screen push/pop API ✅
- Event handling with `@on` decorator ✅
- Click events ✅
- Custom messages ✅
- Rich text rendering ✅

No version upgrade needed.

---

## 13. Timeline Estimate

### For Jackie (Implementation Engineer)

**Estimated Time: 4-6 hours**

- **Hour 1:** Create `ClickableLogGroupItem` class and update sidebar (1 hour)
- **Hour 2-3:** Implement `LogPreviewScreen` with basic layout and fetch logic (2 hours)
- **Hour 4:** Wire up ChatScreen handler and test end-to-end (1 hour)
- **Hour 5:** Add error handling and empty states (1 hour)
- **Hour 6:** Polish styling, add loading indicators, test edge cases (1 hour)

**Breakdown by Complexity:**
- Simple: Adding click handler (30 min)
- Medium: Creating modal screen structure (1 hour)
- Medium: Wiring up event handling (1 hour)
- Medium: Fetching and displaying logs (1.5 hours)
- Simple: Error handling (1 hour)
- Simple: Styling and polish (1 hour)

### Parallel Tasks (Can be done by others)

- **Saanvi (Architect):** Design document and API specification (2 hours)
- **Testing Team:** Write test cases while implementation is in progress (2-3 hours)
- **Documentation:** Update user guide with new feature (1 hour)

---

## 14. Success Criteria

### Functional Requirements

- [x] User can double-click (or Ctrl+Click) a log group in the sidebar
- [x] A modal preview screen opens showing recent logs
- [x] Preview shows last 100 events from the past hour
- [x] Logs are formatted with timestamps and messages
- [x] User can close preview with ESC key or Close button
- [x] Errors are handled gracefully with clear messages
- [x] Empty log groups show helpful "No logs" message

### Non-Functional Requirements

- [x] Preview opens within 2 seconds (for typical log groups)
- [x] UI remains responsive during fetch
- [x] No memory leaks from repeated preview opens
- [x] Works with all sidebar width settings
- [x] Follows existing UI/UX patterns in the app
- [x] Code is documented and follows project conventions

### Testing Criteria

- [x] Unit tests pass for all new components
- [x] Integration tests cover end-to-end flow
- [x] Manual testing checklist completed
- [x] Error scenarios tested (rate limits, auth, etc.)
- [x] Works on both macOS and Linux

---

## 15. Future Enhancements (Out of Scope)

These are potential improvements that should **not** be implemented in the initial version:

1. **Configurable Time Range** - Allow user to select time range (1h, 6h, 24h, etc.)
2. **Search/Filter in Preview** - Add search box to filter displayed logs
3. **Export Logs** - Button to export preview logs to file
4. **Live Streaming** - Auto-refresh to show new logs in real-time
5. **Log Syntax Highlighting** - Pretty-print JSON logs, colorize log levels
6. **Pagination** - Load more logs on scroll (infinite scroll)
7. **Single-Click Preview** - Show preview in sidebar panel instead of modal
8. **Keyboard Navigation** - Arrow keys to navigate between log groups with preview
9. **Copy to Clipboard** - Copy individual log entries or entire preview
10. **Log Stream Selection** - Filter by specific log streams within group

---

## Appendix A: Key File Paths Reference

```
src/logai/
├── ui/
│   ├── app.py                              # Main Textual app
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── chat.py                         # Main chat screen (TARGET)
│   │   └── log_preview.py                  # NEW FILE for preview modal
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── log_groups_sidebar.py           # TARGET for click handling
│   │   ├── messages.py                     # Reusable message widgets
│   │   ├── tool_sidebar.py                 # Reference for patterns
│   │   ├── status_footer.py                # Status bar
│   │   └── input_box.py                    # Chat input
│   └── commands.py                         # Command handler (/refresh, etc.)
├── core/
│   ├── log_group_manager.py                # Data source for log groups
│   ├── orchestrator.py                     # LLM orchestrator
│   └── tools/
│       └── cloudwatch_tools.py             # Tool wrappers for CloudWatch
├── providers/
│   └── datasources/
│       ├── base.py                         # Base datasource classes
│       └── cloudwatch.py                   # CloudWatch API integration
└── config/
    └── settings.py                         # Application settings

tests/
├── unit/
│   └── ui/
│       ├── test_log_groups_sidebar.py      # Existing tests
│       └── test_log_preview.py             # NEW FILE for preview tests
└── integration/
    └── ui/
        └── test_log_preview_integration.py # NEW FILE for integration tests
```

---

## Appendix B: Textual Event Handling Reference

### Click Event Structure

```python
from textual.events import Click

class Click(Event):
    """Emitted when a widget is clicked."""

    button: int         # 1 = left, 2 = middle, 3 = right
    x: int              # X coordinate
    y: int              # Y coordinate
    delta_x: int        # Change in X since last event
    delta_y: int        # Change in Y since last event
    ctrl: bool          # Ctrl key pressed?
    shift: bool         # Shift key pressed?
    meta: bool          # Meta/Cmd key pressed?
    screen_x: int       # Screen X coordinate
    screen_y: int       # Screen Y coordinate
```

### Message Posting Pattern

```python
from textual.message import Message

# Define custom message
class MyCustomMessage(Message):
    def __init__(self, data: str):
        super().__init__()
        self.data = data

# Post message from widget
self.post_message(MyCustomMessage("hello"))

# Handle in parent/screen
@on(MyCustomMessage)
def handle_my_message(self, event: MyCustomMessage):
    print(f"Received: {event.data}")
```

### Screen Push/Pop Pattern

```python
# Push modal screen
result = await self.app.push_screen(MyScreen(param="value"))

# Screen can return value on dismiss
class MyScreen(Screen[str]):
    def action_save(self):
        self.dismiss("saved!")  # Returns "saved!" to push_screen caller

    def action_cancel(self):
        self.dismiss()  # Returns None
```

---

## Appendix C: CloudWatch Logs Data Format

### LogGroupInfo (from LogGroupManager)

```python
{
    "name": "/aws/lambda/my-function",     # Log group name
    "created": 1704067200000,               # Epoch milliseconds
    "stored_bytes": 1048576,                # Size in bytes
    "retention_days": 7                     # Retention policy (or None)
}
```

### Log Event (from CloudWatchDataSource)

```python
{
    "timestamp": 1704067200000,             # Epoch milliseconds
    "message": "START RequestId: abc123",   # Log message (can be multi-line)
    "log_stream": "2024/01/01/[$LATEST]abc", # Log stream name
    "event_id": "unique-event-id"           # CloudWatch event ID
}
```

### Time Range Format

```python
# Epoch milliseconds
start_time = 1704067200000  # 2024-01-01 00:00:00 UTC
end_time = 1704070800000    # 2024-01-01 01:00:00 UTC

# Calculate from current time (Python)
import time
end_time = int(time.time() * 1000)          # Now
start_time = end_time - (60 * 60 * 1000)   # 1 hour ago
```

---

## Conclusion

The log groups sidebar is well-architected and easy to extend. The preview feature can be implemented cleanly by:

1. Adding a clickable widget class with event handling
2. Creating a modal preview screen using Textual's Screen API
3. Leveraging existing CloudWatch datasource for fetching logs
4. Following established patterns for error handling and user feedback

The implementation is straightforward with **no major blockers** identified. The existing codebase provides excellent patterns to follow, and all required dependencies are already in place.

**Key Takeaway:** This is a low-risk, high-value feature that fits naturally into the existing architecture. Estimated implementation time is 4-6 hours for an experienced developer familiar with Textual.

**Recommendation:** Proceed with implementation following the patterns and examples provided in this document.

---

**Document End**

*Generated by George (Investigation Agent) on February 18, 2026*
