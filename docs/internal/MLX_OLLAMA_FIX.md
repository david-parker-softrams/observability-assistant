# MLX Dynamic Library Fix for Ollama

## Problem

When running Ollama on macOS with Apple Silicon, you may see this warning:

```
WARN MLX dynamic library not available error="failed to load MLX dynamic library (searched: [/opt/homebrew/Cellar/ollama/0.16.2/bin /Users/David.Parker/src/observability-assistant/build/lib/ollama])"
```

## Root Cause

- Ollama searches for `libmlxc.dylib` (MLX C bindings) in its own bin directory
- Homebrew installs MLX-C to `/opt/homebrew/lib/` (the standard library location)
- Ollama doesn't check standard library paths, so it can't find the library
- This prevents Ollama from using MLX GPU acceleration on Apple Silicon

## Solution

We provide a helper script that creates a symlink to the MLX-C library in Ollama's bin directory.

### Quick Fix (One-Time)

```bash
./scripts/fix-ollama-mlx.sh
```

### What It Does

The script:
1. Detects your current Ollama version
2. Checks that MLX-C is installed (`libmlxc.dylib`)
3. Creates a symlink: `/opt/homebrew/Cellar/ollama/{version}/bin/libmlxc.dylib` → `/opt/homebrew/lib/libmlxc.dylib`
4. Verifies the fix worked

### Prerequisites

Make sure MLX-C is installed:

```bash
brew install mlx-c
```

## Maintenance

⚠️ **Important:** This fix needs to be reapplied after each Ollama upgrade via Homebrew.

After running `brew upgrade ollama`, simply run:

```bash
./scripts/fix-ollama-mlx.sh
```

## Verification

Check that the warning is gone:

```bash
ollama --version
```

You should see only:
```
ollama version is 0.16.2
```

No MLX warning should appear.

## What is MLX?

MLX is Apple's machine learning framework optimized for Apple Silicon (M1/M2/M3/M4 chips). When enabled, Ollama can use MLX to accelerate model inference using the Metal GPU backend.

### Benefits

- ✅ **GPU Acceleration** - Uses Metal for faster inference
- ✅ **Better Performance** - Especially for image generation and certain text models
- ✅ **Lower CPU Usage** - Offloads work to the Neural Engine and GPU

### Requirements

- **Hardware:** Apple Silicon Mac (M1 or newer)
- **OS:** macOS 14.0 (Sonoma) or later recommended
- **Software:** MLX-C library installed via Homebrew

## Alternative Solutions

If the script doesn't work or you prefer manual installation:

### Manual Symlink Creation

```bash
# Replace 0.16.2 with your Ollama version
ln -sf /opt/homebrew/lib/libmlxc.dylib /opt/homebrew/Cellar/ollama/0.16.2/bin/libmlxc.dylib
```

### Use Official Ollama.app

Download from [ollama.com](https://ollama.com) - the official app bundles MLX libraries and doesn't have this issue.

## Troubleshooting

### Script says "libmlxc.dylib not found"

Install MLX-C:
```bash
brew install mlx-c
```

### Script says "Could not determine Ollama version"

Make sure Ollama is installed and in your PATH:
```bash
which ollama
ollama --version
```

### Warning still appears after fix

1. Restart any running Ollama processes:
   ```bash
   pkill ollama
   ollama serve
   ```

2. Check that the symlink was created:
   ```bash
   ls -la /opt/homebrew/Cellar/ollama/*/bin/libmlxc.dylib
   ```

3. Verify MLX-C is installed:
   ```bash
   ls -la /opt/homebrew/lib/libmlxc.dylib
   ```

## References

- [Ollama GitHub](https://github.com/ollama/ollama)
- [MLX GitHub](https://github.com/ml-explore/mlx)
- [MLX-C GitHub](https://github.com/ml-explore/mlx-c)
- Investigation report: `george-scratch/mlx-ollama-investigation.md` (if created)

## Status

- ✅ **Fixed:** 2026-02-18
- **Ollama Version:** 0.16.2
- **MLX-C Version:** 0.5.0
- **System:** macOS with Apple Silicon
