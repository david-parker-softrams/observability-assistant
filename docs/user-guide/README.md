# LogAI User Guide

Welcome to the LogAI user documentation! This guide will help you get the most out of LogAI, an AI-powered observability assistant for AWS CloudWatch logs.

## Quick Navigation

### Getting Started
- **[Getting Started Guide](getting-started.md)** - Install, configure, and run LogAI for the first time
  - Installation steps
  - Configuration options
  - First query
  - Quick troubleshooting

### Reference Documentation
- **[CLI Reference](cli-reference.md)** - All command-line options and arguments
  - `--aws-profile`, `--aws-region`
  - `logai auth` commands
  - Usage examples
  
- **[Runtime Commands Reference](runtime-commands.md)** - Slash commands available while running
  - `/help`, `/clear`, `/cache`, `/tools`
  - Command usage and examples
  - Keyboard shortcuts

- **[Configuration Guide](configuration.md)** - Complete configuration reference
  - LLM provider settings (Anthropic, OpenAI, GitHub Copilot, Ollama)
  - AWS configuration
  - Agent behavior settings
  - Cache configuration
  - All environment variables

### User Guides
- **[Features Overview](features.md)** - What LogAI can do
  - Natural language queries
  - Tool execution sidebar (NEW)
  - Agent self-direction & auto-retry (NEW)
  - Smart caching
  - PII sanitization
  - Multi-provider LLM support
  - GitHub Copilot integration (25+ models)

- **[Usage Examples](examples.md)** - Common queries and workflows
  - Basic queries
  - Error investigation
  - Time-based queries
  - Service-specific queries
  - Advanced patterns
  - Workflow examples

- **[Troubleshooting Guide](troubleshooting.md)** - Common issues and solutions
  - Installation problems
  - Configuration errors
  - Authentication issues
  - Runtime problems
  - Performance issues

## Documentation by Task

### I want to...

#### Install and Set Up LogAI
1. Start with [Getting Started](getting-started.md)
2. Configure your settings using [Configuration Guide](configuration.md)
3. Test with example queries from [Usage Examples](examples.md)

#### Use GitHub Copilot Integration
1. Read [GitHub Copilot section](configuration.md#github-copilot-configuration) in Configuration Guide
2. Authenticate with `logai auth login`
3. Choose from 25+ available models
4. See [CLI Reference](cli-reference.md#authentication-commands) for auth commands

#### Troubleshoot Issues
1. Check [Troubleshooting Guide](troubleshooting.md) for your specific issue
2. Enable debug logging: `LOGAI_LOG_LEVEL=DEBUG`
3. Use `/config` to verify settings
4. Check tool sidebar with `/tools` to see what's happening

#### Learn Query Patterns
1. Browse [Usage Examples](examples.md) for common patterns
2. Try example queries from [Getting Started](getting-started.md#try-your-first-query)
3. Read [Features Overview](features.md) to understand capabilities

#### Configure Advanced Features
1. Review [Configuration Guide](configuration.md) for all options
2. Enable auto-retry behavior (on by default)
3. Configure caching for better performance
4. Set up PII sanitization (enabled by default)

#### Switch AWS Accounts or Regions
1. Use CLI arguments from [CLI Reference](cli-reference.md#aws-profile-profile)
2. Examples: `logai --aws-profile prod --aws-region us-west-2`
3. See [Configuration precedence](cli-reference.md#configuration-precedence)

## What's New in LogAI

### Latest Features

**Tool Execution Sidebar** (February 2026)
- Real-time visibility into agent tool execution
- See parameters, results, and status
- Expandable results for large datasets
- Toggle with `/tools` command
- [Learn more](features.md#tool-execution-sidebar)

**Agent Self-Direction** (February 2026)
- Automatic retry on empty results
- Time range expansion (1h → 6h → 24h)
- Intent detection (prevents "I'll try X" without action)
- Configurable behavior
- [Learn more](features.md#agent-self-direction--auto-retry)

**GitHub Copilot Integration** (February 2026)
- Access 25+ models with one subscription
- Claude, GPT, Gemini, and Grok models
- Simple OAuth authentication
- Cost-effective model access
- [Learn more](features.md#github-copilot-integration)

## Key Concepts

### Natural Language Queries

LogAI understands plain English queries instead of requiring complex syntax:

```
List all my log groups
Show me errors from /aws/lambda/my-function in the last hour
What are the most common error patterns today?
```

See: [Usage Examples](examples.md)

### Tool Execution

LogAI uses specialized tools to fetch and analyze logs:
- `list_log_groups` - Discover available logs
- `fetch_logs` - Retrieve from specific log group
- `search_logs` - Search across multiple groups

The sidebar shows exactly which tools are used for each query.

See: [Features - Intelligent Tool Execution](features.md#intelligent-tool-execution)

### Caching

Queries are cached locally to improve performance and reduce AWS API costs:
- First query: Fetches from CloudWatch
- Repeat query: Returns instantly from cache
- Configurable size and TTL

See: [Features - Smart Caching](features.md#smart-caching)

### PII Sanitization

Sensitive data is automatically redacted before sending to LLM providers:
- Email addresses, IP addresses
- Credit cards, SSNs, phone numbers
- API keys, tokens, private keys

See: [Features - PII Sanitization](features.md#pii-sanitization)

## Quick Reference

### Essential Commands

**Starting LogAI:**
```bash
logai                                          # Use .env configuration
logai --aws-profile prod                       # Override AWS profile
logai --aws-profile prod --aws-region us-west-2  # Override both
```

**While Running:**
```
/help                    Show available commands
/tools                   Toggle tool sidebar
/cache status            View cache statistics
/clear                   Clear conversation
/config                  Show configuration
/quit                    Exit (or Ctrl+C)
```

**GitHub Copilot:**
```bash
logai auth login         Authenticate
logai auth status        Check status
logai auth logout        Remove credentials
```

### Common Queries

```
List all my log groups
Show me errors from X in the last hour
Find timeout errors across Lambda functions
What are the most common errors today?
Compare errors between service-a and service-b
```

See: [Usage Examples](examples.md) for more

### Configuration Files

**`.env`** - Main configuration file
```bash
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=your-key
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=my-profile
```

See: [Configuration Guide](configuration.md) for all options

## Getting Help

### Documentation
- Read the guides in this directory
- Check [Troubleshooting Guide](troubleshooting.md) for common issues
- Use `/help` command while running LogAI

### In-App Help
```
/help                    Show available commands
/config                  Show current configuration
/tools                   View tool execution details
```

### Community
- **Report Bugs:** https://github.com/logai/logai/issues
- **Request Features:** https://github.com/logai/logai/issues
- **Discussions:** https://github.com/logai/logai/discussions
- **Documentation:** https://github.com/logai/logai/docs

## Contributing to Documentation

Found an error or want to improve the docs?

1. Documentation source: `docs/user-guide/`
2. Create an issue: https://github.com/logai/logai/issues
3. Submit a pull request with improvements

## Documentation Structure

```
docs/user-guide/
├── README.md                    # This file
├── getting-started.md           # Installation and first run
├── cli-reference.md             # Command-line options
├── runtime-commands.md          # Slash commands
├── configuration.md             # All settings and env vars
├── features.md                  # Feature descriptions
├── examples.md                  # Usage examples
└── troubleshooting.md          # Common issues
```

---

**Ready to get started?** Head to [Getting Started Guide](getting-started.md)!
