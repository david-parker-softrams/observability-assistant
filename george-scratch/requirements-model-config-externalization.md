# Requirements: Externalize Model Configuration

**Date:** 2026-02-17
**Priority:** High
**Type:** Feature Enhancement

## Problem Statement

Model-specific configurations (context window sizes, tokenizer encodings) are hardcoded in `token_counter.py`. This creates several issues:

1. **User Barrier**: Users with custom/local models must modify source code to add model configurations
2. **Maintainability**: Every new model requires a code change and redeployment
3. **Flexibility**: No way to override model configs without code changes
4. **Version Control**: User customizations conflict with upstream updates

## User Story

**As a** LogAI user with a custom local model
**I want to** configure model context windows and tokenizer settings via a config file
**So that** I can use my model without modifying source code

## Current State (Hardcoded)

```python
# src/logai/core/context/token_counter.py
CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4-turbo": 128_000,
    "gpt-4o": 128_000,
    "gpt-4": 8_192,
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "llama3.1:8b": 8_192,
    "llama3.1:70b": 128_000,
    "qwen3": 32_768,
    "default": 8_192,
}

MODEL_ENCODINGS: dict[str, str] = {
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4o": "o200k_base",
    "claude": "cl100k_base",
    "github-copilot": "cl100k_base",
}
```

## Desired State (Externalized)

### Config File Structure

**Location:** `~/.logai/model_config.yaml` (user-specific overrides)
**Fallback:** `src/logai/config/default_models.yaml` (built-in defaults)

```yaml
# Model configurations for token counting and context management
models:
  # OpenAI Models
  gpt-4:
    context_window: 8192
    encoding: cl100k_base

  gpt-4-turbo:
    context_window: 128000
    encoding: cl100k_base

  gpt-4o:
    context_window: 128000
    encoding: o200k_base

  # Anthropic Models
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

  # GitHub Copilot
  github-copilot:
    encoding: cl100k_base

  # Local Ollama Models
  llama3.1:8b:
    context_window: 8192
    encoding: cl100k_base

  llama3.1:70b:
    context_window: 128000
    encoding: cl100k_base

  qwen3:
    context_window: 32768
    encoding: cl100k_base

  # User can add custom models here
  # my-custom-model:
  #   context_window: 16384
  #   encoding: cl100k_base

# Default values for unknown models
defaults:
  context_window: 8192
  encoding: cl100k_base
  chars_per_token: 3.5
```

## Requirements

### Functional Requirements

1. **Load Order**
   - Load built-in defaults from `src/logai/config/default_models.yaml`
   - Override with user config from `~/.logai/model_config.yaml` (if exists)
   - User config takes precedence over defaults

2. **Config File Format**
   - Use YAML for readability and ease of editing
   - Support comments for user guidance
   - Validate structure on load (catch errors early)

3. **Model Matching**
   - Use substring matching (e.g., `qwen3` matches `qwen3:32b`, `qwen3:70b`)
   - First match wins (allows specific overrides before generic ones)
   - Fall back to `defaults.context_window` if no match

4. **Backward Compatibility**
   - If no config files exist, use hardcoded defaults
   - Existing code behavior unchanged
   - No breaking changes to API

5. **User Experience**
   - Provide example config file
   - Clear error messages if config is invalid
   - Log which config file is being used (debug level)

### Non-Functional Requirements

1. **Performance**
   - Load config once at startup (cached)
   - Lookups should be O(n) where n = number of model patterns
   - No noticeable latency impact

2. **Error Handling**
   - Invalid YAML → Log warning, fall back to hardcoded defaults
   - Missing file → Use hardcoded defaults (no error)
   - Invalid values → Log warning, use default for that field

3. **Documentation**
   - Update user guide with config file instructions
   - Provide example for adding custom models
   - Document config file precedence

## Success Criteria

### Must Have
- ✅ User can add custom model config without code changes
- ✅ Config file in `~/.logai/` overrides built-in defaults
- ✅ Built-in models work without any config file
- ✅ Clear error messages for invalid configs

### Should Have
- ✅ Example config file included in distribution
- ✅ CLI command to show current model config: `logai config models --show`
- ✅ Validation warns about unknown encoding types

### Nice to Have
- 🔄 Hot reload config without restart (future enhancement)
- 🔄 CLI command to add model: `logai config models --add my-model --context 16384`

## Implementation Plan

### Phase 1: Config File Structure (Jackie)
1. Create `src/logai/config/default_models.yaml` with all current models
2. Define schema/structure
3. Add validation logic

### Phase 2: Config Loader (Jackie)
1. Create `ModelConfigLoader` class in `src/logai/config/model_config.py`
2. Implement load order (defaults → user overrides)
3. Add caching for performance
4. Handle errors gracefully

### Phase 3: Integrate with TokenCounter (Jackie)
1. Modify `TokenCounter.__init__()` to load config
2. Replace hardcoded dicts with config lookups
3. Maintain backward compatibility
4. Add logging

### Phase 4: Testing (Raoul)
1. Unit tests for config loading
2. Test user override behavior
3. Test error handling (invalid YAML, missing file)
4. Test backward compatibility

### Phase 5: Documentation (Tina)
1. Add config file docs to user guide
2. Create example config file
3. Document how to add custom models
4. Update troubleshooting guide

## Files to Create

```
src/logai/config/
├── default_models.yaml         (NEW - built-in model configs)
└── model_config.py             (NEW - config loader)

docs/user-guide/
└── custom-models.md            (NEW - how to add custom models)

examples/
└── model_config.yaml.example   (NEW - example user config)
```

## Files to Modify

```
src/logai/core/context/token_counter.py
  - Remove hardcoded CONTEXT_WINDOWS and MODEL_ENCODINGS
  - Load from ModelConfigLoader instead
  - Add fallback to hardcoded if config load fails

src/logai/config/settings.py
  - Add MODEL_CONFIG_PATH setting (default: ~/.logai/model_config.yaml)
```

## Example Usage

### Adding a Custom Model

**User creates:** `~/.logai/model_config.yaml`

```yaml
models:
  # My custom fine-tuned model
  my-llama-32b:
    context_window: 32768
    encoding: cl100k_base

  # Override built-in model
  qwen3:
    context_window: 65536  # I upgraded to a bigger variant
    encoding: cl100k_base
```

**User runs:** `logai` (app loads custom config automatically)

**Expected behavior:**
- `qwen3:32b` now uses 65,536 token window (user override)
- `my-llama-32b` uses 32,768 token window (new model)
- All other models use built-in defaults

### Viewing Current Config

```bash
$ logai config models --show
Model Configuration:
  Source: ~/.logai/model_config.yaml (user override) + built-in defaults

  Active Models:
    my-llama-32b:
      context_window: 32768 (from ~/.logai/model_config.yaml)
      encoding: cl100k_base

    qwen3:
      context_window: 65536 (from ~/.logai/model_config.yaml - OVERRIDDEN)
      encoding: cl100k_base

    gpt-4-turbo:
      context_window: 128000 (from built-in defaults)
      encoding: cl100k_base

  Defaults:
    context_window: 8192
    encoding: cl100k_base
```

## Migration Path

### Version 1.0 (Current)
- Hardcoded model configs in `token_counter.py`

### Version 1.1 (This Feature)
- Config files supported
- Hardcoded defaults as fallback
- No breaking changes

### Version 2.0 (Future)
- Remove hardcoded defaults
- Config file required (or generate default on first run)

## Risk Mitigation

### Risk: Config file parsing errors
**Mitigation:** Fall back to hardcoded defaults, log clear error message

### Risk: User typos in config
**Mitigation:** Validate on load, warn about unknown keys/values

### Risk: Performance impact from file I/O
**Mitigation:** Load once at startup, cache in memory

### Risk: Breaking existing deployments
**Mitigation:** Config file is optional, hardcoded defaults preserved

## Alternative Approaches Considered

### Option 1: Environment Variables
```bash
export LOGAI_MODEL_QWEN3_CONTEXT_WINDOW=32768
export LOGAI_MODEL_QWEN3_ENCODING=cl100k_base
```
**Rejected:** Too verbose, not scalable for many models

### Option 2: JSON Config File
```json
{
  "models": {
    "qwen3": {
      "context_window": 32768
    }
  }
}
```
**Rejected:** Less readable than YAML, no comments

### Option 3: Python Config File
```python
# model_config.py
MODELS = {
    "qwen3": {"context_window": 32768}
}
```
**Rejected:** Security risk (arbitrary code execution), not user-friendly

### Option 4: Database
**Rejected:** Overkill for simple key-value data

## Chosen: YAML Config File ✅
- Human-readable
- Supports comments
- Standard in config management
- Safe (no code execution)
- Easy to edit

## Dependencies

- `PyYAML` (already in dependencies)
- No new external dependencies needed

## Testing Strategy

### Unit Tests
- Config file parsing
- Override behavior
- Error handling
- Backward compatibility

### Integration Tests
- End-to-end with custom model
- Config file precedence
- CLI commands

### Manual Testing
- Create custom config, verify it loads
- Invalid YAML, verify graceful fallback
- Missing file, verify defaults work

## Documentation Requirements

1. **User Guide**
   - How to create custom model config
   - Config file format and location
   - Override examples

2. **Developer Guide**
   - How ModelConfigLoader works
   - How to add new config fields
   - Testing config changes

3. **Troubleshooting**
   - "My custom model isn't recognized"
   - "Config file not loading"
   - "How to see current config"

## Out of Scope

- Hot reload (restart required for config changes)
- GUI for editing config
- Auto-detection of model capabilities
- Network-based config updates
- Multi-tenant config management

## Questions for Review

1. Should we support JSON in addition to YAML?
2. Should we include ALL Ollama models by default, or just common ones?
3. Should `logai config models --add` be in scope for v1.1?
4. Should we validate encoding names against tiktoken's available encodings?

## Acceptance Criteria

- [ ] User can add custom model to `~/.logai/model_config.yaml`
- [ ] Custom model config is used by TokenCounter
- [ ] Built-in defaults work without any config file
- [ ] Invalid config logs warning and falls back to defaults
- [ ] Documentation explains how to add custom models
- [ ] All existing tests pass
- [ ] New tests cover config loading and overrides
- [ ] Code review approved by Han-Ron
- [ ] User guide updated by Tina

---

**Next Steps:**
1. Review requirements with team
2. Create design document (Saanvi)
3. Implement (Jackie)
4. Test (Raoul)
5. Document (Tina)
