"""Tests for UI widgets."""

import pytest
from textual.widgets import Static

from logai.ui.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    LoadingIndicator,
    SystemMessage,
    UserMessage,
)
from logai.ui.widgets.status_bar import StatusBar


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


class TestStatusBar:
    """Tests for StatusBar widget."""

    def test_status_bar_creation(self) -> None:
        """Test that status bar is created correctly."""
        status_bar = StatusBar(model="claude-3-5-sonnet")
        assert isinstance(status_bar, Static)
        assert status_bar.model == "claude-3-5-sonnet"

    def test_status_bar_set_status(self) -> None:
        """Test that status can be set."""
        status_bar = StatusBar()
        status_bar.set_status("Thinking...")
        assert status_bar.status == "Thinking..."

    def test_status_bar_update_cache_stats(self) -> None:
        """Test that cache stats can be updated."""
        status_bar = StatusBar()
        status_bar.update_cache_stats(10, 5)
        assert status_bar.cache_hits == 10
        assert status_bar.cache_misses == 5
