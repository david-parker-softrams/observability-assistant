"""Command-line interface for LogAI."""

import argparse
import sys
from pathlib import Path

from logai import __version__


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

    # For now, just print a message - TUI will be implemented in Phase 7
    print(f"LogAI v{__version__}")
    print("TUI interface coming soon...")
    print("\nPlease set up your environment variables:")
    print("  - LOGAI_ANTHROPIC_API_KEY or LOGAI_OPENAI_API_KEY")
    print("  - AWS credentials for CloudWatch access")

    return 0


if __name__ == "__main__":
    sys.exit(main())
