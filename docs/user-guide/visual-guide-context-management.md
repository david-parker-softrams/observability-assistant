# Context Management System - Visual User Guide

**Quick Visual Reference for End Users**

---

## 🎯 What You'll See: Status Bar

The status bar at the bottom shows your context usage with color coding:

### Green Zone (Healthy) 🟢

```
┌─────────────────────────────────────────────────────────────────────┐
│ Status: Ready | Cache: 47 hits (82%) | Context: 45% | Model: gpt-4o │
│                                                 ^^^^                  │
│                                              GREEN = Good!            │
└─────────────────────────────────────────────────────────────────────┘

What it means: You have plenty of space. Keep working normally!
Action needed: None - continue your investigation
```

### Yellow Zone (Warning) 🟡

```
┌─────────────────────────────────────────────────────────────────────┐
│ Status: Ready | Cache: 52 hits (80%) | Context: 78% | Model: gpt-4o │
│                                                 ^^^^                  │
│                                              YELLOW = Caution          │
└─────────────────────────────────────────────────────────────────────┘

What it means: Context is filling up. Consider wrapping up soon.
Action needed: Finish current investigation or start new chat soon
```

### Red Zone (Critical) 🔴

```
┌─────────────────────────────────────────────────────────────────────┐
│ Status: Ready | Cache: 58 hits (81%) | Context: 92% | Model: gpt-4o │
│                                                 ^^^^                  │
│                                               RED = Critical!         │
└─────────────────────────────────────────────────────────────────────┘

What it means: Nearly full! Auto-pruning active to maintain space.
Action needed: Finish up now and start a new chat
```

---

## 💬 What You'll See: Toast Notifications

Temporary pop-up messages appear in the top-right to inform you of system actions:

### Cache Notification

```
┌──────────────────────────────────────────────────────────────┐
│ 💾 Cached large result: 1,847 events, 42,315 tokens →       │
│    2,450 token summary                                        │
│                                                [Dismiss] [5s] │
└──────────────────────────────────────────────────────────────┘

What happened: A large CloudWatch query was cached to save space
What it means: The agent received a summary, full details are saved
What to do: Nothing! This is working as designed ✅
```

### Pruning Notification

```
┌──────────────────────────────────────────────────────────────┐
│ ✂️ Pruned 6 old messages to maintain context                │
│    (freed ~8,420 tokens)                                      │
│                                                [Dismiss] [5s] │
└──────────────────────────────────────────────────────────────┘

What happened: Old conversation history was removed
What it means: Recent messages preserved, space freed for new queries
What to do: If you need full history, start a new chat ⚠️
```

### Warning Notification

```
┌──────────────────────────────────────────────────────────────┐
│ ⚠️ Context window 92% full (!)                               │
│                                                [Dismiss] [5s] │
└──────────────────────────────────────────────────────────────┘

What happened: Context is nearly full
What it means: You're approaching maximum capacity
What to do: Finish current query and start new chat 🛑
```

### Error Notification

```
┌──────────────────────────────────────────────────────────────┐
│ ⚠️ Failed to cache large result                              │
│                                                [Dismiss] [8s] │
└──────────────────────────────────────────────────────────────┘

What happened: System couldn't cache a large result
What it means: Result was added to context, may fill faster
What to do: Check disk space, consider restarting ⚠️
```

---

## 🔄 What You'll Experience: Typical Workflow

### Scenario 1: Normal Session (All Green)

```
You:     "List my Lambda log groups"
Agent:   "Here are your 12 Lambda log groups..."
Status:  Context: 15% [GREEN] ✅
         No notifications

You:     "Show me errors from /aws/lambda/api-handler"
Agent:   "I found 45 errors in the last hour..."
Status:  Context: 38% [GREEN] ✅
         No notifications

You:     "What are the most common error types?"
Agent:   "The most common errors are..."
Status:  Context: 52% [GREEN] ✅
         No notifications

Result: Smooth investigation, no intervention needed! 🎉
```

### Scenario 2: Large Query (Caching Kicks In)

```
You:     "Show me all Lambda errors in the last 24 hours"
Agent:   [Querying CloudWatch...]

Notification appears:
┌──────────────────────────────────────────────────────────────┐
│ 💾 Cached large result: 2,300 events, 67,000 tokens →       │
│    3,200 token summary                                        │
└──────────────────────────────────────────────────────────────┘

Agent:   "I found 2,300 errors. The most common are:
          1. TimeoutError (847 occurrences)
          2. ValidationError (456 occurrences)
          ..."

Status:  Context: 65% [GREEN] ✅

You:     "Show me details for the timeout errors"
Agent:   [Fetches from cache]
         "Here are the specific timeout errors:
          - Task timed out after 30.03 seconds
          - Task timed out after 29.98 seconds
          ..."

Result: Large dataset handled smoothly! Token savings = 95% 🚀
```

### Scenario 3: Long Investigation (Pruning Activates)

```
[After 8-10 large queries...]

Status:  Context: 78% [YELLOW] ⚠️

You:     "Now compare with last week's errors"
Agent:   [Querying CloudWatch...]

Notification appears:
┌──────────────────────────────────────────────────────────────┐
│ 💾 Cached large result: 1,950 events, 55,000 tokens →       │
│    2,800 token summary                                        │
└──────────────────────────────────────────────────────────────┘

Status:  Context: 84% [RED] 🔴

Then another notification:
┌──────────────────────────────────────────────────────────────┐
│ ✂️ Pruned 8 old messages to maintain context                │
│    (freed ~12,340 tokens)                                     │
└──────────────────────────────────────────────────────────────┘

Agent:   "Comparing current errors with last week..."

Status:  Context: 71% [YELLOW] ⚠️

Decision Point:
  Option 1: Finish investigation (1-2 more queries)
  Option 2: Start new chat to reset context

You:     "What's the key difference?"
Agent:   "The main difference is..."

Status:  Context: 76% [YELLOW] ⚠️

You:     [Decide to save findings and start fresh]
         /clear

Status:  Context: 5% [GREEN] ✅

Result: System managed context automatically, investigation continued! 💪
```

---

## 🎨 Visual: Context Usage Over Time

### Normal Session (Stays Green)

```
Context
Usage
100% ┤
     │
     │
 75% ┤
     │                                    🟢 🟢
     │                          🟢 🟢 🟢
 50% ┤                    🟢 🟢
     │              🟢 🟢
     │        🟢 🟢
 25% ┤  🟢 🟢
     │🟢
   0% └─────┬─────┬─────┬─────┬─────┬─────→ Time
        Q1   Q2   Q3   Q4   Q5   Q6

Result: Stays in green zone, no action needed
```

### Session With Large Queries (Enters Yellow, Then Pruned)

```
Context
Usage
100% ┤                                              🔴
     │                                        🔴
     │                                  🟡
 75% ┤                            🟡              ⬇️ Pruning
     │                      🟡               🟡      Frees
     │                🟢                           Space
 50% ┤          🟢                              🟢
     │    🟢
     │🟢
 25% ┤
     │
   0% └───┬───┬───┬───┬───┬───┬───┬───┬───┬───→ Time
        Q1 Q2 Q3 Q4 Q5 Q6 Q7 Q8 Q9 Q10

       ▲         ▲         ▲              ▲
     Small    Large     Large          Pruned
     query   cached    cached          freed
                                       space

Result: System automatically manages to prevent overflow
```

### Session Without Context Management (Would Fail)

```
Context
Usage
100% ┤                        ❌ FAILURE
     │                    ❌ OVERFLOW
     │                ❌
 75% ┤            ❌
     │        ❌
     │    ❌
 50% ┤ ❌
     │
   0% └───┬───┬───┬───→ Time
        Q1 Q2 Q3 Q4

Result: Without management, fails after 3-4 large queries
```

---

## 📋 Decision Tree: When to Start New Chat

```
                    Check Status Bar
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                  │
    🟢 GREEN          🟡 YELLOW           🔴 RED
     (0-70%)          (71-85%)          (86-100%)
        │                 │                  │
        ▼                 ▼                  ▼
  ╔══════════╗      ╔══════════╗      ╔══════════╗
  ║ Continue ║      ║  Decide  ║      ║  Finish  ║
  ║ Working  ║      ║  Based   ║      ║   Now    ║
  ║ Normally ║      ║  On Case ║      ║  Start   ║
  ║          ║      ║          ║      ║   New    ║
  ╚══════════╝      ╚══════════╝      ╚══════════╝
        │                 │                  │
        │                 ▼                  │
        │       Are you switching            │
        │           topics?                  │
        │         ┌──────┴──────┐           │
        │         │             │           │
        │        YES           NO           │
        │         │             │           │
        │         ▼             ▼           │
        │    Start New    Continue for      │
        │     Chat        1-2 more          │
        │                 queries           │
        │                                   │
        └───────────────┬───────────────────┘
                        │
                        ▼
                  Investigation
                   Complete ✅
```

---

## 🛠️ Quick Actions Cheat Sheet

### Status Bar Says...

| Status | Color | What to Do |
|--------|-------|------------|
| **Context: 35%** | 🟢 Green | ✅ Keep working - all good! |
| **Context: 78%** | 🟡 Yellow | ⚠️ Plan to wrap up or start new chat soon |
| **Context: 92%** | 🔴 Red | 🛑 Finish now, then `/clear` or restart |

### Notification Says...

| Notification | What to Do |
|--------------|------------|
| **💾 Cached large result...** | ✅ Nothing - keep working |
| **✂️ Pruned X old messages...** | ⚠️ If you need history, start new chat |
| **⚠️ Context window 92% full (!)** | 🛑 Finish query, then `/clear` |
| **⚠️ Failed to cache...** | ⚠️ Check disk space, consider restart |

### Commands to Know

```bash
/clear              # Clear conversation, reset context
/cache status       # Check cache performance
/cache clear        # Clear cached results
/quit               # Exit LogAI (can restart fresh)
```

---

## 💡 Pro Tips

### Tip 1: Glance at Status Bar Regularly

```
Every 3-4 queries → Quick glance at status bar → Decide to continue or reset
```

### Tip 2: Don't Self-Limit Query Size

```
❌ BAD:  "Show me errors from the last 5 minutes only"
         (Artificially limiting to avoid large results)

✅ GOOD: "Show me all errors from the last 24 hours"
         (Let caching handle the size)
```

### Tip 3: Use Multiple Focused Chats

```
Instead of:  One 50-query monster session

Do this:     Chat #1: Error investigation (15 queries) → /clear
             Chat #2: Performance analysis (12 queries) → /clear
             Chat #3: Comparison & summary (8 queries) → /clear
```

### Tip 4: Export Findings Before Clearing

```
Before running /clear:

You:    "Summarize the key findings"
Agent:  "Main findings:
         1. API timeouts increased 300%
         2. Errors concentrated in us-east-1
         3. Database connection issues detected"

[COPY THESE to notes/ticket/docs]

Then: /clear (or /quit → logai)
```

---

## 🎓 Learning Journey

### Day 1: Getting Familiar
- Notice the green status bar indicator
- See your first cache notification (if you run large queries)
- Understand what the colors mean

### Week 1: Building Habits
- Glance at status bar periodically
- Recognize yellow zone and plan accordingly
- Understand when to start new chats

### Month 1: Power User
- Optimize your workflow with multiple focused sessions
- Configure thresholds to match your needs
- Use cache effectively for repeated queries

---

**Remember:** The Context Management System works automatically to prevent failures and enable longer investigations. Just keep an eye on the status bar colors and you'll know when to take action! 🚀

---

**For Complete Details:** See `user-documentation-context-management.md`
**For Quick Reference:** See `quick-reference-context-management.md`
