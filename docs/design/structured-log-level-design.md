# Design Document: Structured Log Level Feature

**Author:** Saanvi (Senior Software Architect)
**Date:** February 24, 2026
**Status:** Ready for Implementation
**Audience:** Implementing Engineer

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [`setup_logging()` Redesign](#2-setup_logging-redesign)
3. [CLI Changes](#3-cli-changes)
4. [Settings Changes](#4-settings-changes)
5. [`.env.example` Updates](#5-envexample-updates)
6. [Precedence Logic](#6-precedence-logic)
7. [Log Level Guidance Per Module](#7-log-level-guidance-per-module)
8. [`structlog` Decision](#8-structlog-decision)
9. [`[DIAGNOSTIC]` Tag Handling](#9-diagnostic-tag-handling)
10. [Test Strategy](#10-test-strategy)
11. [Migration Notes](#11-migration-notes)

---

## 1. Architecture Overview

### Current State

The logging system today is a simple two-state toggle: `--debug` gives you `logging.DEBUG`, absence of `--debug` gives you `logging.INFO`. The `LOGAI_LOG_LEVEL` field exists in `LogAISettings` (settings.py:315) but is dead code — `setup_logging()` never reads it. All 16 module-level loggers (plus one inline in `log_group_manager.py`) use `getLogger(__name__)` and propagate to the root logger configured by `basicConfig`.

### Target State

```
┌─────────────────────────────────────────────────────────────────┐
│                    Log Level Resolution                         │
│                                                                 │
│   CLI --loglevel     ─┐                                         │
│                       ├─► resolve_log_level() ─► setup_logging()│
│   .env LOGAI_LOG_LEVEL┘          │                    │         │
│                          (CLI wins if set)             │         │
│   Default: WARNING ──────────────┘                    ▼         │
│                                              Root Logger        │
│                                              level=RESOLVED     │
│                                              handler=FileHandler│
│                                              file=~/.logai/logs/│
│                                                    logai.log    │
│                                                    │            │
│                                     ┌──────────────┼───────┐    │
│                                     ▼              ▼       ▼    │
│                               orchestrator    chat.py   ...16   │
│                               (getLogger)   (getLogger) modules │
│                                                                 │
│   LiteLLM loggers: handlers cleared, propagate=True (preserved) │
└─────────────────────────────────────────────────────────────────┘
```

The design is intentionally conservative:
- **No new logging framework** (stay with stdlib `logging` — see §8)
- **No per-module level overrides** (all modules inherit from root)
- **No console output** (file-only, preserving TUI integrity)
- **Single point of configuration** (`setup_logging()` in `cli.py`)

### Data Flow

1. User runs `logai --loglevel DEBUG` or sets `LOGAI_LOG_LEVEL=DEBUG` in `.env`
2. `main()` parses CLI args → gets `args.loglevel` (string or `None`)
3. `main()` loads `settings = get_settings()` → `settings.log_level` reflects `.env`
4. `main()` calls `setup_logging(cli_level=args.loglevel, settings=settings)`
5. `setup_logging()` resolves final level: CLI > settings (.env) > default (WARNING)
6. Root logger configured with resolved level and `FileHandler`
7. All 17 module loggers inherit via propagation — no changes needed in modules

---

## 2. `setup_logging()` Redesign

### Current Signature
```python
def setup_logging(debug: bool = False, log_file: str | None = None) -> None:
```

### New Signature
```python
def setup_logging(
    cli_level: str | None = None,
    settings: LogAISettings | None = None,
    log_file: str | None = None,
) -> None:
```

### Complete New Implementation

```python
# Valid log levels for validation
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

# Default log level when nothing is configured
DEFAULT_LOG_LEVEL = "WARNING"


def setup_logging(
    cli_level: str | None = None,
    settings: LogAISettings | None = None,
    log_file: str | None = None,
) -> None:
    """
    Configure application logging.

    Precedence (highest to lowest):
        1. cli_level (from --loglevel flag)
        2. settings.log_level (from LOGAI_LOG_LEVEL env var / .env file)
        3. DEFAULT_LOG_LEVEL ("WARNING")

    Args:
        cli_level: Log level from CLI flag (e.g., "DEBUG", "INFO").
                   None means CLI flag was not provided.
        settings: Application settings instance. If None, only cli_level
                  and DEFAULT_LOG_LEVEL are considered.
        log_file: Path to log file. Defaults to ~/.logai/logs/logai.log.
    """
    # --- Resolve effective log level ---
    effective_level_name: str
    level_source: str

    if cli_level is not None:
        # CLI flag takes highest precedence
        effective_level_name = cli_level.upper()
        level_source = "CLI --loglevel"
    elif settings is not None and settings.log_level != DEFAULT_LOG_LEVEL:
        # Settings (.env) takes second precedence, but only if it differs
        # from the default. Note: if settings.log_level is "WARNING" (the
        # new default), we can't distinguish "user explicitly set WARNING"
        # from "no env var set". This is acceptable — the result is correct
        # either way.
        effective_level_name = settings.log_level
        level_source = "LOGAI_LOG_LEVEL env var"
    elif settings is not None:
        # Settings exist but log_level is at default
        effective_level_name = settings.log_level
        level_source = "default"
    else:
        effective_level_name = DEFAULT_LOG_LEVEL
        level_source = "default"

    # Validate the resolved level
    if effective_level_name not in VALID_LOG_LEVELS:
        # Fall back to default rather than crashing
        print(
            f"⚠️  Warning: Invalid log level '{effective_level_name}', "
            f"falling back to {DEFAULT_LOG_LEVEL}",
            file=sys.stderr,
        )
        effective_level_name = DEFAULT_LOG_LEVEL
        level_source = "default (fallback)"

    level = getattr(logging, effective_level_name)

    # --- Set up file handler ---
    handlers: list[logging.Handler] = []

    try:
        if log_file is None:
            # Use settings.log_file if available, otherwise default path
            if settings is not None and settings.log_file is not None:
                log_file = str(settings.log_file)
            else:
                log_dir = Path.home() / ".logai" / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = str(log_dir / "logai.log")
        else:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = str(log_path)

        handlers.append(logging.FileHandler(log_file))
    except (PermissionError, OSError) as e:
        print(f"⚠️  Warning: Could not create log file: {e}", file=sys.stderr)
        print("   Logging to console only", file=sys.stderr)
        log_file = None
        # Fallback to console ONLY when file fails — this is the
        # emergency path. Under normal operation, nothing goes to console.
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    logger = logging.getLogger(__name__)
    if log_file:
        logger.info(
            f"Logging initialized: level={effective_level_name} "
            f"(source={level_source}), file={log_file}"
        )
    else:
        logger.info(
            f"Logging initialized: level={effective_level_name} "
            f"(source={level_source}), console only"
        )
```

### Key Design Decisions

1. **`settings` parameter instead of reading env directly:** The function receives the already-loaded `LogAISettings` object. This avoids duplicate .env parsing and keeps precedence logic testable.

2. **`cli_level` is a string, not an enum:** argparse `choices` already validates the value. Passing a string keeps the interface simple.

3. **Validation with graceful fallback:** If somehow an invalid level gets through, we fall back to WARNING rather than crashing.

4. **`settings.log_file` is wired in:** The existing `log_file` field in settings was also dead code. Now it's used as a secondary source for log file path, after the `log_file` parameter (CLI `--log-file`), before the default path.

---

## 3. CLI Changes

### Remove `--debug` Flag

Delete lines 219–223 in `cli.py`:

```python
# DELETE THIS BLOCK
parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug logging (default: INFO level)",
)
```

### Add `--loglevel` Flag

Add in the same location:

```python
parser.add_argument(
    "--loglevel",
    type=str.upper,          # Normalize to uppercase
    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    default=None,            # None means "not provided via CLI"
    help="Set log level (default: WARNING). Overrides LOGAI_LOG_LEVEL env var.",
    metavar="LEVEL",
)
```

**Details:**
- `type=str.upper` normalizes input so `--loglevel debug` works the same as `--loglevel DEBUG`.
- `default=None` is crucial: it lets `setup_logging()` distinguish "user didn't pass the flag" from "user passed WARNING". This is essential for the precedence logic.
- `choices` provides built-in validation and auto-generated help text.
- `metavar="LEVEL"` gives clean help output: `--loglevel LEVEL`.

### Add `--debug` Deprecation Error

To give a clear error when users try the old `--debug` flag, add a **custom action** before the argparse block:

```python
class DeprecatedDebugAction(argparse.Action):
    """Custom action that errors when --debug is used."""

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(
            "The --debug flag has been removed. "
            "Use --loglevel DEBUG instead."
        )
```

Then register it:

```python
parser.add_argument(
    "--debug",
    nargs=0,
    action=DeprecatedDebugAction,
    help=argparse.SUPPRESS,  # Hide from --help output
)
```

This gives users a clear, actionable error message:

```
logai: error: The --debug flag has been removed. Use --loglevel DEBUG instead.
```

### Update `setup_logging()` Call Site

Change line 261:

```python
# OLD
setup_logging(debug=args.debug, log_file=args.log_file)

# NEW
setup_logging(cli_level=args.loglevel, settings=settings, log_file=args.log_file)
```

**IMPORTANT:** This call must be moved to AFTER `settings = get_settings()` succeeds, because `setup_logging()` now accepts the settings object. However, we also want logging available as early as possible. The solution:

```python
# Parse arguments
args = parser.parse_args()

# Load settings first (needed for log level resolution)
try:
    settings = get_settings()
except Exception:
    settings = None  # Will fall back to CLI level or default

# Setup logging (uses settings if available for log_level from .env)
setup_logging(cli_level=args.loglevel, settings=settings, log_file=args.log_file)

# Now validate settings (logging is ready for error reporting)
if settings is None:
    # Settings failed to load entirely — this is fatal
    print("❌ Failed to load configuration", file=sys.stderr)
    return 1

try:
    # Override AWS settings from CLI...
    if args.aws_profile is not None:
        settings.aws_profile = args.aws_profile
    # ... rest of existing validation code
```

This reordering ensures:
1. Settings are loaded first (so `.env` log level is available)
2. Logging is set up second (with full precedence resolution)
3. Settings validation happens third (with logging available for error reporting)

### Update Help Text / Epilog

In the parser epilog `Environment Variables:` section, add:

```
  LOGAI_LOG_LEVEL                 # Log level: DEBUG, INFO, WARNING, ERROR (default: WARNING)
```

And update the Examples section:

```
  logai --loglevel DEBUG                     # Enable debug logging
  logai --loglevel INFO                      # Standard operational logging
```

---

## 4. Settings Changes

### Change Default Log Level

In `settings.py`, change line 315:

```python
# OLD
log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
    default="INFO",
    description="Application log level",
)

# NEW
log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
    default="WARNING",
    description="Application log level (DEBUG, INFO, WARNING, ERROR)",
)
```

### No Other Settings Changes Required

- The `log_file` field (line 320–323) is fine as-is — it already supports `Path | None` with `None` default.
- The `LOGAI_` env prefix in `SettingsConfigDict` already maps `LOGAI_LOG_LEVEL` → `log_level`. This is working as designed; it was just never consumed.
- No new settings fields are needed.

---

## 5. `.env.example` Updates

Replace the Logging Configuration section (lines 103–108):

```bash
# === Logging Configuration ===
# Log level: DEBUG, INFO, WARNING, ERROR (default: WARNING)
# Can be overridden at runtime with: logai --loglevel DEBUG
LOGAI_LOG_LEVEL=WARNING

# Log file location (default: ~/.logai/logs/logai.log)
# All log output goes to file only — console/TUI is never disrupted.
# LOGAI_LOG_FILE=~/.logai/logs/logai.log
```

**Changes from current:**
1. Default changed from `INFO` to `WARNING`
2. Comment now mentions `--loglevel` CLI override
3. Comment clarifies file-only logging (TUI safety)
4. Removed misleading "defaults to stderr only" comment on `LOGAI_LOG_FILE`

---

## 6. Precedence Logic

### Algorithm (pseudocode)

```
function resolve_log_level(cli_level, settings):
    if cli_level is not None:           # User passed --loglevel
        return cli_level, "CLI"

    if settings is not None:
        return settings.log_level, "env var / .env"

    return "WARNING", "default"         # Absolute fallback
```

### Precedence Table

| CLI `--loglevel` | `.env` `LOGAI_LOG_LEVEL` | Effective Level | Source |
|---|---|---|---|
| `DEBUG` | `INFO` | **DEBUG** | CLI |
| `DEBUG` | _(not set)_ | **DEBUG** | CLI |
| _(not set)_ | `DEBUG` | **DEBUG** | .env |
| _(not set)_ | `INFO` | **INFO** | .env |
| _(not set)_ | _(not set)_ | **WARNING** | default |
| `ERROR` | `DEBUG` | **ERROR** | CLI |
| `WARNING` | `DEBUG` | **WARNING** | CLI |

### Edge Cases

- **Invalid level in `.env`:** Pydantic's `Literal` validator will reject it at settings load time, before `setup_logging()` is called. The user sees a clear Pydantic validation error.
- **Invalid level via CLI:** argparse `choices` rejects it before `main()` even runs. The user sees: `error: argument --loglevel: invalid choice: 'TRACE'`
- **Settings fail to load:** If `get_settings()` throws (e.g., malformed `.env`), we pass `settings=None` to `setup_logging()`, which falls back to `cli_level` or `DEFAULT_LOG_LEVEL`.

---

## 7. Log Level Guidance Per Module

This is the most important section for the implementing engineer. Below is specific guidance for each module that has a logger. **The engineer does NOT need to modify most log statements** — the current calls are largely at appropriate levels. However, some calls are currently at the wrong level (especially the `logger.info` calls with `[CONTEXT_DEBUG]` tags, which should be `logger.debug`). Those specific changes are called out.

### 7.1 `core/orchestrator.py` (logger: `logai.core.orchestrator`)

This is the most log-heavy module (65+ log calls). It needs the most attention.

| Level | What to log | Examples |
|---|---|---|
| **ERROR** | Failures that break the current operation | `Failed to cache result` (line 863), `Context exhausted` |
| **WARNING** | Recoverable issues, limits reached | `Context budget critically low` (line 1090), `Emergency pruning triggered` (line 1120), `Fetch limit exceeded` (line 2001), `Tool listener error` (line 502), `Error in self-direction logic, continuing` (line 1613) |
| **INFO** | Key operational milestones | `LLM Orchestrator initialized` (line 447), `Result cached with enhanced summary` (line 823), `History pruned: N messages` (line 998), `Emergency pruning complete` (line 1194), `Injecting retry prompt` (line 1507), `Detected intent without action` (line 1564), `Applying exponential backoff before retry` (line 1483) |
| **DEBUG** | All diagnostic/tracing detail | ALL `[DIAGNOSTIC]` and `[FETCH_LOGS_DEBUG]` tagged messages, `[CONTEXT_DEBUG]` tagged messages, budget status logging, mid-loop budget checks, message content previews, cache decision details, tool result processing details |

**Specific changes required in this module:**

| Current | Line(s) | Change To | Reason |
|---|---|---|---|
| `logger.info("[CONTEXT_DEBUG] Orchestrator stored context...")` | 515 | `logger.debug(...)` | Diagnostic tracing, not operational milestone |
| `logger.info("[CONTEXT_DEBUG] Orchestrator retrieved context...")` | 528 | `logger.debug(...)` | Diagnostic tracing |
| `logger.info("[CONTEXT_DEBUG] Sending N messages to LLM")` | 1370, 1693 | `logger.debug(...)` | Per-call tracing detail |
| `logger.info("[CONTEXT_DEBUG] Message N: role=...")` | 1373–1374, 1696–1697 | `logger.debug(...)` | Per-message dump — extremely verbose |
| `logger.info("[CONTEXT_DEBUG] Merging context into system prompt...")` | 1665 | `logger.debug(...)` | Diagnostic tracing |
| `logger.info("[CONTEXT_DEBUG] Context preview...")` | 1668 | `logger.debug(...)` | Diagnostic tracing |
| `logger.info("[CACHE_INJECTION] Injecting cache guidance...")` | 1673 | `logger.debug(...)` | Diagnostic tracing |
| `logger.info("Injecting cache guidance for follow-up...")` | 623 | `logger.debug(...)` | Cache internals, not user-facing milestone |

These `[CONTEXT_DEBUG]` and `[CACHE_INJECTION]` messages were logged at INFO because DEBUG was "opt-in" via `--debug`. With the new system, INFO becomes the standard operational level, and these diagnostic messages need to move to DEBUG where they belong.

### 7.2 `core/context/result_cache.py` (logger: `logai.core.context.result_cache`)

| Level | What to log |
|---|---|
| **ERROR** | Serialization failures, corrupted JSON in cache, DB write failures |
| **WARNING** | Cache misses (line 670), corrupted entries (line 180), stale entries (line 695) |
| **INFO** | Cache hit/store operations with summary stats (line 600, 811, 858, 889) |
| **DEBUG** | Detailed cache internals — statistics methods, field detection (line 244), chunk fetch details (line 647, 687), initialization (line 195) |

**No changes required.** Current levels are appropriate.

### 7.3 `core/context/budget_tracker.py` (logger: `logai.core.context.budget_tracker`)

| Level | What to log |
|---|---|
| **WARNING** | Budget allocation failures, unexpected model |
| **DEBUG** | Token counts, allocation calculations, budget snapshots |

**No changes required.** Currently uses debug appropriately.

### 7.4 `core/context/token_counter.py` (logger: `logai.core.context.token_counter`)

| Level | What to log |
|---|---|
| **WARNING** | Tokenizer fallback (tiktoken not available for model) |
| **DEBUG** | Token count estimates per operation |

**No changes required.**

### 7.5 `core/log_group_manager.py` (logger: `logai.core.log_group_manager`)

| Level | What to log |
|---|---|
| **ERROR** | AWS API failures during log group loading |
| **WARNING** | Update callback errors (line 158), partial load failures |
| **INFO** | Load completed (count, duration), refresh completed |
| **DEBUG** | Individual group processing, filtering details |

**No changes required.** This module uses an inline `logging.getLogger(__name__)` call on line 158 rather than a module-level logger. That's fine — it still propagates to root.

### 7.6 `providers/llm/litellm_provider.py` (logger: uses LiteLLM's loggers)

**CRITICAL — Preserve existing suppression code (lines 25–31):**

```python
for logger_name in ["LiteLLM", "LiteLLM Router", "LiteLLM Proxy"]:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = True
```

This code clears LiteLLM's default stderr handlers (which would corrupt the TUI) while keeping propagation enabled so their messages flow to our file handler. **This must remain unchanged.** The LiteLLM loggers will inherit the root logger's level through propagation.

**No changes required in this module.**

### 7.7 `providers/llm/github_copilot_provider.py` (logger: `logai.providers.llm.github_copilot_provider`)

| Level | What to log |
|---|---|
| **ERROR** | Authentication failures, API request failures (after all retries exhausted) |
| **WARNING** | Individual retry attempts (403, rate limits), token refresh |
| **INFO** | Provider initialization, successful authentication, model selection |
| **DEBUG** | Request/response details, header construction, token details |

**No changes required.** Current levels look appropriate from the module structure.

### 7.8 `config/model_config.py` (logger: `logai.config.model_config`)

| Level | What to log |
|---|---|
| **WARNING** | Unknown model fallback, missing configuration |
| **DEBUG** | Model resolution, config lookup details |

**No changes required.**

### 7.9 `ui/app.py` (logger: `logai.ui.app`)

| Level | What to log |
|---|---|
| **ERROR** | Application crash, screen mount failures |
| **INFO** | App startup, screen transitions |
| **DEBUG** | Widget lifecycle events |

**No changes required.**

### 7.10 `ui/screens/chat.py` (logger: `logai.ui.screens.chat`)

| Level | What to log |
|---|---|
| **ERROR** | Message send failures, component access failures (line 357), mount failures (line 200) |
| **CRITICAL** | Failed to display error to user (line 208) — keep as-is |
| **WARNING** | — |
| **INFO** | Screen mounting (line 170, 197) |
| **DEBUG** | Context injection details (line 266), modal interactions (line 370, 374, 419) |

**No changes required.** Current levels are appropriate.

### 7.11 `ui/screens/context_viewer.py` (logger: `logai.ui.screens.context_viewer`)

| Level | What to log |
|---|---|
| **ERROR** | Context parsing failures |
| **DEBUG** | Context rendering details |

**No changes required.**

### 7.12 `ui/screens/log_preview.py` (logger: `logai.ui.screens.log_preview`)

| Level | What to log |
|---|---|
| **ERROR** | Log fetch failures |
| **WARNING** | Partial results |
| **INFO** | — |
| **DEBUG** | Event counts, selection details |

**Specific changes required:**

| Current | Line(s) | Change To | Reason |
|---|---|---|---|
| `logger.info("[CONTEXT_DEBUG] Fetched N events...")` | 749 | `logger.debug(...)` | Diagnostic detail |
| `logger.info("[CONTEXT_DEBUG] Gathered N of M selected events")` | 906 | `logger.debug(...)` | Diagnostic detail |
| `logger.info("[CONTEXT_DEBUG] Total selected_ids...")` | 910 | `logger.debug(...)` | Diagnostic detail |
| `logger.info("[CONTEXT_DEBUG] Total selected_events gathered...")` | 911 | `logger.debug(...)` | Diagnostic detail |
| `logger.info("[CONTEXT_DEBUG] Dismissing modal...")` | 912 | `logger.debug(...)` | Diagnostic detail |

### 7.13 `ui/widgets/log_groups_sidebar.py` (logger: `logai.ui.widgets.log_groups_sidebar`)

| Level | What to log |
|---|---|
| **WARNING** | Sidebar render errors |
| **DEBUG** | Group selection, filter changes, sidebar state |

**No changes required.**

### 7.14 `ui/widgets/status_footer.py` (logger: `logai.ui.widgets.status_footer`)

| Level | What to log |
|---|---|
| **WARNING** | Status update failures |
| **DEBUG** | Status bar render events |

**No changes required.**

### 7.15 `ui/widgets/tool_sidebar.py` (logger: `logai.ui.widgets.tool_sidebar`)

| Level | What to log |
|---|---|
| **WARNING** | Tool display errors |
| **DEBUG** | Tool call state changes, sidebar updates |

**No changes required.**

### 7.16 `tools/fetch_cached_result.py` (logger: `logai.tools.fetch_cached_result`)

| Level | What to log |
|---|---|
| **ERROR** | Cache read failures |
| **WARNING** | Cache misses |
| **INFO** | Successful chunk fetches (with stats) |
| **DEBUG** | Fetch parameters, offset/limit calculations |

**No changes required.**

### 7.17 `cli.py` (logger: `logai.cli` — created inside `setup_logging()`)

| Level | What to log |
|---|---|
| **INFO** | `Logging initialized: level=X, file=Y` (this is the bootstrap message) |

**No changes required.** The logger inside `setup_logging()` is just for the one initialization message.

### Summary of Required Log Level Changes

Total log statement changes needed: **~13 statements**, all in two files:
- `core/orchestrator.py`: ~8 changes (`logger.info` → `logger.debug` for `[CONTEXT_DEBUG]` and `[CACHE_INJECTION]` prefixed messages)
- `ui/screens/log_preview.py`: ~5 changes (`logger.info` → `logger.debug` for `[CONTEXT_DEBUG]` prefixed messages)

All other modules have appropriate log levels already.

---

## 8. `structlog` Decision

### Recommendation: Do NOT adopt `structlog`. Stay with stdlib `logging`.

### Reasoning

1. **It's already a dependency but completely unused.** The `structlog>=24.1.0` entry in `pyproject.toml` (line 50) was likely added speculatively. Zero imports of `structlog` exist anywhere in the codebase.

2. **17 modules already use `getLogger(__name__)`.** Switching to structlog means touching every single module, changing every single log call. That's a massive diff for zero functional benefit in this feature scope.

3. **structlog's value proposition doesn't apply here.** structlog shines in high-throughput services where structured JSON logging is consumed by log aggregation pipelines (ELK, Datadog, etc.). LogAI's logs go to a local file on the developer's machine. A human reads them. The current `%(asctime)s - %(name)s - %(levelname)s - %(message)s` format is perfect for that.

4. **Risk/reward is terrible.** Adopting structlog would:
   - Touch all 17 modules (high risk)
   - Require updating all ~180 log calls
   - Require all tests to be updated
   - Deliver no user-visible improvement
   - Risk introducing subtle bugs in every module

5. **The informal `[DIAGNOSTIC]` tags are the argument people make for structlog.** "We need structured key-value pairs!" But the right fix is simpler: promote them to proper `logger.debug()` calls (which they mostly already are) and remove the tags. See §9.

### Action Item

Consider removing `structlog` from `pyproject.toml` dependencies in a future cleanup ticket if no other planned feature needs it. Do NOT remove it as part of this feature — keep scope tight.

---

## 9. `[DIAGNOSTIC]` Tag Handling

### Current State

There are 25 log calls in `orchestrator.py` prefixed with informal string tags:
- `[DIAGNOSTIC]` — 5 occurrences (all at `logger.debug`)
- `[FETCH_LOGS_DEBUG]` — 18 occurrences (16 at `logger.debug`, 1 at `logger.warning`, 1 at `logger.debug` with data)
- `[CONTEXT_DEBUG]` — 9 occurrences in orchestrator (all at `logger.info` — **wrong level**)
- `[CACHE_INJECTION]` — 1 occurrence in orchestrator (at `logger.info` — **wrong level**)
- `[CONTEXT_DEBUG]` — 5 occurrences in `log_preview.py` (all at `logger.info` — **wrong level**)

### Clean-Up Plan

#### Step 1: Fix Log Levels First

As specified in §7, change all `[CONTEXT_DEBUG]` and `[CACHE_INJECTION]` messages from `logger.info` to `logger.debug`. This is the highest priority because these messages will pollute INFO-level logs.

#### Step 2: Remove the Bracket-Tag Prefixes

After fixing levels, strip the `[DIAGNOSTIC]`, `[FETCH_LOGS_DEBUG]`, `[CONTEXT_DEBUG]`, and `[CACHE_INJECTION]` string prefixes from all log messages. They are no longer needed because:

- **The log level itself is the filter.** With proper levels, `--loglevel DEBUG` shows everything, `--loglevel INFO` hides diagnostics. No need for manual grep tags.
- **The logger name provides context.** `logai.core.orchestrator - DEBUG - Processing tool result...` is self-documenting.
- **They add noise.** Every `[FETCH_LOGS_DEBUG]` prefix is 18 bytes of repeated text in the log file.

#### Example Transformations

```python
# BEFORE
logger.debug(
    f"[DIAGNOSTIC] Processing tool result: tool_name={tool_name}, "
    f"event_count={event_count}, has_result={bool(result_data_temp)}"
)

# AFTER
logger.debug(
    f"Processing tool result: tool_name={tool_name}, "
    f"event_count={event_count}, has_result={bool(result_data_temp)}"
)
```

```python
# BEFORE
logger.info(f"[CONTEXT_DEBUG] Sending {len(messages)} messages to LLM")

# AFTER
logger.debug(f"Sending {len(messages)} messages to LLM")
```

```python
# BEFORE
logger.warning("[FETCH_LOGS_DEBUG] Failed to parse message content as JSON")

# AFTER — Note: this one stays at WARNING because JSON parse failure is a real concern
logger.warning("Failed to parse tool message content as JSON")
```

#### Step 3: Preserve the `[FETCH_LOGS_DEBUG]` Section Headers (Optional)

The `===== RAW TOOL EXECUTION =====` and `===== FINAL MESSAGE TO LLM =====` separator lines can stay as-is (just drop the `[FETCH_LOGS_DEBUG]` prefix). They aid readability when scanning debug logs:

```python
# Keep this style (it's useful for visual scanning of debug logs)
logger.debug(f"===== RAW TOOL EXECUTION ===== Tool executed: {function_name}")
```

### Scope Note

The tag removal is a string-level cleanup. It can be done in the same PR as the log level feature since every affected line is already being touched to fix levels.

---

## 10. Test Strategy

### 10.1 Unit Tests for `setup_logging()` (file: `tests/unit/test_cli.py`)

The existing `TestLoggingSetup` class needs to be **significantly refactored** because the old tests test `debug: bool` behavior.

#### Tests to Remove/Refactor

- `test_setup_logging_no_console_handler_when_file_succeeds` — refactor to use new signature
- `test_setup_logging_console_handler_when_file_fails` — refactor to use new signature

#### New Tests for Precedence Logic

```python
class TestLogLevelPrecedence:
    """Test suite for log level resolution in setup_logging()."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        yield
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def test_cli_level_overrides_settings(self, tmp_path, clean_env):
        """CLI --loglevel takes precedence over settings.log_level."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "INFO"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()

        setup_logging(
            cli_level="DEBUG",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.DEBUG

    def test_settings_used_when_no_cli_level(self, tmp_path, clean_env):
        """settings.log_level (from .env) used when CLI flag absent."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "ERROR"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()

        setup_logging(
            cli_level=None,
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.ERROR

    def test_default_level_when_nothing_set(self, tmp_path, clean_env):
        """Default WARNING when neither CLI nor env var is set."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_default_level_is_warning(self, tmp_path, clean_env):
        """Verify the default is WARNING, not INFO."""
        from logai.cli import setup_logging, DEFAULT_LOG_LEVEL

        assert DEFAULT_LOG_LEVEL == "WARNING"

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_cli_warning_overrides_env_debug(self, tmp_path, clean_env):
        """CLI WARNING takes precedence even when env is DEBUG."""
        from logai.cli import setup_logging
        from logai.config import LogAISettings

        os.environ["LOGAI_LOG_LEVEL"] = "DEBUG"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-test"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        settings = LogAISettings()

        setup_logging(
            cli_level="WARNING",
            settings=settings,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING

    def test_settings_none_falls_back_to_default(self, tmp_path, clean_env):
        """When settings is None and no CLI, use default."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level=None,
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        assert logging.getLogger().level == logging.WARNING
```

#### New Tests for Log File Behavior (preserve existing patterns)

```python
    def test_file_handler_only_when_file_succeeds(self, tmp_path):
        """No StreamHandler when file logging succeeds."""
        from logai.cli import setup_logging

        setup_logging(
            cli_level="INFO",
            settings=None,
            log_file=str(tmp_path / "test.log"),
        )

        root = logging.getLogger()
        app_handlers = [
            h for h in root.handlers
            if type(h).__name__ not in [
                "LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"
            ]
        ]
        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.FileHandler)

    def test_console_fallback_when_file_fails(self):
        """StreamHandler used as fallback when file logging fails."""
        from logai.cli import setup_logging

        with patch("sys.stderr", new_callable=StringIO):
            setup_logging(
                cli_level="INFO",
                settings=None,
                log_file="/root/cannot/write/here/test.log",
            )

        root = logging.getLogger()
        app_handlers = [
            h for h in root.handlers
            if type(h).__name__ not in [
                "LogCaptureHandler", "_LiveLoggingNullHandler", "_FileHandler"
            ]
        ]
        assert len(app_handlers) == 1
        assert isinstance(app_handlers[0], logging.StreamHandler)
        assert not isinstance(app_handlers[0], logging.FileHandler)
```

### 10.2 Unit Tests for CLI Argument Parsing

```python
class TestLogLevelCLIArgument:
    """Test --loglevel argument parsing."""

    def test_loglevel_debug_accepted(self):
        """--loglevel DEBUG is accepted."""
        with patch("sys.argv", ["logai", "--loglevel", "DEBUG"]):
            parser = _build_parser()  # Extract parser building to testable function
            args = parser.parse_args()
            assert args.loglevel == "DEBUG"

    def test_loglevel_case_insensitive(self):
        """--loglevel debug works (normalized to DEBUG)."""
        with patch("sys.argv", ["logai", "--loglevel", "debug"]):
            parser = _build_parser()
            args = parser.parse_args()
            assert args.loglevel == "DEBUG"

    def test_loglevel_default_is_none(self):
        """No --loglevel flag → args.loglevel is None."""
        with patch("sys.argv", ["logai"]):
            parser = _build_parser()
            args = parser.parse_args()
            assert args.loglevel is None

    def test_loglevel_invalid_rejected(self):
        """Invalid level is rejected by argparse."""
        with patch("sys.argv", ["logai", "--loglevel", "TRACE"]):
            parser = _build_parser()
            with pytest.raises(SystemExit):
                parser.parse_args()

    def test_debug_flag_gives_clear_error(self):
        """--debug gives clear migration error."""
        with patch("sys.argv", ["logai", "--debug"]):
            parser = _build_parser()
            with pytest.raises(SystemExit):
                parser.parse_args()
```

### 10.3 Unit Tests for Settings Default Change

In `tests/unit/test_settings.py`:

```python
    def test_default_log_level_is_warning(self, clean_env):
        """Verify default log_level changed from INFO to WARNING."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings(_env_file=None)
        assert settings.log_level == "WARNING"  # Changed from "INFO"
```

**IMPORTANT:** The existing test `test_default_values` (line 13–25 of `test_settings.py`) asserts `settings.log_level == "INFO"` on line 25. **This test must be updated to assert `"WARNING"`.**

### 10.4 Integration Test: End-to-End Precedence

```python
class TestLogLevelIntegration:
    """Integration test verifying full CLI → setup_logging flow."""

    def test_e2e_loglevel_debug_produces_debug_output(self, tmp_path, clean_env):
        """Full flow: --loglevel DEBUG → DEBUG messages appear in log file."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="DEBUG", settings=None, log_file=str(log_file))

        test_logger = logging.getLogger("test.integration")
        test_logger.debug("debug message")
        test_logger.info("info message")
        test_logger.warning("warning message")

        # Flush handlers
        for h in logging.getLogger().handlers:
            h.flush()

        content = log_file.read_text()
        assert "debug message" in content
        assert "info message" in content
        assert "warning message" in content

    def test_e2e_loglevel_warning_hides_info(self, tmp_path, clean_env):
        """Full flow: --loglevel WARNING → INFO/DEBUG hidden from log."""
        from logai.cli import setup_logging

        log_file = tmp_path / "test.log"
        setup_logging(cli_level="WARNING", settings=None, log_file=str(log_file))

        test_logger = logging.getLogger("test.integration")
        test_logger.debug("should not appear")
        test_logger.info("should not appear")
        test_logger.warning("should appear")

        for h in logging.getLogger().handlers:
            h.flush()

        content = log_file.read_text()
        assert "should not appear" not in content
        assert "should appear" in content
```

### 10.5 Existing Tests That Need Updates

| Test File | Test | Change Required |
|---|---|---|
| `tests/unit/test_settings.py` | `test_default_values` | Change assertion: `log_level == "WARNING"` |
| `tests/unit/test_cli.py` | `TestLoggingSetup` (all 6 tests) | Refactor to new `setup_logging()` signature |
| `tests/unit/test_cli.py` | `TestAWSProfileCLIArgument` and friends | Update `args.debug` references if any setup_logging calls are mocked |

Run `pytest tests/` after all changes to verify nothing else breaks. The existing test suite should catch any regressions.

---

## 11. Migration Notes

### 11.1 Breaking Change: `--debug` Removal

This is a **breaking change** for any user who has `--debug` in their shell aliases, scripts, or documentation. The `DeprecatedDebugAction` custom action provides a clear error message:

```
logai: error: The --debug flag has been removed. Use --loglevel DEBUG instead.
```

### 11.2 Default Level Change: INFO → WARNING

Users who previously relied on default INFO logging will now get WARNING by default. This is intentional — it reduces log noise in normal operation. Users who want INFO-level detail should explicitly set `--loglevel INFO` or `LOGAI_LOG_LEVEL=INFO`.

**Impact:** Users who are actively debugging by reading log files may notice fewer messages until they set `--loglevel INFO` or `--loglevel DEBUG`.

### 11.3 `setup_logging()` Call Order in `main()`

The current code calls `setup_logging()` before `get_settings()`. The new design calls `get_settings()` first (to read `.env` log level), then `setup_logging()`. This means:

- If `get_settings()` fails, logging won't be initialized yet.
- The current startup prints before `get_settings()` already go to stderr anyway (not through logging), so this is safe.
- We handle `get_settings()` failure by passing `settings=None`, which gives us CLI level or default.

### 11.4 LiteLLM Logger Suppression

The LiteLLM suppression code in `litellm_provider.py` (lines 25–31) runs at **module import time**, before `setup_logging()` configures the root logger. This is fine because:

1. The code clears LiteLLM's *handlers* (which prevents stderr output)
2. It sets `propagate=True` (so messages flow to root)
3. When `setup_logging()` later configures the root logger with a `FileHandler`, LiteLLM messages automatically go to the log file via propagation

**No changes needed.** But the engineer should verify this manually after implementation by running with `--loglevel DEBUG` and confirming LiteLLM messages appear in the log file but NOT in the TUI.

### 11.5 Order of Operations Risks

The reordering of `get_settings()` and `setup_logging()` in `main()` means any exception during settings loading won't be logged to the file (logging isn't set up yet). This is acceptable because:

1. Settings errors print to stderr via the existing `try/except` block
2. The TUI isn't running yet at that point, so stderr is safe
3. Once settings load, logging initializes immediately

### 11.6 Concurrency Note

All loggers use the root logger via propagation. `logging.basicConfig(force=True)` is thread-safe (Python's logging module uses locks internally). No concurrency issues.

### 11.7 Scope Boundary

This feature does **not** include:
- Per-module log level overrides (e.g., `LOGAI_LOG_LEVEL_ORCHESTRATOR=DEBUG`)
- Log rotation (can be added later with `RotatingFileHandler`)
- Structured JSON output
- Runtime log level changes (would require restarting the app)
- Console output mode (all logs go to file only)

These are all reasonable future enhancements but are explicitly out of scope.

---

## Appendix A: File Change Summary

| File | Changes |
|---|---|
| `src/logai/cli.py` | Redesign `setup_logging()`, remove `--debug`, add `--loglevel`, add `DeprecatedDebugAction`, reorder `main()` flow, add `VALID_LOG_LEVELS` and `DEFAULT_LOG_LEVEL` constants |
| `src/logai/config/settings.py` | Change `log_level` default from `"INFO"` to `"WARNING"` |
| `src/logai/core/orchestrator.py` | Change ~8 `logger.info` → `logger.debug` (CONTEXT_DEBUG/CACHE_INJECTION tags), remove bracket-tag prefixes from ~25 log messages |
| `src/logai/ui/screens/log_preview.py` | Change ~5 `logger.info` → `logger.debug` (CONTEXT_DEBUG tags), remove bracket-tag prefixes |
| `.env.example` | Update logging section: new default, CLI override note, file-only note |
| `tests/unit/test_cli.py` | Refactor `TestLoggingSetup`, add `TestLogLevelPrecedence`, add `TestLogLevelCLIArgument` |
| `tests/unit/test_settings.py` | Update `test_default_values` assertion |

**Total files changed: 7**
**Estimated LOC changed: ~300 (mostly test code)**

---

## Appendix B: Acceptance Criteria Cross-Reference

| AC# | Requirement | Addressed In |
|---|---|---|
| 1 | `logai --loglevel DEBUG` sets DEBUG | §3 (CLI changes), §2 (setup_logging) |
| 2 | `logai --loglevel INFO` sets INFO | §3, §2 |
| 3 | `LOGAI_LOG_LEVEL=DEBUG` in .env sets DEBUG | §4 (settings), §2 (setup_logging reads settings) |
| 4 | CLI takes precedence over .env | §6 (precedence logic), §2 (resolution algorithm) |
| 5 | Default is WARNING | §4 (settings default), §2 (DEFAULT_LOG_LEVEL) |
| 6 | `--debug` removed with clear error | §3 (DeprecatedDebugAction) |
| 7 | Log to ~/.logai/logs/logai.log only | §2 (file handler logic preserved) |
| 8 | TUI not disrupted | §2 (no console handler in normal operation), §7.6 (LiteLLM suppression preserved) |
| 9 | Log entries at appropriate levels | §7 (all 17 modules with specific guidance) |
| 10 | Existing tests pass | §10.5 (update list), §11 (migration notes) |
| 11 | New tests cover precedence | §10.1–10.4 (comprehensive test plan) |
