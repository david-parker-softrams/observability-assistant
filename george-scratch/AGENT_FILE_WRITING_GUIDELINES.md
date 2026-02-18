# Agent File Writing Guidelines

## CRITICAL: Path Usage Rules

### ✅ ALWAYS Use These Paths:

1. **Workspace Directory** (PREFERRED for all deliverables):
   - `/Users/David.Parker/src/observability-assistant/`
   - This is the project root - use for all investigation documents, reports, and deliverables

2. **George's Scratch Directory** (for working documents):
   - `/Users/David.Parker/src/observability-assistant/george-scratch/`
   - Use for requirements docs, design docs, temporary notes, etc.

3. **Temporary Files** (if absolutely necessary):
   - Use `/tmp/` (the symlink)
   - **NEVER** use `/private/tmp/`
   - Reason: `/tmp` is a symlink to `/private/tmp` on macOS, but tools recognize `/tmp` as valid

### ❌ NEVER Use These Paths:

1. **`/private/tmp/`** - This triggers security prompts in OpenCode
2. **`/var/folders/...`** - System temp directories
3. **Any path starting with `/private/`** - Outside workspace

## Why This Matters

On macOS:
- `/tmp` is a symbolic link to `private/tmp`
- When paths are resolved canonically, `/tmp` becomes `/private/tmp`
- OpenCode sees `/private/tmp` as outside the workspace and prompts for approval
- This interrupts workflow and requires manual intervention

## Best Practice

**For investigation reports and deliverables:**
```
CORRECT: /Users/David.Parker/src/observability-assistant/CACHING_INVESTIGATION.md
WRONG:   /private/tmp/CACHING_INVESTIGATION.md
```

**For truly temporary files (logs, debug output):**
```
CORRECT: /tmp/debug_output.log
WRONG:   /private/tmp/debug_output.log
```

## Python Code Considerations

If writing Python code that uses temp directories:

```python
# ❌ WRONG - resolves to /private/tmp
import os
temp_file = os.path.realpath("/tmp/file.txt")  # Returns /private/tmp/file.txt

# ✅ CORRECT - keeps the symlink
temp_file = "/tmp/file.txt"  # Stays as /tmp/file.txt

# ✅ CORRECT - for workspace files
workspace = "/Users/David.Parker/src/observability-assistant"
output_file = f"{workspace}/report.md"
```

## Summary

- **Default location**: Use workspace or george-scratch directory
- **Temp files only when necessary**: Use `/tmp/` not `/private/tmp/`
- **Never resolve canonical paths for /tmp** - keep the symlink form
