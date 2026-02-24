"""MCP (Model Context Protocol) provider module for LogAI.

This package provides the client infrastructure for connecting to the
AWS CloudWatch MCP server, adapting its tools to the BaseTool interface,
and applying LogAI's sanitization pipeline to MCP results.

``register_mcp_tools`` lives in ``logai.providers.mcp.registry`` and is
re-exported here for convenience.
"""

from logai.providers.mcp.registry import register_mcp_tools

__all__ = ["register_mcp_tools"]
