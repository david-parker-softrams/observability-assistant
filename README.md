# LogAI 🚀

**AI-powered observability assistant for AWS CloudWatch logs**

Query your AWS CloudWatch logs using natural language. LogAI uses Large Language Models (LLMs) with function calling to intelligently fetch and analyze logs, providing insights and root cause analysis through an interactive chat interface.

## ✨ Features

- 🤖 **Natural Language Queries**: Ask questions about your logs in plain English
- 🔍 **Intelligent Log Analysis**: LLM-powered pattern recognition and root cause analysis
- 🛡️ **PII Sanitization**: Automatic redaction of sensitive data (emails, IPs, API keys, etc.)
- ⚡ **Smart Caching**: SQLite-based caching to minimize AWS API calls
- 🎨 **Interactive TUI**: Beautiful terminal user interface built with Textual
- 🔌 **Multiple LLM Providers**: Support for Anthropic Claude and OpenAI GPT models
- 📊 **AWS CloudWatch Integration**: Seamless integration with CloudWatch Logs

## 📋 Requirements

- Python 3.11 or higher
- AWS credentials with CloudWatch Logs read access
- API key for Anthropic Claude or OpenAI GPT

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/logai/logai.git
cd logai

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and configure your credentials:
```bash
# LLM Provider (choose one)
LOGAI_LLM_PROVIDER=anthropic
LOGAI_ANTHROPIC_API_KEY=your-api-key-here

# AWS Credentials
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Usage

Start the interactive chat interface:
```bash
logai
```

Or run as a Python module:
```bash
python -m logai
```

## 💬 Example Queries

Once LogAI is running, try these example queries:

```
🗨️ List all my log groups

🗨️ Show me errors from /aws/lambda/my-function in the last hour

🗨️ Search for "timeout" errors across all Lambda functions in the past 24 hours

🗨️ What are the most common error patterns in the auth-service today?

🗨️ Compare error rates between service-a and service-b over the last 6 hours
```

## 🛠️ Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOGAI_LLM_PROVIDER` | LLM provider (anthropic/openai) | `anthropic` | Yes |
| `LOGAI_ANTHROPIC_API_KEY` | Anthropic API key | - | If using Anthropic |
| `LOGAI_OPENAI_API_KEY` | OpenAI API key | - | If using OpenAI |
| `LOGAI_PII_SANITIZATION_ENABLED` | Enable PII redaction | `true` | No |
| `LOGAI_CACHE_DIR` | Cache directory path | `~/.logai/cache` | No |
| `LOGAI_CACHE_MAX_SIZE_MB` | Max cache size (MB) | `500` | No |
| `AWS_DEFAULT_REGION` | AWS region | - | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | Yes* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | Yes* |
| `AWS_PROFILE` | AWS CLI profile | - | Yes* |

\* Either provide `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or `AWS_PROFILE`

### Special Commands

Within the LogAI chat interface:

- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/cache status` - Show cache statistics
- `/cache clear` - Clear cache
- `/quit` or `/exit` - Exit application

## 🏗️ Architecture

LogAI follows a layered architecture:

```
┌─────────────────────────────────────┐
│   User Interface Layer (TUI)        │
│   - Textual-based chat interface    │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│   Application Core Layer            │
│   - LLM Orchestrator                │
│   - Tool Registry & Execution       │
│   - PII Sanitization                │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│   Integration Layer                 │
│   - LiteLLM (Unified LLM API)       │
│   - CloudWatch Data Source          │
│   - SQLite Cache Manager            │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│   External Services                 │
│   - Anthropic/OpenAI APIs           │
│   - AWS CloudWatch Logs             │
└─────────────────────────────────────┘
```

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=logai --cov-report=html

# Run specific test file
pytest tests/unit/test_sanitizer.py

# Run integration tests (requires AWS credentials)
pytest tests/integration/
```

### Type Checking

```bash
mypy src/logai
```

### Linting

```bash
ruff check src/logai tests/
```

### Code Formatting

```bash
ruff format src/logai tests/
```

## 📚 Documentation

- [Architecture Document](docs/architecture.md) - Detailed system design
- [Configuration Guide](docs/configuration.md) - Advanced configuration options
- [Development Guide](docs/development.md) - Contributing guidelines

## 🔒 Security & Privacy

### PII Sanitization

LogAI includes built-in PII sanitization that redacts sensitive information before sending logs to LLM providers:

- Email addresses
- IP addresses (IPv4/IPv6)
- Credit card numbers
- Social Security Numbers
- Phone numbers
- AWS access keys
- API keys and tokens
- JWT tokens
- Private keys

PII sanitization is **enabled by default** but can be disabled via `LOGAI_PII_SANITIZATION_ENABLED=false`.

### Data Storage

- Logs are cached locally in SQLite database (`~/.logai/cache/cache.db` by default)
- Cache is stored on your local filesystem only
- No data is sent to external services except the configured LLM provider and AWS CloudWatch

## 🗺️ Roadmap

### MVP (Current)
- ✅ AWS CloudWatch Logs integration
- ✅ Anthropic Claude & OpenAI GPT support
- ✅ Interactive TUI chat interface
- ✅ PII sanitization
- ✅ SQLite caching

### Post-MVP
- ⬜ Additional data sources (Splunk, Datadog, New Relic)
- ⬜ Metrics support (not just logs)
- ⬜ Web UI with visualizations and graphs
- ⬜ AWS Bedrock integration
- ⬜ Saved queries and sessions
- ⬜ Alert integration
- ⬜ Multi-source correlation

## 🤝 Contributing

Contributions are welcome! Please see our [Development Guide](docs/development.md) for details.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- Built with [Textual](https://textual.textualize.io/) for the amazing TUI framework
- Powered by [LiteLLM](https://github.com/BerriAI/litellm) for unified LLM access
- Uses [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for AWS integration

## 📞 Support

- 🐛 [Report bugs](https://github.com/logai/logai/issues)
- 💡 [Request features](https://github.com/logai/logai/issues)
- 📖 [Read the docs](https://github.com/logai/logai/docs)

---

Made with ❤️ by the LogAI Team
