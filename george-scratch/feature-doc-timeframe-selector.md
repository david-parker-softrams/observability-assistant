# Log Preview Time Frame Selector

**Feature Guide for LogAI Users**

---

## Overview

The **Time Frame Selector** lets you choose how far back in time to look when previewing logs from a log group. Instead of always viewing the last 15 minutes, you can now select from four time windows: 15 minutes, 1 hour, 8 hours, or 24 hours.

### Why This Matters

Different situations call for different time windows:
- **Quick recent checks** need a narrow window (15 minutes)
- **Troubleshooting ongoing issues** benefit from recent context (1 hour)
- **Trend analysis** requires broader visibility (8 hours)
- **Daily pattern review** needs full-day coverage (24 hours)

With the time frame selector, you can switch between these views instantly without closing and reopening the log preview.

---

## What You'll See

When you double-click a log group in the sidebar to preview its logs, you'll see a new row of time frame buttons at the top of the preview window:

```
┌─────────────────────────────────────────────────────────────┐
│  Log Preview: /aws/lambda/my-function                       │
├─────────────────────────────────────────────────────────────┤
│  Time Frame:  [●15 min][ 1 hour ][ 8 hours ][ 24 hours ]   │  ← New!
├─────────────────────────────────────────────────────────────┤
│  [Select All] [Deselect All]              0 of 10 selected  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [✓] 2026-02-18 14:32:15.123                            │ │
│  │     Error processing payment for order #12345          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ [ ] 2026-02-18 14:31:45.789                            │ │
│  │     Request timeout after 30s                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ... (more log entries)                                     │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│              [Add Selected to Context]         [Close]      │
└─────────────────────────────────────────────────────────────┘
```

The currently selected time frame is **highlighted** (shown with a filled circle ● above).

---

## How to Use the Time Frame Selector

### Opening the Log Preview

1. Make sure the log groups sidebar is visible (press `/logs` if it's hidden)
2. **Double-click** any log group name in the sidebar
3. The log preview window opens, showing the most recent logs from the **last 15 minutes** (default)

### Changing the Time Frame

1. Look at the **Time Frame** row at the top of the preview window
2. Click any of the four time frame buttons:
   - **15 min** - Last 15 minutes
   - **1 hour** - Last 60 minutes
   - **8 hours** - Last 8 hours
   - **24 hours** - Last 24 hours
3. The preview automatically refreshes to show logs from your selected time window

### What Happens When You Change Time Frames

When you click a different time frame button:

1. **Loading indicator appears** - "Loading recent log entries..."
2. **Previous logs clear** - Any selections you made are reset
3. **New logs load** - LogAI fetches logs from the new time window
4. **Results display** - You see the most recent 10 entries from that window
5. **Counter resets** - Selection counter shows "0 of N selected"

This all happens automatically in 1-2 seconds.

---

## Time Frame Options Explained

### 15 Minutes (Default)

**When to use:**
- Quick checks of very recent activity
- Monitoring real-time issues
- Verifying recent deployments
- Fastest loading time

**Example scenarios:**
- "Did my deployment just succeed?"
- "Is the service currently throwing errors?"
- "What happened in the last few minutes?"

**Typical load time:** < 1 second

---

### 1 Hour

**When to use:**
- Recent troubleshooting
- Understanding current issues
- Checking recent patterns
- Balances recency with context

**Example scenarios:**
- "What errors occurred this hour?"
- "Is this timeout issue ongoing?"
- "What changed since my last check?"

**Typical load time:** 1-2 seconds

---

### 8 Hours

**When to use:**
- Trend analysis during business hours
- Understanding daily patterns
- Investigating recurring issues
- Broader context for troubleshooting

**Example scenarios:**
- "What's the error rate today?"
- "Are there any unusual patterns this shift?"
- "How often did this warning appear today?"

**Typical load time:** 1-3 seconds

---

### 24 Hours

**When to use:**
- Full daily pattern review
- Comparing day vs night activity
- Understanding daily cycles
- Complete context for investigations

**Example scenarios:**
- "What happened yesterday?"
- "What's the daily error pattern?"
- "When did this issue first appear today?"

**Typical load time:** 2-4 seconds

---

## Visual Guide

### Button States

The time frame buttons have three visual states:

**1. Selected (Active)**
```
[●15 min]  ← Highlighted with filled background
```
This is your current time window. This button appears with a primary color highlight.

**2. Not Selected (Available)**
```
[ 1 hour ]  ← Normal button appearance
```
Click to switch to this time window.

**3. Hover (Mouse Over)**
```
[ 8 hours ]  ← Slightly highlighted when you move your mouse over it
```

### Understanding the Time Frame Label

The label shows **human-readable time descriptions**:

| Button Label | Actual Time Range | Minutes |
|-------------|-------------------|---------|
| 15 min | Last 15 minutes | 15 |
| 1 hour | Last 60 minutes | 60 |
| 8 hours | Last 8 hours | 480 |
| 24 hours | Last 24 hours | 1440 |

---

## Tips & Best Practices

### Start Small, Then Expand

✅ **Recommended workflow:**
1. Start with **15 min** (fastest, most recent)
2. If you don't see what you need, try **1 hour**
3. Still nothing? Move to **8 hours**
4. Need full context? Use **24 hours**

This approach minimizes loading time while giving you the information you need.

### Understand What You're Viewing

The log preview always shows **the most recent 10 entries** from your selected time window. This means:

- **15 min**: The 10 most recent logs in the last 15 minutes
- **1 hour**: The 10 most recent logs in the last hour
- **8 hours**: The 10 most recent logs in the last 8 hours
- **24 hours**: The 10 most recent logs in the last 24 hours

**Note:** If there are fewer than 10 log entries in the time window, you'll see only what's available.

### When to Use Longer Time Frames

Longer time frames are useful when:
- You're investigating **intermittent issues** that may not appear in short windows
- You want to understand **patterns over time**
- You're looking for the **first occurrence** of a problem
- You're **comparing activity** across different times of day

### Performance Considerations

**Time frame affects loading speed:**
- **15 min & 1 hour**: Very fast (< 1-2 seconds)
- **8 hours**: Still fast (1-3 seconds)
- **24 hours**: Slightly slower (2-4 seconds)

CloudWatch needs more time to search larger time windows, but the difference is usually minimal.

**Tip:** If loading seems slow, your log group might be very active. Consider starting with shorter time frames for faster results.

### Selecting Logs for Agent Context

After changing time frames, your **selection is reset**. This is intentional:

1. You switch from "15 min" to "1 hour"
2. Previous selections clear (they may not exist in the new time window)
3. New logs appear
4. Select the relevant entries from the new results
5. Click "Add Selected to Context"

This ensures you're always adding logs from your current time window to the agent's context.

---

## Keyboard Navigation

You can navigate the time frame selector using your keyboard:

| Key | Action |
|-----|--------|
| **Tab** | Move focus to the time frame buttons |
| **Left Arrow** | Move to previous time frame button |
| **Right Arrow** | Move to next time frame button |
| **Enter** or **Space** | Activate the focused time frame button |
| **Escape** | Close the log preview window |

**Example workflow:**
1. Open log preview (double-click log group)
2. Press **Tab** until time frame buttons are focused
3. Press **Right Arrow** to move to "1 hour"
4. Press **Enter** to select it
5. Logs refresh automatically

---

## Frequently Asked Questions

### What's the default time frame?

**Answer:** **15 minutes**. Every time you open a log preview, it starts with the last 15 minutes. This gives you the most recent logs quickly.

### Does changing the time frame affect my selected logs?

**Answer:** Yes. When you change the time frame, your selections are **cleared** and the log entries **refresh**. This is because:
- The new time window may contain completely different logs
- Previous selections might not exist in the new window
- This ensures you're always selecting from the current view

### Can I use a custom time frame?

**Answer:** Not yet. Currently, you can only choose from the four preset options: 15 min, 1 hour, 8 hours, and 24 hours. Custom time frames may be added in a future version.

### Why don't I see any logs?

**Possible reasons:**

1. **No activity in time window** - Your log group might not have any entries in the selected time frame. Try a longer time frame.

2. **Log group is empty** - The log group might be new or inactive.

3. **Permissions issue** - Your AWS credentials might not have permission to read this log group. Check the error message.

4. **CloudWatch lag** - Very recent logs (< 30 seconds old) might not appear yet due to CloudWatch ingestion delay. Wait a moment and try refreshing.

### How do I see older logs?

**Answer:** Select a longer time frame (8 hours or 24 hours). The preview always shows the **most recent 10 entries** from your selected window.

If you need logs older than 24 hours, close the preview and ask the LogAI agent directly:

```
You: Show me logs from /aws/lambda/my-function from 3 days ago
```

The agent can query any time range CloudWatch supports (up to the log group's retention period).

### Can I see more than 10 log entries?

**Answer:** Not in the preview. The log preview is designed for **quick glances** at recent activity and always shows the 10 most recent entries.

For deeper analysis, use the LogAI agent:

```
You: Show me all errors from /aws/lambda/my-function in the last hour
```

The agent can retrieve and analyze many more log entries.

### Does this use more AWS CloudWatch API calls?

**Answer:** Each time you change the time frame, LogAI makes one CloudWatch API call to fetch the new logs. This is the same as opening a new log preview.

**Tip:** The results are cached briefly, so if you switch back to a recently viewed time frame, it loads from cache (nearly instant).

### What if the preview is slow to load?

**Possible causes and solutions:**

1. **Large time window** - Try a shorter time frame (15 min or 1 hour)
2. **Very active log group** - High-volume log groups take longer to query
3. **CloudWatch API throttling** - AWS may rate-limit requests; wait a moment and try again
4. **Network issues** - Check your internet connection

**Normal loading times:**
- Fast: < 2 seconds
- Normal: 2-4 seconds
- Slow: > 5 seconds (unusual)

### Can I refresh the current time frame?

**Answer:** Not directly. To refresh:
1. Close the log preview (press **Escape** or click **Close**)
2. Double-click the log group again

Or change to a different time frame and change back.

---

## Troubleshooting

### No Logs Appear for Longer Time Frames

**Symptom:** You select "8 hours" or "24 hours" but see "No log entries found."

**Solutions:**

1. **Verify log activity** - The log group might genuinely have no logs in that time window. Check AWS CloudWatch Console to confirm.

2. **Try a shorter window** - Start with 15 min to confirm the log group has recent activity.

3. **Check permissions** - Ensure your AWS credentials have `logs:FilterLogEvents` permission for this log group.

4. **Review retention** - Very old log groups might have logs that have expired based on retention settings.

### Loading Takes Longer with Larger Time Windows

**Symptom:** "24 hours" takes noticeably longer to load than "15 min."

**Explanation:** This is expected. CloudWatch needs more time to search a larger time range.

**Solutions:**

1. **Be patient** - Loading should complete in 2-4 seconds
2. **Start with shorter windows** - Use 15 min or 1 hour for faster results
3. **Check log volume** - Very active log groups take longer; this is normal

### Modal Appears Unresponsive

**Symptom:** You click a time frame button but nothing happens.

**Solutions:**

1. **Wait for current load** - A previous fetch might still be running. Wait for "Loading..." to complete.

2. **Check for errors** - Look for error messages in the preview window.

3. **Close and reopen** - Press **Escape** to close, then double-click the log group again.

4. **Restart LogAI** - If problems persist, close and restart the application.

### Selection Counter Shows "0 of 0 selected"

**Symptom:** Counter shows zero total logs after changing time frames.

**Explanation:** No logs were found in the selected time window.

**Solutions:**

1. **Try a longer time frame** - Switch to a broader window (e.g., from 1 hour to 8 hours)
2. **Verify log group activity** - Check that the log group is actually receiving logs
3. **Check time range** - The log activity might be outside all available time frames

### Can't Click Time Frame Buttons

**Symptom:** Buttons appear grayed out or don't respond to clicks.

**Possible causes:**

1. **Loading in progress** - Wait for current fetch to complete (buttons are enabled during loading, but rapidly clicking may cause confusion)

2. **Modal not fully loaded** - Wait a moment after opening the preview

3. **UI focus issue** - Click inside the modal window first, then try the buttons

### Error Message Appears

**Common errors and solutions:**

| Error Message | Meaning | Solution |
|--------------|---------|----------|
| "Access denied" | AWS permissions issue | Check your AWS credentials and IAM permissions |
| "Log group not found" | Log group was deleted | Refresh log groups list with `/refresh` command |
| "Rate limit exceeded" | Too many API calls | Wait 30 seconds and try again |
| "Timeout" | CloudWatch didn't respond | Check your internet connection; try again |

For any persistent errors, take note of the error message and check the [LogAI Troubleshooting Guide](../docs/user-guide/troubleshooting.md).

---

## Integration with Agent Context

### Adding Logs to Agent Context

The time frame selector works seamlessly with the "Add Selected to Context" feature:

**Workflow:**
1. Select a time frame (e.g., "1 hour")
2. Preview loads logs from the last hour
3. Check the boxes next to interesting log entries
4. Click **"Add Selected to Context"**
5. Modal closes
6. System message appears: "Added X log entries from [log-group] to context"
7. Ask the agent questions about those specific logs

**Example conversation:**
```
[After adding 3 error logs from the last hour to context]

You: What do these errors have in common?

Agent: Looking at the 3 error logs you selected, they all show:
- Authentication failures
- Coming from the same IP address: 203.0.113.42
- Occurring within a 5-minute window
- Suggesting a potential brute-force attack attempt
```

### Time Frame Context in Messages

When you add logs to context, the agent knows which time frame they came from. This helps the agent understand the temporal context of the logs.

---

## Advanced Usage

### Rapid Time Frame Exploration

For quick exploration of different time windows:

1. Open log preview
2. Click through time frames in order: **15 min** → **1 hour** → **8 hours** → **24 hours**
3. Each click refreshes the view
4. Previous fetches are automatically cancelled (no need to wait)
5. Only the final selection's results appear

This is safe and efficient - LogAI handles rapid switching gracefully.

### Combining with Agent Queries

**Strategy:** Use the log preview for quick assessment, then ask the agent for deeper analysis.

**Example workflow:**

1. **Preview** - Double-click log group, select "1 hour" time frame
2. **Assess** - Scan the 10 most recent logs
3. **Select** - Check 2-3 interesting entries
4. **Add to context** - Click "Add Selected to Context"
5. **Query agent** - Ask specific questions about those logs
6. **Expand** - Ask follow-up questions for deeper analysis

**Sample conversation:**
```
[After previewing and adding 2 error logs to context]

You: Analyze these errors

Agent: These are database connection timeout errors...

You: Have there been more errors like this in the past 6 hours?

Agent: [Searches CloudWatch for broader pattern]
```

### Understanding "Most Recent 10 Entries"

The preview always shows the **10 most recent** logs from your time window. Here's what that means for each time frame:

| Time Frame | What You See |
|-----------|-------------|
| **15 min** | The 10 newest logs from the last 15 minutes |
| **1 hour** | The 10 newest logs from the last hour |
| **8 hours** | The 10 newest logs from the last 8 hours |
| **24 hours** | The 10 newest logs from the last 24 hours |

**Important:** If your log group is high-volume, the "10 most recent from 24 hours" might all be from the last few minutes! The time frame sets the **search window**, not the distribution of results.

---

## Comparison with Agent Queries

### When to Use the Log Preview

✅ **Use the log preview when you want to:**
- Quickly glance at recent activity
- Check if a log group has any recent logs
- Get a sense of log patterns before asking questions
- Select specific log entries to share with the agent
- Explore without asking the agent questions

### When to Use Agent Queries

✅ **Use agent queries when you need to:**
- Search across multiple log groups
- Use complex filter patterns
- Analyze many more than 10 log entries
- Get time ranges beyond 24 hours
- Have the agent provide analysis and insights
- Combine logs with other data sources

### Best Practice: Use Both

The most effective workflow combines both approaches:

1. **Preview first** - Quick visual assessment
2. **Select relevant logs** - Add specific entries to context
3. **Query the agent** - Ask for deeper analysis
4. **Iterate** - Refine your investigation based on findings

---

## Summary

The time frame selector gives you flexible control over which logs you see in the log preview window:

- **Four preset time windows:** 15 min, 1 hour, 8 hours, 24 hours
- **One-click switching** between time frames
- **Automatic refresh** when you change time frames
- **Fast loading** for all time windows (typically 1-4 seconds)
- **Reset selections** to ensure consistency
- **Works seamlessly** with "Add Selected to Context" feature

**Remember:**
- Start with shorter time frames for fastest results
- Use longer time frames for pattern analysis and broader context
- Selections are cleared when you change time frames
- The preview always shows the 10 most recent logs from your selected window

---

## Need More Help?

- **LogAI User Guide:** [docs/user-guide/README.md](../docs/user-guide/README.md)
- **Features Overview:** [docs/user-guide/features.md](../docs/user-guide/features.md)
- **Troubleshooting:** [docs/user-guide/troubleshooting.md](../docs/user-guide/troubleshooting.md)
- **Report Issues:** Contact your LogAI administrator or open a support ticket

---

**Feature Version:** 1.0
**Last Updated:** February 18, 2026
**Related Features:** Log Preview, Log Groups Sidebar, Agent Context
