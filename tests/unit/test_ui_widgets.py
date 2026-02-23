"""Tests for UI widgets."""

import pytest
from logai.ui.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    LoadingIndicator,
    SystemMessage,
    UserMessage,
)
from logai.ui.widgets.status_footer import StatusFooter
from logai.ui.widgets.tool_sidebar import ToolCallsSidebar
from textual.widget import Widget
from textual.widgets import Static


class TestUserMessage:
    """Tests for UserMessage widget."""

    def test_user_message_creation(self) -> None:
        """Test that user message is created correctly."""
        msg = UserMessage("Hello, world!")
        assert isinstance(msg, Static)
        # Check that the message was initialized (no exception thrown)
        assert msg is not None

    def test_user_message_has_class(self) -> None:
        """Test that user message has the correct CSS class."""
        msg = UserMessage("Test")
        assert msg.has_class("user-message")


class TestAssistantMessage:
    """Tests for AssistantMessage widget."""

    def test_assistant_message_creation(self) -> None:
        """Test that assistant message is created correctly."""
        msg = AssistantMessage("Hello from AI!")
        assert isinstance(msg, Static)
        # Check that the message was initialized (no exception thrown)
        assert msg is not None

    def test_assistant_message_has_class(self) -> None:
        """Test that assistant message has the correct CSS class."""
        msg = AssistantMessage("Test")
        assert msg.has_class("assistant-message")

    def test_assistant_message_append_token(self) -> None:
        """Test that tokens can be appended to assistant message."""
        msg = AssistantMessage("Hello")
        msg.append_token(" world")
        msg.append_token("!")
        # Check that the method works without exception
        assert msg._content == "Hello world!"


class TestSystemMessage:
    """Tests for SystemMessage widget."""

    def test_system_message_creation(self) -> None:
        """Test that system message is created correctly."""
        msg = SystemMessage("System notification")
        assert isinstance(msg, Static)
        # Check that the message was initialized (no exception thrown)
        assert msg is not None

    def test_system_message_has_class(self) -> None:
        """Test that system message has the correct CSS class."""
        msg = SystemMessage("Test")
        assert msg.has_class("system-message")


class TestLoadingIndicator:
    """Tests for LoadingIndicator widget."""

    def test_loading_indicator_creation(self) -> None:
        """Test that loading indicator is created correctly."""
        indicator = LoadingIndicator()
        assert isinstance(indicator, Static)
        assert indicator.has_class("loading-indicator")


class TestErrorMessage:
    """Tests for ErrorMessage widget."""

    def test_error_message_creation(self) -> None:
        """Test that error message is created correctly."""
        msg = ErrorMessage("An error occurred")
        assert isinstance(msg, Static)
        # Check that the message was initialized (no exception thrown)
        assert msg is not None

    def test_error_message_has_class(self) -> None:
        """Test that error message has the correct CSS class."""
        msg = ErrorMessage("Test error")
        assert msg.has_class("error-message")


class TestStatusFooter:
    """Tests for StatusFooter widget."""

    def test_status_footer_creation(self) -> None:
        """Test that status footer is created correctly."""
        status_footer = StatusFooter(model="claude-3-5-sonnet")
        assert isinstance(status_footer, Widget)
        assert status_footer.model == "claude-3-5-sonnet"

    def test_status_footer_set_status(self) -> None:
        """Test that status can be set."""
        status_footer = StatusFooter()
        status_footer.set_status("Thinking...")
        assert status_footer.status == "Thinking..."

    def test_status_footer_update_cache_stats(self) -> None:
        """Test that cache stats can be updated."""
        status_footer = StatusFooter()
        status_footer.update_cache_stats(10, 5)
        assert status_footer.cache_hits == 10
        assert status_footer.cache_misses == 5

    def test_status_footer_update_context_usage(self) -> None:
        """Test that context usage can be updated."""
        status_footer = StatusFooter()
        status_footer.update_context_usage(75.5)
        assert status_footer.context_utilization == 75.5


class TestToolCallsSidebar:
    """Tests for ToolCallsSidebar widget."""

    def test_sidebar_creation(self) -> None:
        """Test that tool sidebar is created correctly."""
        sidebar = ToolCallsSidebar()
        assert isinstance(sidebar, Static)
        assert sidebar._history == []

    # Note: The _format_result method no longer exists after Phase 1 & 2 refactoring.
    # The sidebar now uses a tree-based display with _add_result_node, _add_log_groups_node, etc.
    # Tests for the tree-based display would require more complex setup with Tree widgets.
