# Git Workflow: Feature Branch Strategy

## Overview
As of 2026-02-23, we are switching from working directly on `main` to using feature branches for all new development work.

## Workflow Process

### 1. Starting New Work
When beginning ANY new feature, bug fix, or enhancement:

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Create feature branch with descriptive name
git checkout -b feature/descriptive-name
```

### 2. Branch Naming Conventions

**Format**: `<type>/<short-description>`

**Types**:
- `feature/` - New features or enhancements
- `fix/` - Bug fixes
- `refactor/` - Code refactoring (no behavior change)
- `docs/` - Documentation only changes
- `test/` - Adding or updating tests
- `chore/` - Maintenance tasks (dependencies, tooling, etc.)

**Examples**:
- `feature/export-logs-to-csv`
- `fix/chat-scroll-position`
- `refactor/simplify-orchestrator`
- `docs/add-installation-guide`
- `test/improve-ui-coverage`
- `chore/update-dependencies`

### 3. Working on the Feature Branch

```bash
# Make changes and commit as usual
git add <files>
git commit -m "descriptive commit message"

# Push feature branch to remote
git push -u origin feature/descriptive-name

# Continue working...
git add <more-files>
git commit -m "another commit"
git push  # No -u needed after first push
```

### 4. Completing the Feature

When the feature is complete, tested, and ready:

```bash
# Ensure all changes are committed and pushed
git push

# Create a pull request
gh pr create --title "Feature: Descriptive Title" --body "$(cat <<'EOF'
## Summary
- Brief description of what this feature does
- Why it was needed
- How it works

## Changes
- List of key changes made
- Files/components affected

## Testing
- How it was tested
- Test results

## Documentation
- Any docs updated or added
EOF
)"
```

### 5. After PR is Merged

```bash
# Switch back to main
git checkout main

# Pull the merged changes
git pull origin main

# Delete the local feature branch (optional cleanup)
git branch -d feature/descriptive-name

# Delete the remote feature branch (optional cleanup)
git push origin --delete feature/descriptive-name
```

## Team Member Responsibilities

### George (TPM)
- **BEFORE tasking any team member**: Create the feature branch
- Communicate the branch name to the team member
- Ensure all work happens on the feature branch, not main
- Create PR when feature is complete and reviewed
- Coordinate merging back to main

### Hans (Librarian)
- Works on `main` for investigations (read-only, no commits)
- If investigation requires experimental changes, creates investigation branch

### Saanvi (Architect)
- Creates design documents in `george-scratch/` (no code changes)
- Reviews design on feature branch if code examples are needed

### Jackie (Engineer)
- **ALWAYS works on feature branches** (never directly on main)
- Commits all code changes to the feature branch
- Pushes feature branch regularly
- Notifies George when work is complete for review

### Han-Ron (Code Reviewer)
- Reviews code on feature branches
- Provides feedback for Jackie to address on the same branch
- Approves when ready for merge

### Raoul (QA Engineer)
- Writes tests on the same feature branch as the feature code
- Ensures all tests pass before feature is marked complete

### Tina (Technical Writer)
- Updates documentation on the same feature branch
- Or creates separate `docs/` branch if documentation is independent

## Exception: Hotfixes

For CRITICAL production bugs that need immediate fixing:

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug-description

# Fix, test, commit
git add <files>
git commit -m "hotfix: description"
git push -u origin hotfix/critical-bug-description

# Create PR and merge immediately after review
gh pr create --title "Hotfix: Critical Bug" --body "Emergency fix for production issue"
```

After hotfix is merged, immediately pull main:
```bash
git checkout main
git pull origin main
```

## Benefits of This Workflow

1. **Main branch always stable** - Only merged, tested code
2. **Parallel development** - Multiple features can be worked on simultaneously
3. **Code review before merge** - PRs enable review process
4. **Clean history** - Feature branches keep related commits together
5. **Easy rollback** - Can revert entire features if needed
6. **Better collaboration** - Clear what's in progress vs. completed

## Important Notes

- **NEVER commit directly to main** (except in extraordinary circumstances with user approval)
- Always create feature branch BEFORE starting work
- Keep feature branches focused (one feature per branch)
- Merge main into feature branch regularly to avoid conflicts
- Delete feature branches after merging to keep repository clean

---

**This workflow is now MANDATORY for all new work as of 2026-02-23.**
