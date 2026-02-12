# Command-Line Reference

This document describes all command-line options and arguments for LogAI.

## Basic Usage

```bash
logai [OPTIONS]
logai [COMMAND]
```

## Global Options

### `--version`

Display the LogAI version and exit.

```bash
logai --version
```

**Example Output:**
```
logai 0.1.0
```

### `--help`

Show help message with all available commands and options, then exit.

```bash
logai --help
```

### `--aws-profile PROFILE`

Specify which AWS profile to use for CloudWatch access. This overrides the `AWS_PROFILE` environment variable.

```bash
logai --aws-profile production
```

**Use Cases:**
- Switching between different AWS accounts
- Testing in different environments without changing `.env`
- DevOps engineers managing multiple client accounts

**Configuration Precedence:**
1. `--aws-profile` argument (highest priority)
2. `AWS_PROFILE` environment variable
3. `AWS_PROFILE` in `.env` file
4. AWS default credential chain (lowest priority)

**Example:**
```bash
# Use production profile
logai --aws-profile production

# Use staging profile
logai --aws-profile staging
```

### `--aws-region REGION`

Specify which AWS region to use for CloudWatch. This overrides the `AWS_DEFAULT_REGION` environment variable.

```bash
logai --aws-region us-west-2
```

**Use Cases:**
- Querying logs from different regions
- Debugging region-specific issues
- Working with multi-region applications

**Configuration Precedence:**
1. `--aws-region` argument (highest priority)
2. `AWS_DEFAULT_REGION` environment variable
3. `AWS_DEFAULT_REGION` in `.env` file

**Example:**
```bash
# Query logs in us-west-2
logai --aws-region us-west-2

# Query logs in eu-west-1
logai --aws-region eu-west-1
```

### Combining AWS Options

You can combine both AWS options for maximum flexibility:

```bash
logai --aws-profile production --aws-region us-east-1
```

**Example Workflow:**
```bash
# Check production logs in us-east-1
logai --aws-profile prod --aws-region us-east-1

# Without changing files, check staging in us-west-2
logai --aws-profile staging --aws-region us-west-2

# Your .env file remains unchanged
```

## Authentication Commands

LogAI provides authentication commands for managing credentials with supported providers.

### `logai auth login`

Authenticate with GitHub Copilot using OAuth.

```bash
logai auth login
```

**What Happens:**
1. LogAI displays a device code and URL
2. You open the URL in your browser
3. Enter the device code shown
4. Authorize LogAI to access GitHub Copilot
5. Token is saved to `~/.local/share/logai/auth.json`

**Options:**
- `--timeout SECONDS` - Authentication timeout in seconds (default: 900)

**Example:**
```bash
# Use default 15-minute timeout
logai auth login

# Use custom timeout
logai auth login --timeout 600
```

**Troubleshooting:**
- If timeout occurs, run the command again
- Ensure you have an active GitHub Copilot subscription
- Check your internet connection

### `logai auth status`

Check GitHub Copilot authentication status.

```bash
logai auth status
```

**Example Output (Authenticated):**
```
🔍 GitHub Copilot Authentication Status

Provider: github-copilot
Authenticated: True
Token: ghu_xxxxxxxxxxxx...
Token file: /Users/yourname/.local/share/logai/auth.json
```

**Example Output (Not Authenticated):**
```
🔍 GitHub Copilot Authentication Status

Provider: github-copilot
Authenticated: False

Run 'logai auth login' to authenticate
```

### `logai auth logout`

Remove stored GitHub Copilot credentials.

```bash
logai auth logout
```

**What Happens:**
- Token file is deleted from `~/.local/share/logai/auth.json`
- You'll need to run `logai auth login` again to use GitHub Copilot

**Example Output:**
```
✅ Logged out successfully
```

### `logai auth list`

List all authenticated providers.

```bash
logai auth list
```

**Example Output:**
```
📋 Authenticated Providers

✓ github-copilot
```

## Usage Examples

### Start with Default Configuration

Use the configuration from your `.env` file:

```bash
logai
```

### Start with Specific Profile

Use a specific AWS profile:

```bash
logai --aws-profile my-profile
```

### Start with Profile and Region

Override both AWS profile and region:

```bash
logai --aws-profile production --aws-region us-west-2
```

### Check Version

Display version information:

```bash
logai --version
```

### Get Help

Display help message:

```bash
logai --help
```

### Authenticate with GitHub Copilot

Set up GitHub Copilot authentication:

```bash
logai auth login
```

### Check Authentication Status

Verify GitHub Copilot credentials:

```bash
logai auth status
```

## Environment Variables

Command-line arguments work alongside environment variables. Here's how they interact:

| Setting | CLI Argument | Environment Variable | Config File |
|---------|--------------|---------------------|-------------|
| AWS Profile | `--aws-profile` | `AWS_PROFILE` | `.env` |
| AWS Region | `--aws-region` | `AWS_DEFAULT_REGION` | `.env` |

**Precedence Order** (highest to lowest):
1. Command-line arguments
2. Environment variables (shell)
3. `.env` file

**Example:**
```bash
# .env file has:
# AWS_PROFILE=dev
# AWS_DEFAULT_REGION=us-east-1

# Shell environment has:
export AWS_PROFILE=staging

# Command line:
logai --aws-profile production

# Result: Uses 'production' profile (CLI wins)
```

## Startup Information

When you start LogAI with CLI arguments, the startup screen shows which configuration is active and where it came from:

```
LogAI v0.1.0
✓ LLM Provider: anthropic
✓ LLM Model: claude-3-5-sonnet-20241022
✓ AWS Region: us-west-2 (from CLI argument)
✓ AWS Profile: prod (from CLI argument)
✓ PII Sanitization: Enabled
✓ Cache Directory: ~/.logai/cache
```

Notice the "(from CLI argument)" indicators showing which settings came from the command line.

## Common Patterns

### DevOps Engineer Workflow

Quickly switch between environments:

```bash
# Morning: Check production
logai --aws-profile prod --aws-region us-east-1

# Afternoon: Debug staging
logai --aws-profile staging --aws-region us-west-2

# Evening: Test development
logai --aws-profile dev --aws-region us-east-1
```

### Multi-Client SRE

Manage multiple client accounts:

```bash
# Client A
logai --aws-profile client-a

# Client B
logai --aws-profile client-b

# Client C with specific region
logai --aws-profile client-c --aws-region eu-west-1
```

### Testing Different Models

Using GitHub Copilot, test different models:

```bash
# First authenticate once
logai auth login

# Edit .env to change model, then run
LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini logai

# Or in .env file:
# LOGAI_GITHUB_COPILOT_MODEL=claude-opus-4.6
logai
```

### One-Off Queries

Quick log check without modifying configuration files:

```bash
# Your .env has dev credentials
# But you need to check prod
logai --aws-profile prod --aws-region us-east-1

# Run your query, then exit
# Next run will use dev credentials from .env
```

## Exit Codes

LogAI uses standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Configuration error or runtime error |
| `130` | Interrupted by user (Ctrl+C) |

**Example:**
```bash
logai --aws-profile prod
echo $?  # Shows exit code
```

## See Also

- **[Configuration Guide](configuration.md)** - All environment variables and settings
- **[Getting Started](getting-started.md)** - Installation and setup
- **[Runtime Commands](runtime-commands.md)** - Slash commands available while running
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
