# GitHub Copilot Integration - Requirements Document

**Date:** February 11, 2026  
**Project:** LogAI  
**Feature:** GitHub Copilot LLM Provider Integration  
**Status:** Approved for Implementation

---

## Executive Summary

Add GitHub Copilot as an LLM provider option in LogAI, enabling users to leverage GitHub Copilot's models (Claude Opus 4.6, GPT-4.1, Gemini 2.5 Pro, etc.) for natural language CloudWatch log querying.

---

## User Story

**As a** LogAI user with GitHub Copilot access  
**I want to** use GitHub Copilot models as my LLM provider  
**So that** I can leverage GitHub's AI models without managing separate API keys

---

## Business Goals

1. **Reduce friction** - Users with GitHub Copilot access don't need additional API keys
2. **Expand model options** - Provide access to 24+ models through a single authentication
3. **Match industry standards** - Implement OAuth authentication like other modern CLI tools
4. **Improve user experience** - Simple `logai auth login` flow similar to OpenCode

---

## Functional Requirements

### FR-1: OAuth Authentication
- **FR-1.1:** Implement OAuth 2.0 Device Code Flow for GitHub authentication
- **FR-1.2:** Store authentication tokens securely in `~/.local/share/logai/auth.json`
- **FR-1.3:** Use file permissions 600 (owner read/write only)
- **FR-1.4:** Support environment variable override: `LOGAI_GITHUB_COPILOT_TOKEN`
- **FR-1.5:** Use existing GitHub OAuth Client ID: `Iv1.b507a08c87ecfe98`

### FR-2: CLI Authentication Commands
- **FR-2.1:** `logai auth login` - Initiate OAuth device code flow
- **FR-2.2:** `logai auth logout` - Remove stored credentials
- **FR-2.3:** `logai auth status` - Check authentication status and show token info (masked)
- **FR-2.4:** `logai auth list` - List all authenticated providers

### FR-3: GitHub Copilot Provider
- **FR-3.1:** Implement `GitHubCopilotProvider` class following `BaseLLMProvider` interface
- **FR-3.2:** Support API endpoint: `https://api.githubcopilot.com/chat/completions`
- **FR-3.3:** Format requests to OpenAI-compatible API format
- **FR-3.4:** Handle bearer token authentication (`Authorization: Bearer gho_...`)
- **FR-3.5:** Support tool calling (function calling) for CloudWatch APIs
- **FR-3.6:** Gracefully handle 401 (unauthorized) and prompt re-authentication

### FR-4: Model Selection
- **FR-4.1:** **Dynamic model list fetching** from GitHub Copilot API
- **FR-4.2:** Cache model list locally for performance
- **FR-4.3:** Support model specification via `--model github-copilot/claude-opus-4.6`
- **FR-4.4:** Provide default model: `github-copilot/claude-opus-4.6`
- **FR-4.5:** List available models with `logai models --provider github-copilot` (or similar)

### FR-5: Configuration Management
- **FR-5.1:** Add GitHub Copilot settings to `src/logai/config/settings.py`
- **FR-5.2:** Support `.env` file configuration:
  - `LOGAI_GITHUB_COPILOT_TOKEN` - Override token
  - `LOGAI_GITHUB_COPILOT_MODEL` - Default model
  - `LOGAI_GITHUB_COPILOT_API_BASE` - Override API endpoint (for testing)
- **FR-5.3:** Maintain compatibility with existing provider configuration

### FR-6: Provider Integration
- **FR-6.1:** Integrate with existing provider factory pattern
- **FR-6.2:** Allow provider selection via `--provider github-copilot` CLI argument
- **FR-6.3:** Support configuration via environment variable: `LOGAI_LLM_PROVIDER=github-copilot`
- **FR-6.4:** Coexist with existing providers (Anthropic, OpenAI, Ollama)

---

## Non-Functional Requirements

### NFR-1: Security
- **NFR-1.1:** Store tokens with file permissions 600 (owner only)
- **NFR-1.2:** Mask tokens in all log output and error messages
- **NFR-1.3:** Use atomic file writes to prevent partial credential writes
- **NFR-1.4:** Validate token format before storage (`gho_` prefix)
- **NFR-1.5:** Clear error messages without exposing sensitive data

### NFR-2: Reliability
- **NFR-2.1:** Handle network failures gracefully (timeouts, connection errors)
- **NFR-2.2:** Implement retry logic with exponential backoff for API requests
- **NFR-2.3:** Validate API responses before processing
- **NFR-2.4:** Provide clear error messages for common failure scenarios

### NFR-3: Performance
- **NFR-3.1:** OAuth device code polling should be efficient (5-second intervals)
- **NFR-3.2:** Token validation should not add significant latency to requests
- **NFR-3.3:** Model list caching to avoid unnecessary API calls
- **NFR-3.4:** Async API calls where appropriate

### NFR-4: Maintainability
- **NFR-4.1:** Follow existing LogAI code patterns and conventions
- **NFR-4.2:** Use type hints throughout
- **NFR-4.3:** Comprehensive docstrings for all public methods
- **NFR-4.4:** Unit test coverage > 80%
- **NFR-4.5:** Integration tests for OAuth flow (mocked)

### NFR-5: Usability
- **NFR-5.1:** Authentication flow should be clear and guided
- **NFR-5.2:** Error messages should be actionable
- **NFR-5.3:** CLI commands should follow Unix conventions
- **NFR-5.4:** Documentation with examples and troubleshooting

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **OAuth Client ID** | Use existing `Iv1.b507a08c87ecfe98` | Quick implementation, works immediately, can change later |
| **Token Storage** | File-based with 600 permissions | Secure enough for v1, XDG compliant |
| **Keyring Support** | Deferred to v2 | Reduces initial complexity, file-based is sufficient |
| **Model List** | **Dynamic API fetch with caching** | User preference - adds flexibility, handles model changes |
| **CLI Framework** | Extend existing argparse | Consistency with current implementation |
| **Provider Pattern** | New `GitHubCopilotProvider` class | Clean separation, follows existing patterns |

---

## Implementation Phases

### Phase 1: Authentication Infrastructure (Days 1-2)
- Create directory structure (`src/logai/auth/`)
- Implement OAuth device code flow
- Implement secure token storage
- Create authentication dataclasses

**Deliverables:**
- `src/logai/auth/__init__.py`
- `src/logai/auth/github_copilot_auth.py`
- `src/logai/auth/token_storage.py`

### Phase 2: CLI Commands (Days 3-4)
- Add `auth` subcommand group to CLI
- Implement `login`, `logout`, `status`, `list` commands
- Add user-friendly output and error handling

**Deliverables:**
- Updates to `src/logai/cli.py`
- CLI help text and examples

### Phase 3: GitHub Copilot Provider (Days 5-6)
- Implement `GitHubCopilotProvider` class
- Add API request/response handling
- Implement error handling and retries
- Add tool calling support

**Deliverables:**
- `src/logai/providers/llm/github_copilot_provider.py`
- `src/logai/providers/llm/__init__.py` updates

### Phase 4: Model Management (Days 7-8)
- Implement dynamic model list fetching
- Add model list caching
- Create model selection logic
- Add `logai models` command or similar

**Deliverables:**
- `src/logai/providers/llm/github_copilot_models.py`
- Model cache storage

### Phase 5: Configuration & Integration (Days 9-10)
- Add settings to `settings.py`
- Integrate with provider factory
- Add environment variable support
- Update startup configuration

**Deliverables:**
- Updates to `src/logai/config/settings.py`
- Updates to provider factory/initialization

### Phase 6: Testing (Days 11-12)
- Unit tests for authentication
- Unit tests for provider
- Integration tests (mocked OAuth)
- End-to-end testing

**Deliverables:**
- `tests/unit/test_github_copilot_auth.py`
- `tests/unit/test_github_copilot_provider.py`
- `tests/integration/test_github_copilot_flow.py`

### Phase 7: Documentation & Polish (Days 13-14)
- Update README.md
- Create GitHub Copilot usage guide
- Add troubleshooting section
- Update .env.example

**Deliverables:**
- Updated documentation
- Usage examples
- Troubleshooting guide

---

## Success Criteria

### Must Have
- ✅ User can authenticate with `logai auth login`
- ✅ User can use GitHub Copilot models with `--provider github-copilot`
- ✅ Authentication persists across sessions
- ✅ Tool calling works with GitHub Copilot models
- ✅ Clear error messages for common issues
- ✅ All existing tests continue to pass
- ✅ New tests have >80% coverage

### Should Have
- ✅ Dynamic model list fetching
- ✅ Model list caching
- ✅ Token masking in all output
- ✅ Comprehensive error handling

### Nice to Have (Future)
- ⏳ OS keyring integration
- ⏳ Token refresh mechanism
- ⏳ LogAI-specific OAuth App registration
- ⏳ Model auto-selection based on task

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| GitHub changes OAuth client ID | High | Low | Document easy update process; consider registering our own |
| GitHub changes available models | Medium | Medium | Dynamic model fetching handles this automatically |
| Token expiration issues | Medium | Low | Handle 401 gracefully, prompt re-auth |
| Dynamic model fetch adds latency | Low | Medium | Cache model list, async fetching |
| Security: file-based storage | Medium | Low | Use 600 permissions, plan keyring for v2 |

---

## Dependencies

### External
- GitHub OAuth API (device code flow)
- GitHub Copilot API endpoint (`api.githubcopilot.com`)
- User has GitHub Copilot access/subscription

### Internal
- Existing `BaseLLMProvider` interface
- `src/logai/config/settings.py` Pydantic models
- `src/logai/cli.py` argparse framework
- pytest testing framework

---

## Out of Scope (v1)

- ❌ OS keyring integration (macOS Keychain, Windows Credential Manager)
- ❌ Token refresh mechanism
- ❌ LogAI-specific OAuth App registration with GitHub
- ❌ Multi-account GitHub authentication
- ❌ GitHub Enterprise support
- ❌ Proxy support for OAuth flow

---

## Testing Strategy

### Unit Tests
- OAuth device code flow logic
- Token storage and retrieval
- API request formatting
- Response parsing
- Error handling

### Integration Tests
- Full OAuth flow (mocked GitHub APIs)
- End-to-end provider usage
- CLI command integration
- Configuration loading

### Manual Testing
- Real OAuth authentication with GitHub
- Model selection and usage
- Token persistence across sessions
- Error scenarios (network failures, invalid tokens)

---

## Documentation Requirements

1. **README.md Update**
   - Add GitHub Copilot to supported providers
   - Add authentication instructions
   - Add usage examples

2. **GitHub Copilot Usage Guide** (`docs/github-copilot.md`)
   - Getting started
   - Authentication flow
   - Model selection
   - Troubleshooting
   - FAQ

3. **API Documentation**
   - Document `GitHubCopilotProvider` class
   - Document authentication module
   - Document CLI commands

4. **.env.example Update**
   - Add GitHub Copilot environment variables
   - Add usage examples

---

## Acceptance Criteria

### User Can:
1. ✅ Authenticate with GitHub using `logai auth login`
2. ✅ View authentication status with `logai auth status`
3. ✅ Use GitHub Copilot models: `logai --provider github-copilot`
4. ✅ Select specific models: `--model github-copilot/claude-opus-4.6`
5. ✅ See dynamically fetched available models
6. ✅ Use environment variable for token: `LOGAI_GITHUB_COPILOT_TOKEN=...`
7. ✅ Logout and clear credentials: `logai auth logout`

### System Must:
1. ✅ Store tokens securely (600 permissions)
2. ✅ Mask tokens in all output
3. ✅ Handle OAuth flow correctly (device code polling)
4. ✅ Support tool calling with GitHub Copilot models
5. ✅ Coexist with other providers
6. ✅ Pass all existing tests
7. ✅ Have >80% test coverage for new code

### Documentation Must:
1. ✅ Explain authentication process
2. ✅ Show usage examples
3. ✅ Include troubleshooting guide
4. ✅ Document environment variables

---

## Open Questions

None - all questions resolved:
- ✅ OAuth Client ID: Use existing `Iv1.b507a08c87ecfe98`
- ✅ Keyring support: Defer to v2
- ✅ Model list: Dynamic API fetch with caching

---

## Approval

- **User Decision:** Approved - Option A (Move forward with implementation)
- **Architecture:** Approved by Sally (architecture-github-copilot-integration.md)
- **Implementation Lead:** Jackie (Senior Software Engineer)
- **Estimated Timeline:** 2 weeks (accelerated for AI agents)

---

## References

- Investigation documents by Hans:
  - `INVESTIGATION_SUMMARY.md`
  - `OPENCODE_AUTH_INVESTIGATION.md`
  - `OPENCODE_TECHNICAL_DETAILS.md`
  - `LOGAI_IMPLEMENTATION_ROADMAP.md`
- Architecture document by Sally:
  - `george-scratch/architecture-github-copilot-integration.md`
- OpenCode GitHub Copilot implementation (reference)
- RFC 8628: OAuth 2.0 Device Authorization Grant
