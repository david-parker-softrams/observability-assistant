# Issues & Recommendations for Jackie

**Date:** February 11, 2026  
**Reviewer:** Billy  
**Overall Assessment:** ✅ Approved for production (with recommended improvements)

---

## Critical Issues (Must Fix Before Production)

**NONE** - Code is production-ready as-is! ✅

---

## High Priority Recommendations (Should Address Before Production)

### 1. Add Metrics Instrumentation
**Location:** `src/logai/core/orchestrator.py`  
**Severity:** Medium  
**Estimated Effort:** 2-3 hours

**Issue:** No metrics tracking for retry behavior. We need observability into:
- Retry attempt counts
- Retry success/failure rates  
- Latency added by retry logic
- Which retry strategies are most effective

**Recommendation:**
```python
# Add after line 408 in orchestrator.py
from logai.metrics import metrics  # or whatever metrics library you use

# In _chat_complete, after successful retry:
metrics.increment("agent.retry.success", tags={
    "reason": retry_reason,
    "attempts": retry_state.attempts
})

# After max retries reached:
metrics.increment("agent.retry.exhausted", tags={
    "reason": retry_reason,
    "attempts": retry_state.attempts
})

# Track latency:
with metrics.timer("agent.retry.duration"):
    # retry logic
```

**Why:** Essential for monitoring health of retry system in production.

---

### 2. Add Exponential Backoff Between Retries
**Location:** `src/logai/core/orchestrator.py`  
**Severity:** Medium  
**Estimated Effort:** 1 hour

**Issue:** Retries happen immediately without delay. Could hit API rate limits with rapid-fire retries.

**Recommendation:**
```python
# Add import
import asyncio

# In _chat_complete, before injecting retry prompt (around line 395):
if retry_state.attempts > 0:
    # Exponential backoff: 1s, 2s, 4s
    delay = min(2 ** (retry_state.attempts - 1), 4)
    await asyncio.sleep(delay)
    logger.info(f"Retry backoff delay: {delay}s")
```

**Why:** Prevents hammering APIs during retries, reduces rate limit risk.

---

## Medium Priority Recommendations (Consider for V1.1)

### 3. Tune Logging Levels
**Location:** `src/logai/core/orchestrator.py` lines 401-460  
**Severity:** Low  
**Estimated Effort:** 15 minutes

**Issue:** All retry attempts logged at INFO level. Could be noisy in production.

**Recommendation:**
```python
# Change line 401 from:
logger.info("Injecting retry prompt", ...)

# To:
logger.debug("Injecting retry prompt", ...)

# Keep INFO for final outcomes:
if retry_state.attempts == self.settings.max_retry_attempts:
    logger.info("Max retry attempts reached", ...)
```

**Why:** Reduces log noise while preserving important information.

---

### 4. Externalize Retry Prompts
**Location:** `src/logai/core/orchestrator.py` lines 93-116  
**Severity:** Low  
**Estimated Effort:** 2 hours

**Issue:** Retry prompts hardcoded in class. Difficult to tune without code changes.

**Recommendation:**
```python
# Move RETRY_PROMPTS to settings.py or separate prompts.yaml
# Load at runtime, allow override via config
```

**Why:** Easier prompt tuning for different models/use cases.

---

### 5. Add Streaming Path Integration Tests
**Location:** `tests/integration/`  
**Severity:** Medium  
**Estimated Effort:** 2-3 hours

**Issue:** `_chat_stream` method has similar retry logic but less test coverage.

**Recommendation:**
```python
# Add test file: tests/integration/test_retry_streaming.py
# Mirror test_agent_retry_behavior.py but use streaming API
```

**Why:** Ensure feature parity between streaming and non-streaming paths.

---

### 6. Add Conversation History Trimming
**Location:** `src/logai/core/orchestrator.py`  
**Severity:** Medium  
**Estimated Effort:** 3-4 hours

**Issue:** System retry messages accumulate in history. Could cause context window issues in long conversations.

**Recommendation:**
```python
# After successful retry resolution:
def _trim_retry_messages(self, messages: list) -> list:
    """Remove resolved retry system messages."""
    # Keep only the last retry message, remove earlier ones
    # Or remove all retry messages after successful resolution
    pass
```

**Why:** Prevents context window overflow in extended conversations.

---

## Low Priority (Future Enhancements)

### 7. Context Window Monitoring
**Issue:** No explicit token counting for conversation history.  
**When:** Post-MVP, if context issues arise in production.

### 8. Retry Strategy Queue
**Issue:** LLM-based strategy selection is non-deterministic.  
**When:** If retry effectiveness is inconsistent in production.

### 9. Intent Detection Tuning UI
**Issue:** No easy way to adjust confidence thresholds or patterns.  
**When:** After gathering production data on false positives/negatives.

---

## Things That Are Great (Don't Change!)

✅ **System Prompt Design** - The "Action, Don't Just Describe" section is perfect  
✅ **RetryState Architecture** - Clean, simple, effective  
✅ **Test Coverage** - 39 tests with 93-95% coverage is excellent  
✅ **Error Handling** - Graceful degradation is well-implemented  
✅ **Feature Flags** - Critical for safe rollout  
✅ **Documentation** - Docstrings are comprehensive and clear  

---

## Questions for Discussion

1. **Metrics Library**: What metrics/observability system should we use? (Prometheus? Datadog? Built-in?)

2. **Streaming Tests**: Should we prioritize streaming tests for MVP or defer to V1.1?

3. **Prompt Tuning**: Do we expect to need prompt tuning post-deployment? If so, externalization might be MVP.

4. **Rate Limits**: Do we have existing rate limit handling we should integrate with for backoff?

---

## Summary

You've done **excellent work**, Jackie! The code is production-ready with only minor improvements suggested. The implementation is clean, well-tested, and thoughtfully designed.

**Recommended Action Plan:**
1. Add metrics instrumentation (2-3 hours)
2. Add exponential backoff (1 hour)  
3. Adjust logging levels (15 minutes)
4. **Then deploy to staging** ✅

The other items can be addressed in V1.1 based on production feedback.

Great job! 👏
