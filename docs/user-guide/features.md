# Features Overview

LogAI provides powerful features for querying and analyzing AWS CloudWatch logs using natural language. This guide explains what LogAI can do and how each feature works.

## Core Features

### Natural Language Queries

Ask questions about your logs in plain English instead of writing complex query syntax.

**Example Queries:**
```
List all my log groups

Show me errors from /aws/lambda/my-function in the last hour

Search for "timeout" across all Lambda functions

What are the most common error patterns today?

Compare error rates between service-a and service-b
```

**How It Works:**
1. You type a question in natural language
2. LogAI's AI agent understands your intent
3. The agent selects and calls appropriate tools
4. Results are formatted and explained
5. You can ask follow-up questions

**Benefits:**
- No need to learn CloudWatch query syntax
- Faster investigation workflows
- Natural conversation interface
- Context-aware follow-up queries

---

### Intelligent Tool Execution

LogAI uses three specialized tools to fetch and analyze your logs. The AI agent automatically selects the right tools for your query.

#### Available Tools

**1. list_log_groups**
- Lists all available CloudWatch log groups
- Supports prefix filtering (e.g., `/aws/lambda/`)
- Helps discover what logs are available

**2. fetch_logs**
- Retrieves logs from a specific log group
- Supports time range filtering
- Supports filter patterns
- Returns detailed log events

**3. search_logs**
- Searches across multiple log groups simultaneously
- Faster than fetching each group individually
- Supports complex filter patterns

**Agent Decision-Making:**

The agent intelligently combines tools:

```
User: "Find errors in service-a and service-b"

Agent:
1. Calls list_log_groups (to find service log groups)
2. Calls search_logs for service-a
3. Calls search_logs for service-b
4. Analyzes and compares results
5. Presents findings
```

---

### Tool Execution Sidebar

**NEW FEATURE** - See exactly what the AI agent is doing in real-time.

The tool sidebar (shown by default on the right side) displays:

**Tool Call Information:**
- Tool name (e.g., `list_log_groups`, `fetch_logs`)
- Status indicators:
  - ◯ Pending - Tool queued for execution
  - ⏳ Running - Tool currently executing
  - ✓ Success - Tool completed successfully
  - ✗ Error - Tool failed

**Execution Details:**
- Parameters passed to each tool
- Results returned (actual data, not just counts)
- Execution duration
- Timestamps

**Interactive Features:**
- Click to expand results
- See actual log group names
- Read actual log messages
- No truncation - full text display

**Why It's Useful:**
- **Transparency** - See exactly what the agent is doing
- **Debugging** - Understand why certain results appear
- **Learning** - Learn which tools work for different queries
- **Verification** - Confirm the agent is using correct parameters

**Toggle Visibility:**
```
/tools                  → Hide or show sidebar
```

---

### Agent Self-Direction & Auto-Retry

**NEW FEATURE** - The agent automatically tries alternative approaches when initial attempts fail.

#### What Is Auto-Retry?

When a query returns no results, the agent doesn't give up. Instead, it automatically:

1. **Expands time ranges** - 1h → 6h → 24h → 7d
2. **Broadens filters** - Removes or simplifies filter patterns
3. **Tries related log groups** - Searches similar or related groups

#### Example Scenario

**Without Auto-Retry:**
```
User: "Find errors in the last 5 minutes"
Agent: "No logs found in the last 5 minutes"
[Done]
```

**With Auto-Retry (Default):**
```
User: "Find errors in the last 5 minutes"
Agent: [Searches last 5 minutes - empty]
Agent: [Auto-expands to 15 minutes]
Agent: [Finds 3 errors]
Agent: "I found 3 errors in the last 15 minutes: ..."
```

#### Configurable Behavior

Control auto-retry behavior in your `.env` file:

```bash
# Enable/disable auto-retry
LOGAI_AUTO_RETRY_ENABLED=true

# Maximum retry attempts (1-5)
LOGAI_MAX_RETRY_ATTEMPTS=3

# Maximum tool iterations per turn (1-100)
LOGAI_MAX_TOOL_ITERATIONS=10
```

#### Intent Detection

The agent detects when it states an intention without executing it:

**Problem (Solved):**
```
Agent: "Let me search the logs for errors..."
[Stops without actually searching]
```

**Solution (Automatic):**
```
Agent: "Let me search the logs for errors..."
System: [Nudges agent to execute]
Agent: [Actually calls search tool]
```

---

### Smart Caching

LogAI caches CloudWatch query results to improve performance and reduce AWS API costs.

#### How Caching Works

1. **First Query** - Fetches from CloudWatch, saves to cache
2. **Repeat Query** - Returns from cache instantly (10-100x faster)
3. **Auto-Expiration** - Old entries removed based on TTL

#### Cache Statistics

View cache performance:

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
```

**Benefits:**
- **Speed** - Cached queries return instantly
- **Cost Savings** - Fewer CloudWatch API calls
- **Reliability** - Works when CloudWatch is slow

#### Cache Management

```bash
/cache status           → View statistics
/cache clear            → Clear all cached data
```

**Configuration:**

```bash
# Cache directory
LOGAI_CACHE_DIR=~/.logai/cache

# Maximum cache size
LOGAI_CACHE_MAX_SIZE_MB=500

# Time-to-live (24 hours)
LOGAI_CACHE_TTL_SECONDS=86400
```

---

### PII Sanitization

Automatically redacts sensitive information before sending logs to LLM providers.

#### What Gets Sanitized

- **Email addresses** - `user@example.com` → `[REDACTED_EMAIL]`
- **IP addresses** - `192.168.1.1` → `[REDACTED_IP]`
- **Credit card numbers** - `4111-1111-1111-1111` → `[REDACTED_CC]`
- **Social Security Numbers** - `123-45-6789` → `[REDACTED_SSN]`
- **Phone numbers** - `(555) 123-4567` → `[REDACTED_PHONE]`
- **AWS access keys** - `AKIAIOSFODNN7EXAMPLE` → `[REDACTED_AWS_KEY]`
- **API keys** - `sk-1234567890abcdef` → `[REDACTED_API_KEY]`
- **Bearer tokens** - `Bearer eyJhbG...` → `[REDACTED_TOKEN]`
- **JWT tokens** - `eyJhbGciOiJIUz...` → `[REDACTED_JWT]`
- **Private keys** - `-----BEGIN PRIVATE KEY-----` → `[REDACTED_PRIVATE_KEY]`

#### How It Works

1. Logs are fetched from CloudWatch
2. PII sanitization is applied
3. Sanitized logs are sent to LLM
4. Original logs remain in cache (not sent to LLM)

#### Configuration

```bash
# Enable (recommended for production)
LOGAI_PII_SANITIZATION_ENABLED=true

# Disable (for testing or non-sensitive logs)
LOGAI_PII_SANITIZATION_ENABLED=false
```

#### Example

**Original Log:**
```
Error: Failed to send email to john.doe@example.com from IP 203.0.113.42
API Key: sk-abc123def456
```

**Sanitized (Sent to LLM):**
```
Error: Failed to send email to [REDACTED_EMAIL] from IP [REDACTED_IP]
API Key: [REDACTED_API_KEY]
```

**Security Note:** The LLM can still analyze the error pattern without seeing sensitive data.

---

### Multi-Provider LLM Support

LogAI works with multiple LLM providers, giving you flexibility in model selection and cost management.

#### Supported Providers

**1. Anthropic Claude**
- Models: Claude 3.5 Sonnet (recommended), Opus, Haiku
- Best for: High-quality analysis, complex reasoning
- Pricing: Pay-per-use

**2. OpenAI GPT**
- Models: GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- Best for: General purpose, widespread availability
- Pricing: Pay-per-use

**3. GitHub Copilot** ⭐ NEW
- Models: 25+ models (Claude, GPT, Gemini, Grok)
- Best for: Cost savings, model variety
- Pricing: Included with GitHub Copilot subscription

**4. Ollama (Local)**
- Models: Llama 3.1, Mistral, others
- Best for: Privacy, offline usage, no API costs
- Pricing: Free (runs on your hardware)

#### Switching Providers

Edit `.env` and change `LOGAI_LLM_PROVIDER`:

```bash
LOGAI_LLM_PROVIDER=github-copilot
```

Then restart LogAI.

See [Configuration Guide](configuration.md#llm-provider-configuration) for details.

---

### GitHub Copilot Integration

Use your existing GitHub Copilot subscription to access 25+ models from multiple providers.

#### Available Models

**Claude Models** (Anthropic):
- claude-opus-4.6 (Most capable)
- claude-sonnet-4.5 (Balanced)
- claude-haiku-4.5 (Fast)

**GPT Models** (OpenAI):
- gpt-5.2, gpt-5.1, gpt-5 (Latest generation)
- gpt-4o, gpt-4o-mini (Current generation)

**Gemini Models** (Google):
- gemini-3-pro-preview (Latest, powerful)
- gemini-2.5-pro (Production)
- gemini-2.5-flash (Fast)

**Other Models:**
- grok-2-1212 (xAI)
- Plus more models added regularly

#### Setup

1. Configure provider:
   ```bash
   LOGAI_LLM_PROVIDER=github-copilot
   LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
   ```

2. Authenticate once:
   ```bash
   logai auth login
   ```

3. Run LogAI:
   ```bash
   logai
   ```

**Benefits:**
- No separate API keys needed
- Access to multiple model families
- Cost included in GitHub Copilot subscription
- Easy model switching

See [Configuration Guide](configuration.md#github-copilot-configuration) for full list of models.

---

### Real-Time Streaming

Responses stream in real-time as the agent thinks and works.

**What You See:**
1. Tool executions appear in sidebar immediately
2. Analysis streams word-by-word as it's generated
3. No waiting for complete response
4. Can read results as they arrive

**Benefits:**
- Immediate feedback
- Better user experience
- Can interrupt if needed
- See progress of long-running queries

---

### Conversation Context

LogAI maintains conversation history, allowing natural follow-up questions.

#### Example Conversation

```
User: "List all Lambda function log groups"
Agent: [Lists 15 Lambda log groups]

User: "Show me errors from the first one"
Agent: [Knows which log group you mean]

User: "What about the last hour?"
Agent: [Refines time range, keeps context]
```

#### Managing Context

```bash
/clear                  → Clear conversation history
```

**When to Clear:**
- Starting a new investigation
- Context is getting confused
- Conversation is too long
- Want a fresh start

---

## Interface Features

### Interactive Terminal UI (TUI)

LogAI uses Textual to provide a rich terminal interface.

**Layout:**
- **Chat Area** (center) - Conversation with the agent
- **Tool Sidebar** (right) - Tool execution details
- **Input Box** (bottom) - Type queries here
- **Status Bar** (very bottom) - Keyboard shortcuts

**Features:**
- Rich text formatting (bold, colors, code blocks)
- Scrollable chat history
- Expandable tool results
- Keyboard navigation
- Mouse support (click, scroll)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+C** | Exit LogAI |
| **Ctrl+Q** | Exit LogAI |
| **Ctrl+D** | Exit LogAI |
| **Up/Down Arrow** | Navigate input history |
| **Page Up/Down** | Scroll chat |
| **Home/End** | Jump to top/bottom |

### Slash Commands

Special commands for controlling LogAI:

| Command | Purpose |
|---------|---------|
| `/help` | Show available commands |
| `/tools` | Toggle tool sidebar |
| `/cache status` | View cache stats |
| `/cache clear` | Clear cache |
| `/model` | Show current LLM model |
| `/config` | Show configuration |
| `/clear` | Clear conversation |
| `/quit`, `/exit` | Exit application |

See [Runtime Commands](runtime-commands.md) for details.

---

## AWS CloudWatch Integration

### Supported Operations

**Log Groups:**
- List all log groups
- Filter by prefix
- Discover available logs

**Log Events:**
- Fetch from specific log groups
- Search across multiple groups
- Time range filtering
- Pattern matching

**Time Range Support:**
- Relative times: "last hour", "past 24 hours"
- ISO 8601 format: `2024-02-12T10:00:00Z`
- Unix timestamps: `1707739200`

### AWS Permissions Required

Your AWS credentials need these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Multi-Region Support

Query logs in different regions:

```bash
# Via command line
logai --aws-region us-west-2

# Via environment variable
export AWS_DEFAULT_REGION=eu-west-1
logai
```

---

## Performance Features

### Efficient Querying

- **Caching** - Avoid redundant API calls
- **Parallel Searches** - Search multiple log groups simultaneously
- **Smart Time Ranges** - Start narrow, expand as needed
- **Filter Patterns** - Reduce data volume at source

### Resource Management

- **Cache Size Limits** - Automatic eviction of old entries
- **Connection Pooling** - Reuse AWS connections
- **Timeout Handling** - Graceful failure on slow queries

---

## Coming Soon

These features are planned for future releases:

- **Additional Data Sources** - Splunk, Datadog, New Relic
- **Metrics Support** - Query CloudWatch Metrics, not just logs
- **Web UI** - Browser-based interface with visualizations
- **Saved Queries** - Save and reuse common queries
- **Alert Integration** - Connect with alerting systems
- **Export Options** - Save results to files

---

## See Also

- **[Getting Started](getting-started.md)** - Installation and setup
- **[Usage Examples](examples.md)** - Common queries and workflows
- **[Configuration Guide](configuration.md)** - All configuration options
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
