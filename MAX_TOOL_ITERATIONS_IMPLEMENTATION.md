# Max Tool Iterations Configuration - Implementation Summary

## Overview
Made the maximum tool iterations limit configurable via settings instead of being hardcoded to 10. This allows users to adjust the limit based on their needs for complex investigations or cost control.

## Changes Made

### 1. Configuration Setting (`src/logai/config/settings.py`)
**Added new field:**
```python
max_tool_iterations: int = Field(
    default=10,
    description="Maximum number of tool calls allowed in a single conversation turn. Prevents infinite loops.",
    ge=1,  # Must be at least 1
    le=100  # Reasonable upper limit
)
```

**Features:**
- Default value: `10` (backward compatible)
- Validation: minimum 1, maximum 100
- Environment variable: `LOGAI_MAX_TOOL_ITERATIONS`
- Part of the Agent Self-Direction settings section

### 2. Orchestrator Updates (`src/logai/core/orchestrator.py`)

**Removed hardcoded constant:**
```python
# OLD: MAX_TOOL_ITERATIONS = 10  # Prevent infinite loops
# NEW: Use self.settings.max_tool_iterations dynamically
```

**Updated in `_chat_complete()` method:**
```python
max_iterations = self.settings.max_tool_iterations
while iteration < max_iterations:
    # ... conversation loop
```

**Updated in `_chat_stream()` method:**
```python
max_iterations = self.settings.max_tool_iterations
while iteration < max_iterations:
    # ... conversation loop
```

**Updated error messages:**
```python
error_msg = f"Maximum tool iterations ({max_iterations}) exceeded."
```

### 3. Test Updates (`tests/unit/test_orchestrator.py`)

**Updated mock_settings fixture:**
- Added `max_tool_iterations = 10` to all mock settings

**Added new test class `TestMaxToolIterationsConfiguration` with 4 tests:**

1. **`test_custom_max_iterations_limit`**
   - Tests that custom limit (5) is respected
   - Verifies orchestrator stops at custom limit
   - Verifies error message includes custom limit

2. **`test_default_max_iterations_value`**
   - Tests that default value (10) works correctly
   - Uses standard orchestrator fixture
   - Verifies backward compatibility

3. **`test_max_iterations_streaming`**
   - Tests that limit works in streaming mode
   - Uses low limit (3) for fast testing
   - Verifies both streaming and non-streaming behave consistently

4. **`test_settings_validation`**
   - Tests valid values (1, 50, 100)
   - Tests default value (10)
   - Tests invalid values raise ValidationError (0, 101)
   - Verifies Pydantic validation works correctly

**Updated existing tests:**
- Updated comments from `MAX_TOOL_ITERATIONS` to `max_tool_iterations`
- Added `max_tool_iterations` to all mock settings objects

### 4. Documentation (`README.md`)

**Added to Environment Variables table:**
```
| `LOGAI_MAX_TOOL_ITERATIONS` | Max tool calls per conversation turn | `10` | No |
```

**Added detailed section:**
```markdown
#### Agent Behavior Settings

**`LOGAI_MAX_TOOL_ITERATIONS`** - Controls the maximum number of tool calls...

- **Default:** `10` (suitable for most queries)
- **Range:** `1-100`
- **When to increase:** Complex investigations, multi-step analysis, debugging
- **When to decrease:** Cost control, faster failure detection, testing
```

**Included usage examples:**
```bash
# Allow more iterations for complex investigations
export LOGAI_MAX_TOOL_ITERATIONS=25
logai

# Strict limit for cost control
export LOGAI_MAX_TOOL_ITERATIONS=5
logai
```

## Testing Results

### Unit Tests
All 26 orchestrator tests pass, including 4 new tests:
```
tests/unit/test_orchestrator.py::TestMaxToolIterationsConfiguration::test_custom_max_iterations_limit PASSED
tests/unit/test_orchestrator.py::TestMaxToolIterationsConfiguration::test_default_max_iterations_value PASSED
tests/unit/test_orchestrator.py::TestMaxToolIterationsConfiguration::test_max_iterations_streaming PASSED
tests/unit/test_orchestrator.py::TestMaxToolIterationsConfiguration::test_settings_validation PASSED
```

### Integration Tests
Verified:
- ✓ Default value is 10
- ✓ Environment variable `LOGAI_MAX_TOOL_ITERATIONS` works
- ✓ Validation rejects values < 1
- ✓ Validation rejects values > 100
- ✓ Orchestrator accesses setting correctly

## Usage

### Via Environment Variable
```bash
# Set custom limit
export LOGAI_MAX_TOOL_ITERATIONS=20
logai

# Or inline
LOGAI_MAX_TOOL_ITERATIONS=5 logai
```

### Via .env File
```bash
# .env
LOGAI_MAX_TOOL_ITERATIONS=15
```

### Programmatically
```python
from logai.config.settings import LogAISettings

settings = LogAISettings(max_tool_iterations=25)
```

## Backward Compatibility

✅ **Fully backward compatible**
- Default value remains 10
- All existing code works without changes
- No breaking changes to API

## Recommendations

### Default (10 iterations)
- Suitable for most queries
- Good balance of thoroughness and safety
- Recommended for production use

### Increased (20-50 iterations)
- Complex multi-step investigations
- Root cause analysis requiring many tool calls
- Debugging sessions with extensive retry logic
- Development and testing environments

### Decreased (5 or less)
- Cost control in high-volume scenarios
- Quick failure detection
- Testing and CI/CD pipelines
- Rate-limited environments

## Performance Implications

**Higher values:**
- ✅ More thorough investigations
- ✅ Better handling of complex queries
- ❌ Higher API costs
- ❌ Longer response times
- ❌ Potential for more "stuck" states

**Lower values:**
- ✅ Lower API costs
- ✅ Faster failure detection
- ✅ Predictable resource usage
- ❌ May stop before completing investigation
- ❌ Less thorough for complex queries

## Files Modified

1. `src/logai/config/settings.py` - Added configuration field
2. `src/logai/core/orchestrator.py` - Removed hardcoded value, use dynamic setting
3. `tests/unit/test_orchestrator.py` - Added 4 new tests, updated mocks
4. `README.md` - Added documentation

## Related Settings

This setting works in conjunction with:
- `max_retry_attempts` (3) - Controls retry prompt injections
- `auto_retry_enabled` (true) - Enables automatic retries
- `intent_detection_enabled` (true) - Detects intent without action

Note: `max_tool_iterations` is the global safety limit that prevents infinite loops, while `max_retry_attempts` controls how many times the orchestrator injects retry guidance prompts.

## Future Enhancements

Potential future improvements:
1. Dynamic adjustment based on query complexity
2. Per-tool iteration limits
3. Warning thresholds before hitting limit
4. Metrics/monitoring for iteration patterns
5. User notifications when approaching limit
