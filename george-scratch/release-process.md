# Release Process Documentation

## Overview

This project uses **Release Please** to automate semantic versioning and changelog generation. Release Please creates pull requests based on your commit messages, following Conventional Commits standards.

## How It Works

### Automated Workflow

1. **You push commits** to `main` branch using conventional commit format
2. **Release Please analyzes** commits since the last release
3. **A Release PR is created** (or updated) automatically with:
   - Updated version number in `pyproject.toml`
   - Generated `CHANGELOG.md` entries
   - A GitHub release draft
4. **When you merge the Release PR**, a new GitHub release is published automatically

### Important Notes

- **Release PRs are NOT automatically merged** - you must manually review and merge them
- **Multiple commits accumulate** - Release Please will keep updating the same PR until you merge it
- **No packages are published** - We're only creating GitHub releases (PyPI publishing can be added later)

## Conventional Commits

Release Please uses **Conventional Commits** to determine version bumps and changelog entries.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Common Types

| Type | Description | Version Bump | Changelog Section |
|------|-------------|--------------|-------------------|
| `feat:` | New feature | **MINOR** (0.X.0) | Features |
| `fix:` | Bug fix | **PATCH** (0.0.X) | Bug Fixes |
| `docs:` | Documentation only | None | Documentation |
| `style:` | Code style changes | None | - |
| `refactor:` | Code refactoring | None | - |
| `perf:` | Performance improvements | **PATCH** (0.0.X) | Performance Improvements |
| `test:` | Adding/updating tests | None | - |
| `chore:` | Maintenance tasks | None | - |
| `ci:` | CI/CD changes | None | - |
| `build:` | Build system changes | None | - |

### Breaking Changes

To trigger a **MAJOR** version bump (X.0.0):

```bash
feat!: redesign configuration system

BREAKING CHANGE: Configuration file format has changed from JSON to YAML.
Users must migrate their config.json to config.yaml format.
```

**Two ways to mark breaking changes:**
1. Add `!` after the type: `feat!:` or `fix!:`
2. Include `BREAKING CHANGE:` in the commit footer

## Version Bumping Rules

Release Please follows **Semantic Versioning** (semver):

- **MAJOR (X.0.0)**: Breaking changes that require user action
- **MINOR (0.X.0)**: New features that are backward-compatible
- **PATCH (0.0.X)**: Bug fixes and improvements

### Examples

```bash
# Patch Release (0.0.1 → 0.0.2)
git commit -m "fix: resolve crash when log group is empty"

# Minor Release (0.0.1 → 0.1.0)
git commit -m "feat: add support for CloudWatch Insights queries"

# Major Release (0.1.0 → 1.0.0)
git commit -m "feat!: redesign API for log queries

BREAKING CHANGE: LogQuery class constructor now requires region parameter."
```

## Example Workflow

### Scenario: Adding a New Feature

1. **Create your feature branch and make changes**
   ```bash
   git checkout -b feature/streaming-logs
   # ... make changes ...
   ```

2. **Commit using conventional format**
   ```bash
   git add .
   git commit -m "feat: add real-time log streaming capability

   Implements WebSocket-based streaming for live log updates.
   Users can now see logs as they arrive in real-time."
   ```

3. **Push and merge to main**
   ```bash
   git push origin feature/streaming-logs
   # Create PR, get approval, merge to main
   ```

4. **Release Please detects the change**
   - After merge, the GitHub Action runs
   - Release Please creates/updates a PR titled: `chore(main): release 0.1.0`
   - The PR includes:
     - Version bump in `pyproject.toml` (0.0.1 → 0.1.0)
     - CHANGELOG.md entry with your feature
     - Release notes

5. **Review and merge the Release PR**
   - Review the generated changelog
   - Verify version number is correct
   - Merge the Release PR
   - GitHub release is automatically published

## Best Practices

### DO ✅

- **Use conventional commits consistently**
  ```bash
  git commit -m "feat: add user authentication"
  git commit -m "fix: correct timezone handling in log queries"
  git commit -m "docs: update API documentation for log filters"
  ```

- **Include scope for clarity** (optional but helpful)
  ```bash
  git commit -m "feat(ui): add dark mode toggle"
  git commit -m "fix(auth): resolve token refresh issue"
  git commit -m "test(integration): add CloudWatch mock tests"
  ```

- **Write descriptive commit bodies for complex changes**
  ```bash
  git commit -m "feat: implement caching layer for log queries

  Adds an in-memory LRU cache to reduce repeated CloudWatch API calls.
  Cache size is configurable via LOGAI_CACHE_SIZE environment variable.
  Default cache size is 100 queries."
  ```

- **Group related changes**
  - Make multiple small, focused commits
  - Each commit should be a logical unit of change

### DON'T ❌

- **Don't use vague messages**
  ```bash
  # Bad
  git commit -m "update stuff"
  git commit -m "fixes"
  git commit -m "wip"

  # Good
  git commit -m "fix: resolve memory leak in log streaming"
  ```

- **Don't mix concerns in one commit**
  ```bash
  # Bad - two separate concerns
  git commit -m "feat: add export feature and fix login bug"

  # Good - separate commits
  git commit -m "feat: add CSV export for log results"
  git commit -m "fix: resolve session timeout on login"
  ```

- **Don't manually edit version numbers**
  - Let Release Please manage `pyproject.toml` version
  - Never commit version bumps manually

## Troubleshooting

### "My commit didn't trigger a release PR"

- Check if you used a type that triggers releases: `feat:`, `fix:`, or breaking changes
- Types like `docs:`, `chore:`, `style:` don't trigger releases
- The GitHub Action only runs on pushes to `main` branch

### "I need to fix something in the Release PR"

- You can continue making commits to `main`
- Release Please will automatically update the existing Release PR
- The PR accumulates all changes until you merge it

### "I made a mistake in my commit message"

**If not yet pushed to main:**
```bash
git commit --amend -m "feat: correct commit message"
```

**If already pushed to main:**
- Make a new commit with the correct type
- Or wait for the release PR and edit the CHANGELOG manually if needed

### "I want to skip a release"

- Simply don't merge the Release PR
- Keep making commits, they'll accumulate in the same PR
- Merge when ready to release all accumulated changes

## Manual Release (Emergency)

If you need to create a release manually:

1. **Update version in both files**
   ```toml
   # pyproject.toml
   [project]
   version = "0.1.0"
   ```

   ```python
   # src/logai/__init__.py
   __version__ = "0.1.0"
   ```

   **Note**: With Release Please configured via `.release-please-config.json`, automated releases will update both files automatically. Manual updates are only needed for emergency releases outside the normal workflow.

2. **Update CHANGELOG.md** with your changes

3. **Create a git tag**
   ```bash
   git add pyproject.toml src/logai/__init__.py CHANGELOG.md
   git commit -m "chore: release 0.1.0"
   git tag v0.1.0
   git push origin main --tags
   ```

4. **Create GitHub release** using the web UI or `gh` CLI

## Current Version

**Current Version**: `0.0.1`

This is our starting version. The first feature commit will bump us to `0.1.0`.

## Future Enhancements

When ready, we can add:
- **Automated PyPI publishing** after release
- **Docker image building and publishing**
- **Release notes customization**
- **Multiple package releases** (if we split into multiple packages)
- **Slack/Discord notifications** for new releases

## References

- [Release Please Documentation](https://github.com/googleapis/release-please)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)

## Questions?

If you have questions about the release process:
1. Review this documentation
2. Check existing Release PRs for examples
3. Ask in team chat
4. Review the [Release Please documentation](https://github.com/googleapis/release-please/tree/main/docs)
