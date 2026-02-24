# Design Document: Release Automation Fix

**Author:** Saanvi (Senior Software Architect)
**Date:** Feb 24, 2026
**Status:** Ready for Implementation
**Requirements:** `george-scratch/requirements-release-automation.md`
**Implementer:** Jackie

---

## Overview

This design addresses two broken aspects of the release pipeline and adds
contributor documentation. The changes are minimal and surgical — three files
created/modified, zero changes to release-please configuration.

### Files to Change

| File | Action |
|---|---|
| `.github/workflows/release.yml` | **Modify** — add auto-merge job |
| `.github/workflows/pr-title-check.yml` | **Create** — new workflow |
| `CONTRIBUTING.md` | **Create** — new file |
| `release-please-config.json` | No change |
| `.release-please-manifest.json` | No change |

---

## 1. Changes to `.github/workflows/release.yml`

### Problem

The release-please action creates a Release PR (e.g., `chore(main): release
logai 0.2.0`) but a human must manually merge it. This breaks the "zero
touch" goal.

### Design Decision

Add a second job `auto-merge` that runs after `release-please` and calls
`gh pr merge --auto --squash` with the PR number output by the release-please
step. Key design points:

- **Why `--auto`:** This sets GitHub's native auto-merge flag. The PR merges
  as soon as all required status checks pass. If the repo has no required
  checks on main, it merges immediately. This is safer than `--merge-now`
  because it respects branch protection rules.
- **Why `--squash`:** Matches the repo's existing squash-merge convention and
  keeps the release commit clean on main.
- **Conditional execution:** The job only runs when `release_created` is
  falsy (meaning release-please created/updated a PR but did NOT cut a final
  release) AND `pr` is truthy (a PR number exists). When `release_created` is
  true, the release already happened — the PR was already merged by
  release-please itself, so there's nothing to auto-merge.
- **`prs` output:** release-please v4 outputs the PR number in a `prs`
  output (JSON string). For a monorepo or single-package repo, the step also
  outputs a flat `pr` key. We use the simpler `pr` output since this is a
  single-package repo.

### Exact YAML

Replace the entire `.github/workflows/release.yml` with:

```yaml
name: Release Please

on:
  push:
    branches:
      - main

concurrency:
  group: release-please
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    outputs:
      release_created: ${{ steps.release.outputs.release_created }}
      pr: ${{ steps.release.outputs.pr }}
    steps:
      - uses: googleapis/release-please-action@v4.4.0
        id: release
        with:
          target-branch: main

  auto-merge:
    needs: release-please
    if: ${{ needs.release-please.outputs.pr && !needs.release-please.outputs.release_created }}
    runs-on: ubuntu-latest
    steps:
      - name: Enable auto-merge on release PR
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ needs.release-please.outputs.pr }}
        run: |
          gh pr merge "$PR_NUMBER" \
            --repo "$GITHUB_REPOSITORY" \
            --auto \
            --squash
```

### Why This Works

1. Push to main triggers `release-please` job.
2. release-please analyzes commits since last release, creates/updates a
   Release PR, and outputs its number.
3. `auto-merge` job picks up the PR number, sets auto-merge via `gh`.
4. GitHub merges the PR once status checks pass (or immediately if none).
5. That merge triggers another push to main, which runs release-please again.
   This time release-please sees its own PR was merged and creates the actual
   GitHub Release + tag. `release_created` is now `true`, so `auto-merge`
   is skipped (nothing to merge).

### Note on `id: release`

The existing workflow does NOT have `id: release` on the release-please step.
**This must be added** — without it, the step outputs are not addressable.
The YAML above includes it.

---

## 2. New `.github/workflows/pr-title-check.yml`

### Problem

PR #6 merged with title `Fix ...` (no conventional commit type prefix).
release-please couldn't parse it and skipped the release. There is no
guardrail preventing this.

### Design Decision: `amannn/action-semantic-pull-request`

I evaluated two approaches:

| Approach | Pros | Cons |
|---|---|---|
| `amannn/action-semantic-pull-request` | Battle-tested (2k+ stars), configurable, maintained, handles edge cases | External dependency |
| Custom shell script with regex | No dependency | Must maintain regex, easy to get wrong on edge cases (scopes, `!`, multi-line) |

**Recommendation: Use `amannn/action-semantic-pull-request@v5`.**

Rationale:
- It is the de facto standard for this exact use case.
- It handles scoped types (`feat(api): ...`), breaking change markers
  (`feat!: ...`), and all edge cases correctly.
- Configuration is declarative YAML — no regex to maintain.
- The action runs in ~2 seconds and has no heavy dependencies.
- It produces excellent human-readable error messages out of the box.

### Trigger Events

The workflow triggers on `pull_request_target` (not `pull_request`). This is
the correct event because:

- `pull_request_target` runs in the context of the base branch, so it has
  access to secrets and works with fork PRs.
- `amannn/action-semantic-pull-request` specifically recommends
  `pull_request_target` in its README.
- We do NOT also need `pull_request` — using both would cause duplicate runs.
  `pull_request_target` covers all cases.

**Important architecture note:** The requirements doc says to trigger on both
`pull_request` and `pull_request_target`. I am recommending **only
`pull_request_target`** because:
1. The `amannn` action's own docs explicitly recommend this.
2. Running on both events would cause every PR to be checked twice — wasteful
   and confusing (two check statuses on every PR).
3. `pull_request_target` already works for both fork and non-fork PRs.

George — if the user insists on both events, Jackie can add both, but the
duplicate runs will be visible on every PR. I'd push back on this.

### Release-Please PR Titles

Release-please creates PRs with titles like `chore(main): release logai 0.2.0`.
This is already a valid conventional commit (`chore` type with `main` scope),
so the check passes automatically. No special exclusion logic needed.

### Exact YAML

Create `.github/workflows/pr-title-check.yml`:

```yaml
name: PR Title Check

on:
  pull_request_target:
    types:
      - opened
      - edited
      - reopened
      - synchronize

permissions:
  pull-requests: read

jobs:
  validate-pr-title:
    name: Validate PR title
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            docs
            style
            refactor
            test
            chore
            perf
            ci
            build
            revert
          requireScope: false
          subjectPattern: ^.+$
          subjectPatternError: |
            The PR title "{subject}" is not valid — the description after the
            type prefix must not be empty.
```

### How It Fails

When a developer opens a PR with title `Fix something broken`, the action
outputs an error like:

```
Pull Request title "Fix something broken" does not match the required format:
<type>[optional scope]: <description>

Valid types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert

Examples:
  feat: add user authentication
  fix(api): handle null response
  docs: update README
```

The check shows as a red X on the PR, blocking merge (assuming this check
is added as a required status check in branch protection — see section 5).

### Branch Protection Requirement

**Important:** For this check to actually *block* merges, the repository's
branch protection rules for `main` must require the
`validate-pr-title` / `Validate PR title` status check to pass. Jackie or
George should verify this is configured in Settings > Branches > Branch
protection rules after the workflow is deployed.

If branch protection is not configured, the check will still run and show
red/green on the PR, but it won't prevent merging. This is a repo settings
concern, not a code concern.

---

## 3. `CONTRIBUTING.md`

### Content Outline

Create `CONTRIBUTING.md` at the repo root with the following sections:

1. **Header** — "Contributing to LogAI"
2. **PR Title Format** — explain that PR titles MUST follow conventional
   commit format because:
   - GitHub squash-merges use the PR title as the commit message on main
   - release-please parses these commit messages to determine version bumps
   - CI enforces the format (PR Title Check workflow)
3. **Format specification:**
   ```
   <type>[optional scope][optional !]: <description>
   ```
4. **Valid types table** with descriptions:
   - `feat` — A new feature
   - `fix` — A bug fix
   - `docs` — Documentation only changes
   - `style` — Formatting, missing semicolons, etc. (no code change)
   - `refactor` — Code change that neither fixes a bug nor adds a feature
   - `test` — Adding or updating tests
   - `chore` — Maintenance tasks, dependency updates, CI changes
   - `perf` — Performance improvements
   - `ci` — CI/CD configuration changes
   - `build` — Build system or external dependency changes
   - `revert` — Reverts a previous commit
5. **Semver bump rules table:**

   | Commit type | Version bump | Example |
   |---|---|---|
   | `fix:`, `perf:` | PATCH (0.1.0 -> 0.1.1) | `fix: handle null pointer in parser` |
   | `feat:` | MINOR (0.1.0 -> 0.2.0) | `feat: add CSV export` |
   | `feat!:` or body contains `BREAKING CHANGE:` | MAJOR (0.1.0 -> 1.0.0) | `feat!: redesign auth API` |
   | `docs:`, `chore:`, `test:`, `ci:`, etc. | No release | `docs: update API reference` |

6. **Examples** — good and bad:
   - `feat: add log streaming support` (valid)
   - `fix(parser): handle empty input` (valid, with scope)
   - `feat!: redesign CLI interface` (valid, breaking change)
   - `Fixed the bug` (INVALID — no type prefix)
   - `Feature: add thing` (INVALID — `Feature` is not a valid type)
7. **Note on CI enforcement** — "PR titles are validated by the `PR Title
   Check` workflow. PRs with invalid titles will not pass CI."

### Exact Content

```markdown
# Contributing to LogAI

## PR Title Format (Required)

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
to automate versioning and releases. Since GitHub squash-merges PRs, your
**PR title becomes the commit message** on `main` — so PR titles must follow
the conventional commit format.

**CI enforces this.** PRs with invalid titles will fail the `PR Title Check`
and cannot be merged.

### Format

```
<type>[optional scope][optional !]: <description>
```

### Valid Types

| Type | Description |
|---|---|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Formatting, whitespace, etc. (no logic change) |
| `refactor` | Code restructuring (no new feature, no bug fix) |
| `test` | Adding or updating tests |
| `chore` | Maintenance, dependency updates |
| `perf` | Performance improvements |
| `ci` | CI/CD configuration changes |
| `build` | Build system or dependency changes |
| `revert` | Reverts a previous commit |

### How Version Bumps Work

[release-please](https://github.com/googleapis/release-please) reads commit
messages on `main` and determines the next version automatically:

| Commit type | Version bump | Example |
|---|---|---|
| `fix:`, `perf:` | **PATCH** (0.1.0 → 0.1.1) | `fix: handle null pointer in parser` |
| `feat:` | **MINOR** (0.1.0 → 0.2.0) | `feat: add CSV export` |
| `feat!:` or `BREAKING CHANGE:` in body | **MAJOR** (0.1.0 → 1.0.0) | `feat!: redesign auth API` |
| `docs:`, `chore:`, `test:`, `ci:`, etc. | No release | `docs: update API reference` |

### Examples

**Valid:**
- `feat: add log streaming support`
- `fix(parser): handle empty input gracefully`
- `feat!: redesign CLI interface`
- `chore: upgrade dependencies`
- `docs: add troubleshooting section to README`

**Invalid (will fail CI):**
- `Fixed the bug` — missing type prefix
- `Feature: add thing` — `Feature` is not a valid type (use `feat`)
- `update readme` — missing type prefix
- `feat add thing` — missing colon after type
```

---

## 4. No Changes Needed

The following files are confirmed correct and must NOT be modified:

### `release-please-config.json`
```json
{
  "packages": {
    ".": {
      "release-type": "python",
      "package-name": "logai",
      "extra-files": [
        "src/logai/__init__.py"
      ]
    }
  }
}
```
- `release-type: python` is correct for this repo
- `package-name: logai` matches the project
- `extra-files` correctly includes the `__init__.py` for version stamping

### `.release-please-manifest.json`
```json
{
  ".": "0.1.0"
}
```
- Tracks the current released version. release-please updates this
  automatically when it creates a release. No manual edits needed.

### release-please step configuration
The step uses `googleapis/release-please-action@v4.4.0` with
`target-branch: main`. This is correct. The action reads
`release-please-config.json` and `.release-please-manifest.json`
automatically from the repo root. No additional `with:` parameters needed.

---

## 5. Post-Deployment Configuration (Manual Step)

After Jackie deploys these workflows, George or the repo admin should:

1. Go to **Settings > Branches > Branch protection rules** for `main`
2. Under "Require status checks to pass before merging", add:
   - `Validate PR title` (from the `pr-title-check.yml` workflow)
3. This ensures PRs with bad titles are actually blocked from merging

This is a GitHub UI setting, not a code change. Without it, the PR title
check runs but is advisory-only.

---

## 6. End-to-End Flow (Post-Implementation)

### Happy Path: Feature PR
```
Developer opens PR: "feat: add log streaming"
  → PR Title Check: PASS ✓
  → Developer merges PR to main (squash merge)
  → Push to main triggers release.yml
  → release-please creates Release PR: "chore(main): release logai 0.2.0"
  → auto-merge job sets --auto --squash on the Release PR
  → GitHub merges the Release PR
  → Push to main triggers release.yml again
  → release-please sees its PR was merged, creates GitHub Release v0.2.0
  → Done. Zero manual steps.
```

### Sad Path: Bad PR Title
```
Developer opens PR: "Fixed the login bug"
  → PR Title Check: FAIL ✗
  → Error message shows required format and examples
  → Developer edits title to: "fix(auth): resolve login failure"
  → PR Title Check: PASS ✓ (re-runs on edit)
  → Merge proceeds normally
```

### No-Release Path: Docs-Only Change
```
Developer opens PR: "docs: update API reference"
  → PR Title Check: PASS ✓
  → Developer merges to main
  → release-please runs, sees only docs commits, no version bump needed
  → No Release PR created, no release
```

---

## Implementation Checklist for Jackie

- [ ] Modify `.github/workflows/release.yml` — add `id: release`, `outputs` block, and `auto-merge` job (exact YAML in section 1)
- [ ] Create `.github/workflows/pr-title-check.yml` (exact YAML in section 2)
- [ ] Create `CONTRIBUTING.md` at repo root (content in section 3)
- [ ] Do NOT modify `release-please-config.json`
- [ ] Do NOT modify `.release-please-manifest.json`
- [ ] After merge: George configures branch protection to require `Validate PR title` check
