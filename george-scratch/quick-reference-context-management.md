# LogAI Context Management - Quick Reference Card

**Version:** 1.0 | **Date:** February 12, 2026

---

## Status Bar Color Codes

| Indicator | Range | Status | What It Means | Action Required |
|-----------|-------|--------|---------------|-----------------|
| **Context: 45%** 🟢 | 0-70% | **NORMAL** | Plenty of space available | ✅ None - keep working normally |
| **Context: 78%** 🟡 | 71-85% | **WARNING** | Context filling up, pruning may start | ⚠️ Consider starting new chat soon |
| **Context: 92% (!)** 🔴 | 86-100% | **CRITICAL** | Auto-pruning active, nearly full | 🛑 Finish up, start new chat now |

---

## Toast Notifications

| Icon | Notification | What It Means | Action |
|------|--------------|---------------|--------|
| 💾 | **Cached large result: 1,847 events, 42,315 tokens → 2,450 token summary** | Large CloudWatch result cached to save space, agent receives summary | ✅ None - working as designed |
| ✂️ | **Pruned 6 old messages to maintain context (freed ~8,420 tokens)** | Old conversation removed to make room, recent messages preserved | ⚠️ If you need full history, start new chat |
| ℹ️ | **Context window 74% full** | Informational - context is filling up (yellow zone) | ℹ️ Monitor and plan to wrap up soon |
| ⚠️ | **Context window 92% full (!)** | Critical warning - nearly at capacity (red zone) | 🛑 Finish investigation and start new chat |
| ⚠️ | **Failed to cache large result** | Cache error - result sent to context instead | ⚠️ Check disk space, may need restart |

---

## When to Start a New Chat

### ✅ Continue Current Chat
- Status bar is **green** (0-70%)
- Doing quick follow-up questions
- Investigation is nearly complete
- Recent context is sufficient

### 🔄 Consider Starting New Chat
- Status bar is **yellow** (71-85%)
- Switching topics or time ranges
- Session is getting long (10+ queries)
- Need full conversation history

### 🆕 Definitely Start New Chat
- Status bar is **red** (86%+)
- Seeing multiple pruning notifications
- Investigation is changing direction
- Responses are slowing down

**How to Start Fresh:**
```
/clear          Clear conversation, stay in session
/quit → logai   Exit and restart (nuclear option)
```

---

## Essential Commands

| Command | Purpose | Example Output |
|---------|---------|----------------|
| `/cache status` | View cache statistics | Total Entries: 127, Size: 45.32 MB, Hit Rate: 79.4% |
| `/cache clear` | Clear all cached data | Cache cleared |
| `/clear` | Clear conversation history | Conversation cleared |
| `/config` | View configuration | Shows all active settings |
| `/quit` | Exit LogAI | Exits application |

---

## Best Practices

### ✅ DO
- ✅ Monitor status bar during long sessions
- ✅ Start new chat when context reaches **yellow** (71%+)
- ✅ Export findings before clearing conversation
- ✅ Break complex investigations into focused sessions
- ✅ Ask for full query size - let caching handle it
- ✅ Use `/cache status` to check performance

### ❌ DON'T
- ❌ Ignore **yellow** warnings and continue indefinitely
- ❌ Self-limit query size to avoid caching
- ❌ Keep pushing when status bar is **red**
- ❌ Forget to save findings before `/clear`
- ❌ Disable caching or pruning (unless necessary)

---

## Configuration Quick Start

Add to `.env` file:

```bash
# Caching Threshold (default: 10000 tokens)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000
# Lower = more aggressive caching (5000-10000)
# Higher = less caching (10000-20000)

# Allocation Strategy (default: adaptive)
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive
# Options:
#   - adaptive: Balanced (recommended)
#   - history-focused: Preserve more conversation
#   - result-focused: Allow larger results

# Cache TTL (default: 3600 = 1 hour)
LOGAI_CACHE_TTL_SECONDS=3600

# Enable/Disable Features (default: true)
LOGAI_ENABLE_RESULT_CACHING=true
LOGAI_ENABLE_HISTORY_PRUNING=true
```

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| **Agent "forgot" early conversation** | `/clear` and ask more specific question |
| **Responses are very slow** | `/clear` or `/quit` → `logai` to restart |
| **Cache errors** | `/cache clear` then restart LogAI |
| **Context stays red despite pruning** | `/clear` or start completely new session |
| **Need full details from cached result** | Ask agent: "Show me specific details for X" |
| **Disk space error** | `df -h ~/.logai/cache` then `/cache clear` |

---

## How Context Management Works

### 1. Large Result Caching 🗄️
```
Query returns 2,000 events (67,000 tokens)
         ↓
System caches full result to disk
         ↓
Creates smart summary (3,200 tokens)
         ↓
Agent receives summary (95% reduction)
         ↓
Agent can fetch details if needed
```

### 2. Automatic History Pruning ✂️
```
Context reaches 80% full
         ↓
System identifies old messages
         ↓
Removes oldest messages (FIFO)
         ↓
Preserves recent 4+ messages
         ↓
Frees ~25% of used space
```

### 3. Real-Time Monitoring 📊
```
Status bar updates in real-time
         ↓
Color changes: Green → Yellow → Red
         ↓
Notifications inform you of actions
         ↓
You decide when to start new chat
```

---

## Visual: Context Window Zones

```
  0%  ├──────────────────────────┤
      │                          │  🟢 GREEN ZONE
      │   Plenty of Space        │  Normal Operation
      │   No Action Needed       │  Keep Working!
 70%  ├──────────────────────────┤
      │                          │  🟡 YELLOW ZONE
      │   Filling Up             │  Warning - Monitor
      │   Consider Wrapping Up   │  Pruning May Start
 85%  ├──────────────────────────┤
      │                          │  🔴 RED ZONE
      │   Nearly Full            │  Critical State
      │   Auto-Pruning Active    │  Finish & Start New
100%  └──────────────────────────┘
```

---

## Example Workflows

### Short Monitoring Session ✅
```
Query: "Show errors in last 2 hours"
Status: Context 25% [GREEN]
         ↓
Query: "What are the most common?"
Status: Context 38% [GREEN]
         ↓
Review findings → Done
```

### Long Investigation Session ⚠️
```
Query: "Show all Lambda errors, last 24h"
Status: Context 52% [GREEN]
💾 Cached large result...
         ↓
Query: "Compare with API Gateway errors"
Status: Context 73% [YELLOW]
💾 Cached large result...
         ↓
[DECISION POINT: Finish or start new?]
         ↓
Query: "What's the correlation?"
Status: Context 84% [RED]
✂️ Pruned 8 old messages...
         ↓
Review findings → /clear → Continue
```

### Multi-Chat Strategy ✅
```
Chat #1: Error Investigation
└─ Identify error patterns → Save findings

Chat #2: Performance Analysis
└─ Analyze response times → Save findings

Chat #3: Comparison & Summary
└─ Compare findings → Create report
```

---

## FAQs

**Q: What happens to cached results when I close LogAI?**
A: They persist on disk for 1 hour (configurable) then auto-delete.

**Q: Can I disable context management?**
A: Not recommended - set `LOGAI_ENABLE_RESULT_CACHING=false` or `LOGAI_ENABLE_HISTORY_PRUNING=false` but may cause failures.

**Q: Will pruning remove important information?**
A: No - recent messages (last 4+) are always preserved. Old messages removed FIFO.

**Q: Does caching affect response quality?**
A: No - agent receives smart summaries and can fetch full details if needed.

**Q: How do I know if a result was cached?**
A: You'll see: `💾 Cached large result: X events, XX,XXX tokens → X,XXX token summary`

---

## Configuration Profiles

### Conservative (Long Conversations)
```bash
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=5000
LOGAI_CONTEXT_ALLOCATION_STRATEGY=history-focused
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=30
```

### Aggressive (Large Results)
```bash
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000
LOGAI_CONTEXT_ALLOCATION_STRATEGY=result-focused
LOGAI_MAX_RESULT_TOKENS=80000
```

### Balanced (Default)
```bash
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=20
```

---

**For complete documentation, see:** `user-documentation-context-management.md`

**Support:** https://github.com/logai/logai/issues
**Docs:** https://github.com/logai/logai/docs
