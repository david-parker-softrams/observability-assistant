# Branch Protection Recommendation: `main`

**Repository:** `david-parker-softrams/observability-assistant`
**Date:** 2026-02-25
**Author:** Tina (Technical Writer)
**Status:** Recommendation — pending team approval

---

## 1. Why This Matters

We switched to feature branches on 2026-02-23, but nothing in GitHub currently
*enforces* that policy. Anyone on the team can still push directly to `main` —
intentionally or by accident. That creates four concrete risks:

| Risk | What can go wrong |
|---|---|
| **Accidental breakage** | An untested commit goes straight to `main`, breaking the app or CI for everyone. |
| **No review gate** | Code with bugs, security issues, or design problems lands without a second set of eyes. |
| **CI checks bypassed** | Ruff, mypy, and the PR title check run on PRs — a direct push skips all of them. |
| **No audit trail** | There's no recorded approval, no linked issue, and no squash commit message, making `git log` on `main` noisy and hard to reason about. |

Branch protection rules solve all four problems at the GitHub level — they're
enforced regardless of which tool or workflow a team member uses.

---

## 2. Recommended Branch Protection Rules for `main`

### 2.1 Require a pull request before merging

- **Require pull request reviews before merging**: ✅ enabled
- **Required approvals**: `1`
- **Dismiss stale pull request approvals when new commits are pushed**: ✅ enabled

> This ensures that every change to `main` has been seen and approved by at
> least one other team member. Enabling stale-review dismissal means a new
> push can't sneak past an existing approval.

---

### 2.2 Require status checks to pass before merging

- **Require status checks to pass before merging**: ✅ enabled
- **Require branches to be up to date before merging**: ✅ enabled

**Required checks:**

| Check name | Source | Status | What it validates |
|---|---|---|---|
| `Validate PR title` | `pr-title-check.yml` (GitHub Actions) | ✅ Ready to use now | PR title follows Conventional Commits format (required for `release-please` versioning) |
| `ruff` | Pre-commit hook (local only) | ⚠️ CI workflow needed | Python linting — catches code errors and style issues |
| `ruff-format` | Pre-commit hook (local only) | ⚠️ CI workflow needed | Python formatting — enforces consistent code style |
| `mypy` | Pre-commit hook (local only) | ⚠️ CI workflow needed | Static type checking on `src/` |

> **Note:** `ruff`, `ruff-format`, and `mypy` currently run only as local
> pre-commit hooks. They are **not** yet executed by a GitHub Actions workflow,
> so they do not produce GitHub status checks and cannot be added as required
> checks in branch protection until a CI workflow is created to run them on
> pull requests. `Validate PR title` is the only check that is ready to
> configure today.

> Requiring the branch to be up to date means a PR cannot be merged if `main`
> has moved ahead since the branch was created. This prevents integration bugs
> from sneaking in.

---

### 2.3 Block direct pushes to `main`

- **Restrict who can push to matching branches**: ✅ enabled (no exceptions)
- **Allow force pushes**: ❌ disabled
- **Allow deletions**: ❌ disabled

> Direct pushes to `main` bypass all of the above. Disabling them is the
> single most important rule.

---

### 2.4 Do not allow bypassing the rules (recommended)

- **Do not allow bypassing the above settings**: ✅ enabled

> By default, GitHub repository admins can bypass branch protection rules.
> Enabling this option means the rules apply to *everyone*, including admins.
> Strongly recommended — "I'm an admin" is not a good reason to skip a review.

---

## 3. Recommended Workflow

With branch protection in place, the day-to-day workflow is:

### Branch naming convention

```
<type>/<short-description>
```

Use the same types as the PR title convention:

| Prefix | When to use |
|---|---|
| `feat/` | New feature or enhancement |
| `fix/` | Bug fix |
| `refactor/` | Code restructuring with no behavior change |
| `docs/` | Documentation only |
| `test/` | Adding or updating tests |
| `chore/` | Maintenance, dependency updates, tooling |
| `hotfix/` | Critical production fix (merge as fast as possible) — use `fix:` (or another valid type) as the PR title prefix, not `hotfix:` |

**Examples:** `feat/export-logs-to-csv`, `fix/chat-scroll-position`, `chore/update-dependencies`

---

### Step-by-step

```bash
# 1. Start from an up-to-date main
git checkout main
git pull origin main

# 2. Create your branch
git checkout -b feat/my-new-feature

# 3. Do your work, commit normally
git add <files>
git commit -m "feat: describe your change"

# 4. Push the branch and open a PR
git push -u origin feat/my-new-feature
gh pr create --title "feat: describe your change" --body "..."

# 5. Wait for CI checks to pass and get 1 approval

# 6. Merge via the GitHub UI (squash merge recommended)
#    release-please uses the squash commit message for versioning

# 7. Clean up
git checkout main
git pull origin main
git branch -d feat/my-new-feature
```

> **PR title is the commit message.** Because we use squash merge, the PR
> title becomes the single commit on `main`. It must follow the
> `<type>: <description>` format — CI enforces this via the
> `Validate PR title` check.

---

## 4. How to Configure It in GitHub

> **Required permission:** Repository admin.

1. Go to the repository on GitHub:
   `https://github.com/david-parker-softrams/observability-assistant`

2. Click **Settings** (top navigation bar).

3. In the left sidebar, click **Branches** (under *Code and automation*).

4. Under *Branch protection rules*, click **Add branch protection rule** (or
   **Edit** if a rule for `main` already exists).

5. In the **Branch name pattern** field, enter:
   ```
   main
   ```

6. Enable the following options:

   - [x] **Require a pull request before merging**
     - Set *Required number of approvals before merging* to `1`
     - [x] Dismiss stale pull request approvals when new commits are pushed

   - [x] **Require status checks to pass before merging**
     - [x] Require branches to be up to date before merging
      - In the search box, add each required check by name:
        - `Validate PR title`
        - `ruff` *(only after a CI workflow has been created — see note below)*
        - `ruff-format` *(only after a CI workflow has been created — see note below)*
        - `mypy` *(only after a CI workflow has been created — see note below)*

     > **Note:** A check only appears in the search box after a GitHub Actions
     > workflow has run it at least once on a PR and reported a status check
     > back to GitHub. `Validate PR title` is available immediately. `ruff`,
     > `ruff-format`, and `mypy` currently run only as local pre-commit hooks
     > and will **not** appear in the search box — even after opening a draft
     > PR — until CI workflows are created to run them on pull requests.

   - [x] **Restrict who can push to matching branches**
     *(Leave the "who can push" list empty — GitHub will then block direct pushes by everyone, including admins, with no exceptions.)*

   - [x] **Allow force pushes** — leave **unchecked** (disabled)

   - [x] **Allow deletions** — leave **unchecked** (disabled)

   - Depending on your repository's GitHub plan and settings, you will see
     **one** of the following options — enable it either way:
     - [x] **Do not allow bypassing the above settings** — enable this *(applies rules to admins too)*
     - **Allow specified actors to bypass required pull requests** — leave the
       actors list **empty** *(an empty list means no one can bypass)*

7. Click **Create** (or **Save changes**).

---

## 5. Impact on Existing Workflows

| Workflow | Impact |
|---|---|
| `release.yml` (Release Please) | ⚠️ Partial — Release Please merges its own PR via `gh pr merge --auto`, which goes through the normal PR flow. Auto-merge will work once CI workflows exist for all required checks. Until then, if `ruff`, `ruff-format`, or `mypy` have been added as required checks before their CI workflows exist, Release Please PRs will be blocked and must be merged manually. |
| `pr-title-check.yml` | Becomes a *blocking* required check instead of advisory. No change to the workflow file itself. |
| Agent team members (Jackie, Raoul, Tina, etc.) | Must push to feature branches and open PRs. Direct commits to `main` will be rejected. |
| Hotfixes | Use a `hotfix/` branch + PR. A single reviewer can approve immediately to keep the turnaround fast. |

---

## 6. Summary

Enabling these four rules costs the team nothing in speed — PRs are already our
documented workflow — but they close the gap between *policy* and *enforcement*:

1. **Require PR + 1 approval** — human review on every change
2. **Require CI checks to pass** — `Validate PR title`, `ruff`, `ruff-format`, `mypy`
3. **Require branch to be up to date** — no silent integration bugs
4. **Block direct pushes and bypasses** — policy is enforced, not just documented
