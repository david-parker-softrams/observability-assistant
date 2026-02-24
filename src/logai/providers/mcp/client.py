"""MCP client lifecycle management.

Manages the lifecycle of an MCP server subprocess and client session.
The MCP server communicates over stdio (stdin/stdout) using JSON-RPC.
"""

import json
import logging
import os
from typing import IO, Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPToolError(Exception):
    """Raised when an MCP tool invocation fails."""

    def __init__(self, tool_name: str, message: str) -> None:
        """
        Initialize MCP tool error.

        Args:
            tool_name: Name of the MCP tool that failed
            message: Error message from the MCP server
        """
        self.tool_name = tool_name
        super().__init__(f"MCP tool '{tool_name}' failed: {message}")


class MCPClientManager:
    """
    Manages the lifecycle of an MCP server subprocess and client session.

    The MCP server is a subprocess communicating over stdio (stdin/stdout)
    using JSON-RPC. This class handles:
    - Starting the server subprocess via ``StdioServerParameters``
    - Establishing a ``ClientSession``
    - Discovering available tools via tools/list (with caching)
    - Invoking tools via tools/call
    - Graceful shutdown

    Usage::

        client = MCPClientManager(command="uvx", args=["awslabs.cloudwatch-mcp-server@latest"])
        await client.start()
        try:
            tools = await client.list_tools()
            result = await client.call_tool("describe_log_groups", {})
        finally:
            await client.stop()
    """

    def __init__(
        self,
        command: str = "uvx",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        log_file_path: str | None = None,
    ) -> None:
        """
        Initialize the MCP client manager.

        Args:
            command: Executable used to launch the MCP server (e.g., ``"uvx"``).
            args: Arguments passed to the command
                  (e.g., ``["awslabs.cloudwatch-mcp-server@latest"]``).
                  Defaults to ``["awslabs.cloudwatch-mcp-server@latest"]``.
            env: Full environment for the subprocess. Should be built from
                 ``os.environ`` with AWS settings overlaid. Defaults to an
                 empty dict (i.e., inherits nothing — callers are expected to
                 supply the correct environment via ``build_mcp_env()``).
            log_file_path: Path to the application log file.  When provided and
                           openable, the MCP server's stderr is redirected there
                           (append mode) instead of the terminal, preventing TUI
                           corruption.  Falls back to ``os.devnull`` if ``None``
                           or the file cannot be opened.
        """
        self._command = command
        self._args = args or ["awslabs.cloudwatch-mcp-server@latest"]
        self._env = env or {}
        self._log_file_path = log_file_path
        self._session: ClientSession | None = None
        self._tools_cache: list[dict[str, Any]] | None = None

        # Context manager handles for the stdio transport — stored so we can
        # cleanly exit them in stop() without requiring a surrounding `async with`.
        # Typed as Any because the concrete CM types are private mcp-library internals.
        self._stdio_cm: Any = None
        self._session_cm: Any = None
        self._read_stream: Any = None
        self._write_stream: Any = None

        # File handle used to redirect MCP server stderr away from the terminal.
        # Opened in start() and closed in stop().
        self._stderr_log: IO[str] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the MCP server subprocess and initialize the session.

        Performs the full MCP handshake (``initialize`` request/response)
        so the client is ready to list and call tools immediately after this
        method returns.

        The MCP server's stderr is redirected to the application log file
        (passed as ``log_file_path`` to ``__init__``) so that subprocess
        output never reaches the terminal and corrupts the Textual TUI.
        If the log file cannot be opened, stderr is silently discarded via
        ``os.devnull``.

        Raises:
            Exception: If the subprocess cannot be started or the handshake
                       fails.  Callers should catch and fall back to native tools.
        """
        # ------------------------------------------------------------------
        # Open stderr redirect — must happen before stdio_client() is entered
        # so the file handle is available for cleanup if anything fails below.
        # ------------------------------------------------------------------
        if self._log_file_path is not None:
            try:
                self._stderr_log = open(  # noqa: SIM115
                    self._log_file_path, "a", encoding="utf-8"
                )
                logger.debug("MCP server stderr → %s", self._log_file_path)
            except OSError:
                logger.debug(
                    "Could not open log file '%s' for MCP stderr; discarding to devnull",
                    self._log_file_path,
                )
                self._stderr_log = open(os.devnull, "w")  # noqa: SIM115
        else:
            # No log file configured — discard stderr so it never hits the terminal.
            self._stderr_log = open(os.devnull, "w")  # noqa: SIM115

        try:
            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
            )

            # Enter the stdio_client context manager — this starts the subprocess
            # and returns async read/write streams over its stdin/stdout.
            # Pass our log file (or devnull) as errlog so stderr never hits the TUI.
            self._stdio_cm = stdio_client(server_params, errlog=self._stderr_log)
            self._read_stream, self._write_stream = await self._stdio_cm.__aenter__()

            # Enter the ClientSession context manager — establishes the JSON-RPC layer.
            self._session_cm = ClientSession(self._read_stream, self._write_stream)
            try:
                self._session = await self._session_cm.__aenter__()
            except Exception:
                # __aenter__ raised before the context manager was fully entered,
                # so we must NOT call __aexit__ on it in stop() — clear the ref now.
                self._session_cm = None
                raise

            # Perform the MCP initialization handshake.
            await self._session.initialize()

        except Exception:
            # If anything in start() fails after we opened the stderr log, close it
            # now so we don't leak the file descriptor.  stop() checks for None, so
            # this is safe even if stop() is later called by the caller's finally block.
            if self._stderr_log is not None:
                self._stderr_log.close()
                self._stderr_log = None
            raise

        logger.info(
            "MCP client session initialized (command=%s args=%s)",
            self._command,
            self._args,
        )

    async def stop(self) -> None:
        """Gracefully shut down the MCP session and server subprocess.

        Safe to call even if ``start()`` was never called or failed partway
        through — guards check for ``None`` before exiting each context manager.
        The stderr log file handle (if any) is always closed here.
        """
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                # Session teardown failure is operator-visible: use WARNING so
                # it surfaces in production logs even at the default log level.
                logger.warning("Error exiting MCP session context manager", exc_info=True)

        if self._stdio_cm is not None:
            try:
                await self._stdio_cm.__aexit__(None, None, None)
            except Exception:
                logger.debug("Error exiting MCP stdio context manager", exc_info=True)

        # Close the stderr redirect file handle now that the subprocess is gone.
        if self._stderr_log is not None:
            try:
                self._stderr_log.close()
            except OSError:
                logger.debug("Error closing MCP stderr log file handle", exc_info=True)
            finally:
                self._stderr_log = None

        self._session = None
        self._tools_cache = None
        # Clear stream and context-manager references so this instance cannot
        # accidentally be reused after stop() and so GC can collect them promptly.
        self._read_stream = None
        self._write_stream = None
        self._stdio_cm = None
        self._session_cm = None
        logger.info("MCP client session closed")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return True if the client session is active."""
        return self._session is not None

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover available tools from the MCP server.

        Converts MCP tool schemas to the OpenAI-compatible function calling
        format used by ``BaseTool.to_function_definition()``.  The result is
        cached after the first call — tools do not change at runtime.

        Returns:
            List of tool definition dicts, each with keys:
            ``name``, ``description``, ``parameters`` (JSON Schema object).

        Raises:
            RuntimeError: If the client has not been started yet.
        """
        if self._tools_cache is not None:
            return self._tools_cache

        if not self._session:
            raise RuntimeError("MCP client not connected. Call start() first.")

        result = await self._session.list_tools()

        tools: list[dict[str, Any]] = []
        for tool in result.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    # MCP tool input schemas are already JSON Schema objects.
                    "parameters": tool.inputSchema,
                }
            )

        self._tools_cache = tools
        logger.info(
            "Discovered %d MCP tools: %s",
            len(tools),
            [t["name"] for t in tools],
        )
        return tools

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke an MCP tool by name with the given arguments.

        MCP returns a ``CallToolResult`` containing a list of content blocks
        (``TextContent``, ``ImageContent``, etc.).  This method collects all
        text blocks, joins them, and attempts JSON parsing.  If the text is
        not valid JSON, it is returned as ``{"raw_text": <text>}``.

        Args:
            name: MCP tool name (e.g., ``"describe_log_groups"``).
            arguments: Tool arguments as a plain dictionary.

        Returns:
            Parsed tool result — a dict if JSON-parseable, otherwise
            ``{"raw_text": <raw response string>}``.

        Raises:
            RuntimeError: If the client has not been started.
            MCPToolError: If the MCP server signals an error for this tool call.
        """
        if not self._session:
            raise RuntimeError("MCP client not connected. Call start() first.")

        result = await self._session.call_tool(name, arguments)

        if result.isError:
            # Collect error text from all content blocks.
            error_parts: list[str] = []
            for content_block in result.content:
                if hasattr(content_block, "text"):
                    error_parts.append(content_block.text)
            raise MCPToolError(name, "\n".join(error_parts))

        # Collect text content from all blocks.
        text_parts: list[str] = []
        for content_block in result.content:
            if hasattr(content_block, "text"):
                text_parts.append(content_block.text)

        combined_text = "\n".join(text_parts)

        # Attempt JSON parsing; fall back to a raw-text wrapper.
        try:
            return json.loads(combined_text)
        except json.JSONDecodeError:
            return {"raw_text": combined_text}
