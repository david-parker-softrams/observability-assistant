"""Command-line interface for LogAI."""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from logai import __version__
from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.config.settings import LogAISettings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.datasources.cloudwatch import CloudWatchDataSource
from logai.providers.llm.litellm_provider import LiteLLMProvider
from logai.ui.app import LogAIApp

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Valid log levels accepted by --loglevel and LOGAI_LOG_LEVEL
# CRITICAL intentionally omitted — no user scenario requires suppressing ERROR but showing CRITICAL
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

# Default log level when neither --loglevel nor LOGAI_LOG_LEVEL is configured
DEFAULT_LOG_LEVEL = "WARNING"


class DeprecatedDebugAction(argparse.Action):
    """Custom argparse action that gives a clear error when --debug is used.

    Users who have --debug in their aliases or scripts will see an actionable
    migration message instead of a confusing "unrecognized argument" error.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error("The --debug flag has been removed. Use --loglevel DEBUG instead.")


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

    All log output goes to a file only — never to stdout or stderr — to
    preserve TUI integrity. A StreamHandler is added only as an emergency
    fallback when the log file cannot be created.

    Args:
        cli_level: Log level from the CLI flag (e.g., "DEBUG", "INFO").
                   None means --loglevel was not provided.
        settings: Application settings instance. If None, only cli_level
                  and DEFAULT_LOG_LEVEL are considered.
        log_file: Path to log file. Defaults to ~/.logai/logs/logai.log.
                  If settings.log_file is set, that is used as a secondary
                  source before falling back to the default path.
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
        # NOTE: If LOGAI_LOG_LEVEL=WARNING is set explicitly in .env, source will
        # show 'default' since WARNING == DEFAULT_LOG_LEVEL. The level is still
        # correct; only the diagnostic label is slightly misleading.
        effective_level_name = settings.log_level
        level_source = "LOGAI_LOG_LEVEL env var"
    elif settings is not None:
        # Settings exist but log_level is at default
        effective_level_name = settings.log_level
        level_source = "default"
    else:
        effective_level_name = DEFAULT_LOG_LEVEL
        level_source = "default"

    # Validate the resolved level. argparse choices= and Pydantic's Literal
    # should prevent invalid values in practice, but guard defensively here.
    if effective_level_name not in VALID_LOG_LEVELS:
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
            # Use settings.log_file if available, otherwise fall back to default
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
        # Emergency fallback to console ONLY when file creation fails.
        # Under normal operation nothing goes to the console, preserving TUI.
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,  # Clear any existing handlers (e.g., from pytest)
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


def _build_parser() -> argparse.ArgumentParser:
    """
    Build and return the CLI argument parser.

    Extracted into its own function so that tests can exercise argument
    parsing in isolation without running main().
    """
    parser = argparse.ArgumentParser(
        prog="logai",
        description="AI-powered observability assistant for AWS CloudWatch logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  logai                                      # Start with default configuration
  logai --aws-profile my-profile             # Use specific AWS profile
  logai --aws-profile prod --aws-region us-west-2  # Use profile and region
  logai --loglevel DEBUG                     # Enable debug logging
  logai --loglevel INFO                      # Standard operational logging
  logai --version                            # Show version information
  logai --help                               # Show this help message

  # Authentication commands
  logai auth login                           # Authenticate with GitHub Copilot
  logai auth status                          # Check authentication status
  logai auth logout                          # Remove stored credentials
  logai auth list                            # List authenticated providers

Environment Variables:
  LOGAI_LLM_PROVIDER              # LLM provider: anthropic (default) or openai
  LOGAI_ANTHROPIC_API_KEY         # Anthropic API key
  LOGAI_OPENAI_API_KEY            # OpenAI API key
  LOGAI_PII_SANITIZATION_ENABLED  # Enable PII sanitization (default: true)
  LOGAI_CACHE_DIR                 # Cache directory (default: ~/.logai/cache)
  LOGAI_LOG_LEVEL                 # Log level: DEBUG, INFO, WARNING, ERROR (default: WARNING)
  AWS_DEFAULT_REGION              # AWS region (can be overridden with --aws-region)
  AWS_PROFILE                     # AWS profile (can be overridden with --aws-profile)
  AWS_ACCESS_KEY_ID               # AWS credentials
  AWS_SECRET_ACCESS_KEY           # AWS credentials

Note: Command-line arguments take precedence over environment variables.

For more information, visit: https://github.com/logai/logai
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file (future feature)",
        default=None,
    )

    parser.add_argument(
        "--aws-profile",
        type=str,
        help="AWS profile name to use for CloudWatch access (overrides AWS_PROFILE)",
        default=None,
        metavar="PROFILE",
    )

    parser.add_argument(
        "--aws-region",
        type=str,
        help="AWS region for CloudWatch (overrides AWS_DEFAULT_REGION)",
        default=None,
        metavar="REGION",
    )

    parser.add_argument(
        "--loglevel",
        type=str.upper,  # Normalize to uppercase so --loglevel debug works
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,  # None = "not provided via CLI" (essential for precedence logic)
        help="Set log level (default: WARNING). Overrides LOGAI_LOG_LEVEL env var.",
        metavar="LEVEL",
    )

    # Keep --debug registered but redirect users to --loglevel with a clear message.
    # Hidden from --help output so it doesn't appear as a supported option.
    parser.add_argument(
        "--debug",
        nargs=0,
        action=DeprecatedDebugAction,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (default: ~/.logai/logs/logai.log)",
    )

    parser.add_argument(
        "--use-mcp",
        action="store_true",
        default=False,
        help=(
            "Use the AWS CloudWatch MCP server for CloudWatch tools (now the default). "
            "This flag is a no-op when LOGAI_USE_MCP_TOOLS=true (the default). "
            "Requires 'uvx' (from the 'uv' package manager) to be on PATH. "
            "Falls back to native boto3 tools automatically if 'uvx' is not found."
        ),
    )

    parser.add_argument(
        "--no-mcp",
        action="store_true",
        default=False,
        help=(
            "Disable the MCP server and use the legacy native boto3 CloudWatch tools instead. "
            "Useful if 'uvx' is unavailable or for troubleshooting MCP connectivity issues."
        ),
    )

    parser.add_argument(
        "--ollama-num-ctx",
        type=int,
        default=None,
        help=(
            "Override the Ollama context window size (num_ctx). "
            "Defaults to 32768 when using Ollama (overrides Ollama's built-in default of 4096). "
            "Increase for larger prompts/tool definitions; decrease to reduce VRAM usage. "
            "Ignored for non-Ollama providers. (overrides LOGAI_OLLAMA_NUM_CTX)"
        ),
        metavar="TOKENS",
    )

    # Add subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth subcommand group
    auth_parser = subparsers.add_parser("auth", help="Manage authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", help="Auth commands")

    # logai auth login
    login_parser = auth_subparsers.add_parser("login", help="Authenticate with GitHub Copilot")
    login_parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Authentication timeout in seconds (default: 900)",
    )

    # logai auth logout
    auth_subparsers.add_parser("logout", help="Remove GitHub Copilot credentials")

    # logai auth status
    auth_subparsers.add_parser("status", help="Show authentication status")

    # logai auth list
    auth_subparsers.add_parser("list", help="List authenticated providers")

    return parser


async def handle_auth_login(args: argparse.Namespace) -> int:
    """Handle 'logai auth login' command."""
    from logai.auth import GitHubCopilotAuth

    auth = GitHubCopilotAuth()
    try:
        print("\n🔐 GitHub Copilot Authentication\n")
        await auth.authenticate(timeout=args.timeout)
        print("\n✅ Authentication successful!")
        print(f"Token saved to: {auth.auth_file_path}")
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Authentication cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT (128 + 2)
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}", file=sys.stderr)
        return 1
    finally:
        await auth.close()


async def handle_auth_logout(args: argparse.Namespace) -> int:
    """Handle 'logai auth logout' command."""
    from logai.auth import GitHubCopilotAuth

    auth = GitHubCopilotAuth()
    try:
        if auth.logout():
            print("✅ Logged out successfully")
            return 0
        else:
            print("ℹ️  No credentials found")
            return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Logout cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT (128 + 2)
    except Exception as e:
        print(f"\n❌ Logout failed: {e}", file=sys.stderr)
        return 1
    finally:
        await auth.close()


async def handle_auth_status(args: argparse.Namespace) -> int:
    """Handle 'logai auth status' command."""
    from logai.auth import GitHubCopilotAuth

    auth = GitHubCopilotAuth()
    try:
        status = auth.get_status()
        print("\n🔍 GitHub Copilot Authentication Status\n")
        print("Provider: github-copilot")
        print(f"Authenticated: {status['authenticated']}")
        if status["authenticated"]:
            print(f"Token: {status['token_prefix']}")
            print(f"Token file: {status['auth_file']}")
        else:
            print("\nRun 'logai auth login' to authenticate")
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Status check cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT (128 + 2)
    except Exception as e:
        print(f"\n❌ Status check failed: {e}", file=sys.stderr)
        return 1
    finally:
        await auth.close()


async def handle_auth_list(args: argparse.Namespace) -> int:
    """Handle 'logai auth list' command."""
    from logai.auth import TokenStorage

    storage = TokenStorage()

    print("\n📋 Authenticated Providers\n")

    # Check GitHub Copilot
    token_data = storage.load_token()
    if token_data:
        print("✓ github-copilot")
    else:
        print("✗ github-copilot (not authenticated)")

    # Future: Check other providers here

    return 0


def build_mcp_env(settings: LogAISettings) -> dict[str, str]:
    """
    Build the environment dictionary for the MCP server subprocess.

    Uses an explicit allowlist rather than inheriting the full parent
    environment.  This prevents LLM API keys (``LOGAI_ANTHROPIC_API_KEY``,
    ``LOGAI_OPENAI_API_KEY``, etc.) and other sensitive credentials from
    leaking into the MCP server subprocess.

    The allowlist includes:
    - POSIX/macOS essentials so ``uvx`` and subprocess tools can locate
      binaries and write temporary files (``PATH``, ``HOME``, ``USER``,
      ``TMPDIR``/``TEMP``/``TMP``).
    - All AWS credential/configuration variables the MCP server needs.
    - ``FASTMCP_LOG_LEVEL`` (set explicitly below).

    AWS profile and region are then overlaid from ``settings`` so that
    CLI flags (``--aws-profile``, ``--aws-region``) are honoured.

    Args:
        settings: Application settings containing AWS profile/region.

    Returns:
        A filtered environment dictionary suitable for passing to
        ``StdioServerParameters(env=...)``.
    """
    # Keys that the MCP subprocess is allowed to inherit from the parent env.
    # Everything else — including LLM API keys — is excluded.
    _ALLOWED_ENV_KEYS = {
        # Shell / OS essentials
        "PATH",
        "HOME",
        "USER",
        "TMPDIR",
        "TEMP",
        "TMP",
        # AWS credentials and configuration
        "AWS_DEFAULT_REGION",
        "AWS_REGION",  # Secondary alias; botocore prefers AWS_DEFAULT_REGION
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_ROLE_ARN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        # MCP server logging (set explicitly below)
        "FASTMCP_LOG_LEVEL",
    }

    env = {k: v for k, v in os.environ.items() if k in _ALLOWED_ENV_KEYS and v}

    # Overlay AWS settings from LogAI config so CLI flags take precedence
    # over whatever happens to be in the ambient environment.
    if settings.aws_profile:
        env["AWS_PROFILE"] = settings.aws_profile
    if settings.aws_region:
        # Use the canonical variable name that the AWS SDK reads by default.
        env["AWS_DEFAULT_REGION"] = settings.aws_region

    # Keep MCP server logs quiet so they don't interfere with our TUI output.
    env["FASTMCP_LOG_LEVEL"] = "ERROR"

    return env


def _run_app(settings: LogAISettings) -> int:
    """
    Synchronous application entry point — initialises all components and runs the TUI.

    MCP client startup/shutdown is intentionally NOT performed here.  Textual's
    ``App.run()`` creates and owns its own ``asyncio`` event loop, so any
    ``await`` call before ``app.run()`` would require a *separate* loop via
    ``asyncio.run()``.  Nesting two ``asyncio.run()`` calls crashes with:

        RuntimeError: asyncio.run() cannot be called from a running event loop

    Instead, an unstarted ``MCPClientManager`` (and its ``ResultProcessor``) are
    passed into ``LogAIApp``, which starts MCP inside ``ChatScreen.on_mount``
    using a Textual ``@work`` worker — safely within Textual's own event loop.

    Args:
        settings: Fully-resolved application settings.

    Returns:
        Integer exit code (0 = success, 1 = failure).
    """
    from logai.core.context.result_cache import ResultCacheManager
    from logai.core.log_group_manager import LogGroupManager
    from logai.core.metrics import MetricsCollector
    from logai.tools.fetch_cached_result import FetchCachedResultTool

    try:
        # ----------------------------------------------------------------
        # Core components (always initialised regardless of tool mode)
        # ----------------------------------------------------------------
        datasource = CloudWatchDataSource(settings)
        sanitizer = LogSanitizer(enabled=settings.pii_sanitization_enabled)
        cache_manager = CacheManager(settings)
        metrics_collector = MetricsCollector()

        result_cache = ResultCacheManager(
            cache_dir=settings.cache_dir / "results",
            ttl_seconds=getattr(settings, "cache_ttl_seconds", 3600),
            max_size_mb=100,
            sample_event_count=settings.cache_sample_event_count,
            metrics_collector=metrics_collector,
        )

        # ----------------------------------------------------------------
        # Tool registration — MCP path or native path
        # ----------------------------------------------------------------
        # MCP tools (when enabled) are NOT registered here.  Registration
        # requires an active MCP subprocess, which must be started inside
        # Textual's event loop.  An unstarted MCPClientManager is passed to
        # LogAIApp, which starts it in ChatScreen.on_mount via a @work worker.
        mcp_client = None
        result_processor = None

        if settings.use_mcp_tools:
            # --- MCP path: build the client/processor but do NOT start ---
            from logai.providers.mcp.client import MCPClientManager
            from logai.providers.mcp.sanitization import ResultProcessor

            mcp_env = build_mcp_env(settings)
            mcp_client = MCPClientManager(
                command=settings.mcp_server_command,
                args=settings.mcp_server_args,
                env=mcp_env,
                log_file_path=str(settings.log_file) if settings.log_file is not None else None,
            )
            result_processor = ResultProcessor(sanitizer=sanitizer, cache=cache_manager)
        else:
            # --- Native path (--no-mcp or MCP unavailable): register immediately ---
            _register_native_cloudwatch_tools(datasource, sanitizer, settings, cache_manager)

        # FetchCachedResultTool is always registered natively — it is application-
        # specific and has no MCP equivalent (design §4.4).
        ToolRegistry.register(
            FetchCachedResultTool(
                result_cache=result_cache,
                metrics_collector=metrics_collector,
            )
        )

        # ----------------------------------------------------------------
        # Pre-load log groups (sync wrapper around the async call, safe here
        # because Textual's event loop has NOT been started yet)
        # ----------------------------------------------------------------
        log_group_manager = LogGroupManager(datasource)

        def show_progress(count: int, message: str) -> None:
            print(f"\r  {message}", end="", flush=True)

        print("  Loading log groups from AWS...", end="", flush=True)
        load_result = asyncio.run(log_group_manager.load_all(progress_callback=show_progress))

        if load_result.success:
            print(
                f"\r✓ Found {load_result.count} log groups ({load_result.duration_ms}ms)          "
            )
        else:
            print(f"\r⚠ Failed to load log groups: {load_result.error_message}          ")
            print("  Agent will discover log groups via tools")

        # ----------------------------------------------------------------
        # LLM provider + orchestrator
        # ----------------------------------------------------------------
        llm_provider = LiteLLMProvider.from_settings(settings)

        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,
            sanitizer=sanitizer,
            settings=settings,
            cache=cache_manager,
            metrics_collector=metrics_collector,
            log_group_manager=log_group_manager,
            result_cache=result_cache,
        )

        print("✓ All components initialized")
        print("\nStarting TUI...\n")

        # Pass the unstarted MCP client (and its result processor) into the
        # app.  LogAIApp will forward them to ChatScreen, which starts the
        # MCP server asynchronously inside on_mount.
        app = LogAIApp(
            orchestrator,
            cache_manager,
            log_group_manager,
            mcp_client=mcp_client,
            result_processor=result_processor,
        )
        app.run()

        return 0

    except Exception as exc:
        logger.critical("Fatal error during app startup or runtime: %s", exc, exc_info=True)
        return 1


def _register_native_cloudwatch_tools(
    datasource: CloudWatchDataSource,
    sanitizer: LogSanitizer,
    settings: LogAISettings,
    cache_manager: CacheManager,
) -> None:
    """
    Register the native boto3-based CloudWatch tools in the ``ToolRegistry``.

    .. deprecated::
        The native boto3 tools are deprecated as of Phase 3 of the MCP migration.
        MCP tools are now the default path. This function is retained only as the
        fallback registered when MCP startup fails or when ``--no-mcp`` is passed.
        It will be removed in a future release once the MCP path is fully proven.

    Extracted into a helper so it can be called from both the ``--no-mcp`` path
    and the MCP startup-failure fallback path without code duplication.

    Args:
        datasource: CloudWatch data source.
        sanitizer: PII sanitizer.
        settings: Application settings.
        cache_manager: Query-level cache.
    """
    from logai.core.tools.cloudwatch_tools import FetchLogsTool, ListLogGroupsTool, SearchLogsTool

    ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache=cache_manager))
    ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache=cache_manager))
    ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache=cache_manager))


def main() -> int:
    """Main CLI entry point."""
    parser = _build_parser()

    # Parse arguments
    args = parser.parse_args()

    # Load settings FIRST — we need settings.log_level for full precedence
    # resolution in setup_logging(). If loading fails we pass settings=None,
    # which causes setup_logging() to fall back to cli_level or DEFAULT_LOG_LEVEL.
    settings = None
    try:
        settings = get_settings()
    except Exception as e:
        print(
            f"Warning: Could not load settings before logging init "
            f"({type(e).__name__}: {e}). Using defaults.",
            file=sys.stderr,
        )

    # Setup logging (uses settings if available for log_level from .env)
    setup_logging(cli_level=args.loglevel, settings=settings, log_file=args.log_file)

    # Handle auth commands (logging is available from this point forward)
    if args.command == "auth":
        if args.auth_command == "login":
            return asyncio.run(handle_auth_login(args))
        elif args.auth_command == "logout":
            return asyncio.run(handle_auth_logout(args))
        elif args.auth_command == "status":
            return asyncio.run(handle_auth_status(args))
        elif args.auth_command == "list":
            return asyncio.run(handle_auth_list(args))
        elif args.auth_command is None:
            parser.error("Usage: logai auth {login,logout,status,list}")
        else:
            print(f"❌ Unknown auth command: {args.auth_command}", file=sys.stderr)
            return 1

    # Load and validate configuration (settings may have already loaded above)
    try:
        if settings is None:
            # First attempt failed; retry now that logging is initialized
            settings = get_settings()

        # Override AWS settings from CLI arguments if provided.
        # CLI arguments take precedence over environment variables.
        if args.aws_profile is not None:
            settings.aws_profile = args.aws_profile
        if args.aws_region is not None:
            settings.aws_region = args.aws_region

        # Apply MCP mode flags to settings (CLI takes precedence over env/default).
        # --no-mcp explicitly opts out; --use-mcp explicitly opts in.
        if args.no_mcp:
            settings.use_mcp_tools = False
        elif args.use_mcp:
            settings.use_mcp_tools = True
        # If neither flag is given, settings.use_mcp_tools retains its value from
        # the environment variable or the default (True as of Phase 3).

        # Override Ollama context window if explicitly provided via CLI.
        if args.ollama_num_ctx is not None:
            settings.ollama_num_ctx = args.ollama_num_ctx

        settings.validate_required_credentials()
        settings.ensure_cache_dir_exists()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}", file=sys.stderr)
        print("\nPlease set the required environment variables:", file=sys.stderr)
        print("  - LOGAI_ANTHROPIC_API_KEY or LOGAI_OPENAI_API_KEY", file=sys.stderr)
        print("  - AWS_DEFAULT_REGION", file=sys.stderr)
        print(
            "  - AWS credentials (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE)",
            file=sys.stderr,
        )
        print("\nSee .env.example for a complete configuration template.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        return 1

    # Pre-flight check: if MCP is enabled, verify that the 'uvx' launcher is available.
    # If not, fall back to native tools with a clear warning.
    if settings.use_mcp_tools:
        if not shutil.which(settings.mcp_server_command):
            print(
                f"⚠ MCP tools enabled but '{settings.mcp_server_command}' not found on PATH.",
                file=sys.stderr,
            )
            print(
                "  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
                file=sys.stderr,
            )
            print(
                "  Falling back to native CloudWatch tools (use --no-mcp to suppress this warning).",
                file=sys.stderr,
            )
            settings.use_mcp_tools = False

    # Print configuration summary
    print(f"LogAI v{__version__}")
    print(f"✓ LLM Provider: {settings.llm_provider}")
    print(f"✓ LLM Model: {settings.current_llm_model}")

    # Show AWS region with source indication
    region_source = "CLI argument" if args.aws_region else "environment/default"
    print(f"✓ AWS Region: {settings.aws_region} (from {region_source})")

    # Show AWS profile if configured
    if settings.aws_profile:
        profile_source = "CLI argument" if args.aws_profile else "environment"
        print(f"✓ AWS Profile: {settings.aws_profile} (from {profile_source})")

    print(f"✓ PII Sanitization: {'Enabled' if settings.pii_sanitization_enabled else 'Disabled'}")
    print(f"✓ Cache Directory: {settings.cache_dir}")
    if settings.use_mcp_tools:
        print(
            f"✓ Tool Mode: MCP ({settings.mcp_server_command} {' '.join(settings.mcp_server_args)})"
        )
    else:
        print("✓ Tool Mode: Native boto3 (legacy — use --use-mcp to enable MCP)")
    print("\nInitializing components...")

    return _run_app(settings)


if __name__ == "__main__":
    sys.exit(main())
