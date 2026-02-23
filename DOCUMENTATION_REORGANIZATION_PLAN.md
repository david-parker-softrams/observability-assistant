# Documentation Reorganization Plan & Analysis

**Prepared by:** Hans (Code Librarian)
**Date:** February 20, 2026
**Total Files to Process:** 56 root-level + 75 george-scratch files
**Estimated Reorganization Time:** ~30 minutes

---

## EXECUTIVE SUMMARY

The repository has accumulated significant documentation across two locations:
- **56 markdown/text files** in the repository root (cluttering the root namespace)
- **75 files** in `george-scratch/` (mix of active session notes and completed feature documentation)

**Key Finding:** Many files in `george-scratch/` represent *completed, production-ready work* that belongs in permanent project documentation, while the root contains duplicates and superseded investigations.

**Recommended Actions:**
1. Move 56 root-level files into organized `docs/` structure
2. Migrate ~40 completed feature docs from `george-scratch/` to permanent locations
3. Keep ~20 essential files in `george-scratch/` for active project coordination
4. Update `.gitignore` to prevent future clutter

---

# QUICK START - ACTION SUMMARY

## By the Numbers

| Category | Count | Action | Target |
|----------|-------|--------|--------|
| Root docs → docs/internal/ | 24 | MOVE | Investigation, implementation docs |
| Root docs → docs/internal/bug-fixes/ | 5 | MOVE | Bug fix reports |
| Root docs → docs/development/ | 18 | MOVE | Testing, guides, references |
| Root docs to keep | 1 | KEEP | README.md |
| Root docs duplicates | 1 | DELETE | IMPLEMENTATION_COMPLETE_EXPANDABLE_RESULTS.md |
| george-scratch → permanent docs | 40 | MOVE | Completed features |
| george-scratch → keep active | 20 | KEEP | Current session notes |
| george-scratch → archive | 15 | ARCHIVE | Old session states |

**Total transformation: ~131 files reorganized into logical structure**

---

## PRIORITY RANKING (Do First)

**Priority 1 (Critical Path):**
1. Create missing subdirectories
2. Move root-level files to docs/ (56 files)
3. Delete obvious duplicates
4. Archive old george-scratch sessions (15 files)

**Priority 2 (Consolidation):**
1. Consolidate log preview feature docs (3 → 1 file)
2. Consolidate context viewer feature docs (10+ → 1 file)
3. Move remaining george-scratch feature docs to permanent locations (40 files)
4. Verify 20 essential files remain in george-scratch/

**Priority 3 (Cleanup):**
1. Update .gitignore
2. Update cross-references in documentation
3. Verify all links still work
4. Commit and document changes

---

# TASK 1: ROOT-LEVEL DOCUMENTATION (56 files)

## Breakdown by Category

### Category A: Investigations (14 files) → docs/internal/

```
INVESTIGATION_SUMMARY.md → docs/internal/opencode-auth-investigation-summary.md
INVESTIGATION_SUMMARY.txt → docs/internal/opencode-auth-investigation-summary.txt
README_INVESTIGATION.md → docs/internal/opencode-auth-investigation-notes.md
OLLAMA_INVESTIGATION_REPORT.md → docs/internal/ollama-setup-investigation.md
CACHING_INVESTIGATION_SUMMARY.txt → docs/internal/caching-investigation-summary.txt
CACHING_SYSTEM_INVESTIGATION.md → docs/internal/caching-system-investigation.md
OPENCODE_AUTH_INVESTIGATION.md → docs/internal/opencode-auth-investigation-detailed.md
OPENCODE_TECHNICAL_DETAILS.md → docs/internal/opencode-auth-technical-details.md
COPILOT_403_FIX_INVESTIGATION.md → docs/internal/copilot-403-error-investigation.md
MIROTHINKER_STATUS.md → docs/internal/mirothinker-status-report.md
STATUS_FOOTER_CLICKABILITY_INVESTIGATION.md → docs/internal/status-footer-clickability-investigation.md
AGENT_SELF_DIRECTION_INVESTIGATION.md → docs/internal/agent-self-direction-investigation.md
TEXTUAL_RESIZABLE_PANES_RESEARCH.md → docs/development/textual-resizable-panes-research.md
LOGAI_IMPLEMENTATION_ROADMAP.md → docs/development/logai-implementation-roadmap.md
```

### Category B: Bug Fixes (5 files) → docs/internal/bug-fixes/

```
BUGFIX_IT_TEXT_IN_FOOTER.md → docs/internal/bug-fixes/bugfix-it-text-in-footer.md
BUGFIX_TOOL_SIDEBAR.md → docs/internal/bug-fixes/bugfix-tool-sidebar.md
STATUS_FOOTER_FIX.md → docs/internal/bug-fixes/status-footer-fix.md
MESSAGE_ORDERING_FIX_SUMMARY.md → docs/internal/bug-fixes/message-ordering-fix-summary.md
LAYOUT_FIX_REPORT.md → docs/internal/bug-fixes/layout-fix-report.md
```

### Category C: Implementation Reports (12 files) → docs/internal/

```
IMPLEMENTATION_SUMMARY.md → docs/internal/implementation-agent-self-direction.md
EXPANDABLE_RESULTS_IMPLEMENTATION.md → docs/internal/implementation-expandable-results.md
IMPLEMENTATION_COMPLETE_EXPANDABLE_RESULTS.md → DELETE (duplicate)
MAX_TOOL_ITERATIONS_IMPLEMENTATION.md → docs/internal/implementation-max-tool-iterations.md
TOOL_SIDEBAR_IMPLEMENTATION.md → docs/internal/implementation-tool-sidebar.md
SIDEBAR_ENHANCEMENT_SUMMARY.md → docs/internal/implementation-sidebar-enhancement.md
SIDEBAR_VISUAL_COMPARISON.md → docs/internal/comparison-sidebar-visual.md
PHASE_3_IMPLEMENTATION_SUMMARY.md → docs/internal/phase-3-implementation-summary.md
PHASE1_COMPLETE.md → docs/internal/phase-1-completion-report.md
PHASE5_SUMMARY.md → docs/internal/phase-5-summary.md
PHASE6_SUMMARY.md → docs/internal/phase-6-summary.md
raoul-phase1-test-report.md → docs/internal/test-report-phase-1.md
INVESTIGATION_DELIVERY_SUMMARY.md → docs/internal/investigation-delivery-summary.md
DOCUMENTATION_REORGANIZATION_SUMMARY.md → docs/internal/project-documentation-reorganization-summary.md
```

### Category D: Testing Docs (7 files) → docs/development/

```
TESTING_COMPLETE.md → docs/development/testing-complete-status.md
TEST_SUMMARY_MULTI_SELECT.md → docs/development/test-summary-multi-select.md
TEST_COMPLETION_REPORT.md → docs/development/test-completion-report.md
TESTING_GUIDE.md → docs/development/testing-guide.md
STATUS_INDICATOR_TESTING_INDEX.md → docs/development/testing-status-indicator-index.md
STATUS_INDICATOR_TESTING_SUMMARY.md → docs/development/testing-status-indicator-summary.md
INTEGRATION_TEST_COMPLETION_REPORT.md → docs/development/test-integration-completion.md
STATUS_INDICATOR_TEST_REPORT.md → docs/development/test-status-indicator-report.md
MANUAL_TEST_REPORT_STATUS_INDICATOR.md → docs/development/test-manual-status-indicator.md
```

### Category E: Quick Refs & Guides (6 files) → docs/development/ & docs/internal/

```
DOCS_QUICK_START.md → docs/development/docs-quick-start.md
PHASE_3_QUICK_REFERENCE.md → docs/development/phase-3-quick-reference.md
AGENT_SELF_DIRECTION_README.md → docs/development/agent-self-direction-readme.md
AGENT_SELF_DIRECTION_QUICK_REFERENCE.md → docs/development/agent-self-direction-quick-ref.md
CODE_REVIEW.md → docs/development/code-review-guide.md
INVESTIGATION_INDEX.md → docs/internal/investigation-index.md
```

### Category F: Comparisons & Analysis (5 files)

```
BEFORE_AFTER_COMPARISON.md → docs/internal/comparison-before-after.md
STATUS_FOOTER_BEFORE_AFTER_COMPARISON.md → docs/internal/comparison-status-footer-before-after.md
README_STATUS_FOOTER_INVESTIGATION.md → docs/internal/status-footer-investigation-notes.md
INVESTIGATION_SUMMARY_STATUS_FOOTER.md → docs/internal/investigation-status-footer-summary.md
ISSUES_FOR_JACKIE.md → docs/internal/issues-for-review.md
```

### Category G: Keep or Minor Actions

```
README.md → KEEP in root (main project documentation)
TASK_COMPLETE_MAX_TOOL_ITERATIONS.md → docs/internal/task-status-max-tool-iterations.md
verification_output.txt → DELETE if outdated, else move to docs/internal/
```

---

# TASK 2: GEORGE-SCRATCH CLEANUP & MIGRATION

## Keep in george-scratch/ (20 files - Active Session Notes)

These are essential for George's current project coordination:

```
✅ 00-READ-ME-FIRST.md - Coordination hub for log preview
✅ QUICK-FIX-GUIDE.md - Active troubleshooting
✅ INVESTIGATION-CHECKLIST.md - Current investigations
✅ README-INVESTIGATION.md - Investigation reference
✅ session-summary-2026-02-20.md - Latest session
✅ end-of-day-summary-2026-02-19.md - Recent status
✅ session-notes-2026-02-19.md - Working notes
✅ session-notes-2026-02-19-context-fixes-complete.md - Feature status
✅ session-notes-2026-02-19-context-visibility-fix.md - Feature status
✅ session-summary-2026-02-19-callback-fix-complete.md - Recent completion
✅ CONTEXT_BUG_QUICK_SUMMARY.txt - Executive brief
✅ CONTEXT_BUG_READ_ME_FIRST.txt - Entry point
✅ CONTEXT_BUG_EXECUTIVE_BRIEF.txt - TPM summary
✅ multi-select-implementation-summary.md - Recent feature
✅ requirements-multi-select-log-groups.md - Recent requirements
✅ session-summary-status-footer-fix-complete.md - Status
✅ CONTEXT_UX_BUG_INVESTIGATION.md - Active investigation
✅ multi-select-code-review-request.md - Active review
✅ hover-area-fix-report.md - Recent fix
✅ QUICK-REFERENCE-LOAD-100.md - Active reference
```

---

## Move to Permanent Docs (40 files)

### Design Docs → docs/architecture/
- design-context-viewer-feature.md
- design-context-viewer-two-sections.md
- design-log-preview-100-entries.md

### Requirements → docs/architecture/
- requirements-context-viewer-feature.md
- requirements-fix-add-to-context-bug.md
- requirements-fix-context-entry-limit-bug.md
- requirements-fix-context-message-order.md
- requirements-fix-context-visibility-bug.md
- requirements-log-preview-last-100.md

### Code Reviews → docs/internal/
- code-review-fix-add-to-context-bug.md
- code-review-fix-context-message-order.md
- code-review-fix-context-visibility-bug.md
- code-review-log-preview-100-entries.md
- code-review-status-footer-refactor.md

### QA Reports → docs/development/
- qa-report-fix-add-to-context-bug.md
- qa-report-fix-context-message-order.md
- qa-report-fix-context-visibility-bug.md
- qa-report-log-preview-100-entries.md
- test-report-status-footer.md

### Implementation Summaries → docs/internal/
- implementation-summary-context-viewer.md
- context-viewer-two-section-implementation-summary.md
- full-context-implementation.md
- multi-select-implementation-summary.md

### Bug Fixes → docs/internal/bug-fixes/
- context-viewer-bug-fix-report.md
- context-viewer-rendering-fix.md
- context-viewer-scrolling-fix.md
- hover-area-fix-report.md

### Investigations → docs/internal/
- CONTEXT_UX_BUG_INVESTIGATION.md
- investigation-add-to-context-bug.md
- investigation-context-modal-result-issue.md
- investigation-log-preview-100-entries.md
- INDEX-LOG-PREVIEW-INVESTIGATION.md

### Documentation → docs/development/ & docs/user-guide/
- doc-summary-log-preview-100-entries.md
- feature-doc-log-preview-100-entries.md
- context-viewer-enhancement-req.md
- context-viewer-code-review-complete.md
- context-viewer-changes-for-review.md
- context-viewer-blank-investigation.md
- release-notes-log-preview-100-entries.md
- CONTEXT_BUG_CODE_MAP.txt

---

## Archive (15 files) → george-scratch/archive/sessions-feb11-13/

Old session states from Feb 11-13 (superseded by newer sessions):

```
SESSION_STATE_2026-02-11.md
SESSION_STATE_2026-02-12.md
SESSION_STATE_2026-02-12_cached-result-guidance.md
SESSION_STATE_2026-02-12_context-management.md
SESSION_STATE_2026-02-12_statusfooter-bugfix.md
SESSION_STATE_2026-02-13_status-indicator-fix.md
SESSION_2026-02-13_complete.md
SESSION_2026-02-13_DAY_SUMMARY.md
SESSION_2026-02-13_FINAL.md
SESSION_SUMMARY_2026-02-13_cache-corruption-fix.md
SESSION_SUMMARY_2026-02-13_clickable-shortcuts-and-cache-race-fix.md
SESSION_SUMMARY_2026-02-13_final.md
SESSION_SUMMARY_2026-02-13_status-indicator-it-bug-fix.md
DAILY_STATUS_2026-02-12.md
qa-summary-log-preview-100-entries.txt
```

---

# TASK 3: CONSOLIDATION OPPORTUNITIES

## High-Priority Consolidations

### 1. Log Preview Feature (3 files → 1)
- `design-log-preview-100-entries.md`
- `feature-doc-log-preview-100-entries.md`
- `doc-summary-log-preview-100-entries.md`
→ **Create:** `docs/architecture/feature-log-preview-100-complete.md`

### 2. Context Viewer Feature (10+ files → 1)
- Multiple `context-viewer-*.md` files
- Design, implementation, fixes, investigations all covered
→ **Create:** `docs/internal/feature-context-viewer-complete.md`

### 3. Log Preview Investigation (3 files → 1)
- `investigation-log-preview-100-entries.md` (768 lines - comprehensive)
- `INDEX-LOG-PREVIEW-INVESTIGATION.md` (summary)
- `INVESTIGATION-SUMMARY-LOG-PREVIEW.md` (summary)
→ **Keep:** comprehensive version, DELETE summaries

### 4. Multi-Select Feature (3 files → 1)
- `multi-select-implementation-summary.md`
- `requirements-multi-select-log-groups.md`
- `multi-select-code-review-request.md`
→ **Create:** `docs/architecture/feature-multi-select-complete.md`

---

# TASK 4: .GITIGNORE UPDATES

Add these rules to `.gitignore`:

```gitignore
# Archive old session files (not needed in active tracking)
george-scratch/archive/

# Temporary backup files
*.md.bak
*.txt.bak

# DS_Store files that may get created
george-scratch/**/.DS_Store
```

---

# EXECUTION PLAN

## Phase 1: Create Directory Structure
```bash
mkdir -p docs/internal/bug-fixes/
mkdir -p george-scratch/archive/sessions-feb11-13/
```

## Phase 2: Move Root-Level Files (45 mins)
- Move 24 files to `docs/internal/`
- Move 5 files to `docs/internal/bug-fixes/`
- Move 18 files to `docs/development/`
- Delete 1 duplicate file
- Keep 1 file in root (README.md)

## Phase 3: Archive Old Sessions (5 mins)
```bash
mv george-scratch/SESSION_*.md george-scratch/archive/sessions-feb11-13/
mv george-scratch/DAILY_STATUS_*.md george-scratch/archive/sessions-feb11-13/
```

## Phase 4: Move Feature Docs from george-scratch (20 mins)
- Move 40 completed feature files to permanent docs/ locations
- Keep 20 essential active session files

## Phase 5: Consolidate Duplicates (15 mins)
- Create consolidated feature documentation files
- Delete redundant copies
- Update cross-references

## Phase 6: Final Cleanup (10 mins)
- Update .gitignore
- Verify all links work
- Test documentation navigation
- Commit changes

---

# SUCCESS CRITERIA

✅ Root-level .md/.txt files reduced from 56 to ~5 (mostly README.md)
✅ george-scratch/ reduced from 75 to 20 active files
✅ 40+ completed feature docs in permanent docs/ structure
✅ 15 old sessions archived but preserved
✅ No broken links in moved documentation
✅ Clear documentation of all major features and investigations
✅ .gitignore updated to prevent future clutter
✅ Single commit documenting the reorganization

---

# CRITICAL NOTES

1. **Do NOT delete** the archive folder from git - it contains historical records
2. **Update cross-references** in moved files that point to other root files
3. **Keep README.md** in root - it's the primary entry point for the project
4. **Preserve all content** - this is a move/reorganize, not a cleanup
5. **Test links** after reorganization to ensure documentation is navigable

---

**This plan is ready for execution. Start with Phase 1 (create directories) and work through sequentially.**
