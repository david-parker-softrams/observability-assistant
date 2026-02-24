# Requirements: Fully Automated Release Process

**Date:** Feb 24, 2026
**Author:** George (TPM)
**Status:** Ready for Design

---

## Goal

Every merge to `main` should automatically produce a semver GitHub Release with
zero manual intervention, provided the PR title follows conventional commit format.

---

## Current State (from Hans's investigation)

### What exists
- `.github/workflows/release.yml` — triggers `googleapis/release-please-action@v4.4.0` on push to `main`
- `release-please-config.json` (repo root) — `release-type: python`, `package-name: logai`
- `.release-please-manifest.json` (repo root) — currently tracks `"." : "0.1.0"`
- Release PR #8 is currently open for `v0.2.0`

### What's broken
1. **No conventional commit enforcement** — PR #6 merged with `Fix ...` (no type prefix),
   release-please couldn't parse it and skipped the release entirely
2. **Release PR requires manual merge** — release-please only opens a Release PR;
   a human must merge it to actually cut the release

---

## Requirements

### R1: Auto-merge Release PRs
When release-please opens a Release PR (e.g. `chore(main): release logai 0.2.0`),
it must be **automatically merged** as soon as it is created (no CI blocking it,
since release-please only creates valid PRs). This makes the release fully hands-free.

Implementation approach: add a second job to `release.yml` that, after the
release-please step, auto-merges the release PR using `gh pr merge --auto --squash`
or the GitHub auto-merge API. The job should only run if a release PR was created.

### R2: Block PRs with Non-Conventional Commit Titles
Add a new GitHub Actions workflow (e.g. `.github/workflows/pr-title-check.yml`)
that runs on `pull_request` events and validates the PR title against the
conventional commit spec:

```
<type>[optional scope][optional !]: <description>
```

Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `revert`

The check must **fail (block merge)** if the title doesn't match.
It should print a helpful error message showing the required format and examples.

GitHub squash-merges use the PR title as the commit message, so enforcing the
PR title enforces the commit message on `main`.

### R3: Conventional Commit Reference Documentation
Add or update a `CONTRIBUTING.md` (or similar) documenting the required PR title
format so contributors know what is expected.

---

## Acceptance Criteria

1. A PR with title `feat: add new thing` merged to `main` → release-please creates
   a Release PR → Release PR is auto-merged → GitHub Release `vX.Y.Z` is published.
   All without any manual steps.
2. A PR with title `Fix something broken` → CI check fails, merge is blocked,
   developer sees a clear error message.
3. A PR with title `fix: correct the thing` → CI check passes, merge proceeds normally.
4. Existing `release.yml` continues to work as-is for the release-please step itself.
5. The new PR title check workflow runs on `pull_request` and `pull_request_target` events
   (to handle forks if needed).

---

## Semver Bump Rules (how release-please decides the version)

| Commit type | Version bump |
|---|---|
| `fix:`, `perf:` | PATCH (0.1.0 → 0.1.1) |
| `feat:` | MINOR (0.1.0 → 0.2.0) |
| `feat!:` or `BREAKING CHANGE:` footer | MAJOR (0.1.0 → 1.0.0) |
| `docs:`, `chore:`, `test:`, `ci:`, `style:`, `refactor:` | No release (changelog only, no version bump) |

These rules are built into release-please's `python` release type — no config needed.

---

## Notes / Constraints

- Do NOT modify `release-please-config.json` or `.release-please-manifest.json` —
  they are correct as-is
- The auto-merge job needs `pull-requests: write` permission (already granted in release.yml)
- The PR title check workflow needs no special permissions
- Must NOT break the existing workflow for non-release PRs
