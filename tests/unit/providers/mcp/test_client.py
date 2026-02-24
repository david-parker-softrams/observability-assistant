"""Unit tests for MCPClientManager."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from logai.providers.mcp.client import MCPClientManager, MCPToolError

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_text_block(text: str) -> MagicMock:
    """Return a mock content block that carries a ``.text`` attribute."""
    block = MagicMock()
    block.text = text
    return block


def _make_call_result(text: str, is_error: bool = False) -> MagicMock:
    """Return a mock ``CallToolResult``."""
    result = MagicMock()
    result.isError = is_error
    result.content = [_make_text_block(text)]
    return result


def _make_list_tools_result(tools: list[dict]) -> MagicMock:
    """Return a mock ``ListToolsResult`` from a list of dicts."""
    result = MagicMock()
    tool_mocks = []
    for t in tools:
        tool = MagicMock()
        tool.name = t["name"]
        tool.description = t.get("description", "")
        tool.inputSchema = t.get("inputSchema", {"type": "object", "properties": {}})
        tool_mocks.append(tool)
    result.tools = tool_mocks
    return result


@pytest.fixture
def manager() -> MCPClientManager:
    """Return a fresh, unstarted MCPClientManager."""
    return MCPClientManager(command="uvx", args=["test-server"], env={})


@pytest.fixture
def connected_manager(manager: MCPClientManager) -> MCPClientManager:
    """Return an MCPClientManager with a mocked session injected."""
    mock_session = AsyncMock()
    manager._session = mock_session
    return manager


# ---------------------------------------------------------------------------
# Lifecycle / property tests
# ---------------------------------------------------------------------------


class TestMCPClientManagerLifecycle:
    """Tests for MCPClientManager connection state and lifecycle."""

    def test_is_connected_false_before_start(self, manager: MCPClientManager) -> None:
        """A new instance should report is_connected=False."""
        assert manager.is_connected is False

    def test_is_connected_true_after_session_injected(
        self, connected_manager: MCPClientManager
    ) -> None:
        """is_connected should be True once a session is present."""
        assert connected_manager.is_connected is True

    @pytest.mark.asyncio
    async def test_stop_safe_when_not_started(self, manager: MCPClientManager) -> None:
        """stop() on a fresh (never-started) instance must not raise."""
        # Should complete without any exception
        await manager.stop()
        # After stop(), session and cache cleared
        assert manager._session is None
        assert manager._tools_cache is None


# ---------------------------------------------------------------------------
# list_tools tests
# ---------------------------------------------------------------------------


class TestMCPClientManagerListTools:
    """Tests for MCPClientManager.list_tools()."""

    @pytest.mark.asyncio
    async def test_list_tools_raises_when_not_connected(self, manager: MCPClientManager) -> None:
        """list_tools() without start() must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await manager.list_tools()

    @pytest.mark.asyncio
    async def test_list_tools_converts_to_openai_format(
        self, connected_manager: MCPClientManager
    ) -> None:
        """list_tools() must return dicts with name/description/parameters keys."""
        raw_tools = [
            {
                "name": "describe_log_groups",
                "description": "Lists CloudWatch log groups",
                "inputSchema": {
                    "type": "object",
                    "properties": {"prefix": {"type": "string"}},
                },
            },
            {
                "name": "get_metric_data",
                "description": "Fetches CloudWatch metrics",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        connected_manager._session.list_tools = AsyncMock(
            return_value=_make_list_tools_result(raw_tools)
        )

        tools = await connected_manager.list_tools()

        assert len(tools) == 2
        for tool, expected in zip(tools, raw_tools, strict=False):
            assert tool["name"] == expected["name"]
            assert tool["description"] == expected["description"]
            assert tool["parameters"] == expected["inputSchema"]

    @pytest.mark.asyncio
    async def test_list_tools_caches_result(self, connected_manager: MCPClientManager) -> None:
        """Calling list_tools() twice must only hit the session once."""
        raw_tools = [
            {
                "name": "describe_log_groups",
                "description": "desc",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        connected_manager._session.list_tools = AsyncMock(
            return_value=_make_list_tools_result(raw_tools)
        )

        first = await connected_manager.list_tools()
        second = await connected_manager.list_tools()

        # Both calls should return the same data
        assert first == second
        # But the underlying session method was only called once
        connected_manager._session.list_tools.assert_called_once()


# ---------------------------------------------------------------------------
# call_tool tests
# ---------------------------------------------------------------------------


class TestMCPClientManagerCallTool:
    """Tests for MCPClientManager.call_tool()."""

    @pytest.mark.asyncio
    async def test_call_tool_raises_when_not_connected(self, manager: MCPClientManager) -> None:
        """call_tool() without start() must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            await manager.call_tool("describe_log_groups", {})

    @pytest.mark.asyncio
    async def test_call_tool_returns_parsed_json(self, connected_manager: MCPClientManager) -> None:
        """If the MCP response is valid JSON, call_tool() returns a parsed dict."""
        payload = {"logGroups": ["/aws/lambda/fn"], "count": 1}
        connected_manager._session.call_tool = AsyncMock(
            return_value=_make_call_result(json.dumps(payload))
        )

        result = await connected_manager.call_tool("describe_log_groups", {})

        assert result == payload

    @pytest.mark.asyncio
    async def test_call_tool_returns_raw_text_on_non_json(
        self, connected_manager: MCPClientManager
    ) -> None:
        """If the MCP response is not valid JSON, result is wrapped in raw_text."""
        connected_manager._session.call_tool = AsyncMock(
            return_value=_make_call_result("plain text response, not JSON")
        )

        result = await connected_manager.call_tool("some_tool", {})

        assert "raw_text" in result
        assert result["raw_text"] == "plain text response, not JSON"

    @pytest.mark.asyncio
    async def test_call_tool_raises_mcp_tool_error_on_failure(
        self, connected_manager: MCPClientManager
    ) -> None:
        """If the MCP server signals isError=True, MCPToolError is raised."""
        connected_manager._session.call_tool = AsyncMock(
            return_value=_make_call_result("Something went wrong", is_error=True)
        )

        with pytest.raises(MCPToolError) as exc_info:
            await connected_manager.call_tool("bad_tool", {"arg": "val"})

        exc = exc_info.value
        assert exc.tool_name == "bad_tool"
        assert "bad_tool" in str(exc)

    @pytest.mark.asyncio
    async def test_call_tool_passes_arguments_to_session(
        self, connected_manager: MCPClientManager
    ) -> None:
        """call_tool() forwards tool name and arguments to the session."""
        connected_manager._session.call_tool = AsyncMock(
            return_value=_make_call_result('{"ok": true}')
        )
        args = {"logGroupName": "/aws/test", "limit": 10}

        await connected_manager.call_tool("describe_log_groups", args)

        connected_manager._session.call_tool.assert_called_once_with("describe_log_groups", args)


# ---------------------------------------------------------------------------
# MCPToolError message format (Gap #15)
# ---------------------------------------------------------------------------


class TestMCPToolErrorMessageFormat:
    """Tests for MCPToolError string representation and attributes."""

    def test_mcp_tool_error_message_format(self) -> None:
        """str(MCPToolError) must follow the canonical 'MCP tool … failed: …' pattern."""
        err = MCPToolError("describe_log_groups", "timeout after 30s")

        assert str(err) == "MCP tool 'describe_log_groups' failed: timeout after 30s"
        assert err.tool_name == "describe_log_groups"

    def test_mcp_tool_error_is_exception(self) -> None:
        """MCPToolError must be a subclass of Exception and be raise-able."""
        with pytest.raises(MCPToolError):
            raise MCPToolError("some_tool", "something went wrong")

    def test_mcp_tool_error_preserves_tool_name_with_special_chars(self) -> None:
        """tool_name containing hyphens / underscores must round-trip through str()."""
        err = MCPToolError("get-logs_insight-query_results", "rate limited")

        assert err.tool_name == "get-logs_insight-query_results"
        assert "get-logs_insight-query_results" in str(err)


# ---------------------------------------------------------------------------
# start() / stop() lifecycle tests — full subprocess mocking (Gap #5)
# ---------------------------------------------------------------------------


def _make_stdio_cm(mock_read: MagicMock, mock_write: MagicMock) -> MagicMock:
    """
    Build a mock that behaves like the async context manager returned by
    ``stdio_client(server_params)``.

    ``__aenter__`` returns the ``(read, write)`` stream pair;
    ``__aexit__`` is a no-op coroutine.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_session_cm(mock_session: MagicMock) -> MagicMock:
    """
    Build a mock that behaves like the async context manager returned by
    ``ClientSession(read, write)``.

    ``__aenter__`` returns ``mock_session``;
    ``__aexit__`` is a no-op coroutine.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestMCPClientManagerStartStop:
    """Full start()/stop() lifecycle tests using patched stdio_client / ClientSession."""

    @pytest.mark.asyncio
    async def test_start_sets_is_connected_true(self, manager: MCPClientManager) -> None:
        """After a successful start(), is_connected must be True."""
        mock_read, mock_write = MagicMock(), MagicMock()
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock(return_value=None)

        stdio_cm = _make_stdio_cm(mock_read, mock_write)
        session_cm = _make_session_cm(mock_session)

        with patch("logai.providers.mcp.client.stdio_client", return_value=stdio_cm):
            with patch("logai.providers.mcp.client.ClientSession", return_value=session_cm):
                await manager.start()

        assert manager.is_connected is True

    @pytest.mark.asyncio
    async def test_stop_clears_session(self, manager: MCPClientManager) -> None:
        """stop() after a successful start() must leave is_connected=False and _session=None."""
        mock_read, mock_write = MagicMock(), MagicMock()
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock(return_value=None)

        stdio_cm = _make_stdio_cm(mock_read, mock_write)
        session_cm = _make_session_cm(mock_session)

        with patch("logai.providers.mcp.client.stdio_client", return_value=stdio_cm):
            with patch("logai.providers.mcp.client.ClientSession", return_value=session_cm):
                await manager.start()

        assert manager.is_connected is True

        await manager.stop()

        assert manager.is_connected is False
        assert manager._session is None

    @pytest.mark.asyncio
    async def test_start_cleans_up_on_session_aenter_failure(
        self, manager: MCPClientManager
    ) -> None:
        """
        If ClientSession.__aenter__ raises, start() must:
        - re-raise the exception
        - clear _session_cm (so stop() does not attempt __aexit__ on it)
        - leave is_connected=False
        """
        mock_read, mock_write = MagicMock(), MagicMock()
        stdio_cm = _make_stdio_cm(mock_read, mock_write)

        # Failing session CM: __aenter__ raises before fully entering
        failing_session_cm = MagicMock()
        failing_session_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("session init failed"))
        failing_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("logai.providers.mcp.client.stdio_client", return_value=stdio_cm):
            with patch(
                "logai.providers.mcp.client.ClientSession",
                return_value=failing_session_cm,
            ):
                with pytest.raises(RuntimeError, match="session init failed"):
                    await manager.start()

        # Critical #2 fix: _session_cm must have been cleared on failure
        assert manager._session_cm is None
        # is_connected must remain False
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, manager: MCPClientManager) -> None:
        """Calling stop() twice on a never-started manager must not raise."""
        await manager.stop()  # first call
        await manager.stop()  # second call — must also succeed silently

        assert manager._session is None

    @pytest.mark.asyncio
    async def test_stop_nulls_all_stream_references(self, manager: MCPClientManager) -> None:
        """
        stop() must set _read_stream, _write_stream, _stdio_cm, and _session_cm
        all to None (Minor #10 fix — prevents accidental reuse after shutdown).
        """
        mock_read, mock_write = MagicMock(), MagicMock()
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock(return_value=None)

        stdio_cm = _make_stdio_cm(mock_read, mock_write)
        session_cm = _make_session_cm(mock_session)

        with patch("logai.providers.mcp.client.stdio_client", return_value=stdio_cm):
            with patch("logai.providers.mcp.client.ClientSession", return_value=session_cm):
                await manager.start()

        # Confirm references are populated after start
        assert manager._read_stream is not None
        assert manager._write_stream is not None
        assert manager._stdio_cm is not None
        assert manager._session_cm is not None

        await manager.stop()

        # All four references must be cleared
        assert manager._read_stream is None
        assert manager._write_stream is None
        assert manager._stdio_cm is None
        assert manager._session_cm is None
