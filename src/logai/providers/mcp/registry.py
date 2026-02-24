"""MCP tool registration helpers.

Extracted from ``logai.cli`` so that ``logai.ui.screens.chat`` can import
``register_mcp_tools`` directly — breaking the circular import that arose
when ``chat.py`` imported from ``cli.py`` and ``cli.py`` (transitively) could
import from the UI layer.
"""

import logging
from typing import TYPE_CHECKING

from logai.core.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from logai.providers.mcp.client import MCPClientManager
    from logai.providers.mcp.sanitization import ResultProcessor

logger = logging.getLogger(__name__)


async def register_mcp_tools(
    mcp_client: "MCPClientManager",
    result_processor: "ResultProcessor",
    exclude_tools: set[str] | None = None,
) -> list[str]:
    """
    Discover MCP tools and register them in the ``ToolRegistry``.

    Fetches the tool list from the connected MCP server, wraps each tool
    in an ``MCPToolAdapter``, and registers it.  Tools whose names appear
    in ``exclude_tools`` are skipped (reserved for future use when a native
    tool should take precedence over its MCP counterpart).

    Args:
        mcp_client: An already-connected ``MCPClientManager``.
        result_processor: Post-processing pipeline (sanitization, etc.)
                          applied to every MCP tool result.
        exclude_tools: Optional set of MCP tool names to skip.

    Returns:
        List of registered MCP tool names.
    """
    from logai.providers.mcp.tool_adapter import MCPToolAdapter

    exclude = exclude_tools or set()
    mcp_tools = await mcp_client.list_tools()
    registered: list[str] = []

    for tool_def in mcp_tools:
        tool_name: str = tool_def["name"]
        if tool_name in exclude:
            logger.info("Skipping MCP tool '%s' (excluded)", tool_name)
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

    logger.info("Registered %d MCP tools: %s", len(registered), registered)
    return registered
