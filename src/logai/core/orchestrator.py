"""LLM Orchestrator - coordinates LLM interactions with tool execution."""

import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.providers.llm.base import BaseLLMProvider, LLMProviderError


class OrchestratorError(Exception):
    """Raised when orchestrator encounters an error."""

    pass


class LLMOrchestrator:
    """
    Coordinates LLM interactions with tool execution.

    The orchestrator is the heart of the system - it manages the conversation
    loop, executes tool calls, and handles the back-and-forth between the LLM
    and external systems.
    """

    MAX_TOOL_ITERATIONS = 10  # Prevent infinite loops

    # System prompt template
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
Available log groups will be discovered via tools.
"""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        sanitizer: LogSanitizer,
        settings: LogAISettings,
        cache: CacheManager | None = None,
    ):
        """
        Initialize LLM orchestrator.

        Args:
            llm_provider: LLM provider instance
            tool_registry: Tool registry with available tools
            sanitizer: PII sanitizer instance
            settings: Application settings
            cache: Optional cache manager
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.sanitizer = sanitizer
        self.settings = settings
        self.cache = cache
        self.conversation_history: list[dict[str, Any]] = []

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt with current context.

        Returns:
            Formatted system prompt
        """
        now = datetime.now(timezone.utc)
        return self.SYSTEM_PROMPT.format(
            current_time=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    async def chat(
        self,
        user_message: str,
        stream: bool = False,
    ) -> str:
        """
        Process a user message through the LLM with tool execution.

        Args:
            user_message: User's message/query
            stream: Whether to stream the response (currently not supported in this method,
                   use chat_stream() instead for streaming)

        Returns:
            Final response text

        Raises:
            OrchestratorError: If orchestration fails
        """
        return await self._chat_complete(user_message)

    async def chat_stream(
        self,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and stream the response.

        Args:
            user_message: User's message/query

        Yields:
            Response tokens

        Raises:
            OrchestratorError: If orchestration fails
        """
        async for token in self._chat_stream(user_message):
            yield token

    async def _chat_complete(self, user_message: str) -> str:
        """
        Process message and return complete response.

        Args:
            user_message: User's message

        Returns:
            Complete response text
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages with system prompt
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ] + self.conversation_history

        # Get available tools
        tools = self.tool_registry.to_function_definitions()

        # Execute conversation loop with tool calling
        iteration = 0
        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1

            try:
                # Get LLM response
                response = await self.llm_provider.chat(
                    messages=messages, tools=tools, stream=False
                )

                # Check if LLM wants to use tools
                if response.has_tool_calls():
                    # Execute tool calls
                    tool_results = await self._execute_tool_calls(response.tool_calls)

                    # Add assistant message with tool calls to history
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls,
                    }
                    self.conversation_history.append(assistant_message)
                    messages.append(assistant_message)

                    # Add tool results as separate messages
                    for tool_result in tool_results:
                        tool_message: dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "content": json.dumps(tool_result["result"]),
                        }
                        self.conversation_history.append(tool_message)
                        messages.append(tool_message)

                    # Continue loop - LLM will process tool results
                    continue

                # No tool calls - we have the final response
                if response.content:
                    self.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )
                    return response.content
                else:
                    # Empty response, shouldn't happen but handle gracefully
                    error_msg = "Received empty response from LLM"
                    self.conversation_history.append({"role": "assistant", "content": error_msg})
                    return error_msg

            except LLMProviderError as e:
                raise OrchestratorError(f"LLM provider error: {str(e)}") from e
            except Exception as e:
                raise OrchestratorError(f"Unexpected error during orchestration: {str(e)}") from e

        # Hit max iterations - likely infinite loop
        error_msg = f"Maximum tool iterations ({self.MAX_TOOL_ITERATIONS}) exceeded. The conversation may be stuck in a loop."
        self.conversation_history.append({"role": "assistant", "content": error_msg})
        return error_msg

    async def _chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Process message and stream the response.

        Note: For MVP, we'll handle tool calls in non-streaming mode,
        then stream the final response. Full streaming with tool calls
        is complex and can be added post-MVP.

        Args:
            user_message: User's message

        Yields:
            Response tokens
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages with system prompt
        messages = [
            {"role": "system", "content": self._get_system_prompt()}
        ] + self.conversation_history

        # Get available tools
        tools = self.tool_registry.to_function_definitions()

        # Execute conversation loop with tool calling (non-streaming)
        iteration = 0
        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1

            try:
                # Get LLM response (non-streaming for tool call handling)
                response = await self.llm_provider.chat(
                    messages=messages, tools=tools, stream=False
                )

                # Check if LLM wants to use tools
                if response.has_tool_calls():
                    # Execute tool calls
                    tool_results = await self._execute_tool_calls(response.tool_calls)

                    # Add assistant message with tool calls to history
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls,
                    }
                    self.conversation_history.append(assistant_message)
                    messages.append(assistant_message)

                    # Add tool results as separate messages
                    for tool_result in tool_results:
                        tool_message: dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "content": json.dumps(tool_result["result"]),
                        }
                        self.conversation_history.append(tool_message)
                        messages.append(tool_message)

                    # Continue loop - LLM will process tool results
                    continue

                # No tool calls - stream the final response
                if response.content:
                    self.conversation_history.append(
                        {"role": "assistant", "content": response.content}
                    )
                    # TODO: Real streaming with tool calls is complex. For MVP, we're "simulating" streaming
                    # by yielding the full response character-by-character. This gives the UI a streaming
                    # effect but doesn't reduce latency for the first token.
                    # Post-MVP: Implement true streaming with incremental tool calling.
                    for char in response.content:
                        yield char
                    return
                else:
                    error_msg = "Received empty response from LLM"
                    self.conversation_history.append({"role": "assistant", "content": error_msg})
                    yield error_msg
                    return

            except LLMProviderError as e:
                error_msg = f"LLM provider error: {str(e)}"
                yield error_msg
                return
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                yield error_msg
                return

        # Hit max iterations
        error_msg = f"Maximum tool iterations ({self.MAX_TOOL_ITERATIONS}) exceeded."
        self.conversation_history.append({"role": "assistant", "content": error_msg})
        yield error_msg

    async def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool call requests from LLM

        Returns:
            List of tool results with tool_call_id and result
        """
        results = []

        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id", "unknown")
            function_info = tool_call.get("function", {})
            function_name = function_info.get("name")
            function_args_str = function_info.get("arguments", "{}")

            try:
                # Parse arguments
                if isinstance(function_args_str, str):
                    function_args = json.loads(function_args_str)
                else:
                    function_args = function_args_str

                # Execute tool
                result = await self.tool_registry.execute(function_name, **function_args)

                results.append({"tool_call_id": tool_call_id, "result": result})

            except json.JSONDecodeError as e:
                # Invalid JSON arguments
                results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": False,
                            "error": f"Failed to parse tool arguments: {str(e)}",
                        },
                    }
                )
            except Exception as e:
                # Tool execution failed
                results.append(
                    {
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": False,
                            "error": f"Tool execution failed: {str(e)}",
                        },
                    }
                )

        return results

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """
        Get conversation history.

        Returns:
            List of message dictionaries
        """
        return self.conversation_history.copy()
