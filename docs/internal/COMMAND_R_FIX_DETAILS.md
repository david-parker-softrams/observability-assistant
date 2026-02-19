# Command-R Tool Calling Fix - Implementation Guide

## Summary
- **Status**: 🟢 READY TO IMPLEMENT
- **Complexity**: TRIVIAL (1-2 line change)
- **Files Modified**: 1 file
- **Time to Fix**: < 5 minutes
- **Risk Level**: MINIMAL

---

## The Exact Problem

**File:** `src/logai/providers/llm/litellm_provider.py`
**Method:** `_supports_tools()` (lines 135-151)
**Issue:** Command-R not in supported models list

### Current Code (BROKEN)
```python
def _supports_tools(self) -> bool:
    """Check if the current model supports tool calling."""
    if self.provider in ["anthropic", "openai"]:
        return True
    if self.provider == "ollama":
        # Check if model family is registered as supporting tools
        model_name = self._get_model_name()
        supported_families = [
            "qwen2.5",
            "qwen3",
            "llama3.1",
            "llama3.2",
            "mistral-nemo",
            "firefunction",
            # ← command-r IS MISSING HERE!
        ]
        return any(f"ollama_chat/{family}" in model_name for family in supported_families)
    return False
```

---

## The Fix

### Recommended: Option A (Minimal)
Add `"command-r"` to the `supported_families` list:

```python
def _supports_tools(self) -> bool:
    """Check if the current model supports tool calling."""
    if self.provider in ["anthropic", "openai"]:
        return True
    if self.provider == "ollama":
        # Check if model family is registered as supporting tools
        model_name = self._get_model_name()
        supported_families = [
            "qwen2.5",
            "qwen3",
            "llama3.1",
            "llama3.2",
            "mistral-nemo",
            "firefunction",
            "command-r",          # ← ADD THIS LINE
        ]
        return any(f"ollama_chat/{family}" in model_name for family in supported_families)
    return False
```

**Change Summary:**
- **Line to add:** `"command-r",` after `"firefunction",`
- **Total lines changed:** 1
- **Breaking changes:** None

### Alternative: Option B (Enhanced - Future-Proof)
If we want to be more thorough, we can add multiple missing models:

```python
def _supports_tools(self) -> bool:
    """Check if the current model supports tool calling."""
    if self.provider in ["anthropic", "openai"]:
        return True
    if self.provider == "ollama":
        # Check if model family is registered as supporting tools
        model_name = self._get_model_name()
        supported_families = [
            "qwen2.5",
            "qwen3",
            "llama3.1",
            "llama3.2",
            "llama3.3",            # ← NEW
            "mistral",             # ← GENERALIZED (from mistral-nemo)
            "mixtral",             # ← NEW
            "firefunction",
            "command-r",           # ← NEW (primary fix)
            "command-r-plus",      # ← NEW (variant)
            "deepseek",            # ← NEW
            "internlm2_5",         # ← NEW
        ]
        return any(f"ollama_chat/{family}" in model_name for family in supported_families)
    return False
```

**Change Summary:**
- **Lines to add:** 7 new model families
- **Lines to modify:** 1 (generalize mistral-nemo to mistral)
- **Total changes:** ~8 lines
- **Breaking changes:** None

---

## Step-by-Step Implementation

### Step 1: Verify the File
```bash
cat src/logai/providers/llm/litellm_provider.py | grep -A 20 "_supports_tools"
```

### Step 2: Apply Minimal Fix (Recommended)
Edit `src/logai/providers/llm/litellm_provider.py` and add `"command-r",` to line 149:

**Find this:**
```python
        supported_families = [
            "qwen2.5",
            "qwen3",
            "llama3.1",
            "llama3.2",
            "mistral-nemo",
            "firefunction",
        ]
```

**Replace with:**
```python
        supported_families = [
            "qwen2.5",
            "qwen3",
            "llama3.1",
            "llama3.2",
            "mistral-nemo",
            "firefunction",
            "command-r",
        ]
```

### Step 3: (Optional) Update Registration Comment
If using Option B, update the comment at lines 35-40 to include command-r.

**Current:**
```python
# Register Ollama models that support function calling
# Based on LiteLLM documentation: https://docs.litellm.ai/docs/providers/ollama
#
# Supported model families (as of Feb 2026):
# - Qwen 2.5/3 series: Native tool calling support
# - Llama 3.1+: Native tool calling support
```

**Updated:**
```python
# Register Ollama models that support function calling
# Based on LiteLLM documentation: https://docs.litellm.ai/docs/providers/ollama
#
# Supported model families (as of Feb 2026):
# - Qwen 2.5/3 series: Native tool calling support
# - Llama 3.1+ series: Native tool calling support
# - Command-R: Native tool calling support
# - Deepseek series: Native tool calling support (deepseek-coder-v2, etc)
```

### Step 4: Test
```bash
# Test the fix
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/Users/David.Parker/src/observability-assistant/src')

from logai.providers.llm.litellm_provider import LiteLLMProvider

# Create a provider instance for command-r
provider = LiteLLMProvider(
    provider="ollama",
    api_key="",
    model="command-r",
    api_base="http://localhost:11434"
)

# Test the method
result = provider._supports_tools()
print(f"Command-R supports tools: {result}")
assert result == True, "FIX DID NOT WORK!"
print("✅ FIX VERIFIED!")
PYEOF
```

---

## Verification Checklist

- [ ] File `src/logai/providers/llm/litellm_provider.py` has been edited
- [ ] `"command-r"` has been added to `supported_families` list
- [ ] Code compiles (run `python -m py_compile src/logai/providers/llm/litellm_provider.py`)
- [ ] Test passes (runs the test code above)
- [ ] No other files modified
- [ ] No syntax errors introduced

---

## Expected Result After Fix

### Before Fix
```
User: "Show me logs"
Model receives: tools = None
Model response: plain text with JSON in markdown code block
Tool calls captured: NONE (empty list)
```

### After Fix
```
User: "Show me logs"
Model receives: tools = [list of available tools]
Model response: proper structured tool calls
Tool calls captured: YES (populated with function names and arguments)
```

---

## Rollback Instructions
If needed to revert:
1. Remove `"command-r",` from line 149
2. The file reverts to its original state

---

## Additional Notes

- **Why this works:** LiteLLM's registry already knows Command-R supports tools
- **Why it was missing:** The model list was incomplete
- **Why it's safe:** We're only adding to a list, not changing logic
- **Why now:** User discovered the issue when trying to use command-r

---

## Questions & Answers

**Q: Will this affect other models?**
A: No, it's purely additive. Other models are unaffected.

**Q: Do we need to restart the application?**
A: Yes, the code change requires restarting LogAI.

**Q: Will this work with both command-r and command-r-plus?**
A: The pattern matching checks `"ollama_chat/command-r"` in model_name, so:
  - ✅ `command-r` matches (contains `command-r`)
  - ✅ `command-r-plus` also matches (contains `command-r`)

**Q: What about future Command-R versions?**
A: The pattern matching is prefix-based, so `command-r-v2`, etc. will all match.
