# Requirements: Structured Log Level Feature

**Date:** Feb 24, 2026
**Author:** George (TPM)
**Status:** Ready for Architecture

---

## User Requirements

### Log Levels
Implement standard LOGLEVEL-style logging with four severity levels:

| Level | Purpose |
|---|---|
| **ERROR** | Anything breaking or show-stopping |
| **WARNING** | Needs attention but not currently causing a problem (e.g. deprecation warnings) |
| **INFO** | All normal operational messages — what the app is doing in standard log format |
| **DEBUG** | Highest granularity — everything DEBUG currently shows plus anything that *might* help diagnose a future problem |

### Configuration
- **CLI flag:** `--loglevel DEBUG` (or INFO, WARNING, ERROR)
- **Environment variable:** `LOGAI_LOG_LEVEL=DEBUG` in `.env`
- **Precedence:** CLI flag overrides `.env` when they differ
- **Remove:** The existing `--debug` flag (replace entirely with `--loglevel`)

### Output
- **Log file only:** `~/.logai/logs/logai.log` (no console output — TUI must not be disrupted)

### Default Log Level
- **WARNING** (when no flag or env var is set)

---

## Current State (from Hans's investigation)

### Key Gap
`LOGAI_LOG_LEVEL` env var is already defined in `LogAISettings` and documented in `.env.example` but is **never actually read** by `setup_logging()` in `cli.py`. The settings field is dead code today.

### Current `setup_logging()` behavior (`src/logai/cli.py:20–61`)
- Takes `debug: bool` and `log_file: str | None`
- `level = logging.DEBUG if debug else logging.INFO`
- Creates `~/.logai/logs/logai.log` with `FileHandler`
- Calls `logging.basicConfig(level=level, format=..., handlers=handlers, force=True)`
- Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

### Current `--debug` CLI flag (`src/logai/cli.py:219–223`)
- `action="store_true"` argparse flag
- Passed to `setup_logging(debug=args.debug)`
- Must be **removed** entirely

### Settings (`src/logai/config/settings.py:314–323`)
```python
log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
log_file: Path | None = Field(default=None)
```
- `log_level` default should change to `"WARNING"`
- These fields need to be wired into `setup_logging()`

### All Application Loggers (17 modules — all `getLogger(__name__)`)
- `logai.cli`
- `logai.config.model_config`
- `logai.core.context.budget_tracker`
- `logai.core.context.result_cache`
- `logai.core.context.token_counter`
- `logai.core.log_group_manager`
- `logai.core.orchestrator`
- `logai.providers.llm.github_copilot_provider`
- `logai.providers.llm.litellm_provider`
- `logai.tools.fetch_cached_result`
- `logai.ui.app`
- `logai.ui.screens.chat`
- `logai.ui.screens.context_viewer`
- `logai.ui.screens.log_preview`
- `logai.ui.widgets.log_groups_sidebar`
- `logai.ui.widgets.status_footer`
- `logai.ui.widgets.tool_sidebar`

All propagate to root — a single root-level `basicConfig` controls all of them.

### Additional Notes
- `structlog` is a listed dependency but unused — design should decide if it's worth adopting
- No `setLevel()` calls exist anywhere — all level control is via `basicConfig` on root logger
- `[DIAGNOSTIC]`, `[FETCH_LOGS_DEBUG]` string prefixes are informal tags in orchestrator.py
- TUI constraint: **Never write to stdout/stderr** — Textual TUI will be corrupted
- LiteLLM loggers are explicitly suppressed in `litellm_provider.py` — design must preserve this

---

## Acceptance Criteria

1. `logai --loglevel DEBUG` sets log level to DEBUG
2. `logai --loglevel INFO` sets log level to INFO (etc. for WARNING, ERROR)
3. `LOGAI_LOG_LEVEL=DEBUG` in `.env` sets log level to DEBUG
4. CLI `--loglevel` takes precedence over `LOGAI_LOG_LEVEL` in `.env`
5. Default log level (no flag, no env var) is WARNING
6. `--debug` flag is **removed** — users get a clear error if they try to use it
7. Log output continues to go to `~/.logai/logs/logai.log` only
8. TUI display is not disrupted
9. Log entries at each level are appropriate and meaningful
10. All existing tests continue to pass
11. New tests cover the configuration / precedence behavior
