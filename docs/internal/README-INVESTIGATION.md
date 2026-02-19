# Context Window Investigation - README

## Overview

This directory contains the comprehensive investigation report on how large CloudWatch query results overflow the LLM agent's context window.

## Files

- **investigation-context-window-limits.md** - Full investigation report (27 KB, 787 lines)

## Quick Summary

### The Problem
Large CloudWatch log query results (up to 1,000 events, 500-700 KB JSON) are being serialized and added to the conversation history **without any size limits or truncation**. When the conversation continues, all previous messages (including these massive results) are resent to the LLM, causing context window overflow.

### Root Cause
1. **No size checking** - Results added to history without validation
2. **No truncation** - Full results passed to agent regardless of size
3. **No chunking** - Results not split into smaller pieces
4. **Full history replay** - Every message sent to LLM on each iteration
5. **No token counting** - Context size never validated before sending

### Critical Code Locations

| File | Lines | Issue |
|------|-------|-------|
| `orchestrator.py` | 513-521, 761-769 | Results added to history with `json.dumps()` without size check |
| `settings.py` | Missing | No config for result size or context limits |
| `cloudwatch_tools.py` | 200-204 | Allows up to 1,000 results per query (~500 KB) |
| `base.py` (LLM) | All | No token counting utilities |

### Key Findings

✅ **What the report covers:**
- Executive summary with problem chain
- Data flow diagrams (10-stage process)
- Actual query result sizes (1,000 events × 500 bytes = 500+ KB)
- Where serialization happens (exact code)
- Token limits by model (Claude 200K, GPT-4 128K, etc.)
- 5 specific problem areas
- 4 existing mechanisms (and why they don't help)
- 3 real failure scenarios
- Configuration gaps
- Proposed solutions in 5 phases

❌ **What currently doesn't exist:**
- Result size limits
- Context window validation
- Token counting
- Result truncation (except UI display)
- Result chunking
- History pruning

## For George

### To Review
1. Read the full report: `investigation-context-window-limits.md`
2. Focus sections for quick understanding:
   - Executive Summary (top of document)
   - Section 3: Problem Areas & Bottlenecks
   - Section 7: Error Scenarios
   - Section 11: Recommendations

### For Design Decisions
Key questions answered in the report:
1. How large can results get? → 500-700 KB per query
2. Where do they overflow? → During next LLM call (orchestrator.py line 725-726)
3. What models are affected? → All (Claude, GPT, Ollama, GitHub Copilot)
4. Can we truncate? → Yes, but need to implement
5. Should we chunk? → Yes, for complete analysis

### Next Steps
1. **Phase 1**: Add token counting and validation
2. **Phase 2**: Implement result truncation with user feedback
3. **Phase 3**: Add result chunking for large queries
4. **Phase 4**: Implement conversation history management (sliding window)
5. **Phase 5**: Update defaults and retry logic

## Investigation Methodology

Hans investigated by:
1. Tracing the complete data flow (CloudWatch → Tool → Orchestrator → LLM)
2. Analyzing each stage for size/limit checks
3. Reading actual code from all relevant files
4. Identifying configuration gaps
5. Creating realistic failure scenarios
6. Mapping exact file locations and line numbers
7. Documenting existing workarounds and why they fail

## Report Statistics

- **Total Lines**: 787
- **Total Size**: 27 KB
- **Sections**: 11
- **Code Examples**: 15+
- **Diagrams**: 2
- **Scenarios**: 3
- **File References**: 10+
- **Recommendations**: 5 phases, 18+ actionable items

---

Generated: February 12, 2026
Investigator: Hans (Code Librarian)
Status: Ready for review and implementation
