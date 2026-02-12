"""Unit tests for LogGroupsSidebar widget."""

import pytest
from unittest.mock import MagicMock

from logai.ui.widgets.log_groups_sidebar import LogGroupsSidebar


class TestLogGroupsSidebar:
    """Test cases for LogGroupsSidebar widget."""

    def test_get_count_no_manager(self):
        """Test count returns 0 when no manager."""
        sidebar = LogGroupsSidebar()
        assert sidebar._get_count() == 0

    def test_get_count_with_manager(self):
        """Test count returns manager count."""
        mock_manager = MagicMock()
        mock_manager.count = 135
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        assert sidebar._get_count() == 135

    def test_get_count_with_manager_zero(self):
        """Test count returns 0 when manager has no groups."""
        mock_manager = MagicMock()
        mock_manager.count = 0
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        assert sidebar._get_count() == 0

    def test_get_log_group_names_no_manager(self):
        """Test log group names returns empty list when no manager."""
        sidebar = LogGroupsSidebar()
        names = sidebar._get_log_group_names()
        assert names == []

    def test_get_log_group_names_sorted(self):
        """Test log group names are returned sorted."""
        mock_manager = MagicMock()
        mock_manager.get_log_group_names.return_value = [
            "/ecs/app",
            "/aws/lambda/func",
            "/aws/apigateway/api",
        ]
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar._get_log_group_names()
        assert names == [
            "/aws/apigateway/api",
            "/aws/lambda/func",
            "/ecs/app",
        ]

    def test_get_log_group_names_already_sorted(self):
        """Test that already sorted names remain sorted."""
        mock_manager = MagicMock()
        mock_manager.get_log_group_names.return_value = [
            "/aws/apigateway/api",
            "/aws/lambda/func",
            "/ecs/app",
        ]
        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar._get_log_group_names()
        assert names == [
            "/aws/apigateway/api",
            "/aws/lambda/func",
            "/ecs/app",
        ]

    def test_full_names_displayed_without_truncation(self):
        """Test that full log group names are displayed without truncation."""
        sidebar = LogGroupsSidebar()

        # Test very long name is not truncated
        long_name = (
            "/aws/lambda/my-very-long-function-name-that-exceeds-the-previous-sidebar-width-limit"
        )
        mock_manager = MagicMock()
        mock_manager.count = 1
        mock_manager.get_log_group_names.return_value = [long_name]

        sidebar_with_data = LogGroupsSidebar(log_group_manager=mock_manager)
        names = sidebar_with_data._get_log_group_names()

        # Verify full name is returned (no truncation)
        assert len(names) == 1
        assert names[0] == long_name
        assert "..." not in names[0]


class TestLogGroupManagerCallbacks:
    """Test callback system in LogGroupManager."""

    def test_register_callback(self):
        """Test callback registration."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        manager.register_update_callback(callback)

        assert callback in manager._update_callbacks

    def test_register_callback_duplicate(self):
        """Test registering same callback twice doesn't duplicate."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        manager.register_update_callback(callback)
        manager.register_update_callback(callback)

        assert manager._update_callbacks.count(callback) == 1

    def test_unregister_callback(self):
        """Test callback unregistration."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        manager.register_update_callback(callback)
        manager.unregister_update_callback(callback)

        assert callback not in manager._update_callbacks

    def test_unregister_callback_not_registered(self):
        """Test unregistering callback that wasn't registered is safe."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback = MagicMock()
        # Should not raise
        manager.unregister_update_callback(callback)

        assert callback not in manager._update_callbacks

    def test_notify_update_calls_callbacks(self):
        """Test _notify_update calls all registered callbacks."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback1 = MagicMock()
        callback2 = MagicMock()
        manager.register_update_callback(callback1)
        manager.register_update_callback(callback2)

        manager._notify_update()

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_notify_update_handles_callback_error(self):
        """Test that callback errors don't break notification chain."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        callback1 = MagicMock(side_effect=Exception("Callback error"))
        callback2 = MagicMock()
        manager.register_update_callback(callback1)
        manager.register_update_callback(callback2)

        # Should not raise
        manager._notify_update()

        # Second callback should still be called
        callback2.assert_called_once()

    def test_notify_update_with_no_callbacks(self):
        """Test _notify_update with no callbacks is safe."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        # Should not raise
        manager._notify_update()

    def test_multiple_callbacks_called_in_order(self):
        """Test multiple callbacks are called in registration order."""
        from logai.core.log_group_manager import LogGroupManager

        mock_datasource = MagicMock()
        manager = LogGroupManager(mock_datasource)

        call_order = []
        callback1 = MagicMock(side_effect=lambda: call_order.append(1))
        callback2 = MagicMock(side_effect=lambda: call_order.append(2))
        callback3 = MagicMock(side_effect=lambda: call_order.append(3))

        manager.register_update_callback(callback1)
        manager.register_update_callback(callback2)
        manager.register_update_callback(callback3)

        manager._notify_update()

        assert call_order == [1, 2, 3]


class TestLogGroupsSidebarIntegration:
    """Integration tests for sidebar with manager."""

    def test_sidebar_initializes_with_empty_manager(self):
        """Test sidebar handles manager with no log groups."""
        mock_manager = MagicMock()
        mock_manager.count = 0
        mock_manager.get_log_group_names.return_value = []

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        assert sidebar._get_count() == 0
        assert sidebar._get_log_group_names() == []

    def test_sidebar_initializes_with_populated_manager(self):
        """Test sidebar handles manager with log groups."""
        mock_manager = MagicMock()
        mock_manager.count = 3
        mock_manager.get_log_group_names.return_value = [
            "/aws/lambda/func1",
            "/aws/lambda/func2",
            "/ecs/service",
        ]

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        assert sidebar._get_count() == 3
        names = sidebar._get_log_group_names()
        assert len(names) == 3
        # Should be sorted
        assert names[0] == "/aws/lambda/func1"

    def test_sidebar_handles_large_number_of_groups(self):
        """Test sidebar handles hundreds of log groups efficiently."""
        mock_manager = MagicMock()
        # Simulate 500 log groups
        log_groups = [f"/aws/lambda/function-{i:03d}" for i in range(500)]
        mock_manager.count = 500
        mock_manager.get_log_group_names.return_value = log_groups

        sidebar = LogGroupsSidebar(log_group_manager=mock_manager)

        assert sidebar._get_count() == 500
        names = sidebar._get_log_group_names()
        assert len(names) == 500
        # Should be sorted
        assert names[0] == "/aws/lambda/function-000"
        assert names[-1] == "/aws/lambda/function-499"
