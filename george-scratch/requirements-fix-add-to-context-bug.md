# Requirements: Fix "Add to Context" Bug - Priority Conflict

**Date**: February 19, 2026
**Feature**: Bug Fix - Add to Context loses user-selected logs
**Priority**: HIGH
**Status**: In Progress

---

## Overview

Fix a bug where user-selected logs added via "Add to Context" are silently lost when tool calls generate cached results. This is a priority conflict issue in the orchestrator's context injection mechanism.

---

## Bug Report

**Symptom**: User selects logs, clicks "Add to Context", asks a question about them, but the agent responds as if the logs weren't in context.

**Root Cause**: In `src/logai/core/orchestrator.py` lines 435-470, the `_get_pending_context_injection()` method returns ONLY cache guidance when both cache guidance and user context exist, silently dropping the user's selected logs.

**Severity**: MEDIUM - Partial failure with high probability in normal usage

---

## User Story

**As a** user debugging with log preview
**I want** my selected logs to always reach the agent
**So that** the agent can answer questions about the logs I explicitly added to context

---

## Requirements

### Functional Requirements

1. **Preserve Both Injections**
   - When both cache guidance and user context exist, both should be sent to the agent
   - User-selected logs must never be lost
   - Cache guidance must still function correctly

2. **Combined Injection Format**
   - Combine both injections with a clear separator
   - Maintain readability for the agent
   - Preserve all existing functionality

3. **Backwards Compatibility**
   - When only cache guidance exists, behavior unchanged
   - When only user context exists, behavior unchanged
   - No breaking changes to existing features

### Non-Functional Requirements

1. **No Data Loss**
   - User-selected logs always reach the agent
   - Cache guidance always included when needed
   - Both injections preserved completely

2. **Clear Separation**
   - Use clear separator between injections
   - Agent can distinguish between different types of context

---

## Technical Details

### Current Buggy Code

Location: `src/logai/core/orchestrator.py` lines 435-470

```python
def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    # Check cache guidance FIRST
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None
        cache_guidance = f"""SYSTEM INSTRUCTION: ..."""
        return cache_guidance  # ← BUG: User context lost!

    # Only reached if cache guidance doesn't exist
    injection = self._pending_context_injection
    self._pending_context_injection = None
    return injection
```

### Required Fix

Replace the method to combine both injections:

```python
def _get_pending_context_injection(self) -> str | None:
    """Get and clear any pending context injection."""
    injections = []

    # Include cache guidance if available
    if self._pending_cache_guidance and self.settings.enable_auto_fetch_guidance:
        guidance = self._pending_cache_guidance
        self._pending_cache_guidance = None
        cache_guidance = f"""SYSTEM INSTRUCTION: ..."""
        injections.append(cache_guidance)

    # Include user-selected log entries if available
    if self._pending_context_injection:
        injection = self._pending_context_injection
        self._pending_context_injection = None
        injections.append(injection)

    # Return combined injections or None if empty
    if injections:
        return "\n\n---\n\n".join(injections)
    return None
```

---

## Acceptance Criteria

- [ ] Method combines both cache guidance and user context when both exist
- [ ] User-selected logs always reach the agent (never lost)
- [ ] Cache guidance still works correctly
- [ ] Clear separator between injections (`\n\n---\n\n`)
- [ ] Both pending variables cleared after use
- [ ] Returns None when no injections pending
- [ ] No breaking changes to existing functionality
- [ ] Unit tests added and passing
- [ ] Manual testing confirms fix works
- [ ] Code review approved

---

## Test Cases

### Test 1: Both injections present
```python
orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}
orchestrator.inject_context_update("USER LOGS: ...")

result = orchestrator._get_pending_context_injection()

# Should contain BOTH
assert "SYSTEM INSTRUCTION" in result
assert "USER-SELECTED LOG ENTRIES" in result
assert "---" in result  # Separator
```

### Test 2: Only cache guidance
```python
orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}

result = orchestrator._get_pending_context_injection()

assert "SYSTEM INSTRUCTION" in result
assert "USER-SELECTED LOG ENTRIES" not in result
```

### Test 3: Only user context
```python
orchestrator.inject_context_update("USER LOGS: ...")

result = orchestrator._get_pending_context_injection()

assert "USER-SELECTED LOG ENTRIES" in result
assert "SYSTEM INSTRUCTION" not in result
```

### Test 4: No injections
```python
result = orchestrator._get_pending_context_injection()

assert result is None
```

### Test 5: Both variables cleared
```python
orchestrator._pending_cache_guidance = {"cache_id": "test", "total_events": 100}
orchestrator.inject_context_update("USER LOGS: ...")

orchestrator._get_pending_context_injection()

# Should be cleared
assert orchestrator._pending_cache_guidance is None
assert orchestrator._pending_context_injection is None
```

---

## Out of Scope

- Changing the cache guidance format
- Modifying how user context is formatted
- Changing the separator format (use `\n\n---\n\n`)
- Adding new features beyond fixing the bug

---

## Dependencies

- Investigation document: `george-scratch/investigation-add-to-context-bug.md`
- Quick fix guide: `george-scratch/QUICK-FIX-GUIDE.md`
- Existing implementation: `src/logai/core/orchestrator.py`

---

## Risks & Mitigations

### Risk: Breaking existing cache guidance
**Mitigation**: Preserve exact cache guidance text, comprehensive testing

### Risk: Separator not clear enough
**Mitigation**: Use standard `---` separator that's clear and unambiguous

### Risk: Order matters (which injection comes first)
**Mitigation**: Cache guidance first (system instruction), then user context - matches priority

---

## Timeline Estimate

- Investigation: Complete (Hans)
- Design: 15 minutes (review investigation)
- Implementation: 30 minutes (simple code change)
- Testing: 30 minutes (5 test cases)
- Code Review: 15 minutes
- QA: 30 minutes (manual testing)

**Total**: ~2-3 hours

---

## Impact

**Before Fix**: User-selected logs lost when tool calls generate cached results
**After Fix**: Both cache guidance and user logs always reach the agent
**User Impact**: "Add to Context" feature works reliably in all scenarios

---

## Notes

- This is a simple but critical bug fix
- The fix is well-understood (Hans provided complete analysis)
- ~35 lines of code change (mostly preserving existing text)
- High confidence in the solution
- Should be prioritized due to user impact

---

**Next Steps**:
1. Jackie implements the fix
2. Jackie writes unit tests (5 test cases)
3. Han-Ron reviews code
4. Raoul performs QA testing
5. Deploy immediately (high-priority bug fix)
