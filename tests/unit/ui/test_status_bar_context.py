"""Tests for status bar context usage display."""

import pytest
from logai.ui.widgets.status_bar import StatusBar
from logai.ui.widgets.status_footer import StatusFooter


class TestStatusBarContextUsage:
    """Test status bar context usage display."""

    def test_context_usage_green_zone(self):
        """Test context usage displays in green for 0-70%."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(45.0)

        assert status_bar.context_utilization == 45.0

    def test_context_usage_yellow_zone(self):
        """Test context usage displays in yellow for 71-85%."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(78.0)

        assert status_bar.context_utilization == 78.0

    def test_context_usage_red_zone(self):
        """Test context usage displays in red for 86-100%."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(92.0)

        assert status_bar.context_utilization == 92.0

    def test_context_usage_boundary_at_71(self):
        """Test context usage boundary at 71% (yellow zone)."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(71.0)

        assert status_bar.context_utilization == 71.0

    def test_context_usage_boundary_at_86(self):
        """Test context usage boundary at 86% (red zone)."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(86.0)

        assert status_bar.context_utilization == 86.0

    def test_context_usage_zero(self):
        """Test context usage at 0%."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(0.0)

        assert status_bar.context_utilization == 0.0

    def test_context_usage_hundred(self):
        """Test context usage at 100%."""
        status_bar = StatusBar(model="test-model")
        status_bar.update_context_usage(100.0)

        assert status_bar.context_utilization == 100.0

    def test_reactive_property_updates_on_change(self):
        """Test that changing context utilization triggers reactive update."""
        status_bar = StatusBar(model="gpt-4")

        # Initial value
        assert status_bar.context_utilization == 0.0

        # Update and verify
        status_bar.update_context_usage(50.0)
        assert status_bar.context_utilization == 50.0

        # Update again
        status_bar.update_context_usage(85.0)
        assert status_bar.context_utilization == 85.0


class TestStatusFooterContextUsage:
    """Test status footer context usage display."""

    def test_context_usage_green_zone(self):
        """Test context usage displays in green for 0-70%."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(45.0)

        assert status_footer.context_utilization == 45.0

    def test_context_usage_yellow_zone(self):
        """Test context usage displays in yellow for 71-85%."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(78.0)

        assert status_footer.context_utilization == 78.0

    def test_context_usage_red_zone(self):
        """Test context usage displays in red for 86-100%."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(92.0)

        assert status_footer.context_utilization == 92.0

    def test_context_usage_boundary_at_71(self):
        """Test context usage boundary at 71% (yellow zone)."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(71.0)

        assert status_footer.context_utilization == 71.0

    def test_context_usage_boundary_at_86(self):
        """Test context usage boundary at 86% (red zone)."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(86.0)

        assert status_footer.context_utilization == 86.0

    def test_context_usage_zero(self):
        """Test context usage at 0%."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(0.0)

        assert status_footer.context_utilization == 0.0

    def test_context_usage_hundred(self):
        """Test context usage at 100%."""
        status_footer = StatusFooter(model="test-model")
        status_footer.update_context_usage(100.0)

        assert status_footer.context_utilization == 100.0

    def test_reactive_property_updates_on_change(self):
        """Test that changing context utilization triggers reactive update."""
        status_footer = StatusFooter(model="gpt-4")

        # Initial value
        assert status_footer.context_utilization == 0.0

        # Update and verify
        status_footer.update_context_usage(50.0)
        assert status_footer.context_utilization == 50.0

        # Update again
        status_footer.update_context_usage(85.0)
        assert status_footer.context_utilization == 85.0
