# LogAI Tools Documentation Index

**Prepared by**: Code Librarian (Hans)  
**Date**: 2026-02-11  
**Status**: Complete

## 📚 Documentation Set

This documentation package contains a complete inventory and reference for all tools available to the LLM agent in LogAI.

### Files in This Package

1. **TOOLS_DOCUMENTATION_INDEX.md** (This File)
   - Navigation guide for the documentation set
   - Quick facts about available tools
   - Where to find information

2. **TOOLS_SUMMARY.md** (Quick Reference)
   - **Length**: 419 lines
   - **Size**: 9.7 KB
   - **Best for**: Quick lookup, at-a-glance reference
   - **Contains**:
     - Executive summary
     - Tool inventory table
     - Quick usage patterns
     - Performance guidelines
     - Error handling guide
     - Configuration reference

3. **AVAILABLE_TOOLS_REFERENCE.md** (Complete Reference)
   - **Length**: 985 lines
   - **Size**: 28 KB
   - **Best for**: Comprehensive understanding, development
   - **Contains**:
     - Detailed specifications for each tool
     - Full parameter documentation
     - Return value structures
     - Time format handling
     - Filter pattern syntax
     - Caching strategy
     - Integration points
     - Architecture details
     - Common usage patterns
     - Limitations and planned features

---

## 🎯 What to Read

### If you have 5 minutes
Read: **TOOLS_SUMMARY.md** sections:
- Tool Inventory
- Tool Details at a Glance
- Common Usage Patterns

### If you have 15 minutes
Read: **TOOLS_SUMMARY.md** fully (all sections)

### If you need to implement something
Read: **AVAILABLE_TOOLS_REFERENCE.md** sections:
- Detailed Tool Specifications (your tool)
- Parameters & Return Types
- Integration Points
- Configuration

### If you need to debug/troubleshoot
Read:
- **TOOLS_SUMMARY.md** → Error Handling section
- **AVAILABLE_TOOLS_REFERENCE.md** → Error Handling & Retries section

### If you're adding a new tool
Read: **AVAILABLE_TOOLS_REFERENCE.md** → Contributing New Tools section

---

## 🔍 Quick Facts

### Total Tools Available
- **3 tools** total
- **2 categories**: Inventory & Discovery, Search & Fetch
- **1 data source**: AWS CloudWatch Logs

### Tool Names
1. `list_log_groups` - Discover available log groups
2. `fetch_logs` - Fetch from specific group
3. `search_logs` - Search across multiple groups

### Common Features
- ✅ Caching (10-100x faster on repeat queries)
- ✅ PII Sanitization (6+ types of sensitive data)
- ✅ Auto-retry (3 attempts with different strategies)
- ✅ Flexible time formats (ISO 8601, relative, epoch)
- ✅ Error handling (graceful failure modes)

### Key Statistics
| Metric | Value |
|--------|-------|
| Total Tools | 3 |
| Implementation Files | 5 |
| Test Files | 2+ |
| Support Time Formats | 3 |
| Max Retry Attempts | 3 |
| PII Types Redacted | 6+ |

---

## 📂 File Locations

### Implementation
```
src/logai/core/tools/
  ├── base.py                    # BaseTool abstract class
  ├── registry.py                # ToolRegistry
  ├── __init__.py
  └── cloudwatch_tools.py        # All 3 tools
```

### Tests
```
tests/unit/
  ├── test_cloudwatch_tools.py   # Tool unit tests
  ├── test_orchestrator.py       # Integration tests
  └── test_tools.py              # Registry tests
```

### Configuration
```
src/logai/
  ├── cli.py                     # Tool registration
  └── config/settings.py         # Tool settings
```

---

## 🛠️ Tool Reference Cards

### Tool 1: list_log_groups
- **Purpose**: Discover available log groups
- **Category**: Inventory & Discovery
- **Required params**: None (all optional)
- **Optional params**: `prefix`, `limit`
- **Returns**: List of log groups with metadata
- **File**: `src/logai/core/tools/cloudwatch_tools.py` (lines 13-125)
- **When used**: Initial discovery, log group lookup

### Tool 2: fetch_logs
- **Purpose**: Fetch logs from specific group
- **Category**: Search & Fetch
- **Required params**: `log_group`, `start_time`
- **Optional params**: `end_time`, `filter_pattern`, `limit`
- **Returns**: Sanitized log events with metadata
- **File**: `src/logai/core/tools/cloudwatch_tools.py` (lines 127-310)
- **When used**: Primary log retrieval, analysis

### Tool 3: search_logs
- **Purpose**: Search across multiple groups
- **Category**: Search & Fetch
- **Required params**: `log_group_patterns`, `search_pattern`, `start_time`
- **Optional params**: `end_time`, `limit`
- **Returns**: Events organized by source group
- **File**: `src/logai/core/tools/cloudwatch_tools.py` (lines 312-521)
- **When used**: Cross-service investigation, correlation

---

## 🚀 Quick Start Examples

### Example 1: List Lambda logs
```python
await orchestrator.execute(
    "list_log_groups",
    prefix="/aws/lambda/",
    limit=10
)
```

### Example 2: Fetch recent errors
```python
await orchestrator.execute(
    "fetch_logs",
    log_group="/aws/lambda/my-function",
    start_time="1h ago",
    filter_pattern="ERROR"
)
```

### Example 3: Search all services for 500 errors
```python
await orchestrator.execute(
    "search_logs",
    log_group_patterns=["/aws/"],
    search_pattern="500",
    start_time="1h ago"
)
```

---

## 📋 Common Scenarios

### Scenario 1: "What log groups do we have?"
1. Call `list_log_groups()` → See all groups
2. Agent responds with inventory

### Scenario 2: "Show me Lambda errors from today"
1. Call `list_log_groups(prefix="/aws/lambda/")` → Find Lambda groups
2. Call `fetch_logs(log_group="...", start_time="1d ago", filter_pattern="ERROR")`
3. Agent analyzes errors and responds

### Scenario 3: "Find timeout errors across all services"
1. Call `search_logs(log_group_patterns=["/aws/"], search_pattern="timeout", start_time="6h ago")`
2. Results organized by service
3. Agent correlates and responds

### Scenario 4: "Any API errors?" (Empty results)
1. Call `fetch_logs(...)` → No results
2. Orchestrator detects empty, nudges agent
3. Agent retries with expanded time range → Finds data
4. Agent responds with findings

---

## 🔧 Configuration Parameters

All tool-related settings in `LogAISettings`:

```python
# Caching
cache_enabled: bool = True
cache_ttl_minutes: int = 5

# Sanitization
pii_sanitization_enabled: bool = True

# Retry behavior
max_tool_iterations: int = 10
max_retry_attempts: int = 3
auto_retry_enabled: bool = True

# CloudWatch API
cloudwatch_region: str = "us-east-1"
max_log_events: int = 1000
```

---

## 📊 Performance Expectations

### Response Times
- **list_log_groups**: 100-500ms
- **fetch_logs** (1h range): 200-800ms
- **fetch_logs** (24h range): 1-5s
- **search_logs** (2-3 groups): 500-2s
- **search_logs** (10+ groups): 2-10s

### Optimization Tips
1. Use narrow time ranges (1h vs 24h)
2. Add filter patterns (ERROR vs no filter)
3. Specify exact log groups (vs prefixes)
4. Leverage caching (repeat queries are fast)
5. Use `limit` to cap results

---

## 🔐 Security Features

### PII Sanitization
All logs are automatically sanitized before reaching the LLM agent.

**Types redacted**:
- Email addresses: `user@example.com` → `[EMAIL]`
- Credit cards: `4111-1111-1111-1111` → `[CREDIT_CARD]`
- Phone numbers: `555-123-4567` → `[PHONE]`
- IPv4 addresses: `192.168.1.1` → `[IPV4]`
- API keys: `sk_live_1234567890` → `[API_KEY]`
- SSNs: `123-45-6789` → `[SSN]`

**Configuration**: Enable/disable via `pii_sanitization_enabled`

---

## ⚙️ Tool Architecture

### Component Hierarchy
```
BaseTool (Abstract Base Class)
  ├── ListLogGroupsTool
  ├── FetchLogsTool
  └── SearchLogsTool

ToolRegistry (Central Manager)
  ├── register(tool)
  ├── get(tool_name)
  ├── execute(tool_name, **kwargs)
  └── to_function_definitions()

LLMOrchestrator (Orchestration)
  ├── Tool call parsing
  ├── Tool execution
  ├── Result analysis
  ├── Retry logic
  └── Response generation
```

### Data Flow
```
User Query → LLM Agent → Tool Call
                          ↓
                    ToolRegistry.execute()
                          ↓
                    Tool.execute()
                          ↓
                    CloudWatch API
                          ↓
                    Sanitizer
                          ↓
                    Cache
                          ↓
                    Result to Agent
```

---

## 🐛 Troubleshooting Guide

### Problem: No logs found
**Possible causes**:
- Time range too narrow
- Wrong log group
- Filter pattern too strict

**Solution**:
- Expand time range
- Call `list_log_groups()` to verify
- Try simpler filter pattern

### Problem: Tool not found error
**Possible causes**:
- Tool not registered
- Wrong tool name

**Solution**:
- Check `src/logai/cli.py` for registration
- Verify tool name spelling

### Problem: Slow response
**Possible causes**:
- Large time range
- No cache hit
- Complex filter pattern

**Solution**:
- Narrow time range
- Repeat query (cache hit)
- Simplify filter pattern

---

## 📖 Study Guide

### For New Team Members
1. Read **TOOLS_SUMMARY.md** (15 minutes)
2. Review **Tool Reference Cards** section above
3. Try **Quick Start Examples** section
4. Read **Common Scenarios** section

### For Feature Development
1. Read relevant tool section in **AVAILABLE_TOOLS_REFERENCE.md**
2. Review **Parameters** and **Return Type** subsections
3. Check **Integration Points** section
4. Look at test examples in `tests/unit/test_cloudwatch_tools.py`

### For Debugging
1. Review **Error Handling** section
2. Check **Common Errors & Solutions** table
3. Examine error message and tool result
4. Consult **Troubleshooting Guide** above

---

## 📝 Document Maintenance

- **Created**: 2026-02-11
- **Maintained by**: Code Librarian (Hans)
- **Review cycle**: After tool changes or quarterly
- **Last reviewed**: 2026-02-11

### Version History
- **v1.0** (2026-02-11): Initial complete documentation

### How to Update
1. Update relevant `.md` file
2. Update version number
3. Note change in this index
4. Commit with descriptive message

---

## 🔗 External References

- **AWS CloudWatch Docs**: https://docs.aws.amazon.com/AmazonCloudWatch/
- **CloudWatch Insights**: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html
- **Filter Pattern Syntax**: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html

---

## 📞 Questions or Issues?

If you have questions about:
- **Tool usage**: Check relevant section in **TOOLS_SUMMARY.md**
- **Parameters**: Check **AVAILABLE_TOOLS_REFERENCE.md** detailed specs
- **Implementation**: Check code in `src/logai/core/tools/`
- **Errors**: Check Error Handling section in **AVAILABLE_TOOLS_REFERENCE.md**

---

**This documentation set is your complete reference for LogAI tools.**

**Start with TOOLS_SUMMARY.md for quick reference,**
**then dive into AVAILABLE_TOOLS_REFERENCE.md for details.**
