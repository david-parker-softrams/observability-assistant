# Troubleshooting Guide

This guide helps you resolve common issues when using LogAI.

## Installation Issues

### Python Version Too Old

**Problem:**
```
ERROR: Python 3.11 or higher is required
```

**Solution:**

Check your Python version:
```bash
python --version
```

If you have Python 3.11+ but it's named differently:
```bash
python3.11 --version
python3 --version
```

Install LogAI with the correct Python version:
```bash
python3.11 -m pip install -e .
```

Update your system Python (varies by OS):
```bash
# macOS with Homebrew
brew install python@3.11

# Ubuntu/Debian
sudo apt update && sudo apt install python3.11

# Windows (download from python.org)
```

---

### Package Installation Fails

**Problem:**
```
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**

**1. Update pip:**
```bash
python -m pip install --upgrade pip
```

**2. Install with verbose logging:**
```bash
pip install -e . -v
```

**3. Install dependencies separately:**
```bash
pip install textual boto3 litellm pydantic pydantic-settings
pip install -e .
```

**4. Use a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

---

## Configuration Issues

### "Configuration Error: API key required"

**Problem:**
```
❌ Configuration Error: LOGAI_ANTHROPIC_API_KEY is required when using Anthropic provider
```

**Solution:**

**1. Check your `.env` file exists:**
```bash
ls -la .env
```

If not found:
```bash
cp .env.example .env
```

**2. Edit `.env` and add your API key:**
```bash
# For Anthropic
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# OR for OpenAI
LOGAI_LLM_PROVIDER=openai
LOGAI_OPENAI_API_KEY=sk-xxxxx

# OR for GitHub Copilot (no API key needed)
LOGAI_LLM_PROVIDER=github-copilot
LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
```

**3. Verify the file is in the correct location:**

The `.env` file must be in the same directory where you run `logai`.

```bash
pwd           # Check current directory
ls .env       # Verify file is here
logai         # Run from this directory
```

---

### "AWS credentials not found"

**Problem:**
```
❌ Configuration Error: AWS credentials not found
```

**Solutions:**

**Method 1: Use AWS Profile**

```bash
# Configure AWS CLI
aws configure --profile my-profile

# Or use existing profile
export AWS_PROFILE=my-profile
logai

# Or use CLI argument
logai --aws-profile my-profile
```

**Method 2: Direct Credentials**

Edit `.env`:
```bash
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_DEFAULT_REGION=us-east-1
```

**Method 3: IAM Role** (EC2/ECS)

If running on AWS infrastructure with an IAM role:
```bash
# Just set the region
AWS_DEFAULT_REGION=us-east-1
```

LogAI will automatically use the instance IAM role.

**Verify AWS credentials work:**
```bash
aws sts get-caller-identity --profile my-profile
```

---

### "Region is required"

**Problem:**
```
❌ Configuration Error: AWS_DEFAULT_REGION is required
```

**Solution:**

Set the region in `.env`:
```bash
AWS_DEFAULT_REGION=us-east-1
```

Or use CLI argument:
```bash
logai --aws-region us-east-1
```

Or export environment variable:
```bash
export AWS_DEFAULT_REGION=us-east-1
logai
```

**Common AWS Regions:**
- `us-east-1` - US East (N. Virginia)
- `us-west-2` - US West (Oregon)
- `eu-west-1` - Europe (Ireland)
- `ap-southeast-1` - Asia Pacific (Singapore)

---

### Configuration Not Loading

**Problem:**

Settings in `.env` are ignored.

**Debugging Steps:**

**1. Verify file name and location:**
```bash
# Must be named exactly ".env" (with leading dot)
ls -la .env

# Must be in the directory where you run logai
pwd
```

**2. Check for syntax errors:**
```bash
# No spaces around = sign
LOGAI_LLM_PROVIDER=anthropic        # ✓ Correct
LOGAI_LLM_PROVIDER = anthropic      # ✗ Wrong

# No quotes needed (usually)
AWS_PROFILE=my-profile              # ✓ Correct
AWS_PROFILE="my-profile"            # ✓ Also works

# Comments with #
# This is a comment                 # ✓ Correct
```

**3. Test configuration loading:**
```bash
python -c "from logai.config.settings import LogAISettings; print(LogAISettings())"
```

**4. Use environment variables as workaround:**
```bash
export LOGAI_LLM_PROVIDER=anthropic
export LOGAI_ANTHROPIC_API_KEY=your-key
export AWS_DEFAULT_REGION=us-east-1
export AWS_PROFILE=my-profile
logai
```

---

## Authentication Issues

### GitHub Copilot Authentication Fails

**Problem:**
```
❌ Authentication failed: Token request timed out
```

**Solutions:**

**1. Increase timeout:**
```bash
logai auth login --timeout 1200
```

**2. Check GitHub Copilot subscription:**

Visit: https://github.com/settings/copilot

Ensure you have an active GitHub Copilot subscription.

**3. Check internet connection:**
```bash
curl -I https://github.com
```

**4. Try again:**

Authentication tokens expire. The flow:
```bash
logai auth login
# Open browser to URL shown
# Enter device code
# Authorize LogAI
```

**5. Manual token cleanup:**

If stuck in bad state:
```bash
rm ~/.local/share/logai/auth.json
logai auth login
```

---

### "Not authenticated" when using GitHub Copilot

**Problem:**
```
❌ LLM provider error: Not authenticated
```

**Solution:**

Authenticate first:
```bash
logai auth status        # Check status
logai auth login         # Authenticate
logai                    # Run LogAI
```

---

## Runtime Issues

### "No log groups found"

**Problem:**

Agent reports no log groups available.

**Causes & Solutions:**

**1. Wrong AWS Region**

Check which region you're connected to:
```bash
/config
```

Look for: `AWS Region: us-east-1`

Change region:
```bash
# Exit LogAI (Ctrl+C)
logai --aws-region us-west-2

# Or update .env
AWS_DEFAULT_REGION=us-west-2
```

**2. Insufficient Permissions**

Your AWS credentials may lack permissions. Required permissions:
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`
- `logs:FilterLogEvents`
- `logs:GetLogEvents`

Test permissions:
```bash
aws logs describe-log-groups --profile my-profile --region us-east-1
```

**3. No Logs in This Region**

Your logs might be in a different region:
```bash
# List regions with log groups
for region in us-east-1 us-west-2 eu-west-1; do
  echo "Region: $region"
  aws logs describe-log-groups --region $region --max-items 5
done
```

---

### "Maximum tool iterations exceeded"

**Problem:**
```
Maximum tool iterations (10) exceeded. The conversation may be stuck in a loop.
```

**Causes:**

The agent is calling too many tools, potentially in a loop.

**Solutions:**

**1. Clear conversation history:**
```
/clear
```

Then try a simpler, more specific query.

**2. Increase iteration limit:**

Edit `.env`:
```bash
LOGAI_MAX_TOOL_ITERATIONS=20
```

Restart LogAI.

**3. Disable auto-retry temporarily:**

Edit `.env`:
```bash
LOGAI_AUTO_RETRY_ENABLED=false
```

This prevents the agent from retrying failed queries.

**4. Be more specific in your query:**

**Instead of:**
```
Find everything
```

**Try:**
```
Find errors in /aws/lambda/my-function in the last hour
```

---

### Slow Performance

**Problem:**

Queries take a long time to complete.

**Solutions:**

**1. Check cache hit rate:**
```
/cache status
```

Look for: `Hit Rate: XX%`

If hit rate is low (<50%), increase cache size:
```bash
# In .env
LOGAI_CACHE_MAX_SIZE_MB=1000
LOGAI_CACHE_TTL_SECONDS=172800  # 48 hours
```

**2. Use more specific queries:**

**Slow:**
```
Show me all logs
```

**Faster:**
```
Show me errors from /aws/lambda/api in the last hour
```

**3. Check AWS API latency:**

```bash
time aws logs describe-log-groups --region us-east-1 --profile my-profile
```

If AWS API is slow, LogAI will also be slow.

**4. Reduce time range:**

**Slow:**
```
Find errors in the last 7 days
```

**Faster:**
```
Find errors in the last 24 hours
```

**5. Use filter patterns:**

**Slow:**
```
Show me all logs from X, find errors
```

**Faster:**
```
Search for "ERROR" in log group X
```

---

### Cache Issues

**Problem:**

Cache grows too large or has stale data.

**Solutions:**

**1. Clear cache:**
```
/cache clear
```

**2. Reduce cache size:**

Edit `.env`:
```bash
LOGAI_CACHE_MAX_SIZE_MB=250
```

**3. Reduce TTL:**

Edit `.env`:
```bash
LOGAI_CACHE_TTL_SECONDS=43200  # 12 hours instead of 24
```

**4. Manual cache cleanup:**

```bash
# Exit LogAI first
rm -rf ~/.logai/cache/*
```

---

### Sidebar Not Showing

**Problem:**

Tool sidebar is missing or invisible.

**Solutions:**

**1. Toggle sidebar:**
```
/tools
```

**2. Expand terminal width:**

The sidebar requires at least 80 columns total width.

Check terminal size:
```bash
tput cols  # Should be 80+
```

Resize terminal or use fullscreen.

**3. Check for UI errors:**

Run with debug logging:
```bash
export LOGAI_LOG_LEVEL=DEBUG
logai
```

Check for UI-related errors in output.

---

## LLM Provider Issues

### Anthropic API Errors

**Problem:**
```
❌ LLM provider error: Invalid API key
```

**Solutions:**

**1. Verify API key:**

Check your API key at: https://console.anthropic.com/

**2. Update `.env`:**
```bash
LOGAI_ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

**3. Check API key format:**

Anthropic keys start with `sk-ant-api03-`

**4. Test API key:**
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $LOGAI_ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

---

### OpenAI API Errors

**Problem:**
```
❌ LLM provider error: Incorrect API key provided
```

**Solutions:**

**1. Verify API key:**

Check your API key at: https://platform.openai.com/api-keys

**2. Update `.env`:**
```bash
LOGAI_OPENAI_API_KEY=sk-xxxxx
```

**3. Check API key format:**

OpenAI keys start with `sk-`

**4. Check billing:**

Ensure your OpenAI account has credits: https://platform.openai.com/account/billing

---

### GitHub Copilot Model Not Available

**Problem:**
```
❌ Model claude-opus-4.6 not available
```

**Solutions:**

**1. Check available models:**
```bash
logai auth status
```

**2. Use a known working model:**
```bash
# In .env
LOGAI_GITHUB_COPILOT_MODEL=gpt-4o-mini
```

**3. Refresh model cache:**
```bash
rm ~/.local/share/logai/github_copilot_models.json
logai auth login
```

**4. Try popular models:**
- `gpt-4o-mini` (Fast, reliable)
- `claude-opus-4.6` (Powerful)
- `gemini-2.5-flash` (Fast alternative)

---

### Ollama Connection Failed

**Problem:**
```
❌ LLM provider error: Connection refused to http://localhost:11434
```

**Solutions:**

**1. Start Ollama server:**
```bash
ollama serve
```

**2. Check Ollama is running:**
```bash
curl http://localhost:11434/api/tags
```

**3. Verify model is pulled:**
```bash
ollama list
```

If model not found:
```bash
ollama pull llama3.1:8b
```

**4. Check base URL in `.env`:**
```bash
LOGAI_OLLAMA_BASE_URL=http://localhost:11434
```

---

## AWS Issues

### Permission Denied

**Problem:**
```
❌ AccessDeniedException: User is not authorized
```

**Solution:**

Your AWS credentials lack required permissions. Add this IAM policy:

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

Or use an existing policy: `CloudWatchLogsReadOnlyAccess`

---

### Rate Limiting

**Problem:**
```
❌ ThrottlingException: Rate exceeded
```

**Solutions:**

**1. Enable caching** (should be enabled by default):
```bash
# In .env
LOGAI_CACHE_MAX_SIZE_MB=500
LOGAI_CACHE_TTL_SECONDS=86400
```

**2. Reduce query frequency:**

Wait a few seconds between queries.

**3. Use more specific queries:**

Avoid queries that scan many log groups.

**4. Check cache status:**
```
/cache status
```

High cache hit rate reduces AWS API calls.

---

## Data Issues

### PII Not Sanitized

**Problem:**

Sensitive data visible in LLM responses.

**Solution:**

**1. Verify PII sanitization is enabled:**
```
/config
```

Look for: `PII Sanitization: Enabled`

**2. Enable in `.env` if disabled:**
```bash
LOGAI_PII_SANITIZATION_ENABLED=true
```

**3. Restart LogAI:**
```bash
# Exit and restart
logai
```

**4. Clear cache:**

Old cached data may not be sanitized:
```
/cache clear
```

---

### Empty Results

**Problem:**

Queries return no results when logs should exist.

**Debugging:**

**1. Check tool sidebar:**

Press `/tools` to show sidebar (if hidden).

Look at:
- Which tools were called
- What parameters were used
- What results were returned

**2. Verify time range:**

The agent might be using a time range that's too narrow.

Try explicitly:
```
Show me logs from the last 24 hours
```

**3. Verify log group name:**
```
List my log groups
```

Confirm the exact log group name, then use it explicitly:
```
Show me logs from /aws/lambda/exact-name
```

**4. Check auto-retry:**

Ensure auto-retry is enabled:
```bash
# In .env
LOGAI_AUTO_RETRY_ENABLED=true
```

**5. Try with DEBUG logging:**
```bash
export LOGAI_LOG_LEVEL=DEBUG
logai
```

Check logs for details about why no results were found.

---

## Getting More Help

### Enable Debug Logging

For any issue, debug logging helps:

```bash
export LOGAI_LOG_LEVEL=DEBUG
logai
```

Or in `.env`:
```bash
LOGAI_LOG_LEVEL=DEBUG
```

### Check Configuration

Verify your settings:
```
/config
```

### Check Tool Execution

Enable tool sidebar:
```
/tools
```

Watch what tools are being called and what results they return.

### Report Bugs

If you've found a bug:

1. **Collect information:**
   - LogAI version: `logai --version`
   - Python version: `python --version`
   - Operating system
   - Steps to reproduce
   - Error messages (full text)
   - Debug logs (if possible)

2. **Search existing issues:**
   https://github.com/logai/logai/issues

3. **Create new issue:**
   https://github.com/logai/logai/issues/new

### Community Support

- **GitHub Discussions:** https://github.com/logai/logai/discussions
- **Documentation:** https://github.com/logai/logai/docs

---

## See Also

- **[Getting Started](getting-started.md)** - Installation and setup
- **[Configuration Guide](configuration.md)** - All settings
- **[CLI Reference](cli-reference.md)** - Command-line options
- **[Features Overview](features.md)** - What LogAI can do
