"""Integration tests for multi-select log groups feature."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from logai.cache.manager import CacheManager
from logai.core.orchestrator import LLMOrchestrator
from logai.ui.screens.chat import ChatScreen
from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar, SelectableLogGroupItem
from textual.app import App, ComposeResult
from textual.events import Click


class FullIntegrationTestApp(App):
    """Test app with full ChatScreen integration."""

    def __init__(self, orchestrator, cache_manager, log_group_manager):
        super().__init__()
        self.orchestrator = orchestrator
        self.cache_manager = cache_manager
        self.log_group_manager = log_group_manager

    def compose(self) -> ComposeResult:
        yield ChatScreen(
            orchestrator=self.orchestrator,
            cache_manager=self.cache_manager,
            log_group_manager=self.log_group_manager,
        )


class TestMultiSelectEndToEndFlow:
    """Integration tests for end-to-end multi-select flow."""

    @pytest.mark.asyncio
    async def test_single_click_selects_and_updates_counter(self):
        """Test single click → selection → visual update → counter update."""
        # Create mock log group manager with test data
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/auth-service", "/aws/lambda/user-service"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        # Create mock orchestrator
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()

        # Create mock cache manager
        mock_cache = Mock(spec=CacheManager)

        # Create full app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for initial mount and population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Get the first log group item
            items = list(sidebar.query(SelectableLogGroupItem))
            assert len(items) == 2
            first_item = items[0]

            # Simulate a single click
            click_event = Mock(spec=Click)
            click_event.button = 1
            click_event.ctrl = False
            click_event.meta = False
            first_item.on_click(click_event)

            # Wait for single-click delay
            await asyncio.sleep(0.4)
            await pilot.pause()

            # Verify selection state
            assert sidebar.has_selection()
            assert sidebar.selection_count == 1
            assert first_item.log_group_name in sidebar.get_selected_groups()

            # Verify visual styling
            assert first_item.has_class("selected")

            # Verify counter is visible and shows correct text
            counter = sidebar.query_one("#selection-counter")
            assert counter.display is True
            assert "1 group selected" in counter.render().plain

    @pytest.mark.asyncio
    async def test_ctrl_click_multi_select_flow(self):
        """Test ctrl-click → multi-select → multiple items styled."""
        # Create mock log group manager
        mock_manager = Mock()
        mock_manager.count = 3
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/service1", "/aws/lambda/service2", "/aws/lambda/service3"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        # Create mocks
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()
        mock_cache = Mock(spec=CacheManager)

        # Create app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Get log group items
            items = list(sidebar.query(SelectableLogGroupItem))
            assert len(items) == 3

            # First click (normal)
            click1 = Mock(spec=Click)
            click1.button = 1
            click1.ctrl = False
            click1.meta = False
            items[0].on_click(click1)
            await asyncio.sleep(0.4)
            await pilot.pause()

            # Second click (with Ctrl)
            click2 = Mock(spec=Click)
            click2.button = 1
            click2.ctrl = True
            click2.meta = False
            items[1].on_click(click2)
            await asyncio.sleep(0.4)
            await pilot.pause()

            # Third click (with Ctrl)
            click3 = Mock(spec=Click)
            click3.button = 1
            click3.ctrl = True
            click3.meta = False
            items[2].on_click(click3)
            await asyncio.sleep(0.4)
            await pilot.pause()

            # Verify all three are selected
            assert sidebar.selection_count == 3
            assert items[0].has_class("selected")
            assert items[1].has_class("selected")
            assert items[2].has_class("selected")

            # Verify counter shows plural
            counter = sidebar.query_one("#selection-counter")
            assert "3 selected" in counter.render().plain

    @pytest.mark.asyncio
    async def test_double_click_preserves_selection(self):
        """Test double-click → preview modal (preserve existing functionality)."""
        # Create mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/auth-service", "/aws/lambda/user-service"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        # Create mocks
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()
        mock_cache = Mock(spec=CacheManager)

        # Create app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Get items
            items = list(sidebar.query(SelectableLogGroupItem))

            # Select first item
            click1 = Mock(spec=Click)
            click1.button = 1
            click1.ctrl = False
            click1.meta = False
            items[0].on_click(click1)
            await asyncio.sleep(0.4)
            await pilot.pause()

            assert sidebar.selection_count == 1
            assert items[0].log_group_name in sidebar.get_selected_groups()

            # Now double-click the second item (should emit preview, not select)
            double_click1 = Mock(spec=Click)
            double_click1.button = 1
            double_click1.ctrl = False
            double_click1.meta = False
            items[1].on_click(double_click1)

            await asyncio.sleep(0.15)  # Within double-click threshold

            double_click2 = Mock(spec=Click)
            double_click2.button = 1
            double_click2.ctrl = False
            double_click2.meta = False
            items[1].on_click(double_click2)

            await asyncio.sleep(0.4)
            await pilot.pause()

            # First item should still be the only selected one
            assert sidebar.selection_count == 1
            assert items[0].log_group_name in sidebar.get_selected_groups()
            assert items[0].has_class("selected")
            assert not items[1].has_class("selected")


class TestAgentIntegrationFlow:
    """Integration tests for agent context injection."""

    @pytest.mark.asyncio
    async def test_selection_to_context_injection_flow(self):
        """Test selection → message sent → context injected → agent receives context."""
        # Create mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/auth-service", "/aws/lambda/user-service"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        # Create mock orchestrator with tracking
        injected_contexts = []

        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()

        def track_inject(context):
            injected_contexts.append(context)

        mock_orchestrator.inject_context_update = Mock(side_effect=track_inject)

        # Mock chat stream
        async def mock_stream(*args, **kwargs):
            yield "Test response"

        mock_orchestrator.chat_stream = mock_stream
        mock_orchestrator.metrics = Mock()
        mock_orchestrator.metrics.get_counter_value = Mock(return_value=0)

        # Create mock cache manager
        mock_cache = Mock(spec=CacheManager)

        # Create app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Select log groups
            sidebar.select_group("/aws/lambda/auth-service")
            sidebar.select_group("/aws/lambda/user-service", add_to_selection=True)
            await pilot.pause()

            # Verify selection
            assert sidebar.selection_count == 2

            # Process a message (returns a Worker due to @work decorator)
            _worker = screen._process_message("search for errors")

            # Wait for the worker to complete
            await pilot.pause()
            await asyncio.sleep(0.5)

            # Verify context was injected
            assert len(injected_contexts) == 1
            context = injected_contexts[0]

            # Verify context contains the selected groups
            assert "USER HAS SELECTED THE FOLLOWING LOG GROUPS:" in context
            assert "/aws/lambda/auth-service" in context
            assert "/aws/lambda/user-service" in context
            assert "2 log group(s)" in context

    @pytest.mark.asyncio
    async def test_no_context_injection_without_selection(self):
        """Test that no context is injected when no groups are selected."""
        # Create mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/service1", "/aws/lambda/service2"]
        )
        mock_manager.register_update_callback = Mock()
        mock_manager.unregister_update_callback = Mock()

        # Create mock orchestrator with tracking
        inject_called = []

        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()
        mock_orchestrator.inject_context_update = Mock(
            side_effect=lambda x: inject_called.append(x)
        )

        # Mock chat stream
        async def mock_stream(*args, **kwargs):
            yield "Test response"

        mock_orchestrator.chat_stream = mock_stream
        mock_orchestrator.metrics = Mock()
        mock_orchestrator.metrics.get_counter_value = Mock(return_value=0)

        # Create mock cache manager
        mock_cache = Mock(spec=CacheManager)

        # Create app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Verify no selection
            assert sidebar.selection_count == 0

            # Process a message (returns a Worker)
            _worker = screen._process_message("search for errors")

            # Wait for worker to complete
            await pilot.pause()
            await asyncio.sleep(0.5)

            # Verify inject_context_update was NOT called
            assert len(inject_called) == 0


class TestSelectionPersistence:
    """Integration tests for selection persistence across operations."""

    @pytest.mark.asyncio
    async def test_selection_cleared_on_log_groups_refresh(self):
        """Test that selection is cleared when log groups are refreshed."""
        # Create mock log group manager
        mock_manager = Mock()
        mock_manager.count = 2
        mock_manager.get_log_group_names = Mock(
            return_value=["/aws/lambda/service1", "/aws/lambda/service2"]
        )

        callbacks = []

        def register_callback(callback):
            callbacks.append(callback)

        mock_manager.register_update_callback = Mock(side_effect=register_callback)
        mock_manager.unregister_update_callback = Mock()

        # Create mocks
        mock_orchestrator = Mock(spec=LLMOrchestrator)
        mock_orchestrator.register_tool_listener = Mock()
        mock_orchestrator.set_context_notification_callback = Mock()
        mock_cache = Mock(spec=CacheManager)

        # Create app
        app = FullIntegrationTestApp(
            orchestrator=mock_orchestrator, cache_manager=mock_cache, log_group_manager=mock_manager
        )

        async with app.run_test() as pilot:
            screen = app.query_one(ChatScreen)
            sidebar = screen._log_groups_sidebar

            # Wait for population
            await pilot.pause()
            await asyncio.sleep(0.1)

            # Select groups
            sidebar.select_group("/aws/lambda/service1")
            sidebar.select_group("/aws/lambda/service2", add_to_selection=True)
            assert sidebar.selection_count == 2

            # Simulate log groups refresh by calling the registered callback
            assert len(callbacks) == 1
            update_callback = callbacks[0]
            update_callback()

            await pilot.pause()

            # Selection should be cleared
            assert sidebar.selection_count == 0
            assert not sidebar.has_selection()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
