# Requirements: Fix Cache Manager Configuration Bug

**Date**: February 17, 2026
**Status**: Approved
**Priority**: Critical
**Estimated Effort**: 1 hour

---

## Executive Summary

The Cache Manager has hardcoded class constants that completely override user `.env` settings. Users who configure `LOGAI_CACHE_MAX_SIZE_MB` in their `.env` file expect it to work, but the code ignores it and uses the hardcoded value instead.

---

## Problem Statement

**Current Behavior (BUG)**:
```python
# In src/logai/cache/manager.py:19-22
CACHE_MAX_SIZE_MB = 500        # Hardcoded - ignores user .env!
CACHE_MAX_ENTRIES = 10000      # Hardcoded - ignores user .env!
CACHE_EVICTION_BATCH = 100     # Hardcoded - ignores user .env!
CACHE_CLEANUP_INTERVAL = 300   # Hardcoded - ignores user .env!
```

**Expected Behavior**:
The Cache Manager should respect user settings from `.env` file:
- `LOGAI_CACHE_MAX_SIZE_MB` (default: 500)
- `LOGAI_CACHE_MAX_ENTRIES` (if exists, not currently in settings)
- `LOGAI_CACHE_EVICTION_BATCH` (if exists)
- `LOGAI_CACHE_CLEANUP_INTERVAL` (if exists)

---

## Impact

**Severity**: High
**Users Affected**: Anyone who tries to configure cache settings in `.env`

**User Story**:
> As a user with limited disk space, I set `LOGAI_CACHE_MAX_SIZE_MB=100` in my `.env` file, expecting the cache to respect this limit. However, the cache still grows to 500MB because my setting is completely ignored.

---

## Root Cause

The `CacheManager` class defines class-level constants that shadow the settings values:

```python
class CacheManager:
    CACHE_MAX_SIZE_MB = 500  # Class constant takes precedence

    def __init__(self, settings: Settings, ...):
        # Uses class constant instead of settings.cache_max_size_mb
        self._max_size_bytes = self.CACHE_MAX_SIZE_MB * 1024 * 1024
```

---

## Solution

### Option 1: Use Settings Directly (RECOMMENDED)

Remove class constants and use `settings` object directly:

```python
class CacheManager:
    def __init__(self, settings: Settings, ...):
        self._max_size_bytes = settings.cache_max_size_mb * 1024 * 1024
        self._max_entries = getattr(settings, 'cache_max_entries', 10000)
        self._eviction_batch = getattr(settings, 'cache_eviction_batch', 100)
        self._cleanup_interval = getattr(settings, 'cache_cleanup_interval', 300)
```

**Pros**: Simple, direct, uses existing settings infrastructure
**Cons**: Need to add missing settings to Settings class if desired

### Option 2: Keep Constants as Defaults

Use constants as fallbacks only:

```python
class CacheManager:
    DEFAULT_MAX_SIZE_MB = 500
    DEFAULT_MAX_ENTRIES = 10000

    def __init__(self, settings: Settings, ...):
        max_size_mb = getattr(settings, 'cache_max_size_mb', self.DEFAULT_MAX_SIZE_MB)
        self._max_size_bytes = max_size_mb * 1024 * 1024
```

**Pros**: Clear separation of defaults
**Cons**: More verbose

---

## Recommended Implementation (Option 1)

### Step 1: Check Current Settings

Verify which cache settings already exist in `settings.py`:
- ✅ `cache_max_size_mb` - Already exists
- ❓ `cache_max_entries` - Check if exists
- ❓ `cache_eviction_batch` - Check if exists
- ❓ `cache_cleanup_interval` - Check if exists

### Step 2: Add Missing Settings (if needed)

If any settings don't exist, add them to `settings.py` and `.env.example`:

```python
# In settings.py
cache_max_entries: int = Field(
    default=10000,
    description="Maximum number of cache entries"
)
```

```bash
# In .env.example
LOGAI_CACHE_MAX_ENTRIES=10000
```

### Step 3: Update CacheManager

Remove class constants and use settings:

```python
# Remove these lines (around line 19-22)
# CACHE_MAX_SIZE_MB = 500
# CACHE_MAX_ENTRIES = 10000
# CACHE_EVICTION_BATCH = 100
# CACHE_CLEANUP_INTERVAL = 300

# Update __init__ to use settings
def __init__(self, settings: Settings, ...):
    self._max_size_bytes = settings.cache_max_size_mb * 1024 * 1024
    self._max_entries = settings.cache_max_entries
    self._eviction_batch = settings.cache_eviction_batch
    self._cleanup_interval = settings.cache_cleanup_interval
```

### Step 4: Update Tests

Update any tests that reference the old constants:
- Search for `CacheManager.CACHE_MAX_SIZE_MB` references
- Update to use settings or mock settings values

---

## Testing Strategy

### Unit Tests
1. Test that CacheManager respects `settings.cache_max_size_mb`
2. Test that changing settings changes cache behavior
3. Test default values work when settings not specified

### Integration Tests
1. Test with `.env` file containing custom cache settings
2. Verify cache respects user-specified limits
3. Verify cache eviction works with custom batch size

### Manual Test
1. Set `LOGAI_CACHE_MAX_SIZE_MB=100` in `.env`
2. Run application and populate cache
3. Verify cache stops at ~100MB (not 500MB)

---

## Success Criteria

- [ ] Cache Manager uses `settings.cache_max_size_mb` instead of hardcoded 500
- [ ] All other cache constants either use settings or have sensible defaults
- [ ] Existing tests pass
- [ ] New tests verify settings are respected
- [ ] Documentation updated (if adding new .env variables)
- [ ] No breaking changes (existing defaults still work)

---

## Breaking Changes

**None expected**. This is a bug fix that makes the code work as documented.

Users who:
- Don't have cache settings in `.env` → No change (uses defaults)
- Have cache settings in `.env` → Settings now work correctly (currently broken)

---

## Files to Modify

1. `src/logai/cache/manager.py` - Remove constants, use settings
2. `src/logai/config/settings.py` - Add missing cache settings (if any)
3. `.env.example` - Add missing cache env vars (if any)
4. `tests/unit/test_cache_manager.py` - Update tests for settings usage
5. `docs/user-guide/configuration.md` - Document cache settings (if not already)

---

## Implementation Plan

1. **Jackie**: Investigate current settings and implement fix
2. **Raoul**: Write/update tests to verify fix
3. **Han-Ron**: Review changes
4. **Tina**: Update documentation if needed
5. **George**: Coordinate and commit

**Estimated Time**: 1 hour development + 30 minutes testing + 15 minutes review = ~2 hours total

---

## Related Issues

This bug was discovered during the hardcoded configuration audit. Other configurations may have similar issues, but this is the only confirmed case where user settings are completely ignored.

---

## References

- Full audit report: `george-scratch/requirements-externalize-hardcoded-config.md`
- Cache Manager: `src/logai/cache/manager.py:19-22`
- Settings class: `src/logai/config/settings.py`

---

**Status**: Ready for implementation
**Next Step**: Jackie investigates and implements fix
