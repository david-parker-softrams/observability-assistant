"""Integration tests for context modal callback flow end-to-end."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from logai.ui.screens.chat import ChatScreen
from logai.ui.screens.log_preview import LogPreviewScreen


class TestModalCallbackIntegration:
    """Integration tests for modal-to-callback flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_modal_to_context_flow(self):
        """Test complete flow from modal open to context injection."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_tool = MagicMock()
        mock_datasource = AsyncMock()
        mock_tool.datasource = mock_datasource
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        registered_callback = None

        def capture_push_screen(screen, callback):
            nonlocal registered_callback
            registered_callback = callback
            assert isinstance(screen, LogPreviewScreen)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        assert registered_callback is not None
        assert callable(registered_callback)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {
                    "timestamp": 1708263045123,
                    "message": "ERROR: Database connection failed",
                    "log_stream": "2024/01/15/[$LATEST]abc123",
                },
                {
                    "timestamp": 1708263046456,
                    "message": "ERROR: Retry attempt failed",
                    "log_stream": "2024/01/15/[$LATEST]abc123",
                },
            ],
        }

        await registered_callback(result)

        chat_screen.orchestrator.inject_context_update.assert_called_once()
        context_message = chat_screen.orchestrator.inject_context_update.call_args[0][0]

        assert "/aws/lambda/test" in context_message
        assert "ERROR: Database connection failed" in context_message
        assert "ERROR: Retry attempt failed" in context_message

    @pytest.mark.asyncio
    async def test_end_to_end_user_cancels_modal(self):
        """Test complete flow when user cancels modal."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()

        mock_tool = MagicMock()
        mock_datasource = AsyncMock()
        mock_tool.datasource = mock_datasource
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        registered_callback = None

        def capture_push_screen(screen, callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        await registered_callback(None)

        chat_screen.orchestrator.inject_context_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_modal_opens_use_different_callbacks(self):
        """Test that opening modal multiple times creates separate callbacks."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event1 = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/function1")
        event2 = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/function2")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event1)
            await chat_screen.on_log_group_preview_requested(event2)

        assert len(callbacks) == 2
        assert callbacks[0] is not callbacks[1]

        result1 = {
            "log_group_name": "/aws/lambda/function1",
            "selected_entries": [{"timestamp": 1708263045123, "message": "From function1"}],
        }
        await callbacks[0](result1)

        result2 = {
            "log_group_name": "/aws/lambda/function2",
            "selected_entries": [{"timestamp": 1708263046456, "message": "From function2"}],
        }
        await callbacks[1](result2)

        assert chat_screen.orchestrator.inject_context_update.call_count == 2

        call1 = chat_screen.orchestrator.inject_context_update.call_args_list[0][0][0]
        call2 = chat_screen.orchestrator.inject_context_update.call_args_list[1][0][0]

        assert "function1" in call1
        assert "function2" in call2

    @pytest.mark.asyncio
    async def test_no_race_condition_with_rapid_operations(self):
        """Test that rapid modal open/close operations don't cause race conditions."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            for i in range(5):
                event = ClickableLogGroupItem.LogGroupPreviewRequested(f"/aws/lambda/function{i}")
                await chat_screen.on_log_group_preview_requested(event)

        assert len(callbacks) == 5

        for i, callback in enumerate(callbacks):
            result = {
                "log_group_name": f"/aws/lambda/function{i}",
                "selected_entries": [{"timestamp": 1708263045000 + i, "message": f"Log {i}"}],
            }
            await callback(result)

        assert chat_screen.orchestrator.inject_context_update.call_count == 5

        calls = chat_screen.orchestrator.inject_context_update.call_args_list
        for i in range(5):
            context_message = calls[i][0][0]
            assert f"function{i}" in context_message

    @pytest.mark.asyncio
    async def test_callback_with_large_entry_count(self):
        """Test callback handles large number of entries efficiently."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {
                    "timestamp": 1708263045000 + i,
                    "message": f"Log entry {i} with some longer message text",
                    "log_stream": "2024/01/15/[$LATEST]abc123",
                }
                for i in range(100)
            ],
        }

        import time

        start_time = time.time()
        await captured_callback(result)
        elapsed_time = time.time() - start_time

        assert elapsed_time < 1.0, f"Callback took {elapsed_time}s, expected < 1s"
        chat_screen.orchestrator.inject_context_update.assert_called_once()


class TestCallbackErrorRecovery:
    """Test error recovery and resilience in callback flow."""

    @pytest.mark.asyncio
    async def test_callback_error_logged_and_notified(self):
        """Test that errors in callback are logged and user is notified."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        chat_screen.orchestrator.inject_context_update = MagicMock(
            side_effect=Exception("Orchestrator failure")
        )
        chat_screen.notify = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_app = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

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
            await captured_callback(result)
            assert mock_logger.error.called

        chat_screen.notify.assert_called_once()
        assert "Failed to add logs to context" in chat_screen.notify.call_args[0][0]

    @pytest.mark.asyncio
    async def test_subsequent_callback_works_after_error(self):
        """Test that subsequent callback invocations work after an error."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        call_count = [0]

        def inject_side_effect(message):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First call fails")

        chat_screen.orchestrator.inject_context_update = MagicMock(side_effect=inject_side_effect)
        chat_screen.notify = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_app = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event1 = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test1")
        event2 = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test2")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event1)
            await chat_screen.on_log_group_preview_requested(event2)

        result1 = {
            "log_group_name": "/aws/lambda/test1",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test1"}],
        }
        with patch("logai.ui.screens.chat.logger"):
            await callbacks[0](result1)

        assert chat_screen.notify.call_count == 1

        result2 = {
            "log_group_name": "/aws/lambda/test2",
            "selected_entries": [{"timestamp": 1708263046456, "message": "Test2"}],
        }
        await callbacks[1](result2)

        assert chat_screen.notify.call_count == 1
        assert chat_screen.orchestrator.inject_context_update.call_count == 2


class TestCallbackTimingAndPerformance:
    """Test timing and performance characteristics of callback."""

    @pytest.mark.asyncio
    async def test_callback_is_async(self):
        """Verify callback is an async function."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        assert asyncio.iscoroutinefunction(captured_callback)

    @pytest.mark.asyncio
    async def test_callback_execution_is_fast(self):
        """Test that callback executes quickly for typical data."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        chat_screen = ChatScreen(orchestrator, cache_manager)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()

        mock_tool = MagicMock()
        mock_tool.datasource = AsyncMock()
        orchestrator.tool_registry.get_tool.return_value = mock_tool

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import ClickableLogGroupItem

        event = ClickableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [
                {
                    "timestamp": 1708263045000 + i,
                    "message": f"Log entry {i}",
                    "log_stream": "2024/01/15/[$LATEST]abc123",
                }
                for i in range(10)
            ],
        }

        import time

        start_time = time.time()
        await captured_callback(result)
        elapsed_time = time.time() - start_time

        assert elapsed_time < 0.1, f"Callback took {elapsed_time}s, expected < 0.1s"
