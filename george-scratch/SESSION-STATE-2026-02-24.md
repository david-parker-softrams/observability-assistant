# Session State — 2026-02-24

## Project Overview

**LogAI** — Python-based LLM observability assistant with a Textual TUI.

---

## Team

| Name | Role | Agent Type |
|------|------|------------|
| George | TPM (me) | — |
| Saanvi | Senior Software Architect | software-architect |
| Jackie | Senior Software Engineer | software-engineer |
| Han-Ron | Expert Code Reviewer | code-reviewer |
| Raoul | QA Engineer | qa-engineer |
| Tina | Technical Writer | technical-writer |
| Hans | Code Librarian / Explorer | librarian |

---

## Workflow Rules

- **Hans investigates → Saanvi designs → Jackie implements → Raoul tests → Han-Ron reviews → George merges**
- All PRs use **squash merge** with `--delete-branch`
- Always wait for Copilot review; address any findings before merging
- If Han-Ron gives HIGH confidence and Copilot has no findings → merge
- If MEDIUM confidence → fix blockers first
- Commit messages follow **conventional commits** (`feat:`, `fix:`, `chore:`, `docs:`, `ci:`, etc.)
- PR title = commit message on main (squash merge) — enforced by CI (`pr-title-check.yml`)
- **Never write to stdout/stderr** — Textual TUI will be corrupted. Log to file only: `~/.logai/logs/logai.log`

---

## Current State

### Version
- Current release: **v0.2.1**
- `.release-please-manifest.json` tracks `"." : "0.2.1"`

### Test Suite
- Run: `python -m pytest tests/unit/ -q --ignore=tests/unit/benchmarks`
- **982 tests passing**
- 8 pre-existing benchmark errors (`pytest-benchmark` not installed) — normal and expected

### Known Pre-existing LSP Errors (do not fix)
- `tests/unit/core/test_orchestrator_context.py:812` — `_pending_cache_guidance` attribute unknown
- `src/logai/ui/screens/chat.py:360` — `datasource` attribute unknown on `BaseTool`
- Several generator return type errors in `tests/unit/test_cli.py`

---

## Completed Work (this project lifetime)

### PR #6 — Fix context window exhaustion (merged to main)
- Removed `fetch_logs` bypass rule that prevented caching, restoring context window protection (94% token savings)
- Strengthened system prompt to force LLM to call `fetch_cached_result_chunk` immediately
- Fixed all Han-Ron review findings

### PR #7 — Structured log level system (merged to main → triggered v0.2.0 release)
- Replaced `--debug` boolean flag with `--loglevel DEBUG|INFO|WARNING|ERROR`
- CLI flag takes precedence over `LOGAI_LOG_LEVEL` env var, which takes precedence over default (`WARNING`)
- 60 new tests in `tests/unit/test_logging_setup.py`
- Removed all `[DIAGNOSTIC]`/`[FETCH_LOGS_DEBUG]`/`[CONTEXT_DEBUG]` bracket tags from orchestrator
- Demoted ~20 over-verbose `logger.info` calls to `logger.debug`

### PR #8 — v0.2.0 release (manually merged by user)
- Release-please's auto-generated release PR

### PR #9 — Release automation (merged to main)
- Added auto-merge of release-please Release PRs to `release.yml`
- Added `pr-title-check.yml` to enforce conventional commit PR titles
- Added `CONTRIBUTING.md` documenting format, types, semver rules

### PR #10 — Remove startup tip popup (merged to main → triggered v0.2.1 release)
- Removed 7-line `self.notify(...)` block from `on_mount` in `src/logai/ui/screens/chat.py`

### PR #11 — v0.2.1 release (auto-merged by pipeline)
- First successful end-to-end automated release — pipeline confirmed working

---

## Pending Items

### ⏳ Manual Step Required (by David)
- **Add `Validate PR title` as a required status check** in branch protection for `main`
- **Where:** GitHub → Settings → Branches → Branch protection rules → `main` → "Require status checks to pass before merging" → search for `Validate PR title`
- The check has fired (ran on PR #10's branch), so the name should appear in the dropdown

---

## Key Files / Directories

### Core Application
| File | Purpose |
|------|---------|
| `src/logai/cli.py` | Entry point, `setup_logging()`, `--loglevel` flag, `DeprecatedDebugAction` |
| `src/logai/__main__.py` | `python -m logai` entry point |
| `src/logai/config/settings.py` | `LogAISettings` (Pydantic), `log_level` default=`"WARNING"`, `LOGAI_` env prefix |
| `src/logai/core/orchestrator.py` | Main LLM orchestrator, caching logic, `ActiveCacheContext`, `_prune_history_if_needed`, `_chat_complete`, `_chat_stream`, `_process_tool_result`, `_log_tool_call_diagnostic` |
| `src/logai/core/context/result_cache.py` | `ResultCacheManager`, `CachedResultSummary`, `_sample_events`, `_select_time_diverse` |
| `src/logai/ui/screens/chat.py` | `ChatScreen`, `on_mount` (tip popup removed) |
| `src/logai/providers/llm/litellm_provider.py` | LiteLLM logger suppression — **do not touch** |

### CI / Release
| File | Purpose |
|------|---------|
| `.github/workflows/release.yml` | Release Please + auto-merge job |
| `.github/workflows/pr-title-check.yml` | PR title conventional commit enforcement |
| `release-please-config.json` | `release-type: python`, `package-name: logai` |
| `.release-please-manifest.json` | Currently `"." : "0.2.1"` |
| `CONTRIBUTING.md` | PR title format documentation |

### Tests
| File | Purpose |
|------|---------|
| `tests/unit/test_logging_setup.py` | 60 new tests for log level system |
| `tests/unit/test_cli.py` | CLI argument and logging setup tests |
| `tests/unit/core/test_orchestrator_context.py` | Orchestrator context/caching tests |
| `tests/unit/core/context/test_result_cache.py` | ResultCacheManager tests |
| `tests/unit/test_settings.py` | Settings defaults tests |

### Design / Scratch Docs
| File | Purpose |
|------|---------|
| `docs/design/structured-log-level-design.md` | Saanvi's design doc for log level feature |
| `george-scratch/design-release-automation.md` | Release automation design |
| `george-scratch/requirements-loglevel-feature.md` | Log level requirements |
| `george-scratch/requirements-release-automation.md` | Release automation requirements |
| `george-scratch/han-ron-review-pr6.md` | Han-Ron's review findings for PR #6 |
| `.env.example` | Documents `LOGAI_LOG_LEVEL`, `LOGAI_LOG_FILE`, correct log path `~/.logai/logs/logai.log` |

---

## Architecture Notes

### Caching System
- `ResultCacheManager` in `src/logai/core/context/result_cache.py`
- `ActiveCacheContext` dataclass tracks active cache state per request
- `fetch_cached_result_chunk` tool is how the LLM retrieves full cached data
- 94% token savings when caching is working correctly

### Logging System
- All 17 app modules use `logging.getLogger(__name__)` — all propagate to root
- Root logger controlled via single `basicConfig` call in `setup_logging()` in `src/logai/cli.py`
- `structlog` listed as dependency but intentionally NOT used — keep stdlib logging
- `LOGAI_LOG_LEVEL` env var wired through `setup_logging()`
- Default log level: `WARNING`
- LiteLLM loggers explicitly suppressed in `litellm_provider.py` — must be preserved

### Release Pipeline
- `release-please` uses conventional commits: `feat:` = minor bump, `fix:`/`perf:` = patch, breaking = major, `docs:`/`chore:`/`test:`/`ci:` = no bump
- Auto-merge only fires on Release PRs (created by release-please), NOT feature PRs
- `amannn/action-semantic-pull-request` pinned to immutable SHA for supply-chain safety
