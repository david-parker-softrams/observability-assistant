#!/bin/bash
# Documentation Reorganization Migration Script
# This script reorganizes 56 root-level and 75 george-scratch files into proper docs/ structure
# Run from repository root directory: /Users/David.Parker/src/observability-assistant

set -e

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║         DOCUMENTATION REORGANIZATION MIGRATION SCRIPT                     ║"
echo "║                    George Scratch Files Cleanup                           ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"

# PHASE 1: Create Missing Directories
echo ""
echo "=== PHASE 1: Creating directory structure ==="
mkdir -p docs/internal/bug-fixes/
mkdir -p george-scratch/archive/sessions-feb11-13/
echo "✅ Directories created"

# PHASE 2: Move Root-Level Investigation Files to docs/internal/
echo ""
echo "=== PHASE 2: Moving investigation docs to docs/internal/ ==="
mv INVESTIGATION_SUMMARY.md docs/internal/opencode-auth-investigation-summary.md 2>/dev/null || echo "  ⚠️  INVESTIGATION_SUMMARY.md not found"
mv INVESTIGATION_SUMMARY.txt docs/internal/opencode-auth-investigation-summary.txt 2>/dev/null || echo "  ⚠️  INVESTIGATION_SUMMARY.txt not found"
mv README_INVESTIGATION.md docs/internal/opencode-auth-investigation-notes.md 2>/dev/null || echo "  ⚠️  README_INVESTIGATION.md not found"
mv OLLAMA_INVESTIGATION_REPORT.md docs/internal/ollama-setup-investigation.md 2>/dev/null || echo "  ⚠️  OLLAMA_INVESTIGATION_REPORT.md not found"
mv CACHING_INVESTIGATION_SUMMARY.txt docs/internal/caching-investigation-summary.txt 2>/dev/null || echo "  ⚠️  CACHING_INVESTIGATION_SUMMARY.txt not found"
mv CACHING_SYSTEM_INVESTIGATION.md docs/internal/caching-system-investigation.md 2>/dev/null || echo "  ⚠️  CACHING_SYSTEM_INVESTIGATION.md not found"
mv OPENCODE_AUTH_INVESTIGATION.md docs/internal/opencode-auth-investigation-detailed.md 2>/dev/null || echo "  ⚠️  OPENCODE_AUTH_INVESTIGATION.md not found"
mv OPENCODE_TECHNICAL_DETAILS.md docs/internal/opencode-auth-technical-details.md 2>/dev/null || echo "  ⚠️  OPENCODE_TECHNICAL_DETAILS.md not found"
mv COPILOT_403_FIX_INVESTIGATION.md docs/internal/copilot-403-error-investigation.md 2>/dev/null || echo "  ⚠️  COPILOT_403_FIX_INVESTIGATION.md not found"
mv MIROTHINKER_STATUS.md docs/internal/mirothinker-status-report.md 2>/dev/null || echo "  ⚠️  MIROTHINKER_STATUS.md not found"
mv STATUS_FOOTER_CLICKABILITY_INVESTIGATION.md docs/internal/status-footer-clickability-investigation.md 2>/dev/null || echo "  ⚠️  STATUS_FOOTER_CLICKABILITY_INVESTIGATION.md not found"
mv AGENT_SELF_DIRECTION_INVESTIGATION.md docs/internal/agent-self-direction-investigation.md 2>/dev/null || echo "  ⚠️  AGENT_SELF_DIRECTION_INVESTIGATION.md not found"
mv INVESTIGATION_DELIVERY_SUMMARY.md docs/internal/investigation-delivery-summary.md 2>/dev/null || echo "  ⚠️  INVESTIGATION_DELIVERY_SUMMARY.md not found"
echo "✅ Investigation docs moved"

# PHASE 3: Move Bug Fix Files to docs/internal/bug-fixes/
echo ""
echo "=== PHASE 3: Moving bug fix docs to docs/internal/bug-fixes/ ==="
mv BUGFIX_IT_TEXT_IN_FOOTER.md docs/internal/bug-fixes/bugfix-it-text-in-footer.md 2>/dev/null || echo "  ⚠️  BUGFIX_IT_TEXT_IN_FOOTER.md not found"
mv BUGFIX_TOOL_SIDEBAR.md docs/internal/bug-fixes/bugfix-tool-sidebar.md 2>/dev/null || echo "  ⚠️  BUGFIX_TOOL_SIDEBAR.md not found"
mv STATUS_FOOTER_FIX.md docs/internal/bug-fixes/status-footer-fix.md 2>/dev/null || echo "  ⚠️  STATUS_FOOTER_FIX.md not found"
mv MESSAGE_ORDERING_FIX_SUMMARY.md docs/internal/bug-fixes/message-ordering-fix-summary.md 2>/dev/null || echo "  ⚠️  MESSAGE_ORDERING_FIX_SUMMARY.md not found"
mv LAYOUT_FIX_REPORT.md docs/internal/bug-fixes/layout-fix-report.md 2>/dev/null || echo "  ⚠️  LAYOUT_FIX_REPORT.md not found"
echo "✅ Bug fix docs moved"

# PHASE 4: Move Implementation Files to docs/internal/
echo ""
echo "=== PHASE 4: Moving implementation docs to docs/internal/ ==="
mv IMPLEMENTATION_SUMMARY.md docs/internal/implementation-agent-self-direction.md 2>/dev/null || echo "  ⚠️  IMPLEMENTATION_SUMMARY.md not found"
mv EXPANDABLE_RESULTS_IMPLEMENTATION.md docs/internal/implementation-expandable-results.md 2>/dev/null || echo "  ⚠️  EXPANDABLE_RESULTS_IMPLEMENTATION.md not found"
mv MAX_TOOL_ITERATIONS_IMPLEMENTATION.md docs/internal/implementation-max-tool-iterations.md 2>/dev/null || echo "  ⚠️  MAX_TOOL_ITERATIONS_IMPLEMENTATION.md not found"
mv TOOL_SIDEBAR_IMPLEMENTATION.md docs/internal/implementation-tool-sidebar.md 2>/dev/null || echo "  ⚠️  TOOL_SIDEBAR_IMPLEMENTATION.md not found"
mv SIDEBAR_ENHANCEMENT_SUMMARY.md docs/internal/implementation-sidebar-enhancement.md 2>/dev/null || echo "  ⚠️  SIDEBAR_ENHANCEMENT_SUMMARY.md not found"
mv SIDEBAR_VISUAL_COMPARISON.md docs/internal/comparison-sidebar-visual.md 2>/dev/null || echo "  ⚠️  SIDEBAR_VISUAL_COMPARISON.md not found"
mv PHASE_3_IMPLEMENTATION_SUMMARY.md docs/internal/phase-3-implementation-summary.md 2>/dev/null || echo "  ⚠️  PHASE_3_IMPLEMENTATION_SUMMARY.md not found"
mv PHASE1_COMPLETE.md docs/internal/phase-1-completion-report.md 2>/dev/null || echo "  ⚠️  PHASE1_COMPLETE.md not found"
mv PHASE5_SUMMARY.md docs/internal/phase-5-summary.md 2>/dev/null || echo "  ⚠️  PHASE5_SUMMARY.md not found"
mv PHASE6_SUMMARY.md docs/internal/phase-6-summary.md 2>/dev/null || echo "  ⚠️  PHASE6_SUMMARY.md not found"
mv raoul-phase1-test-report.md docs/internal/test-report-phase-1.md 2>/dev/null || echo "  ⚠️  raoul-phase1-test-report.md not found"
mv DOCUMENTATION_REORGANIZATION_SUMMARY.md docs/internal/project-documentation-reorganization-summary.md 2>/dev/null || echo "  ⚠️  DOCUMENTATION_REORGANIZATION_SUMMARY.md not found"
echo "✅ Implementation docs moved"

# PHASE 5: Move Testing Docs to docs/development/
echo ""
echo "=== PHASE 5: Moving testing docs to docs/development/ ==="
mv TEXTUAL_RESIZABLE_PANES_RESEARCH.md docs/development/textual-resizable-panes-research.md 2>/dev/null || echo "  ⚠️  TEXTUAL_RESIZABLE_PANES_RESEARCH.md not found"
mv LOGAI_IMPLEMENTATION_ROADMAP.md docs/development/logai-implementation-roadmap.md 2>/dev/null || echo "  ⚠️  LOGAI_IMPLEMENTATION_ROADMAP.md not found"
mv TESTING_COMPLETE.md docs/development/testing-complete-status.md 2>/dev/null || echo "  ⚠️  TESTING_COMPLETE.md not found"
mv TEST_SUMMARY_MULTI_SELECT.md docs/development/test-summary-multi-select.md 2>/dev/null || echo "  ⚠️  TEST_SUMMARY_MULTI_SELECT.md not found"
mv TEST_COMPLETION_REPORT.md docs/development/test-completion-report.md 2>/dev/null || echo "  ⚠️  TEST_COMPLETION_REPORT.md not found"
mv TESTING_GUIDE.md docs/development/testing-guide.md 2>/dev/null || echo "  ⚠️  TESTING_GUIDE.md not found"
mv STATUS_INDICATOR_TESTING_INDEX.md docs/development/testing-status-indicator-index.md 2>/dev/null || echo "  ⚠️  STATUS_INDICATOR_TESTING_INDEX.md not found"
mv STATUS_INDICATOR_TESTING_SUMMARY.md docs/development/testing-status-indicator-summary.md 2>/dev/null || echo "  ⚠️  STATUS_INDICATOR_TESTING_SUMMARY.md not found"
mv INTEGRATION_TEST_COMPLETION_REPORT.md docs/development/test-integration-completion.md 2>/dev/null || echo "  ⚠️  INTEGRATION_TEST_COMPLETION_REPORT.md not found"
mv STATUS_INDICATOR_TEST_REPORT.md docs/development/test-status-indicator-report.md 2>/dev/null || echo "  ⚠️  STATUS_INDICATOR_TEST_REPORT.md not found"
mv MANUAL_TEST_REPORT_STATUS_INDICATOR.md docs/development/test-manual-status-indicator.md 2>/dev/null || echo "  ⚠️  MANUAL_TEST_REPORT_STATUS_INDICATOR.md not found"
echo "✅ Testing docs moved"

# PHASE 6: Move Quick Reference & Guides
echo ""
echo "=== PHASE 6: Moving quick references and guides ==="
mv DOCS_QUICK_START.md docs/development/docs-quick-start.md 2>/dev/null || echo "  ⚠️  DOCS_QUICK_START.md not found"
mv PHASE_3_QUICK_REFERENCE.md docs/development/phase-3-quick-reference.md 2>/dev/null || echo "  ⚠️  PHASE_3_QUICK_REFERENCE.md not found"
mv AGENT_SELF_DIRECTION_README.md docs/development/agent-self-direction-readme.md 2>/dev/null || echo "  ⚠️  AGENT_SELF_DIRECTION_README.md not found"
mv AGENT_SELF_DIRECTION_QUICK_REFERENCE.md docs/development/agent-self-direction-quick-ref.md 2>/dev/null || echo "  ⚠️  AGENT_SELF_DIRECTION_QUICK_REFERENCE.md not found"
mv CODE_REVIEW.md docs/development/code-review-guide.md 2>/dev/null || echo "  ⚠️  CODE_REVIEW.md not found"
echo "✅ Quick references moved"

# PHASE 7: Move Comparison & Analysis Docs
echo ""
echo "=== PHASE 7: Moving comparison and analysis docs ==="
mv BEFORE_AFTER_COMPARISON.md docs/internal/comparison-before-after.md 2>/dev/null || echo "  ⚠️  BEFORE_AFTER_COMPARISON.md not found"
mv STATUS_FOOTER_BEFORE_AFTER_COMPARISON.md docs/internal/comparison-status-footer-before-after.md 2>/dev/null || echo "  ⚠️  STATUS_FOOTER_BEFORE_AFTER_COMPARISON.md not found"
mv INVESTIGATION_INDEX.md docs/internal/investigation-index.md 2>/dev/null || echo "  ⚠️  INVESTIGATION_INDEX.md not found"
mv ISSUES_FOR_JACKIE.md docs/internal/issues-for-review.md 2>/dev/null || echo "  ⚠️  ISSUES_FOR_JACKIE.md not found"
mv README_STATUS_FOOTER_INVESTIGATION.md docs/internal/status-footer-investigation-notes.md 2>/dev/null || echo "  ⚠️  README_STATUS_FOOTER_INVESTIGATION.md not found"
mv INVESTIGATION_SUMMARY_STATUS_FOOTER.md docs/internal/investigation-status-footer-summary.md 2>/dev/null || echo "  ⚠️  INVESTIGATION_SUMMARY_STATUS_FOOTER.md not found"
mv TASK_COMPLETE_MAX_TOOL_ITERATIONS.md docs/internal/task-status-max-tool-iterations.md 2>/dev/null || echo "  ⚠️  TASK_COMPLETE_MAX_TOOL_ITERATIONS.md not found"
echo "✅ Comparison and analysis docs moved"

# PHASE 8: Delete Duplicates
echo ""
echo "=== PHASE 8: Deleting duplicate files ==="
rm -f IMPLEMENTATION_COMPLETE_EXPANDABLE_RESULTS.md && echo "✅ Deleted IMPLEMENTATION_COMPLETE_EXPANDABLE_RESULTS.md" || echo "  ℹ️  File not found (already deleted)"

# PHASE 9: Archive Old george-scratch Sessions
echo ""
echo "=== PHASE 9: Archiving old session states from george-scratch/ ==="
mv george-scratch/SESSION_STATE_2026-02-11.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-11.md not found"
mv george-scratch/SESSION_STATE_2026-02-12.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-12.md not found"
mv george-scratch/SESSION_STATE_2026-02-12_cached-result-guidance.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-12_cached-result-guidance.md not found"
mv george-scratch/SESSION_STATE_2026-02-12_context-management.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-12_context-management.md not found"
mv george-scratch/SESSION_STATE_2026-02-12_statusfooter-bugfix.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-12_statusfooter-bugfix.md not found"
mv george-scratch/SESSION_STATE_2026-02-13_status-indicator-fix.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_STATE_2026-02-13_status-indicator-fix.md not found"
mv george-scratch/SESSION_2026-02-13_complete.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_2026-02-13_complete.md not found"
mv george-scratch/SESSION_2026-02-13_DAY_SUMMARY.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_2026-02-13_DAY_SUMMARY.md not found"
mv george-scratch/SESSION_2026-02-13_FINAL.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_2026-02-13_FINAL.md not found"
mv george-scratch/SESSION_SUMMARY_2026-02-13_cache-corruption-fix.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_SUMMARY_2026-02-13_cache-corruption-fix.md not found"
mv george-scratch/SESSION_SUMMARY_2026-02-13_clickable-shortcuts-and-cache-race-fix.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_SUMMARY_2026-02-13_clickable-shortcuts-and-cache-race-fix.md not found"
mv george-scratch/SESSION_SUMMARY_2026-02-13_final.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_SUMMARY_2026-02-13_final.md not found"
mv george-scratch/SESSION_SUMMARY_2026-02-13_status-indicator-it-bug-fix.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  SESSION_SUMMARY_2026-02-13_status-indicator-it-bug-fix.md not found"
mv george-scratch/DAILY_STATUS_2026-02-12.md george-scratch/archive/sessions-feb11-13/ 2>/dev/null || echo "  ⚠️  DAILY_STATUS_2026-02-12.md not found"
echo "✅ Old session states archived"

# PHASE 10: Summary & Verification
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                         MIGRATION COMPLETE!                               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"

echo ""
echo "📊 VERIFICATION:"
ROOT_DOCS=$(find . -maxdepth 1 -name "*.md" -o -name "*.txt" | wc -l)
SCRATCH_FILES=$(find george-scratch/ -maxdepth 1 -type f | wc -l)
ARCHIVE_FILES=$(find george-scratch/archive/ -type f 2>/dev/null | wc -l)
DOCS_TOTAL=$(find docs/ -type f | wc -l)

echo "  Root-level .md/.txt files: $ROOT_DOCS (should be ~5)"
echo "  george-scratch/ active files: $SCRATCH_FILES (should be ~20)"
echo "  george-scratch/archive/ files: $ARCHIVE_FILES (should be ~15)"
echo "  Total docs/ files: $DOCS_TOTAL (should be ~200+)"

echo ""
echo "✅ Migration script completed successfully!"
echo ""
echo "📝 Next Steps:"
echo "  1. Run: git status"
echo "  2. Review changes: git diff"
echo "  3. Update .gitignore if needed"
echo "  4. Commit: git add -A && git commit -m 'docs: reorganize documentation into structured directories'"
