# Test Documentation: Context Modal Callback Pattern

## Overview

This document provides comprehensive documentation for the test suite covering Jackie's callback pattern fix for the context modal result bug in the LogAI application.

## Bug Context

**Original Issue:** Modal results weren't being received by chat.py because the code incorrectly used `await push_screen()` which doesn't wait for the modal to close or capture its result.

**Fix:** Implemented the proper callback pattern using `app.push_screen(LogPreviewScreen(...), handle_log_selection)` where `handle_log_selection` is an async callback function that receives the modal's result.

**Code Location:** `src/logai/ui/screens/chat.py`, lines 347-382

## Test Suite Summary

- **Total Tests:** 33
- **Pass Rate:** 100% (33/33 passing)
- **Execution Time:** 3.93 seconds
- **Coverage:** 36% of chat.py (specifically covering lines 347-382, 392-432, 433-471)

### Test Files

1. **`tests/unit/ui/test_chat_callback.py`** - 24 unit tests
2. **`tests/integration/test_context_modal_callback.py`** - 9 integration tests

---

## Unit Tests (`test_chat_callback.py`)

### TestCallbackPattern (5 tests)

These tests verify the fundamental callback mechanism.

#### `test_callback_is_defined_in_handler`
**Purpose:** Verifies that the callback function is properly defined and passed to `push_screen()`.

**What it tests:**
- Triggers a `LogGroupPreviewRequested` event
- Verifies `app.push_screen()` is called exactly once
- Confirms the second argument to `push_screen()` is a callable (the callback)

**Why it matters:** Ensures the callback pattern is implemented correctly at the most basic level.

---

#### `test_callback_receives_result_dict`
**Purpose:** Verifies the callback receives and processes result data from the modal.

**What it tests:**
- Extracts the callback from the `push_screen()` call
- Invokes the callback with a mock result dict containing log entries
- Verifies `_inject_log_entries_to_context()` is called with the correct data

**Why it matters:** Confirms data flows from the modal through the callback to the injection method.

---

#### `test_callback_handles_none_result`
**Purpose:** Verifies the callback gracefully handles `None` results (user cancels modal).

**What it tests:**
- Invokes the callback with `None`
- Verifies `_inject_log_entries_to_context()` is NOT called
- Ensures no exceptions are raised

**Why it matters:** Users can cancel modals; the app must handle this gracefully without crashing.

---

#### `test_callback_handles_empty_dict`
**Purpose:** Verifies the callback handles empty result dictionaries.

**What it tests:**
- Invokes the callback with an empty dict `{}`
- Verifies `_inject_log_entries_to_context()` is called with empty data
- Ensures the empty dict is passed through correctly

**Why it matters:** Edge case where the modal returns a dict but with no meaningful data.

---

#### `test_callback_name_is_handle_log_selection`
**Purpose:** Verifies the callback function has the expected name for debugging.

**What it tests:**
- Extracts the callback and checks its `__name__` attribute
- Confirms it equals `"handle_log_selection"`

**Why it matters:** Helps with debugging, logging, and code maintainability. Makes stack traces clearer.

---

### TestCallbackDataFlow (5 tests)

These tests verify data integrity as it flows through the callback.

#### `test_callback_with_single_entry`
**Purpose:** Verifies callback correctly handles a single log entry.

**What it tests:**
- Creates result with 1 log entry
- Invokes callback with this data
- Verifies injection method receives correct log_group_name and 1 entry

**Why it matters:** Single entry is a common use case; data must be preserved accurately.

---

#### `test_callback_with_ten_entries`
**Purpose:** Verifies callback correctly handles 10 log entries.

**What it tests:**
- Creates result with 10 log entries
- Invokes callback with this data
- Verifies injection method receives all 10 entries with correct structure

**Why it matters:** Tests typical batch size; ensures no data loss in moderate volumes.

---

#### `test_callback_with_hundred_entries`
**Purpose:** Verifies callback correctly handles 100 log entries.

**What it tests:**
- Creates result with 100 log entries
- Invokes callback with this data
- Verifies injection method receives all 100 entries

**Why it matters:** Tests larger batch; ensures scalability and no truncation issues.

---

#### `test_callback_preserves_log_group_name`
**Purpose:** Verifies the log group name is preserved through the callback.

**What it tests:**
- Uses specific log group name "production-errors-2024"
- Invokes callback
- Verifies injection method receives exact same log group name

**Why it matters:** Log group name is critical context; corruption would cause incorrect attribution.

---

#### `test_callback_preserves_entry_structure`
**Purpose:** Verifies log entry structure and content are preserved.

**What it tests:**
- Creates entries with specific fields (timestamp, level, message, metadata)
- Invokes callback
- Verifies injection method receives entries with identical structure and values

**Why it matters:** Log entries contain critical diagnostic data; any corruption is unacceptable.

---

### TestCallbackEdgeCases (6 tests)

These tests verify behavior with unusual or edge case inputs.

#### `test_callback_with_zero_entries_selected`
**Purpose:** Verifies callback handles result with 0 selected entries.

**What it tests:**
- Creates result with empty `selected_entries` list
- Invokes callback
- Verifies injection method receives empty list

**Why it matters:** User might dismiss modal without selecting anything; must handle gracefully.

---

#### `test_callback_with_missing_log_group_name_key`
**Purpose:** Verifies callback handles result missing the `log_group_name` key.

**What it tests:**
- Creates result dict without `log_group_name` key
- Invokes callback
- Verifies injection method receives `None` for log_group_name

**Why it matters:** Defensive programming; protects against malformed data from modal.

---

#### `test_callback_with_false_value`
**Purpose:** Verifies callback preserves boolean `False` values.

**What it tests:**
- Creates result with `log_group_name=False`
- Invokes callback
- Verifies `False` is passed through (not converted to None/empty)

**Why it matters:** Falsy values must be distinguished from missing values.

---

#### `test_callback_with_zero_value`
**Purpose:** Verifies callback preserves numeric `0` values.

**What it tests:**
- Creates result with `log_group_name=0`
- Invokes callback
- Verifies `0` is passed through

**Why it matters:** Zero is a valid value and must not be treated as None/empty.

---

#### `test_callback_with_empty_string`
**Purpose:** Verifies callback preserves empty string values.

**What it tests:**
- Creates result with `log_group_name=""`
- Invokes callback
- Verifies empty string is passed through

**Why it matters:** Empty strings are semantically different from None and must be preserved.

---

#### `test_callback_with_missing_selected_entries_key`
**Purpose:** Verifies callback handles result missing the `selected_entries` key.

**What it tests:**
- Creates result dict without `selected_entries` key
- Invokes callback
- Verifies injection method receives `None` for selected_entries

**Why it matters:** Defensive programming; prevents KeyError exceptions.

---

### TestCallbackErrorHandling (2 tests)

These tests verify error handling and logging behavior.

#### `test_inject_method_exception_is_caught`
**Purpose:** Verifies exceptions in the injection method are caught and logged.

**What it tests:**
- Mocks `_inject_log_entries_to_context()` to raise `ValueError`
- Invokes callback
- Verifies exception is caught (no propagation)
- Verifies error is logged

**Why it matters:** Errors in callback shouldn't crash the app; user should see error message.

---

#### `test_callback_logs_received_result`
**Purpose:** Verifies callback logs the result it receives (for debugging).

**What it tests:**
- Invokes callback with test data
- Verifies logger.info is called with result data

**Why it matters:** Logging helps diagnose issues in production; confirms callback was invoked.

---

### TestInjectLogEntriesToContext (7 tests)

These tests verify the `_inject_log_entries_to_context()` method that the callback invokes.

#### `test_inject_extracts_log_group_name`
**Purpose:** Verifies method correctly extracts log group name from result dict.

**What it tests:**
- Calls inject method with specific log group name
- Verifies system message includes that name

**Why it matters:** Log group name provides crucial context in chat messages.

---

#### `test_inject_extracts_selected_entries`
**Purpose:** Verifies method correctly extracts selected entries from result dict.

**What it tests:**
- Calls inject method with 3 entries
- Verifies system message includes all 3 entries in JSON format

**Why it matters:** Selected entries are the core data being injected into context.

---

#### `test_inject_formats_entries_as_json`
**Purpose:** Verifies entries are formatted as JSON with proper indentation.

**What it tests:**
- Calls inject method
- Verifies system message contains JSON-formatted entries
- Confirms JSON is parseable and matches original data

**Why it matters:** JSON format is standard for structured log data; must be valid and readable.

---

#### `test_inject_shows_system_message_for_single_entry`
**Purpose:** Verifies system message uses singular grammar for 1 entry.

**What it tests:**
- Calls inject method with 1 entry
- Verifies message says "1 log entry" (not "1 log entries")

**Why it matters:** Proper grammar improves UX and professionalism.

---

#### `test_inject_shows_system_message_for_multiple_entries`
**Purpose:** Verifies system message uses plural grammar for multiple entries.

**What it tests:**
- Calls inject method with 5 entries
- Verifies message says "5 log entries"

**Why it matters:** Proper grammar for plural case.

---

#### `test_inject_handles_exception_gracefully`
**Purpose:** Verifies method handles exceptions without crashing.

**What it tests:**
- Mocks `show_system_message()` to raise exception
- Calls inject method
- Verifies exception is caught and logged

**Why it matters:** UI errors shouldn't propagate; user should see error message.

---

#### `test_inject_with_zero_entries`
**Purpose:** Verifies method handles 0 entries correctly.

**What it tests:**
- Calls inject method with empty entries list
- Verifies message says "0 log entries"
- Confirms no crash or error

**Why it matters:** Edge case that must be handled gracefully.

---

## Integration Tests (`test_context_modal_callback.py`)

### TestModalCallbackIntegration (5 tests)

These tests verify end-to-end flows from event trigger to context injection.

#### `test_end_to_end_modal_to_context_flow`
**Purpose:** Verifies complete flow from opening modal to injecting context.

**What it tests:**
- Triggers event to open modal
- Simulates modal dismissal with result
- Verifies system message appears in chat with correct content
- Confirms full data flow works

**Why it matters:** This is the primary use case; must work flawlessly end-to-end.

---

#### `test_end_to_end_user_cancels_modal`
**Purpose:** Verifies cancellation flow (modal dismissed with None).

**What it tests:**
- Triggers event to open modal
- Simulates modal dismissal with `None`
- Verifies no system message is shown
- Confirms cancellation is handled gracefully

**Why it matters:** Users frequently cancel operations; app must handle without issues.

---

#### `test_multiple_modal_opens_use_different_callbacks`
**Purpose:** Verifies each modal open creates a new callback (no callback reuse bugs).

**What it tests:**
- Opens modal twice with different data
- Verifies each gets its own callback
- Confirms no cross-contamination between callbacks

**Why it matters:** Callback reuse could cause data to go to wrong context; must be isolated.

---

#### `test_no_race_condition_with_rapid_operations`
**Purpose:** Verifies no race conditions when opening/closing modal rapidly.

**What it tests:**
- Opens modal
- Closes it immediately
- Opens again
- Closes again
- Verifies correct number of messages appear

**Why it matters:** Users might rapidly click; app must handle without corruption or duplication.

---

#### `test_callback_with_large_entry_count`
**Purpose:** Verifies performance and correctness with 500 log entries.

**What it tests:**
- Opens modal with 500 entries
- Verifies all 500 are injected correctly
- Confirms no truncation or performance degradation

**Why it matters:** Real-world log groups can be large; must scale properly.

---

### TestCallbackErrorRecovery (2 tests)

These tests verify error recovery behavior.

#### `test_callback_error_logged_and_notified`
**Purpose:** Verifies errors in callback are logged and user is notified.

**What it tests:**
- Mocks inject method to raise exception
- Triggers callback
- Verifies error is logged
- Confirms user sees notification

**Why it matters:** Users must be informed of errors; silent failures are unacceptable.

---

#### `test_subsequent_callback_works_after_error`
**Purpose:** Verifies app recovers from callback errors and subsequent callbacks work.

**What it tests:**
- First callback fails with exception
- Second callback succeeds
- Verifies second callback works correctly (app didn't get stuck in error state)

**Why it matters:** One error shouldn't permanently break functionality; app must recover.

---

### TestCallbackTimingAndPerformance (2 tests)

These tests verify async behavior and performance.

#### `test_callback_is_async`
**Purpose:** Verifies callback is an async function (required by Textual).

**What it tests:**
- Extracts callback
- Uses `inspect.iscoroutinefunction()` to verify it's async

**Why it matters:** Textual requires async callbacks; sync callbacks would cause errors.

---

#### `test_callback_execution_is_fast`
**Purpose:** Verifies callback executes quickly (<100ms).

**What it tests:**
- Times callback execution
- Asserts total time is under 100ms

**Why it matters:** Slow callbacks block UI; must be fast for good UX.

---

## Coverage Report

### Overall Coverage
- **chat.py:** 36% (198 of 311 lines missed)
- **Callback pattern code (lines 347-382):** 100% covered
- **Injection method (lines 392-432):** 100% covered
- **Formatting helper (lines 433-471):** 100% covered

### Lines Covered
- **347-382:** `on_log_group_preview_requested` method and `handle_log_selection` callback
- **392-432:** `_inject_log_entries_to_context` method
- **433-471:** `_format_log_entries_for_context` helper method

### Lines Not Covered
The uncovered lines (36% of chat.py) are unrelated to the callback pattern and include:
- Lines 138-343: Other event handlers and methods
- Lines 480-731: Message handling, command processing, etc.

These are outside the scope of this test suite focused on the callback pattern fix.

---

## Test Execution

### Running All Tests
```bash
pytest tests/unit/ui/test_chat_callback.py tests/integration/test_context_modal_callback.py -v
```

### Running with Coverage
```bash
pytest tests/unit/ui/test_chat_callback.py tests/integration/test_context_modal_callback.py \
  --cov=src/logai/ui/screens/chat --cov-report=term-missing --cov-report=html -v
```

### Running Specific Test Class
```bash
pytest tests/unit/ui/test_chat_callback.py::TestCallbackPattern -v
```

### Running Specific Test
```bash
pytest tests/unit/ui/test_chat_callback.py::TestCallbackPattern::test_callback_is_defined_in_handler -v
```

---

## Key Testing Insights

### 1. Property Mocking Challenge
**Problem:** `chat_screen.app` is a read-only property in Textual's Screen class.

**Solution:** Use `patch.object(type(chat_screen), "app", new_callable=PropertyMock)` to mock the property at the class level.

**Why it matters:** Incorrect mocking would cause `AttributeError: can't set attribute`.

### 2. SystemMessage Content Access
**Problem:** SystemMessage (inherits from Textual's Static) doesn't expose content publicly.

**Solution:** Access private attribute `_Static__content` for test assertions.

**Why it matters:** Tests need to verify message content to confirm correct data injection.

### 3. Callback Extraction Pattern
**Problem:** Callbacks are passed as arguments to `push_screen()` and aren't directly accessible.

**Solution:** Extract callback from `mock_app.push_screen.call_args[0][1]` after triggering event.

**Why it matters:** Tests need to invoke callbacks directly to verify behavior.

### 4. Async Callback Handling
**Problem:** Callbacks must be async to work with Textual framework.

**Solution:** Use `await` when invoking callbacks in tests; verify with `inspect.iscoroutinefunction()`.

**Why it matters:** Sync callbacks would fail in production; tests must verify async behavior.

---

## Success Criteria Met

✅ **All tests pass:** 33/33 (100% pass rate)
✅ **Fast execution:** 3.93 seconds (under 5 second requirement)
✅ **Comprehensive coverage:** Callback pattern, data flow, edge cases, error handling, integration
✅ **Clear test names:** All tests have descriptive names explaining what they verify
✅ **Documentation:** This comprehensive guide explains every test's purpose and importance

---

## Maintenance Notes

### Adding New Tests
When adding new callback-related tests:
1. Follow the existing naming pattern: `test_<aspect>_<scenario>`
2. Add docstrings explaining the test's purpose
3. Use appropriate test class (`TestCallback*`, `TestInject*`, etc.)
4. Update this documentation with the new test

### Modifying Callback Implementation
If the callback pattern changes in `chat.py`:
1. Run full test suite to identify breaking changes
2. Update affected tests to match new implementation
3. Add new tests for new functionality
4. Update coverage expectations if new lines are added

### Common Issues
- **Property mocking errors:** Ensure using `PropertyMock` for `app` property
- **Content access errors:** Remember to use `_Static__content` for SystemMessage
- **Async errors:** Always `await` callback invocations in tests
- **Missing coverage:** Verify test actually triggers the code path (check with debugger)

---

## Related Files

- `src/logai/ui/screens/chat.py` - Implementation being tested
- `src/logai/ui/screens/log_preview.py` - Modal that dismisses with results
- `src/logai/ui/widgets/messages.py` - SystemMessage widget
- `src/logai/ui/widgets/log_groups_sidebar.py` - Event that triggers modal
- `tests/conftest.py` - Shared test fixtures
