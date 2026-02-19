# Quick Reference: Log Preview Entry Limit Toggle

**Feature:** Switch between 10 and 100 log entries in log preview modal
**Quick Access:** Look for the button between time frame selector and selection controls

---

## Quick Start

### Open Modal → See Button → Click to Toggle

```
Default:  [Load Last 100]  →  Showing 10 entries
Click:    [Show Last 10]   →  Showing 100 entries
```

---

## Button States at a Glance

| Button Label | Color | Meaning | Action |
|--------------|-------|---------|--------|
| **"Load Last 100"** | Gray | Currently at 10 | Click to load 100 |
| **"Show Last 10"** | Blue | Currently at 100 | Click to return to 10 |

---

## Common Tasks

### View More Entries
1. Open log preview (10 entries shown by default)
2. Click **"Load Last 100"** button
3. Wait 1-3 seconds for loading
4. See up to 100 entries

### Return to Default
1. Click **"Show Last 10"** button
2. Returns to 10 entries
3. Faster loading and scrolling

### Change Time Frame While at 100
1. Have 100 entries loaded
2. Click any time frame button (1 hour, 8 hours, etc.)
3. Still loads 100 entries from new time window
4. Limit persists automatically

---

## Visual Guide

### Where Is It?

```
┌──────────────────────────────────────────────────┐
│ Log Preview: /aws/lambda/my-function             │
├──────────────────────────────────────────────────┤
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hrs]│ ← Time selector
├──────────────────────────────────────────────────┤
│ [Load Last 100]            Showing 10 entries   │ ← NEW FEATURE
│  ^Toggle Button             ^Entry Count        │
├──────────────────────────────────────────────────┤
│ [Select All] [Deselect All]    0 of 10 selected │ ← Selection controls
├──────────────────────────────────────────────────┤
│ Log entries appear here...                       │
└──────────────────────────────────────────────────┘
```

---

## Key Behaviors

### ✅ Default Unchanged
- Modal always opens with **10 entries**
- Fast loading by default

### ✅ Limit Persists
- Your choice (10 or 100) stays active when changing time frames
- No need to click "Load Last 100" after every time frame change

### ✅ Shows Actual Count
- If only 47 entries exist, shows "Showing 47 entries"
- Button still shows "Show Last 10" (limit is 100, just fewer results)
- This is normal!

### ⚠️ Selections Clear
- Changing limit (10 ↔ 100) clears selections
- Choose your limit first, then select entries

---

## When to Use

| Use 10 Entries | Use 100 Entries |
|----------------|-----------------|
| Quick checks | Pattern investigation |
| Recent activity only | Historical context needed |
| High-volume logs | Infrequent errors |
| Fast navigation | Trend analysis |
| Initial exploration | Deep dive investigation |

---

## Tips

### 💡 Efficient Workflow
1. Start: 10 entries, narrow time (15 min)
2. Not enough? → Click "Load Last 100"
3. Still not enough? → Expand time frame (1 hour)
4. Done? → Click "Show Last 10" for final review

### 💡 Performance
- **10 entries:** < 1 second typically
- **100 entries:** 1-3 seconds typically
- Narrow time windows load faster

### 💡 Selection Best Practice
- Don't blindly "Select All" with 100 entries
- Scroll through and select only relevant entries
- Keeps context manageable

---

## Troubleshooting Quick Fixes

### Fewer entries than expected?
→ Normal! Shows actual count in time window
→ Expand time frame to see more

### Button stuck or wrong label?
→ Close and reopen modal
→ Resets to default state

### Selections disappeared?
→ Expected when toggling 10 ↔ 100
→ Make limit choice first, then select

### Loading takes forever?
→ Try narrower time window
→ Use "Show Last 10" for faster loads

---

## Quick Comparison

### Before This Feature
```
- Fixed at 10 entries
- Need to manually configure for more
- No easy way to see more context
```

### With This Feature
```
✓ Toggle between 10 and 100 with one click
✓ Fast default, extended when needed
✓ Limit persists across time frame changes
✓ Clear visual feedback
```

---

## Common Questions

**Q: Does this change the default everywhere?**
A: No, each modal starts at 10 entries.

**Q: Can I make 100 the default?**
A: No, always starts at 10 for fast loading.

**Q: Will it load ALL logs?**
A: No, maximum is 100 entries (most recent).

**Q: Does my selection persist when toggling?**
A: No, selections clear when changing limit.

---

## See Full Documentation

For detailed information, examples, and troubleshooting:
→ See: [Feature Guide - Log Preview Load 100 Entries](feature-doc-log-preview-100-entries.md)

---

**Print this page for quick reference at your desk!**

**Version:** 1.0 | **Updated:** February 19, 2026 | **Status:** Production Ready ✓
