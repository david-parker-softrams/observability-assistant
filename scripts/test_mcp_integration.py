#!/usr/bin/env python3
"""
Integration smoke test for the MCP provider module (Phase 1 + 2).

Validates that all new MCP modules import correctly and that the core
objects behave as expected WITHOUT requiring a live MCP server.

Run from the repository root:
    python scripts/test_mcp_integration.py
"""

import sys
from pathlib import Path

# Ensure the src tree is on sys.path when running directly.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# 1. Import all new MCP modules
# ---------------------------------------------------------------------------

print("1. Importing MCP modules...")

from logai.providers.mcp.client import MCPClientManager  # noqa: E402
from logai.providers.mcp.sanitization import ResultProcessor  # noqa: E402
from logai.providers.mcp.tool_adapter import MCPToolAdapter  # noqa: E402

print("   OK — MCPClientManager, MCPToolError, ResultProcessor, MCPToolAdapter imported")

# ---------------------------------------------------------------------------
# 2. Create an MCPClientManager — do NOT call start() (no live server)
# ---------------------------------------------------------------------------

print("2. Creating MCPClientManager (no start())...")

client = MCPClientManager(
    command="uvx",
    args=["awslabs.cloudwatch-mcp-server@latest"],
)

assert not client.is_connected, "New client should not be connected before start()"
print("   OK — client created, is_connected=False")

# ---------------------------------------------------------------------------
# 3. Create a ResultProcessor with no sanitizer
# ---------------------------------------------------------------------------

print("3. Creating ResultProcessor with no sanitizer...")

processor = ResultProcessor(sanitizer=None)
print("   OK — ResultProcessor created")

# ---------------------------------------------------------------------------
# 4. Create an MCPToolAdapter with a fake/hardcoded tool definition
# ---------------------------------------------------------------------------

print("4. Creating MCPToolAdapter with mock tool definition...")

FAKE_NAME = "describe_log_groups"
FAKE_DESCRIPTION = "Lists CloudWatch log groups matching an optional prefix."
FAKE_PARAMETERS = {
    "type": "object",
    "properties": {
        "logGroupNamePrefix": {
            "type": "string",
            "description": "Optional prefix to filter log groups.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of log groups to return.",
        },
    },
    "required": [],
}

adapter = MCPToolAdapter(
    mcp_client=client,
    tool_name=FAKE_NAME,
    tool_description=FAKE_DESCRIPTION,
    tool_parameters=FAKE_PARAMETERS,
    result_processor=processor,
)
print("   OK — MCPToolAdapter created")

# ---------------------------------------------------------------------------
# 5. Verify .name, .description, .parameters properties
# ---------------------------------------------------------------------------

print("5. Verifying adapter properties...")

assert adapter.name == FAKE_NAME, f"Expected name={FAKE_NAME!r}, got {adapter.name!r}"
assert (
    adapter.description == FAKE_DESCRIPTION
), f"Expected description={FAKE_DESCRIPTION!r}, got {adapter.description!r}"
assert (
    adapter.parameters == FAKE_PARAMETERS
), f"Expected parameters={FAKE_PARAMETERS!r}, got {adapter.parameters!r}"
print(f"   OK — name={adapter.name!r}")
print(f"   OK — description={adapter.description!r}")
print(f"   OK — parameters keys={list(adapter.parameters.keys())}")

# ---------------------------------------------------------------------------
# 6. Call to_function_definition() and verify OpenAI format
# ---------------------------------------------------------------------------

print("6. Calling adapter.to_function_definition()...")

func_def = adapter.to_function_definition()

# Verify top-level structure
assert isinstance(func_def, dict), f"Expected dict, got {type(func_def)}"
assert func_def.get("type") == "function", f"Expected type='function', got {func_def.get('type')!r}"
assert "function" in func_def, "Expected 'function' key in result"

inner = func_def["function"]
assert (
    inner.get("name") == FAKE_NAME
), f"Expected function.name={FAKE_NAME!r}, got {inner.get('name')!r}"
assert (
    inner.get("description") == FAKE_DESCRIPTION
), f"Expected function.description={FAKE_DESCRIPTION!r}, got {inner.get('description')!r}"
assert (
    inner.get("parameters") == FAKE_PARAMETERS
), f"Expected function.parameters={FAKE_PARAMETERS!r}, got {inner.get('parameters')!r}"

print("   OK — to_function_definition() returned correct OpenAI function calling format:")
print(f"         type={func_def['type']!r}")
print(f"         function.name={inner['name']!r}")
print(f"         function.description={inner['description']!r}")
print(f"         function.parameters keys={list(inner['parameters'].keys())}")

# ---------------------------------------------------------------------------
# All done
# ---------------------------------------------------------------------------

print()
print("All checks passed.")
