# Architecture Documentation

This directory contains architectural design documents and technical specifications for the LogAI observability assistant.

## Overview Documents

### Core Architecture
- **[overview.md](overview.md)** - Complete system architecture design document
  - Technology stack decisions
  - System architecture
  - LLM integration design
  - Caching strategy
  - AWS CloudWatch integration
  - Security considerations

### Component Architecture
- **[context-management-system.md](context-management-system.md)** - Context management system architecture
- **[context-window-management-improvements.md](context-window-management-improvements.md)** - Context window management implementation (435 lines!)
  - 3x improvement in conversation length
  - Mid-loop token budget tracking
  - Emergency pruning strategy
  - Search result deduplication (50% token reduction)
- **[github-copilot-integration.md](github-copilot-integration.md)** - GitHub Copilot OAuth and API integration
- **[log-groups-sidebar.md](log-groups-sidebar.md)** - Log groups sidebar component architecture
- **[model-configuration-architecture.md](model-configuration-architecture.md)** - 3-tier YAML model configuration system
  - Hardcoded fallbacks → Built-in YAML → User YAML
  - Custom/local model support without code changes
  - ModelConfigLoader and ModelConfig components
- **[ollama-tool-calling-architecture.md](ollama-tool-calling-architecture.md)** - Ollama model tool calling support architecture
  - Why Ollama models support tool calling
  - LiteLLM integration patterns
  - Function calling implementation
- **[preload-log-groups.md](preload-log-groups.md)** - Background log group loading system

## Design Documents

### Feature Designs
- **[design-cache-llm.md](design-cache-llm.md)** - LLM-based cache query design
- **[design-config-cleanup.md](design-config-cleanup.md)** - Configuration cleanup and externalization
- **[design-context-window-fixes.md](design-context-window-fixes.md)** - Context window management improvements
- **[design-log-preview.md](design-log-preview.md)** - Log preview feature design
- **[design-model-config.md](design-model-config.md)** - Model configuration externalization
- **[design-sidebar-resize.md](design-sidebar-resize.md)** - Sidebar resize functionality
- **[design-timeframe-selector.md](design-timeframe-selector.md)** - Timeframe selector design
- **[design-tool-sidebar.md](design-tool-sidebar.md)** - Tool execution sidebar design

### Reviews
- **[config-cleanup-review.md](config-cleanup-review.md)** - Architecture review of config cleanup

## Document Types

### Architecture Documents
Architecture documents describe the high-level system design, component interactions, and technical decisions. They include:
- System components and their relationships
- Technology choices and rationale
- Integration patterns
- Data flow diagrams
- Security considerations

### Design Documents
Design documents provide detailed specifications for individual features or components:
- Feature requirements
- UI/UX mockups
- Implementation approach
- Edge cases and error handling
- Testing strategy

## Navigation by Topic

### TUI/Interface
- Log groups sidebar: [log-groups-sidebar.md](log-groups-sidebar.md)
- Sidebar resize: [design-sidebar-resize.md](design-sidebar-resize.md)
- Tool sidebar: [design-tool-sidebar.md](design-tool-sidebar.md)
- Log preview: [design-log-preview.md](design-log-preview.md)
- Timeframe selector: [design-timeframe-selector.md](design-timeframe-selector.md)

### LLM Integration
- Main architecture: [overview.md](overview.md#6-llm-integration-design)
- GitHub Copilot: [github-copilot-integration.md](github-copilot-integration.md)
- Context management: [context-management-system.md](context-management-system.md)
- Context window fixes: [design-context-window-fixes.md](design-context-window-fixes.md)

### Configuration
- Model config: [design-model-config.md](design-model-config.md)
- Config cleanup: [design-config-cleanup.md](design-config-cleanup.md)
- Config review: [config-cleanup-review.md](config-cleanup-review.md)

### Caching
- Main architecture: [overview.md](overview.md#7-caching-strategy)
- LLM cache design: [design-cache-llm.md](design-cache-llm.md)

### Performance
- Preload system: [preload-log-groups.md](preload-log-groups.md)
- Context window management: [design-context-window-fixes.md](design-context-window-fixes.md)

## Related Documentation

- **User Documentation:** [../user-guide/](../user-guide/) - End-user guides and references
- **Development Documentation:** [../development/](../development/) - Development workflows and best practices
- **Internal Documentation:** [../internal/](../internal/) - Requirements, reviews, and investigations

## Contributing

When creating new architecture or design documents:

1. **Choose the right document type:**
   - Architecture docs for system-level designs
   - Design docs for feature-level specifications

2. **Follow the template structure:**
   - Executive summary
   - Requirements/Goals
   - Design details
   - Implementation considerations
   - Testing approach
   - Security considerations (if applicable)

3. **Update this README** to include your new document

4. **Cross-reference related docs** to maintain documentation linkage

---

**Start exploring:** Begin with [overview.md](overview.md) for the complete system architecture.
