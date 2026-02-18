#!/usr/bin/env python3
"""Wrapper script to run LogAI without full installation."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from logai.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
