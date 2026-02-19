# End-to-End Test Script: Intelligent Context Management System

**QA Engineer:** Raoul
**Date:** February 12, 2026
**Test Environment:** LogAI v1.0 (Dev)
**Duration:** 2-3 hours

---

## Prerequisites

### Environment Setup

1. **AWS CloudWatch Access**
   - Active AWS account with CloudWatch Logs
   - At least 3-5 log groups with data
   - Log groups with varying data volumes (small, medium, large)

2. **LogAI Configuration**
   ```bash
   # Copy and configure .env
   cp .env.example .env

   # Required settings:
   LOGAI_LLM_PROVIDER=github-copilot  # or anthropic/openai
   LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
   AWS_DEFAULT_REGION=us-east-1
   AWS_PROFILE=your-profile

   # Context management settings (use defaults)
   LOGAI_ENABLE_RESULT_CACHING=true
   LOGAI_ENABLE_HISTORY_PRUNING=true
   LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000
   ```

3. **Authentication**
   ```bash
   # If using GitHub Copilot
   logai auth login

   # Verify AWS credentials
   aws sts get-caller-identity --profile your-profile
   ```

4. **Installation**
   ```bash
   cd /Users/David.Parker/src/observability-assistant
   pip install -e .
   ```

### Test Data Preparation

Identify log groups for testing:
- **Small log group:** <100 events/hour
- **Medium log group:** 100-500 events/hour
- **Large log group:** >1000 events/hour

Record these for consistent testing:
```
SMALL_LOG_GROUP="/aws/lambda/small-function"
MEDIUM_LOG_GROUP="/aws/lambda/medium-function"
LARGE_LOG_GROUP="/ecs/production-api"
```

---

## Test Scenarios

### Scenario 1: Normal Operation (Context 0-70%)

**Objective:** Verify basic functionality and status bar display in normal usage

**Steps:**

1. **Start LogAI fresh**
   ```bash
   logai
   ```

2. **Observe initial state**
   - Status bar should show: `Context: 0%` in **green**
   - No toast notifications

3. **Send 5 simple queries**
   ```
   Query 1: "What log groups are available?"
   Query 2: "List log groups"
   Query 3: "What's in /aws/lambda/my-function?"
   Query 4: "Show me recent logs"
   Query 5: "What time range do you have data for?"
   ```

4. **Monitor status bar** after each query
   - Context percentage should increase gradually
   - Should remain **green** (<70%)
   - Example progression: 0% → 12% → 18% → 25% → 32%

**Expected Results:**

✅ Status bar displays context percentage
✅ Color remains green throughout
✅ No toast notifications (normal operation)
✅ All queries execute successfully
✅ No errors in console output

**Pass Criteria:** All checkmarks above

---

### Scenario 2: Large Result Caching (>10,000 tokens)

**Objective:** Verify automatic caching of large CloudWatch results

**Setup:** Use large log group with high event volume

**Steps:**

1. **Start LogAI fresh**
   ```bash
   logai
   ```

2. **Execute query for large result**
   ```
   Query: "Show me all ERROR logs from [LARGE_LOG_GROUP] in the last 24 hours"
   ```

   Alternative if first doesn't trigger:
   ```
   Query: "Get 1000 log events from [LARGE_LOG_GROUP] from the last hour"
   ```

3. **Observe toast notification**
   - Should appear within 1-2 seconds of result arrival
   - Format: "Cached large result: XXX events, YYYYY tokens → ZZZZ token summary"

4. **Check agent response**
   - Agent should acknowledge the cached result
   - Should provide analysis based on summary
   - Response should mention ability to fetch more details

5. **Test FetchCachedResultTool**
   ```
   Follow-up query: "Show me the first 50 events from that cached result"
   ```
   OR
   ```
   Follow-up query: "Search the cached results for [specific pattern]"
   ```

6. **Verify agent can access cached data**
   - Agent should successfully retrieve chunks
   - Should be able to filter/search cached data
   - Should not re-query CloudWatch

**Expected Results:**

✅ Toast notification appears: "Cached large result..."
✅ Context usage stays <70% (doesn't jump to 90%+)
✅ Agent receives summary instead of full result
✅ Agent can use FetchCachedResultTool successfully
✅ Response quality remains high
✅ No errors or warnings about context overflow

**Measurements:**

- Token count before caching: _______ tokens
- Token count after caching: _______ tokens
- Compression ratio: _______ %
- Time to cache: _______ ms

**Pass Criteria:** All checkmarks + compression ratio >80%

---

### Scenario 3: History Pruning (Context 71-85%+)

**Objective:** Verify automatic history pruning when context fills up

**Setup:** Requires sustained interaction to fill context window

**Steps:**

1. **Start LogAI fresh**
   ```bash
   logai
   ```

2. **Execute extended conversation** (aim for 50+ messages)

   **Round 1 (10 queries):**
   ```
   "List all log groups"
   "What's in [LOG_GROUP_1]?"
   "Show me errors from [LOG_GROUP_1] last 6 hours"
   "What about warnings?"
   "Analyze the error patterns"
   "Are there any critical issues?"
   "What's the error rate?"
   "Show me the stack traces"
   "What caused these errors?"
   "Any solutions?"
   ```

   **Round 2 (10 queries):**
   ```
   "Now check [LOG_GROUP_2]"
   "Show me all logs from last hour"
   "Filter for ERROR level"
   "What about INFO logs?"
   "Count the events by level"
   "Show me unique error messages"
   "Group by timestamp"
   "What's the trend?"
   "Compare to yesterday"
   "Any anomalies?"
   ```

   **Round 3 (10 queries):**
   ```
   "Check [LOG_GROUP_3]"
   "Query last 24 hours"
   "Show distribution"
   "Filter by pattern"
   "Count occurrences"
   "What's the max?"
   "What's the average?"
   "Show outliers"
   "Explain the pattern"
   "Root cause?"
   ```

   **Continue until context reaches 85%+**

3. **Monitor status bar color changes**
   - Record when it changes from green → yellow (71%)
   - Record when it changes from yellow → red (86%)

4. **Watch for pruning toast notification**
   - Should appear when utilization hits ~85%
   - Format: "Pruned X old messages to maintain context (freed ~Y tokens)"

5. **Verify conversation continuity**
   - After pruning, send follow-up: "What were we just discussing?"
   - Agent should remember recent context
   - Agent should NOT remember very old messages

6. **Check pruning effectiveness**
   - Context should drop from 85-90% → 60-70%
   - Status bar should update accordingly

**Expected Results:**

✅ Status bar changes to **yellow** at 71%
✅ Status bar changes to **red** at 86%
✅ Toast notification: "Pruned X old messages..."
✅ Conversation continues smoothly after pruning
✅ Agent maintains context of recent messages
✅ Oldest messages are removed (FIFO strategy)
✅ Context drops to sustainable level (~60-70%)

**Measurements:**

- Context before pruning: _______ %
- Messages pruned: _______
- Tokens freed: _______
- Context after pruning: _______ %
- Time to prune: _______ ms

**Pass Criteria:** All checkmarks + context drops by at least 15%

---

### Scenario 4: Multiple Large Results

**Objective:** Verify system handles multiple large results gracefully

**Steps:**

1. **Start LogAI fresh**
   ```bash
   logai
   ```

2. **Execute 5 queries returning large results**
   ```
   Query 1: "Show me all errors from [LARGE_LOG_GROUP_1] last 24h"
   Query 2: "Get warnings from [LARGE_LOG_GROUP_2] last 12h"
   Query 3: "Show INFO logs from [LARGE_LOG_GROUP_3] last 6h"
   Query 4: "Query [LARGE_LOG_GROUP_4] for exceptions"
   Query 5: "Get all events from [LARGE_LOG_GROUP_5] last 1h"
   ```

3. **Observe caching notifications**
   - Should get toast for each large result
   - Each should show event count and token savings

4. **Verify context doesn't overflow**
   - Context usage should stay <95%
   - Multiple pruning events may occur (acceptable)

5. **Test accessing cached results**
   ```
   "Show me details from the first cached result"
   "Search the second result for [pattern]"
   "Compare events from third and fourth results"
   ```

**Expected Results:**

✅ Each large result triggers caching notification
✅ Context usage stays under 95%
✅ All results accessible (summary or via FetchCachedResultTool)
✅ No errors or crashes
✅ Agent can work with all cached results
✅ System remains stable and responsive

**Measurements:**

- Results cached: _______
- Total events cached: _______
- Total tokens saved: _______
- Peak context usage: _______ %

**Pass Criteria:** All checkmarks + peak context <95%

---

### Scenario 5: Stress Test (Long Conversation + Large Results)

**Objective:** Verify system stability under heavy sustained usage

**Warning:** This test takes 30-60 minutes

**Steps:**

1. **Start LogAI fresh**
   ```bash
   logai
   ```

2. **Simulate heavy usage**
   - Execute 100+ messages over 30-60 minutes
   - Mix of:
     - 20 simple queries (list, describe, etc.)
     - 20 medium queries (filtered searches)
     - 10 large queries (1000+ events)
     - 50 analytical questions (trends, patterns, root cause)

3. **Monitor throughout**
   - Context usage progression
   - Number of pruning events
   - Number of caching events
   - Response latency
   - Memory usage
   - UI responsiveness

4. **Key observations**
   - How many times does pruning occur?
   - Does context stabilize or keep growing?
   - Any degradation in response quality?
   - Any UI lag or freezing?

**Expected Results:**

✅ Multiple pruning events occur automatically
✅ Context never exceeds 95%
✅ System remains stable (no crashes)
✅ Agent maintains coherent conversation
✅ Response quality remains acceptable
✅ UI remains responsive (no lag)
✅ Memory usage stable (no leaks)

**Measurements:**

- Total messages: _______
- Pruning events: _______
- Caching events: _______
- Peak context: _______ %
- Average response latency: _______ ms
- Peak memory usage: _______ MB
- UI lag incidents: _______

**Pass Criteria:** All checkmarks + <3 UI lag incidents

---

### Scenario 6: Edge Cases

**Objective:** Test boundary conditions and error handling

#### Test 6A: Empty Conversation

**Steps:**
1. Start LogAI
2. Immediately check status bar

**Expected:**
✅ Status bar shows `Context: 0%` in green

---

#### Test 6B: Single Message

**Steps:**
1. Start LogAI
2. Send one message: "Hello"
3. Check status bar

**Expected:**
✅ Context updates to small percentage (e.g., 5-10%)
✅ Color remains green

---

#### Test 6C: Rapid Queries

**Steps:**
1. Start LogAI
2. Send 10 queries as fast as possible
3. Observe UI behavior

**Expected:**
✅ No UI flicker or lag
✅ Throttling prevents rapid updates (max 1/sec)
✅ All queries execute successfully

---

#### Test 6D: Extremely Large Single Result

**Steps:**
1. Query for maximum CloudWatch result (1000 events, very verbose logs)
2. Observe caching behavior

**Expected:**
✅ Result cached automatically
✅ Summary provided to agent
✅ No context overflow
✅ Agent can fetch chunks

---

#### Test 6E: Context at 100%

**Steps:**
1. Disable pruning temporarily (if possible, or ignore)
2. Fill context to maximum
3. Observe behavior

**Expected:**
✅ System prunes aggressively
OR
✅ Warning notification to user
✅ No crash or data loss

---

#### Test 6F: Cache Directory Issues

**Steps:**
1. Make cache directory read-only:
   ```bash
   chmod 444 ~/.logai/cache/results
   ```
2. Trigger large result caching
3. Observe error handling

**Expected:**
✅ Warning toast notification
✅ System continues working (graceful degradation)
✅ Error logged to console
✅ Full result used instead (may fill context)

**Cleanup:**
```bash
chmod 755 ~/.logai/cache/results
```

---

## Performance Testing

### Latency Measurements

For each scenario, measure:

| Metric | Target | Actual | Pass/Fail |
|--------|--------|--------|-----------|
| Token counting overhead | <1ms | _____ ms | ☐ |
| Cache storage time | <50ms | _____ ms | ☐ |
| Cache retrieval time | <100ms | _____ ms | ☐ |
| Pruning execution time | <20ms | _____ ms | ☐ |
| Status bar update time | <5ms | _____ ms | ☐ |
| Toast notification time | <5ms | _____ ms | ☐ |

### Resource Utilization

Monitor throughout testing:

| Resource | Baseline | Peak | Acceptable? |
|----------|----------|------|-------------|
| CPU usage | _____ % | _____ % | ☐ |
| Memory usage | _____ MB | _____ MB | ☐ |
| Disk I/O (cache) | _____ KB/s | _____ KB/s | ☐ |
| Network I/O (AWS) | _____ KB/s | _____ KB/s | ☐ |

**Tools:**
```bash
# Monitor CPU/Memory
top -pid $(pgrep -f logai)

# Monitor disk
iostat -d 5

# Monitor network
nettop -P -L 1
```

---

## Test Log Template

For each test scenario, record:

```
## Scenario X: [Name]

**Date/Time:**
**Tester:**
**Environment:**

### Execution

**Steps Completed:**
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
...

**Observations:**
-
-
-

**Screenshots:**
- [Attach relevant screenshots]

### Results

**Pass/Fail:**
**Expected Results:** X/X met
**Performance Metrics:**
- Metric 1: _____
- Metric 2: _____

**Issues Found:**
- Issue 1: [Description, Severity]
- Issue 2: [Description, Severity]

**Notes:**
-
```

---

## Issue Classification

### Severity Levels

- **Critical:** System crash, data loss, complete feature failure
- **High:** Major functionality broken, workaround difficult
- **Medium:** Feature partially working, acceptable workaround exists
- **Low:** Minor issue, cosmetic, documentation

### Issue Template

```
## Issue #X: [Short Description]

**Severity:** Critical/High/Medium/Low
**Scenario:** [Which test scenario]
**Component:** [Context tracking/Caching/Pruning/UI]

**Description:**
[Detailed description of the issue]

**Steps to Reproduce:**
1.
2.
3.

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happened]

**Environment:**
- OS:
- Python:
- LogAI version:
- LLM provider:

**Logs/Screenshots:**
[Attach relevant artifacts]

**Workaround:**
[If any]

**Blocker:**
[Yes/No - blocks production deployment?]
```

---

## Success Criteria Summary

To **PASS** comprehensive QA testing:

### Core Functionality (Must Pass All)

- ✅ All 6 test scenarios pass
- ✅ No critical or high-severity bugs
- ✅ Performance targets met:
  - Token counting: <1ms
  - Caching: <50ms storage, <100ms retrieval
  - Pruning: <20ms
  - UI updates: <5ms
- ✅ Resource usage acceptable:
  - CPU: <10% average
  - Memory: Stable (no leaks)
  - UI: No lag or freezing

### User Experience (Must Pass 4/5)

- ☐ Status bar updates clearly visible
- ☐ Toast notifications helpful and non-intrusive
- ☐ No disruption to normal workflow
- ☐ Graceful error handling
- ☐ System feels responsive and stable

### Edge Cases (Must Pass 5/6)

- ☐ Empty conversation
- ☐ Single message
- ☐ Rapid queries
- ☐ Extremely large result
- ☐ Context at 100%
- ☐ Cache directory issues

---

## Sign-off

**QA Engineer:** _____________________ **Date:** __________

**Status:** ☐ PASS - Ready for production ☐ CONDITIONAL PASS - Minor issues ☐ FAIL - Blockers found

**Blocker Issues:** _______

**Recommendations:**
-
-
-

**Next Steps:**
-
