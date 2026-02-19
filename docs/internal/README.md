# Internal Documentation

This directory contains internal project documentation including requirements, code reviews, QA reports, investigations, and historical project records. These documents provide context for development decisions and track the evolution of the project.

## Document Categories

### Requirements Documents (87 files)
Requirements specifications for features and improvements. These define what needs to be built and why.

**Key Requirements:**
- `requirements-general.md` - General project requirements
- `requirements-context-management-system.md` - Context management requirements
- `requirements-log-preview-feature.md` - Log preview feature requirements
- `requirements-github-copilot-integration.md` - GitHub Copilot integration requirements
- Plus 80+ other feature-specific requirements

### Code Reviews
Detailed code review documents for major features and changes. These provide technical analysis of implementations.

**Recent Reviews:**
- `code-review-log-preview-feature.md`
- `code-review-timeframe-selector.md`
- `code-review-context-window-fixes.md`
- `code-review-caching-fixes.md`
- Plus reviews for all major features

### QA Reports
Quality assurance test reports and summaries for features and releases.

**QA Documents:**
- `qa-report-context-management-system.md`
- `qa-report-log-groups-sidebar.md`
- `qa-report-log-preview-feature.md`
- `qa-report-timeframe-selector.md`
- `qa-summary-preload-log-groups.md`

### Investigation Reports
Technical investigations into issues, bugs, and design decisions.

**Key Investigations:**
- `INVESTIGATION_SUMMARY.md` - General investigation summary
- `TUI_ARCHITECTURE_INVESTIGATION.md` - TUI architecture research
- `CONTEXT_WINDOW_INVESTIGATION.md` - Context window analysis
- `COMMAND_R_TOOL_CALLING_INVESTIGATION.md` - Command-R tool calling research
- `CACHE_BUG_ROOT_CAUSE.md` - Cache bug analysis
- `PASTE_FUNCTIONALITY_INVESTIGATION.md` - Paste feature investigation

### Implementation Documentation
Detailed implementation summaries and technical documentation.

**Implementation Docs:**
- `implementation-fix-truncation.md`
- `implementation-list-log-groups-response.md`
- `implementation-log-groups-sidebar.md`
- `implementation-preload-log-groups.md`

### Project Status and Summaries
High-level project status reports and completion summaries.

**Status Documents:**
- `PROJECT_STATUS.md` - Overall project status
- `FINAL_PROJECT_SUMMARY.md` - Final project summary
- `PRODUCTION_READY_SUMMARY.md` - Production readiness summary
- `QA_SIGNOFF_SUMMARY.md` - QA sign-off documentation
- `EXECUTIVE-SUMMARY-QA.md` - Executive QA summary

### Quick References
Quick reference guides for specific features and fixes (internal use).

**References:**
- `quick-reference-command-r.md` - Command-R fix quick reference
- `quick-reference-context-management.md` - Context management reference
- `quickref-timeframe-selector.md` - Timeframe selector reference
- `OPENTHINKER_QUICK_REFERENCE.md` - OpenThinker model reference

### Testing and Verification
Internal testing reports and verification documents.

**Testing Docs:**
- `TOOL_SIDEBAR_TEST_REPORT.md` - Tool sidebar test results
- `phase2-test-quick-reference.md` - Phase 2 test reference
- `phase2-test-summary.md` - Phase 2 test summary
- `raoul-phase2-testing-complete.md` - Phase 2 completion
- `VERIFICATION_CONFIG_CLEANUP_COMPLETE.md` - Config cleanup verification

### Changelogs and Documentation
- `changelog-context-management.md` - Context management changelog
- `documentation-delivery-summary.md` - Documentation delivery summary
- `documentation-log-groups-sidebar.md` - Log groups documentation
- `doc-summary-timeframe-selector.md` - Timeframe selector doc summary

### Fix Summaries and Root Cause Analysis
- `GITHUB_COPILOT_FIX_SUMMARY.md` - GitHub Copilot fixes
- `TOOL_CALLING_FIX_COMPLETE.md` - Tool calling fix completion
- `ROOT_CAUSE_PRIVATE_TMP_ISSUE.md` - Private /tmp issue analysis
- `lsp_errors_fix_report.md` - LSP errors fix report
- `MLX_OLLAMA_FIX.md` - MLX Ollama integration fix

### Implementation Summaries
- `OPENTHINKER_IMPLEMENTATION_SUMMARY.md` - OpenThinker implementation
- `phase-4-ui-implementation-summary.md` - Phase 4 UI summary
- `phase-4-ui-visual-flow.md` - Phase 4 visual flow
- `mvp-implementation-plan.md` - MVP implementation plan
- `project-summary-caching-fixes.md` - Caching fixes summary

## Usage Guidelines

### For Developers
Use these documents to:
- **Understand requirements** before implementing features
- **Review past decisions** to avoid repeating mistakes
- **Learn from investigations** when facing similar issues
- **Track feature evolution** through code reviews and QA reports

### For Project Managers
Use these documents to:
- **Track progress** through status reports and summaries
- **Review quality** through QA reports
- **Understand blockers** through investigation reports
- **Plan releases** using requirement and implementation docs

### For QA Engineers
Use these documents to:
- **Review requirements** before testing
- **Reference past QA reports** for regression testing
- **Understand bug context** through investigation reports
- **Verify fixes** using code review documentation

## Document Naming Conventions

- `requirements-*.md` - Feature or fix requirements
- `code-review-*.md` - Code review documentation
- `qa-report-*.md` - Quality assurance test reports
- `qa-summary-*.md` - QA summary documents
- `investigation-*.md` - Technical investigations
- `implementation-*.md` - Implementation details
- `*-summary.md` or `*_SUMMARY.md` - Project summaries
- `quick-reference-*.md` or `quickref-*.md` - Quick reference guides

## Related Documentation

- **Architecture:** [../architecture/](../architecture/) - System design documents
- **Development:** [../development/](../development/) - Developer workflows and best practices
- **User Guide:** [../user-guide/](../user-guide/) - End-user documentation

## Historical Context

These documents represent the project's development history from February 2026 and earlier. They provide:

1. **Traceability:** Requirements → Design → Implementation → QA
2. **Decision rationale:** Why things were built the way they were
3. **Lessons learned:** What worked and what didn't
4. **Bug history:** Root causes and fixes for issues

## Searching Internal Docs

### Finding Requirements for a Feature
```bash
ls requirements-*feature-name*.md
```

### Finding Code Reviews
```bash
ls code-review-*.md
```

### Finding QA Reports
```bash
ls qa-report-*.md qa-summary-*.md
```

### Finding Investigations
```bash
ls investigation-*.md *INVESTIGATION*.md
```

## Note on Session Files

Session notes and daily status reports remain in the `george-scratch/` directory as they represent real-time development logs and are most useful in chronological context. This includes:

- `SESSION_*.md` - Session notes and summaries
- `SESSION_STATE_*.md` - Session state snapshots
- `DAILY_STATUS_*.md` - Daily status reports
- `*_COMPLETE.md` - Completion markers

## Contributing

When adding new internal documentation:

1. **Use the correct naming convention** based on document type
2. **Reference related documents** for traceability
3. **Include date and context** in the document header
4. **Link to implementations** when documenting requirements
5. **Update this README** if adding a new category

---

**Note:** This documentation is for internal project use. For end-user documentation, see [../user-guide/](../user-guide/).
