# Documentation Quick Start Guide

Quick reference for navigating the LogAI documentation.

## Start Here Based on Your Role

### 📘 I'm a User
**Go to:** [docs/user-guide/README.md](docs/user-guide/README.md)

Essential docs:
1. [Getting Started](docs/user-guide/getting-started.md) - Install and run LogAI
2. [Configuration](docs/user-guide/configuration.md) - Set up LLM providers
3. [Examples](docs/user-guide/examples.md) - Common queries
4. [Troubleshooting](docs/user-guide/troubleshooting.md) - Fix issues

### 🏗️ I'm an Architect
**Go to:** [docs/architecture/README.md](docs/architecture/README.md)

Essential docs:
1. [Architecture Overview](docs/architecture/overview.md) - Complete system design
2. [Context Management](docs/architecture/context-management-system.md)
3. [GitHub Copilot Integration](docs/architecture/github-copilot-integration.md)

### 💻 I'm a Developer
**Go to:** [docs/development/README.md](docs/development/README.md)

Essential docs:
1. [Feature Workflow](docs/development/feature-workflow.md) - How we build features
2. [Textual Best Practices](docs/development/textual-best-practices.md) - TUI patterns
3. [Testing Standards](docs/development/testing-standards.md) - How to test
4. [Local Deployment](docs/development/local-deployment.md) - Run locally

### 📋 I'm a Project Manager / QA
**Go to:** [docs/internal/README.md](docs/internal/README.md)

Find: Requirements, code reviews, QA reports, investigations (87 files)

## Common Tasks

| I want to... | Go here |
|--------------|---------|
| Install LogAI | [docs/user-guide/getting-started.md](docs/user-guide/getting-started.md) |
| Configure Ollama | [docs/ollama-setup.md](docs/ollama-setup.md) |
| Learn query patterns | [docs/user-guide/examples.md](docs/user-guide/examples.md) |
| Fix an issue | [docs/user-guide/troubleshooting.md](docs/user-guide/troubleshooting.md) |
| Understand architecture | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Contribute code | [docs/development/feature-workflow.md](docs/development/feature-workflow.md) |
| Run tests | [docs/development/testing-standards.md](docs/development/testing-standards.md) |
| Review requirements | [docs/internal/](docs/internal/) (search requirements-*.md) |

## Documentation Structure

```
docs/
├── README.md                    # Complete navigation hub
├── user-guide/                  # 16 files - End-user docs
├── architecture/                # 15 files - System design
├── development/                 # 13 files - Developer guides
├── internal/                    # 88 files - Requirements, reviews, QA
├── ollama-setup.md             # Ollama configuration
├── phase7-completion.md        # Phase 7 summary
└── tui.md                      # TUI overview
```

## Quick Topic Search

### LLM / AI
- User: [Configuration](docs/user-guide/configuration.md#llm-providers)
- Architecture: [LLM Integration](docs/architecture/overview.md#6-llm-integration-design)

### TUI / Interface
- User: [Runtime Commands](docs/user-guide/runtime-commands.md)
- Developer: [Textual Best Practices](docs/development/textual-best-practices.md)

### Caching
- User: [Cached Results](docs/user-guide/cached-results.md)
- Architecture: [Cache Design](docs/architecture/design-cache-llm.md)

### Testing
- Developer: [Testing Standards](docs/development/testing-standards.md)
- Internal: [QA Reports](docs/internal/) (qa-report-*.md)

## Need Help?

1. **Start with:** [docs/README.md](docs/README.md) - Complete navigation
2. **Can't find something?** Check the README in each directory
3. **Have feedback?** Create an issue or submit a PR

---

**Ready?** Pick your role above and dive in!
