# Requirements: Externalize Hardcoded Configuration Options

**Date**: February 17, 2026
**Status**: Draft
**Priority**: TBD by user

---

## Executive Summary

A comprehensive code audit identified **23 hardcoded configuration values** that should be externalized to improve user configurability, reduce code modifications, and enhance maintainability. These span three priority levels: Critical (7), Medium (8), and Low (8).

---

## Problem Statement

Users currently cannot customize many operational parameters without modifying source code:
- CloudWatch timeout/retry behavior
- GitHub Copilot API retry and header configuration
- Cache behavior (despite existing .env settings being ignored)
- OAuth settings (preventing use of custom GitHub apps)
- Tool limits and defaults
- UI behavior and performance tuning

---

## Critical Issues (7 items)

### 1. CloudWatch API Timeouts
- **Current**: `connect_timeout=5, read_timeout=30` (hardcoded)
- **File**: `src/logai/providers/datasources/cloudwatch.py:47-48`
- **Impact**: Users in high-latency regions or with large log volumes cannot adjust timeouts
- **Solution**: Add `.env` settings:
  ```
  LOGAI_CLOUDWATCH_CONNECT_TIMEOUT=5
  LOGAI_CLOUDWATCH_READ_TIMEOUT=30
  ```

### 2. CloudWatch Retry Configuration
- **Current**: `retries={"max_attempts": 3, "mode": "adaptive"}` (hardcoded)
- **File**: `src/logai/providers/datasources/cloudwatch.py:46`
- **Impact**: Users cannot tune retry behavior for their network conditions
- **Solution**: Add `.env` settings:
  ```
  LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS=3
  LOGAI_CLOUDWATCH_RETRY_MODE=adaptive
  ```

### 3. GitHub Copilot API Retry Configuration
- **Current**: `MAX_RETRIES=3, RETRY_BASE_DELAY=1.0, RETRY_MAX_DELAY=8.0` (constants)
- **File**: `src/logai/providers/llm/github_copilot_provider.py:63-65`
- **Impact**: Users experiencing rate limiting cannot adjust retry behavior
- **Solution**: Add `.env` settings:
  ```
  LOGAI_GITHUB_COPILOT_MAX_RETRIES=3
  LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY=1.0
  LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY=8.0
  ```

### 4. GitHub Copilot API Headers
- **Current**: `"Copilot-Integration-Id": "vscode-chat", "Editor-Version": "vscode/1.98.2"` (hardcoded)
- **File**: `src/logai/providers/llm/github_copilot_provider.py:279-280, 392-393`
- **Impact**: Requires code changes when VS Code versions change or GitHub updates API requirements
- **Solution**: Add `.env` settings:
  ```
  LOGAI_GITHUB_COPILOT_INTEGRATION_ID=vscode-chat
  LOGAI_GITHUB_COPILOT_EDITOR_VERSION=vscode/1.98.2
  ```

### 5. GitHub OAuth Configuration
- **Current**: `CLIENT_ID="Iv1.b507a08c87ecfe98", SCOPES="user:email read:user", DEFAULT_TIMEOUT=900` (constants)
- **File**: `src/logai/auth/github_copilot_auth.py:99, 105, 108`
- **Impact**: Users cannot use custom GitHub OAuth apps or adjust auth timeout
- **Solution**: Add `.env` settings:
  ```
  LOGAI_GITHUB_OAUTH_CLIENT_ID=Iv1.b507a08c87ecfe98
  LOGAI_GITHUB_OAUTH_SCOPES=user:email read:user
  LOGAI_GITHUB_AUTH_TIMEOUT=900
  ```

### 6. Cache Manager Configuration (CRITICAL BUG)
- **Current**: Class constants override `.env` settings:
  ```python
  CACHE_MAX_SIZE_MB = 500  # Ignores settings.cache_max_size_mb!
  CACHE_MAX_ENTRIES = 10000
  CACHE_EVICTION_BATCH = 100
  CACHE_CLEANUP_INTERVAL = 300
  ```
- **File**: `src/logai/cache/manager.py:19-22`
- **Impact**: HIGH - User `.env` settings for cache are completely ignored
- **Solution**: Remove class constants, use `settings` values directly

### 7. Cache TTL Strategy
- **Current**: Hardcoded TTL logic (15min, 1min, 24h, 5min)
- **File**: `src/logai/cache/manager.py:237-265`
- **Impact**: Users cannot customize cache freshness for their use cases
- **Solution**: Create `cache_config.yaml` (similar to model_config.yaml pattern)

---

## Medium Priority Issues (8 items)

### 8. Tool Default Limits
- **File**: `src/logai/core/tools/cloudwatch_tools.py:86, 224`
- **Current**: Default limits (50/100) hardcoded
- **Solution**: `.env` settings for default/max limits

### 9. GitHub Copilot HTTP Timeouts
- **File**: `src/logai/providers/llm/github_copilot_provider.py:74, 159`
- **Current**: `timeout=120.0, connect=10.0` hardcoded
- **Solution**: `.env` settings for timeouts

### 10. GitHub Copilot Model Cache
- **File**: `src/logai/providers/llm/github_copilot_models.py:81-82`
- **Current**: 24-hour cache duration hardcoded
- **Solution**: `.env` settings for cache duration and file location

### 11. Model Discovery HTTP Timeout
- **File**: `src/logai/providers/llm/github_copilot_models.py:142`
- **Current**: 10s timeout hardcoded
- **Solution**: `.env` setting

### 12. OAuth Polling Behavior
- **File**: `src/logai/auth/github_copilot_auth.py:311, 379`
- **Current**: 5-second intervals hardcoded
- **Solution**: `.env` settings for poll intervals

### 13. Orchestrator Retry Backoff
- **File**: `src/logai/core/orchestrator.py:1737`
- **Current**: `[0.5, 1.0, 2.0]` delays hardcoded
- **Solution**: `.env` or YAML config

### 14. UI Context Update Throttle
- **File**: `src/logai/ui/screens/chat.py:130`
- **Current**: 1.0 second throttle hardcoded
- **Solution**: `.env` setting

### 15. UI Tool Timeouts
- **File**: `src/logai/ui/screens/chat.py:323-329`
- **Current**: Progressive timeouts (10s, 8s, 5s) hardcoded
- **Solution**: `.env` settings

---

## Low Priority Issues (8 items)

### 16-23. Various Advanced Settings
- History pruning configuration
- Budget allocation percentages
- CloudWatch API limits
- Advanced retry strategies
- (See full audit report for details)

---

## Recommended Approach

### Configuration Patterns

**Use .env for**:
- Timeouts and retry configurations
- API settings and headers
- OAuth configuration
- Feature flags
- User-facing limits

**Use YAML config for**:
- Complex nested configurations (cache TTL strategies)
- Advanced expert settings (budget allocation)
- Collections of related settings

### Migration Strategy

**Phase 1 - Critical (Priority 1)**:
1. Fix Cache Manager to use settings (CRITICAL BUG)
2. Externalize CloudWatch timeouts and retries
3. Externalize GitHub Copilot retry and headers
4. Externalize OAuth configuration

**Phase 2 - Medium (Priority 2)**:
1. Externalize tool limits
2. Externalize all HTTP timeouts
3. Create cache_config.yaml for TTL strategies
4. Externalize UI behavior settings

**Phase 3 - Low (Priority 3)**:
1. Advanced configuration options
2. Expert-level tuning parameters
3. Performance optimization settings

---

## Estimated Effort

- **Phase 1 (Critical)**: 4-6 hours development + 2 hours testing
- **Phase 2 (Medium)**: 4-6 hours development + 2 hours testing
- **Phase 3 (Low)**: 2-4 hours development + 1 hour testing
- **Documentation**: 2-3 hours per phase

**Total**: 14-22 hours development + 7-8 hours testing/docs

---

## User Stories

### Critical Priority

**As a user with a slow network**, I want to configure CloudWatch timeouts so I don't get connection errors when querying large log volumes.

**As a user with a custom GitHub OAuth app**, I want to configure my own client ID and scopes so I can use LogAI with my organization's GitHub instance.

**As a user who set cache limits in .env**, I want those settings to be respected so I can control disk usage (CURRENT BUG: settings are ignored).

### Medium Priority

**As a power user**, I want to configure default log fetch limits so I don't have to specify them in every query.

**As a user in a bandwidth-constrained environment**, I want to adjust HTTP timeouts so requests don't fail prematurely.

### Low Priority

**As an advanced user**, I want to fine-tune context budget allocation so I can optimize for my specific use case.

---

## Success Criteria

### Phase 1
- [ ] All critical hardcoded values externalized to .env
- [ ] Cache Manager bug fixed (respects user settings)
- [ ] Backward compatible (existing defaults work)
- [ ] All existing tests pass
- [ ] New tests for config loading
- [ ] Documentation updated with new .env variables

### Phase 2
- [ ] Medium priority values externalized
- [ ] cache_config.yaml pattern implemented
- [ ] Example config files created
- [ ] Tests updated
- [ ] User guide updated

### Phase 3
- [ ] Advanced settings externalized
- [ ] Expert configuration documented
- [ ] Performance tuning guide created

---

## Breaking Changes

**None expected** - all changes will:
1. Keep current defaults
2. Add environment variable overrides
3. Use existing settings infrastructure

**One bug fix** (Cache Manager) changes behavior:
- Currently ignores user `.env` settings
- After fix, will respect user settings
- This is the INTENDED behavior, so it's a fix, not a breaking change

---

## Dependencies

- Existing `settings.py` infrastructure
- `.env` file loading mechanism
- `model_config.yaml` pattern (for cache_config.yaml)
- PyYAML (already added)

---

## Questions for User

1. Which phase(s) would you like to implement?
   - Phase 1 (Critical) only?
   - Phases 1 + 2 (Critical + Medium)?
   - All phases?

2. Should we create the cache_config.yaml pattern now or defer to Phase 2?

3. Any specific configurations from the list that are more important to you?

---

## Next Steps

1. User selects priority level
2. Create detailed design document
3. Jackie implements changes
4. Raoul writes tests
5. Han-Ron reviews code
6. Tina updates documentation
7. Commit and push

---

**Prepared by**: Hans (Code Librarian) and George (TPM)
**Status**: Awaiting user decision on scope
