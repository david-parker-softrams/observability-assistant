# OpenThinker:32b Quick Reference

## Quick Start

```bash
# 1. Pull and run the model
ollama run openthinker:32b

# 2. Set LogAI config
export LOGAI_LLM_PROVIDER=ollama
export LOGAI_OLLAMA_MODEL=openthinker:32b

# 3. Run LogAI
logai
```

## What Was Changed

| File | Change | Line(s) |
|------|--------|---------|
| `litellm_provider.py` | Added to model registration | 51 |
| `litellm_provider.py` | Added to supported families | 155 |
| `default_models.yaml` | Added model configuration | 95-101 |
| `model_config.py` | Added to hardcoded defaults | 102 |

## Key Features

- ❌ **Tool Calling:** NOT supported (use Qwen3, Llama 3.1, or Command-R for tool tasks)
- ✅ **Context Window:** 131,072 tokens (128K)
- ✅ **Reasoning:** Extended chain-of-thought reasoning (like o1/DeepSeek-R1)
- ✅ **Streaming:** Supported

**Model Type:** Reasoning model optimized for pure reasoning, NOT tool calling

## Configuration

```yaml
# ~/.logai/config.yaml
llm_provider: ollama
ollama_model: openthinker:32b
ollama_base_url: http://localhost:11434
```

## Testing

```bash
# Run all tests
pytest tests/unit/test_model_config.py -v
pytest tests/unit/test_llm_provider.py -v

# All tests pass ✅
```

## Model Info

- **Context:** 128K tokens
- **Encoding:** cl100k_base
- **Type:** Reasoning model (similar to OpenAI's o1)
- **Provider:** Ollama
- **Tool Support:** ❌ NOT supported (use Qwen3, Llama 3.1, or Command-R for tool tasks)
- **Best For:** Pure reasoning, mathematics, logic problems

## Example Usage in Code

```python
from logai.providers.llm.litellm_provider import LiteLLMProvider

# Create provider
provider = LiteLLMProvider(
    provider="ollama",
    api_key="",
    model="openthinker:32b",
    api_base="http://localhost:11434"
)

# Use for reasoning tasks (NOT tool calling)
response = await provider.chat(
    messages=[{"role": "user", "content": "Solve this logic problem..."}]
)

# Note: This is a reasoning model - does NOT support native tool calling
# For tool-based tasks, use Qwen3, Llama 3.1, or Command-R
```

## Verification

```python
from logai.config.model_config import ModelConfigLoader

loader = ModelConfigLoader.get_instance()

# Get context window
window = loader.get_context_window("openthinker:32b")
assert window == 131_072

# Get encoding
encoding = loader.get_encoding("openthinker:32b")
assert encoding == "cl100k_base"
```

## Ready for Code Review ✅
