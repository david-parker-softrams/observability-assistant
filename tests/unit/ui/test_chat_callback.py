"""Unit tests for chat screen callback pattern with log preview modal."""

import json
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, PropertyMock, call, patch

import pytest
from logai.ui.screens.chat import ChatScreen


class TestCallbackPattern:
    """Test the callback pattern for modal results."""

    @pytest.mark.asyncio
    async def test_callback_is_defined_in_handler(self):
        """Verify that the callback function is defined when handling preview request."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        # Mock the app using patch
        mock_app = MagicMock()
        mock_app.push_screen = MagicMock()

        # Create a mock tool with datasource
        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()

        # Mock the orchestrator's tool registry
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        # Create the event
        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        # Handle the event with patched app
        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Verify push_screen was called with 2 arguments (screen, callback)
        mock_app.push_screen.assert_called_once()
        call_args = mock_app.push_screen.call_args
        assert len(call_args[0]) == 2, "push_screen should be called with screen and callback"

        # Verify the second argument is a callable
        callback = call_args[0][1]
        assert callable(callback), "Second argument should be a callback function"

    @pytest.mark.asyncio
    async def test_callback_receives_result_dict(self):
        """Test that callback receives result dictionary when modal dismisses."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        # Mock _inject_log_entries_to_context
        chat_screen._inject_log_entries_to_context = AsyncMock()

        # Create test result
        test_result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045123, "message": "Test log 1"},
                {"timestamp": 1708263046456, "message": "Test log 2"},
            ],
        }

        # Mock the app
        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        # Create a mock tool with datasource
        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        # Create the event
        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        # Handle the event to capture callback
        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Verify callback was captured
        assert callback_func is not None, "Callback should be captured"

        # Now call the callback with result
        await callback_func(test_result)

        # Verify _inject_log_entries_to_context was called with correct result
        chat_screen._inject_log_entries_to_context.assert_called_once_with(test_result)

    @pytest.mark.asyncio
    async def test_callback_handles_none_result(self):
        """Test that callback handles None result (user cancelled)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        # Mock _inject_log_entries_to_context
        chat_screen._inject_log_entries_to_context = AsyncMock()

        # Mock the app
        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        # Create a mock tool with datasource
        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        # Create the event
        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        # Handle the event to capture callback
        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Call callback with None (user cancelled)
        await callback_func(None)

        # Verify _inject_log_entries_to_context was NOT called
        chat_screen._inject_log_entries_to_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_handles_empty_dict(self):
        """Test that callback handles empty dict (no selections)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        # Mock _inject_log_entries_to_context
        chat_screen._inject_log_entries_to_context = AsyncMock()

        # Mock the app
        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        # Create a mock tool with datasource
        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        # Create the event
        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        # Handle the event to capture callback
        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Call callback with empty dict
        await callback_func({})

        # Empty dict is falsy, so _inject should NOT be called
        chat_screen._inject_log_entries_to_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_name_is_handle_log_selection(self):
        """Verify callback function has descriptive name."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        # Mock the app
        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        # Create a mock tool with datasource
        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        # Create the event
        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        # Handle the event to capture callback
        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Verify callback has descriptive name
        assert callback_func.__name__ == "handle_log_selection"


class TestCallbackDataFlow:
    """Test data flow from modal through callback to context injection."""

    def _setup_chat_screen_with_callback(self, orchestrator, cache_manager):
        """Helper to setup chat screen and capture callback."""
        chat_screen = ChatScreen(orchestrator, cache_manager)
        chat_screen._inject_log_entries_to_context = AsyncMock()

        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        return chat_screen, mock_app, lambda: callback_func

    @pytest.mark.asyncio
    async def test_callback_with_single_entry(self):
        """Test callback correctly processes a single log entry."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045123, "message": "Single log entry"},
            ],
        }

        await get_callback()(result)
        chat_screen._inject_log_entries_to_context.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_callback_with_ten_entries(self):
        """Test callback correctly processes 10 log entries."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045000 + i, "message": f"Log entry {i}"} for i in range(10)
            ],
        }

        await get_callback()(result)
        chat_screen._inject_log_entries_to_context.assert_called_once_with(result)
        call_arg = chat_screen._inject_log_entries_to_context.call_args[0][0]
        assert len(call_arg["selected_entries"]) == 10

    @pytest.mark.asyncio
    async def test_callback_with_hundred_entries(self):
        """Test callback correctly processes 100 log entries."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045000 + i, "message": f"Log entry {i}"} for i in range(100)
            ],
        }

        await get_callback()(result)
        chat_screen._inject_log_entries_to_context.assert_called_once_with(result)
        call_arg = chat_screen._inject_log_entries_to_context.call_args[0][0]
        assert len(call_arg["selected_entries"]) == 100

    @pytest.mark.asyncio
    async def test_callback_preserves_log_group_name(self):
        """Test that log_group_name is preserved through callback."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/my-special-function")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/my-special-function",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        await get_callback()(result)
        call_arg = chat_screen._inject_log_entries_to_context.call_args[0][0]
        assert call_arg["log_group_name"] == "/aws/lambda/my-special-function"

    @pytest.mark.asyncio
    async def test_callback_preserves_entry_structure(self):
        """Test that entry structure is preserved through callback."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {
                    "timestamp": 1708263045123,
                    "message": "Complex log entry",
                    "log_stream": "2024/01/15/[$LATEST]abc123",
                    "event_id": "event-001",
                },
            ],
        }

        await get_callback()(result)
        call_arg = chat_screen._inject_log_entries_to_context.call_args[0][0]
        entry = call_arg["selected_entries"][0]
        assert entry["timestamp"] == 1708263045123
        assert entry["message"] == "Complex log entry"
        assert entry["log_stream"] == "2024/01/15/[$LATEST]abc123"
        assert entry["event_id"] == "event-001"


class TestCallbackEdgeCases:
    """Test edge cases and error conditions for the callback pattern."""

    def _setup_chat_screen_with_callback(self, orchestrator, cache_manager):
        """Helper to setup chat screen and capture callback."""
        chat_screen = ChatScreen(orchestrator, cache_manager)
        chat_screen._inject_log_entries_to_context = AsyncMock()

        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        return chat_screen, mock_app, lambda: callback_func

    @pytest.mark.asyncio
    async def test_callback_with_zero_entries_selected(self):
        """Test callback when modal dismisses with 0 entries selected."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [],
        }

        await get_callback()(result)
        # Empty list is truthy dict, so injection SHOULD be called
        chat_screen._inject_log_entries_to_context.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_callback_with_missing_log_group_name_key(self):
        """Test callback behavior when result dict is missing log_group_name."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        async def inject_with_error(result):
            _ = result["log_group_name"]  # Will raise KeyError

        chat_screen._inject_log_entries_to_context = AsyncMock(side_effect=inject_with_error)

        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        with pytest.raises(KeyError):
            await callback_func(result)

    @pytest.mark.asyncio
    async def test_callback_with_false_value(self):
        """Test callback with False value (should not call inject)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        await get_callback()(False)
        chat_screen._inject_log_entries_to_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_with_zero_value(self):
        """Test callback with 0 value (should not call inject)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        await get_callback()(0)
        chat_screen._inject_log_entries_to_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_with_empty_string(self):
        """Test callback with empty string (should not call inject)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen, mock_app, get_callback = self._setup_chat_screen_with_callback(
            orchestrator, cache_manager
        )

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        await get_callback()("")
        chat_screen._inject_log_entries_to_context.assert_not_called()


class TestCallbackErrorHandling:
    """Test error handling in callback pattern."""

    @pytest.mark.asyncio
    async def test_inject_method_exception_is_caught(self):
        """Test that exceptions in _inject_log_entries_to_context are handled."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen._inject_log_entries_to_context = AsyncMock(
            side_effect=Exception("Injection failed")
        )

        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        with pytest.raises(Exception, match="Injection failed"):
            await callback_func(result)

    @pytest.mark.asyncio
    async def test_callback_logs_received_result(self):
        """Test that callback logs the result it receives."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen._inject_log_entries_to_context = AsyncMock()

        mock_app = MagicMock()
        callback_func = None

        def capture_callback(screen, callback):
            nonlocal callback_func
            callback_func = callback

        mock_app.push_screen = capture_callback

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        with patch("logai.ui.screens.chat.logger") as mock_logger:
            await callback_func(result)
            assert mock_logger.debug.called
            log_calls = [str(call) for call in mock_logger.debug.call_args_list]
            assert any(
                "Injecting" in str(call) and "log entries" in str(call) for call in log_calls
            )


class TestInjectLogEntriesToContext:
    """Test the _inject_log_entries_to_context method that callback invokes."""

    @pytest.mark.asyncio
    async def test_inject_extracts_log_group_name(self):
        """Test that inject method extracts log_group_name from result."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        result = {
            "log_group_name": "/aws/lambda/my-function",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        await chat_screen._inject_log_entries_to_context(result)

        chat_screen.orchestrator.inject_context_update.assert_called_once()
        context_message = chat_screen.orchestrator.inject_context_update.call_args[0][0]
        assert "/aws/lambda/my-function" in context_message

    @pytest.mark.asyncio
    async def test_inject_extracts_selected_entries(self):
        """Test that inject method extracts selected_entries from result."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045123, "message": "Entry 1"},
                {"timestamp": 1708263046456, "message": "Entry 2"},
                {"timestamp": 1708263047789, "message": "Entry 3"},
            ],
        }

        await chat_screen._inject_log_entries_to_context(result)

        chat_screen.orchestrator.inject_context_update.assert_called_once()
        context_message = chat_screen.orchestrator.inject_context_update.call_args[0][0]
        assert "Entry 1" in context_message
        assert "Entry 2" in context_message
        assert "Entry 3" in context_message

    @pytest.mark.asyncio
    async def test_inject_formats_entries_as_json(self):
        """Test that inject method formats entries as JSON."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        await chat_screen._inject_log_entries_to_context(result)

        context_message = chat_screen.orchestrator.inject_context_update.call_args[0][0]
        assert "```json" in context_message
        assert "```" in context_message

    @pytest.mark.asyncio
    async def test_inject_shows_system_message_for_single_entry(self):
        """Test that inject shows 'entry' (singular) for 1 entry."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        mock_container = MagicMock()
        chat_screen.query_one = MagicMock(return_value=mock_container)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Single entry"}],
        }

        await chat_screen._inject_log_entries_to_context(result)

        mock_container.mount.assert_called_once()
        # SystemMessage is created with the text passed to __init__
        # Check the call args for the SystemMessage
        system_msg_call = mock_container.mount.call_args[0][0]
        # SystemMessage inherits from Static which stores content internally
        # We need to check the initial render content
        # Access the SystemMessage content via _Static__content
        content = system_msg_call._Static__content
        assert "1 log entry" in str(content)

    @pytest.mark.asyncio
    async def test_inject_shows_system_message_for_multiple_entries(self):
        """Test that inject shows 'entries' (plural) for multiple entries."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        mock_container = MagicMock()
        chat_screen.query_one = MagicMock(return_value=mock_container)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {"timestamp": 1708263045000 + i, "message": f"Entry {i}"} for i in range(3)
            ],
        }

        await chat_screen._inject_log_entries_to_context(result)

        mock_container.mount.assert_called_once()
        system_msg_call = mock_container.mount.call_args[0][0]
        content = system_msg_call._Static__content
        assert "3 log entries" in str(content)

    @pytest.mark.asyncio
    async def test_inject_handles_exception_gracefully(self):
        """Test that inject handles exceptions and shows error notification."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock(
            side_effect=Exception("Context update failed")
        )
        chat_screen.notify = MagicMock()

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        await chat_screen._inject_log_entries_to_context(result)

        chat_screen.notify.assert_called_once()
        notification_args = chat_screen.notify.call_args
        assert "Failed to add logs to context" in notification_args[0][0]
        assert notification_args[1]["severity"] == "error"

    @pytest.mark.asyncio
    async def test_inject_with_zero_entries(self):
        """Test inject behavior with zero entries."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock()
        mock_container = MagicMock()
        chat_screen.query_one = MagicMock(return_value=mock_container)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [],
        }

        await chat_screen._inject_log_entries_to_context(result)

        chat_screen.orchestrator.inject_context_update.assert_called_once()

        mock_container.mount.assert_called_once()
        system_msg_call = mock_container.mount.call_args[0][0]
        content = system_msg_call._Static__content
        assert "0 log entries" in str(content)
