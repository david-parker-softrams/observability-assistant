# Command-R Tool Calling Fix - Quick Reference

## TL;DR
Problem: Command-R via Ollama not making tool calls
Root Cause: Missing from supported models list
Solution: Add "command-r" to the list (1 line)
Status: Ready to implement

---

## The One-Liner Fix

File: src/logai/providers/llm/litellm_provider.py
Line: 149
Action: Add "command-r" to this list after "firefunction":

    supported_families = [
        "qwen2.5",
        "qwen3",
        "llama3.1",
        "llama3.2",
        "mistral-nemo",
        "firefunction",
        "command-r",        # ADD THIS
    ]

---

## Why This Works

Does Command-R support function calling? YES (LiteLLM confirmed)
Does Ollama support Command-R? YES
Are tools sent to model currently? NO (missing from list)
Will adding the line fix it? YES
Will it break other models? NO
Is it safe to implement? YES

---

## Implementation Checklist

1. Open src/logai/providers/llm/litellm_provider.py
2. Find line 142 (look for supported_families = [)
3. Add "command-r", after "firefunction",
4. Save file
5. Run: python -m py_compile src/logai/providers/llm/litellm_provider.py
6. Verify: No syntax errors
7. Test with: ollama run command-r
8. Restart LogAI application
9. Confirm: Tool calls now work

---

## Testing

python3 -c "
import sys
sys.path.insert(0, 'src')
from logai.providers.llm.litellm_provider import LiteLLMProvider
provider = LiteLLMProvider('ollama', '', 'command-r', api_base='http://localhost:11434')
assert provider._supports_tools() == True
print('Fix verified!')
"

---

## Key Finding: Command-R Does Support Tools!

The issue is NOT with Command-R or LiteLLM.
The issue is OUR code doesn't recognize it.

LiteLLM Registry shows:
- supports_function_calling: True
- supports_tool_choice: True
- Model provider: cohere_chat (native) or ollama_chat (via Ollama)

Our code ignores this capability because "command-r" is missing from our supported list.

---

## Before & After

BEFORE (Broken):
- User asks for logs
- _supports_tools() returns False
- tools = None sent to model
- Model returns JSON in markdown text
- Tool calls not recognized

AFTER (Fixed):
- User asks for logs
- _supports_tools() returns True
- tools = list sent to model
- Model makes proper function calls
- Tool calls recognized

---

## Files Modified
- src/logai/providers/llm/litellm_provider.py (1 line added)

---

## Risk Assessment
Scope: Minimal (1 line, additive only)
Risk Level: MINIMAL
Rollback: Trivial (revert 1 line)

---

## Investigation Documents

1. INVESTIGATION_SUMMARY.md - Executive summary
2. COMMAND_R_TOOL_CALLING_INVESTIGATION.md - Full technical report
3. COMMAND_R_FIX_DETAILS.md - Implementation guide
4. QUICK_REFERENCE.md - This file

---

Implementation Time: < 5 minutes
