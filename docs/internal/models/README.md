# Model Integration Documentation

This directory contains production model integration documentation for LogAI, including implementation guides, configuration details, and usage instructions for various LLM models.

## Available Model Documentation

### Reasoning Models
- **[deepseek-r1-integration.md](deepseek-r1-integration.md)** - DeepSeek-R1:32b reasoning model integration
  - Chain-of-thought reasoning capabilities
  - 128K context window (131,072 tokens)
  - All variants supported (1.5b-671b)
  - Ollama integration details

- **[openthinker-integration.md](openthinker-integration.md)** - OpenThinker reasoning model implementation
  - Reasoning model configuration
  - Integration patterns
  - Usage guidelines

## Document Purpose

These documents provide comprehensive implementation details for integrating new LLM models into LogAI:
- Model registration and configuration
- Context window specifications
- Tool calling capabilities
- Provider-specific settings
- Testing and verification procedures
- Production readiness assessments

## Using These Documents

### For Users
Consult these documents when:
- Adding a new model to your LogAI configuration
- Understanding model capabilities and limitations
- Troubleshooting model-specific issues
- Configuring Ollama or other providers

### For Developers
Reference these documents when:
- Implementing support for new models
- Understanding the model integration architecture
- Reviewing model configuration patterns
- Adding new model families

## Related Documentation

- **User Configuration:** [../../user-guide/configuration.md](../../user-guide/configuration.md) - User-facing model configuration guide
- **Model Architecture:** [../../architecture/model-configuration-architecture.md](../../architecture/model-configuration-architecture.md) - 3-tier YAML configuration system
- **Ollama Setup:** [../../ollama-setup.md](../../ollama-setup.md) - Ollama installation and setup

---

**Note:** These are production-approved integrations that have been reviewed, tested, and deployed.
