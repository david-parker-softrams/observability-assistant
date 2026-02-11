# LogAI 🚀

**AI-powered observability assistant for AWS CloudWatch logs**

Query your AWS CloudWatch logs using natural language. LogAI uses Large Language Models (LLMs) with function calling to intelligently fetch and analyze logs, providing insights and root cause analysis through an interactive chat interface.

## ✨ Features

- 🤖 **Natural Language Queries**: Ask questions about your logs in plain English
- 🔍 **Intelligent Log Analysis**: LLM-powered pattern recognition and root cause analysis
- 🛡️ **PII Sanitization**: Automatic redaction of sensitive data (emails, IPs, API keys, etc.)
- ⚡ **Smart Caching**: SQLite-based caching to minimize AWS API calls
- 🎨 **Interactive TUI**: Beautiful terminal user interface built with Textual
- 🔌 **Multiple LLM Providers**: Support for Anthropic Claude, OpenAI GPT, and Ollama (local models)
- 📊 **AWS CloudWatch Integration**: Seamless integration with CloudWatch Logs

## 📋 Requirements

- Python 3.11 or higher
- AWS credentials with CloudWatch Logs read access
- API key for Anthropic Claude or OpenAI GPT (or local Ollama installation)

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

### Using Ollama (Local Models)

For privacy-focused or offline usage, you can use local Ollama models:

1. **Install Ollama:**
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.ai
```

2. **Pull a function-calling capable model:**
```bash
ollama pull llama3.1:8b
# or for better performance (requires more RAM):
ollama pull llama3.1:70b
```

3. **Start Ollama server (if not already running):**
```bash
ollama serve
```

4. **Configure `.env`:**
```bash
LOGAI_LLM_PROVIDER=ollama
LOGAI_OLLAMA_BASE_URL=http://localhost:11434
LOGAI_OLLAMA_MODEL=llama3.1:8b
```

**Note**: Only models with function calling support will work (Llama 3.1, Mistral, etc.)

### Usage

Start the interactive chat interface:
```bash
logai
```

Or run as a Python module:
```bash
python -m logai
```

## 🔧 Command-Line Arguments

LogAI supports command-line arguments to override AWS configuration without modifying environment variables or `.env` files. This is especially useful for DevOps engineers and SREs who frequently switch between AWS accounts, profiles, or regions.

### AWS Profile and Region

Specify AWS profile and region directly via CLI arguments:

```bash
# Use a specific AWS profile
logai --aws-profile my-profile

# Specify both profile and region
logai --aws-profile prod --aws-region us-west-2

# Override environment variables
AWS_PROFILE=dev logai --aws-profile prod  # Uses 'prod', not 'dev'
```

### Configuration Precedence

When determining which AWS configuration to use, LogAI follows this precedence order (highest to lowest):

1. **Command-line arguments** (`--aws-profile`, `--aws-region`) - Highest priority
2. **Environment variables** (`AWS_PROFILE`, `AWS_DEFAULT_REGION`)
3. **Values from `.env` file**
4. **AWS default credential chain** (for profiles only)

**Key principle:** Command-line arguments always override environment variables and `.env` file settings.

### Practical Examples

**Switch between environments without changing `.env`:**
```bash
# Query production logs
logai --aws-profile prod --aws-region us-east-1

# Then query staging without modifying any files
logai --aws-profile staging --aws-region us-west-2
```

**Use different profiles for different accounts:**
```bash
# Client A logs
logai --aws-profile client-a

# Client B logs
logai --aws-profile client-b
```

**Override environment for one-off queries:**
```bash
# Your .env has AWS_PROFILE=dev, but you need to check prod
logai --aws-profile prod
```

**View configuration at startup:**

When you launch LogAI with CLI arguments, the startup output shows which configuration is active and where it came from:

```
LogAI v0.1.0
✓ LLM Provider: anthropic
✓ LLM Model: claude-3-5-sonnet-20241022
✓ AWS Region: us-west-2 (from CLI argument)
✓ AWS Profile: prod (from CLI argument)
✓ PII Sanitization: Enabled
✓ Cache Directory: ~/.logai/cache
```

### Available CLI Options

| Argument | Description | Example |
|----------|-------------|---------|
| `--aws-profile PROFILE` | AWS profile name for CloudWatch access | `--aws-profile prod` |
| `--aws-region REGION` | AWS region for CloudWatch | `--aws-region us-west-2` |
| `--version` | Display LogAI version | `--version` |
| `--help` | Show help message and examples | `--help` |

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
| `LOGAI_LLM_PROVIDER` | LLM provider (anthropic/openai/ollama) | `anthropic` | Yes |
| `LOGAI_ANTHROPIC_API_KEY` | Anthropic API key | - | If using Anthropic |
| `LOGAI_OPENAI_API_KEY` | OpenAI API key | - | If using OpenAI |
| `LOGAI_OLLAMA_BASE_URL` | Ollama base URL | `http://localhost:11434` | If using Ollama |
| `LOGAI_OLLAMA_MODEL` | Ollama model name | `llama3.1:8b` | If using Ollama |
| `LOGAI_PII_SANITIZATION_ENABLED` | Enable PII redaction | `true` | No |
| `LOGAI_CACHE_DIR` | Cache directory path | `~/.logai/cache` | No |
| `LOGAI_CACHE_MAX_SIZE_MB` | Max cache size (MB) | `500` | No |
| `AWS_DEFAULT_REGION` | AWS region (overridden by `--aws-region`) | - | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | Yes* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | Yes* |
| `AWS_PROFILE` | AWS CLI profile (overridden by `--aws-profile`) | - | Yes* |

\* Either provide `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` or `AWS_PROFILE`

**Note:** AWS-related environment variables can be overridden using command-line arguments. See [Command-Line Arguments](#-command-line-arguments) for details.

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
