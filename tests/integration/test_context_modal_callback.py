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
        """Test complete flow from modal open to context injection.

        The callback registered with push_screen is synchronous — it
        schedules the async injection via call_later.  We verify that
        call_later is invoked with the right arguments rather than
        awaiting the callback directly.
        """
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        # Pass datasource directly — the registry-based lookup was replaced by
        # a constructor parameter when OP-4 threaded CloudWatchDataSource through.
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()
        # Intercept call_later so we can capture the scheduled coroutine.
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        registered_callback = None

        def capture_push_screen(screen, callback):
            nonlocal registered_callback
            registered_callback = callback
            assert isinstance(screen, LogPreviewScreen)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

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

        # Invoke the sync callback — it schedules async work via call_later.
        registered_callback(result)

        # Verify that the async injection was scheduled with the right result.
        assert len(scheduled_calls) == 1
        fn, args = scheduled_calls[0]
        # Bound method identity is not stable across attribute lookups, so
        # compare by name rather than using `is`.
        assert fn.__name__ == "_inject_log_entries_to_context"
        assert args[0] is result

        # Now actually run the scheduled async method to verify context content.
        await fn(*args)

        chat_screen.orchestrator.inject_context_update.assert_called_once()
        context_message = chat_screen.orchestrator.inject_context_update.call_args[0][0]

        assert "/aws/lambda/test" in context_message
        assert "ERROR: Database connection failed" in context_message
        assert "ERROR: Retry attempt failed" in context_message

    @pytest.mark.asyncio
    async def test_end_to_end_user_cancels_modal(self):
        """Test complete flow when user cancels modal (callback receives None)."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        registered_callback = None

        def capture_push_screen(screen, callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        # Simulate the user dismissing the modal without selecting entries.
        registered_callback(None)

        # No async work should be scheduled when the user cancels.
        assert len(scheduled_calls) == 0
        chat_screen.orchestrator.inject_context_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_modal_opens_use_different_callbacks(self):
        """Test that opening modal multiple times creates separate callbacks."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event1 = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/function1")
        event2 = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/function2")

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
        callbacks[0](result1)

        result2 = {
            "log_group_name": "/aws/lambda/function2",
            "selected_entries": [{"timestamp": 1708263046456, "message": "From function2"}],
        }
        callbacks[1](result2)

        # Both callbacks should have scheduled async work.
        assert len(scheduled_calls) == 2

        # Run both scheduled injections.
        for fn, args in scheduled_calls:
            await fn(*args)

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
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            for i in range(5):
                event = SelectableLogGroupItem.LogGroupPreviewRequested(f"/aws/lambda/function{i}")
                await chat_screen.on_log_group_preview_requested(event)

        assert len(callbacks) == 5

        for i, callback in enumerate(callbacks):
            result = {
                "log_group_name": f"/aws/lambda/function{i}",
                "selected_entries": [{"timestamp": 1708263045000 + i, "message": f"Log {i}"}],
            }
            callback(result)

        assert len(scheduled_calls) == 5

        for fn, args in scheduled_calls:
            await fn(*args)

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
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

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
        captured_callback(result)
        # Run the scheduled async work.
        for fn, args in scheduled_calls:
            await fn(*args)
        elapsed_time = time.time() - start_time

        assert elapsed_time < 1.0, f"Callback took {elapsed_time}s, expected < 1s"
        chat_screen.orchestrator.inject_context_update.assert_called_once()


class TestCallbackErrorRecovery:
    """Test error recovery and resilience in callback flow."""

    @pytest.mark.asyncio
    async def test_callback_error_logged_and_notified(self):
        """Test that errors in the async injection step are logged and user is notified."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        chat_screen.orchestrator.inject_context_update = MagicMock(
            side_effect=Exception("Orchestrator failure")
        )
        chat_screen.notify = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        mock_app = MagicMock()

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        result = {
            "log_group_name": "/aws/lambda/test",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test"}],
        }

        captured_callback(result)

        with patch("logai.ui.screens.chat.logger") as mock_logger:
            for fn, args in scheduled_calls:
                await fn(*args)
            assert mock_logger.error.called

        chat_screen.notify.assert_called_once()
        assert "Failed to add logs to context" in chat_screen.notify.call_args[0][0]

    @pytest.mark.asyncio
    async def test_subsequent_callback_works_after_error(self):
        """Test that subsequent callback invocations work after an error."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        call_count = [0]

        def inject_side_effect(message):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First call fails")

        chat_screen.orchestrator.inject_context_update = MagicMock(side_effect=inject_side_effect)
        chat_screen.notify = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        mock_app = MagicMock()

        callbacks = []

        def capture_push_screen(screen, callback):
            callbacks.append(callback)

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event1 = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test1")
        event2 = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test2")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event1)
            await chat_screen.on_log_group_preview_requested(event2)

        result1 = {
            "log_group_name": "/aws/lambda/test1",
            "selected_entries": [{"timestamp": 1708263045123, "message": "Test1"}],
        }
        callbacks[0](result1)

        result2 = {
            "log_group_name": "/aws/lambda/test2",
            "selected_entries": [{"timestamp": 1708263046456, "message": "Test2"}],
        }
        callbacks[1](result2)

        with patch("logai.ui.screens.chat.logger"):
            for fn, args in scheduled_calls:
                await fn(*args)

        assert chat_screen.notify.call_count == 1
        assert chat_screen.orchestrator.inject_context_update.call_count == 2


class TestCallbackTimingAndPerformance:
    """Test timing and performance characteristics of callback."""

    @pytest.mark.asyncio
    async def test_callback_is_sync(self):
        """Verify the push_screen callback is a plain (synchronous) function.

        The callback schedules async work via call_later rather than being
        a coroutine itself, which is the correct Textual pattern.
        """
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

        with patch.object(type(chat_screen), "app", new_callable=PropertyMock) as mock_app_prop:
            mock_app_prop.return_value = mock_app
            await chat_screen.on_log_group_preview_requested(event)

        assert callable(captured_callback)
        assert not asyncio.iscoroutinefunction(captured_callback)

    @pytest.mark.asyncio
    async def test_callback_execution_is_fast(self):
        """Test that the sync callback and subsequent async injection execute quickly."""
        orchestrator = MagicMock()
        cache_manager = MagicMock()
        mock_datasource = AsyncMock()
        chat_screen = ChatScreen(orchestrator, cache_manager, datasource=mock_datasource)

        mock_app = MagicMock()
        chat_screen.orchestrator.inject_context_update = MagicMock()
        chat_screen.query_one = MagicMock()
        scheduled_calls: list = []
        chat_screen.call_later = lambda fn, *args, **kwargs: scheduled_calls.append((fn, args))

        captured_callback = None

        def capture_push_screen(screen, callback):
            nonlocal captured_callback
            captured_callback = callback

        mock_app.push_screen = capture_push_screen

        from logai.ui.widgets.log_groups_sidebar import SelectableLogGroupItem

        event = SelectableLogGroupItem.LogGroupPreviewRequested("/aws/lambda/test")

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
        captured_callback(result)
        for fn, args in scheduled_calls:
            await fn(*args)
        elapsed_time = time.time() - start_time

        assert elapsed_time < 0.1, f"Callback took {elapsed_time}s, expected < 0.1s"
