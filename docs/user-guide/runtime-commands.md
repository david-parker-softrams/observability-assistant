# Runtime Commands Reference

While LogAI is running, you can use special slash commands to control the application, view statistics, and manage your session. All commands start with a forward slash `/`.

## Available Commands

### `/help`

Display help information showing all available commands.

**Usage:**
```
/help
```

**Example Output:**
```
Available Commands:

/help - Show this help message
/clear - Clear conversation history
/refresh - Update the list of log groups from AWS
/logs - Toggle log groups sidebar (left)
/tools - Toggle tool calls sidebar (right)
/cache status - Show cache statistics
/cache clear - Clear the cache
/model - Show current LLM model
/config - Show current configuration
/quit or /exit - Exit the application (or use Ctrl+C)

Usage Tips:
- Ask questions in natural language about your CloudWatch logs
- The assistant will use tools to fetch and analyze logs for you
- Log groups are pre-loaded at startup - use /refresh to update
- Responses are streamed in real-time
- PII sanitization is enabled by default
```

---

### `/refresh`

Update the list of CloudWatch log groups from AWS. LogAI automatically loads log groups at startup, but use this command when you need to refresh the list during your session.

**Usage:**
```
/refresh
```

**Example Output:**
```
⏳ Refreshing log groups from AWS... (52 found)
✓ Updated: Found 135 log groups (+12 new)
✓ Agent context updated
```

**When to Use:**
- After creating new log groups in AWS Console or via IaC tools
- After switching AWS profiles or regions (restart LogAI instead)
- When you suspect the list is outdated
- After deploying new services that create log groups
- When troubleshooting and a log group you expect isn't visible

**What It Does:**
1. Fetches fresh list of all log groups from AWS CloudWatch
2. Updates the agent's internal knowledge with the new list
3. Updates the log groups sidebar (if visible)
4. Replaces the old list completely

**Performance:**
- Typically completes in 1-3 seconds for small accounts (<500 groups)
- May take 10-30 seconds for large accounts (1000s of groups)
- Shows progress updates as it loads

**Note:** LogAI automatically loads log groups at startup, so you typically only need to refresh if you've made changes in AWS during your session.

---

### `/clear`

Clear the conversation history. This removes all previous messages from the current session but does not affect the cache.

**Usage:**
```
/clear
```

**Example Output:**
```
Conversation history cleared.
```

**When to Use:**
- Starting a new investigation
- Conversation context is getting too long
- You want to reset the agent's understanding
- Cleaning up before asking unrelated questions

**Note:** This does not clear the cache. Use `/cache clear` for that.

---

### `/cache status`

Show statistics about the cache including size, hit rate, and number of entries.

**Usage:**
```
/cache status
```

**Example Output:**
```
Cache Statistics:

Total Entries: 127
Total Size: 45.32 MB
Cache Hits: 342
Cache Misses: 89
Hit Rate: 79.4%

Cache Directory: /Users/yourname/.logai/cache
Max Size: 500 MB
Max Entries: 10000
```

**Understanding the Statistics:**

- **Total Entries** - Number of cached queries
- **Total Size** - Disk space used by cache
- **Cache Hits** - Number of times a cached result was reused
- **Cache Misses** - Number of times data had to be fetched from AWS
- **Hit Rate** - Percentage of requests served from cache (higher is better)

**When to Use:**
- Checking if cache is working effectively
- Determining if cache size should be increased
- Troubleshooting performance issues
- Understanding cost savings from caching

---

### `/cache clear`

Clear all cached data. This removes all entries from the cache database.

**Usage:**
```
/cache clear
```

**Example Output:**
```
Cache cleared. Removed 127 entries.
```

**When to Use:**
- Cache has stale data
- Testing without cached results
- Freeing up disk space
- Troubleshooting unexpected results

**Warning:** After clearing the cache, the next queries will be slower and will make fresh AWS API calls.

---

### `/model`

Show information about the currently configured LLM model.

**Usage:**
```
/model
```

**Example Output:**
```
LLM Configuration:

Provider: anthropic
Model: claude-3-5-sonnet-20241022
Streaming: Enabled
Max Tool Iterations: 10
```

**When to Use:**
- Verifying which model is being used
- Checking LLM configuration
- Troubleshooting model-specific issues
- Confirming provider settings

---

### `/config`

Show the current configuration including LLM provider, AWS settings, and application options.

**Usage:**
```
/config
```

**Example Output:**
```
Current Configuration:

LLM Provider: anthropic
LLM Model: claude-3-5-sonnet-20241022
AWS Region: us-east-1
AWS Profile: production
Log Groups Loaded: 135
PII Sanitization: Enabled
Cache Directory: /Users/yourname/.logai/cache
Cache Max Size: 500 MB
Cache TTL: 86400s
```

**When to Use:**
- Verifying configuration settings
- Checking which AWS region is active
- Confirming PII sanitization is enabled
- Troubleshooting configuration issues

---

### `/logs`

Toggle the visibility of the log groups sidebar. The sidebar displays all your CloudWatch log groups in alphabetical order on the left side of the interface.

**Usage:**
```
/logs
```

**Example Output:**
```
Log groups sidebar hidden.
```

Or:
```
Log groups sidebar shown.
```

**About the Log Groups Sidebar:**

When visible (default), the sidebar displays:
- Complete list of all CloudWatch log groups
- Count in title (e.g., "LOG GROUPS (135)")
- Alphabetically sorted names
- Smart truncation for long names
- Automatically updates when `/refresh` is used

**When to Use:**
- You want more screen space for the chat
- Quick reference to see what log groups are available
- Verify a specific log group exists
- See the total count of your log groups

**Tip:** The sidebar is shown by default. Toggle it off if you prefer a simpler interface or have a narrow terminal.

**Layout with Both Sidebars:**
```
┌─────────────┬────────────────────────┬──────────────┐
│ Log Groups  │   Chat Messages        │ Tool Calls   │
│ (left)      │   (center)             │ (right)      │
└─────────────┴────────────────────────┴──────────────┘
```

**Default Visibility:**

To change whether the sidebar is visible at startup, edit your `.env` file:
```bash
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true   # Show by default
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=false  # Hide by default
```

The `/logs` command toggles the sidebar during your session, regardless of the configuration setting.

---

### `/tools`

Toggle the visibility of the tool calls sidebar. The sidebar shows real-time information about which tools the agent is using and what results it receives.

**Usage:**
```
/tools
```

**Example Output:**
```
Tool calls sidebar hidden.
```

Or:
```
Tool calls sidebar shown.
```

**About the Tool Sidebar:**

When visible (default), the right sidebar displays:
- Tool names (e.g., `list_log_groups`, `fetch_logs`)
- Status indicators (◯ pending → ⏳ running → ✓ success / ✗ error)
- Parameters passed to each tool
- Results returned by tools
- Execution time and timestamps

**When to Use:**
- You want more screen space for the chat
- You want to see what the agent is doing behind the scenes
- Debugging unexpected behavior
- Understanding which tools are being called

**Tip:** The right sidebar is shown by default. Toggle it off if you prefer a simpler interface.

---

### `/quit` or `/exit`

Exit the LogAI application.

**Usage:**
```
/quit
```

Or:
```
/exit
```

**Example Output:**
```
Use Ctrl+C or Ctrl+Q to quit the application.
```

**Note:** The preferred way to exit is using keyboard shortcuts:
- **Ctrl+C** - Interrupt and exit
- **Ctrl+Q** - Quit gracefully
- **Ctrl+D** - End of input (also exits)

---

## Command Usage Tips

### Commands are Not Case-Sensitive

All slash commands work regardless of case:

```
/help
/HELP
/Help
```

All produce the same result.

### Commands Must Start with `/`

Regular messages are sent to the AI agent. Only messages starting with `/` are treated as commands:

```
help                    → Sent to AI (asks for help with logs)
/help                   → Shows command help
```

### Unknown Commands

If you type an unknown command, LogAI will let you know:

```
/unknown
```

Output:
```
Unknown command: /unknown
Use /help to see available commands.
```

### Subcommands

Some commands have subcommands (like `/cache`):

```
/cache status           → Show cache statistics
/cache clear            → Clear the cache
```

If you use `/cache` without a subcommand:

```
/cache
```

Output:
```
Usage: /cache [status|clear]
```

---

## Keyboard Shortcuts

In addition to slash commands, LogAI supports these keyboard shortcuts:

| Shortcut | Action |
|----------|--------|
| **Ctrl+C** | Exit LogAI |
| **Ctrl+Q** | Exit LogAI |
| **Ctrl+D** | Exit LogAI |
| **Up Arrow** | Previous command in history |
| **Down Arrow** | Next command in history |
| **Page Up** | Scroll chat up |
| **Page Down** | Scroll chat down |
| **Home** | Scroll to top of chat |
| **End** | Scroll to bottom of chat |

---

## Common Workflows

### Starting a New Investigation

```
/clear                  → Clear previous conversation
/refresh                → Get latest log groups (if needed)
List all log groups     → Start fresh query
```

### After Deploying New Services

```
/refresh                → Load newly created log groups
Show me the new log groups → Verify they appear
```

### Checking Performance

```
/cache status           → Check hit rate
```

If hit rate is low, consider increasing cache size or TTL in your configuration.

### Troubleshooting

```
/config                 → Verify settings
/model                  → Check which LLM is active
/cache clear            → Clear stale data
/clear                  → Reset conversation
```

### Managing Screen Space

```
/logs                   → Hide left sidebar for more room
/tools                  → Hide right sidebar for more room
[Ask your questions]
/logs                   → Show sidebar to see log groups
/tools                  → Show sidebar to see tool details
```

**Tip:** You can hide both sidebars for maximum chat space, or show both for full visibility into what's available and what the agent is doing.

### Before Ending Session

```
/cache status           → Note statistics
/quit                   → Exit (or use Ctrl+C)
```

---

## Differences from Natural Language Queries

Understanding the difference between commands and natural language:

| Input | Type | Handled By | Purpose |
|-------|------|------------|---------|
| `/help` | Command | LogAI directly | Show command help |
| `help me find errors` | Query | AI agent | Search for errors in logs |
| `/clear` | Command | LogAI directly | Clear conversation |
| `clear the cache` | Query | AI agent | Will explain caching, doesn't clear it |
| `/refresh` | Command | LogAI directly | Update log groups list |
| `refresh my understanding` | Query | AI agent | Will re-explain something |
| `/logs` | Command | LogAI directly | Toggle log groups sidebar |
| `/tools` | Command | LogAI directly | Toggle tool sidebar |
| `what tools are available?` | Query | AI agent | Explains available tools |

**Rule of Thumb:** If you want to control LogAI itself, use a `/command`. If you want to work with logs, use natural language.

---

## Command History

LogAI remembers your previous inputs (both commands and queries). Use **Up Arrow** and **Down Arrow** to navigate through your history:

1. Type a command or query
2. Press **Enter** to execute
3. Press **Up Arrow** to see previous input
4. Press **Down Arrow** to see next input
5. Press **Enter** to re-execute

This works for both slash commands and natural language queries.

---

## See Also

- **[CLI Reference](cli-reference.md)** - Command-line arguments
- **[Features Overview](features.md)** - All LogAI features
- **[Configuration Guide](configuration.md)** - Environment variables and settings
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
