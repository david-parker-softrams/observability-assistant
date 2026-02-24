"""MCP tool adapter — wraps MCP server tools as BaseTool instances.

Each MCP tool discovered at runtime is wrapped in an ``MCPToolAdapter``
so it can be registered in the ``ToolRegistry`` and dispatched by the
orchestrator through the exact same code path as native tools.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from logai.core.tools.base import BaseTool, ToolExecutionError
from logai.providers.mcp.client import MCPClientManager, MCPToolError

if TYPE_CHECKING:
    from logai.providers.mcp.sanitization import ResultProcessor

logger = logging.getLogger(__name__)


class MCPToolAdapter(BaseTool):
    """
    Adapts an MCP server tool to the ``BaseTool`` interface.

    This allows MCP tools to be registered in ``ToolRegistry`` and
    dispatched by the orchestrator using the same code path as native
    tools.  The adapter:

    1. Delegates execution to ``MCPClientManager.call_tool()``.
    2. Passes the raw result through ``ResultProcessor`` (sanitization,
       format normalisation).
    3. Wraps all failures as ``ToolExecutionError`` so the orchestrator's
       error handling works unchanged.
    """

    def __init__(
        self,
        mcp_client: MCPClientManager,
        tool_name: str,
        tool_description: str,
        tool_parameters: dict[str, Any],
        result_processor: ResultProcessor | None = None,
    ) -> None:
        """
        Initialise the adapter.

        Args:
            mcp_client: Connected ``MCPClientManager`` used to dispatch calls.
            tool_name: Exact MCP tool name (e.g., ``"describe_log_groups"``).
            tool_description: Human-readable description from the MCP server.
            tool_parameters: JSON Schema parameter definition from the MCP server.
            result_processor: Optional post-processing pipeline (sanitization,
                               caching).  If ``None``, raw MCP results are
                               returned as-is.
        """
        self._mcp_client = mcp_client
        self._name = tool_name
        self._description = tool_description
        self._parameters = tool_parameters
        self._result_processor = result_processor

    # ------------------------------------------------------------------
    # BaseTool interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the MCP tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the MCP tool description."""
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        """Return the MCP tool parameter schema (JSON Schema format)."""
        return self._parameters

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the MCP tool and apply post-processing.

        Calls ``MCPClientManager.call_tool()``, then passes the raw result
        through ``ResultProcessor.process()`` if one was provided.  A
        ``"success": True`` key is injected into results that don't already
        contain it, for consistency with native tools.

        Args:
            **kwargs: Tool parameters as defined by the MCP tool's schema.

        Returns:
            Processed result dictionary.

        Raises:
            ToolExecutionError: If the MCP call fails or an unexpected error
                                occurs during execution or post-processing.
        """
        try:
            raw_result = await self._mcp_client.call_tool(self._name, kwargs)

            # Apply post-processing (sanitization, format normalisation).
            if self._result_processor is not None:
                result = await self._result_processor.process(self._name, raw_result)
            else:
                result = raw_result

            # Ensure a top-level "success" key is present for consistency
            # with native tool result dicts.
            if isinstance(result, dict) and "success" not in result:
                result["success"] = True

            return result

        except MCPToolError as exc:
            raise ToolExecutionError(
                message=str(exc),
                tool_name=self._name,
                # Only log argument *keys*, not values — values may contain
                # user-supplied strings that could include sensitive data.
                details={"source": "mcp", "argument_keys": list(kwargs.keys())},
            ) from exc
        except ToolExecutionError:
            # Re-raise ToolExecutionErrors from the processor as-is.
            raise
        except Exception as exc:
            raise ToolExecutionError(
                message=f"MCP tool execution failed: {exc}",
                tool_name=self._name,
                # Same rationale: keys are safe to log; values are not.
                details={"source": "mcp", "argument_keys": list(kwargs.keys())},
            ) from exc
