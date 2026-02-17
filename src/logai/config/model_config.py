"""Model configuration loader for token counting and context management."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Try to import yaml, but don't fail if it's not available
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

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
            "gpt-4-turbo-preview": {"context_window": 128_000, "encoding": "cl100k_base"},
            "gpt-4o": {"context_window": 128_000, "encoding": "o200k_base"},
            "gpt-4": {"context_window": 8_192, "encoding": "cl100k_base"},
            "claude-3-5-sonnet": {"context_window": 200_000, "encoding": "cl100k_base"},
            "claude-3-5-sonnet-20241022": {"context_window": 200_000, "encoding": "cl100k_base"},
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
            logger.debug("No default config file found, using hardcoded defaults")

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

        if not YAML_AVAILABLE:
            logger.warning("PyYAML not installed, cannot load config files")
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                logger.warning(f"Config file {path} does not contain a valid YAML dict")
                return None

            return data

        except Exception as e:
            # Catch yaml.YAMLError and other exceptions
            error_type = type(e).__name__
            if "YAML" in error_type:
                logger.warning(f"Failed to parse YAML file {path}: {e}")
            elif isinstance(e, PermissionError):
                logger.warning(f"Permission denied reading {path}")
            else:
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
                            warnings.append(f"Model '{model_name}': unknown encoding '{encoding}'")

                    # Validate chars_per_token
                    if "chars_per_token" in model_data:
                        cpt = model_data["chars_per_token"]
                        if not isinstance(cpt, int | float) or cpt <= 0:
                            errors.append(f"Model '{model_name}': chars_per_token must be positive")
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

    def _merge_configs(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
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

    def _build_config_data(self, data: dict[str, Any], sources: list[str]) -> ModelConfigData:
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
            "o200k_base",  # GPT-4o
            "p50k_base",  # GPT-3.5
            "r50k_base",  # GPT-3
            "gpt2",  # Legacy
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
