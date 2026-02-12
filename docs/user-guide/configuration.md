# Configuration Guide

This guide covers all configuration options for LogAI. Configuration is managed through environment variables, typically stored in a `.env` file.

## Configuration File

LogAI uses a `.env` file in the project root directory for configuration. Create this file by copying the example:

```bash
cp .env.example .env
```

Then edit `.env` to set your configuration values.

## LLM Provider Configuration

LogAI supports four LLM providers: Anthropic Claude, OpenAI GPT, GitHub Copilot, and Ollama (local models).

### Provider Selection

**Variable:** `LOGAI_LLM_PROVIDER`  
**Required:** Yes  
**Default:** `anthropic`  
**Options:** `anthropic`, `openai`, `github-copilot`, `ollama`

```bash
LOGAI_LLM_PROVIDER=anthropic
```

---

### Anthropic Configuration

#### API Key

**Variable:** `LOGAI_ANTHROPIC_API_KEY`  
**Required:** Yes (when using Anthropic)  
**Default:** None

Get your API key from: https://console.anthropic.com/

```bash
LOGAI_ANTHROPIC_API_KEY=sk-ant-api03-...
```

#### Model Selection

**Variable:** `LOGAI_ANTHROPIC_MODEL`  
**Required:** No  
**Default:** `claude-3-5-sonnet-20241022`

```bash
LOGAI_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**Available Models:**
- `claude-3-5-sonnet-20241022` (Recommended - best balance)
- `claude-3-opus-20240229` (Most capable)
- `claude-3-sonnet-20240229` (Balanced)
- `claude-3-haiku-20240307` (Fastest, most economical)

---

### OpenAI Configuration

#### API Key

**Variable:** `LOGAI_OPENAI_API_KEY`  
**Required:** Yes (when using OpenAI)  
**Default:** None

Get your API key from: https://platform.openai.com/api-keys

```bash
LOGAI_OPENAI_API_KEY=sk-...
```

#### Model Selection

**Variable:** `LOGAI_OPENAI_MODEL`  
**Required:** No  
**Default:** `gpt-4-turbo-preview`

```bash
LOGAI_OPENAI_MODEL=gpt-4-turbo-preview
```

**Available Models:**
- `gpt-4-turbo-preview` (Recommended)
- `gpt-4` (Most capable)
- `gpt-3.5-turbo` (Fastest, most economical)

---

### GitHub Copilot Configuration

GitHub Copilot provides access to 25+ models from multiple providers using your existing GitHub Copilot subscription. No separate API keys needed!

#### Authentication

First, authenticate with GitHub Copilot:

```bash
logai auth login
```

Follow the browser prompts to authorize LogAI. Your token will be saved to `~/.local/share/logai/auth.json`.

#### Model Selection

**Variable:** `LOGAI_GITHUB_COPILOT_MODEL`  
**Required:** Yes (when using GitHub Copilot)  
**Default:** `claude-opus-4.5`

```bash
LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
```

**Available Models (25+):**

**Claude Models** (Anthropic):
- `claude-haiku-4.5` - Fast, economical
- `claude-sonnet-4` - Balanced
- `claude-sonnet-4.5` - Balanced, newer
- `claude-opus-4.5` - Most capable (Recommended)
- `claude-opus-4.6` - Most capable, latest
- `claude-opus-41` - Alternative powerful model

**GPT Models** (OpenAI):
- `gpt-4o-mini` - Fast, economical (Good for testing)
- `gpt-4o` - Balanced
- `gpt-4.1` - Capable
- `gpt-5` - Latest generation
- `gpt-5-mini` - Fast from latest generation
- `gpt-5.1` - Latest, most capable
- `gpt-5.1-codex` - Code-optimized
- `gpt-5.1-codex-max` - Maximum code capability
- `gpt-5.1-codex-mini` - Fast code model
- `gpt-5.2` - Very latest
- `gpt-5.2-codex` - Latest code model

**Gemini Models** (Google):
- `gemini-2.5-flash` - Fast
- `gemini-2.5-pro` - Powerful
- `gemini-3-flash-preview` - Latest fast (preview)
- `gemini-3-pro-preview` - Latest powerful (preview)

**Other Models:**
- `grok-2-1212` - xAI Grok (powerful)
- `grok-code-fast-1` - xAI Grok (code-optimized, fast)

#### API Base URL

**Variable:** `LOGAI_GITHUB_COPILOT_API_BASE`  
**Required:** No  
**Default:** `https://api.githubcopilot.com`

```bash
LOGAI_GITHUB_COPILOT_API_BASE=https://api.githubcopilot.com
```

**Note:** You typically don't need to change this.

#### Checking Available Models

To see which models are currently available:

```bash
logai auth status
```

The cache is updated every 24 hours automatically.

---

### Ollama Configuration (Local Models)

Run models locally on your machine for privacy or offline usage.

#### Base URL

**Variable:** `LOGAI_OLLAMA_BASE_URL`  
**Required:** No  
**Default:** `http://localhost:11434`

```bash
LOGAI_OLLAMA_BASE_URL=http://localhost:11434
```

#### Model Selection

**Variable:** `LOGAI_OLLAMA_MODEL`  
**Required:** No  
**Default:** `llama3.1:8b`

```bash
LOGAI_OLLAMA_MODEL=llama3.1:8b
```

**Recommended Models:**
- `llama3.1:8b` - Good balance (requires ~8GB RAM)
- `llama3.1:70b` - Best quality (requires ~40GB RAM)
- `mistral:latest` - Alternative model

**Important:** Only use models with function calling support. Llama 3.1 and newer Mistral models work well.

#### Setup Ollama

1. Install Ollama:
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a model:
   ```bash
   ollama pull llama3.1:8b
   ```

3. Start the server:
   ```bash
   ollama serve
   ```

---

## AWS Configuration

Configure AWS credentials and region for CloudWatch Logs access.

### AWS Region

**Variable:** `AWS_DEFAULT_REGION`  
**Required:** Yes  
**Default:** None  
**Override:** `--aws-region` CLI argument

```bash
AWS_DEFAULT_REGION=us-east-1
```

**Common Regions:**
- `us-east-1` - US East (N. Virginia)
- `us-west-2` - US West (Oregon)
- `eu-west-1` - Europe (Ireland)
- `ap-southeast-1` - Asia Pacific (Singapore)

See [AWS Regions](https://docs.aws.amazon.com/general/latest/gr/rande.html) for full list.

### AWS Credentials (Method 1: Direct)

**Variables:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

**Required:** Yes (if not using AWS profile)  
**Default:** None

```bash
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**When to Use:**
- CI/CD environments
- Testing with temporary credentials
- IAM user credentials

### AWS Credentials (Method 2: Profile)

**Variable:** `AWS_PROFILE`  
**Required:** Yes (if not using direct credentials)  
**Default:** None  
**Override:** `--aws-profile` CLI argument

```bash
AWS_PROFILE=my-profile-name
```

**When to Use:**
- Local development
- Multiple AWS accounts
- Using AWS CLI profiles
- SSO authentication

**Setup AWS Profile:**

```bash
# Configure AWS CLI profile
aws configure --profile my-profile-name

# Or use AWS SSO
aws configure sso
```

### AWS Credentials Precedence

LogAI checks for AWS credentials in this order:

1. **Command-line arguments** (`--aws-profile`, `--aws-region`)
2. **Environment variables** (`AWS_PROFILE`, `AWS_DEFAULT_REGION`, etc.)
3. **`.env` file** settings
4. **AWS credential chain** (IAM roles, instance profiles, etc.)

---

## Application Settings

### UI Settings

#### Log Groups Sidebar Visibility

**Variable:** `LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE`  
**Required:** No  
**Default:** `true`  
**Type:** Boolean (`true` or `false`)

```bash
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true
```

**Purpose:** Controls whether the log groups sidebar is visible by default when LogAI starts.

**When Enabled (Default):**
- Left sidebar shows all log groups at startup
- Provides quick reference to available log groups
- Shows count in title: "LOG GROUPS (135)"
- Automatically updates when `/refresh` is used

**When Disabled:**
- Sidebar hidden at startup
- More screen space for chat and tool sidebar
- Can still be toggled on with `/logs` command
- Setting persists across restarts

**Use Cases:**
- **Enable (Default):** When you want to see all available log groups at a glance
- **Disable:** When you prefer a cleaner interface or have a small terminal window

**Toggle During Session:**
```
/logs                   → Show/hide sidebar (doesn't change config)
```

---

### PII Sanitization

**Variable:** `LOGAI_PII_SANITIZATION_ENABLED`  
**Required:** No  
**Default:** `true`  
**Type:** Boolean (`true` or `false`)

```bash
LOGAI_PII_SANITIZATION_ENABLED=true
```

**What is Sanitized:**
- Email addresses
- IP addresses (IPv4 and IPv6)
- Credit card numbers
- Social Security Numbers (SSNs)
- Phone numbers
- AWS access keys
- API keys and bearer tokens
- JWT tokens
- Private keys

**When Enabled:**
- Sensitive data is redacted before sending to LLM
- Format: `[REDACTED_EMAIL]`, `[REDACTED_IP]`, etc.
- Original data remains in cache (not sent to LLM)

**When to Disable:**
- Testing in development
- Logs don't contain sensitive data
- You want to see full log content
- Debugging sanitization issues

**Security Note:** Keep this enabled in production when sending logs to third-party LLM providers.

---

### Cache Configuration

#### Cache Directory

**Variable:** `LOGAI_CACHE_DIR`  
**Required:** No  
**Default:** `~/.logai/cache`  
**Type:** Path

```bash
LOGAI_CACHE_DIR=~/.logai/cache
```

**Purpose:** Store cached CloudWatch log queries to reduce AWS API calls and improve performance.

**Custom Location Example:**
```bash
LOGAI_CACHE_DIR=/var/cache/logai
```

#### Cache Maximum Size

**Variable:** `LOGAI_CACHE_MAX_SIZE_MB`  
**Required:** No  
**Default:** `500`  
**Type:** Integer (1-10000)  
**Unit:** Megabytes

```bash
LOGAI_CACHE_MAX_SIZE_MB=500
```

**Guidelines:**
- **100-200 MB**: Light usage, limited logs
- **500 MB**: Default, good for most users
- **1000-2000 MB**: Heavy usage, many log groups
- **5000+ MB**: Enterprise, extensive log history

When cache reaches max size, oldest entries are automatically removed.

#### Cache TTL (Time To Live)

**Variable:** `LOGAI_CACHE_TTL_SECONDS`  
**Required:** No  
**Default:** `86400` (24 hours)  
**Type:** Integer  
**Unit:** Seconds

```bash
LOGAI_CACHE_TTL_SECONDS=86400
```

**Common Values:**
- `3600` - 1 hour (for rapidly changing logs)
- `21600` - 6 hours
- `43200` - 12 hours
- `86400` - 24 hours (default)
- `604800` - 7 days (for historical analysis)

**Note:** Historical logs (older than 24 hours from now) are cached longer automatically.

---

## Agent Behavior Settings

These settings control how the AI agent operates, including retry behavior and tool execution limits.

### Maximum Tool Iterations

**Variable:** `LOGAI_MAX_TOOL_ITERATIONS`  
**Required:** No  
**Default:** `10`  
**Type:** Integer (1-100)

```bash
LOGAI_MAX_TOOL_ITERATIONS=10
```

**Purpose:** Prevents infinite loops by limiting the number of tool calls in a single conversation turn.

**Guidelines:**
- **5**: Quick failures, cost control, testing
- **10**: Default, suitable for most queries
- **15-20**: Complex investigations
- **25+**: Multi-step analysis, debugging sessions

**Example Scenarios:**

**Simple query** (uses 2-3 iterations):
```
User: "List my log groups"
→ Agent calls list_log_groups
→ Agent responds with results
Total: 1-2 iterations
```

**Complex query** (uses 5-8 iterations):
```
User: "Find errors in service-a and compare with service-b"
→ Agent calls list_log_groups
→ Agent calls search_logs for service-a
→ Agent calls search_logs for service-b
→ Agent analyzes and responds
Total: 3-6 iterations (plus potential retries)
```

### Automatic Retry

**Variable:** `LOGAI_AUTO_RETRY_ENABLED`  
**Required:** No  
**Default:** `true`  
**Type:** Boolean

```bash
LOGAI_AUTO_RETRY_ENABLED=true
```

**Purpose:** Enables automatic retry when queries return empty results.

**What Happens When Enabled:**
1. Agent gets empty results
2. Automatically tries alternative approaches:
   - Expands time range (1h → 6h → 24h)
   - Broadens filter patterns
   - Tries related log groups
3. Makes 2-3 attempts before giving up
4. Reports findings to user

**When to Disable:**
- Testing specific query behavior
- Debugging agent decisions
- Cost optimization (fewer LLM calls)
- You want immediate "no results" responses

**Example with Auto-Retry Enabled:**
```
User: "Find errors in the last 5 minutes"
→ Agent searches last 5 minutes (empty)
→ Agent automatically expands to 15 minutes
→ Agent finds 3 errors
→ Reports findings
```

**Example with Auto-Retry Disabled:**
```
User: "Find errors in the last 5 minutes"
→ Agent searches last 5 minutes (empty)
→ Immediately reports "No errors found"
```

### Intent Detection

**Variable:** `LOGAI_INTENT_DETECTION_ENABLED`  
**Required:** No  
**Default:** `true`  
**Type:** Boolean

```bash
LOGAI_INTENT_DETECTION_ENABLED=true
```

**Purpose:** Detects when the agent states an intention without executing it, then nudges it to act.

**What It Catches:**

**Without Intent Detection:**
```
Agent: "I'll search the last hour for errors"
[Stops without searching]
```

**With Intent Detection:**
```
Agent: "I'll search the last hour for errors"
[System nudges: "Execute your stated action now"]
Agent: [Actually calls search tool]
```

**When to Disable:**
- Testing agent behavior
- Debugging prompting issues
- Experimental configurations

**Recommended:** Keep enabled for best user experience.

### Maximum Retry Attempts

**Variable:** `LOGAI_MAX_RETRY_ATTEMPTS`  
**Required:** No  
**Default:** `3`  
**Type:** Integer (1-5)

```bash
LOGAI_MAX_RETRY_ATTEMPTS=3
```

**Purpose:** Limits the number of retry attempts for each scenario (empty results, not found, etc.)

**Guidelines:**
- **1**: No retries, fail fast
- **2**: One retry attempt
- **3**: Default, good balance
- **5**: Maximum persistence

Works in conjunction with `LOGAI_AUTO_RETRY_ENABLED`.

### Time Expansion Factor

**Variable:** `LOGAI_TIME_EXPANSION_FACTOR`  
**Required:** No  
**Default:** `4.0`  
**Type:** Float

```bash
LOGAI_TIME_EXPANSION_FACTOR=4.0
```

**Purpose:** Controls how much to expand time ranges on retry.

**Examples:**
- Factor `4.0`: 1h → 4h → 16h
- Factor `2.0`: 1h → 2h → 4h → 8h
- Factor `6.0`: 1h → 6h → 36h

**Recommended:** Keep at `4.0` for balanced behavior.

---

## Logging Configuration

### Log Level

**Variable:** `LOGAI_LOG_LEVEL`  
**Required:** No  
**Default:** `INFO`  
**Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`

```bash
LOGAI_LOG_LEVEL=INFO
```

**Log Levels:**

- **DEBUG**: Very detailed, includes all operations
  - Tool calls, arguments, results
  - Cache operations
  - Retry logic details
  - Use for: Development, troubleshooting

- **INFO**: Standard operational messages
  - Startup configuration
  - Major operations
  - Retry attempts
  - Use for: Normal operation, monitoring

- **WARNING**: Potential issues
  - Missing optional config
  - Cache evictions
  - Retry exhausted
  - Use for: Production monitoring

- **ERROR**: Serious issues
  - Configuration errors
  - API failures
  - Tool execution failures
  - Use for: Error tracking

### Log File

**Variable:** `LOGAI_LOG_FILE`  
**Required:** No  
**Default:** None (logs to stderr only)  
**Type:** Path

```bash
LOGAI_LOG_FILE=~/.logai/logai.log
```

**When to Use:**
- Debugging issues
- Monitoring in production
- Analyzing agent behavior
- Troubleshooting performance

**Example:**
```bash
LOGAI_LOG_FILE=/var/log/logai/application.log
```

**Note:** If not set, logs only appear in stderr (terminal output).

---

## Configuration Precedence

Understanding how configuration values are determined:

### Order of Precedence (Highest to Lowest)

1. **Command-line arguments** - `--aws-profile`, `--aws-region`
2. **Environment variables** - Shell exports
3. **`.env` file** - Project configuration file
4. **Defaults** - Built-in default values

### Example Scenario

**`.env` file:**
```bash
AWS_PROFILE=development
AWS_DEFAULT_REGION=us-east-1
LOGAI_MAX_TOOL_ITERATIONS=10
```

**Shell environment:**
```bash
export AWS_PROFILE=staging
export AWS_DEFAULT_REGION=us-west-2
```

**Command line:**
```bash
logai --aws-profile production --aws-region eu-west-1
```

**Result:**
- AWS Profile: `production` (from CLI)
- AWS Region: `eu-west-1` (from CLI)
- Max Tool Iterations: `10` (from .env, no override)

---

## Configuration Examples

### Minimal Configuration (Anthropic)

```bash
# LLM Provider
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# AWS
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=my-profile
```

### Full Configuration (All Options)

```bash
# === LLM Provider ===
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
LOGAI_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# === AWS Configuration ===
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=production

# === Application Settings ===
LOGAI_PII_SANITIZATION_ENABLED=true
LOGAI_CACHE_DIR=~/.logai/cache
LOGAI_CACHE_MAX_SIZE_MB=1000
LOGAI_CACHE_TTL_SECONDS=86400

# === UI Settings ===
LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE=true

# === Agent Behavior ===
LOGAI_MAX_TOOL_ITERATIONS=15
LOGAI_AUTO_RETRY_ENABLED=true
LOGAI_INTENT_DETECTION_ENABLED=true
LOGAI_MAX_RETRY_ATTEMPTS=3
LOGAI_TIME_EXPANSION_FACTOR=4.0

# === Logging ===
LOGAI_LOG_LEVEL=INFO
LOGAI_LOG_FILE=~/.logai/logai.log
```

### GitHub Copilot Configuration

```bash
# LLM Provider
LOGAI_LLM_PROVIDER=github-copilot
LOGAI_GITHUB_COPILOT_MODEL=claude-opus-4.6

# AWS
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=my-profile

# Application (use defaults for rest)
LOGAI_CACHE_MAX_SIZE_MB=1000
```

Then authenticate:
```bash
logai auth login
```

### Multi-Environment Configuration

Create multiple `.env` files:

**`.env.development`:**
```bash
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=sk-ant-dev-xxxxx
AWS_PROFILE=dev
AWS_DEFAULT_REGION=us-east-1
LOGAI_LOG_LEVEL=DEBUG
```

**`.env.production`:**
```bash
LOGAI_LLM_PROVIDER=github-copilot
LOGAI_GITHUB_COPILOT_MODEL=claude-opus-4.6
AWS_PROFILE=prod
AWS_DEFAULT_REGION=us-east-1
LOGAI_LOG_LEVEL=WARNING
LOGAI_MAX_TOOL_ITERATIONS=20
```

Copy the appropriate file:
```bash
cp .env.production .env
logai
```

---

## Validating Configuration

Check your configuration before running:

```bash
# Validate environment variables are set
python -c "from logai.config.settings import LogAISettings; s = LogAISettings(); s.validate_required_credentials(); print('✓ Configuration valid')"
```

Or start LogAI and check the startup output:

```
LogAI v0.1.0
✓ LLM Provider: anthropic
✓ LLM Model: claude-3-5-sonnet-20241022
✓ AWS Region: us-east-1 (from environment/default)
✓ AWS Profile: production (from environment)
✓ PII Sanitization: Enabled
✓ Cache Directory: /Users/yourname/.logai/cache
```

Use `/config` command while running to see current configuration:

```
/config
```

---

## See Also

- **[Getting Started](getting-started.md)** - Installation and first run
- **[CLI Reference](cli-reference.md)** - Command-line arguments
- **[Features Overview](features.md)** - All LogAI features
- **[Troubleshooting](troubleshooting.md)** - Configuration issues
