# Design: Complete Hardcoded Configuration Cleanup (Phases 2 & 3)

**Date**: February 17, 2026
**Status**: Draft for Review
**Scope**: 16 remaining hardcoded configuration values
**Estimated Effort**: 10-16 hours

---

## Executive Summary

This design covers the externalization of all remaining hardcoded configuration values identified in the audit. We'll implement both Phase 2 (Medium priority - 8 items) and Phase 3 (Low priority - 8 items) to complete the configuration cleanup initiative.

---

## Architecture Overview

### Configuration Strategy

**Use `.env` file for**: User-facing operational settings
- Timeouts, retry limits, rate limits
- HTTP client configuration
- Polling intervals
- UI behavior settings
- Tool limits and defaults

**Use `advanced_config.yaml` for**: Expert-level tuning
- Complex nested configurations
- Budget allocation strategies
- Advanced retry sequences
- Performance tuning parameters

### Three-Tier Pattern (Consistent with Model Config)

```
1. Hardcoded Fallbacks (in code as constants)
   ↓ (if .env not set)
2. Default Values (from settings.py with defaults)
   ↓ (if .env set)
3. User .env Values (override defaults)

For YAML configs:
1. Hardcoded Fallbacks
   ↓ (if YAML not found)
2. Built-in YAML (src/logai/config/advanced_config.yaml)
   ↓ (if user YAML exists)
3. User YAML (~/.logai/advanced_config.yaml)
```

---

## Phase 2: Medium Priority (8 items)

### Group 1: CloudWatch Configuration

#### **Item 1: CloudWatch API Timeouts**
**Current**: `src/logai/providers/datasources/cloudwatch.py:47-48`
```python
connect_timeout=5, read_timeout=30
```

**Solution**:
```python
# In settings.py
cloudwatch_connect_timeout: int = Field(
    default=5,
    description="CloudWatch API connection timeout in seconds",
    gt=0,
    le=60,
)
cloudwatch_read_timeout: int = Field(
    default=30,
    description="CloudWatch API read timeout in seconds",
    gt=0,
    le=300,
)
```

**Usage**:
```python
# In cloudwatch.py
config = Config(
    connect_timeout=self.settings.cloudwatch_connect_timeout,
    read_timeout=self.settings.cloudwatch_read_timeout,
    retries=...,
)
```

**.env**:
```bash
LOGAI_CLOUDWATCH_CONNECT_TIMEOUT=5
LOGAI_CLOUDWATCH_READ_TIMEOUT=30
```

---

#### **Item 2: CloudWatch Retry Configuration**
**Current**: `src/logai/providers/datasources/cloudwatch.py:46`
```python
retries={"max_attempts": 3, "mode": "adaptive"}
```

**Solution**:
```python
# In settings.py
cloudwatch_max_retry_attempts: int = Field(
    default=3,
    description="CloudWatch API maximum retry attempts",
    gt=0,
    le=10,
)
cloudwatch_retry_mode: str = Field(
    default="adaptive",
    description="CloudWatch API retry mode (standard, legacy, adaptive)",
)

@field_validator('cloudwatch_retry_mode')
def validate_retry_mode(cls, v):
    valid_modes = ['standard', 'legacy', 'adaptive']
    if v not in valid_modes:
        raise ValueError(f"Retry mode must be one of {valid_modes}")
    return v
```

**.env**:
```bash
LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS=3
LOGAI_CLOUDWATCH_RETRY_MODE=adaptive
```

---

### Group 2: GitHub Copilot Provider Configuration

#### **Item 3: GitHub Copilot Retry Configuration**
**Current**: `src/logai/providers/llm/github_copilot_provider.py:63-65`
```python
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 8.0
```

**Solution**:
```python
# In settings.py
github_copilot_max_retries: int = Field(
    default=3,
    description="Maximum retry attempts for GitHub Copilot API 403 errors",
    ge=0,
    le=10,
)
github_copilot_retry_base_delay: float = Field(
    default=1.0,
    description="Base delay in seconds for GitHub Copilot retry backoff",
    gt=0,
    le=10,
)
github_copilot_retry_max_delay: float = Field(
    default=8.0,
    description="Maximum delay in seconds for GitHub Copilot retry backoff",
    gt=0,
    le=60,
)
```

**Usage**:
```python
# In github_copilot_provider.py - remove class constants
def __init__(self, settings: Settings, ...):
    self._max_retries = settings.github_copilot_max_retries
    self._retry_base_delay = settings.github_copilot_retry_base_delay
    self._retry_max_delay = settings.github_copilot_retry_max_delay
```

**.env**:
```bash
LOGAI_GITHUB_COPILOT_MAX_RETRIES=3
LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY=1.0
LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY=8.0
```

---

#### **Item 4: GitHub Copilot API Headers**
**Current**: `src/logai/providers/llm/github_copilot_provider.py:279-280, 392-393`
```python
"Copilot-Integration-Id": "vscode-chat"
"Editor-Version": "vscode/1.98.2"
```

**Solution**:
```python
# In settings.py
github_copilot_integration_id: str = Field(
    default="vscode-chat",
    description="GitHub Copilot integration identifier",
)
github_copilot_editor_version: str = Field(
    default="vscode/1.98.2",
    description="GitHub Copilot editor version string",
)
```

**.env**:
```bash
LOGAI_GITHUB_COPILOT_INTEGRATION_ID=vscode-chat
LOGAI_GITHUB_COPILOT_EDITOR_VERSION=vscode/1.98.2
```

---

#### **Item 5: GitHub Copilot HTTP Timeouts**
**Current**: `src/logai/providers/llm/github_copilot_provider.py:74, 159`
```python
timeout: float = 120.0
httpx.Timeout(self._timeout, connect=10.0)
```

**Solution**:
```python
# In settings.py
github_copilot_request_timeout: float = Field(
    default=120.0,
    description="GitHub Copilot HTTP request timeout in seconds",
    gt=0,
    le=600,
)
github_copilot_connect_timeout: float = Field(
    default=10.0,
    description="GitHub Copilot HTTP connect timeout in seconds",
    gt=0,
    le=60,
)
```

**.env**:
```bash
LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT=120
LOGAI_GITHUB_COPILOT_CONNECT_TIMEOUT=10
```

---

#### **Item 6: GitHub Copilot Model Cache**
**Current**: `src/logai/providers/llm/github_copilot_models.py:81-82`
```python
CACHE_DURATION_HOURS = 24
CACHE_FILE_NAME = "github_copilot_models.json"
```

**Solution**:
```python
# In settings.py
github_model_cache_hours: int = Field(
    default=24,
    description="Hours to cache GitHub Copilot model list",
    gt=0,
    le=168,  # 1 week max
)
github_model_cache_file: str = Field(
    default="github_copilot_models.json",
    description="Filename for GitHub Copilot model cache",
)
```

**.env**:
```bash
LOGAI_GITHUB_MODEL_CACHE_HOURS=24
LOGAI_GITHUB_MODEL_CACHE_FILE=github_copilot_models.json
```

---

### Group 3: GitHub OAuth Configuration

#### **Item 7: GitHub OAuth Settings**
**Current**: `src/logai/auth/github_copilot_auth.py:99, 105, 108`
```python
CLIENT_ID = "Iv1.b507a08c87ecfe98"
SCOPES = "user:email read:user"
DEFAULT_TIMEOUT = 900
```

**Solution**:
```python
# In settings.py
github_oauth_client_id: str = Field(
    default="Iv1.b507a08c87ecfe98",
    description="GitHub OAuth client ID",
)
github_oauth_scopes: str = Field(
    default="user:email read:user",
    description="GitHub OAuth scopes (space-separated)",
)
github_auth_timeout: int = Field(
    default=900,
    description="GitHub OAuth authentication timeout in seconds",
    gt=0,
    le=3600,
)
```

**.env**:
```bash
LOGAI_GITHUB_OAUTH_CLIENT_ID=Iv1.b507a08c87ecfe98
LOGAI_GITHUB_OAUTH_SCOPES=user:email read:user
LOGAI_GITHUB_AUTH_TIMEOUT=900
```

---

#### **Item 8: OAuth Polling Behavior**
**Current**: `src/logai/auth/github_copilot_auth.py:311, 379`
```python
interval = 5  # default
slow_down += 5
```

**Solution**:
```python
# In settings.py
github_auth_poll_interval: int = Field(
    default=5,
    description="GitHub OAuth polling interval in seconds",
    gt=0,
    le=60,
)
github_auth_slow_down_increment: int = Field(
    default=5,
    description="Seconds to add when GitHub OAuth requests slow_down",
    gt=0,
    le=30,
)
```

**.env**:
```bash
LOGAI_GITHUB_AUTH_POLL_INTERVAL=5
LOGAI_GITHUB_AUTH_SLOW_DOWN_INCREMENT=5
```

---

### Group 4: Tool Configuration

#### **Item 9: Tool Default Limits**
**Current**: `src/logai/core/tools/cloudwatch_tools.py:86, 224`
```python
list_log_groups: limit=50, max=100
fetch_logs: limit=100, max=1000
```

**Solution**:
```python
# In settings.py
tool_list_log_groups_default_limit: int = Field(
    default=50,
    description="Default limit for list_log_groups tool",
    gt=0,
    le=100,
)
tool_list_log_groups_max_limit: int = Field(
    default=100,
    description="Maximum limit for list_log_groups tool",
    gt=0,
    le=100,
)
tool_fetch_logs_default_limit: int = Field(
    default=100,
    description="Default limit for fetch_logs tool",
    gt=0,
    le=10000,
)
tool_fetch_logs_max_limit: int = Field(
    default=1000,
    description="Maximum limit for fetch_logs tool",
    gt=0,
    le=10000,
)
```

**.env**:
```bash
LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT=50
LOGAI_TOOL_LIST_LOG_GROUPS_MAX_LIMIT=100
LOGAI_TOOL_FETCH_LOGS_DEFAULT_LIMIT=100
LOGAI_TOOL_FETCH_LOGS_MAX_LIMIT=1000
```

---

### Group 5: Orchestrator & UI Configuration

#### **Item 10: Orchestrator Retry Backoff**
**Current**: `src/logai/core/orchestrator.py:1737`
```python
base_delays = [0.5, 1.0, 2.0]
```

**Solution**:
```python
# In settings.py
orchestrator_retry_delays: str = Field(
    default="0.5,1.0,2.0",
    description="Comma-separated retry delays in seconds",
)

@property
def orchestrator_retry_delays_list(self) -> list[float]:
    """Parse retry delays string into list of floats."""
    return [float(x.strip()) for x in self.orchestrator_retry_delays.split(',')]
```

**.env**:
```bash
LOGAI_ORCHESTRATOR_RETRY_DELAYS=0.5,1.0,2.0
```

---

#### **Item 11: UI Context Update Throttle**
**Current**: `src/logai/ui/screens/chat.py:130`
```python
self._context_update_throttle_seconds: float = 1.0
```

**Solution**:
```python
# In settings.py
ui_context_update_throttle: float = Field(
    default=1.0,
    description="UI context update throttle in seconds",
    gt=0,
    le=10,
)
```

**.env**:
```bash
LOGAI_UI_CONTEXT_UPDATE_THROTTLE=1.0
```

---

#### **Item 12: UI Tool Timeouts**
**Current**: `src/logai/ui/screens/chat.py:323-329`
```python
# Progressive timeouts: 10s, 8s, 5s
```

**Solution**:
```python
# In settings.py
ui_tool_timeout_initial: int = Field(
    default=10,
    description="Initial tool timeout in seconds (first iteration)",
    gt=0,
    le=60,
)
ui_tool_timeout_subsequent: int = Field(
    default=8,
    description="Subsequent tool timeout in seconds",
    gt=0,
    le=60,
)
ui_tool_timeout_final: int = Field(
    default=5,
    description="Final tool timeout in seconds (last iterations)",
    gt=0,
    le=60,
)
```

**.env**:
```bash
LOGAI_UI_TOOL_TIMEOUT_INITIAL=10
LOGAI_UI_TOOL_TIMEOUT_SUBSEQUENT=8
LOGAI_UI_TOOL_TIMEOUT_FINAL=5
```

---

#### **Item 13: Model Discovery HTTP Timeout**
**Current**: `src/logai/providers/llm/github_copilot_models.py:142`
```python
async with httpx.AsyncClient(timeout=10.0)
```

**Solution**:
```python
# In settings.py
model_discovery_timeout: float = Field(
    default=10.0,
    description="HTTP timeout for model discovery in seconds",
    gt=0,
    le=60,
)
```

**.env**:
```bash
LOGAI_MODEL_DISCOVERY_TIMEOUT=10
```

---

## Phase 3: Low Priority (8 items)

### Advanced Configuration YAML

For complex nested configurations, we'll create `advanced_config.yaml`:

```yaml
# src/logai/config/advanced_config.yaml
version: 1

# History Management
history:
  preserve_recent_messages: 4  # Keep last N messages during emergency pruning

# Context Budget Allocation (percentages as decimals)
budget_allocation:
  safety_buffer: 0.05      # 5% safety buffer
  response_reserve: 0.04   # 4% for LLM response
  system_prompt: 0.05      # 5% for system prompt

  # Allocation strategies
  strategies:
    adaptive:
      history: 0.55          # 55% for conversation history
      results: 0.45          # 45% for results/context
    history_focused:
      history: 0.70
      results: 0.30
    results_focused:
      history: 0.40
      results: 0.60

# CloudWatch API Limits
cloudwatch:
  max_events_per_request: 10000  # AWS API limit

# Performance Tuning
performance:
  # Add future performance settings here
  token_counting_cache_size: 1000
```

---

### Advanced Config Loader

```python
# src/logai/config/advanced_config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

@dataclass(frozen=True)
class BudgetAllocationStrategy:
    history: float
    results: float

@dataclass(frozen=True)
class BudgetAllocation:
    safety_buffer: float
    response_reserve: float
    system_prompt: float
    strategies: dict[str, BudgetAllocationStrategy]

@dataclass(frozen=True)
class AdvancedConfig:
    history_preserve_recent: int
    budget_allocation: BudgetAllocation
    cloudwatch_max_events: int

class AdvancedConfigLoader:
    """Singleton loader for advanced configuration (similar to ModelConfigLoader)."""

    _instance = None
    _config: AdvancedConfig | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> AdvancedConfig:
        """Load advanced config with three-tier precedence."""
        if self._config is not None:
            return self._config

        # 1. Start with hardcoded defaults
        config = self._get_hardcoded_defaults()

        # 2. Load built-in YAML (if exists)
        builtin_path = Path(__file__).parent / "advanced_config.yaml"
        if builtin_path.exists():
            config = self._merge_yaml(config, builtin_path)

        # 3. Load user YAML (if exists)
        user_path = Path.home() / ".logai" / "advanced_config.yaml"
        if user_path.exists():
            config = self._merge_yaml(config, user_path)

        self._config = config
        return config

    def _get_hardcoded_defaults(self) -> AdvancedConfig:
        """Hardcoded fallback values."""
        return AdvancedConfig(
            history_preserve_recent=4,
            budget_allocation=BudgetAllocation(
                safety_buffer=0.05,
                response_reserve=0.04,
                system_prompt=0.05,
                strategies={
                    "adaptive": BudgetAllocationStrategy(0.55, 0.45),
                },
            ),
            cloudwatch_max_events=10000,
        )
```

---

## Implementation Plan

### Phase 2: Medium Priority (~8-12 hours)

#### **Step 1: Settings Expansion** (2 hours)
- Add all 13 new settings to `settings.py`
- Add validators for enum-like fields (retry_mode, etc.)
- Update `.env.example` with all new variables

#### **Step 2: CloudWatch Provider** (1 hour)
- Update `cloudwatch.py` to use settings for timeouts and retries
- Remove hardcoded values
- Add tests

#### **Step 3: GitHub Copilot Provider** (2 hours)
- Update `github_copilot_provider.py` for retry config and headers
- Update timeouts to use settings
- Remove class constants

#### **Step 4: GitHub Copilot Models** (1 hour)
- Update cache duration and filename from settings
- Update model discovery timeout

#### **Step 5: GitHub OAuth** (1.5 hours)
- Update `github_copilot_auth.py` for OAuth settings
- Update polling behavior

#### **Step 6: Tools & Orchestrator** (1.5 hours)
- Update `cloudwatch_tools.py` for limits
- Update `orchestrator.py` for retry delays
- Parse comma-separated delays

#### **Step 7: UI Components** (1 hour)
- Update `chat.py` for throttle and timeouts
- Use settings values

#### **Step 8: Testing** (2 hours)
- Add/update tests for all modified files
- Integration tests for settings usage
- Verify defaults work

---

### Phase 3: Low Priority (~2-4 hours)

#### **Step 1: Advanced Config Infrastructure** (1 hour)
- Create `advanced_config.py` loader (similar to `model_config.py`)
- Create `advanced_config.yaml` with defaults
- Create `examples/advanced_config.yaml.example`

#### **Step 2: Integrate Advanced Config** (1 hour)
- Update `orchestrator.py` for history preservation
- Update `budget_tracker.py` for allocation strategies
- Update `cloudwatch.py` for max events

#### **Step 3: Testing** (1-2 hours)
- Tests for AdvancedConfigLoader
- Tests for config precedence
- Integration tests

---

## Testing Strategy

### Unit Tests
For each modified file:
1. Test that settings/config values are used (not hardcoded)
2. Test with custom values
3. Test with missing values (defaults work)
4. Test validators (invalid values rejected)

### Integration Tests
1. Test with custom `.env` file
2. Test with custom `advanced_config.yaml`
3. Test precedence order (hardcoded → builtin → user)
4. Test backward compatibility (no settings = same behavior)

### Manual Tests
1. Set custom CloudWatch timeouts and verify behavior
2. Set custom retry delays and observe
3. Set custom tool limits and test
4. Create user advanced_config.yaml and verify usage

---

## Breaking Changes

**None Expected** - all changes will:
1. Keep current defaults (same values as hardcoded)
2. Add environment variable overrides
3. Maintain backward compatibility

---

## Success Criteria

### Phase 2
- [ ] All 13 settings added to `settings.py` with validation
- [ ] All `.env.example` entries documented
- [ ] All 7 modified files use settings (not hardcoded values)
- [ ] All existing tests pass
- [ ] New tests verify settings usage (90%+ coverage)
- [ ] No breaking changes (backward compatible)

### Phase 3
- [ ] AdvancedConfigLoader implemented with singleton pattern
- [ ] `advanced_config.yaml` created with defaults
- [ ] Example file created with documentation
- [ ] 3 modified files use advanced config
- [ ] Tests verify YAML loading and precedence
- [ ] No breaking changes

---

## Risk Mitigation

### Risk: Breaking Existing Behavior
**Mitigation**:
- Use exact same defaults as current hardcoded values
- Comprehensive testing before commit
- Feature flag if needed

### Risk: Settings Validation Too Strict
**Mitigation**:
- Reasonable upper bounds (not arbitrary limits)
- Document why limits exist
- Allow override via advanced config if needed

### Risk: Performance Impact
**Mitigation**:
- Settings accessed once (in __init__ or cached)
- No repeated lookups
- Benchmark if concerned

---

## Documentation

### User Documentation
1. Update `docs/user-guide/configuration.md`:
   - Document all new .env variables
   - Explain when to use each setting
   - Provide examples

2. Create `docs/advanced-configuration.md`:
   - Expert-level tuning guide
   - Budget allocation strategies
   - Performance optimization tips

### Developer Documentation
1. Update architecture docs with config pattern
2. Document config precedence order
3. Add examples for future config additions

---

## Files to Modify

### Phase 2 (13 items → 10 files)
1. **`src/logai/config/settings.py`** - Add 13 new settings
2. **`.env.example`** - Document 13 new env vars
3. **`src/logai/providers/datasources/cloudwatch.py`** - Timeouts & retries
4. **`src/logai/providers/llm/github_copilot_provider.py`** - Retry, headers, timeouts
5. **`src/logai/providers/llm/github_copilot_models.py`** - Cache & discovery timeout
6. **`src/logai/auth/github_copilot_auth.py`** - OAuth & polling
7. **`src/logai/core/tools/cloudwatch_tools.py`** - Tool limits
8. **`src/logai/core/orchestrator.py`** - Retry delays
9. **`src/logai/ui/screens/chat.py`** - Throttle & timeouts
10. **Tests** - Update/add tests for all above

### Phase 3 (Advanced config → 6 files)
1. **`src/logai/config/advanced_config.py`** - New config loader
2. **`src/logai/config/advanced_config.yaml`** - Built-in defaults
3. **`examples/advanced_config.yaml.example`** - User guide
4. **`src/logai/core/orchestrator.py`** - History preservation
5. **`src/logai/core/context/budget_tracker.py`** - Budget allocation
6. **Tests** - Tests for advanced config

**Total**: ~16 files modified/created

---

## Estimated Timeline

| Phase | Task | Time |
|-------|------|------|
| **Phase 2** | Settings expansion | 2h |
| | CloudWatch provider | 1h |
| | GitHub Copilot provider | 2h |
| | GitHub Copilot models | 1h |
| | GitHub OAuth | 1.5h |
| | Tools & Orchestrator | 1.5h |
| | UI components | 1h |
| | Testing Phase 2 | 2h |
| **Phase 2 Total** | | **12h** |
| **Phase 3** | Advanced config infra | 1h |
| | Integration | 1h |
| | Testing Phase 3 | 1-2h |
| **Phase 3 Total** | | **3-4h** |
| **Documentation** | User & dev docs | 2h |
| **Buffer** | Unexpected issues | 2h |
| **GRAND TOTAL** | | **19-20h** |

With team parallelization and AI agent speed: **~10-12 hours actual time**

---

## Next Steps

1. **Saanvi**: Review this design document
2. **Jackie**: Implement Phase 2 (13 settings)
3. **Raoul**: Write tests for Phase 2
4. **Han-Ron**: Review Phase 2 code
5. **George**: Coordinate and commit Phase 2
6. **Jackie**: Implement Phase 3 (advanced config)
7. **Raoul**: Write tests for Phase 3
8. **Han-Ron**: Review Phase 3 code
9. **Tina**: Update documentation
10. **George**: Final commit and push

---

**Status**: Ready for Saanvi's architecture review
**Next**: Get Saanvi's feedback and approval
