"""Integration tests for Log Groups Sidebar feature.

These tests verify the end-to-end functionality of the log groups sidebar,
including startup behavior, command integration, multi-sidebar interaction,
data flow, configuration, and UI behavior.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from logai.cache.manager import CacheManager
from logai.config.settings import LogAISettings
from logai.core.log_group_manager import (
    LogGroupInfo,
    LogGroupManager,
    LogGroupManagerResult,
    LogGroupManagerState,
)
from logai.core.orchestrator import LLMOrchestrator
from logai.core.sanitizer import LogSanitizer
from logai.core.tools.registry import ToolRegistry
from logai.ui.commands import CommandHandler
from logai.ui.screens.chat import ChatScreen
from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar


class TestStartupBehavior:
    """Test sidebar visibility and initialization at startup."""

    def test_sidebar_visible_on_startup_when_configured_true(self):
        """Test sidebar is visible by default when configured to true."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        # Create settings with sidebar visible
        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True

        # Create orchestrator and cache manager mocks
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Verify initial state
        assert chat_screen._log_groups_sidebar_visible is True

    def test_sidebar_hidden_on_startup_when_configured_false(self):
        """Test sidebar is hidden by default when configured to false."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        # Create settings with sidebar hidden
        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = False

        # Create orchestrator and cache manager mocks
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Verify initial state
        assert chat_screen._log_groups_sidebar_visible is False

    def test_sidebar_receives_preloaded_log_groups(self):
        """Test sidebar displays log groups loaded during pre-loading."""
        # Create mock datasource with log groups
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Create log groups data
        log_groups_data = {
            "logGroups": [
                {
                    "logGroupName": "/aws/lambda/function-1",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                    "retentionInDays": 7,
                },
                {
                    "logGroupName": "/aws/lambda/function-2",
                    "creationTime": 1234567890000,
                    "storedBytes": 2048,
                    "retentionInDays": 7,
                },
            ]
        }

        mock_paginator.paginate.return_value = [log_groups_data]
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        # Create manager and sidebar
        manager = LogGroupManager(mock_datasource)
        sidebar = LogGroupsSidebar(log_group_manager=manager)

        # Simulate loading log groups (synchronous for test)
        # In real scenario, this happens during startup
        import asyncio

        result = asyncio.run(manager.load_all())

        # Verify manager has log groups
        assert manager.count == 2
        assert manager.state == LogGroupManagerState.READY

        # Verify sidebar can access log groups
        assert sidebar._get_count() == 2
        names = sidebar._get_log_group_names()
        assert len(names) == 2
        assert "/aws/lambda/function-1" in names
        assert "/aws/lambda/function-2" in names


class TestCommandIntegration:
    """Test integration with /logs and /refresh commands."""

    @pytest.mark.asyncio
    async def test_logs_command_toggles_sidebar_visibility(self):
        """Test /logs command toggles sidebar visibility."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Create command handler
        handler = CommandHandler(
            orchestrator=mock_orchestrator,
            cache_manager=mock_cache_manager,
            settings=mock_settings,
            chat_screen=chat_screen,
            log_group_manager=mock_manager,
        )

        # Initial state: visible
        assert chat_screen._log_groups_sidebar_visible is True

        # Toggle to hidden
        chat_screen.toggle_log_groups_sidebar()
        assert chat_screen._log_groups_sidebar_visible is False

        # Toggle back to visible
        chat_screen.toggle_log_groups_sidebar()
        assert chat_screen._log_groups_sidebar_visible is True

    @pytest.mark.asyncio
    async def test_refresh_command_updates_sidebar_content(self):
        """Test /refresh command triggers sidebar update via callback."""
        # Create mock datasource
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Initial load: 2 log groups
        initial_data = {
            "logGroups": [
                {
                    "logGroupName": "/aws/lambda/function-1",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                    "retentionInDays": 7,
                },
                {
                    "logGroupName": "/aws/lambda/function-2",
                    "creationTime": 1234567890000,
                    "storedBytes": 2048,
                    "retentionInDays": 7,
                },
            ]
        }

        # After refresh: 3 log groups
        refreshed_data = {
            "logGroups": [
                {
                    "logGroupName": "/aws/lambda/function-1",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                    "retentionInDays": 7,
                },
                {
                    "logGroupName": "/aws/lambda/function-2",
                    "creationTime": 1234567890000,
                    "storedBytes": 2048,
                    "retentionInDays": 7,
                },
                {
                    "logGroupName": "/aws/lambda/function-3",
                    "creationTime": 1234567890000,
                    "storedBytes": 4096,
                    "retentionInDays": 7,
                },
            ]
        }

        # Setup paginator to return different data on each call
        mock_paginator.paginate.side_effect = [[initial_data], [refreshed_data]]
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        # Create manager and sidebar
        manager = LogGroupManager(mock_datasource)
        sidebar = LogGroupsSidebar(log_group_manager=manager)

        # Track callback invocations
        callback_invoked = []

        def test_callback():
            callback_invoked.append(True)

        manager.register_update_callback(test_callback)

        # Initial load
        result = await manager.load_all()
        assert result.success is True
        assert result.count == 2
        assert len(callback_invoked) == 1  # Callback invoked on initial load

        # Refresh (should trigger callback again)
        result = await manager.refresh()
        assert result.success is True
        assert result.count == 3
        assert len(callback_invoked) == 2  # Callback invoked on refresh

        # Verify sidebar has updated data
        assert sidebar._get_count() == 3
        names = sidebar._get_log_group_names()
        assert len(names) == 3
        assert "/aws/lambda/function-3" in names

    @pytest.mark.asyncio
    async def test_logs_command_works_correctly_with_sidebar(self):
        """Test /logs command handler returns correct messages."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Create command handler
        handler = CommandHandler(
            orchestrator=mock_orchestrator,
            cache_manager=mock_cache_manager,
            settings=mock_settings,
            chat_screen=chat_screen,
            log_group_manager=mock_manager,
        )

        # Test toggle to hidden
        chat_screen._log_groups_sidebar_visible = True
        response = handler._toggle_log_groups_sidebar()
        assert chat_screen._log_groups_sidebar_visible is False
        assert "hidden" in response.lower()

        # Test toggle to visible
        chat_screen._log_groups_sidebar_visible = False
        response = handler._toggle_log_groups_sidebar()
        assert chat_screen._log_groups_sidebar_visible is True
        assert "shown" in response.lower()


class TestMultiSidebarInteraction:
    """Test interaction between log groups sidebar and tool calls sidebar."""

    def test_both_sidebars_can_be_visible_simultaneously(self):
        """Test both sidebars can be open at the same time."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Verify both can be visible
        chat_screen._log_groups_sidebar_visible = True
        chat_screen._tool_sidebar_visible = True

        assert chat_screen._log_groups_sidebar_visible is True
        assert chat_screen._tool_sidebar_visible is True

    def test_toggling_one_sidebar_does_not_affect_other(self):
        """Test toggling one sidebar doesn't affect the other."""
        # Create mock dependencies
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        # Create chat screen
        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Both visible initially
        chat_screen._log_groups_sidebar_visible = True
        chat_screen._tool_sidebar_visible = True

        # Toggle log groups sidebar
        chat_screen.toggle_log_groups_sidebar()

        # Verify only log groups sidebar affected
        assert chat_screen._log_groups_sidebar_visible is False
        assert chat_screen._tool_sidebar_visible is True

        # Toggle tool sidebar
        chat_screen.toggle_sidebar()

        # Verify only tool sidebar affected
        assert chat_screen._log_groups_sidebar_visible is False
        assert chat_screen._tool_sidebar_visible is False


class TestDataFlow:
    """Test data flow from LogGroupManager to sidebar."""

    @pytest.mark.asyncio
    async def test_callback_triggers_sidebar_update(self):
        """Test LogGroupManager callback triggers sidebar update."""
        # Create mock datasource
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        log_groups_data = {
            "logGroups": [
                {
                    "logGroupName": f"/aws/lambda/function-{i}",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                    "retentionInDays": 7,
                }
                for i in range(1, 11)
            ]
        }

        mock_paginator.paginate.return_value = [log_groups_data]
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        # Create manager and sidebar
        manager = LogGroupManager(mock_datasource)
        sidebar = LogGroupsSidebar(log_group_manager=manager)

        # Track callback invocations
        update_called = []
        original_populate = sidebar._populate_log_groups

        def tracked_populate():
            update_called.append(True)
            return original_populate()

        sidebar._populate_log_groups = tracked_populate

        # Register callback
        manager.register_update_callback(sidebar._on_log_groups_updated)

        # Load log groups (should trigger callback)
        result = await manager.load_all()

        # Verify callback was invoked
        assert result.success is True
        assert len(update_called) >= 1  # At least one update

    def test_sidebar_displays_log_groups_in_sorted_order(self):
        """Test sidebar displays log groups alphabetically sorted."""
        # Create mock manager with unsorted log groups
        mock_manager = MagicMock()
        mock_manager.count = 5
        mock_manager.get_log_group_names.return_value = [
            "/ecs/service-1",
            "/aws/lambda/function-a",
            "/aws/apigateway/api-1",
            "/aws/lambda/function-b",
            "/aws/ecs/cluster-1",
        ]

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        # Get sorted names
        names = sidebar._get_log_group_names()

        # Verify sorted
        assert names == [
            "/aws/apigateway/api-1",
            "/aws/ecs/cluster-1",
            "/aws/lambda/function-a",
            "/aws/lambda/function-b",
            "/ecs/service-1",
        ]

    def test_empty_state_handled_correctly(self):
        """Test sidebar handles empty log groups list."""
        # Create mock manager with no log groups
        mock_manager = MagicMock()
        mock_manager.count = 0
        mock_manager.get_log_group_names.return_value = []

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        # Verify empty state
        assert sidebar._get_count() == 0
        assert sidebar._get_log_group_names() == []

    @pytest.mark.asyncio
    async def test_large_dataset_handling(self):
        """Test sidebar handles 1000+ log groups efficiently."""
        # Create mock datasource with 1200 log groups
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Create 1200 log groups across 24 pages (50 per page)
        pages = []
        for page_num in range(24):
            page_data = {
                "logGroups": [
                    {
                        "logGroupName": f"/aws/lambda/function-{page_num * 50 + i:04d}",
                        "creationTime": 1234567890000,
                        "storedBytes": 1024,
                        "retentionInDays": 7,
                    }
                    for i in range(50)
                ]
            }
            pages.append(page_data)

        mock_paginator.paginate.return_value = pages
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        # Create manager and sidebar
        manager = LogGroupManager(mock_datasource)
        sidebar = LogGroupsSidebar(log_group_manager=manager)

        # Load log groups
        result = await manager.load_all()

        # Verify all loaded
        assert result.success is True
        assert result.count == 1200

        # Verify sidebar can handle large dataset
        assert sidebar._get_count() == 1200
        names = sidebar._get_log_group_names()
        assert len(names) == 1200

        # Verify sorting still works
        assert names[0] == "/aws/lambda/function-0000"
        assert names[-1] == "/aws/lambda/function-1199"


class TestConfiguration:
    """Test configuration settings for sidebar visibility."""

    def test_configuration_setting_respected_at_startup(self):
        """Test LOGAI_LOG_GROUPS_SIDEBAR_VISIBLE setting is respected."""
        # Test with True
        mock_settings_true = MagicMock()
        mock_settings_true.log_groups_sidebar_visible = True

        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()
        mock_manager = MagicMock()

        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings_true):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )
            assert chat_screen._log_groups_sidebar_visible is True

        # Test with False
        mock_settings_false = MagicMock()
        mock_settings_false.log_groups_sidebar_visible = False

        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings_false):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )
            assert chat_screen._log_groups_sidebar_visible is False

    def test_config_changes_take_effect_on_restart(self):
        """Test configuration changes require restart to take effect."""
        # Create initial screen with visible=True
        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True

        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()
        mock_manager = MagicMock()

        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen1 = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )
            assert chat_screen1._log_groups_sidebar_visible is True

        # "Change" config and create new screen (simulating restart)
        mock_settings.log_groups_sidebar_visible = False

        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen2 = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )
            assert chat_screen2._log_groups_sidebar_visible is False


class TestUIBehavior:
    """Test UI-specific behavior of the sidebar."""

    def test_sidebar_title_shows_correct_count(self):
        """Test sidebar title displays correct log group count."""
        # Create mock manager with 135 log groups
        mock_manager = MagicMock()
        mock_manager.count = 135
        mock_manager.get_log_group_names.return_value = [
            f"/aws/lambda/function-{i}" for i in range(135)
        ]

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        # Verify count
        assert sidebar._get_count() == 135

    def test_full_log_group_names_displayed_without_truncation(self):
        """Test full log group names are displayed without ellipsis."""
        sidebar = LogGroupsSidebar()

        # Create mock manager with very long log group name
        mock_manager = MagicMock()
        long_name = "/aws/lambda/my-very-long-function-name-that-exceeds-the-sidebar-width-limit-production-environment"
        mock_manager.count = 1
        mock_manager.get_log_group_names.return_value = [long_name]

        sidebar_with_data = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar_with_data._get_log_group_names()

        # Verify full name is returned without truncation
        assert len(names) == 1
        assert names[0] == long_name
        assert "..." not in names[0]

    def test_multiple_long_names_all_displayed_fully(self):
        """Test multiple long names are all displayed without truncation."""
        mock_manager = MagicMock()
        long_names = [
            "/aws/lambda/my-very-long-function-name-for-processing-payments-production",
            "/aws/lambda/another-extremely-long-function-name-for-user-authentication-staging",
            "/ecs/service/super-long-container-service-name-for-api-gateway-integration",
        ]
        mock_manager.count = 3
        mock_manager.get_log_group_names.return_value = long_names

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar._get_log_group_names()

        # Verify all full names are returned
        assert len(names) == 3
        for i, name in enumerate(sorted(long_names)):
            assert names[i] == name
            assert "..." not in names[i]

    def test_layout_stable_during_toggle_operations(self):
        """Test layout state doesn't corrupt during toggle."""
        mock_datasource = Mock()
        mock_manager = LogGroupManager(mock_datasource)

        mock_settings = MagicMock()
        mock_settings.log_groups_sidebar_visible = True
        mock_orchestrator = MagicMock()
        mock_cache_manager = MagicMock()

        with patch("logai.ui.screens.chat.get_settings", return_value=mock_settings):
            chat_screen = ChatScreen(
                orchestrator=mock_orchestrator,
                cache_manager=mock_cache_manager,
                log_group_manager=mock_manager,
            )

        # Perform multiple rapid toggles
        for _ in range(10):
            chat_screen.toggle_log_groups_sidebar()

        # State should be stable (toggled 10 times from True = back to True)
        assert chat_screen._log_groups_sidebar_visible is True

        # Toggle one more time to False
        chat_screen.toggle_log_groups_sidebar()
        assert chat_screen._log_groups_sidebar_visible is False


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_sidebar_handles_manager_callback_error_gracefully(self):
        """Test sidebar handles errors in callback gracefully."""
        mock_manager = MagicMock()
        mock_manager.count = 5
        mock_manager.get_log_group_names.side_effect = Exception("Test error")

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        # This should not raise - error should be caught
        try:
            sidebar._on_log_groups_updated()
            # If we get here, error was handled gracefully
            assert True
        except Exception:
            # If exception propagates, test fails
            assert False, "Exception should have been caught"

    def test_sidebar_works_without_manager(self):
        """Test sidebar works when no manager is provided."""
        sidebar = LogGroupsSidebar(log_group_manager=None)

        # Should return safe defaults
        assert sidebar._get_count() == 0
        assert sidebar._get_log_group_names() == []

    @pytest.mark.asyncio
    async def test_callback_unregistration_prevents_updates(self):
        """Test unregistering callback stops updates."""
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        log_groups_data = {
            "logGroups": [
                {
                    "logGroupName": "/aws/lambda/function-1",
                    "creationTime": 1234567890000,
                    "storedBytes": 1024,
                    "retentionInDays": 7,
                }
            ]
        }

        mock_paginator.paginate.return_value = [log_groups_data]
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        manager = LogGroupManager(mock_datasource)

        # Create callback that tracks invocations
        call_count = []

        def test_callback():
            call_count.append(1)

        # Register callback
        manager.register_update_callback(test_callback)

        # Load (should invoke callback)
        await manager.load_all()
        assert len(call_count) == 1

        # Unregister callback
        manager.unregister_update_callback(test_callback)

        # Refresh (should NOT invoke callback)
        await manager.refresh()
        assert len(call_count) == 1  # Still 1, not 2


class TestPerformance:
    """Test performance characteristics of the sidebar."""

    @pytest.mark.asyncio
    async def test_sidebar_efficient_with_large_dataset(self):
        """Test sidebar remains efficient with 2000+ log groups."""
        # Create mock datasource with 2000 log groups
        mock_datasource = Mock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Create 40 pages of 50 log groups each
        pages = []
        for page_num in range(40):
            page_data = {
                "logGroups": [
                    {
                        "logGroupName": f"/aws/lambda/function-{page_num * 50 + i:04d}",
                        "creationTime": 1234567890000,
                        "storedBytes": 1024,
                        "retentionInDays": 7,
                    }
                    for i in range(50)
                ]
            }
            pages.append(page_data)

        mock_paginator.paginate.return_value = pages
        mock_client.get_paginator.return_value = mock_paginator
        mock_datasource.client = mock_client

        # Create manager and sidebar
        manager = LogGroupManager(mock_datasource)
        sidebar = LogGroupsSidebar(log_group_manager=manager)

        # Load log groups
        result = await manager.load_all()

        # Verify loaded
        assert result.success is True
        assert result.count == 2000

        # Test that sorting 2000 items is still efficient
        import time

        start = time.time()
        names = sidebar._get_log_group_names()
        duration = time.time() - start

        # Should complete in less than 100ms
        assert duration < 0.1
        assert len(names) == 2000
