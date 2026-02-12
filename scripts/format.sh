#!/bin/bash
set -e

echo "Formatting code..."
ruff format src/logai/ tests/

echo ""
echo "Fixing imports..."
ruff check --fix src/logai/ tests/

echo ""
echo "✅ Formatting complete!"
