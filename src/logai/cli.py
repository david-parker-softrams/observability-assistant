"""Command-line interface for LogAI."""

import argparse
import asyncio
import sys
from pathlib import Path

from logai import __version__
from logai.cache.manager import CacheManager
from logai.config import get_settings
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.datasources.cloudwatch import CloudWatchDataSource
from logai.providers.llm.litellm_provider import LiteLLMProvider
from logai.ui.app import LogAIApp


async def handle_auth_login(args: argparse.Namespace) -> int:
    """Handle 'logai auth login' command."""
    from logai.auth import GitHubCopilotAuth

    auth = GitHubCopilotAuth()
    try:
        print("\n🔐 GitHub Copilot Authentication\n")
        token = await auth.authenticate(timeout=args.timeout)
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
        print(f"Provider: github-copilot")
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
    parser = argparse.ArgumentParser(
        prog="logai",
        description="AI-powered observability assistant for AWS CloudWatch logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  logai                                      # Start with default configuration
  logai --aws-profile my-profile             # Use specific AWS profile
  logai --aws-profile prod --aws-region us-west-2  # Use profile and region
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
    logout_parser = auth_subparsers.add_parser("logout", help="Remove GitHub Copilot credentials")

    # logai auth status
    status_parser = auth_subparsers.add_parser("status", help="Show authentication status")

    # logai auth list
    list_parser = auth_subparsers.add_parser("list", help="List authenticated providers")

    # Parse arguments
    args = parser.parse_args()

    # Handle auth commands
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
            auth_parser.print_help()
            return 1
        else:
            print(f"❌ Unknown auth command: {args.auth_command}", file=sys.stderr)
            auth_parser.print_help()
            return 1

    # Load and validate configuration
    try:
        settings = get_settings()

        # Override AWS settings from CLI arguments if provided
        # CLI arguments take precedence over environment variables
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

        # Import and register tools
        from logai.core.tools.cloudwatch_tools import (
            FetchLogsTool,
            ListLogGroupsTool,
            SearchLogsTool,
        )

        # Register tools in the registry
        ToolRegistry.register(ListLogGroupsTool(datasource, settings, cache=cache_manager))
        ToolRegistry.register(FetchLogsTool(datasource, sanitizer, settings, cache=cache_manager))
        ToolRegistry.register(SearchLogsTool(datasource, sanitizer, settings, cache=cache_manager))

        # Initialize LLM provider
        llm_provider = LiteLLMProvider.from_settings(settings)

        # Initialize orchestrator
        orchestrator = LLMOrchestrator(
            llm_provider=llm_provider,
            tool_registry=ToolRegistry,  # type: ignore[arg-type]
            sanitizer=sanitizer,
            settings=settings,
            cache=cache_manager,
        )

        print("✓ All components initialized")
        print("\nStarting TUI...\n")

        # Start TUI
        app = LogAIApp(orchestrator, cache_manager)
        app.run()

        return 0

    except Exception as e:
        print(f"❌ Failed to initialize: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
