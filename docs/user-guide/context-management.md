# LogAI Context Management System - User Documentation

**Version:** 1.1
**Last Updated:** February 26, 2026
**Status:** Updated for context window scaling changes

---

## Table of Contents

1. [Understanding Context Management](#1-understanding-context-management)
2. [Status Bar Indicator Guide](#2-status-bar-indicator-guide)
3. [Toast Notifications Guide](#3-toast-notifications-guide)
4. [Best Practices](#4-best-practices)
5. [Frequently Asked Questions](#5-frequently-asked-questions)
6. [Advanced Configuration](#6-advanced-configuration)
7. [Quick Reference Card](#7-quick-reference-card)

---

## 1. Understanding Context Management

### What is the Context Window?

Every AI model has a limited "context window" — the total amount of text it can process at once. Think of it as the model's working memory. LogAI needs to fit several things into this window:

- **System instructions** - How the agent should behave and what tools it has
- **Conversation history** - Your questions and the agent's responses
- **Tool results** - CloudWatch logs fetched by the agent
- **Response space** - Room for the agent to think and respond

### Why Does It Matter?

Without proper management, large CloudWatch queries can quickly fill the context window:

- **The Problem:** A single query returning 1,000+ log events can consume 20,000-50,000 tokens
- **The Impact:** After just 2-3 large queries, the context window is full
- **The Consequence:** The agent fails, loses track of earlier conversation, or can't respond

**Example Scenario Without Context Management:**
```
Query 1: "Show me Lambda errors from the last hour" → 45,000 tokens
Query 2: "What about API Gateway errors?" → 38,000 tokens
Query 3: "Compare the two..." → FAILURE: Context window full
```

### How It Works

LogAI's Context Management System automatically handles this with three intelligent behaviors:

#### 1. **Large Result Caching** 🗄️

When a CloudWatch query returns a large result (over 10,000 tokens by default), LogAI automatically:

1. **Caches the full result** to disk (stored outside the context window)
2. **Creates a smart summary** with key statistics and sample events
3. **Sends the summary to the agent** instead of the full result
4. **Provides a tool** for the agent to fetch specific details if needed

**What You'll See:**
```
💾 Cached large result: 1,847 events, 42,315 tokens → 2,450 token summary
```

**What This Means:**
- Your full results are preserved and available
- The agent receives a compact summary (token reduction of 80-95%)
- If the agent needs specific details, it can fetch them using the `FetchCachedResultTool`
- Your conversation can continue without hitting limits

**Real-World Example:**
```
You: Show me all errors from /aws/lambda/api-handler in the last 24 hours

[LogAI fetches 2,300 log events - 67,000 tokens]

LogAI: 💾 Cached large result: 2,300 events, 67,000 tokens → 3,200 token summary

Agent: I found 2,300 error events in the last 24 hours. The most common
       errors are:
       1. TimeoutError (847 occurrences)
       2. ValidationError (456 occurrences)
       3. DatabaseConnectionError (234 occurrences)

       Would you like me to analyze specific error types in detail?

[Token savings: 63,800 tokens - conversation can continue for many more queries!]
```

#### 2. **Automatic History Pruning** ✂️

When your context window fills up (reaches 80% by default), LogAI automatically removes old messages to make room:

1. **Detects when context is filling** (at 80% utilization threshold)
2. **Selects old messages to remove** using First-In-First-Out (FIFO)
3. **Preserves recent conversation** (always keeps the last 4+ messages)
4. **Never removes system messages** or important context
5. **Frees approximately 25%** of the used space to give breathing room

**What You'll See:**
```
✂️ Pruned 6 old messages to maintain context (freed ~8,420 tokens)
```

**What This Means:**
- Old conversation history is removed to prevent overflow
- Your recent conversation (last few exchanges) is always preserved
- The agent can continue working without running out of space
- This happens automatically when needed

**What Gets Pruned (in order):**
1. ✅ Oldest user questions from earlier in the conversation
2. ✅ Oldest agent responses from earlier in the conversation
3. ✅ Old tool results that are no longer relevant
4. ❌ System prompts (never pruned)
5. ❌ Recent messages (last 4+ exchanges always preserved)

**Preservation Strategy:**
```
[Conversation Timeline]

Message 1  (15 min ago) ──┐
Message 2  (14 min ago)   │
Message 3  (12 min ago)   ├─── Eligible for pruning (if needed)
Message 4  (10 min ago)   │
Message 5  (8 min ago)  ──┘
Message 6  (5 min ago)  ──┐
Message 7  (3 min ago)    ├─── Always preserved (recent context)
Message 8  (1 min ago)    │
Message 9  (now)        ──┘
```

#### 3. **Real-Time Status Monitoring** 📊

The status bar at the bottom of LogAI shows your current context usage with color coding:

```
Status: Ready | Cache: 47 hits (82%) | Context: 45% | Model: gpt-4o-mini
                                                ^^^^
                                         Color-coded indicator
```

**Color Meanings:**
- **🟢 Green (0-70%)** - Normal, plenty of space available
- **🟡 Yellow (71-85%)** - Warning, context filling up
- **🔴 Red (86-100%)** - Critical, automatic pruning active

---

## 2. Status Bar Indicator Guide

### Understanding the Context Display

The status bar at the bottom of LogAI continuously shows your context usage:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Status: Ready | Cache: 47 hits (82%) | Context: 45% | Model: gpt-4o │
└─────────────────────────────────────────────────────────────────────┘
```

The **Context:** section shows how full your context window is with color coding.

### Green Zone: 0-70% (Normal Operation)

```
Context: 45%   [displayed in GREEN]
```

**What It Means:**
- Plenty of space available in your context window
- No action needed from the system or from you
- Queries are operating normally
- Both history and results fit comfortably

**What To Do:**
- Nothing! Keep working normally
- Ask complex questions without worry
- Run large CloudWatch queries
- Continue multi-step investigations

**Example Session in Green Zone:**
```
You: List my Lambda log groups
Agent: Here are your 12 Lambda log groups...
Status Bar: Context: 15% [GREEN]

You: Show me errors from /aws/lambda/api-handler
Agent: I found 45 errors in the last hour...
Status Bar: Context: 38% [GREEN]

You: What are the most common error types?
Agent: The most common errors are...
Status Bar: Context: 52% [GREEN]

[All is well - plenty of space remaining]
```

### Yellow Zone: 71-85% (Warning)

```
Context: 78%   [displayed in YELLOW]
```

**What It Means:**
- Context window is filling up
- Automatic pruning may occur soon if you continue
- Not critical yet, but approaching limits
- Large results are being cached to slow growth

**What To Do:**
- **If investigation is nearly complete:** Continue and finish your current analysis
- **If investigation will continue:** Consider starting a new chat soon to reset context
- **If asking exploratory questions:** This is a good time to wrap up this conversation thread

**What Will Happen:**
- Large results are automatically cached (you may see cache notifications)
- If context reaches 80%+, automatic pruning will begin
- Recent conversation is always preserved

**Example Session Entering Yellow Zone:**
```
You: Analyze all errors across Lambda functions in the last 6 hours
Agent: [Fetches large dataset]
Status Bar: Context: 72% [YELLOW]  ← Just entered warning zone

[LogAI automatically caches the large result]
💾 Cached large result: 3,420 events, 78,000 tokens → 4,100 token summary

Agent: I found 3,420 errors across 8 Lambda functions...
Status Bar: Context: 74% [YELLOW]

[You can continue, but be aware you're approaching limits]
```

**When to Start a New Chat:**
```
✅ Good time to start new chat:
   - Switching to a different time range or service
   - Moving from error investigation to performance analysis
   - Shifting to a completely different topic
   - You need the full history for an upcoming complex analysis

⏸️ OK to continue current chat:
   - Finishing up current investigation (1-2 more queries)
   - Asking clarifying questions about recent results
   - Getting specific details from cached results
```

### Red Zone: 86-100% (Critical)

```
Context: 92% (!)   [displayed in RED with warning indicator]
```

**What It Means:**
- Context window is nearly full
- Automatic pruning is actively removing old messages
- System is working hard to maintain space
- You're approaching maximum capacity

**What To Do:**
- **Finish your current query** and review results
- **Export or save** any important findings
- **Start a new chat** to reset context and continue with fresh space

**What's Happening Automatically:**
- Old messages are being removed (FIFO - oldest first)
- Large results are being cached aggressively
- Recent conversation (last 4+ messages) is preserved
- System notifications will inform you of actions taken

**Example Session in Red Zone:**
```
You: Now compare these errors with production logs from last week
Agent: [Fetches another large dataset]
Status Bar: Context: 87% [RED]

✂️ Pruned 8 old messages to maintain context (freed ~12,340 tokens)

Agent: Comparing current errors with last week's data...
Status Bar: Context: 81% [RED] (!)

[Pruning bought you some breathing room, but you're still in critical zone]

You: What's the key difference?
Agent: The main difference is...
Status Bar: Context: 84% [RED] (!)

[Time to finish up and start a new chat]
```

**How to Reset:**
```
Option 1: Use the /clear command
/clear
Status Bar: Context: 5% [GREEN]  ← Fresh start, same session

Option 2: Exit and restart LogAI
/quit
logai
Status Bar: Context: 5% [GREEN]  ← Completely fresh session
```

### Visual Guide: Context Zones

```
Context Window Utilization
──────────────────────────────────────────────────────────────

  0%  ├────────────────────────────────────┤
      │                                    │  🟢 GREEN ZONE
      │     Plenty of Space                │  Normal Operation
      │     No Action Needed               │  Keep Working!
 70%  ├────────────────────────────────────┤
      │                                    │  🟡 YELLOW ZONE
      │     Filling Up                     │  Warning - Monitor Usage
      │     Consider Wrapping Up Soon      │  Pruning May Start Soon
 85%  ├────────────────────────────────────┤
      │                                    │  🔴 RED ZONE
      │     Nearly Full                    │  Critical - Pruning Active
      │     Auto-Pruning Active            │  Finish & Start New Chat
100%  └────────────────────────────────────┘
```

---

## 3. Toast Notifications Guide

LogAI displays toast notifications (temporary pop-up messages) to inform you about context management events. Here's what each notification means and what to do:

### Cache Notifications

#### "Cached large result: X events, XX,XXX tokens → X,XXX token summary"

```
💾 Cached large result: 1,847 events, 42,315 tokens → 2,450 token summary
```

**What It Means:**
- A CloudWatch query returned a large result
- The full result was saved to disk cache
- A compact summary was sent to the agent instead
- Token reduction of 80-95% achieved

**What To Do:**
- ✅ **Nothing!** This is working as designed
- The agent can still access full details if needed
- Your results are preserved and available
- Conversation can continue without filling context

**Technical Details:**
- Full results stored in: `~/.logai/cache/results/`
- Cache expires after: 1 hour (configurable)
- Agent can fetch details using: `FetchCachedResultTool`

**Example Flow:**
```
You: Show me all Lambda timeout errors in the last 24 hours

[LogAI queries CloudWatch → 3,200 events, 89,000 tokens]

💾 Cached large result: 3,200 events, 89,000 tokens → 4,800 token summary

Agent: I found 3,200 timeout errors across 15 Lambda functions.
       The most affected functions are:
       1. api-handler (847 timeouts)
       2. data-processor (623 timeouts)
       3. auth-service (401 timeouts)

You: Show me details for the api-handler timeouts

[Agent uses FetchCachedResultTool to get specific events]

Agent: Here are the specific timeout errors for api-handler...
```

#### "Failed to cache large result"

```
⚠️ Failed to cache large result
```

**What It Means:**
- System attempted to cache a large result but encountered an error
- The full result was sent to context instead (not ideal)
- This may cause context to fill up faster than normal
- Potential issues: disk space, permissions, or cache corruption

**What To Do:**
- ⚠️ **Monitor your context usage** - check status bar
- Consider starting a new chat soon to avoid hitting limits
- Check available disk space: `df -h ~/.logai/cache`
- Check cache directory permissions
- If issue persists, see [Troubleshooting](#troubleshooting)

**Troubleshooting Steps:**
```bash
# Check disk space
df -h ~/.logai/cache

# Check permissions
ls -la ~/.logai/cache

# Clear cache and retry
/cache clear

# Restart LogAI
/quit
logai
```

### History Pruning Notifications

#### "Pruned X old messages to maintain context (freed ~X tokens)"

```
✂️ Pruned 6 old messages to maintain context (freed ~8,420 tokens)
```

**What It Means:**
- Context window reached 80%+ utilization
- System automatically removed old messages to make room
- Recent conversation (last 4+ messages) was preserved
- Specified number of tokens freed up for new content

**What To Do:**
- ✅ **If recent context is sufficient:** Continue your investigation
- ⚠️ **If you need full history:** Start a new chat to avoid losing important context
- 💡 **Best practice:** Export findings before pruning becomes frequent

**What Was Removed:**
- Oldest user questions (FIFO order)
- Oldest agent responses
- Old tool results no longer relevant
- **Not removed:** System prompts, recent messages

**Example:**
```
[After several large queries...]
Status Bar: Context: 82% [YELLOW]

✂️ Pruned 6 old messages to maintain context (freed ~8,420 tokens)

Status Bar: Context: 67% [GREEN]

[Old conversation removed, recent context preserved, space freed]
```

**When This Is Normal:**
```
✅ Normal scenarios for pruning:
   - Long investigation session (10+ queries)
   - Multiple large CloudWatch queries
   - Complex multi-step analysis
   - Working with verbose log output

⚠️ Concerning scenarios (indicate you should start new chat):
   - Pruning happens after just 3-4 queries
   - Pruning happens multiple times in succession
   - Status bar stays in RED zone despite pruning
```

### Context Warning Notifications

#### "Context window XX% full"

```
ℹ️ Context window 74% full
```

**What It Means:**
- Informational update about context utilization
- Displayed when crossing 70% threshold
- No automatic action taken yet
- Just making you aware of the current state

**What To Do:**
- ℹ️ **Acknowledge and monitor** - keep an eye on status bar
- Plan to wrap up or start new chat soon
- Consider whether you need full history for upcoming queries

#### "Context window XX% full (!)"

```
⚠️ Context window 92% full (!)
```

**What It Means:**
- Critical warning - context is nearly full (90%+)
- Automatic pruning is active
- You're approaching maximum capacity
- Further queries may trigger aggressive pruning

**What To Do:**
- 🛑 **Finish current investigation** and save findings
- 🆕 **Start a new chat** to reset context
- 📋 **Export important results** before clearing

---

## 4. Best Practices

### For Long Analysis Sessions

#### Monitor the Status Bar
- **Glance at context percentage** periodically during investigations
- **Pay attention to color changes** from green → yellow → red
- **Plan ahead** when you see yellow (71%+)

```
Good Habit:
Every 3-4 queries → Quick glance at status bar → Assess whether to continue
```

#### Know When to Start a New Chat

**🟢 Continue Current Chat When:**
- Status bar is green (0-70%)
- You're doing quick follow-up queries
- Investigation is nearly complete
- Recent context is all you need

**🟡 Consider Starting New Chat When:**
- Status bar is yellow (71-85%)
- You're switching topics or time ranges
- Investigation is getting long (10+ queries)
- You need full conversation history going forward

**🔴 Definitely Start New Chat When:**
- Status bar is red (86%+)
- You see multiple pruning notifications
- Investigation is changing direction
- You need reliable access to full context

**How to Start Fresh:**
```
Option 1: Clear current conversation
/clear

Option 2: Exit and restart (nuclear option)
/quit
logai
```

### For Large Log Queries

#### Don't Worry About Query Size
- Caching automatically handles results up to 10,000+ events
- The system is designed to work with large CloudWatch queries
- Focus on asking the right questions, not limiting query size

**Example - Don't Do This:**
```
❌ BAD: Self-limiting to avoid context issues
You: Show me errors from the last 5 minutes only
[Artificially limiting to avoid large results]

✅ GOOD: Ask what you actually need
You: Show me all errors from the last 24 hours
[Let the system handle the size]
```

#### Request Specific Details When Needed
If you want specific information from cached results, just ask:

```
You: Show me timeout errors from the last 24 hours

💾 Cached large result: 2,100 events, 58,000 tokens → 3,200 token summary

Agent: I found 2,100 timeout errors. Most common in api-handler...

You: Show me the actual error messages for api-handler timeouts

[Agent uses FetchCachedResultTool to retrieve specific details]

Agent: Here are the specific error messages:
       1. "Task timed out after 30.03 seconds"
       2. "Task timed out after 29.98 seconds"
       ...
```

### For Complex Investigations

#### Break Into Focused Sessions
Instead of one long session covering everything, break complex investigations into focused chats:

**❌ Bad Approach (Single Long Session):**
```
Chat #1:
- Check errors (context: 45%)
- Check performance (context: 68%)
- Check security (context: 82%)
- Compare with last week (context: 94% - RED!)
- Try to analyze trends (PRUNING, losing context)
- Attempt root cause (confused, missing history)
```

**✅ Good Approach (Multiple Focused Sessions):**
```
Chat #1 - Error Analysis:
- Identify error patterns → Save findings
- Context stays in green zone

Chat #2 - Performance Analysis:
- Analyze response times → Save findings
- Context stays in green zone

Chat #3 - Comparison:
- Compare findings from Chat #1 and #2
- Context stays manageable
```

#### Use Multiple Chats for Different Aspects

**Strategy: One Chat Per Topic**
```
/quit → logai     [Chat #1: Lambda errors]
                  Focus: Error investigation for Lambda functions
                  Context: Stays green, full history available

/quit → logai     [Chat #2: API Gateway performance]
                  Focus: Performance metrics for API Gateway
                  Context: Fresh start, no old Lambda context

/quit → logai     [Chat #3: Comparison & Summary]
                  Focus: Compare findings, create summary
                  Context: Clean slate for synthesis
```

#### Export Findings Before Starting New Chat

Don't lose important information when starting fresh:

```
Current Chat (Context: 85% - YELLOW):
You: What are the key findings from this investigation?
Agent: The main findings are:
       1. API timeouts increased 300% since deployment
       2. Errors concentrated in us-east-1 region
       3. Pattern shows database connection issues

[COPY THESE FINDINGS - Save to notes, documentation, ticket, etc.]

Then start new chat:
/clear

You: Based on finding #3, show me database connection errors in detail...
```

### For Production Monitoring

#### Set Up Multiple Short Sessions
For production monitoring, use short focused sessions rather than one long session:

```
Morning Check (9:00 AM):
"Show me overnight errors" → Review → /clear

Midday Check (1:00 PM):
"Show me errors in the last 4 hours" → Review → /clear

Afternoon Check (5:00 PM):
"Show me errors since midday" → Review → /clear
```

#### Use Specific Time Windows
More specific queries are more efficient:

```
✅ GOOD (Specific):
"Show me errors in the last 2 hours"
[Results: 150 events, 4,200 tokens - fits in context]

❌ LESS EFFICIENT (Too Broad):
"Show me all errors today"
[Results: 2,800 events, 78,000 tokens - will be cached]
```

---

## 5. Frequently Asked Questions

### General Questions

#### Q: What happens to cached results when I close LogAI?

**A:** Cached results are stored on disk and persist between sessions:

- **Storage Location:** `~/.logai/cache/results/`
- **Time-to-Live (TTL):** 1 hour by default (configurable)
- **Automatic Cleanup:** Expired results are deleted automatically
- **Manual Cleanup:** Use `/cache clear` command

**Example Timeline:**
```
10:00 AM - Run query → Result cached
10:30 AM - Close LogAI
10:45 AM - Reopen LogAI → Cached result still available
11:05 AM - Result expires (1 hour TTL) → Automatically deleted
```

#### Q: Can I disable context management?

**A:** Not recommended, but you can adjust settings:

**⚠️ Warning:** Disabling these features may cause context overflow and agent failures.

```bash
# In .env file:

# Disable result caching (NOT RECOMMENDED)
LOGAI_ENABLE_RESULT_CACHING=false
# Risk: Context will fill quickly with large results

# Disable history pruning (NOT RECOMMENDED)
LOGAI_ENABLE_HISTORY_PRUNING=false
# Risk: Context will eventually overflow and cause failures

# Adjust thresholds (SAFER)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000  # Cache only very large results
# Allows more results in context, but safer than disabling
```

**Recommendation:** Keep both features enabled and adjust thresholds if needed.

#### Q: How do I know if a result was cached?

**A:** You'll see a toast notification:

```
💾 Cached large result: 1,847 events, 42,315 tokens → 2,450 token summary
```

**Also visible in:**
- Chat conversation (if notifications are enabled)
- Debug logs (`LOGAI_LOG_LEVEL=DEBUG`)
- Tool sidebar (shows cache_id in result summary)

#### Q: Will pruning remove important information?

**A:** No, the pruning strategy is designed to preserve important context:

**What's Preserved:**
- ✅ System prompts (never pruned)
- ✅ Recent messages (last 4+ exchanges)
- ✅ Any messages marked as "important"
- ✅ Active tool results

**What's Removed (FIFO order):**
- ❌ Oldest user questions
- ❌ Oldest agent responses
- ❌ Old tool results

**Example:**
```
[Conversation with 15 messages, need to prune 6]

Messages 1-6  (Oldest) → PRUNED
Messages 7-11          → PRUNED (if needed)
Messages 12-15 (Recent) → ALWAYS PRESERVED
```

**If you need full history:**
- Don't rely on pruning - start a new chat when needed
- Export important findings before context gets full
- Use multiple focused sessions

#### Q: Does context management affect response quality?

**A:** No - the system is designed to maintain quality:

**How Quality is Preserved:**

1. **Smart Summaries:**
   - Cached results include key statistics, patterns, and sample events
   - Agent receives all critical information in compact form
   - Summaries designed to answer most questions without fetching

2. **On-Demand Details:**
   - If agent needs specific details, it can fetch them using `FetchCachedResultTool`
   - Agent automatically requests more data when summary isn't sufficient
   - You can also explicitly ask for details

3. **Recent Context:**
   - Pruning always preserves recent conversation
   - Agent always has full context for current investigation
   - Historical context removed only when no longer relevant

**Example - Quality Maintained:**
```
You: Analyze errors from all Lambda functions in the last 24 hours

💾 Cached large result: 4,200 events, 112,000 tokens → 6,100 token summary

Agent: [Receives summary with]:
       - Total event count: 4,200
       - Error breakdown by function
       - Time distribution
       - Common error patterns
       - Sample events (50 most relevant)

Agent: I found 4,200 errors across 18 Lambda functions.
       The most critical issue is in api-handler (1,243 errors)...

[HIGH QUALITY response despite working with summary]

You: Show me specific error messages for api-handler

[Agent fetches full details for api-handler specifically]

Agent: Here are the actual error messages from api-handler:
       [Detailed list of specific errors]

[COMPLETE DETAILS when requested]
```

### Troubleshooting Questions

#### Q: What if agent seems to "forget" early conversation?

**A:** This indicates context was pruned:

**Why It Happens:**
- Context window filled up (80%+)
- Automatic pruning removed old messages
- Early conversation no longer in context

**Solution:**
1. **For current session:** Accept that old context is gone, continue with recent context
2. **For future:** Start a new chat when you see yellow (71%+) status
3. **Best practice:** Break long investigations into multiple focused sessions

**Example:**
```
[After 12 queries, context at 84%]

You: Remember that error pattern we saw at the beginning?

Agent: I don't have that information in the current context.
       Could you describe the pattern you're referring to?

[Old context was pruned - agent only has recent messages]

Solution: Start new chat and be more specific:
You: Show me timeout errors from /aws/lambda/api-handler,
     then analyze the pattern
```

#### Q: What if responses slow down significantly?

**A:** This may indicate context window is full:

**Symptoms:**
- Responses take 30+ seconds
- Status bar shows red (86%+)
- Multiple pruning notifications
- Agent responses are less coherent

**Causes:**
- Context window nearly full
- Model spending more time processing large context
- Automatic pruning creating fragmented context

**Solutions:**
```
Immediate fix:
/clear
[Clears conversation, resets context]

Or restart:
/quit
logai
[Completely fresh start]

Prevention:
- Start new chat when status bar shows yellow
- Break long investigations into focused sessions
- Monitor context usage during session
```

#### Q: What if I see cache errors repeatedly?

**A:** This indicates a problem with the cache system:

**Common Causes:**
1. **Disk Space:** Cache directory is full
2. **Permissions:** Can't write to cache directory
3. **Corruption:** Cache database is corrupted
4. **Configuration:** Invalid cache settings

**Diagnostic Steps:**
```bash
# Check disk space
df -h ~/.logai/cache

# Check permissions
ls -la ~/.logai/cache

# Check cache size
du -sh ~/.logai/cache

# View cache statistics
# (in LogAI)
/cache status
```

**Solutions:**
```bash
# Clear cache
# (in LogAI)
/cache clear

# Or manually delete cache
rm -rf ~/.logai/cache
mkdir -p ~/.logai/cache

# Check .env settings
grep CACHE .env

# Restart LogAI
/quit
logai
```

#### Q: How do I check current cache size and utilization?

**A:** Use the `/cache status` command:

```
You: /cache status

Cache Statistics:
  Total Entries: 127
  Total Size: 45.32 MB
  Cache Hits: 342
  Cache Misses: 89
  Hit Rate: 79.4%

Result Cache:
  Cached Results: 23
  Cache Size: 38.15 MB
  Oldest Entry: 45 minutes ago
  Newest Entry: 2 minutes ago
```

**Interpreting Results:**
- **High hit rate (70%+):** Cache is working well
- **Low hit rate (<50%):** Querying diverse data sets
- **Large size (>400MB):** Consider clearing old entries
- **Many entries (>100):** Normal for long sessions

### Configuration Questions

#### Q: How do I change when results get cached?

**A:** Adjust the `CACHE_LARGE_RESULTS_THRESHOLD` setting:

```bash
# In .env file:

# Default: Cache results over 10,000 tokens
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000

# Cache larger results only (less aggressive)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000

# Cache smaller results (more aggressive)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=5000
```

**Guidance:**
- **Lower threshold (5,000):** More aggressive caching, slower context growth
- **Default (10,000):** Balanced approach, works well for most use cases
- **Higher threshold (20,000):** Less caching, context fills faster

#### Q: How do I change when history gets pruned?

**A:** The threshold isn't directly configurable, but pruning starts at 80% utilization. However, you can influence behavior:

```bash
# In .env file:

# Disable pruning entirely (NOT RECOMMENDED)
LOGAI_ENABLE_HISTORY_PRUNING=false

# Adjust how much context different components can use
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive

# Strategies:
# - adaptive: Balanced (default)
# - history-focused: Preserve more conversation history
# - result-focused: Allow larger tool results
```

**Example Effects:**
```
ADAPTIVE (default):
- History: 55% of available space
- Results: 45% of available space
- Balanced approach

HISTORY_FOCUSED:
- History: 65% of available space
- Results: 35% of available space
- Preserves more conversation, but limits result size

RESULT_FOCUSED:
- History: 40% of available space
- Results: 60% of available space
- Allows larger results, but prunes history sooner
```

---

## 6. Advanced Configuration

For power users who want to customize context management behavior.

### Environment Variables Reference

Add these to your `.env` file:

```bash
#═══════════════════════════════════════════════════════════════
# CONTEXT MANAGEMENT CONFIGURATION
#═══════════════════════════════════════════════════════════════

# ── Result Caching ──────────────────────────────────────────

# Enable/disable result caching
# Default: true
# Impact: When false, all results go directly to context
LOGAI_ENABLE_RESULT_CACHING=true

# Token threshold for caching results
# Default: 10000
# Range: 1000-50000
# Guidance: Lower = more aggressive caching, slower context growth
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000

# Cache time-to-live in seconds
# Default: 3600 (1 hour)
# Range: 600-86400 (10 minutes to 24 hours)
# Impact: How long cached results are retained
LOGAI_CACHE_TTL_SECONDS=3600

# Maximum cache size in MB
# Default: 100
# Range: 10-1000
# Impact: Maximum disk space used for cached results
LOGAI_CACHE_MAX_SIZE_MB=100

# Enable incremental fetching from cache
# Default: true
# Impact: Allows fetching cached results in chunks
LOGAI_ENABLE_INCREMENTAL_FETCH=true

# Maximum events per cached chunk
# Default: 100
# Range: 10-500
# Impact: Size of chunks when fetching from cache
LOGAI_MAX_EVENTS_PER_CHUNK=100

# ── History Pruning ─────────────────────────────────────────

# Enable/disable automatic history pruning
# Default: true
# Impact: When false, context may overflow
LOGAI_ENABLE_HISTORY_PRUNING=true

# Number of recent messages to always preserve
# Default: 20
# Range: 4-50
# Impact: Minimum conversation context kept during pruning
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=20

# Enable history summarization (future feature)
# Default: false
# Impact: Summarize pruned history instead of deleting
LOGAI_ENABLE_HISTORY_SUMMARIZATION=false

# ── Context Allocation ──────────────────────────────────────

# Context budget allocation strategy
# Options: adaptive, history-focused, result-focused
# Default: adaptive
# Impact: How context space is divided between history and results
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive

# ── Context Window Limits ───────────────────────────────────

# Model context window size (auto-detected if not set)
# Examples:
#   - Claude 3.5 Sonnet: 200000
#   - GPT-4 Turbo: 128000
#   - GPT-4o: 128000
#   - Gemini 2.5 Pro: 1000000 (1M!)
# LOGAI_CONTEXT_WINDOW_SIZE=200000

# Safety buffer (tokens reserved for safety margin)
# Default: 5000
# Range: 1000-20000
# Impact: Prevents accidental overflow
LOGAI_CONTEXT_WINDOW_BUFFER=5000

# Maximum tokens for tool results
# Default: 50000
# Range: 10000-100000
# Impact: Hard limit on result size in context
LOGAI_MAX_RESULT_TOKENS=50000

# Maximum tokens for conversation history
# Default: 80000
# Range: 20000-150000
# Impact: Hard limit on history size in context
LOGAI_MAX_HISTORY_TOKENS=80000

# Maximum tokens for system prompt
# Default: 10000
# Range: 5000-20000
# Impact: Space allocated for system instructions
LOGAI_MAX_SYSTEM_PROMPT_TOKENS=10000

# Tokens reserved for model response
# Default: 8000
# Range: 4000-16000
# Impact: Space reserved for agent to generate response
LOGAI_RESERVE_RESPONSE_TOKENS=8000
```

### Configuration Profiles

Pre-configured profiles for common use cases:

#### Profile 1: Conservative (Maximize History Retention)

Best for: Long investigations where full conversation history is critical

```bash
# Aggressive caching to preserve context space
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=5000

# History-focused allocation
LOGAI_CONTEXT_ALLOCATION_STRATEGY=history-focused

# Keep more recent messages
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=30

# Longer cache retention
LOGAI_CACHE_TTL_SECONDS=7200  # 2 hours
```

**Effect:**
- More results are cached (5,000 token threshold vs 10,000 default)
- More space allocated to history (65% vs 55%)
- More recent messages preserved (30 vs 20)
- Cached results retained longer (2 hours vs 1)

#### Profile 2: Aggressive (Maximize Result Detail)

Best for: Detailed analysis of large result sets

```bash
# Less aggressive caching
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000

# Result-focused allocation
LOGAI_CONTEXT_ALLOCATION_STRATEGY=result-focused

# Fewer messages preserved (prune sooner)
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=10

# Allow larger results in context
LOGAI_MAX_RESULT_TOKENS=80000
```

**Effect:**
- Fewer results cached (20,000 token threshold)
- More space for results in context (60% vs 45%)
- History pruned more aggressively (10 messages vs 20)
- Can fit larger results in context (80K vs 50K tokens)

#### Profile 3: Balanced (Default)

Best for: General use, mixed workloads

```bash
# Default thresholds
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=20
LOGAI_CACHE_TTL_SECONDS=3600
```

**Effect:**
- Balanced approach for most use cases
- Adapts to conversation patterns
- Good for mix of small and large queries

#### Profile 4: Production Monitoring

Best for: Short sessions, real-time monitoring

```bash
# Cache even small results (short sessions)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=5000

# Short cache TTL (monitoring is time-sensitive)
LOGAI_CACHE_TTL_SECONDS=1800  # 30 minutes

# Small history window (quick checks)
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=8

# Result-focused (monitoring queries return data)
LOGAI_CONTEXT_ALLOCATION_STRATEGY=result-focused
```

**Effect:**
- Optimized for quick monitoring queries
- Short cache life (monitoring data is time-sensitive)
- Minimal history retention (not investigating, just checking)

### Testing Your Configuration

After changing configuration, test the behavior:

```bash
# Restart LogAI to pick up new configuration
/quit
logai

# Check configuration is loaded
/config

# Run a test query
"Show me errors from /aws/lambda/api-handler in the last hour"

# Monitor the status bar
[Watch Context: percentage]

# Check cache behavior
/cache status

# Run a large query to test caching
"Show me all Lambda errors in the last 24 hours"

# Verify notification appears
[Watch for "Cached large result..." notification]
```

### Troubleshooting Configuration Issues

**Problem: Caching is too aggressive**
```bash
# Solution: Raise threshold
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000
```

**Problem: Context fills too quickly**
```bash
# Solution: Lower caching threshold
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=5000

# And/or use history-focused allocation
LOGAI_CONTEXT_ALLOCATION_STRATEGY=history-focused
```

**Problem: Pruning happens too early**
```bash
# Solution: Use history-focused strategy
LOGAI_CONTEXT_ALLOCATION_STRATEGY=history-focused

# And/or preserve more messages
LOGAI_HISTORY_SLIDING_WINDOW_MESSAGES=30
```

**Problem: Not enough detail in results**
```bash
# Solution: Raise caching threshold
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=20000

# And/or use result-focused allocation
LOGAI_CONTEXT_ALLOCATION_STRATEGY=result-focused
```

---

## 7. Quick Reference Card

One-page summary for quick reference.

### Status Bar Color Codes

| Color | Range | Meaning | Action |
|-------|-------|---------|--------|
| **🟢 Green** | 0-70% | Normal - plenty of space | None - keep working |
| **🟡 Yellow** | 71-85% | Warning - filling up | Consider wrapping up soon |
| **🔴 Red** | 86-100% | Critical - pruning active | Finish up, start new chat |

### Toast Notifications

| Notification | Meaning | Action Required |
|--------------|---------|-----------------|
| 💾 Cached large result: X events... | Result cached to save space | ✅ None - working as designed |
| ✂️ Pruned X old messages... | History pruned to make room | ⚠️ Consider starting new chat if you need full history |
| ⚠️ Context window XX% full (!) | Critical - nearly full | 🛑 Finish up and start new chat |
| ⚠️ Failed to cache large result | Cache error occurred | ⚠️ Check disk space, consider restarting |

### When to Start a New Chat

| Scenario | Status Bar | Action |
|----------|------------|--------|
| Quick follow-up questions | 🟢 Green (0-70%) | Continue current chat |
| Investigation nearly done | 🟡 Yellow (71-85%) | Finish, then start new chat |
| Switching topics/time ranges | 🟡 Yellow (71-85%) | Start new chat now |
| Seeing pruning notifications | 🔴 Red (86%+) | Start new chat immediately |
| Context stays red despite pruning | 🔴 Red (86%+) | Start new chat immediately |

### Key Commands

```bash
/clear              # Clear conversation history (reset context)
/cache status       # View cache statistics
/cache clear        # Clear all cached data
/config             # View current configuration
/quit               # Exit LogAI
```

### Configuration Quick Reference

```bash
# In .env file:

# Caching threshold (default: 10000 tokens)
LOGAI_CACHE_LARGE_RESULTS_THRESHOLD=10000

# Enable/disable features
LOGAI_ENABLE_RESULT_CACHING=true      # Cache large results
LOGAI_ENABLE_HISTORY_PRUNING=true     # Prune old messages

# Allocation strategy (default: adaptive)
LOGAI_CONTEXT_ALLOCATION_STRATEGY=adaptive
# Options: adaptive, history-focused, result-focused

# Cache TTL (default: 3600 seconds = 1 hour)
LOGAI_CACHE_TTL_SECONDS=3600
```

### Best Practices Checklist

- ✅ Monitor status bar during long sessions
- ✅ Start new chat when context reaches yellow (71%+)
- ✅ Export findings before clearing or starting new chat
- ✅ Break complex investigations into focused sessions
- ✅ Don't limit query size - let caching handle it
- ✅ Use `/cache status` to check cache performance
- ✅ Clear cache if disk space becomes an issue

### Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Agent "forgot" early conversation | `/clear` and be more specific in new chat |
| Responses are slow | `/clear` or `/quit` → `logai` |
| Cache errors | `/cache clear` → restart LogAI |
| Context stays red | `/clear` or start new session |
| Need full query details | Ask agent to fetch specific details |

---

## Appendix: Technical Architecture

For technical users and developers who want to understand how the system works.

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Context Management System                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Budget     │  │   Result     │  │   History    │      │
│  │   Tracker    │  │   Cache      │  │   Pruner     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                    ┌───────▼────────┐                        │
│                    │  Orchestrator  │                        │
│                    └───────┬────────┘                        │
│                            │                                 │
│         ┌──────────────────┴──────────────────┐             │
│         │                                       │             │
│    ┌────▼────┐                           ┌────▼────┐        │
│    │   LLM   │                           │   UI    │        │
│    │ Provider│                           │ (Status │        │
│    │         │                           │  Bar)   │        │
│    └─────────┘                           └─────────┘        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Token Flow

```
CloudWatch Query
       │
       ▼
┌─────────────┐
│ Fetch Logs  │
│ (Raw Data)  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Token Counter                         │
│ ├─ Count tokens in result            │
│ └─ Check against threshold (10K)     │
└──────┬───────────────────────────────┘
       │
       ├─────────► tokens < 10K ────────┐
       │                                 │
       └─────────► tokens >= 10K        │
                          │              │
                          ▼              ▼
                   ┌─────────────┐  ┌────────────┐
                   │ Cache Result│  │ Add to     │
                   │ Create Sum. │  │ Context    │
                   └─────┬───────┘  │ Directly   │
                         │          └────────────┘
                         ▼
                   ┌─────────────┐
                   │ Add Summary │
                   │ to Context  │
                   │ (2-5K toks) │
                   └─────────────┘
```

### Budget Allocation

```
Context Window (Example: 128,000 tokens for GPT-4)
├─ Safety Buffer (5%): 6,400 tokens
├─ Response Reserve (4%): 5,120 tokens
├─ System Prompt (5%): 6,400 tokens
└─ Available for Content (86%): 110,080 tokens
    ├─ History (55%): 60,544 tokens
    └─ Results (45%): 49,536 tokens
```

**Allocation Strategies:**

```
ADAPTIVE (default):
├─ History: 55% of available content space
└─ Results: 45% of available content space

HISTORY_FOCUSED:
├─ History: 65% of available content space
└─ Results: 35% of available content space

RESULT_FOCUSED:
├─ History: 40% of available content space
└─ Results: 60% of available content space
```

### Pruning Algorithm

```python
# Pseudocode for history pruning

if context_utilization >= 80%:
    # Calculate target tokens to free (25% of current usage)
    target_free = current_tokens * 0.25

    # Identify prunable messages
    prunable = []
    for message in conversation_history:
        if message.is_system:
            continue  # Never prune system messages
        if message.is_recent (last 4 messages):
            continue  # Never prune recent messages
        if message.important:
            continue  # Never prune important messages
        prunable.append(message)

    # Select oldest messages until target reached
    tokens_freed = 0
    to_remove = []
    for message in prunable (oldest first):
        if tokens_freed >= target_free:
            break
        to_remove.append(message)
        tokens_freed += message.tokens

    # Remove selected messages
    for message in to_remove:
        conversation_history.remove(message)

    # Notify user
    notify(f"Pruned {len(to_remove)} messages, freed ~{tokens_freed} tokens")
```

### Cache Storage Structure

```
~/.logai/cache/
├── results/
│   ├── result_abc123.json          # Cached result metadata
│   ├── result_abc123_events.json   # Actual events data
│   ├── result_def456.json
│   └── result_def456_events.json
└── index.json                       # Cache index with TTL info
```

**Result Metadata:**
```json
{
  "cache_id": "result_abc123",
  "tool_name": "fetch_logs",
  "timestamp": "2026-02-12T10:30:00Z",
  "ttl_seconds": 3600,
  "expires_at": "2026-02-12T11:30:00Z",
  "event_count": 1847,
  "token_count": 42315,
  "summary": {
    "total_events": 1847,
    "time_range": "2026-02-12T09:30:00Z to 2026-02-12T10:30:00Z",
    "log_group": "/aws/lambda/api-handler",
    "error_count": 42,
    "sample_events": [...]
  }
}
```

---

**End of User Documentation**

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 12, 2026 | Tina | Initial draft for review |

## Review Checklist

- [ ] Technical accuracy verified
- [ ] All notifications documented
- [ ] Configuration options complete
- [ ] Examples are clear and realistic
- [ ] Best practices are actionable
- [ ] FAQ answers common questions
- [ ] Quick reference card is comprehensive
- [ ] Advanced configuration is accurate
- [ ] Visual elements enhance understanding
- [ ] Tone is user-friendly and reassuring

## Next Steps

1. **Review by George** - Technical accuracy and completeness
2. **Review by QA (Raoul)** - User experience and clarity
3. **Integration into LogAI docs** - Add to `docs/user-guide/`
4. **Create changelog entry** - Document for release notes
5. **Update README** - Add link to Context Management guide
