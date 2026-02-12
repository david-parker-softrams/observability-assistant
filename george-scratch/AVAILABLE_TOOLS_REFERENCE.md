# LogAI Available Tools Reference

**Last Updated**: 2026-02-11  
**Documentation Version**: 1.0

## Overview

This document provides a complete inventory of all tools/functions available to the LLM agent in LogAI. The agent uses these tools to interact with AWS CloudWatch, fetch logs, analyze data, and provide observability insights.

### Key Statistics

- **Total Tools**: 3
- **Tool Categories**: 2 (Inventory, Search & Fetch)
- **Data Source**: AWS CloudWatch Logs
- **Common Features**: Caching, PII Sanitization, Time Range Filtering

---

## Quick Reference

| Tool Name | Purpose | Category | Required Params |
|-----------|---------|----------|-----------------|
| `list_log_groups` | Discover available log groups | Inventory | None (optional prefix) |
| `fetch_logs` | Get logs from a specific group | Search & Fetch | `log_group`, `start_time` |
| `search_logs` | Search across multiple groups | Search & Fetch | `log_group_patterns`, `search_pattern`, `start_time` |

---

## Tool Categories

### Category 1: Inventory & Discovery
**Purpose**: Discover what data is available before querying  
**Tools**: `list_log_groups`

### Category 2: Search & Fetch
**Purpose**: Retrieve and search log data across time ranges  
**Tools**: `fetch_logs`, `search_logs`

---

## Detailed Tool Specifications

### 1. list_log_groups

**Tool Name**: `list_log_groups`

**Purpose**:
Lists all available CloudWatch log groups in the current AWS region. This is the discovery tool used to understand what log sources exist before querying logs. Users typically call this first to explore available options or when they don't specify a log group name.

**Category**: Inventory & Discovery

**Parameters**:
```json
{
  "type": "object",
  "properties": {
    "prefix": {
      "type": "string",
      "description": "Optional prefix to filter log groups (e.g., '/aws/lambda/', '/ecs/'). Leave empty to list all log groups."
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of log groups to return (default: 50, max: 100)",
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": []
}
```

**Parameter Details**:
- `prefix` (optional, string):
  - Filter results by log group name prefix
  - Common prefixes: `/aws/lambda/`, `/ecs/`, `/aws/apigateway/`, `/aws/rds/`
  - Example: `prefix="/aws/lambda/"` returns only Lambda function logs
  - Default: None (lists all groups)

- `limit` (optional, integer):
  - Maximum number of results to return
  - Default: 50
  - Maximum: 100
  - Minimum: 1

**Return Type**: 
```json
{
  "success": true,
  "log_groups": [
    {
      "name": "/aws/lambda/function-name",
      "created": 1704067200000,
      "retention_in_days": 30,
      "stored_bytes": 1048576
    }
  ],
  "count": 1,
  "prefix": "/aws/lambda/"
}
```

**Return Fields**:
- `success` (boolean): Indicates if operation was successful
- `log_groups` (array): List of log group objects
  - `name` (string): Full log group name
  - `created` (number): Creation timestamp in milliseconds
  - `retention_in_days` (number): Log retention period
  - `stored_bytes` (number): Total data stored in group
- `count` (number): Total number of log groups returned
- `prefix` (string): The prefix used for filtering (if any)

**Example Usage Scenarios**:
1. User: "What log groups do we have?"
   - Agent: Calls `list_log_groups()` to discover all available groups

2. User: "Show me Lambda logs"
   - Agent: Calls `list_log_groups(prefix="/aws/lambda/")` to find Lambda-related groups

3. User: "Any ECS logs?"
   - Agent: Calls `list_log_groups(prefix="/ecs/")` to find ECS container logs

**Error Handling**:
- Returns `success: false` if AWS API fails
- Returns empty `log_groups` array if no matches found
- Handles rate limiting gracefully with built-in retries

**Caching**: Enabled  
- Cache key: `query_type`, `prefix`, `limit`
- TTL: Configured in settings

**File Location**: 
- Implementation: `src/logai/core/tools/cloudwatch_tools.py` (lines 13-125)
- Tests: `tests/unit/test_cloudwatch_tools.py`

**When Agent Uses This**:
- Initial log group discovery
- When user doesn't specify a log group name
- When a specified log group isn't found (retry strategy)
- To suggest available alternatives to user
- When expanding investigation scope

---

### 2. fetch_logs

**Tool Name**: `fetch_logs`

**Purpose**:
Fetches actual log events from a specific CloudWatch log group within a time range. This is the primary tool for retrieving log data for analysis. Supports time range filtering and CloudWatch filter patterns for targeted searching. All logs are automatically sanitized to remove PII before being returned to the LLM.

**Category**: Search & Fetch

**Parameters**:
```json
{
  "type": "object",
  "properties": {
    "log_group": {
      "type": "string",
      "description": "The CloudWatch log group name (e.g., '/aws/lambda/my-function')"
    },
    "start_time": {
      "type": "string",
      "description": "Start of time range. Supports ISO 8601 (2024-01-15T10:00:00Z), relative ('1h ago', '30m ago', '2d ago', 'yesterday'), or epoch ms"
    },
    "end_time": {
      "type": "string",
      "description": "End of time range. Same formats as start_time. Defaults to 'now' if not specified."
    },
    "filter_pattern": {
      "type": "string",
      "description": "CloudWatch filter pattern to search for specific content. Examples: 'ERROR', '\"Exception\"', '{ $.level = \"error\" }'"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of log events to return (default: 100, max: 1000)",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": ["log_group", "start_time"]
}
```

**Parameter Details**:

- `log_group` (required, string):
  - Full CloudWatch log group name
  - Format: `/aws/service/function-name` or custom name
  - Example: `/aws/lambda/my-function`
  - No default; must be specified

- `start_time` (required, string):
  - Beginning of the time range to query
  - Formats accepted:
    - **ISO 8601**: `2024-01-15T10:30:00Z` or `2024-01-15T10:30:00+00:00`
    - **Relative**: `1h ago`, `30m ago`, `2d ago`, `yesterday`, `1w ago`
    - **Epoch milliseconds**: `1705315800000`
  - No default; must be specified

- `end_time` (optional, string):
  - End of the time range to query
  - Same formats as `start_time`
  - Default: `now` (current time)
  - Defaults to `start_time + 1 hour` if only start is provided

- `filter_pattern` (optional, string):
  - CloudWatch filter pattern for targeted searching
  - **Simple patterns**: `ERROR`, `timeout`, `"404"`
  - **JSON patterns**: `{ $.level = "ERROR" }`, `{ $.statusCode > 400 }`
  - **Multiple conditions**: `{ ($.level = "ERROR") && ($.service = "auth") }`
  - Default: None (returns all logs)

- `limit` (optional, integer):
  - Maximum number of log events to return
  - Default: 100
  - Maximum: 1000
  - Useful for controlling response size

**Return Type**:
```json
{
  "success": true,
  "log_group": "/aws/lambda/my-function",
  "events": [
    {
      "timestamp": 1704067200000,
      "message": "Function invoked with parameters: {...}",
      "log_stream": "2024/01/01/[$LATEST]abc123",
      "id": "36199749134368582180452323872461849873296891395491110912"
    }
  ],
  "count": 1,
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-01T01:00:00Z"
  },
  "filter_pattern": "ERROR",
  "sanitization": {
    "enabled": true,
    "redactions": {
      "email": 3,
      "ipv4": 1,
      "credit_card": 0
    },
    "summary": "Redacted 4 sensitive items"
  }
}
```

**Return Fields**:
- `success` (boolean): Indicates if operation was successful
- `log_group` (string): The log group queried
- `events` (array): Log events returned
  - `timestamp` (number): Event time in milliseconds
  - `message` (string): Log message (sanitized)
  - `log_stream` (string): Stream name within the group
  - `id` (string): CloudWatch event ID
- `count` (number): Number of events returned
- `time_range` (object): The actual time range used
  - `start` (string): ISO 8601 start time
  - `end` (string): ISO 8601 end time
- `filter_pattern` (string): The filter used (if any)
- `sanitization` (object): PII sanitization results
  - `enabled` (boolean): Whether sanitization is active
  - `redactions` (object): Count of redacted items by type
  - `summary` (string): Human-readable summary

**Example Usage Scenarios**:

1. User: "Show me Lambda logs from the last hour"
   - Agent calls: `fetch_logs(log_group="/aws/lambda/my-function", start_time="1h ago")`

2. User: "Find errors in the API logs"
   - Agent calls: `fetch_logs(log_group="/aws/apigateway/api", start_time="2024-01-15T10:00:00Z", filter_pattern="ERROR", limit=50)`

3. User: "Get JSON logs with status > 400"
   - Agent calls: `fetch_logs(log_group="/my-app/logs", start_time="1h ago", filter_pattern="{ $.status > 400 }")`

4. User: "What happened during the outage at 3 AM?"
   - Agent calls: `fetch_logs(log_group="/production/app", start_time="2024-01-15T03:00:00Z", end_time="2024-01-15T03:30:00Z", limit=200)`

**Error Handling**:
- Returns `success: false` if log group doesn't exist
- Returns `success: false` if time range is invalid
- Returns `success: false` if AWS API fails
- Returns empty `events` array if no matches found (common; triggers retry logic)

**Sanitization**:
- All logs are automatically sanitized to remove PII
- Redactions include: credit cards, email addresses, IPv4 addresses, phone numbers, etc.
- Sanitization is configurable (enabled/disabled per settings)
- Redaction counts are returned for transparency

**Caching**: Enabled
- Cache key: `query_type`, `log_group`, `start_time`, `end_time`, `filter_pattern`, `limit`
- TTL: Configured in settings

**Common Time Range Issues**:
- Time range too small: Returns no logs → agent expands range
- Time range too large: Returns too many logs → agent narrows range or adds filter
- Future time range: Returns no logs → agent suggests current time
- Timezone mismatches: ISO 8601 format recommended

**Retry Behavior**:
- If no logs found: Orchestrator suggests expanding time range
- If no logs found: Orchestrator suggests broadening filter pattern
- If not found error: Orchestrator calls `list_log_groups` to find correct group

**File Location**:
- Implementation: `src/logai/core/tools/cloudwatch_tools.py` (lines 127-310)
- Tests: `tests/unit/test_cloudwatch_tools.py`

**When Agent Uses This**:
- Primary tool for log retrieval
- After discovering log group with `list_log_groups`
- When user asks about logs from specific service
- When analyzing errors, performance, or specific events
- Most frequent tool in agent workflow

---

### 3. search_logs

**Tool Name**: `search_logs`

**Purpose**:
Searches across multiple CloudWatch log groups simultaneously for a specific pattern. This is the cross-service investigation tool used when you need to correlate events, find issues across multiple services, or don't know which service produced logs. Essential for distributed system troubleshooting.

**Category**: Search & Fetch

**Parameters**:
```json
{
  "type": "object",
  "properties": {
    "log_group_patterns": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of log group name patterns/prefixes to search. Example: ['/aws/lambda/', '/ecs/'] to search all Lambda and ECS logs"
    },
    "search_pattern": {
      "type": "string",
      "description": "CloudWatch filter pattern to search for across log groups. Example: 'ERROR', 'timeout', '\"500\"'"
    },
    "start_time": {
      "type": "string",
      "description": "Start of time range. Supports ISO 8601, relative ('1h ago'), or epoch ms"
    },
    "end_time": {
      "type": "string",
      "description": "End of time range (defaults to 'now' if not specified)"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum total number of log events to return (default: 100, max: 1000)",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": ["log_group_patterns", "search_pattern", "start_time"]
}
```

**Parameter Details**:

- `log_group_patterns` (required, array):
  - Array of log group name patterns or prefixes to search
  - Each item can be a full name or prefix pattern
  - Examples:
    - `["/aws/lambda/"]` - Search all Lambda functions
    - `["/ecs/"]` - Search all ECS containers
    - `["/aws/lambda/", "/ecs/"]` - Search both Lambda and ECS
    - `["/aws/lambda/my-function", "/api-gateway"]` - Specific groups
  - Supports wildcards: `/aws/*/` matches all AWS service logs
  - No default; must be specified

- `search_pattern` (required, string):
  - CloudWatch filter pattern to find across groups
  - Same patterns as `fetch_logs` filter_pattern
  - Examples: `ERROR`, `"timeout"`, `{ $.statusCode = 500 }`
  - No default; must be specified

- `start_time` (required, string):
  - Beginning of time range
  - Same formats as `fetch_logs` start_time
  - No default; must be specified

- `end_time` (optional, string):
  - End of time range
  - Same formats as `fetch_logs` start_time
  - Default: `now`

- `limit` (optional, integer):
  - Maximum total events across all groups
  - Default: 100
  - Maximum: 1000
  - Distributed across matching groups

**Return Type**:
```json
{
  "success": true,
  "log_group_patterns": ["/aws/lambda/", "/ecs/"],
  "search_pattern": "ERROR",
  "events": [
    {
      "timestamp": 1704067200000,
      "message": "ERROR: Connection timeout",
      "log_stream": "2024/01/01/[$LATEST]abc123",
      "log_group": "/aws/lambda/my-function"
    }
  ],
  "events_by_group": {
    "/aws/lambda/function1": [
      {
        "timestamp": 1704067200000,
        "message": "ERROR: Connection timeout"
      }
    ],
    "/ecs/service": [
      {
        "timestamp": 1704067210000,
        "message": "ERROR: Service unavailable"
      }
    ]
  },
  "count": 2,
  "groups_found": 2,
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-01T01:00:00Z"
  },
  "sanitization": {
    "enabled": true,
    "redactions": {"email": 0},
    "summary": "No sensitive data redacted"
  }
}
```

**Return Fields**:
- `success` (boolean): Indicates if operation was successful
- `log_group_patterns` (array): Patterns searched
- `search_pattern` (string): The search pattern used
- `events` (array): All matching events (flattened)
  - Includes `log_group` field showing source group
- `events_by_group` (object): Events organized by source log group
  - Key: log group name
  - Value: array of events from that group
- `count` (number): Total events found
- `groups_found` (number): Number of groups with matches
- `time_range` (object): Time range used
- `sanitization` (object): PII sanitization results

**Example Usage Scenarios**:

1. User: "Find all errors across all services in the last hour"
   - Agent calls: `search_logs(log_group_patterns=["/aws/"], search_pattern="ERROR", start_time="1h ago")`

2. User: "Search for 500 errors in Lambda and ECS"
   - Agent calls: `search_logs(log_group_patterns=["/aws/lambda/", "/ecs/"], search_pattern="\"500\"", start_time="2h ago")`

3. User: "Where's the timeout error happening?"
   - Agent calls: `search_logs(log_group_patterns=["/aws/"], search_pattern="timeout", start_time="1h ago", limit=50)`

4. User: "Correlate authentication failures"
   - Agent calls: `search_logs(log_group_patterns=["/auth/", "/api/", "/web/"], search_pattern="\"auth failed\"", start_time="3h ago")`

**Benefits**:
- **Cross-service correlation**: Find related errors across services
- **Distributed tracing**: Follow errors through system
- **Root cause analysis**: Understand cascade failures
- **Performance analysis**: Find bottlenecks across services

**Error Handling**:
- Returns `success: false` if no log groups match patterns
- Returns empty `events` if no matches found
- Returns `events_by_group` with empty arrays for groups with no matches
- Handles partial failures (some groups fail, others succeed)

**Caching**: Enabled
- Cache key: `query_type`, `log_group_patterns` (sorted tuple), `search_pattern`, `start_time`, `end_time`, `limit`
- TTL: Configured in settings

**Performance Considerations**:
- Searches happen in parallel across groups
- Results aggregated and de-duplicated
- Large result sets can be paginated with `limit`
- `events_by_group` helps with filtering results

**File Location**:
- Implementation: `src/logai/core/tools/cloudwatch_tools.py` (lines 312-521)
- Tests: `tests/unit/test_cloudwatch_tools.py`

**When Agent Uses This**:
- Cross-service investigation
- When user doesn't specify which service
- Correlating events across distributed system
- Root cause analysis
- Performance troubleshooting across services

---

## Tool Execution Flow

```
User Query
    ↓
Agent (LLM) decides which tool(s) to call
    ↓
┌─────────────────────────────────────────────┐
│ Tool Selection Logic                        │
├─────────────────────────────────────────────┤
│ If user asks about available logs:          │
│   → call list_log_groups()                  │
│                                             │
│ If user specifies a log group:              │
│   → call fetch_logs()                       │
│                                             │
│ If user wants to search multiple groups:    │
│   → call search_logs()                      │
│                                             │
│ If log group not found:                     │
│   → call list_log_groups() to find it       │
│                                             │
│ If first search has no results:             │
│   → retry with expanded time range          │
│   → retry with broader filter pattern       │
│   → try related log groups                  │
└─────────────────────────────────────────────┘
    ↓
Tool Execution
    ├─ Check cache (if enabled)
    ├─ Call AWS CloudWatch API
    ├─ Sanitize results (remove PII)
    ├─ Cache results
    └─ Return to LLM
    ↓
Agent Processing
    ├─ Analyze results
    ├─ Check for empty results
    ├─ Decide on retry if needed
    └─ Generate response
    ↓
Response to User
```

## Time Range Handling

### Supported Time Formats

All time parameters (`start_time`, `end_time`) support:

1. **ISO 8601 Format** (Recommended for accuracy)
   ```
   2024-01-15T10:30:00Z
   2024-01-15T10:30:00+00:00
   2024-01-15T10:30:00-05:00
   ```

2. **Relative Format** (Natural language)
   ```
   1h ago      → 1 hour ago
   30m ago     → 30 minutes ago
   2d ago      → 2 days ago
   yesterday   → 24 hours ago
   1w ago      → 7 days ago
   ```

3. **Epoch Milliseconds** (Programmatic)
   ```
   1705315800000
   ```

### Time Range Expansion Strategy

Agent automatically retries with expanded time ranges:

```
Initial attempt:  1h ago → now
↓ (no results)
2nd attempt:      6h ago → now
↓ (no results)
3rd attempt:      24h ago → now
↓ (no results)
4th attempt:      7d ago → now
```

### Common Time Range Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Too narrow range | No logs found | Expand to 24h or 7d |
| Too broad range | Too many logs | Add filter pattern or narrow range |
| Future time | No logs found | Use `now` for end_time |
| Timezone issues | Wrong time range | Use ISO 8601 format |
| Wrong day | Looking at wrong data | Verify start_time date |

## Filter Pattern Syntax

### CloudWatch Filter Pattern Examples

**Simple String Matching**:
```
ERROR           → lines containing "ERROR"
"timeout"       → lines containing exactly "timeout" (case-sensitive)
INFO ERROR      → lines containing both INFO and ERROR
```

**JSON Pattern Matching** (for JSON logs):
```
{ $.level = "ERROR" }          → JSON with level field = "ERROR"
{ $.statusCode > 400 }         → JSON with statusCode > 400
{ $.requestId = "12345" }      → JSON with exact requestId
{ ($.level = "ERROR") && ($.service = "auth") }  → Multiple conditions
```

**Complex Patterns**:
```
{ $.duration > 1000 }          → Queries taking > 1 second
{ $.error != "" }              → Any logs with error field
{ $.eventType = "FAILURE" }    → Specific event types
```

## Caching Strategy

All tools support caching to improve performance:

- **Cache Enabled**: By default (can be disabled in settings)
- **Cache Keys**: Include all parameters except `limit` in some cases
- **TTL**: Configurable in settings (default: 5 minutes)
- **Hit Rate**: High for repeated user queries

### Cache Hit Scenarios

```
First call:   fetch_logs(...) → CloudWatch API → Cache miss → Slow
Second call:  fetch_logs(...) [same params] → Cache hit → Fast
Retry call:   fetch_logs(...) [different time] → Cache miss → Slow
```

## Sanitization & Privacy

All logs are automatically sanitized before being returned to the LLM:

### Redaction Types

- **Email addresses**: `user@example.com` → `[EMAIL]`
- **Credit cards**: `4111-1111-1111-1111` → `[CREDIT_CARD]`
- **Phone numbers**: `555-123-4567` → `[PHONE]`
- **IPv4 addresses**: `192.168.1.1` → `[IPV4]`
- **API Keys**: `sk_live_1234567890` → `[API_KEY]`
- **SSN**: `123-45-6789` → `[SSN]`

### Redaction Tracking

Return value includes:
```json
"sanitization": {
  "enabled": true,
  "redactions": {
    "email": 3,
    "credit_card": 1,
    "ipv4": 2
  },
  "summary": "Redacted 6 sensitive items"
}
```

### Enabling/Disabling

Configure in `LogAISettings.pii_sanitization_enabled`

## Error Handling & Retries

### Retry Scenarios

The orchestrator automatically triggers retries for:

1. **Empty Results**: No logs found
   - Retry strategy: Expand time range → Broaden filter → Try different group

2. **Log Group Not Found**: Specified group doesn't exist
   - Retry strategy: Call `list_log_groups` → Suggest alternatives

3. **Partial Results**: Limited data returned
   - Retry strategy: Expand time range → Check related groups

4. **Intent Without Action**: Agent talks about action but doesn't execute
   - Retry strategy: Nudge agent to execute the tool call

### Max Retry Attempts

- **Default**: 3 attempts per query
- **Configurable**: `LogAISettings.max_retry_attempts`
- **Protection**: Prevents infinite loops

### Error Messages

Tools return `success: false` with:
```json
{
  "success": false,
  "error": "Log group '/aws/lambda/nonexistent' does not exist"
}
```

## Performance Characteristics

### Response Times (Typical)

| Operation | Time | Notes |
|-----------|------|-------|
| `list_log_groups` | 100-500ms | Lists only, very fast |
| `fetch_logs` (small range) | 200-800ms | Depends on data volume |
| `fetch_logs` (large range) | 1-5s | May need filtering |
| `search_logs` (2-3 groups) | 500-2s | Parallel execution |
| `search_logs` (10+ groups) | 2-10s | Depends on data |

### Factors Affecting Performance

- **Log volume**: More logs = slower response
- **Time range**: Larger range = more data to scan
- **Filter pattern**: Better filters = faster results
- **AWS rate limits**: API throttling
- **Cache hits**: 10-100x faster with cache

### Optimization Tips

1. Use specific time ranges (narrow when possible)
2. Add filter patterns to narrow results
3. Specify exact log group names
4. Use `limit` to cap results
5. Search fewer log groups simultaneously

## Integration Points

### Tool Registry

Tools are registered in the tool registry at startup:

```python
# src/logai/cli.py
ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache))
ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache))
ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache))
```

### LLM Orchestrator

The orchestrator converts tools to function definitions:

```python
tools = tool_registry.to_function_definitions()
response = llm_provider.chat(messages, tools=tools)
```

### Tool Call Listeners

External components (like UI sidebars) can listen for tool calls:

```python
orchestrator.register_tool_listener(callback)
# Called for each tool call with ToolCallRecord
```

## Tool Architecture

### Base Tool Class

All tools inherit from `BaseTool`:

```python
class BaseTool(ABC):
    @property
    def name(self) -> str: ...
    
    @property
    def description(self) -> str: ...
    
    @property
    def parameters(self) -> dict: ...
    
    async def execute(self, **kwargs) -> dict: ...
    
    def to_function_definition(self) -> dict: ...
```

### Tool Registry

Central registry for managing tools:

```python
class ToolRegistry:
    @classmethod
    def register(cls, tool: BaseTool) -> None: ...
    
    @classmethod
    def get(cls, tool_name: str) -> BaseTool: ...
    
    @classmethod
    def execute(cls, tool_name: str, **kwargs) -> dict: ...
    
    @classmethod
    def to_function_definitions(cls) -> list[dict]: ...
```

### Tool Execution Flow

```
LLM generates tool call → Parse tool name & args → Registry lookup 
→ Tool.execute() → Return result → Parse result → Return to LLM
```

## Configuration

### Tool-Related Settings

In `LogAISettings`:

```python
# Caching
cache_enabled: bool = True
cache_ttl_minutes: int = 5

# Sanitization
pii_sanitization_enabled: bool = True

# Retry behavior
max_tool_iterations: int = 10
max_retry_attempts: int = 3
auto_retry_enabled: bool = True

# CloudWatch API
cloudwatch_region: str = "us-east-1"
max_log_events: int = 1000
```

## Testing Tools

### Test Coverage

- **Unit tests**: `tests/unit/test_cloudwatch_tools.py`
- **Integration tests**: `tests/unit/test_orchestrator.py`
- **Mock fixtures**: Mocked CloudWatch datasource

### Running Tests

```bash
pytest tests/unit/test_cloudwatch_tools.py -v
pytest tests/unit/test_orchestrator.py::TestToolExecution -v
```

### Test Patterns

All tool tests follow pattern:
1. Mock datasource
2. Create tool instance
3. Call execute()
4. Assert results

## Common Usage Patterns

### Pattern 1: Discover and Fetch

```
User: "Show me Lambda logs from today"

Agent:
1. list_log_groups(prefix="/aws/lambda/")  → Get available Lambda groups
2. fetch_logs(log_group="...", start_time="1d ago")  → Get logs
3. Analyze and respond
```

### Pattern 2: Search for Issue

```
User: "Find all 500 errors in the last hour"

Agent:
1. search_logs(
     log_group_patterns=["/aws/"],
     search_pattern="500",
     start_time="1h ago"
   ) → Find all 500 errors
2. Organize by service
3. Provide analysis
```

### Pattern 3: Cross-Service Correlation

```
User: "Something went wrong, investigate"

Agent:
1. search_logs(
     log_group_patterns=["/aws/"],
     search_pattern="ERROR",
     start_time="30m ago"
   ) → Find all errors
2. events_by_group tells which services affected
3. Correlate failures and suggest root cause
```

### Pattern 4: Automatic Retry

```
User: "Any API errors?"

Agent:
1. search_logs(patterns, "ERROR", start_time="1h ago")
   → No results
2. Orchestrator detects empty results
3. Retry with expanded range (6h)
4. Retry with broader pattern
5. Eventually finds data or reports truly empty
```

## Limitations & Known Issues

### Current Limitations

1. **No custom metrics**: Tools only handle logs, not metrics
2. **CloudWatch only**: No multi-cloud support yet
3. **Single region**: Per execution context
4. **No log tailing**: Can't stream real-time logs
5. **No structured analysis**: LLM analyzes, not tool

### Planned Features

- [ ] Real-time log streaming
- [ ] CloudWatch Insights integration
- [ ] Multi-region support
- [ ] Lambda/EC2 metrics tools
- [ ] Anomaly detection tools
- [ ] Custom metrics tools

## Contributing New Tools

To add a new tool:

1. Create class extending `BaseTool`
2. Implement required properties and methods
3. Register in CLI or configuration
4. Add tests in `tests/unit/test_tools.py`
5. Update this documentation

Example:
```python
class MyNewTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool_name"
    
    @property
    def description(self) -> str:
        return "What this tool does"
    
    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {...}}
    
    async def execute(self, **kwargs) -> dict:
        # Implementation
        return {"success": True, ...}
```

## References

- **Tool Implementation**: `src/logai/core/tools/`
- **Orchestrator**: `src/logai/core/orchestrator.py`
- **CloudWatch Datasource**: `src/logai/providers/datasources/cloudwatch.py`
- **Tests**: `tests/unit/test_cloudwatch_tools.py`

---

## Document Maintenance

- **Last Updated**: 2026-02-11
- **Last Reviewed By**: Code Librarian (Hans)
- **Next Review**: After tool changes or quarterly

**Changes Tracked**:
- v1.0 (2026-02-11): Initial complete documentation of 3 tools
