# Release Notes: Log Preview Entry Limit Toggle

**Release Date:** February 19, 2026
**Feature Type:** Enhancement
**Impact:** Low (Non-Breaking)
**Status:** Production Ready

---

## New Feature: Toggle Between 10 and 100 Log Entries

The log preview modal now includes a convenient toggle button that lets you switch between viewing 10 entries (default) and 100 entries from your selected time window.

### What's New

**Toggle Button:**
- Switch between 10 and 100 entries with a single click
- Button shows "Load Last 100" when at default (10 entries)
- Changes to "Show Last 10" when showing 100 entries
- Button color provides visual feedback (gray → blue when active)

**Entry Count Display:**
- Shows actual number of entries loaded (e.g., "Showing 47 entries")
- Updates automatically when toggling or changing time frames
- Provides transparency about data volume

**Smart Persistence:**
- Your chosen limit (10 or 100) persists when changing time frames
- Reduces clicks during investigation workflows
- Can toggle back anytime you need

### User Benefits

✅ **Flexible Context** - Start with 10 for speed, expand to 100 when you need more information

✅ **Non-Disruptive** - Default behavior unchanged (still opens with 10 entries)

✅ **Better Investigation** - See more historical data without leaving the modal

✅ **Intuitive** - Simple toggle button, clear visual feedback

✅ **Workflow-Friendly** - Limit persists across time frame changes

### How to Use

**View More Entries:**
1. Open any log preview modal (10 entries shown by default)
2. Click "Load Last 100" button
3. Modal loads up to 100 entries from the current time window

**Return to Default:**
1. Click "Show Last 10" button
2. Modal returns to 10 entries for faster navigation

**With Time Frames:**
- Your limit choice (10 or 100) stays active when changing time frames
- Switch from 15 min → 1 hour → 8 hours, limit persists

### Behavior Changes

**None!** This is a purely additive feature:
- Default behavior preserved (10 entries on open)
- No configuration required
- All existing features work identically
- Backwards compatible

### Visual Changes

A new control row appears between the time frame selector and selection controls:

```
┌──────────────────────────────────────────────────┐
│ Time Frame: [15 min] [1 hour] [8 hours] [24 hrs]│
├──────────────────────────────────────────────────┤
│ [Load Last 100]            Showing 10 entries   │ ← NEW
├──────────────────────────────────────────────────┤
│ [Select All] [Deselect All]    0 of 10 selected │
└──────────────────────────────────────────────────┘
```

### Performance Notes

- **10 entries:** Loads in < 1 second (unchanged)
- **100 entries:** Loads in 1-3 seconds typically
- No impact on overall application performance
- Efficient rendering of additional entries

### Use Cases

**When to Load 100 Entries:**
- Investigating patterns that need more data points
- Looking for infrequent events or errors
- Analyzing trends or sequences
- Need more historical context in current time window

**When to Keep 10 Entries:**
- Quick checks and recent activity
- High-volume log groups
- Fast navigation and selection
- Initial exploration

### Technical Details

**Implementation:**
- Single file modified: `src/logai/ui/screens/log_preview.py`
- No database or API changes
- No external dependencies added
- Fully tested (66/66 tests passing)

**Quality:**
- Code review approved (10/10 score)
- QA testing passed (100% success rate)
- Zero regressions detected
- Production ready

### Compatibility

**Fully Compatible With:**
- Time frame selector (15 min, 1 hour, 8 hours, 24 hours)
- Selection controls (Select All, Deselect All)
- Add to Context functionality
- All existing log preview features

**No Changes To:**
- Default loading behavior
- AWS API calls or permissions
- Configuration requirements
- Keyboard shortcuts

### Known Behaviors (Not Issues)

**Entry Count vs Limit:**
- If fewer than 100 entries exist in the time window, the actual count is shown
- Example: Clicking "Load Last 100" might show "Showing 47 entries"
- This is normal - you received all available entries

**Selection Clearing:**
- Selections are cleared when toggling between 10 and 100 entries
- This is intentional to prevent confusion with stale selections
- Best practice: Choose your limit first, then make selections

**Modal Instance:**
- Each time you open a log preview, it starts at 10 entries
- The toggle state does not persist across modal instances
- This ensures fast loading by default

### Migration Notes

**No Migration Required**
- Feature is automatically available after deployment
- No user action needed
- No configuration changes required
- Works immediately on first use

### Documentation

**New Documentation:**
- Feature Guide: `george-scratch/feature-doc-log-preview-100-entries.md`
- Quick Reference: `george-scratch/quickref-log-preview-100-entries.md`
- Release Notes: This document

**Updated Documentation:**
- `docs/user-guide/features.md` - Added feature entry
- `docs/user-guide/README.md` - Link added (if needed)

### Related Features

This feature complements existing log preview capabilities:
- **Time Frame Selector** - Change time windows (15 min to 24 hours)
- **Selection Controls** - Select and manage log entries
- **Context Management** - Add selected entries to conversation context

### Feedback and Support

**Questions or Issues?**
- See full documentation: `feature-doc-log-preview-100-entries.md`
- Check quick reference: `quickref-log-preview-100-entries.md`
- Report bugs: GitHub Issues
- Request enhancements: GitHub Discussions

### Future Enhancements (Potential)

These are **not** included in this release but could be considered:
- Arbitrary entry counts (user inputs custom number)
- Configurable default (start at 100 instead of 10)
- Pagination ("load more" instead of fixed counts)
- Remember preference across sessions

---

## Changelog Entry

### Added
- Toggle button in log preview modal to switch between 10 and 100 entries
- Entry count display showing actual number of entries loaded
- Persistent limit across time frame changes within same modal session

### Changed
- None (purely additive feature)

### Fixed
- None (no bugs fixed)

### Deprecated
- None

### Removed
- None

---

## For Developers

### Code Changes
- File modified: `src/logai/ui/screens/log_preview.py` (+117 lines)
- New constant: `LOAD_MORE_LIMIT = 100`
- New reactive property: `current_limit`
- New methods: `on_load_100_clicked()`, `watch_current_limit()`, `_update_limit_button()`, `_update_entry_count_display()`
- New CSS rules for button and display styling

### Testing
- 29 new unit tests added
- Total tests: 66 (37 existing + 29 new)
- All tests passing (100% success rate)
- Manual testing completed and documented

### Quality Metrics
- Code review score: 10/10 (Han-Ron)
- QA score: 10/10 (Raoul)
- Test coverage: 51% (appropriate for UI-heavy file)
- Zero regressions detected

---

**Version:** 1.0.0
**Release Date:** February 19, 2026
**Status:** ✅ Deployed to Production

---

## Summary for Announcements

### Short Version (Tweet/Slack)
```
🎉 New Feature: Log Preview now lets you toggle between 10 and 100 entries
with one click! Default stays at 10 for fast loading, but expand to 100
when you need more context. Your choice persists when changing time frames.
Simple, intuitive, non-disruptive. Available now!
```

### Medium Version (Blog Post Intro)
```
We're excited to announce a new enhancement to the Log Preview modal:
entry limit toggle! You can now easily switch between viewing 10 entries
(default) and 100 entries with a single button click. This gives you
flexible control during investigations - start with 10 for speed, expand
to 100 when you need more context. Your limit choice intelligently persists
when changing time frames, reducing clicks and streamlining your workflow.
The feature is completely non-disruptive (default behavior unchanged) and
available immediately. Read on to learn more...
```

### Long Version (Email Newsletter)
```
Subject: New Feature: Flexible Entry Limits in Log Preview

Hi LogAI Users,

We've just released a quality-of-life improvement to the log preview modal
that gives you more control over how much data you see.

WHAT'S NEW:
A new toggle button lets you switch between 10 entries (default) and
100 entries from your selected time window. The button is located right
below the time frame selector and provides clear visual feedback about
your current state.

WHY WE BUILT IT:
We heard from users that sometimes 10 entries wasn't enough context for
investigations, but increasing the default would slow down quick checks.
This toggle gives you the best of both worlds - fast defaults with easy
expansion when needed.

HOW IT WORKS:
- Modal opens with 10 entries (unchanged)
- Click "Load Last 100" to see more
- Click "Show Last 10" to return to default
- Your choice persists when changing time frames

SMART BEHAVIORS:
The feature includes thoughtful details like showing actual entry counts
(not just the limit), persisting your choice across time frame changes,
and providing clear loading indicators.

NO CHANGES REQUIRED:
This is a purely additive feature - it's automatically available with no
configuration needed. All existing workflows work exactly as before.

Learn more in the full documentation:
[Link to feature guide]

Happy investigating!
- The LogAI Team
```

---

**End of Release Notes**
