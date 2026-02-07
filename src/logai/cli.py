"""Command-line interface for LogAI."""

import argparse
import sys
from pathlib import Path

from logai import __version__
from logai.config import get_settings


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="logai",
        description="AI-powered observability assistant for AWS CloudWatch logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  logai                    # Start interactive TUI chat
  logai --version         # Show version information
  logai --help            # Show this help message

Environment Variables:
  LOGAI_LLM_PROVIDER              # LLM provider: anthropic (default) or openai
  LOGAI_ANTHROPIC_API_KEY         # Anthropic API key
  LOGAI_OPENAI_API_KEY            # OpenAI API key
  LOGAI_PII_SANITIZATION_ENABLED  # Enable PII sanitization (default: true)
  LOGAI_CACHE_DIR                 # Cache directory (default: ~/.logai/cache)
  AWS_DEFAULT_REGION              # AWS region for CloudWatch
  AWS_ACCESS_KEY_ID               # AWS credentials
  AWS_SECRET_ACCESS_KEY           # AWS credentials

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

    args = parser.parse_args()

    # Load and validate configuration
    try:
        settings = get_settings()
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
    print(f"✓ AWS Region: {settings.aws_region}")
    print(f"✓ PII Sanitization: {'Enabled' if settings.pii_sanitization_enabled else 'Disabled'}")
    print(f"✓ Cache Directory: {settings.cache_dir}")
    print("\nTUI interface coming soon...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
