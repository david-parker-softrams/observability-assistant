# Usage Examples

This guide provides practical examples of common LogAI queries and workflows. Use these as templates for your own log analysis tasks.

## Basic Queries

### Listing Log Groups

**Discover what logs are available:**

```
List all my log groups
```

```
Show me all Lambda function log groups
```

```
What log groups start with /aws/ecs/?
```

**What the Agent Does:**
- Answers immediately from the pre-loaded list (no API call needed)
- Filters and formats based on your query
- Can group by service type or prefix

**Use Cases:**
- Finding available logs
- Discovering service names
- Understanding log structure

**Note:** The agent already knows your log groups from startup. Use `/refresh` if you've created new ones during your session.

---

### Viewing Recent Logs

**See the latest log entries:**

```
Show me the latest logs from /aws/lambda/my-function
```

```
Get the last 10 minutes of logs from my-service
```

```
What are the most recent entries in /ecs/production/api?
```

**Time Ranges:**
- "last 5 minutes", "last hour"
- "past 24 hours", "today"
- "last week", "past 7 days"

---

## Error Investigation

### Finding Errors

**Search for error messages:**

```
Find errors in /aws/lambda/my-function in the last hour
```

```
Show me all errors across my Lambda functions today
```

```
Search for "exception" in production logs
```

**What the Agent Does:**
1. Lists relevant log groups
2. Searches for error patterns
3. Presents errors chronologically
4. Highlights important details

---

### Error Analysis

**Understand error patterns:**

```
What are the most common errors in the last 24 hours?
```

```
Analyze error patterns in /ecs/production/api
```

```
How many errors occurred in service-a today?
```

```
Compare error rates between service-a and service-b
```

**Agent Capabilities:**
- Counts error occurrences
- Identifies patterns
- Compares across services
- Provides context

---

### Specific Error Types

**Target specific error conditions:**

```
Find timeout errors in my Lambda functions
```

```
Show me out of memory errors from ECS tasks
```

```
Search for 500 errors in API Gateway logs
```

```
Find database connection errors in the last 6 hours
```

**Common Error Patterns:**
- `timeout`, `timed out`
- `out of memory`, `OOM`
- `500`, `503`, `504`
- `connection refused`, `connection reset`
- `exception`, `error`, `failed`

---

## Time-Based Queries

### Relative Time Ranges

**Use natural time expressions:**

```
Show me logs from the last 5 minutes
```

```
Find errors in the past hour
```

```
What happened in the last 30 minutes?
```

```
Search for warnings today
```

**Supported Expressions:**
- Minutes: "5 minutes", "30m"
- Hours: "1 hour", "2h", "6 hours"
- Days: "today", "1 day", "7d"
- Weeks: "this week", "last week"

---

### Specific Time Windows

**Query specific time periods:**

```
Show me logs between 2:00 PM and 3:00 PM today
```

```
Find errors from yesterday afternoon
```

```
What happened last night between midnight and 6 AM?
```

**Note:** The agent understands context and converts relative times appropriately.

---

## Service-Specific Queries

### AWS Lambda

**Lambda function analysis:**

```
List all my Lambda functions
```

```
Show me cold starts in my Lambda functions
```

```
Find timeouts in /aws/lambda/api-handler
```

```
What Lambda functions had errors today?
```

```
Analyze memory usage patterns in my Lambda logs
```

---

### Amazon ECS

**ECS task and service logs:**

```
Show me logs from my ECS services
```

```
Find errors in /ecs/production/api-service
```

```
What ECS tasks restarted today?
```

```
Search for health check failures in ECS logs
```

---

### API Gateway

**API request analysis:**

```
Find 500 errors in API Gateway logs
```

```
Show me slow API requests (over 1 second)
```

```
What are the most frequent API errors?
```

```
Analyze API Gateway error patterns
```

---

### Application Logs

**Custom application analysis:**

```
Show me logs from my-application
```

```
Find database queries that took over 1 second
```

```
Search for authentication failures
```

```
What users encountered errors today?
```

---

## Advanced Queries

### Multi-Service Investigation

**Investigate across multiple services:**

```
Find errors across all production services
```

```
Compare error rates between dev, staging, and prod
```

```
Show me errors in both api-service and worker-service
```

```
What services had the most errors today?
```

**Agent Behavior:**
- Searches multiple log groups in parallel
- Aggregates results
- Provides comparative analysis

---

### Pattern Matching

**Search for specific patterns:**

```
Find logs containing "user_id=12345"
```

```
Search for requests with status code 503
```

```
Show me logs with "payment" and "failed"
```

```
Find logs matching the pattern "ERROR: Database connection*"
```

**Pattern Tips:**
- Use quotes for exact phrases
- Combine multiple terms
- Include status codes, IDs, keywords

---

### Root Cause Analysis

**Investigate incidents:**

```
What happened around 2:30 PM today?
```

```
Find errors before the deployment at 3:00 PM
```

```
What caused the spike in errors last hour?
```

```
Trace the sequence of events leading to the error
```

**Agent Process:**
1. Searches relevant time window
2. Identifies key events
3. Orders chronologically
4. Highlights potential causes

---

### Performance Investigation

**Analyze performance issues:**

```
Find slow requests in the API logs
```

```
Show me queries that took over 5 seconds
```

```
What operations are timing out?
```

```
Analyze latency patterns in the last hour
```

---

## Workflow Examples

### Morning Check-In

**Quick health check of your services:**

```
User: List my production log groups

User: Any errors in the last 12 hours?

User: Show me the most recent error

User: What services are affected?
```

---

### Incident Response

**Responding to an alert:**

```
User: Show me errors from api-service in the last 10 minutes

User: How many errors occurred?

User: What are the error messages?

User: Did this happen before today?

User: Find similar errors in the past week
```

**Agent Auto-Retry:**
If initial search returns nothing, agent automatically expands time range to find context.

---

### Deployment Verification

**Check logs after deployment:**

```
User: Show me logs from my-service since 5 minutes ago

User: Any errors or warnings?

User: Compare error rates before and after 3:00 PM

User: Are there any new error patterns?
```

---

### Performance Tuning

**Identify performance bottlenecks:**

```
User: Find slow database queries in the last hour

User: What queries took over 1 second?

User: How often does this occur?

User: Show me the slowest query

User: Find similar slow queries today
```

---

### User-Specific Investigation

**Track down user-reported issues:**

```
User: Find logs for user_id=12345 in the last hour

User: Did this user encounter any errors?

User: What operations did they perform?

User: When did the error occur?

User: Find other users with the same error
```

---

## Follow-Up Patterns

### Contextual Follow-Ups

LogAI maintains conversation context, enabling natural follow-up questions:

**Example 1: Narrowing Down**
```
User: Show me errors from all Lambda functions

Agent: [Lists errors from 5 Lambda functions]

User: Focus on the first one

Agent: [Shows details for first function only]

User: What about the last hour?

Agent: [Refines to last hour, same function]
```

**Example 2: Expanding Scope**
```
User: Find errors in api-service

Agent: [Shows 3 errors in last hour]

User: Expand to the last 24 hours

Agent: [Shows 27 errors across 24 hours]

User: What are the most common ones?

Agent: [Groups and counts error types]
```

---

## Tips for Effective Queries

### Be Specific

**Less Effective:**
```
Show me logs
```

**More Effective:**
```
Show me error logs from /aws/lambda/api-handler in the last hour
```

**Why:** Specific queries get faster, more relevant results.

---

### Start Broad, Then Narrow

**Workflow:**
```
1. "List my Lambda functions"
2. "Show me errors from production Lambda functions"
3. "Focus on the api-handler function"
4. "Show me errors in the last hour"
5. "What's the most recent error?"
```

**Why:** Build context progressively, let agent guide you.

---

### Use Natural Language

**Works Well:**
```
Find errors from last night
What happened around 2 PM?
Show me the most recent timeout
```

**Also Works:**
```
query logs where level=ERROR
fetch /aws/lambda/my-function
search pattern "timeout"
```

**Why:** Natural language is easier and the agent understands both styles.

---

### Leverage Auto-Retry

**Let the agent expand searches automatically:**

```
User: Find errors in the last 5 minutes
```

If nothing found, agent will automatically:
- Try 15 minutes
- Try 1 hour
- Try broader patterns

**You get results without repeated manual queries.**

---

## Common Patterns Cheat Sheet

| Goal | Example Query |
|------|---------------|
| **List services** | `List all my log groups` |
| **Recent logs** | `Show me the latest logs from X` |
| **Find errors** | `Find errors in X in the last hour` |
| **Count errors** | `How many errors in X today?` |
| **Compare services** | `Compare errors between X and Y` |
| **Time range** | `Show me logs from X between 2 PM and 3 PM` |
| **Pattern search** | `Find logs containing "timeout"` |
| **Root cause** | `What happened around 2:30 PM?` |
| **User tracking** | `Find logs for user_id=123` |
| **Performance** | `Find slow requests in X` |

---

## Understanding Agent Behavior

### How Pre-loaded Log Groups Work

**At Startup:**
LogAI loads all your log groups and provides them to the agent. The agent has this information from the first query.

**Example:**
```
User: "What log groups do I have?"

Agent: [Answers immediately from pre-loaded list]
"You have 135 log groups across Lambda, ECS, API Gateway..."
```

No `list_log_groups` tool call needed!

### When Agent Uses list_log_groups

The agent rarely needs this tool now since log groups are pre-loaded. It may still use it when:
- User explicitly requests "a fresh lookup"
- User asks to "refresh the list" (though `/refresh` is better)
- Debugging specific listing issues

**Example (explicit refresh request):**
```
User: "Do a fresh lookup of log groups"

Agent:
1. Calls list_log_groups to get fresh data
2. Presents updated results
```

---

### When Agent Uses fetch_logs

**Triggers:**
- You specify an exact log group name
- You want recent logs (no filter)
- You need detailed log events

**Example:**
```
User: "Show me latest logs from /aws/lambda/api"

Agent:
1. Knows "/aws/lambda/api" exists (from pre-loaded list)
2. Calls fetch_logs with log_group="/aws/lambda/api"
3. Retrieves last hour of logs
4. Presents formatted results
```

**Benefit of Pre-loading:**
If you mistype the log group name, the agent can suggest corrections based on the pre-loaded list:
```
User: "Show me logs from /aws/lambda/api-handlr"

Agent: "I don't see that exact log group. Did you mean /aws/lambda/api-handler?"
```

---

### When Agent Uses search_logs

**Triggers:**
- You search for specific patterns
- You mention specific keywords (error, timeout, etc.)
- You want filtered results across multiple groups

**Example:**
```
User: "Find timeout errors in production"

Agent:
1. Identifies production log groups from pre-loaded list
2. Calls search_logs with filter_pattern="timeout"
3. Searches those log groups
4. Returns matching events
5. If empty, auto-retries with broader search
```

**Benefit of Pre-loading:**
The agent can intelligently select which log groups to search based on your query and the pre-loaded list.

---

## Sidebar Usage

The tool sidebar shows exactly what the agent is doing. Use it to:

### Learn Tool Patterns

Watch which tools the agent selects for different queries:

- **List query** → `list_log_groups`
- **Error search** → `search_logs` with filter
- **Recent logs** → `fetch_logs` with time range

### Verify Parameters

Check that the agent is using correct parameters:

- Right log group names
- Appropriate time ranges
- Correct filter patterns

### Debug Issues

If results are unexpected:

1. Check sidebar for tool calls
2. Verify parameters used
3. See actual results returned
4. Understand what data the agent received

### Toggle Visibility

```
/tools                  → Hide if you need more screen space
```

---

## See Also

- **[Features Overview](features.md)** - All LogAI capabilities
- **[Getting Started](getting-started.md)** - Installation and setup
- **[Runtime Commands](runtime-commands.md)** - Slash commands
- **[Troubleshooting](troubleshooting.md)** - Common issues
