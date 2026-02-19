# LogAI Documentation

Welcome to the LogAI documentation! This directory contains all documentation for the AI-Powered Observability Assistant.

## Documentation Structure

```
docs/
├── README.md                    # This file
├── user-guide/                  # End-user documentation
├── architecture/                # System architecture and design
├── development/                 # Developer guides and workflows
└── internal/                    # Requirements, reviews, and investigations
```

Plus root-level guides:
- `ollama-setup.md` - Ollama setup and configuration guide
- `phase7-completion.md` - Phase 7 project completion summary
- `tui.md` - TUI (Terminal User Interface) overview

## Quick Navigation

### 👥 For End Users
**Start here:** [user-guide/README.md](user-guide/README.md)

Get started using LogAI:
- [Getting Started](user-guide/getting-started.md) - Installation and first run
- [Configuration](user-guide/configuration.md) - LLM providers, AWS setup
- [Features Overview](user-guide/features.md) - What LogAI can do
- [Usage Examples](user-guide/examples.md) - Common queries and workflows
- [CLI Reference](user-guide/cli-reference.md) - Command-line options
- [Runtime Commands](user-guide/runtime-commands.md) - Slash commands
- [Troubleshooting](user-guide/troubleshooting.md) - Common issues

Feature-specific guides:
- [Timeframe Selector](user-guide/timeframe-selector.md) - Log preview timeframes
- [Context Management](user-guide/context-management.md) - Context system
- [Cached Results](user-guide/cached-results.md) - Working with cache
- [GitHub Models Provider](user-guide/github-models-provider.md) - Copilot integration

### 🏗️ For Architects and Technical Leads
**Start here:** [architecture/README.md](architecture/README.md)

Understand the system design:
- [Architecture Overview](architecture/overview.md) - Complete system architecture
- [Context Management System](architecture/context-management-system.md) - Context architecture
- [GitHub Copilot Integration](architecture/github-copilot-integration.md) - OAuth and API integration
- [Log Groups Sidebar](architecture/log-groups-sidebar.md) - Sidebar component
- [Preload Log Groups](architecture/preload-log-groups.md) - Background loading

Design documents:
- [Log Preview Design](architecture/design-log-preview.md)
- [Timeframe Selector Design](architecture/design-timeframe-selector.md)
- [Tool Sidebar Design](architecture/design-tool-sidebar.md)
- [Cache LLM Design](architecture/design-cache-llm.md)
- Plus 10+ more design documents

### 💻 For Developers
**Start here:** [development/README.md](development/README.md)

Learn the development workflow:
- [Feature Development Workflow](development/feature-workflow.md) - Complete process
- [Textual Best Practices](development/textual-best-practices.md) - TUI framework patterns
- [Testing Standards](development/testing-standards.md) - How to test
- [Local Deployment](development/local-deployment.md) - Setup guide

Agent and tool documentation:
- [Agent Self-Direction](development/agent-self-direction.md) - AI agent patterns
- [File Writing Guidelines](development/file-writing-guidelines.md) - Code standards
- [Tools Reference](development/tools-reference.md) - Available tools

Testing:
- [Manual Testing Plan](development/manual-testing-plan.md)
- [E2E Test: Context Management](development/e2e-test-context-management.md)
- [Tool Sidebar Testing](development/tool-sidebar-testing.md)

### 📋 For Project Managers and QA
**Start here:** [internal/README.md](internal/README.md)

Track project history and quality:
- Requirements documents (87 files)
- Code reviews
- QA reports and summaries
- Investigation reports
- Project status and summaries
- Testing and verification docs

## Documentation by Topic

### LLM and AI
- **User:** [Configuration - LLM Providers](user-guide/configuration.md#llm-providers)
- **User:** [GitHub Models Provider](user-guide/github-models-provider.md)
- **Architecture:** [LLM Integration Design](architecture/overview.md#6-llm-integration-design)
- **Architecture:** [GitHub Copilot Integration](architecture/github-copilot-integration.md)
- **Development:** [Agent Self-Direction](development/agent-self-direction.md)

### TUI (Terminal User Interface)
- **Root:** [tui.md](tui.md) - TUI overview
- **User:** [Runtime Commands](user-guide/runtime-commands.md) - Keyboard shortcuts
- **Architecture:** [Log Groups Sidebar](architecture/log-groups-sidebar.md)
- **Architecture:** [Tool Sidebar Design](architecture/design-tool-sidebar.md)
- **Development:** [Textual Best Practices](development/textual-best-practices.md)

### Log Management
- **User:** [Features - Log Fetching](user-guide/features.md#intelligent-tool-execution)
- **User:** [Timeframe Selector](user-guide/timeframe-selector.md)
- **Architecture:** [Log Preview Design](architecture/design-log-preview.md)
- **Architecture:** [Preload Log Groups](architecture/preload-log-groups.md)

### Caching
- **User:** [Cached Results Guide](user-guide/cached-results.md)
- **User:** [Features - Smart Caching](user-guide/features.md#smart-caching)
- **Architecture:** [Caching Strategy](architecture/overview.md#7-caching-strategy)
- **Architecture:** [Cache LLM Design](architecture/design-cache-llm.md)

### Context Management
- **User:** [Context Management Guide](user-guide/context-management.md)
- **User:** [Visual Context Guide](user-guide/visual-guide-context-management.md)
- **Architecture:** [Context Management System](architecture/context-management-system.md)
- **Architecture:** [Context Window Fixes](architecture/design-context-window-fixes.md)

### Configuration
- **User:** [Configuration Guide](user-guide/configuration.md)
- **User:** [AWS Profile Argument](user-guide/aws-profile-argument.md)
- **Architecture:** [Model Config Design](architecture/design-model-config.md)
- **Architecture:** [Config Cleanup](architecture/design-config-cleanup.md)

### Testing
- **Development:** [Testing Standards](development/testing-standards.md)
- **Development:** [Manual Testing Plan](development/manual-testing-plan.md)
- **Development:** [E2E Tests](development/e2e-test-context-management.md)
- **Internal:** QA reports and test summaries (multiple files)

### Ollama Integration
- **Root:** [ollama-setup.md](ollama-setup.md) - Complete Ollama setup guide
- **User:** [Configuration - Ollama](user-guide/configuration.md#ollama-configuration)
- **User:** [Troubleshooting - Ollama](user-guide/troubleshooting.md#ollama-issues)

## Common Tasks

### I want to...

#### Learn to use LogAI
1. Start: [user-guide/getting-started.md](user-guide/getting-started.md)
2. Configure: [user-guide/configuration.md](user-guide/configuration.md)
3. Try examples: [user-guide/examples.md](user-guide/examples.md)

#### Understand how LogAI works
1. Architecture: [architecture/overview.md](architecture/overview.md)
2. Components: Browse [architecture/](architecture/)
3. Design decisions: Review design docs in [architecture/](architecture/)

#### Contribute to LogAI
1. Workflow: [development/feature-workflow.md](development/feature-workflow.md)
2. Best practices: [development/textual-best-practices.md](development/textual-best-practices.md)
3. Testing: [development/testing-standards.md](development/testing-standards.md)
4. Setup: [development/local-deployment.md](development/local-deployment.md)

#### Troubleshoot an issue
1. User guide: [user-guide/troubleshooting.md](user-guide/troubleshooting.md)
2. Investigation reports: Browse [internal/](internal/) for similar issues
3. Root cause analyses: Check [internal/](internal/) for bug investigations

#### Review project history
1. Requirements: [internal/](internal/) - requirements-*.md files
2. Code reviews: [internal/](internal/) - code-review-*.md files
3. QA reports: [internal/](internal/) - qa-report-*.md files
4. Project status: [internal/](internal/) - status and summary files

## Documentation Standards

### For All Documentation
- Use clear, concise language
- Include practical examples
- Cross-reference related documentation
- Keep code examples up-to-date
- Use consistent formatting

### For User Documentation
- Focus on "how to" accomplish tasks
- Include troubleshooting tips
- Show example commands and output
- Explain concepts in plain language
- Avoid internal implementation details

### For Technical Documentation
- Include architectural diagrams where helpful
- Explain design decisions and tradeoffs
- Document edge cases and error handling
- Reference related components
- Keep security considerations in mind

### For Internal Documentation
- Include context and background
- Document decisions and rationale
- Link requirements to implementations
- Track issues to resolution
- Preserve historical context

## Contributing to Documentation

### Found an Issue?
1. Check if the issue still exists
2. Create a GitHub issue with details
3. Suggest a fix if possible

### Want to Improve Docs?
1. Make your changes
2. Update cross-references
3. Update relevant README files
4. Test any code examples
5. Submit a pull request

### Adding New Documentation?
1. Choose the right directory:
   - `user-guide/` - End-user documentation
   - `architecture/` - Design and architecture
   - `development/` - Developer guides
   - `internal/` - Requirements and reviews
2. Follow the existing structure and style
3. Update the appropriate README.md
4. Add cross-references
5. Include in relevant navigation sections

## Quick Reference

### Essential User Docs
- [Getting Started](user-guide/getting-started.md)
- [Configuration](user-guide/configuration.md)
- [CLI Reference](user-guide/cli-reference.md)
- [Examples](user-guide/examples.md)
- [Troubleshooting](user-guide/troubleshooting.md)

### Essential Technical Docs
- [Architecture Overview](architecture/overview.md)
- [Feature Workflow](development/feature-workflow.md)
- [Testing Standards](development/testing-standards.md)
- [Textual Best Practices](development/textual-best-practices.md)

### Special Topics
- [Ollama Setup](ollama-setup.md)
- [TUI Overview](tui.md)
- [GitHub Copilot](user-guide/github-models-provider.md)

## Getting Help

- **Users:** Start with [user-guide/troubleshooting.md](user-guide/troubleshooting.md)
- **Developers:** Check [development/README.md](development/README.md)
- **Architecture questions:** See [architecture/README.md](architecture/README.md)
- **Project history:** Browse [internal/README.md](internal/README.md)

---

**Ready to start?** Choose your path above based on your role!
