# LogAI Examples

This directory contains example scripts demonstrating various LogAI features and capabilities.

## Available Examples

### demo_phase5.py - LLM Integration with Tools
Demonstrates the complete flow of:
- User query processing
- LLM deciding to call tools
- Tool execution (with mocked CloudWatch)
- LLM analyzing results
- Returning answers to users

**Run with:**
```bash
python examples/demo_phase5.py
```

### demo_phase6.py - Caching System
Showcases the SQLite-based caching system that:
- Reduces CloudWatch API calls
- Improves query performance
- Handles cache expiration
- Manages cache size limits

**Run with:**
```bash
python examples/demo_phase6.py
```

## Development Runner

The `logai_dev.py` script in the root directory allows running LogAI without full installation:

```bash
./logai_dev.py
```

This is useful during development for testing changes without reinstalling the package.

## Prerequisites

All examples require:
- Python 3.11+
- LogAI dependencies installed (`pip install -e .`)
- AWS credentials configured (for real CloudWatch access)
- LLM provider API key (Anthropic/OpenAI/GitHub Copilot)

## Contributing

When adding new examples:
1. Use descriptive filenames (e.g., `demo_feature_name.py`)
2. Include docstrings explaining what the example demonstrates
3. Add usage instructions to this README
4. Keep examples focused on a single feature or workflow
