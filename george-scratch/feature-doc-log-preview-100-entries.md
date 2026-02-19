# Log Preview: Load Last 100 Entries Feature Guide

**Feature:** Toggle button for loading 10 or 100 log entries
**Version:** Added February 2026
**Status:** Production Ready

---

## Overview

The Log Preview modal now includes a convenient toggle button that lets you switch between viewing 10 entries (default) and 100 entries from your selected time window. This gives you flexible control over how much log data you see without changing the default behavior.

### What It Does

- **Default View:** Opens with 10 entries (just like before)
- **Extended View:** Click one button to load up to 100 entries
- **Easy Toggle:** Switch back and forth as many times as you need
- **Persistent Choice:** Your selection stays active when you change time frames

### Why Use This Feature

**Quick Context:**
- See 10 entries by default for fast loading and focused viewing
- Load 100 entries when you need more historical context
- Perfect for investigating patterns that need more data points

**Flexible Investigation:**
- Start with 10 entries to get oriented
- Expand to 100 when you spot something interesting
- Return to 10 for faster navigation

**Non-Disruptive:**
- Default behavior unchanged (still opens with 10 entries)
- Completely optional - use it when you need it
- No configuration required

### When to Use It

**Use 10 Entries (Default) When:**
- You want a quick overview
- Looking for recent events only
- Fast loading is a priority
- Working with high-volume log groups

**Use 100 Entries When:**
- Investigating patterns that need more data
- Searching for infrequent events
- Need more historical context
- Analyzing error sequences or trends

---

## How to Use

### Step-by-Step Instructions

#### 1. Open Log Preview Modal

Open a log preview in any of the usual ways:
- Click on a log group in the left sidebar
- Use a query like: "Show me logs from /aws/lambda/my-function"

**What You See:**
```
┌──────────────────────────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-function                     │
├──────────────────────────────────────────────────────────┤
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Load Last 100]                    Showing 10 entries   │
├──────────────────────────────────────────────────────────┤
│ [Select All] [Deselect All]              0 of 10 selected│
├──────────────────────────────────────────────────────────┤
│ │ Entry 1  │ 2026-02-19 10:45:23 │ Log message...       │
│ │ Entry 2  │ 2026-02-19 10:45:22 │ Another message...   │
│ │   ...    │                     │                       │
│ (8 more entries)                                         │
├──────────────────────────────────────────────────────────┤
│         [Add Selected to Context]  [Close]               │
└──────────────────────────────────────────────────────────┘
```

**Default State:**
- 10 entries are loaded
- Button shows "Load Last 100"
- Display shows "Showing 10 entries"

#### 2. Load 100 Entries

Click the **"Load Last 100"** button to fetch more entries.

**What Happens:**
1. Button becomes temporarily disabled
2. Loading indicator appears: "Loading recent log entries..."
3. Up to 100 entries are fetched from the current time window
4. Display updates automatically

**What You See After Loading:**
```
┌──────────────────────────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-function                     │
├──────────────────────────────────────────────────────────┤
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Show Last 10]                    Showing 100 entries   │  ← Changed!
├──────────────────────────────────────────────────────────┤
│ [Select All] [Deselect All]             0 of 100 selected│
├──────────────────────────────────────────────────────────┤
│ │ Entry 1  │ 2026-02-19 10:45:23 │ Log message...       │
│ │ Entry 2  │ 2026-02-19 10:45:22 │ Another message...   │
│ │   ...    │                     │                       │
│ (98 more entries)                                        │
├──────────────────────────────────────────────────────────┤
│         [Add Selected to Context]  [Close]               │
└──────────────────────────────────────────────────────────┘
```

**Notice the Changes:**
- Button label changed to "Show Last 10" (blue/primary color)
- Entry count shows "Showing 100 entries"
- Selection counter shows "0 of 100 selected"
- All 100 entries are visible in the scrollable list

#### 3. Return to 10 Entries

Click the **"Show Last 10"** button to return to the default view.

**What Happens:**
1. Modal clears current entries
2. Fetches the last 10 entries
3. Display updates to show fewer entries

**What You See:**
- Back to the default state
- Button shows "Load Last 100" again
- Display shows "Showing 10 entries"
- Ready to toggle again if needed

#### 4. Using With Time Frame Selector

Your entry limit choice **persists** when you change time frames.

**Example Workflow:**
1. Click "Load Last 100" → Now viewing 100 entries from 15 minutes
2. Click "1 hour" time frame → Fetches 100 entries from last hour
3. Button still shows "Show Last 10" (limit stayed at 100)
4. Click "Show Last 10" → Returns to 10 entries
5. Click "8 hours" → Fetches 10 entries from last 8 hours

**Why This Is Helpful:**
- If you need more context, you don't have to click "Load Last 100" after every time frame change
- Your investigation workflow remains uninterrupted
- Intuitive behavior - the limit you chose stays active

---

## Key Features

### Toggle Button Functionality

**Button States:**

| State | Label | Button Color | Meaning |
|-------|-------|--------------|---------|
| Default | "Load Last 100" | Gray (default) | Currently showing 10 entries |
| Active | "Show Last 10" | Blue (primary) | Currently showing 100 entries |

**Button Behavior:**
- Click once to switch from 10 to 100
- Click again to switch back from 100 to 10
- Simple toggle - no complex menus or options
- Always shows what action will happen next

### Entry Count Display

Located on the right side of the button row, this shows how many entries are actually displayed.

**What It Shows:**
- "Showing 10 entries" - When viewing 10 entries
- "Showing 100 entries" - When viewing 100 entries
- "Showing 47 entries" - When fewer than requested are available
- Empty - When no entries exist

**Important Note:** The display shows the **actual** number of entries, not the requested limit. If you click "Load Last 100" but only 47 entries exist in the time window, you'll see "Showing 47 entries" - this is normal and expected.

### Limit Persistence Across Time Frame Changes

Your chosen limit stays active when you change time frames.

**Scenario 1: Staying at 100**
```
1. Open modal → 10 entries from "15 min"
2. Click "Load Last 100" → 100 entries from "15 min"
3. Click "1 hour" time frame → 100 entries from "1 hour"
4. Click "8 hours" → Still 100 entries from "8 hours"
```

**Scenario 2: Switching Limits**
```
1. Open modal → 10 entries from "15 min"
2. Click "Load Last 100" → 100 entries from "15 min"
3. Click "1 hour" → 100 entries from "1 hour"
4. Click "Show Last 10" → 10 entries from "1 hour"
5. Click "8 hours" → 10 entries from "8 hours"
```

**Why It Works This Way:**
- More intuitive - if you wanted 100 entries, you probably still want 100 entries
- Fewer clicks during investigation
- Can still switch back anytime

### Loading Indicators

When fetching entries, you'll see clear feedback:

**Visual Indicators:**
- "Loading recent log entries..." message appears
- Button temporarily disabled (prevents double-clicking)
- Existing entries cleared to avoid confusion

**Performance:**
- Typically completes in 1-3 seconds
- May take longer for busy log groups or large time windows
- UI remains responsive - you can still interact with other elements

---

## Tips & Best Practices

### When to Use 10 vs 100 Entries

**Start With 10 (Default):**
- Initial exploration of a log group
- Quick checks for recent activity
- High-volume log groups (lots of entries)
- When you know what you're looking for

**Expand to 100 When:**
- You need more historical context
- Looking for patterns or trends
- Investigating infrequent errors
- Initial 10 entries don't have enough information
- Comparing multiple log messages

### Performance Considerations

**Loading Time:**
- **10 entries:** Very fast (< 1 second typically)
- **100 entries:** Slightly longer (1-3 seconds typically)
- **Time window matters:** Larger windows may take longer

**Best Practices:**
1. Start with shorter time windows (15 min or 1 hour)
2. If 100 entries load slowly, consider narrowing the time window
3. Remember that fewer entries mean faster selection and export operations

### Workflow Recommendations

**Efficient Investigation Workflow:**

```
1. Open log preview with default time window (15 min)
   → See 10 recent entries

2. Scan the 10 entries for immediate issues
   → If found, investigate directly
   → If not found, proceed to step 3

3. Click "Load Last 100" to see more context
   → Look for patterns or infrequent errors
   → If found, analyze and select relevant entries

4. If still nothing found, expand time window
   → Click "1 hour" or "8 hours"
   → Limit stays at 100, so you see more from the wider window

5. When done investigating, click "Show Last 10"
   → Return to focused view for final verification
```

**Multi-Log Group Comparison:**
```
1. Open first log group → "Load Last 100" → Analyze
2. Close modal
3. Open second log group → "Load Last 100" → Compare
4. Note: Each modal instance starts at 10 by default
```

### Selection and Export

**With 100 Entries Loaded:**
- "Select All" works on all 100 entries
- Selection counter shows "100 of 100 selected" when all selected
- "Add Selected to Context" works the same regardless of count
- Consider selecting only relevant entries to keep context manageable

**Best Practice:**
- Don't blindly select all 100 entries
- Scroll through and select specific entries that are relevant
- Use Ctrl+Click or Shift+Click for multi-selection (if supported)

### Memory and Performance

**No Concerns for Normal Use:**
- 100 entries is not a large dataset
- No noticeable performance impact on display or scrolling
- Selection operations work smoothly

**If You Experience Slowness:**
- Consider using narrower time windows
- Use filter patterns to reduce entry volume
- Return to 10 entries for faster interaction

---

## Troubleshooting

### What if fewer than 100 entries are available?

**This is normal!** If your log group doesn't have 100 entries in the selected time window, you'll see however many actually exist.

**Example:**
- You click "Load Last 100"
- Only 47 entries exist in the last 15 minutes
- Display shows: "Showing 47 entries"
- Button still shows: "Show Last 10" (because the limit is 100)

**This is not an error** - you got all available entries within your time window.

**What to do:**
1. If you need more entries, expand the time window (click "1 hour" or "8 hours")
2. If you're investigating recent activity, 47 entries might be all that exist

### What happens during errors?

If the fetch operation fails, you'll see an error message:

**Example Error Message:**
```
Error loading logs:

[Log group was recently deleted]
```

**What to do:**
1. The button remains in the same state (doesn't change label)
2. You can try again by clicking the button
3. If error persists, check the log group still exists
4. Try a different time window
5. Check your AWS permissions

**Common Error Scenarios:**
- Log group deleted or doesn't exist
- AWS permissions insufficient
- Network connectivity issues
- CloudWatch API throttling (rare)

### Button shows wrong label or state

**Rare Issue:** Button label doesn't match actual entries displayed.

**What might cause this:**
- Network interruption during fetch
- Rapid clicking of multiple buttons

**How to fix:**
1. Close the modal
2. Reopen the log preview
3. The modal resets to default state (10 entries)
4. Try the operation again

### Entry count display is empty

**This is normal when:**
- No entries exist in the selected time window
- Log group is empty
- Time window is too narrow for any entries

**What you'll see:**
- Entry count display shows nothing
- Main area shows "No log entries found"
- Button still works normally

**What to do:**
1. Expand the time window (try "1 hour" or "8 hours")
2. Verify the log group has recent activity
3. Check if logs are being written to this group

### Selections cleared after toggling

**This is expected behavior!** When you change the entry limit (10 ↔ 100), your selections are cleared.

**Why this happens:**
- The entry list completely refreshes
- Old selections are no longer valid
- Prevents confusion with outdated selections

**Workaround:**
1. Make your limit choice (10 or 100) first
2. Then make your selections
3. Avoid toggling after you've selected entries

### Loading takes a long time

**If loading 100 entries is slow (>10 seconds):**

**Possible causes:**
- Very large time window (8 hours or 24 hours)
- High-volume log group with many entries
- CloudWatch API is under load
- Network latency

**What to do:**
1. Try narrower time window first (15 min)
2. If still slow, it might be a high-volume log group
3. Consider using filter patterns to reduce volume
4. Return to 10 entries for faster interaction
5. If persistent, check AWS service health

---

## Common Questions

### Q: Does clicking "Load Last 100" load ALL logs in that time window?

**A:** No, it loads up to 100 entries. If more than 100 entries exist, you'll see the most recent 100.

### Q: Will this change my default log preview behavior elsewhere?

**A:** No, each time you open a log preview modal, it starts with 10 entries by default. The 100-entry mode is only active for the current modal session.

### Q: Can I configure the default to be 100 instead of 10?

**A:** Not currently. The default is always 10 entries when opening a log preview. This is by design to keep loading fast.

### Q: Does my selection persist when I toggle between 10 and 100?

**A:** No, selections are cleared when you change the limit. Make your limit choice first, then select entries.

### Q: What happens if I have 100 entries loaded and change the time frame?

**A:** The limit stays at 100, so it will fetch 100 entries from the new time window. This is intentional to support your investigation workflow.

### Q: Can I load more than 100 entries (like 200 or 500)?

**A:** Not currently. The feature supports two modes: 10 entries (default) and 100 entries (extended).

### Q: Does loading 100 entries cost more in AWS API calls?

**A:** The CloudWatch API call is the same regardless of whether you request 10 or 100 entries - the cost is about the same. The main difference is slightly more data transfer.

### Q: Can I use this feature with "Add Selected to Context"?

**A:** Yes! Load 100 entries, select the relevant ones, and add them to context just like you would with 10 entries.

### Q: Does the button work on mobile or narrow terminals?

**A:** Yes, the layout adapts to available space. The button and entry count display will adjust to fit your terminal width.

---

## Visual Reference

### Default State (10 Entries)
```
┌──────────────────────────────────────────────────────────┐
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Load Last 100]                    Showing 10 entries   │
│  ^gray button                      ^subtle gray text    │
├──────────────────────────────────────────────────────────┤
```

### Active State (100 Entries)
```
┌──────────────────────────────────────────────────────────┐
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Show Last 10]                    Showing 100 entries   │
│  ^blue button                      ^subtle gray text    │
├──────────────────────────────────────────────────────────┤
```

### Partial Results (47 available of 100 requested)
```
┌──────────────────────────────────────────────────────────┐
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Show Last 10]                    Showing 47 entries    │
│  ^blue (limit is 100)              ^actual count        │
├──────────────────────────────────────────────────────────┤
```

### Loading State
```
┌──────────────────────────────────────────────────────────┐
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hours]      │
├──────────────────────────────────────────────────────────┤
│ [Load Last 100]                    Showing 10 entries   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│              Loading recent log entries...               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Related Features

### Time Frame Selector
- Changes the time window for log fetching (15 min, 1 hour, 8 hours, 24 hours)
- Works seamlessly with the entry limit toggle
- Your limit choice persists across time frame changes
- See: [Time Frame Selector Guide](timeframe-selector.md)

### Selection Controls
- "Select All" - Selects all visible entries (10 or 100)
- "Deselect All" - Clears selections
- Selection counter updates based on entry count

### Add Selected to Context
- Works the same with 10 or 100 entries
- Select relevant entries and add them to the conversation context
- Helps the AI agent understand what you're investigating

---

## See Also

- **[Time Frame Selector Guide](timeframe-selector.md)** - Change time windows for log fetching
- **[Quick Reference Card](quickref-log-preview-100-entries.md)** - One-page summary
- **[Context Management Guide](context-management.md)** - How to add logs to context
- **[Features Overview](features.md)** - All LogAI features

---

**Feature Version:** 1.0
**Last Updated:** February 19, 2026
**Implementation Status:** Production Ready ✓
