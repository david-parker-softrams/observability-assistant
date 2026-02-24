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
