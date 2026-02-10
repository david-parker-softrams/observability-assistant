"""Tool registry for managing available LLM tools."""

from typing import Any

from .base import BaseTool, ToolExecutionError


class ToolRegistry:
    """
    Registry for managing available LLM tools.

    Tools can be registered and retrieved by name, and the registry provides
    a unified interface for tool execution and function definition export.
    """

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in cls._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. Each tool must have a unique name."
            )
        cls._tools[tool.name] = tool

    @classmethod
    def unregister(cls, tool_name: str) -> None:
        """
        Unregister a tool from the registry.

        Args:
            tool_name: Name of the tool to unregister
        """
        cls._tools.pop(tool_name, None)

    @classmethod
    def get(cls, tool_name: str) -> BaseTool | None:
        """
        Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return cls._tools.get(tool_name)

    @classmethod
    def get_all(cls) -> list[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all registered tool instances
        """
        return list(cls._tools.values())

    @classmethod
    def to_function_definitions(cls) -> list[dict[str, Any]]:
        """
        Get function definitions for all registered tools.

        Returns a list of function definitions compatible with LLM function calling.

        Returns:
            List of function definitions
        """
        return [tool.to_function_definition() for tool in cls._tools.values()]

    @classmethod
    async def execute(cls, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Tool execution results

        Raises:
            ToolExecutionError: If tool not found or execution fails
        """
        tool = cls.get(tool_name)
        if tool is None:
            raise ToolExecutionError(
                message=f"Tool '{tool_name}' not found in registry",
                tool_name=tool_name,
                details={"available_tools": list(cls._tools.keys())},
            )

        try:
            return await tool.execute(**kwargs)
        except ToolExecutionError:
            # Re-raise tool execution errors as-is
            raise
        except Exception as e:
            # Wrap other exceptions in ToolExecutionError
            raise ToolExecutionError(
                message=str(e),
                tool_name=tool_name,
                details={"exception_type": type(e).__name__},
            ) from e

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools (useful for testing)."""
        cls._tools.clear()
