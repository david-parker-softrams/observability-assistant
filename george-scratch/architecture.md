# AI-Powered Observability Assistant - Architecture Design Document

**Document Version:** 1.1  
**Date:** February 6, 2026  
**Author:** Sally (Senior Software Architect)  
**Status:** APPROVED - Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [MVP Scope](#2-mvp-scope)
3. [Technology Stack Selection](#3-technology-stack-selection)
4. [System Architecture](#4-system-architecture)
5. [Project Structure](#5-project-structure)
6. [LLM Integration Design](#6-llm-integration-design)
7. [Caching Strategy](#7-caching-strategy)
8. [AWS CloudWatch Integration](#8-aws-cloudwatch-integration)
9. [PII Sanitization Layer](#9-pii-sanitization-layer)
10. [Extensibility Design](#10-extensibility-design)
11. [Configuration Management](#11-configuration-management)
12. [Error Handling & Logging](#12-error-handling--logging)
13. [Testing Strategy](#13-testing-strategy)
14. [Packaging & Distribution](#14-packaging--distribution)
15. [Security Considerations](#15-security-considerations)
16. [Appendix: Open Questions Resolution](#16-appendix-open-questions-resolution)

---

## 1. Executive Summary

This document outlines the architecture for the AI-Powered Observability Assistant (LogAI), a CLI/TUI tool that enables DevOps Engineers and SREs to query and analyze observability data through natural language. The MVP focuses on AWS CloudWatch integration with Anthropic Claude as the primary LLM provider, with an extensible design for future data sources and LLM providers.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | **Python 3.11+** | Best LLM library ecosystem, rapid development, team familiarity |
| TUI Framework | **Textual** | Modern async Python TUI, rich widget library, active development |
| Caching | **SQLite** | Simple, reliable, sufficient for MVP (file-based deferred to post-MVP) |
| LLM Integration | **LiteLLM** | Unified interface for multiple LLM providers (APPROVED) |
| AWS SDK | **boto3** | Official AWS SDK, well-documented, production-proven |
| PII Protection | **Sanitization Layer** | Configurable redaction, enabled by default |

---

## 2. MVP Scope

> **This section defines the approved MVP scope. Features marked as "Post-MVP" should not be implemented in the initial release.**

### 2.1 MVP Deliverables (Phase 1)

| Component | MVP Scope | Post-MVP |
|-----------|-----------|----------|
| **TUI** | Basic chat interface with Textual | Log viewer panel, split panes |
| **LLM Provider** | Anthropic Claude only | OpenAI, AWS Bedrock |
| **LLM Integration** | LiteLLM (approved) | Direct SDK fallbacks |
| **Data Source** | AWS CloudWatch only | Splunk, Datadog, New Relic |
| **Caching** | SQLite only | File-based compression for large payloads |
| **PII Sanitization** | Full implementation (default: enabled) | Custom pattern plugins |
| **Configuration** | Environment variables | YAML/TOML config files |
| **Authentication** | boto3 credential chain | Vault integration |

### 2.2 MVP Feature Checklist

Jackie should implement these features in priority order:

1. **Project Setup**
   - [ ] Python 3.11+ project with pyproject.toml
   - [ ] Basic directory structure
   - [ ] Development dependencies (pytest, mypy, ruff)

2. **Configuration**
   - [ ] Pydantic settings with environment variables
   - [ ] Anthropic API key validation
   - [ ] AWS credential validation

3. **Core LLM Integration**
   - [ ] LiteLLM provider wrapper for Anthropic
   - [ ] Tool/function registration system
   - [ ] Basic conversation handling

4. **CloudWatch Integration**
   - [ ] List log groups tool
   - [ ] Fetch logs tool
   - [ ] Basic error handling

5. **PII Sanitization**
   - [ ] Sanitizer with default patterns
   - [ ] Configuration toggle
   - [ ] Integration with LLM orchestrator

6. **Caching**
   - [ ] SQLite cache store
   - [ ] TTL-based expiration
   - [ ] Basic eviction

7. **TUI**
   - [ ] Basic Textual app with chat panel
   - [ ] Message display and input
   - [ ] Status bar

8. **Testing**
   - [ ] Unit tests for core modules
   - [ ] Integration tests with moto/respx

---

## 3. Technology Stack Selection

### 3.1 Programming Language: Python 3.11+

**Recommendation:** Python 3.11 or higher

**Rationale:**

1. **LLM Ecosystem Leadership**: Python has the most mature LLM integration libraries (LangChain, LiteLLM, OpenAI SDK, Anthropic SDK). This is critical for our core functionality.

2. **AWS SDK Maturity**: `boto3` is the official, best-documented AWS SDK with excellent CloudWatch support.

3. **TUI Options**: Python has excellent TUI libraries (Textual, Rich, Prompt Toolkit) that are actively maintained.

4. **Development Velocity**: For an MVP, Python allows rapid iteration. DevOps/SRE teams are typically comfortable with Python.

5. **Type Safety**: Python 3.11+ with strict type hints and tools like `mypy` provides adequate type safety for a project of this scope.

**Alternatives Considered:**

| Language | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Go** | Fast binaries, good CLI tools, strong concurrency | Weaker LLM libraries, no mature TUI frameworks, slower development | Not ideal for LLM-heavy MVP |
| **TypeScript/Node** | Good async model, Ink for TUI | NPM dependency hell, less mature AWS/LLM libraries than Python | Close second, but Python wins on ecosystem |

### 3.2 TUI Framework: Textual

**Recommendation:** [Textual](https://textual.textualize.io/) (by Textualize)

**Rationale:**

1. **Modern Architecture**: Built on async Python, excellent for handling streaming LLM responses.

2. **Rich Widget Library**: Provides chat-like interfaces, scrollable panels, input boxes, and syntax highlighting out of the box.

3. **CSS-like Styling**: Uses TCSS (Textual CSS) for styling, making UI development intuitive.

4. **Active Development**: Well-maintained, regular releases, growing community.

5. **Built on Rich**: Seamless integration with Rich for formatted output (syntax highlighting, tables, markdown).

**Example Chat Interface Capabilities:**
- Scrollable message history
- Input field with multi-line support
- Status indicators (loading, connected, error)
- Split panes for showing logs alongside chat

### 3.3 LLM Integration: LiteLLM (APPROVED)

**Recommendation:** [LiteLLM](https://github.com/BerriAI/litellm) as the primary integration layer

> **APPROVED**: Stakeholder approved LiteLLM for unified provider access. This simplifies integration and future provider additions.

**Rationale:**

1. **Unified Interface**: Single API for OpenAI, Anthropic, and 100+ other providers (including future Bedrock support).

2. **Function Calling Support**: Handles the nuances of function calling across different providers.

3. **Streaming Support**: Built-in support for streaming responses.

4. **Fallback Handling**: Can configure fallback providers if primary fails.

5. **Cost Tracking**: Built-in token counting and cost estimation.

**Architecture:**
```
User Request → LiteLLM → [Anthropic API | OpenAI API | Future: Bedrock]
                  ↓
            Unified Response Format
```

**Alternative Considered:** Direct SDK usage (anthropic, openai packages)
- More control but requires maintaining separate code paths for each provider
- May revisit post-MVP if LiteLLM doesn't meet specific needs

### 3.4 AWS SDK: boto3

**Recommendation:** `boto3` with `botocore` for low-level operations

**Rationale:**
- Official AWS SDK for Python
- Comprehensive CloudWatch Logs support
- Built-in retry logic and credential handling
- Pagination support for large result sets

### 3.5 Complete Dependency List

```toml
# pyproject.toml - Key Dependencies

[project]
requires-python = ">=3.11"

dependencies = [
    # Core
    "textual>=0.47.0",          # TUI framework
    "rich>=13.7.0",              # Rich text formatting
    
    # LLM Integration
    "litellm>=1.30.0",           # Unified LLM interface
    "anthropic>=0.18.0",         # Anthropic SDK (direct access if needed)
    "openai>=1.12.0",            # OpenAI SDK (direct access if needed)
    
    # AWS
    "boto3>=1.34.0",             # AWS SDK
    "botocore>=1.34.0",          # AWS low-level SDK
    
    # Configuration & Validation
    "pydantic>=2.6.0",           # Configuration validation
    "pydantic-settings>=2.2.0",  # Environment variable parsing
    "python-dotenv>=1.0.0",      # .env file support
    
    # Utilities
    "structlog>=24.1.0",         # Structured logging
    "tenacity>=8.2.0",           # Retry logic
    "aiosqlite>=0.19.0",         # Async SQLite for caching
    "aiofiles>=23.2.0",          # Async file operations
    "httpx>=0.27.0",             # Async HTTP client
    
    # Date/Time
    "python-dateutil>=2.8.0",    # Date parsing
    "pendulum>=3.0.0",           # Better datetime handling
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "moto>=5.0.0",               # AWS mocking
    "respx>=0.20.0",             # HTTP mocking
    "pytest-mock>=3.12.0",
]
```

---

## 4. System Architecture

### 4.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE LAYER                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Textual TUI Application                         │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────────────┐ │ │
│  │  │ Chat Panel   │  │ Status Bar       │  │ Log Viewer Panel (future)  │ │ │
│  │  │ - Messages   │  │ - Connection     │  │ - Syntax Highlighting      │ │ │
│  │  │ - Input      │  │ - Provider       │  │ - Search                   │ │ │
│  │  │ - History    │  │ - Cache Status   │  │ - Filtering                │ │ │
│  │  └──────────────┘  └──────────────────┘  └────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            APPLICATION CORE LAYER                            │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────────┐  │
│  │  Chat Controller  │  │  Session Manager  │  │   Response Formatter    │  │
│  │  - User input     │  │  - Conversation   │  │   - Markdown render     │  │
│  │  - Command parse  │  │  - Context mgmt   │  │   - Log formatting      │  │
│  │  - Response route │  │  - History        │  │   - Table display       │  │
│  └─────────┬─────────┘  └───────────────────┘  └─────────────────────────┘  │
│            │                                                                 │
│            ▼                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         LLM Orchestrator                               │  │
│  │  - Tool registration & execution                                       │  │
│  │  - Conversation management                                             │  │
│  │  - Streaming response handling                                         │  │
│  │  - Function call coordination                                          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTEGRATION LAYER                                  │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────────┐  │
│  │   LLM Provider    │  │  Data Source      │  │    Cache Manager        │  │
│  │   Interface       │  │  Interface        │  │                         │  │
│  │  ┌─────────────┐  │  │  ┌─────────────┐  │  │  ┌──────────────────┐   │  │
│  │  │ Anthropic   │  │  │  │ CloudWatch  │  │  │  │ Query Cache      │   │  │
│  │  │ Provider    │  │  │  │ Source      │  │  │  │ (SQLite)         │   │  │
│  │  ├─────────────┤  │  │  ├─────────────┤  │  │  ├──────────────────┤   │  │
│  │  │ OpenAI      │  │  │  │ Splunk      │  │  │  │ Log Cache        │   │  │
│  │  │ Provider    │  │  │  │ (Future)    │  │  │  │ (File-based)     │   │  │
│  │  ├─────────────┤  │  │  ├─────────────┤  │  │  └──────────────────┘   │  │
│  │  │ Bedrock     │  │  │  │ Datadog     │  │  │                         │  │
│  │  │ (Future)    │  │  │  │ (Future)    │  │  │                         │  │
│  │  └─────────────┘  │  │  └─────────────┘  │  │                         │  │
│  └───────────────────┘  └───────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                 │
                    ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SERVICES                                  │
│  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────────────┐  │
│  │   Anthropic API   │  │   AWS CloudWatch  │  │   Local Filesystem      │  │
│  │   OpenAI API      │  │   Logs API        │  │   (Cache Storage)       │  │
│  └───────────────────┘  └───────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Descriptions

#### 4.2.1 User Interface Layer

**TUI Application** (`ui/`)
- Main entry point for user interaction
- Handles keyboard input, display updates, and user feedback
- Manages layout: chat panel, status bar, and future log viewer
- Streams LLM responses character-by-character for real-time feedback

#### 4.2.2 Application Core Layer

**Chat Controller** (`core/chat.py`)
- Processes user input and routes to appropriate handlers
- Manages special commands (e.g., `/clear`, `/config`, `/help`)
- Coordinates between UI and LLM Orchestrator

**Session Manager** (`core/session.py`)
- Maintains conversation history and context
- Manages context window limits (truncation strategy)
- Persists sessions for potential future "resume" feature

**Response Formatter** (`core/formatter.py`)
- Formats LLM responses for TUI display
- Renders markdown, code blocks, and tables
- Formats log data with syntax highlighting

**LLM Orchestrator** (`core/orchestrator.py`)
- **Central coordinator** for LLM interactions
- Registers and manages available tools/functions
- Executes tool calls and handles results
- Manages conversation flow with function calling loops

#### 4.2.3 Integration Layer

**LLM Provider Interface** (`providers/llm/`)
- Abstract base class defining LLM provider contract
- Concrete implementations for each provider
- Handles provider-specific quirks (response formats, rate limits)

**Data Source Interface** (`providers/datasources/`)
- Abstract base class for observability data sources
- CloudWatch implementation for MVP
- Defines standard methods: `fetch_logs()`, `list_log_groups()`, etc.

**Cache Manager** (`cache/`)
- Hybrid caching: SQLite for metadata/queries, files for log payloads
- Handles cache invalidation, TTL, and size management
- Thread-safe async operations

### 4.3 Data Flow

#### 4.3.1 Standard Query Flow

```
User: "Show me errors from the auth-service in the last hour"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 1. TUI captures input, sends to Chat Controller                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Chat Controller packages message, sends to LLM Orchestrator      │
│    - Includes conversation history                                  │
│    - Includes available tools/functions                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. LLM Orchestrator sends to LLM Provider (via LiteLLM)             │
│    - Streams response back to TUI                                   │
│    - Detects function call requests                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. LLM requests tool: fetch_cloudwatch_logs(                        │
│       log_group="/aws/lambda/auth-service",                         │
│       start_time="-1h",                                             │
│       filter_pattern="ERROR"                                        │
│    )                                                                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Cache Manager checks for cached results                          │
│    - Cache HIT: Return cached data                                  │
│    - Cache MISS: Continue to CloudWatch                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. CloudWatch Source fetches logs via boto3                         │
│    - Handles pagination                                             │
│    - Applies rate limiting                                          │
│    - Returns log events                                             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. Cache Manager stores results                                     │
│    - Metadata in SQLite                                             │
│    - Log payloads in compressed files                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. Tool result returned to LLM Orchestrator                         │
│    - LLM receives log data                                          │
│    - LLM analyzes and generates response                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. LLM response streamed to TUI                                     │
│    - User sees analysis in real-time                                │
│    - Response formatted with markdown/code highlighting             │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.3.2 Multi-Tool Flow (Complex Query)

For queries like "Compare error rates between auth-service and user-service over the last 24 hours":

1. LLM may issue **multiple parallel tool calls**
2. Orchestrator executes tools concurrently where possible
3. Results aggregated and returned to LLM
4. LLM synthesizes final analysis

---

## 5. Project Structure

### 5.1 Directory Layout

```
observability-assistant/
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # Project documentation
├── LICENSE                     # License file
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules
│
├── src/
│   └── logai/                  # Main package (LogAI = Log + AI)
│       ├── __init__.py
│       ├── __main__.py         # Entry point: python -m logai
│       ├── cli.py              # CLI argument parsing
│       │
│       ├── ui/                 # User Interface Layer
│       │   ├── __init__.py
│       │   ├── app.py          # Main Textual application
│       │   ├── screens/        # TUI screens
│       │   │   ├── __init__.py
│       │   │   ├── chat.py     # Main chat screen
│       │   │   └── config.py   # Configuration screen
│       │   ├── widgets/        # Custom TUI widgets
│       │   │   ├── __init__.py
│       │   │   ├── message.py  # Chat message widget
│       │   │   ├── input.py    # User input widget
│       │   │   └── status.py   # Status bar widget
│       │   └── styles/         # TCSS stylesheets
│       │       └── app.tcss
│       │
│       ├── core/               # Application Core Layer
│       │   ├── __init__.py
│       │   ├── orchestrator.py # LLM orchestration
│       │   ├── chat.py         # Chat controller
│       │   ├── session.py      # Session management
│       │   ├── formatter.py    # Response formatting
│       │   ├── sanitizer.py    # PII sanitization (MVP)
│       │   └── tools/          # LLM Tools/Functions
│       │       ├── __init__.py
│       │       ├── base.py     # Base tool class
│       │       ├── registry.py # Tool registry
│       │       ├── cloudwatch.py  # CloudWatch tools
│       │       └── analysis.py    # Analysis tools
│       │
│       ├── providers/          # Integration Layer
│       │   ├── __init__.py
│       │   ├── llm/            # LLM Providers
│       │   │   ├── __init__.py
│       │   │   ├── base.py     # Abstract LLM provider
│       │   │   └── litellm_provider.py  # LiteLLM unified provider (MVP)
│       │   │
│       │   └── datasources/    # Data Sources
│       │       ├── __init__.py
│       │       ├── base.py     # Abstract data source
│       │       └── cloudwatch.py  # AWS CloudWatch
│       │
│       ├── cache/              # Caching Layer
│       │   ├── __init__.py
│       │   ├── manager.py      # Cache orchestration
│       │   └── sqlite_store.py # SQLite for metadata (MVP)
│       │
│       ├── config/             # Configuration
│       │   ├── __init__.py
│       │   ├── settings.py     # Pydantic settings
│       │   └── validation.py   # Config validation
│       │
│       └── utils/              # Utilities
│           ├── __init__.py
│           ├── logging.py      # Logging setup
│           ├── retry.py        # Retry decorators
│           └── time.py         # Time parsing utilities
│
├── tests/                      # Test Suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests
│   │   ├── __init__.py
│   │   ├── test_orchestrator.py
│   │   ├── test_cache.py
│   │   ├── test_sanitizer.py   # PII sanitization tests
│   │   └── ...
│   ├── integration/            # Integration tests
│   │   ├── __init__.py
│   │   ├── test_cloudwatch.py
│   │   └── ...
│   └── fixtures/               # Test fixtures/data
│       ├── cloudwatch_responses/
│       └── llm_responses/
│
└── docs/                       # Documentation
    ├── architecture.md         # This document
    ├── configuration.md        # Config guide
    └── development.md          # Developer guide
```

### 5.2 Package Name

**Package Name:** `logai` (Log + AI)

- Short, memorable, easy to type
- Clearly describes the tool's purpose
- No conflicts with existing popular packages
- CLI command: `logai`

### 5.3 Module Organization Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Dependency Direction**: Higher layers depend on lower layers, never reverse
3. **Interface Segregation**: Abstract base classes define contracts between layers
4. **Explicit Exports**: Each package's `__init__.py` defines public API

---

## 6. LLM Integration Design

### 6.1 Function Calling Architecture

The LLM will use function calling (tool use) to interact with observability data. This is the heart of the system.

```python
# core/tools/base.py

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """Schema for a single tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None

class ToolDefinition(BaseModel):
    """Complete tool definition for LLM."""
    name: str
    description: str
    parameters: list[ToolParameter]

class BaseTool(ABC):
    """Abstract base class for all LLM tools."""
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return tool definition for LLM."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the tool with given parameters."""
        pass
```

### 6.2 MVP Tool Definitions

#### 6.2.1 CloudWatch Tools

```python
# Tool: list_log_groups
{
    "name": "list_log_groups",
    "description": "List available CloudWatch log groups. Use this to discover what log groups exist before querying logs.",
    "parameters": [
        {
            "name": "prefix",
            "type": "string",
            "description": "Filter log groups by prefix (e.g., '/aws/lambda/')",
            "required": false
        },
        {
            "name": "limit",
            "type": "integer",
            "description": "Maximum number of log groups to return (default: 50)",
            "required": false
        }
    ]
}

# Tool: fetch_logs
{
    "name": "fetch_logs",
    "description": "Fetch log events from CloudWatch. Use this to retrieve actual log data for analysis.",
    "parameters": [
        {
            "name": "log_group",
            "type": "string",
            "description": "The CloudWatch log group name (e.g., '/aws/lambda/my-function')",
            "required": true
        },
        {
            "name": "start_time",
            "type": "string",
            "description": "Start of time range. Supports: ISO 8601 (2024-01-15T10:00:00Z), relative ('1h ago', '30m ago', 'yesterday'), or epoch ms",
            "required": true
        },
        {
            "name": "end_time",
            "type": "string",
            "description": "End of time range. Same formats as start_time. Defaults to 'now' if not specified.",
            "required": false
        },
        {
            "name": "filter_pattern",
            "type": "string",
            "description": "CloudWatch filter pattern (e.g., 'ERROR', '\"Exception\"', '{ $.level = \"error\" }')",
            "required": false
        },
        {
            "name": "log_stream_prefix",
            "type": "string",
            "description": "Filter to specific log stream prefix",
            "required": false
        },
        {
            "name": "limit",
            "type": "integer",
            "description": "Maximum number of log events to return (default: 100, max: 1000)",
            "required": false
        }
    ]
}

# Tool: search_logs
{
    "name": "search_logs",
    "description": "Search across multiple log groups for a pattern. Use for cross-service investigation.",
    "parameters": [
        {
            "name": "log_group_prefixes",
            "type": "array",
            "description": "List of log group prefixes to search (e.g., ['/aws/lambda/', '/ecs/'])",
            "required": true
        },
        {
            "name": "search_pattern",
            "type": "string",
            "description": "Pattern to search for across log groups",
            "required": true
        },
        {
            "name": "start_time",
            "type": "string",
            "description": "Start of time range",
            "required": true
        },
        {
            "name": "end_time",
            "type": "string",
            "description": "End of time range (defaults to now)",
            "required": false
        }
    ]
}

# Tool: get_log_statistics
{
    "name": "get_log_statistics",
    "description": "Get statistical summary of logs (error counts, patterns, frequencies). Use for high-level analysis before diving into details.",
    "parameters": [
        {
            "name": "log_group",
            "type": "string",
            "description": "The CloudWatch log group name",
            "required": true
        },
        {
            "name": "start_time",
            "type": "string",
            "description": "Start of time range",
            "required": true
        },
        {
            "name": "end_time",
            "type": "string",
            "description": "End of time range",
            "required": false
        },
        {
            "name": "group_by",
            "type": "string",
            "description": "Field to group by: 'level', 'hour', 'stream', 'minute'",
            "required": false
        }
    ]
}
```

#### 6.2.2 Analysis Tools

```python
# Tool: analyze_error_pattern
{
    "name": "analyze_error_pattern",
    "description": "Analyze error patterns in previously fetched logs. Call this after fetch_logs to get detailed pattern analysis.",
    "parameters": [
        {
            "name": "context_id",
            "type": "string",
            "description": "Reference to previously fetched log data in this session",
            "required": true
        }
    ]
}

# Tool: correlate_events
{
    "name": "correlate_events",
    "description": "Correlate events across multiple log fetches by timestamp. Use after fetching logs from multiple sources.",
    "parameters": [
        {
            "name": "context_ids",
            "type": "array",
            "description": "List of context IDs from previous fetch_logs calls",
            "required": true
        },
        {
            "name": "time_window_seconds",
            "type": "integer",
            "description": "Time window for correlation (default: 60 seconds)",
            "required": false
        }
    ]
}
```

### 6.3 Tool Registry Pattern

```python
# core/tools/registry.py

from typing import Type
from .base import BaseTool

class ToolRegistry:
    """Registry for managing available tools."""
    
    _tools: dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> Type[BaseTool]:
        """Decorator to register a tool."""
        instance = tool_class()
        cls._tools[instance.definition.name] = instance
        return tool_class
    
    @classmethod
    def get_tool(cls, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def get_all_definitions(cls) -> list[dict]:
        """Get all tool definitions for LLM."""
        return [tool.definition.model_dump() for tool in cls._tools.values()]
    
    @classmethod
    async def execute(cls, name: str, **kwargs) -> dict:
        """Execute a tool by name."""
        tool = cls.get_tool(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return await tool.execute(**kwargs)
```

### 6.4 LLM Response Handling

```python
# core/orchestrator.py

class LLMOrchestrator:
    """Coordinates LLM interactions with tool execution."""
    
    MAX_TOOL_ITERATIONS = 10  # Prevent infinite loops
    
    async def process_message(
        self, 
        user_message: str,
        conversation_history: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Process a user message, handling tool calls."""
        
        messages = conversation_history + [
            {"role": "user", "content": user_message}
        ]
        
        iteration = 0
        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1
            
            # Get LLM response (streaming)
            response = await self.llm_provider.chat(
                messages=messages,
                tools=ToolRegistry.get_all_definitions(),
                stream=True
            )
            
            # Check for tool calls
            if response.tool_calls:
                # Execute tools
                tool_results = await self._execute_tool_calls(response.tool_calls)
                
                # Add assistant message and tool results to conversation
                messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
                messages.extend(tool_results)
                
                # Continue loop - LLM will process tool results
                continue
            
            # No tool calls - stream final response
            async for chunk in response.stream():
                yield chunk
            
            break
```

### 6.5 System Prompt Design

```python
SYSTEM_PROMPT = """You are an expert observability assistant helping DevOps engineers and SREs analyze logs and troubleshoot issues.

## Your Capabilities
You have access to tools to fetch and analyze logs from AWS CloudWatch. Use these tools to help users:
- Find and analyze log entries
- Identify error patterns and root causes
- Correlate events across services
- Provide actionable insights

## Guidelines

### Tool Usage
1. Always start by understanding what log groups are available if the user doesn't specify
2. Use appropriate time ranges - start narrow and expand if needed
3. Use filter patterns to reduce data volume when searching for specific issues
4. Fetch logs before attempting analysis

### Response Style
1. Be concise but thorough
2. Highlight important findings (errors, patterns, anomalies)
3. Provide actionable recommendations when possible
4. Use code blocks for log excerpts
5. Summarize large result sets

### Error Handling
1. If a log group doesn't exist, suggest alternatives
2. If no logs found, suggest adjusting time range or filters
3. Explain any limitations clearly

## Context
Current time: {current_time}
User's timezone: {user_timezone}
Available log groups will be discovered via tools.
"""
```

---

## 7. Caching Strategy

### 7.1 Overview

**MVP Approach:** SQLite-only for simplicity

> **Note:** The original hybrid approach (SQLite + file-based) is deferred to post-MVP. SQLite is sufficient for MVP log volumes.

**Rationale:**
- Log data is immutable (append-only nature of time series)
- SQLite provides ACID guarantees and is simple to deploy
- Single-file database simplifies backup and cleanup
- Can store log payloads as JSON blobs for MVP

### 7.2 Cache Architecture

```
~/.logai/cache/
├── cache.db                 # SQLite database (metadata + log payloads)
└── cache.lock               # Lock file for concurrent access
```

### 7.3 SQLite Schema

```sql
-- Query cache metadata
CREATE TABLE cache_entries (
    id TEXT PRIMARY KEY,           -- SHA256 hash of normalized query
    query_type TEXT NOT NULL,      -- 'fetch_logs', 'list_log_groups', etc.
    log_group TEXT,                -- Log group name (if applicable)
    start_time INTEGER NOT NULL,   -- Epoch milliseconds
    end_time INTEGER NOT NULL,     -- Epoch milliseconds
    filter_pattern TEXT,           -- CloudWatch filter pattern
    payload TEXT NOT NULL,         -- JSON blob of log data (MVP: inline storage)
    payload_size INTEGER,          -- Uncompressed size in bytes
    log_count INTEGER,             -- Number of log events
    created_at INTEGER NOT NULL,   -- When cached
    expires_at INTEGER NOT NULL,   -- TTL expiration
    last_accessed INTEGER NOT NULL,-- For LRU eviction
    hit_count INTEGER DEFAULT 0    -- Usage tracking
);

-- Indexes for efficient lookup
CREATE INDEX idx_log_group_time ON cache_entries(log_group, start_time, end_time);
CREATE INDEX idx_expires_at ON cache_entries(expires_at);
CREATE INDEX idx_last_accessed ON cache_entries(last_accessed);

-- Cache statistics
CREATE TABLE cache_stats (
    stat_key TEXT PRIMARY KEY,
    stat_value INTEGER
);
```

### 7.4 Cache Key Generation

```python
def generate_cache_key(
    query_type: str,
    log_group: str | None,
    start_time: int,
    end_time: int,
    filter_pattern: str | None = None,
    **kwargs
) -> str:
    """Generate deterministic cache key."""
    
    # Normalize time to minute boundaries for better hit rate
    # (logs don't change that fast)
    start_normalized = (start_time // 60000) * 60000
    end_normalized = (end_time // 60000) * 60000
    
    key_parts = {
        "type": query_type,
        "log_group": log_group,
        "start": start_normalized,
        "end": end_normalized,
        "filter": filter_pattern,
        **{k: v for k, v in sorted(kwargs.items())}
    }
    
    key_string = json.dumps(key_parts, sort_keys=True)
    return hashlib.sha256(key_string.encode()).hexdigest()
```

### 7.5 TTL Policies

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Log events (historical) | 24 hours | Immutable data, aggressive caching |
| Log events (< 5 min old) | 1 minute | May still be ingesting |
| Log group list | 15 minutes | Rarely changes |
| Statistics/aggregations | 5 minutes | May want fresher data |

```python
def calculate_ttl(query_type: str, end_time: int) -> int:
    """Calculate TTL based on query type and recency."""
    
    now = int(time.time() * 1000)
    age_minutes = (now - end_time) / 60000
    
    if query_type == "list_log_groups":
        return 15 * 60  # 15 minutes
    
    if query_type in ("fetch_logs", "search_logs"):
        if age_minutes < 5:
            return 60  # 1 minute for very recent data
        else:
            return 24 * 60 * 60  # 24 hours for historical
    
    if query_type == "get_log_statistics":
        return 5 * 60  # 5 minutes
    
    return 60 * 60  # 1 hour default
```

### 7.6 Size Management

**Configuration:**
```python
CACHE_MAX_SIZE_MB = 500          # Maximum cache size
CACHE_MAX_ENTRIES = 10000        # Maximum number of entries
CACHE_EVICTION_BATCH = 100       # Entries to evict at once
CACHE_CLEANUP_INTERVAL = 300     # Seconds between cleanup runs
```

**Eviction Strategy:** LRU (Least Recently Used) with size awareness

```python
async def evict_if_needed(self):
    """Evict entries if cache exceeds limits."""
    
    current_size = await self.get_cache_size()
    entry_count = await self.get_entry_count()
    
    if current_size <= CACHE_MAX_SIZE_MB * 1024 * 1024 and entry_count <= CACHE_MAX_ENTRIES:
        return
    
    # Delete expired entries first
    await self.delete_expired()
    
    # If still over limit, evict by LRU
    while await self.get_cache_size() > CACHE_MAX_SIZE_MB * 1024 * 1024 * 0.9:  # Target 90%
        entries = await self.get_lru_entries(CACHE_EVICTION_BATCH)
        await self.delete_entries(entries)
```

### 7.7 Cache Invalidation

**Manual Invalidation:**
- User command: `/cache clear` - Clear all cache
- User command: `/cache clear <log-group>` - Clear specific log group
- User command: `/cache status` - Show cache statistics

**Automatic Invalidation:**
- TTL expiration (checked on access and periodic cleanup)
- Size-based eviction

**No Real-Time Invalidation:** Given that log data is immutable, we don't need CloudWatch notifications or polling for changes.

---

## 8. AWS CloudWatch Integration

### 8.1 Authentication

**Primary Method:** boto3 credential chain

```python
# providers/datasources/cloudwatch.py

import boto3
from botocore.config import Config

class CloudWatchSource:
    """AWS CloudWatch data source implementation."""
    
    def __init__(self, settings: CloudWatchSettings):
        self.config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'  # Adaptive retry with backoff
            },
            connect_timeout=5,
            read_timeout=30
        )
        
        # boto3 will use standard credential chain:
        # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. Shared credential file (~/.aws/credentials)
        # 3. AWS config file (~/.aws/config)
        # 4. IAM role (if running on EC2/ECS/Lambda)
        self.client = boto3.client(
            'logs',
            region_name=settings.aws_region,
            config=self.config
        )
```

**Environment Variables:**
```bash
# AWS Credentials (standard boto3 variables)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# OR use a profile
AWS_PROFILE=my-profile
```

### 8.2 CloudWatch APIs Used

| Operation | AWS API | Notes |
|-----------|---------|-------|
| List log groups | `describe_log_groups` | Paginated, 50 per page |
| List log streams | `describe_log_streams` | Paginated, 50 per page |
| Fetch logs | `filter_log_events` | Paginated, 10,000 events max per call |
| Search logs | `filter_log_events` | With filter pattern |
| Insights query | `start_query` + `get_query_results` | For complex aggregations (future) |

### 8.3 Implementation Details

```python
# providers/datasources/cloudwatch.py

from typing import AsyncGenerator
import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

class CloudWatchSource(BaseDataSource):
    """CloudWatch Logs data source."""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def list_log_groups(
        self,
        prefix: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        """List available log groups."""
        
        paginator = self.client.get_paginator('describe_log_groups')
        params = {}
        if prefix:
            params['logGroupNamePrefix'] = prefix
        
        log_groups = []
        async for page in paginator.paginate(**params):
            for lg in page['logGroups']:
                log_groups.append({
                    'name': lg['logGroupName'],
                    'created': lg.get('creationTime'),
                    'stored_bytes': lg.get('storedBytes', 0),
                    'retention_days': lg.get('retentionInDays')
                })
                if len(log_groups) >= limit:
                    return log_groups
        
        return log_groups
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_logs(
        self,
        log_group: str,
        start_time: int,
        end_time: int,
        filter_pattern: str | None = None,
        log_stream_prefix: str | None = None,
        limit: int = 1000
    ) -> list[dict]:
        """Fetch log events from CloudWatch."""
        
        params = {
            'logGroupName': log_group,
            'startTime': start_time,
            'endTime': end_time,
            'limit': min(limit, 10000),  # API max
        }
        
        if filter_pattern:
            params['filterPattern'] = filter_pattern
        if log_stream_prefix:
            params['logStreamNamePrefix'] = log_stream_prefix
        
        events = []
        paginator = self.client.get_paginator('filter_log_events')
        
        try:
            for page in paginator.paginate(**params):
                for event in page['events']:
                    events.append({
                        'timestamp': event['timestamp'],
                        'message': event['message'],
                        'log_stream': event['logStreamName'],
                        'event_id': event['eventId']
                    })
                    if len(events) >= limit:
                        return events
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                raise LogGroupNotFoundError(f"Log group not found: {log_group}")
            elif error_code == 'ThrottlingException':
                raise RateLimitError("CloudWatch rate limit exceeded")
            raise
        
        return events
```

### 8.4 Rate Limiting

AWS CloudWatch has quota limits:
- `filter_log_events`: 15 transactions per second per account per region
- `describe_log_groups`: 5 transactions per second

**Handling Strategy:**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class RateLimitError(Exception):
    pass

# Retry decorator for rate limit handling
rate_limit_retry = retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=1, max=30)
)
```

### 8.5 Error Handling

| Error Type | Handling | User Message |
|------------|----------|--------------|
| `ResourceNotFoundException` | Return empty, suggest alternatives | "Log group '/aws/x' not found. Did you mean '/aws/y'?" |
| `InvalidParameterException` | Validate inputs, retry with fixes | "Invalid filter pattern. Please use CloudWatch syntax." |
| `ThrottlingException` | Exponential backoff retry | "Rate limited. Retrying..." |
| `AccessDeniedException` | Surface to user | "Access denied. Check AWS permissions." |
| Network timeout | Retry with backoff | "Connection timeout. Retrying..." |

---

## 9. PII Sanitization Layer

> **IMPORTANT:** This feature is enabled by default. Log data sent to LLM providers will be sanitized to remove PII and sensitive information.

### 9.1 Overview

The PII Sanitization Layer is a configurable component that redacts sensitive information from log data before sending it to external LLM providers. This protects against accidental exposure of:

- Personal Identifiable Information (PII)
- API keys and secrets
- Internal IP addresses and hostnames
- Email addresses and phone numbers
- Credit card numbers and financial data

### 9.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LLM Orchestrator                            │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐   │
│  │ Tool Result  │───▶│   Sanitizer      │───▶│  LLM Provider   │   │
│  │ (Raw Logs)   │    │   (if enabled)   │    │  (Anthropic)    │   │
│  └──────────────┘    └──────────────────┘    └─────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│                      ┌──────────────────┐                          │
│                      │ Redaction Report │                          │
│                      │ (for debugging)  │                          │
│                      └──────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.3 Default Patterns (Enabled by Default)

The following patterns are redacted by default:

| Pattern Type | Regex Pattern | Replacement | Example |
|--------------|---------------|-------------|---------|
| **Email** | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | `[EMAIL_REDACTED]` | `user@example.com` → `[EMAIL_REDACTED]` |
| **IPv4 Address** | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | `[IP_REDACTED]` | `192.168.1.100` → `[IP_REDACTED]` |
| **IPv6 Address** | `([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}` | `[IP_REDACTED]` | Full IPv6 → `[IP_REDACTED]` |
| **Credit Card** | `\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b` | `[CC_REDACTED]` | `4111-1111-1111-1111` → `[CC_REDACTED]` |
| **SSN** | `\b\d{3}-\d{2}-\d{4}\b` | `[SSN_REDACTED]` | `123-45-6789` → `[SSN_REDACTED]` |
| **Phone (US)** | `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` | `[PHONE_REDACTED]` | `555-123-4567` → `[PHONE_REDACTED]` |
| **AWS Access Key** | `AKIA[0-9A-Z]{16}` | `[AWS_KEY_REDACTED]` | `AKIAIOSFODNN7EXAMPLE` → `[AWS_KEY_REDACTED]` |
| **AWS Secret Key** | `(?i)aws.{0,20}secret.{0,20}['"][0-9a-zA-Z/+=]{40}['"]` | `[AWS_SECRET_REDACTED]` | Matches secret key patterns |
| **Generic API Key** | `(?i)(api[_-]?key\|apikey\|api[_-]?secret)['":\s]*['"]?[a-zA-Z0-9_-]{20,}['"]?` | `[API_KEY_REDACTED]` | `api_key: "sk-abc123..."` → `[API_KEY_REDACTED]` |
| **Bearer Token** | `(?i)bearer\s+[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+` | `[TOKEN_REDACTED]` | JWT tokens |
| **Private Key** | `-----BEGIN\s+(RSA\|DSA\|EC\|OPENSSH)?\s*PRIVATE KEY-----` | `[PRIVATE_KEY_REDACTED]` | PEM private keys |
| **Password in URL** | `://[^:]+:([^@]+)@` | `://[user]:[PASSWORD_REDACTED]@` | `mysql://user:pass@host` |

### 9.4 Implementation

```python
# core/sanitizer.py

import re
from dataclasses import dataclass
from typing import Callable

@dataclass
class SanitizationPattern:
    """Defines a pattern to detect and redact."""
    name: str
    pattern: re.Pattern
    replacement: str
    enabled: bool = True

@dataclass
class SanitizationResult:
    """Result of sanitization with statistics."""
    sanitized_text: str
    redaction_count: int
    redactions: dict[str, int]  # Pattern name -> count

class LogSanitizer:
    """Sanitizes log data before sending to LLM."""
    
    DEFAULT_PATTERNS: list[SanitizationPattern] = [
        SanitizationPattern(
            name="email",
            pattern=re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            replacement="[EMAIL_REDACTED]"
        ),
        SanitizationPattern(
            name="ipv4",
            pattern=re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            replacement="[IP_REDACTED]"
        ),
        SanitizationPattern(
            name="credit_card",
            pattern=re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
            replacement="[CC_REDACTED]"
        ),
        SanitizationPattern(
            name="ssn",
            pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            replacement="[SSN_REDACTED]"
        ),
        SanitizationPattern(
            name="phone_us",
            pattern=re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            replacement="[PHONE_REDACTED]"
        ),
        SanitizationPattern(
            name="aws_access_key",
            pattern=re.compile(r'AKIA[0-9A-Z]{16}'),
            replacement="[AWS_KEY_REDACTED]"
        ),
        SanitizationPattern(
            name="aws_secret_key",
            pattern=re.compile(r'(?i)aws.{0,20}secret.{0,20}[\'"][0-9a-zA-Z/+=]{40}[\'"]'),
            replacement="[AWS_SECRET_REDACTED]"
        ),
        SanitizationPattern(
            name="generic_api_key",
            pattern=re.compile(r'(?i)(api[_-]?key|apikey|api[_-]?secret)[\'\":\s]*[\'"]?[a-zA-Z0-9_-]{20,}[\'"]?'),
            replacement="[API_KEY_REDACTED]"
        ),
        SanitizationPattern(
            name="bearer_token",
            pattern=re.compile(r'(?i)bearer\s+[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'),
            replacement="[TOKEN_REDACTED]"
        ),
        SanitizationPattern(
            name="private_key",
            pattern=re.compile(r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)?\s*PRIVATE KEY-----'),
            replacement="[PRIVATE_KEY_REDACTED]"
        ),
    ]
    
    def __init__(self, settings: SanitizationSettings):
        self.enabled = settings.enabled
        self.patterns = self._build_patterns(settings)
        self.log_redactions = settings.log_redactions
    
    def _build_patterns(self, settings: SanitizationSettings) -> list[SanitizationPattern]:
        """Build pattern list based on settings."""
        patterns = []
        
        for pattern in self.DEFAULT_PATTERNS:
            # Check if pattern is disabled in settings
            if pattern.name in settings.disabled_patterns:
                continue
            patterns.append(pattern)
        
        # Add custom patterns from settings
        for custom in settings.custom_patterns:
            patterns.append(SanitizationPattern(
                name=custom.name,
                pattern=re.compile(custom.pattern),
                replacement=custom.replacement
            ))
        
        return patterns
    
    def sanitize(self, text: str) -> SanitizationResult:
        """Sanitize text, removing PII and sensitive data."""
        if not self.enabled:
            return SanitizationResult(
                sanitized_text=text,
                redaction_count=0,
                redactions={}
            )
        
        redactions: dict[str, int] = {}
        result = text
        
        for pattern in self.patterns:
            matches = pattern.pattern.findall(result)
            if matches:
                redactions[pattern.name] = len(matches)
                result = pattern.pattern.sub(pattern.replacement, result)
        
        total_redactions = sum(redactions.values())
        
        if self.log_redactions and total_redactions > 0:
            logger.info(
                "Sanitization complete",
                total_redactions=total_redactions,
                by_type=redactions
            )
        
        return SanitizationResult(
            sanitized_text=result,
            redaction_count=total_redactions,
            redactions=redactions
        )
    
    def sanitize_log_events(self, events: list[dict]) -> list[dict]:
        """Sanitize a list of log events."""
        sanitized = []
        for event in events:
            sanitized_event = event.copy()
            if 'message' in sanitized_event:
                result = self.sanitize(sanitized_event['message'])
                sanitized_event['message'] = result.sanitized_text
            sanitized.append(sanitized_event)
        return sanitized
```

### 9.5 Configuration

```python
# config/settings.py

class CustomPattern(BaseModel):
    """User-defined sanitization pattern."""
    name: str
    pattern: str  # Regex pattern string
    replacement: str

class SanitizationSettings(BaseSettings):
    """PII Sanitization configuration."""
    model_config = SettingsConfigDict(env_prefix='LOGAI_SANITIZATION_')
    
    # Master toggle - DEFAULT IS ENABLED
    enabled: bool = True
    
    # Patterns to disable (by name)
    disabled_patterns: list[str] = []
    
    # Custom patterns to add
    custom_patterns: list[CustomPattern] = []
    
    # Log redaction statistics
    log_redactions: bool = True
    
    # Show redaction summary to user
    show_summary: bool = True
```

### 9.6 Environment Variables

```bash
# .env.example - Sanitization Settings

# ============================================
# PII Sanitization (DEFAULT: ENABLED)
# ============================================

# Master toggle (default: true)
LOGAI_SANITIZATION_ENABLED=true

# Disable specific patterns (comma-separated)
# Options: email, ipv4, credit_card, ssn, phone_us, aws_access_key, 
#          aws_secret_key, generic_api_key, bearer_token, private_key
LOGAI_SANITIZATION_DISABLED_PATTERNS=

# Log redaction statistics (default: true)
LOGAI_SANITIZATION_LOG_REDACTIONS=true

# Show summary to user after sanitization (default: true)
LOGAI_SANITIZATION_SHOW_SUMMARY=true
```

### 9.7 Integration with LLM Orchestrator

```python
# core/orchestrator.py

class LLMOrchestrator:
    """Coordinates LLM interactions with tool execution."""
    
    def __init__(self, settings: Settings):
        self.sanitizer = LogSanitizer(settings.sanitization)
        # ...
    
    async def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Execute tools and sanitize results before returning to LLM."""
        results = []
        
        for call in tool_calls:
            # Execute the tool
            raw_result = await ToolRegistry.execute(call['name'], **call['arguments'])
            
            # Sanitize log data in results
            if 'events' in raw_result:
                raw_result['events'] = self.sanitizer.sanitize_log_events(
                    raw_result['events']
                )
            elif 'logs' in raw_result:
                raw_result['logs'] = self.sanitizer.sanitize_log_events(
                    raw_result['logs']
                )
            
            results.append({
                "role": "tool",
                "tool_call_id": call['id'],
                "content": json.dumps(raw_result)
            })
        
        return results
```

### 9.8 User Feedback

When sanitization is enabled and redactions occur, the TUI shows a brief summary:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 🔒 PII Sanitization: 12 items redacted (3 emails, 5 IPs, 4 tokens) │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.9 Testing Sanitization

```python
# tests/unit/test_sanitizer.py

class TestLogSanitizer:
    
    def test_sanitizes_email(self):
        sanitizer = LogSanitizer(SanitizationSettings())
        result = sanitizer.sanitize("Contact user@example.com for help")
        assert result.sanitized_text == "Contact [EMAIL_REDACTED] for help"
        assert result.redactions == {"email": 1}
    
    def test_sanitizes_multiple_patterns(self):
        sanitizer = LogSanitizer(SanitizationSettings())
        text = "User user@test.com from 192.168.1.1 with key AKIAIOSFODNN7EXAMPLE"
        result = sanitizer.sanitize(text)
        assert "[EMAIL_REDACTED]" in result.sanitized_text
        assert "[IP_REDACTED]" in result.sanitized_text
        assert "[AWS_KEY_REDACTED]" in result.sanitized_text
        assert result.redaction_count == 3
    
    def test_disabled_sanitization(self):
        settings = SanitizationSettings(enabled=False)
        sanitizer = LogSanitizer(settings)
        text = "user@example.com"
        result = sanitizer.sanitize(text)
        assert result.sanitized_text == text
        assert result.redaction_count == 0
    
    def test_disabled_pattern(self):
        settings = SanitizationSettings(disabled_patterns=["email"])
        sanitizer = LogSanitizer(settings)
        result = sanitizer.sanitize("user@example.com from 192.168.1.1")
        assert "user@example.com" in result.sanitized_text  # Not redacted
        assert "[IP_REDACTED]" in result.sanitized_text      # Still redacted
    
    def test_custom_pattern(self):
        settings = SanitizationSettings(
            custom_patterns=[
                CustomPattern(
                    name="internal_id",
                    pattern=r"INTERNAL-\d{8}",
                    replacement="[INTERNAL_ID_REDACTED]"
                )
            ]
        )
        sanitizer = LogSanitizer(settings)
        result = sanitizer.sanitize("Processing INTERNAL-12345678")
        assert result.sanitized_text == "Processing [INTERNAL_ID_REDACTED]"
```

---

## 10. Extensibility Design

### 10.1 Data Source Plugin Architecture

**Interface-Based Design:** All data sources implement a common interface.

```python
# providers/datasources/base.py

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class LogEvent(BaseModel):
    """Standardized log event across all sources."""
    timestamp: int          # Epoch milliseconds
    message: str            # Log message content
    source: str             # Source identifier (log stream, host, etc.)
    metadata: dict[str, Any] = {}  # Source-specific metadata

class DataSourceCapabilities(BaseModel):
    """Declares what a data source can do."""
    supports_filter_patterns: bool = False
    supports_log_streams: bool = False
    supports_insights_queries: bool = False
    supports_metrics: bool = False
    max_time_range_hours: int = 24 * 7  # Max queryable range

class BaseDataSource(ABC):
    """Abstract base class for all data sources."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this source."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> DataSourceCapabilities:
        """Declare source capabilities."""
        pass
    
    @abstractmethod
    async def list_log_groups(
        self,
        prefix: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        """List available log groups/sources."""
        pass
    
    @abstractmethod
    async def fetch_logs(
        self,
        log_group: str,
        start_time: int,
        end_time: int,
        filter_pattern: str | None = None,
        limit: int = 1000
    ) -> list[LogEvent]:
        """Fetch log events."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if source is accessible."""
        pass
```

### 10.2 Data Source Registry

```python
# providers/datasources/registry.py

class DataSourceRegistry:
    """Registry for managing data sources."""
    
    _sources: dict[str, type[BaseDataSource]] = {}
    _instances: dict[str, BaseDataSource] = {}
    
    @classmethod
    def register(cls, name: str):
        """Decorator to register a data source class."""
        def decorator(source_class: type[BaseDataSource]):
            cls._sources[name] = source_class
            return source_class
        return decorator
    
    @classmethod
    def get(cls, name: str, settings: Any) -> BaseDataSource:
        """Get or create a data source instance."""
        if name not in cls._instances:
            if name not in cls._sources:
                raise ValueError(f"Unknown data source: {name}")
            cls._instances[name] = cls._sources[name](settings)
        return cls._instances[name]
    
    @classmethod
    def available_sources(cls) -> list[str]:
        """List registered data source names."""
        return list(cls._sources.keys())


# Usage in cloudwatch.py
@DataSourceRegistry.register("cloudwatch")
class CloudWatchSource(BaseDataSource):
    ...
```

### 10.3 Adding New Data Sources (Future)

To add Splunk support:

```python
# providers/datasources/splunk.py

@DataSourceRegistry.register("splunk")
class SplunkSource(BaseDataSource):
    
    @property
    def name(self) -> str:
        return "splunk"
    
    @property
    def capabilities(self) -> DataSourceCapabilities:
        return DataSourceCapabilities(
            supports_filter_patterns=True,
            supports_insights_queries=True,
            max_time_range_hours=24 * 30  # 30 days
        )
    
    async def fetch_logs(self, ...) -> list[LogEvent]:
        # Splunk-specific implementation
        # Translate filter_pattern to Splunk SPL
        # Call Splunk REST API
        # Convert to LogEvent format
        pass
```

### 10.4 LLM Provider Extensibility

```python
# providers/llm/base.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMResponse(BaseModel):
    content: str
    tool_calls: list[dict] | None = None
    usage: dict | None = None

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def supports_function_calling(self) -> bool:
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False
    ) -> LLMResponse | AsyncGenerator[str, None]:
        pass


# providers/llm/registry.py
class LLMProviderRegistry:
    """Registry for LLM providers."""
    _providers: dict[str, type[BaseLLMProvider]] = {}
    
    @classmethod
    def register(cls, name: str):
        def decorator(provider_class: type[BaseLLMProvider]):
            cls._providers[name] = provider_class
            return provider_class
        return decorator
```

### 10.5 Configuration for Multiple Sources

```python
# config/settings.py

class DataSourceSettings(BaseModel):
    """Settings for a single data source."""
    enabled: bool = True
    type: str  # "cloudwatch", "splunk", etc.
    config: dict[str, Any] = {}

class Settings(BaseSettings):
    # Multiple data sources
    data_sources: dict[str, DataSourceSettings] = {
        "cloudwatch": DataSourceSettings(type="cloudwatch")
    }
    
    # Active sources for queries
    active_sources: list[str] = ["cloudwatch"]
```

---

## 11. Configuration Management

### 11.1 Environment Variable Schema

```bash
# .env.example

# ============================================
# LLM Configuration
# ============================================

# LLM Provider: "anthropic" for MVP (OpenAI post-MVP)
LOGAI_LLM_PROVIDER=anthropic

# Anthropic Configuration (MVP)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# OpenAI Configuration (Post-MVP)
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4-turbo

# LLM Settings
LOGAI_LLM_MAX_TOKENS=4096
LOGAI_LLM_TEMPERATURE=0.1

# ============================================
# AWS Configuration
# ============================================

# AWS Credentials (or use AWS_PROFILE)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Alternative: Use AWS profile
# AWS_PROFILE=my-profile

# CloudWatch Settings
LOGAI_CLOUDWATCH_DEFAULT_LIMIT=100
LOGAI_CLOUDWATCH_MAX_RESULTS=10000

# ============================================
# Cache Configuration
# ============================================

LOGAI_CACHE_DIR=~/.logai/cache
LOGAI_CACHE_MAX_SIZE_MB=500
LOGAI_CACHE_TTL_HOURS=24
LOGAI_CACHE_ENABLED=true

# ============================================
# PII Sanitization (DEFAULT: ENABLED)
# ============================================

LOGAI_SANITIZATION_ENABLED=true
LOGAI_SANITIZATION_DISABLED_PATTERNS=
LOGAI_SANITIZATION_LOG_REDACTIONS=true

# ============================================
# Application Settings
# ============================================

# Logging
LOGAI_LOG_LEVEL=INFO
LOGAI_LOG_FILE=~/.logai/logs/app.log

# UI Settings
LOGAI_THEME=dark
LOGAI_TIMEZONE=UTC

# Debug Mode
LOGAI_DEBUG=false
```

### 11.2 Pydantic Settings Model

```python
# config/settings.py

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    model_config = SettingsConfigDict(env_prefix='LOGAI_LLM_')
    
    provider: str = "anthropic"  # MVP: Anthropic only
    max_tokens: int = 4096
    temperature: float = 0.1
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {'anthropic'}  # MVP: Anthropic only
        if v.lower() not in allowed:
            raise ValueError(f"Provider must be one of: {allowed}")
        return v.lower()

class AnthropicSettings(BaseSettings):
    """Anthropic-specific settings."""
    model_config = SettingsConfigDict(env_prefix='ANTHROPIC_')
    
    api_key: str = Field(..., description="Anthropic API key")
    model: str = "claude-sonnet-4-20250514"

class CloudWatchSettings(BaseSettings):
    """CloudWatch configuration."""
    model_config = SettingsConfigDict(env_prefix='LOGAI_CLOUDWATCH_')
    
    default_limit: int = 100
    max_results: int = 10000

class CacheSettings(BaseSettings):
    """Cache configuration."""
    model_config = SettingsConfigDict(env_prefix='LOGAI_CACHE_')
    
    dir: str = "~/.logai/cache"
    max_size_mb: int = 500
    ttl_hours: int = 24
    enabled: bool = True
    
    @field_validator('dir')
    @classmethod
    def expand_path(cls, v: str) -> str:
        return os.path.expanduser(v)

class AppSettings(BaseSettings):
    """Application-wide settings."""
    model_config = SettingsConfigDict(env_prefix='LOGAI_')
    
    log_level: str = "INFO"
    log_file: str = "~/.logai/logs/app.log"
    theme: str = "dark"
    timezone: str = "UTC"
    debug: bool = False

class Settings(BaseSettings):
    """Root settings aggregating all configuration."""
    
    llm: LLMSettings = Field(default_factory=LLMSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    cloudwatch: CloudWatchSettings = Field(default_factory=CloudWatchSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    sanitization: SanitizationSettings = Field(default_factory=SanitizationSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    
    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment and .env file."""
        from dotenv import load_dotenv
        load_dotenv()  # Load .env file
        return cls()
```

### 11.3 Configuration Validation

```python
# config/validation.py

class ConfigValidator:
    """Validates configuration at startup."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.errors: list[str] = []
        self.warnings: list[str] = []
    
    def validate(self) -> bool:
        """Run all validations. Returns True if valid."""
        self._validate_llm()
        self._validate_aws()
        self._validate_cache()
        self._validate_sanitization()
        return len(self.errors) == 0
    
    def _validate_llm(self):
        """Validate LLM configuration."""
        if not self.settings.anthropic.api_key:
            self.errors.append("ANTHROPIC_API_KEY is required")
    
    def _validate_aws(self):
        """Validate AWS configuration."""
        # boto3 handles credential chain, just warn if none found
        import boto3
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            self.errors.append(
                "No AWS credentials found. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
                "or AWS_PROFILE, or configure ~/.aws/credentials"
            )
    
    def _validate_cache(self):
        """Validate cache directory."""
        cache_dir = Path(self.settings.cache.dir)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.errors.append(f"Cannot create cache directory: {cache_dir}")
    
    def _validate_sanitization(self):
        """Validate sanitization settings."""
        if not self.settings.sanitization.enabled:
            self.warnings.append(
                "PII sanitization is DISABLED. Log data will be sent to LLM unsanitized."
            )
```

### 11.4 Configuration File Support (Optional - Post-MVP)

For power users, support an optional YAML/TOML config file:

```yaml
# ~/.logai/config.yaml

llm:
  provider: anthropic
  temperature: 0.1

cloudwatch:
  default_limit: 200
  
cache:
  max_size_mb: 1000

sanitization:
  enabled: true
  disabled_patterns:
    - phone_us  # Don't redact phone numbers
  
# Custom log group aliases for convenience
aliases:
  auth: /aws/lambda/auth-service-prod
  api: /aws/ecs/api-gateway-prod
```

---

## 12. Error Handling & Logging

### 12.1 Error Hierarchy

```python
# utils/exceptions.py

class LogAIError(Exception):
    """Base exception for all LogAI errors."""
    
    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message

# Configuration errors
class ConfigurationError(LogAIError):
    """Configuration is invalid or missing."""
    pass

# LLM errors
class LLMError(LogAIError):
    """Base class for LLM-related errors."""
    pass

class LLMAuthenticationError(LLMError):
    """API key invalid or expired."""
    pass

class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""
    pass

class LLMContextLengthError(LLMError):
    """Context window exceeded."""
    pass

# Data source errors
class DataSourceError(LogAIError):
    """Base class for data source errors."""
    pass

class LogGroupNotFoundError(DataSourceError):
    """Log group doesn't exist."""
    pass

class AccessDeniedError(DataSourceError):
    """Insufficient permissions."""
    pass

class RateLimitError(DataSourceError):
    """Data source rate limit exceeded."""
    pass

# Cache errors
class CacheError(LogAIError):
    """Cache operation failed."""
    pass
```

### 12.2 Error Handling Strategy

```python
# core/error_handler.py

class ErrorHandler:
    """Centralized error handling with user-friendly messages."""
    
    ERROR_MESSAGES = {
        LLMAuthenticationError: "Authentication failed. Please check your API key.",
        LLMRateLimitError: "Rate limit reached. Waiting before retry...",
        LogGroupNotFoundError: "Log group not found. Use 'list log groups' to see available options.",
        AccessDeniedError: "Access denied. Please check your AWS permissions.",
        RateLimitError: "AWS rate limit reached. Retrying with backoff...",
    }
    
    async def handle(
        self, 
        error: Exception, 
        context: dict | None = None
    ) -> str:
        """Handle error and return user-friendly message."""
        
        # Log full error for debugging
        logger.exception("Error occurred", extra={
            "error_type": type(error).__name__,
            "context": context
        })
        
        # Get user-friendly message
        for error_type, message in self.ERROR_MESSAGES.items():
            if isinstance(error, error_type):
                return message
        
        # Generic fallback
        if isinstance(error, LogAIError):
            return error.user_message
        
        return "An unexpected error occurred. Check logs for details."
```

### 12.3 Structured Logging

```python
# utils/logging.py

import structlog
from pathlib import Path

def setup_logging(settings: AppSettings) -> None:
    """Configure structured logging."""
    
    # Ensure log directory exists
    log_file = Path(settings.log_file).expanduser()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if not settings.debug else 
                structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # File handler for JSON logs
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(file_handler)


# Usage example
logger = structlog.get_logger()

async def fetch_logs(...):
    logger.info(
        "Fetching logs",
        log_group=log_group,
        start_time=start_time,
        end_time=end_time
    )
    try:
        result = await cloudwatch.fetch_logs(...)
        logger.info("Logs fetched", count=len(result))
        return result
    except Exception as e:
        logger.error("Failed to fetch logs", error=str(e))
        raise
```

### 12.4 User-Facing Error Display

```python
# In TUI application
class ChatScreen(Screen):
    
    async def handle_error(self, error: Exception):
        """Display error to user in chat."""
        message = await self.error_handler.handle(error)
        
        # Show error in chat with appropriate styling
        self.add_message(
            role="system",
            content=f"**Error:** {message}",
            style="error"  # Red/warning styling
        )
        
        # If recoverable, suggest next steps
        if isinstance(error, LogGroupNotFoundError):
            self.add_message(
                role="system",
                content="Tip: You can ask me to 'list log groups' to see what's available.",
                style="hint"
            )
```

---

## 13. Testing Strategy

### 13.1 Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E/UI    │  ← Manual + limited automation
                    │   Tests     │
                    └─────────────┘
               ┌─────────────────────────┐
               │   Integration Tests     │  ← Test real component interactions
               │   (with mocked APIs)    │
               └─────────────────────────┘
          ┌───────────────────────────────────┐
          │         Unit Tests                │  ← Most tests here
          │  (isolated, fast, comprehensive)  │
          └───────────────────────────────────┘
```

### 13.2 Unit Testing

**Framework:** pytest + pytest-asyncio

**Coverage Target:** 80%+ for core modules

```python
# tests/unit/test_cache.py

import pytest
from logai.cache.manager import CacheManager
from logai.cache.sqlite_store import SQLiteStore

@pytest.fixture
async def cache_manager(tmp_path):
    """Create a test cache manager."""
    store = SQLiteStore(tmp_path / "test.db")
    await store.initialize()
    return CacheManager(store)

class TestCacheManager:
    
    async def test_cache_miss_returns_none(self, cache_manager):
        result = await cache_manager.get("nonexistent-key")
        assert result is None
    
    async def test_cache_hit_returns_data(self, cache_manager):
        await cache_manager.set("test-key", {"data": "value"}, ttl=3600)
        result = await cache_manager.get("test-key")
        assert result == {"data": "value"}
    
    async def test_expired_entry_returns_none(self, cache_manager, freezer):
        await cache_manager.set("test-key", {"data": "value"}, ttl=60)
        freezer.tick(delta=timedelta(seconds=120))
        result = await cache_manager.get("test-key")
        assert result is None


# tests/unit/test_tools.py

class TestCloudWatchTool:
    
    async def test_fetch_logs_validates_log_group(self):
        tool = FetchLogsTool(mock_cloudwatch)
        
        with pytest.raises(ValidationError) as exc:
            await tool.execute(log_group="", start_time="1h ago")
        
        assert "log_group" in str(exc.value)
    
    async def test_fetch_logs_parses_relative_time(self):
        tool = FetchLogsTool(mock_cloudwatch)
        
        result = await tool.execute(
            log_group="/aws/test",
            start_time="1h ago"
        )
        
        # Verify correct epoch calculation
        mock_cloudwatch.fetch_logs.assert_called_once()
        call_args = mock_cloudwatch.fetch_logs.call_args
        assert call_args.kwargs['start_time'] == pytest.approx(
            int(time.time() * 1000) - 3600000,
            abs=1000
        )
```

### 13.3 Integration Testing

**Mocking Strategy:**
- `moto` for AWS services
- `respx` for HTTP APIs (LLM providers)

```python
# tests/integration/test_cloudwatch_integration.py

import pytest
from moto import mock_logs
import boto3

@pytest.fixture
def aws_credentials():
    """Mock AWS credentials."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture
@mock_logs
def cloudwatch_with_data(aws_credentials):
    """Create CloudWatch with test data."""
    client = boto3.client('logs', region_name='us-east-1')
    
    # Create test log group and stream
    client.create_log_group(logGroupName='/aws/test/myapp')
    client.create_log_stream(
        logGroupName='/aws/test/myapp',
        logStreamName='test-stream'
    )
    
    # Add test log events
    client.put_log_events(
        logGroupName='/aws/test/myapp',
        logStreamName='test-stream',
        logEvents=[
            {'timestamp': 1000, 'message': 'INFO: Test message'},
            {'timestamp': 2000, 'message': 'ERROR: Test error'},
        ]
    )
    
    return client

@mock_logs
class TestCloudWatchIntegration:
    
    async def test_fetch_logs_returns_events(self, cloudwatch_with_data):
        source = CloudWatchSource(CloudWatchSettings())
        
        events = await source.fetch_logs(
            log_group='/aws/test/myapp',
            start_time=0,
            end_time=10000
        )
        
        assert len(events) == 2
        assert events[0].message == 'INFO: Test message'
    
    async def test_filter_pattern_works(self, cloudwatch_with_data):
        source = CloudWatchSource(CloudWatchSettings())
        
        events = await source.fetch_logs(
            log_group='/aws/test/myapp',
            start_time=0,
            end_time=10000,
            filter_pattern='ERROR'
        )
        
        assert len(events) == 1
        assert 'ERROR' in events[0].message


# tests/integration/test_llm_integration.py

import respx
import httpx

@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API."""
    with respx.mock(base_url="https://api.anthropic.com") as respx_mock:
        respx_mock.post("/v1/messages").mock(
            return_value=httpx.Response(200, json={
                "content": [{"type": "text", "text": "Here's the analysis..."}],
                "model": "claude-sonnet-4-20250514",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            })
        )
        yield respx_mock

class TestLLMIntegration:
    
    async def test_chat_returns_response(self, mock_anthropic):
        provider = AnthropicProvider(AnthropicSettings(api_key="test"))
        
        response = await provider.chat(
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        assert "analysis" in response.content.lower()
```

### 13.4 Test Fixtures

```python
# tests/conftest.py

import pytest
import json
from pathlib import Path

@pytest.fixture
def fixture_dir():
    """Path to test fixtures."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_cloudwatch_response(fixture_dir):
    """Load sample CloudWatch API response."""
    with open(fixture_dir / "cloudwatch_responses" / "filter_log_events.json") as f:
        return json.load(f)

@pytest.fixture
def sample_llm_function_call(fixture_dir):
    """Load sample LLM function call response."""
    with open(fixture_dir / "llm_responses" / "function_call.json") as f:
        return json.load(f)

@pytest.fixture
async def test_settings():
    """Create test settings."""
    return Settings(
        llm=LLMSettings(provider="anthropic"),
        anthropic=AnthropicSettings(api_key="test-key"),
        cache=CacheSettings(dir="/tmp/logai-test-cache"),
        sanitization=SanitizationSettings(enabled=True),
        app=AppSettings(debug=True, log_level="DEBUG")
    )
```

### 13.5 Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/logai --cov-report=html

# Run specific test file
pytest tests/unit/test_cache.py

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_cache.py::TestCacheManager::test_cache_hit_returns_data
```

---

## 14. Packaging & Distribution

### 14.1 Package Configuration

```toml
# pyproject.toml

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "logai-cli"
version = "0.1.0"
description = "AI-powered observability assistant for DevOps and SREs"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "Your Team", email = "team@example.com"}
]
keywords = ["observability", "cloudwatch", "llm", "devops", "sre", "logs"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Monitoring",
]

dependencies = [
    # ... (as listed in section 3.5)
]

[project.scripts]
logai = "logai.cli:main"

[project.urls]
Homepage = "https://github.com/yourorg/logai"
Documentation = "https://github.com/yourorg/logai/docs"
Repository = "https://github.com/yourorg/logai"
Issues = "https://github.com/yourorg/logai/issues"

[tool.hatch.build.targets.sdist]
include = [
    "/src",
]

[tool.hatch.build.targets.wheel]
packages = ["src/logai"]
```

### 14.2 Distribution Methods

#### 14.2.1 PyPI (Primary)

```bash
# Build
python -m build

# Upload to PyPI
python -m twine upload dist/*

# User installation
pip install logai-cli
```

#### 14.2.2 Homebrew (macOS) - Post-MVP

```ruby
# Formula: logai.rb
class Logai < Formula
  desc "AI-powered observability assistant"
  homepage "https://github.com/yourorg/logai"
  url "https://github.com/yourorg/logai/archive/v0.1.0.tar.gz"
  sha256 "..."
  license "MIT"
  
  depends_on "python@3.11"
  
  def install
    virtualenv_install_with_resources
  end
  
  test do
    system "#{bin}/logai", "--version"
  end
end
```

#### 14.2.3 Standalone Binary (PyInstaller) - Post-MVP

For users who don't want to manage Python:

```bash
# Build standalone binary
pyinstaller --onefile --name logai src/logai/__main__.py

# Creates: dist/logai (macOS/Linux) or dist/logai.exe (Windows)
```

### 14.3 Release Process

```yaml
# .github/workflows/release.yml

name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install build tools
        run: pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*
```

---

## 15. Security Considerations

### 15.1 Credential Handling

1. **Never log credentials**: Ensure API keys are never written to logs
2. **Memory handling**: Use secure string handling where possible
3. **Environment isolation**: Credentials only in environment variables (MVP)

```python
# Credential masking in logs
def mask_secret(value: str) -> str:
    """Mask secrets for logging."""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]
```

### 15.2 Input Validation

1. **Sanitize log group names**: Prevent injection in CloudWatch queries
2. **Validate time ranges**: Prevent excessive resource consumption
3. **Limit result sizes**: Prevent memory exhaustion

### 15.3 Data Privacy

1. **Log data stays local**: Cached data stored only locally
2. **PII Sanitization**: Enabled by default - redacts sensitive patterns before sending to LLM (see Section 9)
3. **User control**: Sanitization can be configured or disabled if needed

### 15.4 AWS Permissions (Least Privilege)

Recommended IAM policy for the tool:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:FilterLogEvents",
                "logs:GetLogEvents",
                "logs:StartQuery",
                "logs:GetQueryResults"
            ],
            "Resource": "*"
        }
    ]
}
```

---

## 16. Appendix: Open Questions Resolution

This section addresses the open questions from the requirements document.

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Language/Framework** | Python 3.11+ | Best LLM ecosystem, rapid development, excellent TUI libraries |
| **TUI Framework** | Textual | Modern async design, rich widgets, active development, streaming support |
| **Caching Strategy** | SQLite (MVP) | Simple, reliable, sufficient for initial log volumes |
| **LLM Function Calling** | Tool registry pattern with standardized definitions | Clean separation, easy to extend, provider-agnostic |
| **LLM Provider** | LiteLLM with Anthropic (MVP) | APPROVED - unified interface, Anthropic Claude for MVP |
| **PII Protection** | Sanitization layer (default enabled) | APPROVED - protects sensitive data before LLM transmission |
| **Error Handling** | Structured exceptions + user-friendly messages | Clear error hierarchy, contextual logging, graceful degradation |
| **Testing Strategy** | pytest + moto + respx | Comprehensive mocking, async support, good coverage |
| **Packaging/Distribution** | PyPI (primary) | MVP distribution; Homebrew + binaries post-MVP |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-06 | Sally (Architect) | Initial architecture document |
| 1.1 | 2026-02-06 | Sally (Architect) | Updated per stakeholder decisions: renamed to LogAI, added PII sanitization layer, clarified MVP scope, confirmed LiteLLM |

---

## Next Steps

1. ~~**Review**: TPM and Engineering review of this document~~ COMPLETE
2. ~~**Clarifications**: Address any questions or concerns~~ COMPLETE
3. ~~**Approval**: Sign-off from stakeholders~~ APPROVED
4. **Implementation**: Jackie to begin implementation following this design

---

*Document prepared by Sally, Senior Software Architect*
