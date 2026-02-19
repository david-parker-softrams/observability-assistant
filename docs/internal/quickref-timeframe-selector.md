# Time Frame Selector - Quick Reference Card

**One-page guide to the log preview time frame selector**

---

## Quick Start

1. **Double-click** a log group in the sidebar
2. **Click** a time frame button at the top: `[15 min] [1 hour] [8 hours] [24 hours]`
3. Logs **automatically refresh** from the selected time window
4. View the 10 most recent entries from that window

---

## Available Time Frames

| Button | Time Range | Best For | Load Time |
|--------|-----------|----------|-----------|
| **15 min** | Last 15 minutes | Quick checks, real-time monitoring | < 1 sec |
| **1 hour** | Last 60 minutes | Recent troubleshooting, ongoing issues | 1-2 sec |
| **8 hours** | Last 8 hours | Trend analysis, business day patterns | 1-3 sec |
| **24 hours** | Last 24 hours | Daily patterns, full context | 2-4 sec |

**Default:** 15 minutes

---

## Common Use Cases

### Quick Recent Check
```
Time Frame: 15 min
Goal: "Is the service currently working?"
```

### Troubleshoot Ongoing Issue
```
Time Frame: 1 hour
Goal: "What errors occurred recently?"
```

### Analyze Trends
```
Time Frame: 8 hours
Goal: "Are there patterns during business hours?"
```

### Review Daily Activity
```
Time Frame: 24 hours
Goal: "What's the daily error pattern?"
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  Log Preview: /aws/lambda/my-function                       │
├─────────────────────────────────────────────────────────────┤
│  Time Frame:  [●15 min][ 1 hour ][ 8 hours ][ 24 hours ]   │  ← Click here
├─────────────────────────────────────────────────────────────┤
│  [Select All] [Deselect All]              0 of 10 selected  │
├─────────────────────────────────────────────────────────────┤
│  Log entries appear here...                                 │
└─────────────────────────────────────────────────────────────┘
```

**Selected button** = Highlighted with primary color
**Click any button** = Logs refresh automatically

---

## Key Behaviors

### When You Change Time Frames:

1. ✅ Loading indicator appears
2. ✅ Previous log entries clear
3. ✅ Selections reset (checkboxes cleared)
4. ✅ New logs load from selected time window
5. ✅ Counter updates: "0 of N selected"

### What You See:

- **Always** the 10 most recent log entries
- **From** your selected time window
- **Sorted** newest first

---

## Keyboard Navigation

| Key | Action |
|-----|--------|
| **Tab** | Focus on time frame buttons |
| **Left/Right Arrow** | Move between buttons |
| **Enter** or **Space** | Select focused time frame |
| **Escape** | Close preview window |

---

## Quick Tips

✅ **Start small** - Begin with 15 min, expand as needed
✅ **Fast results** - Shorter time frames load faster
✅ **Selections reset** - When you change time frames, selections clear
✅ **10 entries max** - Preview always shows 10 most recent logs
✅ **Safe to switch** - Rapidly clicking different time frames is OK

---

## Common Workflows

### Exploration Workflow
```
1. Open preview → See 15 min logs
2. Click "1 hour" → See broader context
3. Click "8 hours" → Check for patterns
4. Select interesting logs
5. Add to agent context
```

### Quick Assessment Workflow
```
1. Open preview (defaults to 15 min)
2. Scan the 10 most recent logs
3. Decision:
   - No issues? Close and move on
   - Found something? Add to context and query agent
   - Need more? Switch to longer time frame
```

### Pattern Analysis Workflow
```
1. Start with "24 hours" for full daily view
2. Identify interesting time periods
3. Switch to "1 hour" for detailed look
4. Select specific logs
5. Add to context and query agent
```

---

## Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| **No logs appear** | Try longer time frame (e.g., 1 hour → 8 hours) |
| **Loading is slow** | Try shorter time frame (e.g., 24 hours → 1 hour) |
| **Button doesn't respond** | Wait for current load to finish |
| **Selections disappeared** | Expected! Selections reset when time frame changes |
| **"0 of 0 selected"** | No logs in time window; try longer time frame |

---

## Integration with Agent Context

### Adding Logs to Context:

1. Select time frame (e.g., "1 hour")
2. Check boxes next to interesting logs
3. Click **"Add Selected to Context"**
4. Modal closes
5. System message confirms addition
6. Ask agent questions about those logs

### Example:
```
[Select 3 error logs from "1 hour" time frame]
Click "Add Selected to Context"

System: Added 3 log entries from /aws/lambda/my-function to context

You: What do these errors have in common?
Agent: [Analyzes the 3 selected logs...]
```

---

## Feature Limits

| What | Limit |
|------|-------|
| **Max entries shown** | 10 (most recent) |
| **Max time window** | 24 hours |
| **Min time window** | 15 minutes |
| **Custom time frames** | Not available (preset options only) |

---

## Best Practices

### ⭐ Start with Shortest Time Frame
- Loads fastest
- Shows most recent activity
- Expand only if needed

### ⭐ Use Longer Time Frames for Patterns
- 8 hours: Business day patterns
- 24 hours: Daily cycles and trends

### ⭐ Combine with Agent Queries
- Preview: Quick visual scan
- Select: Add interesting logs to context
- Query: Ask agent for deeper analysis

### ⭐ Don't Worry About Speed
- All time frames load quickly (1-4 seconds)
- Switching time frames is safe and instant
- Previous fetches auto-cancel if you switch

---

## FAQ Speed Round

**Q: What's the default?**
A: 15 minutes

**Q: Do selections carry over?**
A: No, selections reset when you change time frames

**Q: Can I use custom time frames?**
A: Not yet (preset options only)

**Q: Why don't I see logs?**
A: Try a longer time frame or check log group activity

**Q: Can I see more than 10 logs?**
A: Not in preview; use agent queries for more logs

**Q: Does it cost more API calls?**
A: One API call per time frame change (results are cached briefly)

---

## Visual Legend

| Symbol | Meaning |
|--------|---------|
| `[●15 min]` | Selected / Active time frame |
| `[ 1 hour ]` | Available / Not selected |
| `⏳` | Loading in progress |
| `✓` | Log entry selected (checkbox) |
| `[ ]` | Log entry not selected |

---

## Related Commands

```bash
/logs                   # Toggle log groups sidebar
/refresh                # Update log groups list
/clear                  # Clear conversation
/help                   # Show all commands
```

---

## Where to Get Help

- **Full Guide:** `george-scratch/feature-doc-timeframe-selector.md`
- **User Guide:** `docs/user-guide/README.md`
- **Troubleshooting:** `docs/user-guide/troubleshooting.md`
- **Features Overview:** `docs/user-guide/features.md`

---

## Remember

🎯 **Purpose:** Quick preview of recent logs
🎯 **Always:** 10 most recent entries
🎯 **Smart:** Start small, expand as needed
🎯 **Fast:** All time frames load in 1-4 seconds
🎯 **Safe:** Selections reset to avoid confusion

---

**Feature Version:** 1.0
**Quick Reference Version:** 1.0
**Last Updated:** February 18, 2026
