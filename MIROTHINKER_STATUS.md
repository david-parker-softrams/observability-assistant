# MiroThinker-v1.5-30B-GGUF Configuration Status

## 🚫 VERDICT: NOT RECOMMENDED FOR THIS APPLICATION

---

## Quick Status

| Item | Status | Details |
|------|--------|---------|
| **Tool Calling Support** | ❌ NO | Reasoning models don't support function calling |
| **CloudWatch Integration** | ❌ WILL FAIL | Tools won't be sent to model |
| **Configuration Difficulty** | ✅ EASY | If you ignore warnings, easy to configure |
| **Hardware Requirements** | ⚠️ HIGH | 30GB RAM, 20GB VRAM, 18GB disk |
| **Recommendation** | ❌ AVOID | Use Qwen 3 or Llama 3.1 instead |

---

## If You Want to Try Anyway

### .env Configuration
```bash
LOGAI_LLM_PROVIDER=ollama
LOGAI_OLLAMA_MODEL=mirothinker-v1.5-30b-gguf:q5_k_m
LOGAI_OLLAMA_BASE_URL=http://localhost:11434
AWS_PROFILE=your-profile-name
AWS_DEFAULT_REGION=us-east-1
```

### Installation
```bash
# Pull the model
ollama pull mirothinker-v1.5-30b-gguf:q5_k_m

# Start server
ollama serve
```

### Expected Result
- ✅ Model loads
- ✅ LLM responds to questions
- ❌ **CloudWatch tools FAIL**
- ❌ **Error: "Maximum tool iterations exceeded"**
- ❌ **Unusable for this application**

---

## Why MiroThinker Doesn't Work

MiroThinker is a **reasoning model** (like DeepSeek-R1, OpenThinker). These models are designed for:
- ✅ Complex reasoning
- ✅ Step-by-step thinking
- ❌ Function/tool calling

The codebase explicitly excludes reasoning models from tool support:
```python
# In litellm_provider.py, lines 58-59
"ollama_chat/openthinker": {"supports_function_calling": False},
"ollama_chat/deepseek-r1": {"supports_function_calling": False},
```

MiroThinker would be marked the same way if registered.

---

## ✅ RECOMMENDED MODELS (All Support Tool Calling)

### Best: Qwen 3 32B
```bash
LOGAI_OLLAMA_MODEL=qwen3:32b
ollama pull qwen3:32b
```
- Excellent reasoning
- Full tool support
- 20GB disk, 32GB RAM

### Alternative: Llama 3.1 70B
```bash
LOGAI_OLLAMA_MODEL=llama3.1:70b
ollama pull llama3.1:70b
```
- Strong reasoning
- Native tool support
- 40GB disk, 48GB RAM

### Lightweight: Llama 3.1 8B
```bash
LOGAI_OLLAMA_MODEL=llama3.1:8b
ollama pull llama3.1:8b
```
- Quick inference
- Tool support
- 4.7GB disk, 8GB RAM

---

## Technical Details

**Why This Matters:**

The system needs tools to function:
1. User asks a question
2. System converts it to tool calls
3. Tools fetch CloudWatch logs
4. LLM analyzes the logs
5. User gets the answer

Without tool support → No step 3 → System fails

**How It's Checked:**

```python
def _supports_tools(self) -> bool:
    if self.provider == "ollama":
        model_name = self._get_model_name()  # e.g., "ollama_chat/qwen3:32b"
        supported_families = [
            "qwen2.5", "qwen3", "llama3.1", "llama3.2",
            "mistral-nemo", "firefunction", "command-r",
        ]
        # Returns True only if model family is in the list
        return any(f"ollama_chat/{family}" in model_name
                   for family in supported_families)
    return False
```

MiroThinker would not match any family → `_supports_tools()` returns `False` → No tools sent.

---

## File Locations

- Implementation: `src/logai/providers/llm/litellm_provider.py`
- Settings: `src/logai/config/settings.py`
- Full Report: `OLLAMA_INVESTIGATION_REPORT.md`

---

## Summary

| Aspect | MiroThinker | Qwen 3 | Llama 3.1 |
|--------|------------|--------|-----------|
| Tool Calling | ❌ No | ✅ Yes | ✅ Yes |
| Reasoning | ✅ Excellent | ✅ Good | ✅ Good |
| CloudWatch | ❌ Broken | ✅ Works | ✅ Works |
| RAM | 30GB | 32GB | 48GB (70B) |
| Recommendation | ❌ Avoid | ✅ BEST | ✅ Good |

**Conclusion:** Don't use MiroThinker for this application.
