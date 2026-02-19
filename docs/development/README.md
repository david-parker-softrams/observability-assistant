# Development Documentation

This directory contains documentation for developers working on LogAI, including workflows, guidelines, best practices, and testing documentation.

## Development Workflows

### Feature Development
- **[feature-workflow.md](feature-workflow.md)** - Complete feature development workflow
  - Requirements gathering
  - Design and architecture
  - Implementation phases
  - Code review process
  - QA and testing
  - Documentation requirements

### Agent Guidelines
- **[agent-self-direction.md](agent-self-direction.md)** - AI agent self-direction design and guidelines
- **[file-writing-guidelines.md](file-writing-guidelines.md)** - Guidelines for agents writing files

## Best Practices

### Framework-Specific
- **[textual-best-practices.md](textual-best-practices.md)** - Textual framework best practices
  - CSS layout lessons learned
  - Common pitfalls and solutions
  - Widget composition patterns
  - Performance considerations

## Testing Documentation

### Testing Standards
- **[testing-standards.md](testing-standards.md)** - Testing standards and implementation guidelines
  - Unit testing requirements
  - Integration testing approach
  - Mocking strategies
  - Coverage expectations

### Test Plans
- **[manual-testing-plan.md](manual-testing-plan.md)** - Manual testing procedures
- **[tool-sidebar-testing.md](tool-sidebar-testing.md)** - Tool sidebar manual test guide
- **[e2e-test-context-management.md](e2e-test-context-management.md)** - E2E test script for context management

## Tools and Reference

### Tools Documentation
- **[tools-reference.md](tools-reference.md)** - Complete tools reference for agents
- **[tools-index.md](tools-index.md)** - Tools documentation index
- **[tools-summary.md](tools-summary.md)** - Summary of available tools

## Deployment

### Local Development
- **[local-deployment.md](local-deployment.md)** - Local deployment and setup guide
  - Development environment setup
  - Running locally
  - Common issues and solutions

## Quick Start for Developers

### Setting Up Your Development Environment

1. **Clone and install:**
   ```bash
   git clone <repository>
   cd observability-assistant
   pip install -e ".[dev]"
   ```

2. **Review development workflow:**
   - Read [feature-workflow.md](feature-workflow.md) for the complete process
   - Check [file-writing-guidelines.md](file-writing-guidelines.md) for code standards

3. **Understand the tech stack:**
   - Review [../architecture/overview.md](../architecture/overview.md) for architecture
   - Read [textual-best-practices.md](textual-best-practices.md) for TUI development

4. **Set up testing:**
   - Follow [testing-standards.md](testing-standards.md)
   - Use [manual-testing-plan.md](manual-testing-plan.md) for manual tests

## Development Workflow Overview

### 1. Feature Planning
Start with [feature-workflow.md](feature-workflow.md) which covers:
- Creating requirements documents
- Writing design specifications
- Getting architecture review
- Planning implementation phases

### 2. Implementation
Follow these guidelines:
- **Code Standards:** [file-writing-guidelines.md](file-writing-guidelines.md)
- **TUI Development:** [textual-best-practices.md](textual-best-practices.md)
- **Agent Behavior:** [agent-self-direction.md](agent-self-direction.md)

### 3. Testing
Ensure quality with:
- **Standards:** [testing-standards.md](testing-standards.md)
- **Manual Tests:** [manual-testing-plan.md](manual-testing-plan.md)
- **E2E Tests:** [e2e-test-context-management.md](e2e-test-context-management.md)

### 4. Deployment
Use local deployment guide:
- **Setup:** [local-deployment.md](local-deployment.md)

## Documentation by Role

### For New Developers
Start here:
1. [feature-workflow.md](feature-workflow.md) - Understand the development process
2. [../architecture/overview.md](../architecture/overview.md) - Learn the system architecture
3. [textual-best-practices.md](textual-best-practices.md) - TUI framework patterns
4. [local-deployment.md](local-deployment.md) - Set up your environment

### For AI Agents
Essential reading:
1. [agent-self-direction.md](agent-self-direction.md) - Self-direction patterns
2. [file-writing-guidelines.md](file-writing-guidelines.md) - Code writing standards
3. [tools-reference.md](tools-reference.md) - Available tools
4. [feature-workflow.md](feature-workflow.md) - Complete workflow

### For QA Engineers
Testing focus:
1. [testing-standards.md](testing-standards.md) - What to test and how
2. [manual-testing-plan.md](manual-testing-plan.md) - Manual test procedures
3. [tool-sidebar-testing.md](tool-sidebar-testing.md) - Component-specific tests
4. [e2e-test-context-management.md](e2e-test-context-management.md) - E2E scenarios

## Best Practices Highlights

### Textual Framework (TUI)
From [textual-best-practices.md](textual-best-practices.md):
- ⚠️ Avoid multiple `dock: top` elements in the same container
- ✅ Use natural vertical layout with `height: auto`
- ✅ Prefer containers with vertical layout over docking
- ✅ Test layout changes with debug mode enabled

### Testing
From [testing-standards.md](testing-standards.md):
- Write unit tests for all new functionality
- Mock external dependencies (AWS, LLM providers)
- Maintain 80%+ code coverage
- Include integration tests for critical paths

### Code Quality
From [file-writing-guidelines.md](file-writing-guidelines.md):
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write clear docstrings
- Keep functions focused and small

## Related Documentation

- **Architecture:** [../architecture/](../architecture/) - System design and component architecture
- **User Guide:** [../user-guide/](../user-guide/) - End-user documentation
- **Internal:** [../internal/](../internal/) - Requirements, reviews, and investigations

## Contributing to Development Docs

### Adding New Documentation

1. **Choose the right category:**
   - Workflows for process documentation
   - Best practices for lessons learned
   - Testing for QA procedures
   - Tools for agent/developer references

2. **Follow the template:**
   - Clear introduction
   - Practical examples
   - Common pitfalls to avoid
   - References to related docs

3. **Update this README** with your new document

4. **Cross-reference** related documentation

### Improving Existing Docs

Found something unclear or outdated?
1. Update the relevant document
2. Ensure examples still work
3. Update cross-references if needed
4. Submit your changes

---

**Start developing:** Read [feature-workflow.md](feature-workflow.md) to understand the complete development process.
