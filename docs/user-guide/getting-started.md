# Getting Started with LogAI

Welcome to LogAI! This guide will help you install, configure, and run LogAI for the first time.

## What is LogAI?

LogAI is an AI-powered observability assistant that lets you query AWS CloudWatch logs using natural language. Instead of writing complex CloudWatch query syntax, simply ask questions in plain English and LogAI uses Large Language Models (LLMs) to fetch and analyze your logs.

## Requirements

Before installing LogAI, ensure you have:

- **Python 3.11 or higher** - Check with `python --version`
- **AWS Credentials** - With CloudWatch Logs read access
- **LLM Provider Access** - One of the following:
  - Anthropic API key (Claude models)
  - OpenAI API key (GPT models)
  - GitHub Copilot subscription (access to 25+ models)
  - Ollama installation (for local models)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/logai/logai.git
cd logai
```

### Step 2: Install LogAI

Install LogAI in development mode:

```bash
pip install -e .
```

Or install with development dependencies if you plan to contribute:

```bash
pip install -e ".[dev]"
```

### Step 3: Verify Installation

Check that LogAI is installed correctly:

```bash
logai --version
```

You should see output like: `logai 0.1.0`

## Configuration

### Step 1: Create Configuration File

Copy the example environment file:

```bash
cp .env.example .env
```

### Step 2: Configure LLM Provider

Edit `.env` and choose your LLM provider. You have four options:

#### Option A: Anthropic Claude (Recommended)

```bash
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=your-api-key-here
LOGAI_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

Get your API key from: https://console.anthropic.com/

#### Option B: OpenAI GPT

```bash
LOGAI_LLM_PROVIDER=openai
LOGAI_OPENAI_API_KEY=your-api-key-here
LOGAI_OPENAI_MODEL=gpt-4-turbo-preview
```

Get your API key from: https://platform.openai.com/api-keys

#### Option C: GitHub Copilot (25+ Models)

If you have a GitHub Copilot subscription, you can access 25+ models from Claude, GPT, Gemini, and more:

```bash
LOGAI_LLM_PROVIDER=github-copilot
LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
```

Then authenticate:

```bash
logai auth login
```

Follow the browser prompt to complete authentication. No API key needed!

See [Configuration Guide](configuration.md#github-copilot) for the full list of available models.

#### Option D: Ollama (Local Models)

For privacy-focused or offline usage:

1. Install Ollama:
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Pull a function-calling capable model:
   ```bash
   ollama pull llama3.1:8b
   ```

3. Start Ollama server:
   ```bash
   ollama serve
   ```

4. Configure LogAI:
   ```bash
   LOGAI_LLM_PROVIDER=ollama
   LOGAI_OLLAMA_BASE_URL=http://localhost:11434
   LOGAI_OLLAMA_MODEL=llama3.1:8b
   ```

### Step 3: Configure AWS Credentials

Add your AWS credentials to `.env`. You can use one of two methods:

#### Method 1: Direct Credentials

```bash
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

#### Method 2: AWS Profile

```bash
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=your-aws-profile-name
```

**Note**: Command-line arguments will override these settings. See [CLI Reference](cli-reference.md) for details.

### Step 4: Optional Settings

Configure additional settings as needed:

```bash
# Enable PII sanitization (recommended - enabled by default)
LOGAI_PII_SANITIZATION_ENABLED=true

# Cache settings
LOGAI_CACHE_DIR=~/.logai/cache
LOGAI_CACHE_MAX_SIZE_MB=500

# Agent behavior
LOGAI_MAX_TOOL_ITERATIONS=10
```

See [Configuration Guide](configuration.md) for all available settings.

## First Run

### Start LogAI

Launch LogAI with your configuration:

```bash
logai
```

You should see the startup screen showing your configuration:

```
LogAI v0.1.0
✓ LLM Provider: anthropic
✓ LLM Model: claude-3-5-sonnet-20241022
✓ AWS Region: us-east-1 (from environment/default)
✓ PII Sanitization: Enabled
✓ Cache Directory: /Users/yourname/.logai/cache

Initializing components...
⏳ Loading log groups from AWS... (52 found)
✓ Found 135 log groups (1234ms)
✓ All components initialized

Starting TUI...
```

### What Happens During Startup

When LogAI starts, it automatically:

1. **Loads Your Log Groups** - Fetches all CloudWatch log groups from your AWS account
2. **Shows Progress** - Displays "Loading log groups..." with a running count
3. **Provides Context to Agent** - Makes the complete list available to the AI assistant

**Why this is helpful:**
- **Faster queries** - The agent already knows your log groups, no need to look them up
- **Better suggestions** - Agent can recommend relevant log groups
- **Reduced API calls** - Fewer requests to AWS CloudWatch

**What you'll see:**
- Progress indicator: `⏳ Loading log groups from AWS... (52 found)`
- Success message: `✓ Found 135 log groups (1234ms)`
- If loading fails: `⚠ Failed to load log groups: [error details]` (app continues, agent can still discover log groups)

**Note:** If you have many log groups (1000+), this may take a few seconds. LogAI shows progress updates in real-time.

### Understanding the Interface

LogAI opens with an interactive terminal interface featuring:

1. **Chat Area** (center) - Where you ask questions and see responses
2. **Tool Sidebar** (right) - Shows which tools the agent is using in real-time
3. **Input Box** (bottom) - Where you type your queries
4. **Status Bar** (very bottom) - Shows keyboard shortcuts

### Try Your First Query

Type a simple query to test the connection:

```
List all my log groups
```

Press **Enter** to send. You should see:

1. The agent calling the `list_log_groups` tool (visible in the right sidebar)
2. A list of your CloudWatch log groups
3. Tool execution details in the sidebar (status, duration, results)

### More Example Queries

Try these queries to explore LogAI's capabilities:

```
Show me errors from /aws/lambda/my-function in the last hour
```

```
Search for "timeout" across all Lambda functions
```

```
What are the most common errors in the last 24 hours?
```

See [Usage Examples](examples.md) for more query ideas.

## Using Command-Line Arguments

You can override configuration settings using command-line arguments. This is especially useful when switching between AWS accounts or regions:

```bash
# Use a specific AWS profile
logai --aws-profile production

# Override both profile and region
logai --aws-profile staging --aws-region us-west-2
```

See [CLI Reference](cli-reference.md) for all available options.

## Common Slash Commands

While LogAI is running, you can use these special commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/refresh` | Update the list of log groups from AWS |
| `/tools` | Toggle tool sidebar visibility |
| `/cache status` | Show cache statistics |
| `/cache clear` | Clear the cache |
| `/clear` | Clear conversation history |
| `/exit` or `/quit` | Exit LogAI |

See [Runtime Commands](runtime-commands.md) for complete documentation.

## Keyboard Shortcuts

- **Ctrl+C** or **Ctrl+Q** - Exit LogAI
- **Ctrl+D** - Exit LogAI
- **Up/Down Arrow** - Navigate command history (in input box)
- **Page Up/Down** - Scroll chat area

## What's Next?

Now that LogAI is running, explore these guides:

- **[Features Overview](features.md)** - Learn about all LogAI features
- **[Usage Examples](examples.md)** - Common queries and workflows
- **[Configuration Guide](configuration.md)** - Advanced configuration options
- **[Runtime Commands](runtime-commands.md)** - All slash commands
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## Quick Troubleshooting

### "Configuration Error: LOGAI_ANTHROPIC_API_KEY is required"

You haven't configured your LLM provider credentials. Edit `.env` and add your API key for your chosen provider.

### "AWS credentials not found"

Configure your AWS credentials in `.env` or use the `--aws-profile` argument to specify an AWS profile.

### "No log groups found"

Your AWS credentials may not have the correct permissions, or you're connected to the wrong region. Check:
- Your AWS region setting matches where your log groups are located
- Your IAM user/role has `logs:DescribeLogGroups` permission
- Try using `/refresh` to reload the list after fixing credentials

### Startup is slow

If you have many log groups (1000s), loading them at startup may take 10-30 seconds. This is normal:
- LogAI shows progress: "Loading... (234 found)"
- This happens once at startup
- Improves performance for all subsequent queries

### Tool sidebar not showing

Use the `/tools` command to toggle the sidebar visibility. It's shown by default.

For more troubleshooting help, see [Troubleshooting Guide](troubleshooting.md).

## Getting Help

- **In-app help**: Type `/help` while running LogAI
- **Report bugs**: https://github.com/logai/logai/issues
- **Request features**: https://github.com/logai/logai/issues
- **Documentation**: https://github.com/logai/logai/docs
