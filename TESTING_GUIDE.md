# Quick Testing Guide for Agent Self-Direction

## Setup

```bash
cd /Users/David.Parker/src/observability-assistant

# Set up environment
export LOGAI_LLM_PROVIDER=github-copilot
export AWS_DEFAULT_REGION=us-east-1

# Optional: Adjust retry settings
export LOGAI_MAX_RETRY_ATTEMPTS=3
export LOGAI_AUTO_RETRY_ENABLED=true
export LOGAI_INTENT_DETECTION_ENABLED=true
```

## Test Scenarios

### 1. Empty Results Retry (Auto-Expand Time Range)

**Test Query:**
```
Find errors in /aws/lambda/my-function in the last 5 minutes
```

**Expected Behavior:**
- Agent searches with 5-minute window
- If empty, automatically expands to 1 hour, then 6 hours, then 24 hours
- Reports findings from expanded search
- Does NOT ask user "would you like me to expand?"

**Look For:**
- Multiple tool calls with different time ranges
- Log messages: "Injecting retry prompt" (INFO level)
- Final response mentions expanded time range

### 2. Log Group Not Found (Auto-List Alternatives)

**Test Query:**
```
Show me logs from /aws/lambda/nonexistent-function
```

**Expected Behavior:**
- First fetch_logs fails with "log group not found"
- Agent automatically calls list_log_groups
- Suggests similar log groups or alternatives
- May try one of the suggestions automatically

**Look For:**
- Tool call sequence: fetch_logs → list_log_groups
- Log message: "Detected log group not found error"
- Response includes available alternatives

### 3. Intent Without Action (Nudge to Execute)

**Test Query:**
```
Can you search for errors?
```

**Expected Behavior:**
- Agent might initially respond "I'll search for errors"
- System detects intent without action
- Nudges agent to execute immediately
- Agent then actually calls fetch_logs or search_logs

**Look For:**
- Initial text response without tool call
- Log message: "Detected intent without action, nudging agent"
- Follow-up tool call
- Final response with actual results

### 4. Premature Giving Up Prevention

**Test Query:**
```
Find warnings in /aws/lambda/low-traffic-function in the last 10 minutes
```

**Expected Behavior:**
- First search returns empty
- If agent tries to give up ("No logs found...")
- System encourages trying broader search
- Agent expands time range and tries again

**Look For:**
- Log message: "Detected premature giving up"
- Multiple search attempts
- Agent persistence before final report

## Quick Validation Tests

### Test 1: Intent Detector
```bash
python3 << 'EOF'
from src.logai.core.intent_detector import IntentDetector

# Should detect intent
result = IntentDetector.detect_intent("I'll search the logs now")
assert result is not None, "Should detect search intent"
print("✓ Intent detection works")

# Should detect giving up
giving_up = IntentDetector.detect_premature_giving_up("No logs were found")
assert giving_up == True, "Should detect giving up"
print("✓ Giving up detection works")
EOF
```

### Test 2: Retry State
```bash
python3 << 'EOF'
from src.logai.core.orchestrator import RetryState

state = RetryState()
assert state.should_retry(3) == True, "Should allow retry"
state.record_attempt("tool", {}, "strategy")
assert state.attempts == 1, "Should track attempts"
print("✓ Retry state works")
EOF
```

### Test 3: Configuration
```bash
python3 << 'EOF'
from src.logai.config.settings import LogAISettings

settings = LogAISettings(
    llm_provider='ollama',
    aws_region='us-east-1'
)
assert settings.max_retry_attempts == 3, "Default retry limit"
assert settings.auto_retry_enabled == True, "Auto-retry enabled"
print("✓ Settings configured")
EOF
```

### Test 4: Unit Tests
```bash
# Run all orchestrator tests
python3 -m pytest tests/unit/test_orchestrator.py -v

# Run only self-direction tests
python3 -m pytest tests/unit/test_orchestrator.py -k "retry or intent" -v
```

## Observability

### Log Monitoring

Watch for these log messages during testing:

```bash
# In a separate terminal, tail logs if configured
tail -f ~/.logai/logs/logai.log
```

**Key Log Messages:**
- `Injecting retry prompt` - Retry logic triggered
- `Detected intent without action` - Agent nudged to act
- `Detected premature giving up` - Persistence enforcement
- `Detected empty results` - Empty result analysis
- `Detected log group not found error` - Error recovery

### Debug Mode

For more verbose logging:
```bash
export LOGAI_LOG_LEVEL=DEBUG
logai
```

## Feature Flag Testing

### Disable Auto-Retry
```bash
export LOGAI_AUTO_RETRY_ENABLED=false
logai
```
**Expected:** Agent works normally but won't automatically retry on empty results

### Disable Intent Detection
```bash
export LOGAI_INTENT_DETECTION_ENABLED=false
logai
```
**Expected:** Agent works normally but won't detect intent-without-action

### Reduce Retry Limit
```bash
export LOGAI_MAX_RETRY_ATTEMPTS=1
logai
```
**Expected:** Agent retries only once before giving up

## Success Criteria

✅ **Auto-Retry Working:**
- Empty results trigger automatic retry with different parameters
- Agent doesn't ask user before retrying
- Sees 2-3 attempts before giving up

✅ **Intent Detection Working:**
- Agent doesn't just say "I'll do X" without doing X
- Follow-up tool calls happen automatically
- No need for user to repeat request

✅ **Persistence Working:**
- Agent tries multiple approaches
- Doesn't give up after first empty result
- Expands search parameters intelligently

✅ **Safety Working:**
- Retries stop at configured limit
- No infinite loops
- Graceful error handling

## Common Issues & Solutions

### Issue: Agent still gives up immediately
**Solution:** Check that `LOGAI_AUTO_RETRY_ENABLED=true`

### Issue: Too many retries
**Solution:** Adjust `LOGAI_MAX_RETRY_ATTEMPTS` to lower value

### Issue: Not detecting intent
**Solution:** Check that `LOGAI_INTENT_DETECTION_ENABLED=true`

### Issue: Logs not showing retry messages
**Solution:** Set `LOGAI_LOG_LEVEL=INFO` or `DEBUG`

## Performance Verification

Expected overhead:
- **Latency:** <100ms per retry decision
- **Extra API calls:** 1-3 additional LLM calls for retries
- **Memory:** Negligible (small state objects)
- **Token usage:** +200-500 tokens per retry prompt

Monitor:
```bash
# Watch API call count
# Watch response times
# Check token usage in LLM provider dashboard
```

## Rollback Plan

If issues arise, disable features:
```bash
export LOGAI_AUTO_RETRY_ENABLED=false
export LOGAI_INTENT_DETECTION_ENABLED=false
```

System will fall back to original behavior gracefully.

---

**Quick Start Command:**
```bash
export LOGAI_LLM_PROVIDER=github-copilot && \
export AWS_DEFAULT_REGION=us-east-1 && \
export LOGAI_LOG_LEVEL=INFO && \
logai
```

Then try: "Find errors in my Lambda functions from the last 5 minutes"
