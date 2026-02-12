# Tool Sidebar - Manual Testing Guide

**For**: George, Jackie, or other team members  
**Purpose**: Quick manual testing checklist for sidebar functionality  
**Time Required**: 15-20 minutes

---

## Pre-Testing Setup

```bash
# Set environment variables
export LOGAI_LLM_PROVIDER=github-copilot
export LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
export AWS_PROFILE=bosc-dev
export AWS_DEFAULT_REGION=us-east-1
export LOGAI_LOG_LEVEL=INFO

# Launch LogAI
logai
```

---

## Test Checklist

### ✅ Test 1: Initial State (1 min)

**Action**: Just launched the app

**Verify**:
- [ ] Sidebar visible on right side of screen
- [ ] Shows "TOOL CALLS" header
- [ ] Shows empty state: "No tool calls yet.\nAsk a question to see\nthe agent's tools here."
- [ ] Width is approximately 28 columns (about 1/3 of a 100-column terminal)
- [ ] Messages area on left takes remaining space

**Expected Layout**:
```
┌─────────────────────────────────┬──────────────────────┐
│  Messages (left)                │  TOOL CALLS (right)  │
│                                 │  ────────────────    │
│  [Welcome message]              │  No tool calls yet.  │
│                                 │  Ask a question...   │
│                                 │                      │
└─────────────────────────────────┴──────────────────────┘
```

---

### ✅ Test 2: Toggle Off (1 min)

**Action**: Type `/tools` and press Enter

**Verify**:
- [ ] Sidebar disappears
- [ ] Confirmation message: "Tool calls sidebar hidden."
- [ ] Messages area expands to full width
- [ ] Input still works normally

---

### ✅ Test 3: Toggle On (1 min)

**Action**: Type `/tools` again and press Enter

**Verify**:
- [ ] Sidebar reappears
- [ ] Confirmation message: "Tool calls sidebar shown."
- [ ] Still shows empty state (no tool calls made yet)
- [ ] Messages area shrinks back to left side

---

### ✅ Test 4: Help Command (30 sec)

**Action**: Type `/help` and press Enter

**Verify**:
- [ ] Help text includes: `[cyan]/tools[/cyan] - Toggle tool calls sidebar`

---

### ✅ Test 5: Simple Tool Call (2 min)

**Action**: Type: `What log groups exist?`

**Verify During Execution**:
- [ ] Tool call appears immediately in sidebar
- [ ] Shows tool name: `list_log_groups`
- [ ] Status progresses: ◯ (pending) → ⏳ (running) → ✓ (success)
- [ ] Timestamp appears: "Time: HH:MM:SS"

**Verify After Completion**:
- [ ] Duration appears: "Duration: Xms"
- [ ] Result shows: "N groups" (where N is the count)
- [ ] Tool call entry is expandable (click to see details)

**Example**:
```
✓ list_log_groups
  Status: success
  Time: 14:32:05
  Duration: 245ms
  Result: 12 groups
```

---

### ✅ Test 6: Multi-Step Query (3 min)

**Action**: Type: `Find errors in my Lambda logs from the last hour`

**Verify**:
- [ ] Multiple tool calls appear
- [ ] Each in chronological order (oldest at top)
- [ ] Each shows progression: ◯ → ⏳ → ✓
- [ ] Sidebar auto-scrolls to show latest tool call
- [ ] All tools complete with ✓ (or ✗ if errors)

**Expected Sequence** (may vary):
1. `list_log_groups` → ✓
2. `query_logs` → ✓
3. `get_log_events` → ✓ (if needed)

---

### ✅ Test 7: Complex Query (3 min)

**Action**: Type: `Analyze error patterns across all log groups`

**Verify**:
- [ ] Many tool calls (5-10+)
- [ ] Sidebar handles rapid updates smoothly
- [ ] No UI lag or stuttering
- [ ] Auto-scroll keeps latest visible
- [ ] Can scroll back to see older calls

---

### ✅ Test 8: Parameters Display (2 min)

**Action**: Expand a tool call node by clicking on it

**Verify**:
- [ ] Can see "Args: ..." line
- [ ] Arguments show as key=value pairs
- [ ] Long arguments truncated with "..."
- [ ] If more than 3 params, shows "+N more"

**Example**:
```
Args: log_group=/aws/lambda/my-func..., start_time=2026-01-...
```

---

### ✅ Test 9: Results Display (2 min)

**Action**: Look at completed tool calls

**Verify Pattern Recognition**:
- [ ] Count pattern: `count: 42`
- [ ] Events pattern: `100 events`
- [ ] Log groups pattern: `12 groups`
- [ ] Success pattern: `success` or `failed`
- [ ] Large results truncated with "..."

---

### ✅ Test 10: Error Handling (2 min)

**Action**: Type: `Show me logs from /invalid/log/group/name`

**Verify**:
- [ ] Tool call shows ✗ icon
- [ ] Status: error
- [ ] Error message displayed (truncated if long)
- [ ] Duration still calculated
- [ ] Red/error color applied

**Example**:
```
✗ query_logs
  Status: error
  Time: 14:35:12
  Duration: 156ms
  Error: Log group not found
```

---

### ✅ Test 11: History Limit (2 min)

**Action**: Make many queries to accumulate 25+ tool calls

**Verify**:
- [ ] Sidebar keeps only most recent 20 tool calls
- [ ] Oldest calls drop off automatically
- [ ] No performance degradation
- [ ] Memory doesn't grow unbounded

**How to Test**: Ask several multi-step queries in succession.

---

### ✅ Test 12: Toggle Preserves History (1 min)

**Action**: 
1. Make a query (get some tool calls)
2. Type `/tools` to hide sidebar
3. Type `/tools` to show sidebar again

**Verify**:
- [ ] Previous tool calls still visible
- [ ] History preserved across toggle
- [ ] All details intact (status, duration, etc.)

---

### ✅ Test 13: Terminal Resize (2 min)

**Action**: Resize terminal window to different widths:
- 80 columns (narrow)
- 100 columns (comfortable)
- 120+ columns (wide)

**Verify**:
- [ ] Layout adapts gracefully at all sizes
- [ ] No overlap between messages and sidebar
- [ ] Text wraps appropriately
- [ ] Sidebar maintains min-width (24 columns)

**Note**: On very narrow terminals (< 100 cols), layout may be cramped. This is expected for MVP. Phase 4 will add auto-hide.

---

### ✅ Test 14: Streaming Responses (2 min)

**Action**: Make a query and watch the response stream

**Verify**:
- [ ] Message text streams character by character
- [ ] Tool calls update independently in sidebar
- [ ] No blocking or freezing
- [ ] Both areas update smoothly

---

### ✅ Test 15: Input Functionality (1 min)

**Action**: With sidebar visible, test input box

**Verify**:
- [ ] Can type normally
- [ ] Enter submits message
- [ ] Cursor behavior correct
- [ ] No interference from sidebar

---

## Optional: Stress Tests

### Stress Test 1: Rapid Queries
Type multiple queries in quick succession without waiting for responses.

**Verify**:
- [ ] All tool calls appear
- [ ] No crashes or hangs
- [ ] UI remains responsive

### Stress Test 2: Long Session
Keep app running for 30+ minutes with occasional queries.

**Verify**:
- [ ] No memory leaks
- [ ] Performance stays consistent
- [ ] Tool call limit (20) enforced throughout

---

## Bug Reporting Template

If you find a bug, report it with this format:

```markdown
**Bug**: [Short description]
**Severity**: Critical / High / Medium / Low
**Steps to Reproduce**:
1. Step 1
2. Step 2
3. Step 3

**Expected**: [What should happen]
**Actual**: [What actually happened]
**Screenshot**: [If applicable]
```

---

## Quick Pass/Fail Criteria

✅ **PASS** if:
- All 15 core tests pass
- No crashes or errors
- UI is responsive and smooth
- Feature works as expected

❌ **FAIL** if:
- Any critical functionality broken
- Frequent crashes or hangs
- Sidebar doesn't display tool calls
- Toggle command doesn't work

---

## After Testing

Report results to:
- Raoul (QA) - For test verification
- George (PM) - For sign-off
- Jackie (Dev) - For any bug fixes

**Congratulations!** You've completed manual testing for the tool sidebar. 🎉

---

*Testing Guide v1.0 - February 11, 2026*
