# LogAI Tools Summary - Quick Reference

**Prepared by**: Code Librarian (Hans)
**Date**: 2026-02-11
**Status**: Complete

## Executive Summary

LogAI provides **3 core tools** to the LLM agent for interacting with AWS CloudWatch logs. All tools support:
- ✅ Caching for performance
- ✅ PII sanitization for security
- ✅ Flexible time range formats
- ✅ Error handling and retry logic

---

## Tool Inventory

### 🔍 Quick Lookup Table

```
┌─────────────────────┬──────────────────────────────┬────────────────┬──────────────────┐
│ Tool Name           │ Purpose                      │ Category       │ Key Feature      │
├─────────────────────┼──────────────────────────────┼────────────────┼──────────────────┤
│ list_log_groups     │ Discover available groups    │ Inventory      │ Discovery        │
│ fetch_logs          │ Fetch logs from one group    │ Search & Fetch │ Single group     │
│ search_logs         │ Search across many groups    │ Search & Fetch │ Multi-group      │
└─────────────────────┴──────────────────────────────┴────────────────┴──────────────────┘
```

---

## Tool Details at a Glance

### 1️⃣ list_log_groups

**What it does**: Lists all CloudWatch log groups (discovery tool)

**When to use**:
- User: "What log groups do we have?"
- User: "Show me Lambda logs"
- Agent needs to find log group name

**Required params**: None (all optional)

**Optional params**:
- `prefix`: Filter by name prefix (e.g., "/aws/lambda/")
- `limit`: Max results to return (1-100, default 50)

**Returns**: List of log groups with metadata

**Example call**:
```python
await orchestrator.execute(
    "list_log_groups",
    prefix="/aws/lambda/",
    limit=25
)
```

---

### 2️⃣ fetch_logs

**What it does**: Fetches log events from a specific log group

**When to use**:
- User specifies log group: "Show me /aws/lambda/my-function logs"
- User asks for errors: "Find errors in API logs"
- User wants specific time range: "Logs from 3 AM yesterday"

**Required params**:
- `log_group`: Full CloudWatch log group name
- `start_time`: Start of time range

**Optional params**:
- `end_time`: End of time range (default: now)
- `filter_pattern`: Search pattern (e.g., "ERROR")
- `limit`: Max events (1-1000, default 100)

**Returns**: Sanitized log events with metadata

**Example call**:
```python
await orchestrator.execute(
    "fetch_logs",
    log_group="/aws/lambda/my-function",
    start_time="1h ago",
    filter_pattern="ERROR",
    limit=50
)
```

---

### 3️⃣ search_logs

**What it does**: Searches across multiple log groups simultaneously

**When to use**:
- User: "Find all 500 errors across services"
- User: "Search for timeout errors everywhere"
- Agent needs to correlate issues across services

**Required params**:
- `log_group_patterns`: Array of groups/prefixes to search
- `search_pattern`: What to find
- `start_time`: Start of time range

**Optional params**:
- `end_time`: End of time range (default: now)
- `limit`: Max total events (1-1000, default 100)

**Returns**: Events organized by log group

**Example call**:
```python
await orchestrator.execute(
    "search_logs",
    log_group_patterns=["/aws/lambda/", "/ecs/"],
    search_pattern="ERROR",
    start_time="1h ago"
)
```

---

## Time Format Support

### All tools accept these time formats:

**1. ISO 8601** (Recommended)
```
2024-01-15T10:30:00Z
```

**2. Relative** (Natural language)
```
1h ago, 30m ago, 2d ago, yesterday, 1w ago
```

**3. Epoch milliseconds** (Unix timestamp)
```
1705315800000
```

---

## Return Value Structure

### Success Response
```json
{
  "success": true,
  "count": 5,
  "data": {...},
  "sanitization": {
    "enabled": true,
    "redactions": {"email": 2, "ipv4": 1},
    "summary": "Redacted 3 sensitive items"
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Log group not found"
}
```

---

## Common Usage Patterns

### Pattern 1: List → Fetch
```
User: "Show Lambda logs from today"
  ↓
Agent calls list_log_groups(prefix="/aws/lambda/")
  ↓
Agent calls fetch_logs(log_group="...", start_time="1d ago")
  ↓
Agent responds with analysis
```

### Pattern 2: Search for Issue
```
User: "Find 500 errors"
  ↓
Agent calls search_logs(
  log_group_patterns=["/aws/"],
  search_pattern="500",
  start_time="1h ago"
)
  ↓
Agent organizes by service and responds
```

### Pattern 3: Automatic Retry on Empty Results
```
User: "Any errors?"
  ↓
Agent calls fetch_logs(...) → No results
  ↓
Orchestrator detects empty results
  ↓
Orchestrator nudges agent to retry with:
  - Expanded time range (6h, 24h, 7d)
  - Broader filter pattern
  - Different log groups
```

---

## Key Features

### 🔒 Security: PII Sanitization
- Automatically removes sensitive data
- Redacts: emails, credit cards, IPs, phone numbers, API keys, SSNs
- Configurable (enabled/disabled)
- Returns redaction counts for transparency

### ⚡ Performance: Caching
- Enabled by default
- 10-100x faster for repeated queries
- Configurable TTL (default 5 minutes)
- Transparent to agent

### 🔄 Resilience: Auto-Retry
- Detects empty results
- Expands time ranges automatically
- Suggests alternatives when groups not found
- Prevents premature giving up
- Max retry attempts: 3 (configurable)

### 📊 Flexibility: Multiple Formats
- Time ranges: ISO 8601, relative, epoch milliseconds
- Filter patterns: Simple strings, JSON patterns, complex expressions
- Result limits: Configurable 1-1000 events
- Log group prefixes: Wildcards supported

---

## Performance Guidelines

### Typical Response Times

| Operation | Time | Notes |
|-----------|------|-------|
| list_log_groups | 100-500ms | Very fast |
| fetch_logs (1h) | 200-800ms | Depends on volume |
| fetch_logs (24h) | 1-5s | May need filter |
| search_logs (3 groups) | 500-2s | Parallel search |
| search_logs (10+ groups) | 2-10s | Scales linearly |

### Optimization Tips

1. **Use narrow time ranges** when possible
2. **Add filter patterns** to reduce data
3. **Specify exact log groups** instead of prefixes
4. **Cache results** are 10-100x faster
5. **Limit results** to what's needed (use `limit` param)

---

## File Locations

### Implementation
- `src/logai/core/tools/cloudwatch_tools.py` - All 3 tools
- `src/logai/core/tools/registry.py` - Tool registry
- `src/logai/core/tools/base.py` - BaseTool class

### Tests
- `tests/unit/test_cloudwatch_tools.py` - Tool tests
- `tests/unit/test_orchestrator.py` - Integration tests

### Configuration
- `src/logai/config/settings.py` - Tool settings
- `src/logai/cli.py` - Tool registration

---

## Settings Configuration

```python
# In LogAISettings:

# Caching
cache_enabled: bool = True
cache_ttl_minutes: int = 5

# Sanitization
pii_sanitization_enabled: bool = True

# Retry behavior
max_tool_iterations: int = 10
max_retry_attempts: int = 3
auto_retry_enabled: bool = True

# CloudWatch
cloudwatch_region: str = "us-east-1"
max_log_events: int = 1000
```

---

## Error Handling

### Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Log group not found | Wrong name | Call list_log_groups() |
| No logs found | Time range too narrow | Expand to 24h or 7d |
| Too many logs | Range too broad | Add filter pattern |
| Future time | End time in future | Use "now" |
| Invalid pattern | Bad syntax | Check CloudWatch filter pattern docs |

### Retry Behavior

Agent automatically retries for:
1. Empty results (no logs found)
2. Log group not found
3. Partial results (incomplete data)
4. Intent without action (stated but not executed)

Each retry uses a different strategy and has max 3 attempts.

---

## Limitations

### Current Limitations
- ❌ No metrics (only logs)
- ❌ CloudWatch only (no multi-cloud)
- ❌ Single region per context
- ❌ No real-time streaming
- ❌ No structured analysis tool

### Planned Features
- [ ] Real-time log tailing
- [ ] CloudWatch Insights integration
- [ ] Multi-region support
- [ ] Metrics tools
- [ ] Anomaly detection
- [ ] Custom analysis tools

---

## Integration Points

### How Tools Connect

```
CLI Entry
  ↓
Tool Registration
  ↓
Tool Registry
  ↓
LLM Orchestrator
  ↓
LLM Provider (generates tool calls)
  ↓
Tool Execution
  ↓
CloudWatch DataSource
  ↓
AWS CloudWatch API
  ↓
Sanitizer (remove PII)
  ↓
Cache (store results)
  ↓
Response to Agent
```

### Tool Listeners

UI components can listen for tool calls:
```python
orchestrator.register_tool_listener(callback)
# Receives ToolCallRecord for each tool execution
```

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Tools | 3 |
| CloudWatch API Calls | 3 different operations |
| Support Time Formats | 3 (ISO 8601, relative, epoch) |
| Max Retry Attempts | 3 (default) |
| Cache TTL | 5 minutes (default) |
| Max Results | 1000 (configurable) |
| Min Results | 1 (configurable) |
| PII Types Redacted | 6+ types |
| Tool Categories | 2 |
| Implementation Files | 5 |
| Test Files | 2+ |

---

## Reference Links

- **Full Documentation**: `AVAILABLE_TOOLS_REFERENCE.md`
- **Tool Code**: `src/logai/core/tools/`
- **Tests**: `tests/unit/test_cloudwatch_tools.py`
- **Orchestrator**: `src/logai/core/orchestrator.py`

---

**Document Version**: 1.0
**Last Updated**: 2026-02-11
**Maintained By**: Code Librarian (Hans)
