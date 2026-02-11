"""Command-line interface for LogAI."""

import argparse
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

    # Parse arguments
    args = parser.parse_args()

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
