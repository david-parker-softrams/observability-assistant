"""Command-line interface for LogAI."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

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

# Valid log levels accepted by --loglevel and LOGAI_LOG_LEVEL
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
    except Exception:
        pass  # Will be handled after logging is initialized

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
            parser.parse_args(["auth", "--help"])
            return 1
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
    print("\nInitializing components...")

    try:
        # Initialize components
        datasource = CloudWatchDataSource(settings)
        sanitizer = LogSanitizer(enabled=settings.pii_sanitization_enabled)
        cache_manager = CacheManager(settings)

        # Initialize metrics collector
        from logai.core.metrics import MetricsCollector

        metrics_collector = MetricsCollector()

        # Import and register tools
        from logai.core.tools.cloudwatch_tools import (
            FetchLogsTool,
            ListLogGroupsTool,
            SearchLogsTool,
        )
        from logai.tools.fetch_cached_result import FetchCachedResultTool

        # Register CloudWatch tools in the registry
        ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache=cache_manager))
        ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache=cache_manager))
        ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache=cache_manager))

        # Initialize result cache for large tool results
        from logai.core.context.result_cache import ResultCacheManager

        result_cache = ResultCacheManager(
            cache_dir=settings.cache_dir / "results",
            ttl_seconds=getattr(settings, "cache_ttl_seconds", 3600),
            max_size_mb=100,
            sample_event_count=settings.cache_sample_event_count,
            metrics_collector=metrics_collector,
        )

        # Register context management tool
        ToolRegistry.register(
            FetchCachedResultTool(
                result_cache=result_cache,
                metrics_collector=metrics_collector,
            )
        )

        # === NEW: Pre-load log groups ===
        from logai.core.log_group_manager import LogGroupManager

        log_group_manager = LogGroupManager(datasource)

        # Define progress callback for CLI output
        def show_progress(count: int, message: str) -> None:
            # Use carriage return to update in place
            print(f"\r  {message}", end="", flush=True)

        print("  Loading log groups from AWS...", end="", flush=True)

        # Run async load synchronously
        result = asyncio.run(log_group_manager.load_all(progress_callback=show_progress))

        if result.success:
            print(f"\r✓ Found {result.count} log groups ({result.duration_ms}ms)          ")
        else:
            print(f"\r⚠ Failed to load log groups: {result.error_message}          ")
            print("  Agent will discover log groups via tools")
        # === END NEW ===

        # Initialize LLM provider
        llm_provider = LiteLLMProvider.from_settings(settings)

        # Initialize orchestrator with context management
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

        # Start TUI (modified to accept log_group_manager)
        app = LogAIApp(orchestrator, cache_manager, log_group_manager)
        app.run()

        return 0

    except Exception as e:
        print(f"❌ Failed to initialize: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
