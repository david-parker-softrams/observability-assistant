# Architectural Design: Migrate Tool Calls to AWS CloudWatch MCP Server

**Author:** Saanvi (Senior Software Architect)
**Date:** 2026-02-24
**Status:** Draft — Pending TPM Review
**Document:** `george-scratch/design-mcp-migration.md`

---

## 1. Executive Summary

This document describes the architectural design for migrating LogAI's custom CloudWatch tool implementations to use the official AWS Labs CloudWatch MCP Server (`awslabs.cloudwatch-mcp-server`). The MCP server exposes CloudWatch capabilities via the standardized Model Context Protocol over stdio, replacing our hand-rolled boto3-based tools with a maintained, upstream implementation.

### Recommendation

I recommend a **phased, additive migration** strategy:

1. **Phase 1** (1–2 days): Introduce an MCP client layer alongside existing tools, gated by a configuration flag. Both paths coexist. The MCP client wraps the `BaseTool` interface so the existing `ToolRegistry`, orchestrator, and TUI sidebar require zero changes.
2. **Phase 2** (1 day): Replace `list_log_groups` and `fetch_logs`/`search_logs` with MCP equivalents under the flag. Validate behavioral parity.
3. **Phase 3** (0.5 day): Remove deprecated native CloudWatch tools once MCP path is proven in production.

This approach preserves our critical PII sanitization and result caching layers, keeps `fetch_cached_result_chunk` as a native tool, and minimizes risk to the Textual TUI.

### Key Architectural Decision

MCP tools will be **wrapped in `BaseTool`-conforming adapter classes** that are registered in the existing `ToolRegistry`. This means:
- The orchestrator (`_execute_tool_calls`) requires **no changes** for MCP routing.
- The TUI sidebar tool status tracking (PENDING → RUNNING → SUCCESS/ERROR) works unchanged.
- The sanitization and caching adapter layer is applied at the adapter level, not in the orchestrator.

This is preferable to a "bypass" approach (routing MCP calls outside the registry) because it maintains a single code path for tool dispatch and avoids branching logic in the already-complex orchestrator.

---

## 2. Tool Mapping

### 2.1 Detailed Mapping Table

| Current Tool | MCP Equivalent(s) | Mapping Quality | Notes |
|---|---|---|---|
| `list_log_groups` | `describe_log_groups` | **Good** — near 1:1 | MCP tool returns metadata (stored bytes, retention, etc.) in addition to names. Our tool only returns names + ARN. We gain richer metadata. Minor: MCP uses `log_group_name_prefix` vs. our `prefix`. |
| `fetch_logs` | `execute_log_insights_query` + `get_logs_insight_query_results` | **Moderate** — behavioral shift | Our tool uses `FilterLogEvents` API (simple scan). MCP uses **CloudWatch Logs Insights** (query language). This is fundamentally different: Insights queries are async (submit → poll), more powerful (aggregation, parsing), but higher latency. See §2.2. |
| `search_logs` | `execute_log_insights_query` + `get_logs_insight_query_results` | **Moderate** — same as above | Our cross-group search maps to a multi-group Insights query. Insights natively supports querying across multiple log groups, so this is actually a cleaner fit than our manual loop-and-merge. |
| `fetch_cached_result_chunk` | **No MCP equivalent** | N/A | This is application-specific. Must remain a native tool. |

### 2.2 Behavioral Analysis: `fetch_logs` → Insights Query

**What we gain:**
- CloudWatch Logs Insights is significantly more powerful than `FilterLogEvents` — supports `parse`, `stats`, `sort`, `limit`, aggregation queries
- The MCP server provides `analyze_log_group` for anomaly detection — a capability we don't have today
- The MCP server handles query lifecycle management (submit, poll, cancel)
- Upstream maintenance — AWS Labs maintains the MCP server, so new CloudWatch features arrive without our effort

**What we lose / risks:**
- **Latency**: Insights queries are async. `execute_log_insights_query` returns a query ID; `get_logs_insight_query_results` must be polled. Typical latency: 2–10s vs. <1s for `FilterLogEvents`. The LLM will need to make two tool calls per log fetch.
- **Query language**: Our current `filter_pattern` uses CloudWatch filter syntax. Insights uses a different query language (`fields @timestamp, @message | filter @message like /ERROR/`). The LLM must learn this. Most modern LLMs (Claude, GPT-4) handle Insights syntax well, but this is a behavioral change.
- **Result format**: Insights returns `results` as a list of field-value pairs, not raw log events. Our sanitizer expects `events` with `message`, `timestamp`, `logStreamName` fields. The adapter must transform results.
- **Cost**: Insights queries are billed per GB scanned (same as `FilterLogEvents`), but the pricing model differs slightly.

**Architect's opinion:** The Insights-based approach is **architecturally superior** for an AI assistant. The LLM can leverage Insights' query language for complex analysis (e.g., "show me the top 10 error messages by frequency in the last hour") without us building that logic ourselves. The latency trade-off is acceptable for an interactive assistant. I recommend embracing the two-call pattern (`execute` → `get_results`) rather than trying to hide it.

### 2.3 New Capabilities Available via MCP

The MCP server exposes tools we don't have today. While out of scope for the initial migration, the architecture should allow these to be trivially enabled:

| MCP Tool | Capability |
|---|---|
| `analyze_log_group` | Anomaly detection, pattern analysis |
| `cancel_logs_insight_query` | Cancel long-running queries |
| `get_metric_data` | CloudWatch Metrics integration |
| `get_active_alarms` | CloudWatch Alarms integration |
| `analyze_metric` | Metric anomaly detection |

We should register *all* MCP tools (not just the mapped ones) and let the LLM decide which to use. This gives us immediate feature expansion with zero additional code.

---

## 3. MCP Client Architecture

### 3.1 SDK Selection

Use the official **`mcp` Python package** (PyPI: `mcp`, repo: `modelcontextprotocol/python-sdk`). Specifically:

- `mcp.client.stdio.stdio_client` — creates a connection to an MCP server subprocess over stdio
- `mcp.ClientSession` — manages the JSON-RPC session (tool listing, tool invocation)

The `mcp` package is async-native and uses `anyio`/`asyncio`, which aligns perfectly with our existing async architecture (Textual TUI, async orchestrator, async tool execution).

### 3.2 New Module Location

Create a new module at:

```
src/logai/providers/mcp/
├── __init__.py
├── client.py          # MCPClientManager — lifecycle, connection management
├── tool_adapter.py    # MCPToolAdapter(BaseTool) — wraps MCP tools as BaseTool
└── sanitization.py    # MCPResultSanitizer — post-processing adapter
```

**Rationale:** Place under `providers/` because the MCP server is an external provider of tool capabilities, analogous to how `providers/datasources/cloudwatch.py` provides data access and `providers/llm/` provides LLM access.

### 3.3 MCPClientManager — Lifecycle Management

```python
# src/logai/providers/mcp/client.py

import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages the lifecycle of an MCP server subprocess and client session.

    The MCP server is a subprocess communicating over stdio (stdin/stdout)
    using JSON-RPC. This class handles:
    - Starting the server subprocess
    - Establishing a ClientSession
    - Discovering available tools via tools/list
    - Invoking tools via tools/call
    - Graceful shutdown
    """

    def __init__(
        self,
        command: str = "uvx",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or ["awslabs.cloudwatch-mcp-server@latest"]
        self._env = env or {}
        self._session: ClientSession | None = None
        self._tools_cache: list[dict[str, Any]] | None = None
        # Context manager handles for the stdio transport
        self._stdio_cm = None
        self._session_cm = None
        self._read_stream = None
        self._write_stream = None

    async def start(self) -> None:
        """Start the MCP server subprocess and initialize the session."""
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )

        # Enter the stdio_client context manager
        self._stdio_cm = stdio_client(server_params)
        self._read_stream, self._write_stream = await self._stdio_cm.__aenter__()

        # Enter the ClientSession context manager
        self._session_cm = ClientSession(self._read_stream, self._write_stream)
        self._session = await self._session_cm.__aenter__()

        # Initialize the session (MCP handshake)
        await self._session.initialize()

        logger.info("MCP client session initialized")

    async def stop(self) -> None:
        """Gracefully shut down the MCP session and server subprocess."""
        if self._session_cm:
            await self._session_cm.__aexit__(None, None, None)
        if self._stdio_cm:
            await self._stdio_cm.__aexit__(None, None, None)
        self._session = None
        self._tools_cache = None
        logger.info("MCP client session closed")

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        Discover available tools from the MCP server.

        Returns tool definitions in OpenAI-compatible function calling format.
        Caches the result after first call (tools don't change at runtime).
        """
        if self._tools_cache is not None:
            return self._tools_cache

        if not self._session:
            raise RuntimeError("MCP client not connected. Call start() first.")

        result = await self._session.list_tools()

        # Convert MCP tool schemas to OpenAI function calling format
        tools = []
        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,  # Already JSON Schema
            })

        self._tools_cache = tools
        logger.info(f"Discovered {len(tools)} MCP tools: {[t['name'] for t in tools]}")
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Invoke an MCP tool by name with given arguments.

        Args:
            name: MCP tool name
            arguments: Tool arguments as a dictionary

        Returns:
            Tool result (parsed from MCP response)

        Raises:
            RuntimeError: If client not connected
            MCPToolError: If tool invocation fails
        """
        if not self._session:
            raise RuntimeError("MCP client not connected. Call start() first.")

        result = await self._session.call_tool(name, arguments)

        # MCP returns CallToolResult with content (list of TextContent/ImageContent)
        # Extract text content and parse as JSON if possible
        if result.isError:
            error_text = ""
            for content_block in result.content:
                if hasattr(content_block, "text"):
                    error_text += content_block.text
            raise MCPToolError(name, error_text)

        # Collect text from all content blocks
        text_parts = []
        for content_block in result.content:
            if hasattr(content_block, "text"):
                text_parts.append(content_block.text)

        combined_text = "\n".join(text_parts)

        # Try to parse as JSON; fall back to raw text
        import json
        try:
            return json.loads(combined_text)
        except json.JSONDecodeError:
            return {"raw_text": combined_text}


class MCPToolError(Exception):
    """Raised when an MCP tool invocation fails."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"MCP tool '{tool_name}' failed: {message}")
```

### 3.4 Lifecycle: When to Start/Stop

**Start:** During CLI startup (`src/logai/cli.py`), after settings are loaded and AWS credentials validated, but *before* tool registration. The MCP server must be running so we can call `list_tools()` to discover tools for registration.

**Stop:** On application exit. The Textual app's `on_unmount` or a `try/finally` block in `cli.py` should call `mcp_client.stop()`.

**Failure mode:** If the MCP server fails to start (e.g., `uvx` not installed, network issues downloading the package), fall back to native tools. This is Phase 1's dual-path behavior. Log a warning and continue.

### 3.5 Async Considerations

The MCP SDK is fully async. Our application already uses `asyncio` throughout:
- Tool execution is `async def execute()`
- The orchestrator uses `await` for tool calls
- Textual's event loop is asyncio-based

**No async compatibility issues.** The `MCPClientManager.call_tool()` is an `async def` that `await`s the MCP session's `call_tool`, which fits naturally into `BaseTool.execute()`.

One concern: the MCP server subprocess communicates over stdio. The `mcp` SDK handles this via `anyio` streams, which integrate with asyncio. No thread pool executor needed.

---

## 4. Tool Registry Integration

### 4.1 Approach: MCP Tools Wrap `BaseTool`

Each MCP tool will be wrapped in an `MCPToolAdapter` class that implements `BaseTool`. This is the cleanest integration point because:

1. `ToolRegistry` continues to work with zero changes
2. `ToolRegistry.to_function_definitions()` automatically includes MCP tools
3. `ToolRegistry.execute()` dispatches to MCP tools via the same path as native tools
4. The orchestrator's `_execute_tool_calls()` requires no changes
5. TUI sidebar tool tracking works unchanged

### 4.2 MCPToolAdapter Implementation

```python
# src/logai/providers/mcp/tool_adapter.py

from typing import Any

from logai.core.tools.base import BaseTool, ToolExecutionError
from logai.providers.mcp.client import MCPClientManager, MCPToolError


class MCPToolAdapter(BaseTool):
    """
    Adapts an MCP server tool to the BaseTool interface.

    This allows MCP tools to be registered in the ToolRegistry and
    dispatched by the orchestrator using the same code path as native tools.
    """

    def __init__(
        self,
        mcp_client: MCPClientManager,
        tool_name: str,
        tool_description: str,
        tool_parameters: dict[str, Any],
        result_processor: "ResultProcessor | None" = None,
    ) -> None:
        self._mcp_client = mcp_client
        self._name = tool_name
        self._description = tool_description
        self._parameters = tool_parameters
        self._result_processor = result_processor

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        try:
            result = await self._mcp_client.call_tool(self._name, kwargs)

            # Apply post-processing (sanitization, caching, format normalization)
            if self._result_processor:
                result = await self._result_processor.process(self._name, result)

            # Ensure result is a dict with 'success' key for consistency
            if isinstance(result, dict) and "success" not in result:
                result["success"] = True

            return result

        except MCPToolError as e:
            raise ToolExecutionError(
                message=str(e),
                tool_name=self._name,
                details={"source": "mcp", "arguments": kwargs},
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                message=f"MCP tool execution failed: {str(e)}",
                tool_name=self._name,
                details={"source": "mcp", "arguments": kwargs},
            ) from e
```

### 4.3 Dynamic Tool Discovery and Registration

At startup, after the MCP client connects, we discover tools and register them:

```python
# In src/logai/cli.py startup sequence (or a dedicated registration function)

async def register_mcp_tools(
    mcp_client: MCPClientManager,
    result_processor: ResultProcessor,
    exclude_tools: set[str] | None = None,
) -> list[str]:
    """
    Discover MCP tools and register them in the ToolRegistry.

    Args:
        mcp_client: Connected MCP client
        result_processor: Post-processing pipeline
        exclude_tools: Tool names to skip (if overridden by native tools)

    Returns:
        List of registered MCP tool names
    """
    exclude = exclude_tools or set()
    mcp_tools = await mcp_client.list_tools()
    registered = []

    for tool_def in mcp_tools:
        tool_name = tool_def["name"]
        if tool_name in exclude:
            logger.info(f"Skipping MCP tool '{tool_name}' (excluded)")
            continue

        adapter = MCPToolAdapter(
            mcp_client=mcp_client,
            tool_name=tool_name,
            tool_description=tool_def["description"],
            tool_parameters=tool_def["parameters"],
            result_processor=result_processor,
        )
        ToolRegistry.register(adapter)
        registered.append(tool_name)

    return registered
```

### 4.4 Keeping `fetch_cached_result_chunk` as a Native Tool

`fetch_cached_result_chunk` is purely application-level (it retrieves chunks from our `ResultCacheManager`). It has no CloudWatch equivalent and must remain native. Since both native and MCP tools go through the same `ToolRegistry`, this coexistence is automatic — no special handling needed.

### 4.5 ToolRegistry Changes

**None required.** The `ToolRegistry` class at `src/logai/core/tools/registry.py` is already generic enough:
- `register(tool: BaseTool)` — works with any `BaseTool` subclass
- `execute(tool_name, **kwargs)` — dispatches by name
- `to_function_definitions()` — calls `tool.to_function_definition()` on each

The `MCPToolAdapter` is a `BaseTool`, so it slots in seamlessly. This is the primary advantage of the adapter pattern.

---

## 5. Sanitization & Caching Adapter

### 5.1 Problem Statement

Our existing tools apply PII sanitization and result caching *inside* the tool implementation (see `FetchLogsTool.execute()` lines 267–296 in `cloudwatch_tools.py`). The MCP server returns raw CloudWatch data with no sanitization. We must intercept MCP results and apply our policies.

### 5.2 ResultProcessor — Post-Processing Pipeline

Create a composable result processor that the `MCPToolAdapter` calls after each MCP tool invocation:

```python
# src/logai/providers/mcp/sanitization.py

import logging
from typing import Any, Protocol

from logai.cache.manager import CacheManager
from logai.core.sanitizer import LogSanitizer

logger = logging.getLogger(__name__)


class ResultProcessor:
    """
    Post-processing pipeline for MCP tool results.

    Applies sanitization, caching, and format normalization to raw
    MCP server responses before they reach the LLM.
    """

    def __init__(
        self,
        sanitizer: LogSanitizer | None = None,
        cache: CacheManager | None = None,
    ) -> None:
        self._sanitizer = sanitizer
        self._cache = cache

        # Map MCP tool names to processing strategies
        self._processors: dict[str, str] = {
            # Tools that return log data → need sanitization
            "execute_log_insights_query": "passthrough",    # Returns query ID only
            "get_logs_insight_query_results": "sanitize",   # Returns actual log data
            "describe_log_groups": "passthrough",           # Metadata only, no PII
            "analyze_log_group": "sanitize",                # May contain log samples
            "cancel_logs_insight_query": "passthrough",     # No data returned
            # Metrics/alarms tools — no log data, no sanitization needed
            "get_metric_data": "passthrough",
            "get_metric_metadata": "passthrough",
            "get_active_alarms": "passthrough",
            "get_alarm_history": "passthrough",
            "get_recommended_metric_alarms": "passthrough",
            "analyze_metric": "passthrough",
        }

    async def process(self, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Process a raw MCP tool result.

        Args:
            tool_name: Name of the MCP tool
            result: Raw result from MCP server

        Returns:
            Processed result with sanitization applied
        """
        strategy = self._processors.get(tool_name, "passthrough")

        if strategy == "sanitize" and self._sanitizer and self._sanitizer.enabled:
            result = self._apply_sanitization(tool_name, result)

        return result

    def _apply_sanitization(self, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        """
        Apply PII sanitization to log-containing results.

        MCP Logs Insights results have a different structure than our native tools:
        - Native: {"events": [{"message": "...", "timestamp": ...}, ...]}
        - Insights: {"results": [{"@message": "...", "@timestamp": "..."}, ...]}

        This method handles both formats.
        """
        # Handle Insights query results format
        results_list = result.get("results", [])
        if results_list:
            sanitized_results = []
            total_redactions: dict[str, int] = {}

            for record in results_list:
                # Insights returns field-value pairs
                # Sanitize all string values
                sanitized_record = {}
                for key, value in record.items():
                    if isinstance(value, str):
                        sanitized = self._sanitizer.sanitize_text(value)
                        sanitized_record[key] = sanitized.sanitized_text
                        # Accumulate redaction counts
                        for pattern_name, count in sanitized.redactions.items():
                            total_redactions[pattern_name] = (
                                total_redactions.get(pattern_name, 0) + count
                            )
                    else:
                        sanitized_record[key] = value
                sanitized_results.append(sanitized_record)

            result["results"] = sanitized_results
            result["sanitization"] = {
                "enabled": True,
                "redactions": total_redactions,
                "summary": self._sanitizer.get_redaction_summary(total_redactions),
            }

        # Also handle any "events" key (for analyze_log_group samples)
        events = result.get("events", [])
        if events and isinstance(events, list):
            sanitized_events, redactions = self._sanitizer.sanitize_log_events(events)
            result["events"] = sanitized_events
            result["sanitization"] = {
                "enabled": True,
                "redactions": redactions,
                "summary": self._sanitizer.get_redaction_summary(redactions),
            }

        return result
```

### 5.3 Caching Strategy

Caching is handled at **two levels** in the current architecture:

1. **Query-level caching** (`CacheManager`): Caches tool results by query parameters. Used in `ListLogGroupsTool`, `FetchLogsTool`, `SearchLogsTool`.
2. **Result-level caching** (`ResultCacheManager`): Caches large results for chunked retrieval. Managed by `_process_tool_result()` in the orchestrator.

For MCP tools:

- **Level 1 (Query-level):** Can optionally be added to `ResultProcessor`, but I recommend **deferring this** initially. The MCP server may have its own caching, and the Insights query model (async submit → poll results) doesn't map cleanly to our key-value cache. The cost-benefit isn't clear until we measure actual latency.
- **Level 2 (Result-level):** Works **unchanged**. The orchestrator's `_process_tool_result()` operates on the final tool result dict regardless of whether it came from a native tool or an MCP adapter. Large results from `get_logs_insight_query_results` will be automatically cached by the existing budget-aware mechanism.

### 5.4 Call Chain Diagram

```
LLM → tool_call("get_logs_insight_query_results", {...})
  │
  ▼
LLMOrchestrator._execute_tool_calls()
  │
  ├── ToolCallRecord(status=PENDING) → notify sidebar
  ├── ToolCallRecord(status=RUNNING) → notify sidebar
  │
  ▼
ToolRegistry.execute("get_logs_insight_query_results", **args)
  │
  ▼
MCPToolAdapter.execute(**args)
  │
  ├── MCPClientManager.call_tool("get_logs_insight_query_results", args)
  │       │
  │       └── [JSON-RPC over stdio to MCP server subprocess]
  │                │
  │                └── MCP server → CloudWatch Logs Insights API
  │
  ├── ResultProcessor.process("get_logs_insight_query_results", raw_result)
  │       │
  │       └── LogSanitizer.sanitize_text() on each field
  │
  └── return sanitized result dict
  │
  ▼
LLMOrchestrator._process_tool_result()
  │
  ├── Budget check (token count)
  ├── Large result? → ResultCacheManager.cache_result() → enhanced summary
  │
  └── return to conversation
```

---

## 6. Orchestrator Changes

### 6.1 Answer: Minimal to No Changes Required

The key architectural insight is that by wrapping MCP tools in `MCPToolAdapter(BaseTool)` and registering them in `ToolRegistry`, **the orchestrator requires no changes for MCP routing.** The dispatch path is:

```python
# In _execute_tool_calls (line 2017 of orchestrator.py):
result = await self.tool_registry.execute(function_name, **function_args)
```

This already dispatches to whatever `BaseTool` is registered under that name. If it's an `MCPToolAdapter`, the MCP call happens transparently.

### 6.2 What About Distinguishing MCP from Native?

**We don't need to.** That's the point of the adapter pattern. The orchestrator treats all tools identically. The `MCPToolAdapter` handles the MCP-specific concerns internally.

### 6.3 Tool Status Tracking

The existing status tracking code (lines 1973–2050 of `orchestrator.py`) works unchanged:

```python
record = ToolCallRecord(id=tool_call_id, name=function_name, ...)
record.status = ToolCallStatus.PENDING
self._notify_tool_call(record)  # TUI sidebar updates

record.status = ToolCallStatus.RUNNING
self._notify_tool_call(record)

# ... await self.tool_registry.execute() ...

record.status = ToolCallStatus.SUCCESS  # or ERROR on exception
self._notify_tool_call(record)
```

The MCP call latency (especially for Insights queries) means the RUNNING state will be visible longer in the sidebar, which is actually *better* UX — users see the tool is working.

### 6.4 One Optional Enhancement: Tool Source Annotation

While not required, it would be useful for debugging to annotate `ToolCallRecord` with the tool source:

```python
@dataclass
class ToolCallRecord:
    # ... existing fields ...
    source: str = "native"  # "native" or "mcp"
```

The `MCPToolAdapter` can set this by overriding `to_function_definition()` to include metadata, or the orchestrator can check `isinstance(tool, MCPToolAdapter)`. This is a nice-to-have, not a blocker.

---

## 7. AWS Credential Pass-Through

### 7.1 Current Flow

```
CLI args (--aws-profile, --aws-region)
  → settings.aws_profile, settings.aws_region (in cli.py, lines 414-417)
    → CloudWatchDataSource.__init__(settings) (creates boto3 session with profile/region)
```

### 7.2 MCP Server Configuration

The CloudWatch MCP server reads credentials from environment variables:
- `AWS_PROFILE` — AWS profile name
- `AWS_REGION` — AWS region
- `FASTMCP_LOG_LEVEL` — logging level (optional)

### 7.3 Pass-Through Design

When constructing the `MCPClientManager`, build the `env` dict from `LogAISettings`:

```python
# In CLI startup (src/logai/cli.py)

import os

def build_mcp_env(settings: LogAISettings) -> dict[str, str]:
    """
    Build environment variables for the MCP server subprocess.

    Inherits the parent process's environment and overlays
    LogAI's AWS configuration.
    """
    env = dict(os.environ)  # Inherit parent env (PATH, HOME, etc.)

    if settings.aws_profile:
        env["AWS_PROFILE"] = settings.aws_profile
    if settings.aws_region:
        env["AWS_REGION"] = settings.aws_region

    # Set log level based on our debug setting
    env["FASTMCP_LOG_LEVEL"] = "ERROR"  # Keep MCP server logs quiet

    return env

# Usage:
mcp_env = build_mcp_env(settings)
mcp_client = MCPClientManager(
    command="uvx",
    args=["awslabs.cloudwatch-mcp-server@latest"],
    env=mcp_env,
)
```

**Critical detail:** The `env` dict passed to `StdioServerParameters` **replaces** the subprocess environment (it doesn't merge). We must inherit `os.environ` and overlay our settings. The `PATH` variable is particularly important — `uvx` must be findable.

### 7.4 IAM Permissions

The MCP server requires additional IAM permissions beyond what our current tools need:

| Current permissions needed | Additional MCP permissions needed |
|---|---|
| `logs:FilterLogEvents` | `logs:StartQuery` |
| `logs:DescribeLogGroups` | `logs:GetQueryResults` |
| | `logs:StopQuery` |
| | `logs:ListLogAnomalyDetectors` |
| | `logs:ListAnomalies` |
| | `cloudwatch:GetMetricData` (if using metrics tools) |
| | `cloudwatch:DescribeAlarms` (if using alarms tools) |

**Action item:** Document the expanded IAM policy in the project README. Users upgrading to MCP will need to update their IAM roles.

---

## 8. Migration Strategy

### 8.1 Recommended Approach: Phased, Additive, Flag-Gated

#### Phase 1: Add MCP Client (Side-by-Side)

**Duration:** 1–2 days
**Risk:** Low
**Goal:** MCP infrastructure in place, all tools registered, native tools still active by default.

Changes:
1. Add `mcp` dependency to `pyproject.toml`
2. Create `src/logai/providers/mcp/` module with `client.py`, `tool_adapter.py`, `sanitization.py`
3. Add settings to `LogAISettings`:
   ```python
   use_mcp_tools: bool = Field(default=False, description="Use MCP server for CloudWatch tools")
   mcp_server_command: str = Field(default="uvx", description="MCP server launch command")
   mcp_server_args: list[str] = Field(
       default=["awslabs.cloudwatch-mcp-server@latest"],
       description="MCP server command arguments",
   )
   ```
4. In `cli.py` startup, if `use_mcp_tools` is True:
   - Start `MCPClientManager`
   - Call `register_mcp_tools()` instead of registering native CloudWatch tools
   - Still register `FetchCachedResultTool` natively
   - If MCP startup fails, log warning and fall back to native tools
5. Add `--use-mcp` CLI flag (maps to `settings.use_mcp_tools`)

**Testing:** Run both paths against the same AWS account. Compare tool results for correctness.

#### Phase 2: Validate and Tune

**Duration:** 1 day
**Risk:** Medium
**Goal:** Confirm behavioral parity. Tune sanitization mapping for Insights result format.

Changes:
1. Test with real CloudWatch data:
   - `describe_log_groups` output matches `list_log_groups` semantics
   - Insights query results sanitized correctly
   - Large results cached properly by `_process_tool_result()`
   - Tool status tracking works in TUI sidebar
2. Adjust `ResultProcessor` sanitization mappings based on actual MCP response shapes
3. Verify the LLM handles the two-call Insights pattern naturally (Claude and GPT-4 should)
4. Performance benchmark: measure latency delta between native and MCP paths

#### Phase 3: Remove Native CloudWatch Tools

**Duration:** 0.5 day
**Risk:** Low (after Phase 2 validation)
**Goal:** Clean up. Single code path.

Changes:
1. Remove `src/logai/core/tools/cloudwatch_tools.py` (or archive)
2. Remove `CloudWatchDataSource` from `src/logai/providers/datasources/cloudwatch.py`
3. Remove `boto3` dependency (unless other components use it)
4. Default `use_mcp_tools` to `True` and eventually remove the flag
5. Update system prompt in orchestrator to reference Insights query capabilities

### 8.2 Why Not Big-Bang?

A big-bang replacement would:
- Remove the ability to quickly roll back if MCP server has issues
- Require coordinated testing of sanitization, caching, and TUI in one release
- Risk breaking the app for users who don't have `uvx` installed

The phased approach lets us ship Phase 1 as a preview feature, gather feedback, and iterate.

---

## 9. Risks & Open Questions

### 9.1 Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **MCP server subprocess crashes mid-session** | High | Implement health checks in `MCPClientManager`. Detect broken pipe on `call_tool()` and attempt restart. Consider a heartbeat mechanism. |
| **Insights query latency** (2–10s per query) | Medium | The LLM's multi-turn loop already handles tool call latency. The TUI sidebar's RUNNING state provides user feedback. May need to increase `max_tool_iterations` if Insights requires submit+poll pattern. |
| **`uvx` not installed on user's system** | Medium | Document as a prerequisite. `uvx` is from the `uv` package manager. Add a startup check: `shutil.which("uvx")`. Fall back to native tools with a clear error message. |
| **MCP server version drift** | Medium | Pin the MCP server version in `mcp_server_args` (e.g., `awslabs.cloudwatch-mcp-server@0.2.0`). `@latest` is convenient for dev but risky for production. |
| **Result format mismatch** | Medium | Insights results use `@message`, `@timestamp` field names vs. our `message`, `timestamp`. The `ResultProcessor` must normalize. May need iterative fixes as we discover edge cases. |
| **Sanitization gaps** | High | MCP results may contain PII in unexpected fields (e.g., log group names with customer IDs, metric labels). The `ResultProcessor` should sanitize *all* string values in log-data-returning tools, not just known fields. |
| **Two-call pattern confuses some LLMs** | Low | Smaller/older models may struggle with "call execute_log_insights_query, then call get_logs_insight_query_results with the query ID." Claude and GPT-4 handle this well. For Ollama models, may need system prompt guidance. |
| **stdio buffer deadlock** | Low | The `mcp` SDK handles buffering, but large results could theoretically cause backpressure. The SDK uses async streams which mitigate this. Monitor in testing. |

### 9.2 Open Questions

1. **Should we expose ALL MCP tools to the LLM, or only the log-related subset?**
   - My recommendation: Expose all. The LLM is smart enough to ignore irrelevant tools, and metrics/alarms tools are valuable for observability use cases. But this increases the tool schema token cost in each LLM call. Measure the impact.

2. **How does the MCP server handle Insights query polling?**
   - Does `get_logs_insight_query_results` block until the query completes, or does it return immediately with a status? If it returns `Running` status, the LLM will need to poll. Need to test this.

3. **Can we version-pin the MCP server?**
   - `uvx awslabs.cloudwatch-mcp-server@latest` always gets the latest version. For production stability, we should pin: `uvx awslabs.cloudwatch-mcp-server@0.X.Y`. Need to determine the current stable version.

4. **What happens when MCP server's stdout/stderr overlap?**
   - The MCP protocol uses stdout for JSON-RPC. If the MCP server also logs to stdout, it could corrupt the protocol. The MCP spec says servers should use stderr for logging. Verify the CloudWatch MCP server follows this.

5. **Do we need `analyze_log_group` integration into the system prompt?**
   - The anomaly detection tool is powerful but may return large payloads. Should we guide the LLM on when to use it, or let it discover organically?

6. **Token cost of expanded tool schemas:**
   - Our current 4 tools produce ~800 tokens of schema. The MCP server exposes 10+ tools, potentially 2000+ tokens. This eats into context budget. Need to measure and potentially filter to relevant tools only.

---

## 10. Dependencies & Prerequisites

### 10.1 New Python Packages

| Package | Version | Purpose |
|---|---|---|
| `mcp` | `>=1.0.0` | MCP Python SDK (client, session, stdio transport) |

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...

    # MCP (Model Context Protocol)
    "mcp>=1.0.0",
]
```

The `mcp` package depends on `anyio`, `httpx-sse`, and `pydantic` — all of which are either already in our dependency tree or compatible.

### 10.2 System Dependencies

| Dependency | Required By | Installation |
|---|---|---|
| `uvx` (from `uv`) | Launching MCP server | `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `awslabs.cloudwatch-mcp-server` | MCP server itself | Auto-installed by `uvx` on first run (downloaded to cache) |

### 10.3 AWS IAM Permissions

Existing permissions plus:
```json
{
    "Effect": "Allow",
    "Action": [
        "logs:StartQuery",
        "logs:GetQueryResults",
        "logs:StopQuery",
        "logs:ListLogAnomalyDetectors",
        "logs:ListAnomalies"
    ],
    "Resource": "*"
}
```

If using metrics/alarms tools:
```json
{
    "Effect": "Allow",
    "Action": [
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmHistory"
    ],
    "Resource": "*"
}
```

### 10.4 Startup Check

Add a pre-flight check in `cli.py` when `use_mcp_tools` is enabled:

```python
import shutil

if settings.use_mcp_tools:
    if not shutil.which("uvx"):
        print("⚠ MCP tools enabled but 'uvx' not found on PATH.")
        print("  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("  Falling back to native CloudWatch tools.")
        settings.use_mcp_tools = False
```

---

## Appendix A: File Change Summary

| File | Change Type | Description |
|---|---|---|
| `src/logai/providers/mcp/__init__.py` | **New** | Module init |
| `src/logai/providers/mcp/client.py` | **New** | `MCPClientManager` class |
| `src/logai/providers/mcp/tool_adapter.py` | **New** | `MCPToolAdapter(BaseTool)` class |
| `src/logai/providers/mcp/sanitization.py` | **New** | `ResultProcessor` class |
| `src/logai/config/settings.py` | **Modified** | Add `use_mcp_tools`, `mcp_server_command`, `mcp_server_args` fields |
| `src/logai/cli.py` | **Modified** | Add MCP startup logic, `--use-mcp` flag, fallback handling |
| `pyproject.toml` | **Modified** | Add `mcp>=1.0.0` dependency |
| `src/logai/core/orchestrator.py` | **No change** | Adapter pattern means orchestrator is unaware of MCP |
| `src/logai/core/tools/registry.py` | **No change** | Works with any `BaseTool` subclass |
| `src/logai/core/tools/base.py` | **No change** | Interface remains stable |
| `src/logai/core/tools/cloudwatch_tools.py` | **Deprecated in Phase 3** | Kept during Phase 1-2 for fallback |
| `src/logai/providers/datasources/cloudwatch.py` | **Deprecated in Phase 3** | Kept during Phase 1-2 for fallback |

## Appendix B: Sequence Diagram — MCP Tool Call Flow

```
User → TUI → Orchestrator → LLM Provider → LLM
                                               │
                                               ▼
                                    LLM returns tool_call:
                                    "get_logs_insight_query_results"
                                               │
                                               ▼
                              Orchestrator._execute_tool_calls()
                                               │
                                    ToolCallRecord(PENDING)
                                    ToolCallRecord(RUNNING)
                                               │
                                               ▼
                                    ToolRegistry.execute()
                                               │
                                               ▼
                                    MCPToolAdapter.execute()
                                               │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                              ▼                 ▼                 ▼
                        MCPClient         ResultProcessor    Return to
                        .call_tool()      .process()         Orchestrator
                              │                 │                 │
                              ▼                 ▼                 ▼
                        MCP Server        LogSanitizer      _process_tool_result()
                        (subprocess)      .sanitize()       (budget/cache)
                              │                                   │
                              ▼                                   ▼
                        CloudWatch                          Conversation
                        Logs Insights                       History
                        API                                       │
                                                                  ▼
                                                            LLM (next turn)
```

---

*End of Design Document*
