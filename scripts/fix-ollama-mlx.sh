#!/bin/bash
# Fix Ollama MLX dynamic library loading
#
# This script creates a symlink to the MLX-C library in Ollama's bin directory
# so that Ollama can find and load the MLX dynamic library for GPU acceleration.
#
# Usage: ./scripts/fix-ollama-mlx.sh
#
# Run this script after each `brew upgrade ollama` to restore MLX support.

set -e

echo "🔍 Detecting Ollama version..."
OLLAMA_VERSION=$(ollama --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)

if [ -z "$OLLAMA_VERSION" ]; then
    echo "❌ Error: Could not determine Ollama version"
    echo "   Make sure Ollama is installed and accessible in PATH"
    exit 1
fi

echo "✓ Found Ollama version: $OLLAMA_VERSION"

OLLAMA_BIN_DIR="/opt/homebrew/Cellar/ollama/${OLLAMA_VERSION}/bin"

echo "🔍 Checking Ollama bin directory..."
if [ ! -d "$OLLAMA_BIN_DIR" ]; then
    echo "❌ Error: Ollama bin directory not found: $OLLAMA_BIN_DIR"
    exit 1
fi
echo "✓ Found: $OLLAMA_BIN_DIR"

echo "🔍 Checking for MLX-C library..."
if [ ! -f "/opt/homebrew/lib/libmlxc.dylib" ]; then
    echo "❌ Error: libmlxc.dylib not found in /opt/homebrew/lib/"
    echo "   Install it with: brew install mlx-c"
    exit 1
fi
echo "✓ Found: /opt/homebrew/lib/libmlxc.dylib"

echo ""
echo "🔗 Creating symlink for Ollama $OLLAMA_VERSION..."
ln -sf /opt/homebrew/lib/libmlxc.dylib "$OLLAMA_BIN_DIR/libmlxc.dylib"

if [ -L "$OLLAMA_BIN_DIR/libmlxc.dylib" ]; then
    echo "✅ Successfully linked libmlxc.dylib to $OLLAMA_BIN_DIR"
    echo ""
    echo "🧪 Verifying fix..."
    echo ""

    # Check if warning appears
    if ollama --version 2>&1 | grep -qi "mlx.*warn"; then
        echo "⚠️  Warning: MLX warning still appears"
        echo "   The symlink was created but Ollama may still show warnings"
    else
        echo "✅ Success! MLX warning is gone"
        echo ""
        echo "   Ollama can now use MLX for GPU acceleration on Apple Silicon"
    fi
else
    echo "❌ Failed to create symlink"
    exit 1
fi

echo ""
echo "📝 Note: This fix will need to be reapplied after 'brew upgrade ollama'"
echo "   Just run this script again: ./scripts/fix-ollama-mlx.sh"
