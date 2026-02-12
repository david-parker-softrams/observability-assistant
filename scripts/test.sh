#!/bin/bash
set -e

echo "Running type checking..."
mypy src/logai/

echo ""
echo "Running linting..."
ruff check src/logai/

echo ""
echo "Running tests..."
pytest

echo ""
echo "✅ All checks passed!"
