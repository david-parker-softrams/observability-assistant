# Root Cause Analysis: Why Agents Use `/private/tmp` Instead of `/tmp`

## Investigation Date
February 18, 2026

## Problem Statement
Agents (especially Hans, the librarian) repeatedly attempt to write files to `/private/tmp/` instead of `/tmp/`, triggering OpenCode security prompts that require manual intervention.

## Root Cause Identified

### The Technical Reality on macOS

```bash
$ ls -la / | grep tmp
lrwxr-xr-x@  1 root  wheel    11 Nov 22 03:17 tmp -> private/tmp

$ readlink /tmp
private/tmp
```

On macOS, `/tmp` is a **symbolic link** to `private/tmp`.

### Python's Path Resolution Behavior

```python
import os

print(os.path.abspath('/tmp'))     # Returns: /tmp
print(os.path.realpath('/tmp'))    # Returns: /private/tmp  ← THE CULPRIT
print(os.readlink('/tmp'))         # Returns: private/tmp
```

**Key Finding**: `os.path.realpath()` resolves symlinks to their canonical paths, converting `/tmp` → `/private/tmp`.

## Why Agents Choose `/private/tmp`

### Hypothesis 1: Technical Correctness (MOST LIKELY)
Agents, especially code-focused ones, may reason:
- "Symlinks can be fragile or change"
- "I should use the canonical/real path for reliability"
- "Best practice is to resolve symlinks using `realpath()`"
- **Result**: Agent uses `/private/tmp` thinking it's more "correct"

### Hypothesis 2: Training Data Examples
LLM training data likely includes:
- Python documentation showing `os.path.realpath()` usage
- macOS system documentation mentioning `/private/tmp`
- Stack Overflow answers recommending canonical paths
- **Result**: Agent learns that `/private/tmp` is the "proper" path on macOS

### Hypothesis 3: Environment Variables
Some macOS environment variables point to `/private/tmp`:
```bash
SSH_AUTH_SOCK=/private/tmp/com.apple.launchd.mRdMZ9hAYD/Listeners
DISPLAY=/private/tmp/com.apple.launchd.esm4ifq0Gk/org.xquartz:0
```
- **Result**: Agent sees system using `/private/tmp` and follows suit

### Hypothesis 4: No Explicit Counter-Instruction
Until now, agents had no specific instruction to:
- Avoid canonical path resolution
- Use `/tmp` instead of `/private/tmp`
- Understand the OpenCode workspace security model
- **Result**: Agent makes reasonable but problematic choice

## Why This Is Problematic

### OpenCode's Workspace Security Model
- OpenCode monitors file operations
- `/private/tmp` is outside the defined workspace
- Triggers security prompt: "Allow access to /private/tmp?"
- Requires manual user intervention each time

### The Irony
- Agents are trying to be **more correct** (using canonical paths)
- But this creates **more friction** (security prompts)
- The "less correct" path (`/tmp`) is actually **more practical**

## Evidence from Codebase

### No Source of `/private/tmp` in Project
Search results show `/private/tmp` is ONLY mentioned in:
- Reminders NOT to use it
- Session summaries noting the problem
- The guidelines document created today

**Conclusion**: Agents are NOT learning this from project documentation.

### Previous Occurrences
From session summaries:
```
SESSION_SUMMARY_2026-02-13_final.md:
  - **Note:** Required multiple reminders about /tmp vs /private/tmp usage

SESSION_SUMMARY_2026-02-13_clickable-shortcuts-and-cache-race-fix.md:
  - **Note:** Reminded multiple times to use `/tmp` instead of `/private/tmp` ✅

SESSION_SUMMARY_2026-02-13_status-indicator-it-bug-fix.md:
  - **Use file logging for TUI debugging** - Remember: `/tmp/` not `/private/tmp/`
```

This is a **recurring pattern**, confirming it's a systematic reasoning issue, not a one-time mistake.

## Solution Implemented

### 1. Created Agent File Writing Guidelines
Document: `AGENT_FILE_WRITING_GUIDELINES.md`
- Explicitly prohibits `/private/tmp/`
- Explains the OpenCode security model
- Provides clear rules for file paths

### 2. Updated TPM (George) System Prompt
Added explicit instruction to include in all delegations:
```
"IMPORTANT: Write all files to the workspace directory or george-scratch subdirectory.
If you absolutely must use a temporary directory, use `/tmp/` (NOT `/private/tmp/`).
Never resolve paths to their canonical form - use `/tmp/` exactly as written."
```

### 3. Technical Explanation for Agents
When delegating, explain WHY:
- macOS: `/tmp` is a symlink to `private/tmp`
- Python's `realpath()` converts `/tmp` → `/private/tmp`
- OpenCode sees `/private/tmp` as outside workspace
- Use `/tmp/` to avoid security prompts

## Prevention Strategy

### For TPM (George)
✅ Always include path guidelines in delegation prompts
✅ Emphasize using `/tmp/` not `/private/tmp/`
✅ Explain the reasoning (not just the rule)

### For Agents
✅ Prefer workspace directory for deliverables
✅ Use `/tmp/` only when necessary
✅ Never use `os.path.realpath()` on `/tmp`
✅ Use `os.path.abspath()` instead (preserves symlinks)

### Monitoring
- Watch for OpenCode security prompts
- Note any agent still using `/private/tmp`
- Update guidelines if new cases emerge

## Conclusion

**Root Cause**: Agents apply technically correct reasoning (`realpath()` to resolve symlinks) that conflicts with OpenCode's workspace security model.

**Solution**: Explicit instructions to use `/tmp/` and avoid path resolution, combined with explanation of WHY this matters.

**Success Metric**: Zero OpenCode security prompts for `/private/tmp` access after these guidelines are followed.

---

## Appendix: Technical Details

### Test Commands Used
```bash
# Show symlink
ls -la / | grep tmp
readlink /tmp

# Python path resolution
python3 -c "import os; print('realpath:', os.path.realpath('/tmp')); print('abspath:', os.path.abspath('/tmp'))"

# Search for mentions
grep -r "private/tmp" /Users/David.Parker/src/observability-assistant/ --include="*.py" --include="*.md"
```

### Key Files
- Guidelines: `george-scratch/AGENT_FILE_WRITING_GUIDELINES.md`
- This analysis: `george-scratch/ROOT_CAUSE_PRIVATE_TMP_ISSUE.md`
- Session summaries showing pattern: `george-scratch/SESSION_SUMMARY_2026-02-13_*.md`
