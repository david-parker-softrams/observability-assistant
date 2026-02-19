# Design Document: Externalize Model Configuration to YAML Files

**Author:** Saanvi (Senior Software Architect)
**Date:** 2026-02-17
**Status:** Ready for Implementation
**Requirements:** `/george-scratch/requirements-model-config-externalization.md`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Config File Schema](#3-config-file-schema)
4. [ModelConfigLoader Class Design](#4-modelconfigloader-class-design)
5. [Load Order and Precedence Rules](#5-load-order-and-precedence-rules)
6. [TokenCounter Integration](#6-tokencounter-integration)
7. [Caching Strategy](#7-caching-strategy)
8. [Error Handling Strategy](#8-error-handling-strategy)
9. [Security Considerations](#9-security-considerations)
10. [Backward Compatibility](#10-backward-compatibility)
11. [File Structure](#11-file-structure)
12. [Code Examples](#12-code-examples)
13. [Testing Strategy](#13-testing-strategy)
14. [Implementation Checklist](#14-implementation-checklist)

---

## 1. Executive Summary

This design document details the architecture for externalizing model-specific configurations (context windows, tokenizer encodings) from hardcoded Python dictionaries to YAML configuration files. The design prioritizes:

- **Zero-friction user experience**: Works out of the box with no configuration required
- **Extensibility**: Users can add custom models without code changes
- **Safety**: Graceful fallbacks ensure the system always works
- **Performance**: Single load at startup with efficient caching
- **Maintainability**: Clean separation of concerns

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config format | YAML | Human-readable, supports comments, no code execution |
| Load strategy | Eager (startup) | Avoid latency during token counting operations |
| Merge strategy | Deep merge with user precedence | Users can override specific fields without redefining entire models |
| Error handling | Graceful fallback to hardcoded | Never break existing functionality |
| Caching | Module-level singleton | One load per process, thread-safe reads |

---

## 2. Architecture Overview

### Component Diagram

```
                                    ┌─────────────────────────┐
                                    │   ~/.logai/             │
                                    │   model_config.yaml     │
                                    │   (User Overrides)      │
                                    └───────────┬─────────────┘
                                                │
                                                ▼
┌─────────────────┐      ┌──────────────────────────────────────────┐
│                 │      │         ModelConfigLoader                 │
│  TokenCounter   │─────▶│  ┌────────────────────────────────────┐  │
│                 │      │  │ load_config()                      │  │
│  - count_tokens │      │  │   1. Load default_models.yaml      │  │
│  - get_context  │      │  │   2. Load user config (if exists)  │  │
│    _window      │      │  │   3. Deep merge (user wins)        │  │
│  - _get_encoding│      │  │   4. Validate schema               │  │
└─────────────────┘      │  │   5. Cache result                  │  │
                         │  └────────────────────────────────────┘  │
                         │                                          │
                         │  ┌────────────────────────────────────┐  │
                         │  │ get_model_config(model_name)       │  │
                         │  │   - Substring matching             │  │
                         │  │   - Returns ModelConfig dataclass  │  │
                         │  └────────────────────────────────────┘  │
                         │                                          │
                         │  ┌────────────────────────────────────┐  │
                         │  │ get_context_window(model_name)     │  │
                         │  │ get_encoding(model_name)           │  │
                         │  │   - Convenience methods            │  │
                         │  └────────────────────────────────────┘  │
                         └──────────────────────────────────────────┘
                                                ▲
                                                │
                                    ┌───────────┴─────────────┐
                                    │   src/logai/config/     │
                                    │   default_models.yaml   │
                                    │   (Built-in Defaults)   │
                                    └─────────────────────────┘
```

### Data Flow

```
Startup
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  1. ModelConfigLoader.load() called (lazy, on first access)      │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. Load src/logai/config/default_models.yaml                    │
│     └─ If missing/invalid: Use HARDCODED_DEFAULTS                │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. Check for ~/.logai/model_config.yaml                         │
│     └─ If exists: Load and validate                              │
│     └─ If invalid: Log warning, skip user config                 │
│     └─ If missing: Continue with defaults only                   │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  4. Deep merge: user config over defaults                        │
│     └─ User models added to model list                           │
│     └─ User overrides replace default values                     │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  5. Cache merged config in module-level singleton                │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
Runtime (TokenCounter.get_context_window("qwen3:32b"))
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│  6. ModelConfigLoader.get_context_window("qwen3:32b")            │
│     └─ Iterate model patterns                                    │
│     └─ "qwen3" matches "qwen3:32b" (substring)                   │
│     └─ Return 32768 (or user override if defined)                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Config File Schema

### YAML Schema Definition

```yaml
# Schema version for future compatibility
schema_version: "1.0"

# Model-specific configurations
# Keys are model name patterns (substring matching)
models:
  <model-pattern>:
    context_window: <integer>      # Required: Max tokens in context
    encoding: <string>             # Optional: tiktoken encoding name
    chars_per_token: <float>       # Optional: Fallback estimation ratio
    # Future extensibility: additional fields can be added

# Default values for models not in the list
defaults:
  context_window: <integer>        # Required: Default context window
  encoding: <string>               # Required: Default encoding
  chars_per_token: <float>         # Optional: Default estimation ratio
```

### Example: default_models.yaml

```yaml
# LogAI Model Configuration - Built-in Defaults
# DO NOT EDIT - Create ~/.logai/model_config.yaml for custom settings
#
# Schema version for future compatibility
schema_version: "1.0"

models:
  # ===================
  # OpenAI Models
  # ===================
  gpt-4:
    context_window: 8192
    encoding: cl100k_base

  gpt-4-turbo:
    context_window: 128000
    encoding: cl100k_base

  gpt-4o:
    context_window: 128000
    encoding: o200k_base

  # ===================
  # Anthropic Models
  # ===================
  claude-3-5-sonnet:
    context_window: 200000
    encoding: cl100k_base

  claude-3-opus:
    context_window: 200000
    encoding: cl100k_base

  claude-opus-4:
    context_window: 200000
    encoding: cl100k_base

  claude-sonnet-4:
    context_window: 200000
    encoding: cl100k_base

  # Generic claude pattern (matches claude-*, including github-copilot variants)
  claude:
    encoding: cl100k_base

  # ===================
  # GitHub Copilot
  # ===================
  github-copilot:
    encoding: cl100k_base

  # ===================
  # Local Ollama Models
  # ===================
  llama3.1:8b:
    context_window: 8192
    encoding: cl100k_base

  llama3.1:70b:
    context_window: 128000
    encoding: cl100k_base

  llama3.1:
    context_window: 8192
    encoding: cl100k_base

  qwen3:
    context_window: 32768
    encoding: cl100k_base

  mistral:
    context_window: 32768
    encoding: cl100k_base

  codellama:
    context_window: 16384
    encoding: cl100k_base

# Default values for unknown models
defaults:
  context_window: 8192
  encoding: cl100k_base
  chars_per_token: 3.5
```

### Example: User Override (~/.logai/model_config.yaml)

```yaml
# User Model Configuration for LogAI
# This file overrides built-in defaults
#
# Tip: Only include models you want to override or add
# All built-in models remain available

schema_version: "1.0"

models:
  # Override existing model
  qwen3:
    context_window: 65536  # Upgraded to larger context

  # Add custom model
  my-custom-llama:
    context_window: 32768
    encoding: cl100k_base

  # Add company-specific model
  internal-gpt-fine-tuned:
    context_window: 16384
    encoding: cl100k_base

# Optionally override defaults for truly unknown models
defaults:
  context_window: 16384  # Assume larger default for modern models
```

### Schema Validation Rules

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `schema_version` | string | No | Semantic version (e.g., "1.0") |
| `models` | dict | Yes | Non-empty if present |
| `models.<name>.context_window` | int | No* | > 0, <= 2,000,000 |
| `models.<name>.encoding` | string | No | Valid tiktoken encoding or custom |
| `models.<name>.chars_per_token` | float | No | > 0, <= 10.0 |
| `defaults.context_window` | int | Yes | > 0, <= 2,000,000 |
| `defaults.encoding` | string | Yes | Valid tiktoken encoding |
| `defaults.chars_per_token` | float | No | > 0, <= 10.0 |

*At least one of `context_window` or `encoding` should be present for a model entry to be meaningful.

---

## 4. ModelConfigLoader Class Design

### Class Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      ModelConfigLoader                           │
├─────────────────────────────────────────────────────────────────┤
│ Class Attributes:                                                │
│   _instance: ModelConfigLoader | None    # Singleton instance    │
│   _config: ModelConfigData | None        # Cached config         │
│   _loaded: bool                          # Load status           │
├─────────────────────────────────────────────────────────────────┤
│ Constants:                                                       │
│   DEFAULT_CONFIG_PATH: Path              # Built-in defaults     │
│   USER_CONFIG_PATH: Path                 # User overrides        │
│   HARDCODED_DEFAULTS: dict               # Ultimate fallback     │
├─────────────────────────────────────────────────────────────────┤
│ Methods:                                                         │
│   + load() -> ModelConfigData            # Load and cache        │
│   + reload() -> ModelConfigData          # Force reload          │
│   + get_model_config(model: str)         # Get config for model  │
│     -> ModelConfig                                               │
│   + get_context_window(model: str) -> int                        │
│   + get_encoding(model: str) -> str | None                       │
│   + get_all_models() -> dict[str, ModelConfig]                   │
│   + is_loaded() -> bool                                          │
├─────────────────────────────────────────────────────────────────┤
│ Private Methods:                                                 │
│   - _load_yaml_file(path: Path) -> dict | None                   │
│   - _validate_config(data: dict) -> ValidationResult             │
│   - _merge_configs(base: dict, override: dict) -> dict           │
│   - _match_model(model: str) -> str | None                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       ModelConfig                                │
├─────────────────────────────────────────────────────────────────┤
│ @dataclass(frozen=True)                                          │
│                                                                  │
│   context_window: int                                            │
│   encoding: str | None                                           │
│   chars_per_token: float                                         │
│   source: str           # "default", "builtin", "user"           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     ModelConfigData                              │
├─────────────────────────────────────────────────────────────────┤
│ @dataclass                                                       │
│                                                                  │
│   models: dict[str, ModelConfig]                                 │
│   defaults: ModelConfig                                          │
│   schema_version: str                                            │
│   sources: list[str]    # Ordered list of loaded config paths    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ValidationResult                              │
├─────────────────────────────────────────────────────────────────┤
│ @dataclass                                                       │
│                                                                  │
│   valid: bool                                                    │
│   errors: list[str]                                              │
│   warnings: list[str]                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Interface Specification

```python
"""Model configuration loader for token counting and context management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a single model."""

    context_window: int
    encoding: str | None = None
    chars_per_token: float = 3.5
    source: str = "default"  # "default", "builtin", "user"


@dataclass
class ModelConfigData:
    """Complete model configuration data."""

    models: dict[str, ModelConfig] = field(default_factory=dict)
    defaults: ModelConfig = field(
        default_factory=lambda: ModelConfig(context_window=8192, encoding="cl100k_base")
    )
    schema_version: str = "1.0"
    sources: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of config validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ModelConfigLoader:
    """
    Loads and manages model configurations from YAML files.

    Load order:
    1. Built-in defaults (src/logai/config/default_models.yaml)
    2. User overrides (~/.logai/model_config.yaml)

    User configs are merged on top of defaults. If all configs fail to load,
    falls back to hardcoded defaults to ensure the system always works.

    Usage:
        # Get singleton instance (auto-loads on first access)
        loader = ModelConfigLoader.get_instance()

        # Get context window for a model
        window = loader.get_context_window("claude-3-5-sonnet")

        # Get full config
        config = loader.get_model_config("gpt-4-turbo")
        print(f"Window: {config.context_window}, Source: {config.source}")

    Thread Safety:
        Read operations are thread-safe after initial load.
        reload() should only be called from a single thread.
    """

    # Singleton instance
    _instance: "ModelConfigLoader | None" = None

    # Paths
    DEFAULT_CONFIG_PATH: Path = Path(__file__).parent / "default_models.yaml"
    USER_CONFIG_PATH: Path = Path.home() / ".logai" / "model_config.yaml"

    # Ultimate fallback (hardcoded) - matches current token_counter.py
    HARDCODED_DEFAULTS: dict[str, Any] = {
        "models": {
            "gpt-4-turbo": {"context_window": 128_000, "encoding": "cl100k_base"},
            "gpt-4o": {"context_window": 128_000, "encoding": "o200k_base"},
            "gpt-4": {"context_window": 8_192, "encoding": "cl100k_base"},
            "claude-3-5-sonnet": {"context_window": 200_000, "encoding": "cl100k_base"},
            "claude-3-opus": {"context_window": 200_000, "encoding": "cl100k_base"},
            "claude-opus-4": {"context_window": 200_000, "encoding": "cl100k_base"},
            "claude-sonnet-4": {"context_window": 200_000, "encoding": "cl100k_base"},
            "claude": {"encoding": "cl100k_base"},
            "github-copilot": {"encoding": "cl100k_base"},
            "llama3.1:8b": {"context_window": 8_192, "encoding": "cl100k_base"},
            "llama3.1:70b": {"context_window": 128_000, "encoding": "cl100k_base"},
            "qwen3": {"context_window": 32_768, "encoding": "cl100k_base"},
        },
        "defaults": {
            "context_window": 8_192,
            "encoding": "cl100k_base",
            "chars_per_token": 3.5,
        },
    }

    def __init__(self) -> None:
        """Initialize loader (use get_instance() for singleton access)."""
        self._config: ModelConfigData | None = None
        self._loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ModelConfigLoader":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing only)."""
        cls._instance = None

    def load(self) -> ModelConfigData:
        """
        Load configuration from files.

        Returns cached config if already loaded. Use reload() to force refresh.

        Returns:
            ModelConfigData with merged configuration
        """
        if self._loaded and self._config is not None:
            return self._config

        return self._do_load()

    def reload(self) -> ModelConfigData:
        """
        Force reload configuration from files.

        Returns:
            ModelConfigData with fresh configuration
        """
        self._loaded = False
        self._config = None
        return self._do_load()

    def _do_load(self) -> ModelConfigData:
        """Internal load implementation."""
        sources: list[str] = []
        merged_data: dict[str, Any] = {}

        # Step 1: Load built-in defaults
        default_data = self._load_yaml_file(self.DEFAULT_CONFIG_PATH)
        if default_data is not None:
            validation = self._validate_config(default_data)
            if validation.valid:
                merged_data = default_data
                sources.append(str(self.DEFAULT_CONFIG_PATH))
                for warning in validation.warnings:
                    logger.warning(f"Default config warning: {warning}")
            else:
                for error in validation.errors:
                    logger.error(f"Default config error: {error}")
                logger.warning("Using hardcoded defaults due to invalid default config")
        else:
            logger.info("No default config file found, using hardcoded defaults")

        # If no valid defaults loaded, use hardcoded
        if not merged_data:
            merged_data = self.HARDCODED_DEFAULTS.copy()
            sources.append("hardcoded")

        # Step 2: Load user overrides
        if self.USER_CONFIG_PATH.exists():
            user_data = self._load_yaml_file(self.USER_CONFIG_PATH)
            if user_data is not None:
                validation = self._validate_config(user_data, is_user_config=True)
                if validation.valid:
                    merged_data = self._merge_configs(merged_data, user_data)
                    sources.append(str(self.USER_CONFIG_PATH))
                    for warning in validation.warnings:
                        logger.warning(f"User config warning: {warning}")
                    logger.info(f"Loaded user config from {self.USER_CONFIG_PATH}")
                else:
                    for error in validation.errors:
                        logger.warning(f"User config error: {error}")
                    logger.warning("Ignoring invalid user config")

        # Step 3: Convert to ModelConfigData
        self._config = self._build_config_data(merged_data, sources)
        self._loaded = True

        logger.debug(f"Model config loaded from: {', '.join(sources)}")
        logger.debug(f"Total models configured: {len(self._config.models)}")

        return self._config

    def get_model_config(self, model: str) -> ModelConfig:
        """
        Get configuration for a specific model.

        Uses substring matching: "qwen3" matches "qwen3:32b", "qwen3:70b", etc.
        First match wins, so more specific patterns should come first in config.

        Args:
            model: Model name to look up

        Returns:
            ModelConfig for the model (or defaults if no match)
        """
        config = self.load()
        model_lower = model.lower()

        # Check for exact match first
        if model_lower in config.models:
            return config.models[model_lower]

        # Substring matching (first match wins)
        for pattern, model_config in config.models.items():
            if pattern in model_lower:
                return model_config

        # Return defaults
        return config.defaults

    def get_context_window(self, model: str) -> int:
        """Get context window size for a model."""
        return self.get_model_config(model).context_window

    def get_encoding(self, model: str) -> str | None:
        """Get tiktoken encoding name for a model."""
        return self.get_model_config(model).encoding

    def get_chars_per_token(self, model: str) -> float:
        """Get chars per token ratio for fallback estimation."""
        return self.get_model_config(model).chars_per_token

    def get_all_models(self) -> dict[str, ModelConfig]:
        """Get all configured models."""
        return self.load().models.copy()

    def is_loaded(self) -> bool:
        """Check if config has been loaded."""
        return self._loaded

    def get_sources(self) -> list[str]:
        """Get list of config sources that were loaded."""
        config = self.load()
        return config.sources.copy()

    # --- Private methods ---

    def _load_yaml_file(self, path: Path) -> dict[str, Any] | None:
        """
        Safely load a YAML file.

        Uses yaml.safe_load() to prevent code execution.

        Args:
            path: Path to YAML file

        Returns:
            Parsed dict or None if file doesn't exist or is invalid
        """
        if not path.exists():
            return None

        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                logger.warning(f"Config file {path} does not contain a valid YAML dict")
                return None

            return data

        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML file {path}: {e}")
            return None
        except PermissionError:
            logger.warning(f"Permission denied reading {path}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error reading {path}: {e}")
            return None

    def _validate_config(
        self, data: dict[str, Any], is_user_config: bool = False
    ) -> ValidationResult:
        """
        Validate configuration structure and values.

        Args:
            data: Parsed YAML data
            is_user_config: If True, use relaxed validation (partial configs OK)

        Returns:
            ValidationResult with errors and warnings
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check schema version
        if "schema_version" in data:
            version = data["schema_version"]
            if not isinstance(version, str):
                warnings.append("schema_version should be a string")
            elif version not in ("1.0", "1"):
                warnings.append(f"Unknown schema version: {version}")

        # Validate models section
        if "models" in data:
            if not isinstance(data["models"], dict):
                errors.append("'models' must be a dictionary")
            else:
                for model_name, model_data in data["models"].items():
                    if not isinstance(model_data, dict):
                        errors.append(f"Model '{model_name}' must be a dictionary")
                        continue

                    # Validate context_window
                    if "context_window" in model_data:
                        window = model_data["context_window"]
                        if not isinstance(window, int) or window <= 0:
                            errors.append(
                                f"Model '{model_name}': context_window must be positive int"
                            )
                        elif window > 2_000_000:
                            warnings.append(
                                f"Model '{model_name}': context_window unusually large: {window}"
                            )

                    # Validate encoding
                    if "encoding" in model_data:
                        encoding = model_data["encoding"]
                        if not isinstance(encoding, str):
                            errors.append(f"Model '{model_name}': encoding must be string")
                        elif encoding not in self._get_known_encodings():
                            warnings.append(
                                f"Model '{model_name}': unknown encoding '{encoding}'"
                            )

                    # Validate chars_per_token
                    if "chars_per_token" in model_data:
                        cpt = model_data["chars_per_token"]
                        if not isinstance(cpt, (int, float)) or cpt <= 0:
                            errors.append(
                                f"Model '{model_name}': chars_per_token must be positive"
                            )
                        elif cpt > 10.0:
                            warnings.append(
                                f"Model '{model_name}': chars_per_token unusually high: {cpt}"
                            )
        elif not is_user_config:
            errors.append("'models' section is required")

        # Validate defaults section
        if "defaults" in data:
            defaults = data["defaults"]
            if not isinstance(defaults, dict):
                errors.append("'defaults' must be a dictionary")
            else:
                if "context_window" not in defaults and not is_user_config:
                    errors.append("defaults.context_window is required")
                elif "context_window" in defaults:
                    window = defaults["context_window"]
                    if not isinstance(window, int) or window <= 0:
                        errors.append("defaults.context_window must be positive int")

                if "encoding" not in defaults and not is_user_config:
                    errors.append("defaults.encoding is required")
                elif "encoding" in defaults:
                    if not isinstance(defaults["encoding"], str):
                        errors.append("defaults.encoding must be string")
        elif not is_user_config:
            errors.append("'defaults' section is required")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _merge_configs(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge override config on top of base config.

        Args:
            base: Base configuration (defaults)
            override: Override configuration (user)

        Returns:
            Merged configuration dict
        """
        result = base.copy()

        # Merge models
        if "models" in override:
            if "models" not in result:
                result["models"] = {}

            for model_name, model_data in override["models"].items():
                if model_name in result["models"]:
                    # Merge individual model fields
                    result["models"][model_name] = {
                        **result["models"][model_name],
                        **model_data,
                    }
                else:
                    # Add new model
                    result["models"][model_name] = model_data

        # Merge defaults
        if "defaults" in override:
            if "defaults" not in result:
                result["defaults"] = {}
            result["defaults"] = {**result["defaults"], **override["defaults"]}

        # Override schema version if present
        if "schema_version" in override:
            result["schema_version"] = override["schema_version"]

        return result

    def _build_config_data(
        self, data: dict[str, Any], sources: list[str]
    ) -> ModelConfigData:
        """Convert raw dict to ModelConfigData."""
        defaults_data = data.get("defaults", {})
        defaults = ModelConfig(
            context_window=defaults_data.get("context_window", 8192),
            encoding=defaults_data.get("encoding", "cl100k_base"),
            chars_per_token=defaults_data.get("chars_per_token", 3.5),
            source="default",
        )

        models: dict[str, ModelConfig] = {}
        models_data = data.get("models", {})

        # Determine if this model came from user config
        has_user_config = any("model_config.yaml" in s for s in sources)

        for name, model_data in models_data.items():
            # Determine source for this model
            # (simplified: mark all as "user" if user config was loaded)
            source = "user" if has_user_config else "builtin"

            models[name.lower()] = ModelConfig(
                context_window=model_data.get("context_window", defaults.context_window),
                encoding=model_data.get("encoding", defaults.encoding),
                chars_per_token=model_data.get("chars_per_token", defaults.chars_per_token),
                source=source,
            )

        return ModelConfigData(
            models=models,
            defaults=defaults,
            schema_version=data.get("schema_version", "1.0"),
            sources=sources,
        )

    def _get_known_encodings(self) -> set[str]:
        """Get set of known tiktoken encodings."""
        return {
            "cl100k_base",  # GPT-4, Claude approximation
            "o200k_base",   # GPT-4o
            "p50k_base",    # GPT-3.5
            "r50k_base",    # GPT-3
            "gpt2",         # Legacy
        }


# Module-level convenience functions
def get_model_config_loader() -> ModelConfigLoader:
    """Get the singleton ModelConfigLoader instance."""
    return ModelConfigLoader.get_instance()


def get_context_window(model: str) -> int:
    """Convenience function to get context window for a model."""
    return get_model_config_loader().get_context_window(model)


def get_encoding(model: str) -> str | None:
    """Convenience function to get encoding for a model."""
    return get_model_config_loader().get_encoding(model)
```

---

## 5. Load Order and Precedence Rules

### Load Order

```
Priority (lowest to highest):
   1. Hardcoded defaults (HARDCODED_DEFAULTS in code)     [FALLBACK]
   2. Built-in defaults (src/logai/config/default_models.yaml)
   3. User overrides (~/.logai/model_config.yaml)         [HIGHEST]
```

### Precedence Rules

| Scenario | Result |
|----------|--------|
| User defines model not in defaults | Model added with user values |
| User overrides existing model's `context_window` | User value used, other fields from defaults |
| User provides empty value | Empty value wins (explicit override) |
| User omits a field | Default value used |
| Built-in file missing | Hardcoded defaults used |
| User file has invalid YAML | User file ignored, warning logged |
| Both files missing/invalid | Hardcoded defaults used |

### Merge Example

```yaml
# Built-in default_models.yaml
models:
  qwen3:
    context_window: 32768
    encoding: cl100k_base

# User model_config.yaml
models:
  qwen3:
    context_window: 65536
    # encoding not specified

# Merged result
models:
  qwen3:
    context_window: 65536    # From user (override)
    encoding: cl100k_base    # From default (preserved)
    source: "user"
```

---

## 6. TokenCounter Integration

### Modified TokenCounter Class

```python
"""Token counting utilities for context management."""

import json
import logging
from typing import Any

from logai.config.model_config import get_model_config_loader, ModelConfigLoader

logger = logging.getLogger(__name__)

# Lazy load tiktoken to avoid startup cost
_tokenizer_cache: dict[str, Any] = {}


class TokenCounter:
    """
    Fast, accurate token counting for LLM context management.

    Uses tiktoken for OpenAI/Claude models with fallback heuristics
    for unsupported models. All methods are class methods for ease of use.

    Model configurations are loaded from YAML files:
    - Built-in: src/logai/config/default_models.yaml
    - User overrides: ~/.logai/model_config.yaml

    Performance: <1ms for typical content, <10ms for very large content (500KB)
    Accuracy: Within ±5% for supported models
    """

    # Reference to config loader (allows injection for testing)
    _config_loader: ModelConfigLoader | None = None

    @classmethod
    def _get_config_loader(cls) -> ModelConfigLoader:
        """Get or create the model config loader."""
        if cls._config_loader is None:
            cls._config_loader = get_model_config_loader()
        return cls._config_loader

    @classmethod
    def _set_config_loader(cls, loader: ModelConfigLoader | None) -> None:
        """Set custom config loader (for testing)."""
        cls._config_loader = loader

    @classmethod
    def _get_encoding(cls, model: str) -> Any:
        """
        Get or create tokenizer encoding for a model.

        Uses lazy loading and caching for performance.

        Args:
            model: Model name or identifier

        Returns:
            tiktoken Encoding object or None if unavailable
        """
        # Check cache first
        if model in _tokenizer_cache:
            return _tokenizer_cache[model]

        # Get encoding name from config
        loader = cls._get_config_loader()
        encoding_name = loader.get_encoding(model)

        if encoding_name is None:
            _tokenizer_cache[model] = None
            return None

        try:
            import tiktoken

            encoding = tiktoken.get_encoding(encoding_name)
            _tokenizer_cache[model] = encoding
            return encoding
        except ImportError:
            logger.warning("tiktoken not installed, using character-based estimation")
            _tokenizer_cache[model] = None
            return None
        except Exception as e:
            logger.warning(f"Failed to load tokenizer for {model}: {e}")
            _tokenizer_cache[model] = None
            return None

    @classmethod
    def count_tokens(cls, text: str, model: str = "claude-3-5-sonnet") -> int:
        """
        Count tokens in text for a specific model.

        Args:
            text: Text to count tokens for
            model: Model name (used to select tokenizer)

        Returns:
            Estimated token count

        Performance: <1ms for typical content
        """
        if not text:
            return 0

        encoding = cls._get_encoding(model)

        if encoding is not None:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed, using fallback: {e}")

        # Fallback: character-based estimation
        loader = cls._get_config_loader()
        chars_per_token = loader.get_chars_per_token(model)
        return int(len(text) / chars_per_token) + 1

    @classmethod
    def get_context_window(cls, model: str) -> int:
        """
        Get context window size for a model.

        Args:
            model: Model name

        Returns:
            Context window size in tokens
        """
        loader = cls._get_config_loader()
        return loader.get_context_window(model)

    # ... rest of methods remain unchanged ...
```

### Key Integration Points

1. **Lazy Loading**: Config is loaded on first access to `_get_config_loader()`
2. **Testability**: `_set_config_loader()` allows injecting mock for tests
3. **Backward Compatibility**: API unchanged, behavior identical
4. **Removed Hardcoded Dicts**: `MODEL_ENCODINGS` and `CONTEXT_WINDOWS` removed from class

---

## 7. Caching Strategy

### Module-Level Singleton

```python
# Single instance per process
_loader_instance: ModelConfigLoader | None = None

def get_model_config_loader() -> ModelConfigLoader:
    """Get the singleton ModelConfigLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ModelConfigLoader()
        _loader_instance.load()  # Eager load
    return _loader_instance
```

### Caching Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        Layer 1: Singleton                        │
│  ModelConfigLoader._instance (class-level)                       │
│  - One instance per process                                      │
│  - Created on first get_instance() call                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Layer 2: Config Cache                       │
│  ModelConfigLoader._config (instance-level)                      │
│  - Cached after first load()                                     │
│  - Invalidated only by reload()                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 3: Tokenizer Cache                      │
│  _tokenizer_cache (module-level dict)                            │
│  - Caches tiktoken Encoding objects                              │
│  - Key: model name                                               │
│  - Never invalidated (tokenizers don't change)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Performance Characteristics

| Operation | Complexity | Typical Time |
|-----------|------------|--------------|
| First load() | O(n) where n = models in config | ~5ms |
| Subsequent load() | O(1) - returns cached | <0.01ms |
| get_context_window() | O(m) where m = model patterns | <0.1ms |
| get_encoding() | O(m) where m = model patterns | <0.1ms |
| count_tokens() (cached) | O(len(text)) | <1ms for typical |

### Thread Safety

- **Read operations**: Thread-safe (immutable ModelConfig objects)
- **load()**: Thread-safe (returns cached after first call)
- **reload()**: NOT thread-safe (should only be called at startup or in tests)

---

## 8. Error Handling Strategy

### Error Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                     Error Category                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. FILE ERRORS (Non-fatal)                                      │
│     ├─ File not found → Use next layer of defaults               │
│     ├─ Permission denied → Log warning, use defaults             │
│     └─ I/O error → Log warning, use defaults                     │
│                                                                  │
│  2. PARSE ERRORS (Non-fatal)                                     │
│     ├─ Invalid YAML syntax → Log warning, skip file              │
│     ├─ Not a dict at root → Log warning, skip file               │
│     └─ Encoding error → Log warning, skip file                   │
│                                                                  │
│  3. VALIDATION ERRORS (Logged, continue with valid parts)        │
│     ├─ Invalid context_window → Use default for that model       │
│     ├─ Invalid encoding → Use default for that model             │
│     ├─ Missing required field → Use hardcoded default            │
│     └─ Unknown schema_version → Log warning, continue            │
│                                                                  │
│  4. RUNTIME ERRORS (Graceful degradation)                        │
│     ├─ tiktoken import error → Use char-based estimation         │
│     ├─ Unknown encoding name → Fall back to default              │
│     └─ Memory error → Log error, use hardcoded defaults          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Error Handling Code Example

```python
def _load_yaml_file(self, path: Path) -> dict[str, Any] | None:
    """Safely load YAML with comprehensive error handling."""
    if not path.exists():
        logger.debug(f"Config file not found: {path}")
        return None

    try:
        # Check file permissions
        if not os.access(path, os.R_OK):
            logger.warning(f"Permission denied reading config: {path}")
            return None

        # Check file size (prevent DoS)
        file_size = path.stat().st_size
        if file_size > 1_000_000:  # 1MB limit
            logger.warning(f"Config file too large ({file_size} bytes): {path}")
            return None

        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            logger.warning(f"Config file is empty: {path}")
            return None

        if not isinstance(data, dict):
            logger.warning(f"Config file root must be dict: {path}")
            return None

        return data

    except yaml.YAMLError as e:
        logger.warning(f"YAML parse error in {path}: {e}")
        return None
    except UnicodeDecodeError as e:
        logger.warning(f"Encoding error in {path}: {e}")
        return None
    except PermissionError:
        logger.warning(f"Permission denied: {path}")
        return None
    except OSError as e:
        logger.warning(f"I/O error reading {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading {path}: {e}")
        return None
```

### User-Facing Error Messages

| Error Scenario | Log Level | Message |
|----------------|-----------|---------|
| User config not found | DEBUG | "No user config at ~/.logai/model_config.yaml" |
| User config invalid YAML | WARNING | "Invalid YAML in user config: {details}. Using defaults." |
| Invalid context_window | WARNING | "Model 'xyz': invalid context_window. Using default." |
| Unknown encoding | WARNING | "Model 'xyz': unknown encoding 'abc'. May not work." |
| All configs failed | WARNING | "Using hardcoded model defaults." |

---

## 9. Security Considerations

### YAML Safe Loading

```python
# ALWAYS use safe_load, NEVER use load() or unsafe_load()
import yaml

# CORRECT - safe, no code execution
data = yaml.safe_load(file_content)

# DANGEROUS - allows arbitrary Python code execution
# data = yaml.load(file_content, Loader=yaml.FullLoader)  # DO NOT USE
# data = yaml.unsafe_load(file_content)                   # DO NOT USE
```

### Input Validation

```python
def _validate_config(self, data: dict[str, Any]) -> ValidationResult:
    """Validate all input before use."""

    # 1. Type validation
    if not isinstance(data, dict):
        return ValidationResult(valid=False, errors=["Root must be dict"])

    # 2. Value bounds
    if "context_window" in data:
        window = data["context_window"]
        if not isinstance(window, int):
            return ValidationResult(valid=False, errors=["context_window must be int"])
        if window <= 0 or window > 2_000_000:
            return ValidationResult(valid=False, errors=["context_window out of bounds"])

    # 3. String length limits
    if "encoding" in data:
        encoding = data["encoding"]
        if not isinstance(encoding, str):
            return ValidationResult(valid=False, errors=["encoding must be string"])
        if len(encoding) > 100:
            return ValidationResult(valid=False, errors=["encoding name too long"])

    # 4. Model name limits
    for model_name in data.get("models", {}):
        if len(model_name) > 200:
            return ValidationResult(valid=False, errors=["model name too long"])
```

### File Permission Checks

```python
def _check_file_permissions(self, path: Path) -> bool:
    """Check that file has safe permissions."""
    if not path.exists():
        return True  # File doesn't exist is OK

    # Check ownership (on Unix)
    if hasattr(os, 'getuid'):
        stat = path.stat()
        if stat.st_uid != os.getuid():
            logger.warning(f"Config file {path} not owned by current user")
            # Continue anyway, but log warning

    return True
```

### Defense in Depth

1. **safe_load()**: Prevents arbitrary code execution
2. **Type validation**: All values validated before use
3. **Bounds checking**: Numeric values constrained
4. **Size limits**: File size and string length limits
5. **Graceful degradation**: Invalid configs don't crash the system

---

## 10. Backward Compatibility

### Guarantee

> **All existing code continues to work unchanged.**

### Strategy

1. **API Preserved**: `TokenCounter.get_context_window()` signature unchanged
2. **Behavior Preserved**: Same results for same inputs
3. **Hardcoded Fallback**: If all else fails, use existing hardcoded values
4. **Optional Feature**: Config files are optional, not required

### Migration Path

```
Version 1.0 (Current)
├── Hardcoded in token_counter.py
└── Works as-is

Version 1.1 (This Feature)
├── Config files supported
├── Hardcoded values as fallback
├── No breaking changes
└── Existing code unchanged

Version 2.0 (Future)
├── Config file required (or auto-generated)
├── Hardcoded values removed
└── Migration guide provided
```

### Deprecation Timeline

| Version | Hardcoded Defaults | Config Files | Notes |
|---------|-------------------|--------------|-------|
| 1.0 | Primary | Not supported | Current |
| 1.1 | Fallback | Supported | This release |
| 1.2 | Fallback | Preferred | Docs updated |
| 2.0 | Removed | Required | Breaking change |

---

## 11. File Structure

### New Files

```
src/logai/config/
├── __init__.py              # Add exports
├── settings.py              # Existing
├── validation.py            # Existing
├── model_config.py          # NEW: ModelConfigLoader
└── default_models.yaml      # NEW: Built-in defaults

examples/
└── model_config.yaml.example  # NEW: Example user config

docs/user-guide/
└── custom-models.md         # NEW: Documentation

tests/unit/config/
└── test_model_config.py     # NEW: Unit tests
```

### Modified Files

```
src/logai/config/__init__.py
  + from .model_config import (
  +     ModelConfigLoader,
  +     get_model_config_loader,
  +     get_context_window,
  +     get_encoding,
  + )

src/logai/core/context/token_counter.py
  - Remove CONTEXT_WINDOWS dict
  - Remove MODEL_ENCODINGS dict
  + Import from model_config
  + Use ModelConfigLoader for lookups
```

### File Locations

| File | Purpose | Required |
|------|---------|----------|
| `src/logai/config/default_models.yaml` | Built-in defaults | Yes |
| `~/.logai/model_config.yaml` | User overrides | No |
| `src/logai/config/model_config.py` | Loader implementation | Yes |

---

## 12. Code Examples

### Example 1: Basic Usage

```python
# In any code that needs model config
from logai.config import get_context_window, get_encoding

# Get context window for a model
window = get_context_window("gpt-4-turbo")
print(f"GPT-4 Turbo context window: {window}")  # 128000

# Get encoding for token counting
encoding = get_encoding("claude-3-5-sonnet")
print(f"Claude encoding: {encoding}")  # cl100k_base

# Substring matching works automatically
window = get_context_window("qwen3:32b")  # Matches "qwen3" pattern
print(f"Qwen3:32b context window: {window}")  # 32768
```

### Example 2: Full Config Access

```python
from logai.config.model_config import get_model_config_loader

loader = get_model_config_loader()

# Get full config for a model
config = loader.get_model_config("claude-opus-4")
print(f"Context: {config.context_window}")
print(f"Encoding: {config.encoding}")
print(f"Source: {config.source}")  # "builtin" or "user"

# List all configured models
for name, cfg in loader.get_all_models().items():
    print(f"{name}: {cfg.context_window} tokens")

# Check which config files were loaded
print(f"Config sources: {loader.get_sources()}")
```

### Example 3: TokenCounter Integration

```python
from logai.core.context.token_counter import TokenCounter

# Count tokens (uses config internally)
text = "Hello, how can I help you today?"
tokens = TokenCounter.count_tokens(text, "claude-3-5-sonnet")
print(f"Token count: {tokens}")

# Get context window (now from config)
window = TokenCounter.get_context_window("gpt-4o")
print(f"Available context: {window}")

# Will fit check
will_fit = TokenCounter.will_fit(text, 10000, 128000, "gpt-4-turbo")
print(f"Will fit: {will_fit}")
```

### Example 4: User Config Override

```yaml
# ~/.logai/model_config.yaml
schema_version: "1.0"

models:
  # Override built-in model
  qwen3:
    context_window: 65536  # Upgraded version

  # Add completely new model
  my-company-llm:
    context_window: 32768
    encoding: cl100k_base

defaults:
  # Use larger default for unknown models
  context_window: 16384
```

```python
# Code automatically picks up the override
from logai.config import get_context_window

# Gets 65536 (user override) instead of 32768 (default)
window = get_context_window("qwen3:32b")
print(f"Qwen3 window: {window}")

# New model works too
window = get_context_window("my-company-llm")
print(f"My LLM window: {window}")
```

### Example 5: Error Handling

```python
from logai.config.model_config import ModelConfigLoader

loader = ModelConfigLoader()

try:
    config = loader.load()
    print(f"Loaded from: {config.sources}")
except Exception as e:
    # This should never happen - loader always returns valid config
    print(f"Unexpected error: {e}")

# Check if user config was loaded
if any("model_config.yaml" in s for s in config.sources):
    print("User config loaded successfully")
else:
    print("Using built-in defaults only")
```

### Example 6: Testing with Mock Config

```python
import pytest
from logai.config.model_config import ModelConfigLoader, ModelConfig, ModelConfigData
from logai.core.context.token_counter import TokenCounter


class TestTokenCounterWithMockConfig:
    """Test TokenCounter with custom config."""

    @pytest.fixture
    def mock_loader(self):
        """Create a mock config loader."""
        loader = ModelConfigLoader()
        loader._config = ModelConfigData(
            models={
                "test-model": ModelConfig(
                    context_window=10000,
                    encoding="cl100k_base",
                    source="test"
                )
            },
            defaults=ModelConfig(context_window=5000, encoding="cl100k_base"),
            sources=["test"],
        )
        loader._loaded = True
        return loader

    def test_custom_model(self, mock_loader):
        """Test with custom model config."""
        TokenCounter._set_config_loader(mock_loader)

        try:
            window = TokenCounter.get_context_window("test-model")
            assert window == 10000
        finally:
            TokenCounter._set_config_loader(None)
```

---

## 13. Testing Strategy

### Unit Tests

```python
# tests/unit/config/test_model_config.py

import pytest
from pathlib import Path
import tempfile
import yaml

from logai.config.model_config import (
    ModelConfigLoader,
    ModelConfig,
    ModelConfigData,
    ValidationResult,
)


class TestModelConfigLoader:
    """Unit tests for ModelConfigLoader."""

    @pytest.fixture
    def loader(self):
        """Create fresh loader for each test."""
        ModelConfigLoader.reset_instance()
        return ModelConfigLoader()

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory."""
        return tmp_path

    # --- Loading Tests ---

    def test_load_default_config(self, loader):
        """Test loading built-in default config."""
        config = loader.load()

        assert config is not None
        assert len(config.models) > 0
        assert config.defaults.context_window > 0

    def test_load_caches_result(self, loader):
        """Test that load() caches result."""
        config1 = loader.load()
        config2 = loader.load()

        assert config1 is config2

    def test_reload_refreshes_cache(self, loader):
        """Test that reload() refreshes cache."""
        config1 = loader.load()
        config2 = loader.reload()

        # New object, but same values
        assert config1 is not config2
        assert config1.defaults.context_window == config2.defaults.context_window

    def test_load_with_missing_default_file(self, loader, monkeypatch):
        """Test fallback when default config file missing."""
        monkeypatch.setattr(
            ModelConfigLoader,
            "DEFAULT_CONFIG_PATH",
            Path("/nonexistent/path.yaml")
        )

        config = loader.reload()

        # Should use hardcoded defaults
        assert "hardcoded" in config.sources
        assert config.defaults.context_window == 8192

    # --- User Config Tests ---

    def test_user_config_override(self, loader, temp_config_dir, monkeypatch):
        """Test user config overrides defaults."""
        user_config = temp_config_dir / "model_config.yaml"
        user_config.write_text(yaml.dump({
            "schema_version": "1.0",
            "models": {
                "qwen3": {"context_window": 99999}
            }
        }))

        monkeypatch.setattr(ModelConfigLoader, "USER_CONFIG_PATH", user_config)
        config = loader.reload()

        assert config.models["qwen3"].context_window == 99999

    def test_user_config_adds_new_model(self, loader, temp_config_dir, monkeypatch):
        """Test user config can add new models."""
        user_config = temp_config_dir / "model_config.yaml"
        user_config.write_text(yaml.dump({
            "schema_version": "1.0",
            "models": {
                "my-custom-model": {
                    "context_window": 50000,
                    "encoding": "cl100k_base"
                }
            }
        }))

        monkeypatch.setattr(ModelConfigLoader, "USER_CONFIG_PATH", user_config)
        config = loader.reload()

        assert "my-custom-model" in config.models
        assert config.models["my-custom-model"].context_window == 50000

    def test_invalid_user_config_ignored(self, loader, temp_config_dir, monkeypatch):
        """Test invalid user config is ignored gracefully."""
        user_config = temp_config_dir / "model_config.yaml"
        user_config.write_text("invalid: yaml: content: [")

        monkeypatch.setattr(ModelConfigLoader, "USER_CONFIG_PATH", user_config)
        config = loader.reload()

        # Should still work with defaults
        assert config is not None
        assert str(user_config) not in config.sources

    # --- Model Lookup Tests ---

    def test_get_context_window_exact_match(self, loader):
        """Test context window lookup with exact model name."""
        window = loader.get_context_window("gpt-4-turbo")
        assert window == 128000

    def test_get_context_window_substring_match(self, loader):
        """Test context window lookup with substring matching."""
        window = loader.get_context_window("qwen3:32b")
        assert window == 32768  # Matches "qwen3" pattern

    def test_get_context_window_unknown_model(self, loader):
        """Test context window for unknown model returns default."""
        window = loader.get_context_window("totally-unknown-model-xyz")
        assert window == 8192  # Default value

    def test_get_encoding_returns_correct_value(self, loader):
        """Test encoding lookup."""
        encoding = loader.get_encoding("gpt-4o")
        assert encoding == "o200k_base"

    # --- Validation Tests ---

    def test_validate_valid_config(self, loader):
        """Test validation of valid config."""
        data = {
            "schema_version": "1.0",
            "models": {"test": {"context_window": 1000}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"}
        }
        result = loader._validate_config(data)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_context_window(self, loader):
        """Test validation catches invalid context_window."""
        data = {
            "models": {"test": {"context_window": -100}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"}
        }
        result = loader._validate_config(data)
        assert result.valid is False
        assert any("context_window" in e for e in result.errors)

    def test_validate_unknown_encoding_warning(self, loader):
        """Test validation warns about unknown encoding."""
        data = {
            "models": {"test": {"encoding": "unknown_encoding_xyz"}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"}
        }
        result = loader._validate_config(data)
        # Should be valid but with warning
        assert any("unknown encoding" in w for w in result.warnings)

    # --- Merge Tests ---

    def test_merge_adds_new_models(self, loader):
        """Test merge adds new models from override."""
        base = {"models": {"a": {"context_window": 100}}}
        override = {"models": {"b": {"context_window": 200}}}

        result = loader._merge_configs(base, override)

        assert "a" in result["models"]
        assert "b" in result["models"]

    def test_merge_overrides_existing(self, loader):
        """Test merge overrides existing model values."""
        base = {"models": {"a": {"context_window": 100, "encoding": "e1"}}}
        override = {"models": {"a": {"context_window": 200}}}

        result = loader._merge_configs(base, override)

        assert result["models"]["a"]["context_window"] == 200
        assert result["models"]["a"]["encoding"] == "e1"  # Preserved


class TestModelConfigLoaderSingleton:
    """Tests for singleton behavior."""

    def test_get_instance_returns_same_object(self):
        """Test singleton returns same instance."""
        ModelConfigLoader.reset_instance()

        instance1 = ModelConfigLoader.get_instance()
        instance2 = ModelConfigLoader.get_instance()

        assert instance1 is instance2

    def test_reset_instance_clears_singleton(self):
        """Test reset clears singleton."""
        instance1 = ModelConfigLoader.get_instance()
        ModelConfigLoader.reset_instance()
        instance2 = ModelConfigLoader.get_instance()

        assert instance1 is not instance2
```

### Integration Tests

```python
# tests/integration/test_model_config_integration.py

import pytest
from pathlib import Path
import tempfile
import yaml

from logai.core.context.token_counter import TokenCounter
from logai.config.model_config import ModelConfigLoader


class TestTokenCounterConfigIntegration:
    """Integration tests for TokenCounter with config system."""

    @pytest.fixture(autouse=True)
    def reset_loader(self):
        """Reset loader before each test."""
        ModelConfigLoader.reset_instance()
        TokenCounter._set_config_loader(None)
        yield
        ModelConfigLoader.reset_instance()
        TokenCounter._set_config_loader(None)

    def test_token_counter_uses_config(self):
        """Test TokenCounter uses config for context windows."""
        # Should get value from config
        window = TokenCounter.get_context_window("gpt-4-turbo")
        assert window == 128000

    def test_token_counter_user_override(self, tmp_path, monkeypatch):
        """Test TokenCounter respects user overrides."""
        user_config = tmp_path / "model_config.yaml"
        user_config.write_text(yaml.dump({
            "schema_version": "1.0",
            "models": {"gpt-4-turbo": {"context_window": 999999}}
        }))

        monkeypatch.setattr(ModelConfigLoader, "USER_CONFIG_PATH", user_config)

        window = TokenCounter.get_context_window("gpt-4-turbo")
        assert window == 999999

    def test_token_counter_custom_model(self, tmp_path, monkeypatch):
        """Test TokenCounter works with custom models."""
        user_config = tmp_path / "model_config.yaml"
        user_config.write_text(yaml.dump({
            "schema_version": "1.0",
            "models": {
                "my-llm": {
                    "context_window": 50000,
                    "encoding": "cl100k_base"
                }
            }
        }))

        monkeypatch.setattr(ModelConfigLoader, "USER_CONFIG_PATH", user_config)

        window = TokenCounter.get_context_window("my-llm")
        assert window == 50000

        # Token counting should work
        tokens = TokenCounter.count_tokens("Hello world", "my-llm")
        assert tokens > 0

    def test_backward_compatibility(self):
        """Test existing code continues to work."""
        # All existing models should work
        models = [
            ("claude-3-5-sonnet", 200000),
            ("gpt-4-turbo", 128000),
            ("gpt-4o", 128000),
            ("llama3.1:8b", 8192),
        ]

        for model, expected in models:
            window = TokenCounter.get_context_window(model)
            assert window == expected, f"{model} expected {expected}, got {window}"
```

---

## 14. Implementation Checklist

### Phase 1: Config File Structure (Est: 2 hours)
- [ ] Create `src/logai/config/default_models.yaml` with all current models
- [ ] Create `examples/model_config.yaml.example` for users
- [ ] Verify YAML syntax and structure

### Phase 2: ModelConfigLoader (Est: 4 hours)
- [ ] Create `src/logai/config/model_config.py`
- [ ] Implement `ModelConfigLoader` class
- [ ] Implement `ModelConfig` and `ModelConfigData` dataclasses
- [ ] Implement YAML loading with safe_load
- [ ] Implement validation
- [ ] Implement config merging
- [ ] Add logging
- [ ] Update `src/logai/config/__init__.py` exports

### Phase 3: TokenCounter Integration (Est: 2 hours)
- [ ] Modify `TokenCounter` to use `ModelConfigLoader`
- [ ] Remove hardcoded `CONTEXT_WINDOWS` dict
- [ ] Remove hardcoded `MODEL_ENCODINGS` dict
- [ ] Add `_get_config_loader()` method
- [ ] Add `_set_config_loader()` for testing
- [ ] Verify all existing tests pass

### Phase 4: Testing (Est: 4 hours)
- [ ] Create `tests/unit/config/test_model_config.py`
- [ ] Unit tests for loading
- [ ] Unit tests for validation
- [ ] Unit tests for merging
- [ ] Unit tests for model lookup
- [ ] Integration tests with TokenCounter
- [ ] Backward compatibility tests

### Phase 5: Documentation (Est: 2 hours)
- [ ] Create `docs/user-guide/custom-models.md`
- [ ] Add inline docstrings
- [ ] Update README if needed

### Deliverables
1. `src/logai/config/default_models.yaml` - Built-in model configurations
2. `src/logai/config/model_config.py` - ModelConfigLoader implementation
3. `examples/model_config.yaml.example` - Example user config
4. `tests/unit/config/test_model_config.py` - Comprehensive unit tests
5. Updated `src/logai/core/context/token_counter.py` - Integration
6. `docs/user-guide/custom-models.md` - User documentation

---

## Questions for Review

Before implementation begins, please confirm:

1. **Schema Versioning**: Should we add support for schema version migrations, or is "1.0" sufficient for now?

2. **Encoding Validation**: Should we validate encoding names against tiktoken at load time (fails fast) or at runtime (more lenient)?

3. **CLI Commands**: Is `logai config models --show` in scope for this implementation, or deferred?

4. **Hot Reload**: The requirements mention this as "Nice to Have" / out of scope. Confirm no hot reload support needed.

5. **Precedence Order**: The design has `more-specific-pattern` first wins. Should we document this explicitly or change the behavior?

---

## Appendix: Design Decisions Log

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Config format | YAML, JSON, TOML, Python | YAML | Human-readable, comments, industry standard |
| Load timing | Eager (startup), Lazy (first use) | Lazy | Avoid startup cost if config not needed |
| Singleton vs instance | Module singleton, Class method | Singleton | Simple, testable with reset |
| Merge strategy | Replace, Deep merge | Deep merge | Users can override single fields |
| Error handling | Exception, Silent fail, Graceful fallback | Graceful fallback | Never break existing functionality |
| Validation strictness | Strict (reject invalid), Lenient (warn + continue) | Lenient | User experience over strictness |

---

**Document Version:** 1.0
**Last Updated:** 2026-02-17
**Author:** Saanvi (Senior Software Architect)
