"""Base classes for LLM tools/functions."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """
    Abstract base class for all LLM tools.

    Tools are functions that the LLM can call to interact with external systems
    (e.g., fetching logs from CloudWatch, analyzing data, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name (used by LLM to reference it)."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description (helps LLM understand when to use it)."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """
        Return the tool parameters schema in JSON Schema format.

        Example:
            {
                "type": "object",
                "properties": {
                    "log_group": {
                        "type": "string",
                        "description": "CloudWatch log group name"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO 8601 or relative like '1h ago')"
                    }
                },
                "required": ["log_group", "start_time"]
            }
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters as defined in the schema

        Returns:
            Dictionary with tool execution results

        Raises:
            ToolExecutionError: If tool execution fails
        """
        pass

    def to_function_definition(self) -> dict[str, Any]:
        """
        Convert tool to LLM function definition format.

        Returns a dictionary compatible with LiteLLM/OpenAI/Anthropic function calling.

        Returns:
            Function definition dictionary for LLM
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""

    def __init__(self, message: str, tool_name: str, details: dict[str, Any] | None = None):
        """
        Initialize tool execution error.

        Args:
            message: Error message
            tool_name: Name of the tool that failed
            details: Optional additional error details
        """
        self.message = message
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(f"Tool '{tool_name}' execution failed: {message}")
