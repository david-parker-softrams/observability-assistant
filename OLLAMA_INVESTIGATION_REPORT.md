# Ollama Integration Investigation Report
**Date:** February 20, 2026
**Investigator:** Hans (Code Librarian)
**Status:** ✅ Investigation Complete

---

## Executive Summary

The codebase has a **fully functional Ollama integration** with native tool calling support. The system is ready to support MiroThinker-v1.5-30B-GGUF:Q5_K_M or any other Ollama model that supports function calling.

**Key Finding:** Tool calling support has been enabled for Ollama models (as of Feb 10, 2026), resolving the earlier limitations.

---

## 1. OLLAMA PROVIDER IMPLEMENTATION LOCATION

### Primary Implementation File
**File:** `src/logai/providers/llm/litellm_provider.py` (402 lines)

**Architecture:**
- Uses **LiteLLM** library as the abstraction layer for multiple LLM providers
- Ollama provider is integrated alongside Anthropic, OpenAI, and GitHub Copilot
- All providers implement the `BaseLLMProvider` abstract interface

### Base Provider Interface
**File:** `src/logai/providers/llm/base.py`
- Defines abstract methods: `chat()` and `stream_chat()`
- Defines `LLMResponse` class for structured responses
- Custom error types: `LLMProviderError`, `RateLimitError`, `AuthenticationError`, `InvalidRequestError`

### Provider Configuration
**Files:**
- `src/logai/config/settings.py` (lines 49-57) - Settings definition
- `src/logai/config/validation.py` - URL validation
- `.env.example` (lines 35-41) - Environment variable template

---

## 2. TOOL CALLING SUPPORT STATUS

### ✅ Current Support: ENABLED

**Tool Calling Implementation:**
```python
# Location: litellm_provider.py, lines 148-167

def _supports_tools(self) -> bool:
    """Check if the current model supports tool calling."""
    if self.provider in ["anthropic", "openai"]:
        return True
    if self.provider == "ollama":
        # Check if model family is registered as supporting tools
        model_name = self._get_model_name()
        supported_families = [
            "qwen2.5", "qwen3", "llama3.1", "llama3.2",
            "mistral-nemo", "firefunction", "command-r",
        ]
        return any(f"ollama_chat/{family}" in model_name
                   for family in supported_families)
    return False
```

### Registered Models with Function Calling Support
**Location:** `litellm_provider.py`, lines 51-61

```python
litellm.register_model(
    model_cost={
        "ollama_chat/qwen2.5": {"supports_function_calling": True},
        "ollama_chat/qwen3": {"supports_function_calling": True},
        "ollama_chat/llama3.1": {"supports_function_calling": True},
        "ollama_chat/llama3.2": {"supports_function_calling": True},
        "ollama_chat/command-r": {"supports_function_calling": True},
        "ollama_chat/openthinker": {"supports_function_calling": False},
        "ollama_chat/deepseek-r1": {"supports_function_calling": False},
    }
)
```

### Tool Sending Logic
**Location:** `litellm_provider.py`

**In `chat()` method (lines 213-215):**
```python
# Only send tools if the model supports them
if tools and self._supports_tools():
    params["tools"] = tools
```

**In `stream_chat()` method (lines 305-307):**
```python
# Only send tools if the model supports them
if tools and self._supports_tools():
    params["tools"] = tools
```

---

## 3. CONFIGURATION REQUIREMENTS

### For Standard Ollama Models (Recommended)

**Step 1: .env Configuration**
```bash
LOGAI_LLM_PROVIDER=ollama
LOGAI_OLLAMA_MODEL=qwen3:32b
LOGAI_OLLAMA_BASE_URL=http://localhost:11434
AWS_PROFILE=your-profile-name
AWS_DEFAULT_REGION=us-east-1
```

**Step 2: Pull the Model**
```bash
ollama pull qwen3:32b
```

**Step 3: Start Ollama Server**
```bash
ollama serve
```

---

## 4. MIROTHINKER CONFIGURATION (NOT RECOMMENDED)

### ⚠️ IMPORTANT LIMITATION

**MiroThinker-v1.5-30B-GGUF is a REASONING MODEL and likely does NOT support function calling.**

**Current Support Status:** ❌ **Likely Not Supported**

**Supported Model Families:**
- ✅ Qwen 2.5 & 3
- ✅ Llama 3.1 & 3.2
- ✅ Command-R
- ✅ Mistral Nemo
- ✅ Firefunction v2
- ❌ OpenThinker
- ❌ DeepSeek-R1
- ❌ MiroThinker

### If You Still Want to Try
```bash
# .env
LOGAI_OLLAMA_MODEL=mirothinker-v1.5-30b-gguf:q5_k_m
```

**Expected Result:** Tool calling will be DISABLED.

---

## 5. HARDWARE REQUIREMENTS

| Model | RAM Required | VRAM (GPU) | Disk Space |
|-------|--------------|-----------|-----------|
| llama3.1:8b | 8GB | 6GB | ~4.7GB |
| qwen3:32b | 32GB | 24GB | ~20GB |
| mirothinker-v1.5-30b | 30GB | 20GB | ~18GB |

---

## 6. FILE LOCATIONS

### Core Implementation
- `src/logai/providers/llm/litellm_provider.py` - Main provider (402 lines)
- `src/logai/providers/llm/base.py` - Base interface (138 lines)
- `src/logai/config/settings.py` - Configuration
- `.env.example` - Example config

### Tests
- `tests/unit/test_llm_provider.py` - Unit tests

### Documentation
- `docs/ollama-setup.md` - User guide
- `docs/architecture/ollama-tool-calling-architecture.md` - Technical details

---

## 7. SUMMARY

| Aspect | Status | Details |
|--------|--------|---------|
| **Ollama Provider** | ✅ Implemented | Full LiteLLM support |
| **Tool Calling** | ✅ Enabled | Compatible models only |
| **Configuration** | ✅ Simple | 3-4 env vars |
| **MiroThinker** | ❌ No tools | Reasoning model |
| **AWS Integration** | ✅ Required | For CloudWatch |

---

**Investigation Complete** ✅
