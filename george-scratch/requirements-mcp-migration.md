# Requirements: Migrate Tool Calls to AWS CloudWatch MCP Server

**Date:** 2026-02-24
**Requested by:** David Parker
**Assigned to:** Saanvi (Software Architect)

---

## Background

The application is an AI-powered observability assistant (LogAI) that uses LLM tool calls to
interact with AWS CloudWatch. Currently all tool call logic is custom-built in-house.

AWS Labs has published an official open-source **CloudWatch MCP Server**
(`awslabs.cloudwatch-mcp-server`) that exposes CloudWatch capabilities through the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) — a standardized
protocol for connecting LLMs to external tools and data sources.

We want to evaluate and plan replacing our custom in-house tool call implementations with
the official CloudWatch MCP server.

---

## Current State: Existing Tools

The application exposes 4 tools to the LLM today:

| Tool | File | Description |
|---|---|---|
| `list_log_groups` | `src/logai/core/tools/cloudwatch_tools.py` | Lists CloudWatch log groups with optional prefix filter |
| `fetch_logs` | `src/logai/core/tools/cloudwatch_tools.py` | Fetches log events from a specific log group (sanitized, time range + filter pattern support) |
| `search_logs` | `src/logai/core/tools/cloudwatch_tools.py` | Cross-group search for patterns across multiple log groups |
| `fetch_cached_result_chunk` | `src/logai/tools/fetch_cached_result.py` | Retrieves paginated chunks of previously cached large query results |

### How Tools Are Currently Wired

- Tools are **hardcoded and registered at CLI startup** (`src/logai/cli.py`, lines 465-495)
- Each tool is instantiated with dependency injection (datasource, sanitizer, settings, cache manager)
- Registered to a singleton `ToolRegistry` class
- Tool schemas sent to LLM via `ToolRegistry.to_function_definitions()` (OpenAI-compatible format)
- Tool dispatch handled by `LLMOrchestrator._execute_tool_calls()` in `src/logai/core/orchestrator.py`
- LLM communication uses **LiteLLM** (primary, supporting Anthropic/OpenAI/Ollama) and **httpx**
  (GitHub Copilot provider, direct HTTP to OpenAI-compatible endpoint)

---

## CloudWatch MCP Server Capabilities

The AWS Labs CloudWatch MCP Server (`awslabs.cloudwatch-mcp-server`) provides:

### Logs Tools (most relevant)
- `describe_log_groups` — Finds metadata about CloudWatch log groups
- `analyze_log_group` — Analyzes CloudWatch logs for anomalies, message patterns, and error patterns
- `execute_log_insights_query` — Executes CloudWatch Logs Insights queries; returns a query ID
- `get_logs_insight_query_results` — Retrieves results of an executed Logs Insights query
- `cancel_logs_insight_query` — Cancels an in-progress Logs Insights query

### Metrics Tools
- `get_metric_data`, `get_metric_metadata`, `get_recommended_metric_alarms`, `analyze_metric`

### Alarms Tools
- `get_active_alarms`, `get_alarm_history`

### Deployment
- Runs locally via `uvx awslabs.cloudwatch-mcp-server@latest`
- Uses `stdio` transport (subprocess-based)
- Configured via `AWS_PROFILE` and `AWS_REGION` env vars
- IAM permissions required: `logs:DescribeLogGroups`, `logs:StartQuery`, `logs:GetQueryResults`,
  `logs:StopQuery`, `logs:ListLogAnomalyDetectors`, `logs:ListAnomalies`, `cloudwatch:*` (various)

---

## Design Goals

1. **Evaluate fit**: Determine how well the CloudWatch MCP server's tools cover our existing
   tool surface area (4 tools above).

2. **MCP client integration**: Design how to integrate an MCP client into our existing
   LLM orchestration pipeline. Our app is the MCP *client* — it must connect to the MCP server
   subprocess, discover its tools, and route LLM tool calls to it.

3. **Handle gaps**: Our `fetch_cached_result_chunk` tool is application-specific (not a CloudWatch
   concept). The design must account for tools that cannot be replaced by MCP.

4. **LiteLLM + GitHub Copilot compatibility**: The MCP client layer must work with both of our
   LLM providers. The tool schema format must remain OpenAI-compatible.

5. **Log sanitization**: Our current `fetch_logs` and `search_logs` tools run log data through
   a sanitizer (PII redaction, etc.). The MCP server returns raw CloudWatch data. The design must
   preserve sanitization.

6. **Result caching**: Our current tools integrate with a `CacheManager` for performance.
   The design should preserve or replicate this behavior.

7. **AWS profile/region pass-through**: Our app accepts `--aws-profile` and `--aws-region` CLI
   args today. These must be forwarded to the MCP server process.

8. **Minimal disruption to TUI**: The Textual-based TUI and tool execution sidebar that displays
   tool status (PENDING → RUNNING → SUCCESS/ERROR) must continue to work.

---

## Out of Scope

- Replacing the LLM provider layer (LiteLLM / GitHub Copilot) — that stays as-is
- Other AWS MCP servers (non-CloudWatch) — not in scope for this phase
- Remote/managed MCP hosting — local stdio transport only for this phase

---

## Deliverable

Saanvi should produce a detailed architectural design document covering:

1. Tool-by-tool mapping: current tool → MCP equivalent (or "no equivalent, keep as-is")
2. MCP client architecture: how to embed an MCP stdio client into the Python application
3. Tool registry changes: how MCP tools get registered alongside (or instead of) custom tools
4. Sanitization & caching adapter layer design
5. Orchestrator changes needed for MCP tool call routing
6. AWS credential/profile pass-through approach
7. Migration strategy: phased approach vs. big-bang replacement
8. Risks and open questions
