# LogAI MVP - Implementation Plan

**Date:** February 6, 2026  
**Prepared by:** George (TPM)  
**For:** Jackie (Senior Software Engineer)

## Overview

This document provides a detailed implementation plan for the LogAI MVP, broken down into phases with clear deliverables. Follow this plan sequentially, testing each phase before moving to the next.

## Reference Documents

- Requirements: `george-scratch/requirements.md`
- Architecture: `george-scratch/architecture.md` (comprehensive, 1400+ lines)

## Implementation Phases

### Phase 1: Project Setup & Foundation
**Goal:** Set up the project structure with all necessary configuration

**Tasks:**
1. Create Python 3.11+ project with `pyproject.toml`
   - Package name: `logai`
   - Include all dependencies from architecture doc Section 3.5
   - Set up entry point: `logai` command

2. Create directory structure as specified in architecture Section 5.1
   - All directories from `src/logai/` tree
   - Test directories: `tests/unit/`, `tests/integration/`, `tests/fixtures/`
   - Documentation: `docs/`

3. Set up development tools
   - `pytest` for testing
   - `mypy` for type checking
   - `ruff` for linting
   - `.gitignore` for Python project

4. Create `.env.example` file with required environment variables:
   - `LOGAI_LLM_PROVIDER` (anthropic, openai)
   - `LOGAI_ANTHROPIC_API_KEY`
   - `LOGAI_OPENAI_API_KEY`
   - `LOGAI_PII_SANITIZATION_ENABLED` (default: true)
   - `LOGAI_CACHE_DIR` (default: ~/.logai/cache)
   - `AWS_*` variables for CloudWatch

5. Create basic README.md with:
   - Project description
   - Installation instructions
   - Quick start guide
   - Environment variable setup

**Deliverable:** Complete project skeleton that can be installed with `pip install -e .`

**Test:** Run `logai --version` successfully

---

### Phase 2: Configuration Management
**Goal:** Implement type-safe configuration with Pydantic

**Reference:** Architecture Section 11

**Tasks:**
1. Create `src/logai/config/settings.py`
   - Implement `LogAISettings` using Pydantic Settings
   - Support for all environment variables
   - Validation for required fields (API keys, AWS region)
   - Default values where appropriate

2. Create `src/logai/config/validation.py`
   - Validation functions for API keys format
   - AWS region validation
   - Path validation for cache directory

3. Implement configuration loading in `src/logai/cli.py`
   - Load settings on startup
   - Handle missing required config gracefully
   - Display helpful error messages

**Deliverable:** Configuration system that loads and validates settings from environment

**Test:** 
- Unit tests for settings validation
- Test with missing API keys (should error with helpful message)
- Test with valid configuration (should load successfully)

---

### Phase 3: PII Sanitization Layer
**Goal:** Implement configurable PII sanitization (default: enabled)

**Reference:** Architecture Section 9

**Tasks:**
1. Create `src/logai/core/sanitizer.py`
   - Implement `LogSanitizer` class with default patterns:
     - Email addresses
     - IP addresses
     - Credit card numbers
     - SSNs
     - Phone numbers
     - AWS keys
     - API keys/tokens
     - JWT tokens
     - Private keys
   - Configuration toggle via settings
   - Return redaction summary (e.g., "Redacted 3 emails, 2 IPs")

2. Create utility functions:
   - `sanitize_text(text: str) -> tuple[str, dict]` - returns sanitized text + stats
   - `sanitize_logs(logs: list[dict]) -> tuple[list[dict], dict]` - batch sanitization

**Deliverable:** Working PII sanitizer with comprehensive pattern coverage

**Test:**
- Unit tests for each pattern type (see architecture Section 9)
- Test with real-world log examples
- Test configuration toggle (enabled/disabled)
- Verify redaction summary is accurate

---

### Phase 4: AWS CloudWatch Integration
**Goal:** Implement CloudWatch data source with boto3

**Reference:** Architecture Section 8

**Tasks:**
1. Create `src/logai/providers/datasources/base.py`
   - Abstract `BaseDataSource` class defining interface

2. Create `src/logai/providers/datasources/cloudwatch.py`
   - Implement `CloudWatchSource` class
   - Methods:
     - `list_log_groups(prefix, limit)` - with pagination
     - `fetch_logs(log_group, start_time, end_time, filter_pattern, limit)` - with pagination
     - `search_logs(log_group_prefixes, pattern, start_time, end_time)` - multi-group search
   - Implement retry logic with `tenacity`
   - Error handling for common boto3 exceptions
   - Time parsing utilities (support ISO 8601, relative times like "1h ago", epoch ms)

3. Create `src/logai/utils/time.py`
   - Parse relative times: "1h ago", "30m ago", "yesterday"
   - Parse ISO 8601
   - Parse epoch milliseconds
   - Convert to CloudWatch format

**Deliverable:** Working CloudWatch integration that can fetch logs

**Test:**
- Unit tests with mocked boto3 responses (use `moto`)
- Test pagination handling
- Test time parsing utilities
- Test error handling (invalid log group, network errors)
- Integration test with real CloudWatch (optional, requires AWS creds)

---

### Phase 5: LLM Integration with Tools
**Goal:** Implement LiteLLM integration with function calling

**Reference:** Architecture Sections 3.3 and 6

**Tasks:**
1. Create `src/logai/core/tools/base.py`
   - `ToolParameter`, `ToolDefinition`, `BaseTool` classes

2. Create `src/logai/core/tools/registry.py`
   - `ToolRegistry` class with decorator pattern
   - `register()`, `get_tool()`, `get_all_definitions()`, `execute()` methods

3. Create `src/logai/core/tools/cloudwatch.py`
   - Implement tools (see Architecture Section 6.2.1):
     - `ListLogGroupsTool`
     - `FetchLogsTool`
     - `SearchLogsTool`
   - Register tools with `@ToolRegistry.register` decorator
   - Each tool should use CloudWatchSource to fetch data
   - Each tool should use CacheManager (Phase 6) for caching

4. Create `src/logai/providers/llm/base.py`
   - Abstract `BaseLLMProvider` class

5. Create `src/logai/providers/llm/litellm_provider.py`
   - Implement `LiteLLMProvider` using LiteLLM library
   - Support streaming responses
   - Handle function calling
   - Support Anthropic (MVP) and OpenAI

6. Create `src/logai/core/orchestrator.py`
   - `LLMOrchestrator` class (see Architecture Section 6.4)
   - `process_message()` method with tool execution loop
   - Maximum 10 iterations to prevent infinite loops
   - Integration with sanitizer (sanitize logs before sending to LLM)
   - System prompt from Architecture Section 6.5

**Deliverable:** Working LLM orchestrator that can call CloudWatch tools

**Test:**
- Unit tests for each tool
- Unit tests for tool registry
- Mock LLM responses with tool calls
- Integration test: Ask "List log groups" → LLM calls list_log_groups tool
- Integration test: Ask "Show me errors from X" → LLM calls fetch_logs tool
- Test sanitization integration (logs are sanitized before going to LLM)

---

### Phase 6: Caching System
**Goal:** Implement SQLite cache for logs and queries

**Reference:** Architecture Section 7

**Tasks:**
1. Create `src/logai/cache/sqlite_store.py`
   - Implement SQLite schema from Architecture Section 7.3
   - Async operations using `aiosqlite`
   - Methods:
     - `get(key)` - retrieve cached entry
     - `set(key, data, ttl)` - store entry
     - `delete(key)` - remove entry
     - `delete_expired()` - cleanup expired entries
     - `get_cache_size()` - total cache size
     - `get_entry_count()` - number of entries
     - `evict_if_needed()` - LRU eviction

2. Create `src/logai/cache/manager.py`
   - `CacheManager` orchestration layer
   - Cache key generation (Architecture Section 7.4)
   - TTL calculation (Architecture Section 7.5)
   - Size management and eviction (Architecture Section 7.6)
   - Background cleanup task

3. Integrate caching with CloudWatch tools
   - Check cache before fetching from CloudWatch
   - Store results in cache after fetching

**Deliverable:** Working cache system that reduces CloudWatch API calls

**Test:**
- Unit tests for cache operations
- Test TTL expiration
- Test LRU eviction
- Test cache key generation (same query = same key)
- Integration test: Fetch logs twice → second fetch is from cache
- Test cache size limits and eviction

---

### Phase 7: TUI with Textual
**Goal:** Build interactive chat interface

**Reference:** Architecture Sections 3.2 and 4.2.1

**Tasks:**
1. Create `src/logai/ui/app.py`
   - Main Textual application class
   - Basic layout with chat panel and status bar
   - Handle keyboard input
   - Display streamed LLM responses

2. Create `src/logai/ui/widgets/message.py`
   - Message widget for displaying chat messages
   - Support markdown rendering via Rich
   - Syntax highlighting for code blocks

3. Create `src/logai/ui/widgets/input.py`
   - Multi-line input widget
   - Submit on Enter, newline on Shift+Enter
   - Command history (up/down arrows)

4. Create `src/logai/ui/widgets/status.py`
   - Status bar showing:
     - Connection status
     - Current LLM provider
     - Cache status
     - Loading indicator

5. Create `src/logai/ui/styles/app.tcss`
   - Textual CSS for styling the UI

6. Create `src/logai/ui/screens/chat.py`
   - Main chat screen
   - Wire up widgets
   - Handle user input → orchestrator → display response

7. Create `src/logai/cli.py`
   - CLI entry point with argument parsing
   - Commands:
     - `logai` - Start TUI chat
     - `logai --version` - Show version
     - `logai --help` - Show help
   - Load configuration and launch TUI app

8. Implement special commands:
   - `/help` - Show available commands
   - `/clear` - Clear conversation
   - `/cache status` - Show cache stats
   - `/cache clear` - Clear cache
   - `/quit` or `/exit` - Exit application

**Deliverable:** Working TUI that users can chat with

**Test:**
- Manual testing of TUI interaction
- Test streaming responses display correctly
- Test markdown rendering
- Test code block syntax highlighting
- Test special commands
- Test error display

---

### Phase 8: Integration & End-to-End Testing
**Goal:** Verify complete system works together

**Tasks:**
1. Create integration tests in `tests/integration/`
   - Test complete flow: User message → LLM → Tool call → CloudWatch → Cache → Response
   - Test with real Anthropic API (requires API key)
   - Test with mocked CloudWatch (use moto)

2. Create example scenarios:
   - "List all log groups"
   - "Show me errors from /aws/lambda/my-function in the last hour"
   - "Search for 'timeout' across all Lambda functions"
   - Multi-turn conversation with follow-up questions

3. Error handling verification:
   - Invalid log group name
   - No logs found in time range
   - API errors (rate limiting, network)
   - Invalid configuration

4. Performance testing:
   - Measure cache hit rate
   - Measure response times
   - Test with large log volumes

5. Create user documentation:
   - Installation guide
   - Configuration guide
   - Usage examples
   - Troubleshooting

**Deliverable:** Fully functional MVP ready for use

**Test:**
- Run full integration test suite
- Manual end-to-end testing with real services
- Performance benchmarks
- Documentation review

---

## Success Criteria

The MVP is complete when:

1. ✅ User can install with `pip install -e .`
2. ✅ User can configure with environment variables
3. ✅ User can run `logai` to start TUI chat
4. ✅ User can ask questions about CloudWatch logs in natural language
5. ✅ LLM uses tools to fetch logs from CloudWatch
6. ✅ PII is sanitized by default (configurable)
7. ✅ Logs are cached to reduce API calls
8. ✅ Responses are streamed in real-time
9. ✅ Error handling is robust and user-friendly
10. ✅ All unit and integration tests pass
11. ✅ Documentation is complete

## Notes for Jackie

- **Follow the phases sequentially** - each builds on the previous
- **Write tests as you go** - don't save testing for the end
- **Commit frequently** - small, focused commits
- **Ask questions** - if anything is unclear, ask George
- **Reference the architecture doc** - it has detailed code examples
- **Use type hints** - mypy should pass with no errors
- **Handle errors gracefully** - always provide helpful error messages

## Getting Help

- **Architecture Questions**: Ask George to clarify with Sally
- **Code Review**: Billy will review completed phases
- **Testing Strategy**: Raoul can help with test coverage
- **Documentation**: Tina will handle final documentation

Good luck! 🚀
