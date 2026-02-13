"""Additional test to verify StatusFooter widget functionality."""

from unittest.mock import Mock

import pytest
from logai.ui.widgets.status_footer import StatusFooter
from textual.binding import Binding


def test_status_footer_has_compose_method():
    """Test that StatusFooter has the compose method for widget creation."""
    footer = StatusFooter()
    assert hasattr(footer, "compose")
    assert callable(footer.compose)


def test_status_footer_has_update_methods():
    """Test that StatusFooter has the necessary update methods."""
    footer = StatusFooter()
    assert hasattr(footer, "_update_status_display")
    assert callable(footer._update_status_display)
    assert hasattr(footer, "_update_shortcuts")
    assert callable(footer._update_shortcuts)


def test_status_display_built_correctly():
    """Test that status display text is built correctly for different statuses."""
    footer = StatusFooter()

    # These are simple tests that don't require a full Textual context
    # They verify the reactive attributes work

    # Test active status
    footer.set_status("Thinking...")
    assert footer.status == "Thinking..."

    # Test ready status
    footer.set_status("Ready")
    assert footer.status == "Ready"

    # Test tool execution status
    footer.set_status("Running tool: bash...")
    assert footer.status == "Running tool: bash..."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
