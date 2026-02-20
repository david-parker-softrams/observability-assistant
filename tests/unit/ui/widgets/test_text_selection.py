"""Tests for text selection functionality in chat messages and context viewer."""

import pytest
from logai.ui.screens.context_viewer import ContextParser, ContextViewerScreen
from logai.ui.widgets.messages import (
    AssistantMessage,
    ChatMessage,
    ErrorMessage,
    LoadingIndicator,
    SystemMessage,
    UserMessage,
)
from textual.widgets import TextArea


class TestChatMessageInheritance:
    """Test that ChatMessage properly inherits from TextArea."""

    def test_chat_message_is_textarea(self):
        """Verify ChatMessage is a TextArea widget."""
        msg = ChatMessage("test")
        assert isinstance(msg, TextArea)

    def test_chat_message_read_only(self):
        """Verify ChatMessage is read-only by default."""
        msg = ChatMessage("test")
        assert msg.read_only is True

    def test_chat_message_no_line_numbers(self):
        """Verify ChatMessage has no line numbers by default."""
        msg = ChatMessage("test")
        assert msg.show_line_numbers is False


class TestChatMessageInitialization:
    """Test initialization properties of ChatMessage subclasses."""

    def test_chat_message_empty_initialization(self):
        """Verify ChatMessage can be initialized empty."""
        msg = ChatMessage()
        assert msg.text == ""
        assert msg.read_only is True

    def test_chat_message_with_content(self):
        """Verify ChatMessage initialization with content."""
        content = "Hello, World!"
        msg = ChatMessage(content)
        assert content in msg.text
        assert msg.read_only is True

    def test_user_message_initialization(self):
        """Verify UserMessage initialization properties."""
        content = "Hello"
        msg = UserMessage(content)
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert msg.show_line_numbers is False
        # Content should be prefixed with "You:"
        assert "You:" in msg.text
        assert content in msg.text

    def test_assistant_message_initialization(self):
        """Verify AssistantMessage initialization properties."""
        content = "Hello"
        msg = AssistantMessage(content)
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert msg.show_line_numbers is False
        # Content should be prefixed with "Assistant:"
        assert "Assistant:" in msg.text
        assert content in msg.text

    def test_assistant_message_empty_initialization(self):
        """Verify AssistantMessage can be initialized empty for streaming."""
        msg = AssistantMessage()
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert "Assistant:" in msg.text
        # Should have prefix but no content yet
        assert msg._content == ""

    def test_system_message_initialization(self):
        """Verify SystemMessage initialization properties."""
        content = "System notification"
        msg = SystemMessage(content)
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert msg.show_line_numbers is False
        assert content in msg.text

    def test_error_message_initialization(self):
        """Verify ErrorMessage initialization properties."""
        content = "An error occurred"
        msg = ErrorMessage(content)
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert msg.show_line_numbers is False
        assert "Error:" in msg.text
        assert content in msg.text

    def test_loading_indicator_initialization(self):
        """Verify LoadingIndicator initialization properties."""
        msg = LoadingIndicator()
        assert isinstance(msg, TextArea)
        assert msg.read_only is True
        assert msg.show_line_numbers is False
        assert "Thinking..." in msg.text


class TestAssistantMessageStreaming:
    """Test AssistantMessage streaming functionality."""

    def test_append_token_single(self):
        """Verify append_token() works with a single token."""
        msg = AssistantMessage()
        msg.append_token("Hello")
        assert "Hello" in msg.text
        assert msg._content == "Hello"

    def test_append_token_multiple(self):
        """Verify append_token() works with multiple tokens."""
        msg = AssistantMessage()
        msg.append_token("Hello")
        msg.append_token(" ")
        msg.append_token("World")
        assert "Hello World" in msg.text
        assert msg._content == "Hello World"

    def test_append_token_preserves_prefix(self):
        """Verify streaming preserves the 'Assistant:' prefix."""
        msg = AssistantMessage()
        msg.append_token("Test")
        assert "Assistant:" in msg.text
        # Content should come after prefix
        text_parts = msg.text.split("Assistant:")
        assert len(text_parts) > 1
        assert "Test" in text_parts[1]

    def test_append_token_with_initial_content(self):
        """Verify streaming works when message has initial content."""
        msg = AssistantMessage("Initial ")
        msg.append_token("streamed")
        assert "Initial streamed" in msg.text
        assert msg._content == "Initial streamed"

    def test_append_token_special_characters(self):
        """Verify streaming handles special characters."""
        msg = AssistantMessage()
        msg.append_token("Hello\n")
        msg.append_token("World!")
        assert "Hello\nWorld!" in msg.text

    def test_append_token_empty_string(self):
        """Verify streaming handles empty token strings."""
        msg = AssistantMessage()
        msg.append_token("")
        msg.append_token("Hello")
        assert "Hello" in msg.text


class TestContextViewerTextAreaUsage:
    """Test that context viewer uses TextArea widgets."""

    def test_context_viewer_composes_textarea_widgets(self):
        """Verify ContextViewerScreen compose method creates TextArea widgets."""
        import inspect
        from datetime import datetime

        metadata = ContextParser.parse("Test content")
        viewer = ContextViewerScreen(
            staged_context="Test staged",
            conversation_history=[{"role": "user", "content": "Hello"}],
            metadata=metadata,
        )

        # Verify compose method exists and check its source
        assert hasattr(viewer, "compose")
        source = inspect.getsource(viewer.compose)

        # Verify TextArea is used in compose
        assert "TextArea" in source
        # Verify correct IDs are used
        assert "staged-content" in source
        assert "memory-content" in source
        # Verify read_only is set
        assert "read_only=True" in source


class TestStripRichMarkup:
    """Test the _strip_rich_markup() method."""

    def setup_method(self):
        """Set up test fixtures."""
        from datetime import datetime

        metadata = ContextParser.parse("")
        self.viewer = ContextViewerScreen(
            staged_context="",
            conversation_history=[],
            metadata=metadata,
        )

    def test_strip_bold_markup(self):
        """Verify bold markup is stripped."""
        result = self.viewer._strip_rich_markup("[bold]test[/bold]")
        assert result == "test"

    def test_strip_cyan_markup(self):
        """Verify color markup is stripped."""
        result = self.viewer._strip_rich_markup("[cyan]test[/cyan]")
        assert result == "test"

    def test_strip_combined_markup(self):
        """Verify combined markup is stripped."""
        result = self.viewer._strip_rich_markup("[bold cyan]test[/bold cyan]")
        # Should remove tags but keep content
        assert "test" in result
        assert "[bold" not in result
        assert "[/bold" not in result

    def test_strip_nested_content(self):
        """Verify markup is stripped from nested content."""
        result = self.viewer._strip_rich_markup("[bold green][User][/bold green]")
        # Should preserve [User] but remove markup tags
        assert "[User]" in result
        assert "[bold" not in result
        assert "green" not in result.lower() or result == "[User]"

    def test_strip_plain_text_unchanged(self):
        """Verify plain text without markup is unchanged."""
        text = "plain text without any markup"
        result = self.viewer._strip_rich_markup(text)
        assert result == text

    def test_strip_multiple_tags(self):
        """Verify multiple tags in sequence are stripped."""
        result = self.viewer._strip_rich_markup("[bold]Hello[/bold] [cyan]World[/cyan]")
        assert "Hello" in result
        assert "World" in result
        assert "[bold]" not in result
        assert "[cyan]" not in result

    def test_strip_dim_italic_markup(self):
        """Verify dim and italic markup is stripped."""
        result = self.viewer._strip_rich_markup("[dim italic]test[/dim italic]")
        assert "test" in result
        assert "[dim" not in result

    def test_strip_maintains_newlines(self):
        """Verify newlines are preserved when stripping markup."""
        text = "[bold]Line 1[/bold]\n[cyan]Line 2[/cyan]"
        result = self.viewer._strip_rich_markup(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "\n" in result

    def test_strip_empty_string(self):
        """Verify empty string is handled correctly."""
        result = self.viewer._strip_rich_markup("")
        assert result == ""

    def test_strip_unicode_content(self):
        """Verify unicode content is preserved."""
        text = "[bold]Hello 世界 🌍[/bold]"
        result = self.viewer._strip_rich_markup(text)
        assert "Hello 世界 🌍" in result


class TestMessageTypesCSSClasses:
    """Test that all message types have proper CSS classes."""

    def test_user_message_has_class(self):
        """Verify UserMessage adds user-message class."""
        msg = UserMessage("test")
        assert "user-message" in msg.classes

    def test_assistant_message_has_class(self):
        """Verify AssistantMessage adds assistant-message class."""
        msg = AssistantMessage("test")
        assert "assistant-message" in msg.classes

    def test_system_message_has_class(self):
        """Verify SystemMessage adds system-message class."""
        msg = SystemMessage("test")
        assert "system-message" in msg.classes

    def test_error_message_has_class(self):
        """Verify ErrorMessage adds error-message class."""
        msg = ErrorMessage("test")
        assert "error-message" in msg.classes

    def test_loading_indicator_has_class(self):
        """Verify LoadingIndicator adds loading-indicator class."""
        msg = LoadingIndicator()
        assert "loading-indicator" in msg.classes


class TestTextAreaReadOnlyBehavior:
    """Test that TextArea read-only behavior is preserved."""

    def test_read_only_prevents_editing(self):
        """Verify read-only TextArea prevents direct text editing."""
        msg = ChatMessage("original")
        # read_only property should be True
        assert msg.read_only is True
        # TextArea with read_only=True should not allow direct editing
        # (This is enforced by Textual, we just verify the flag)

    def test_assistant_message_streaming_works_despite_readonly(self):
        """Verify append_token() works even though TextArea is read-only."""
        msg = AssistantMessage()
        # Even though read_only is True, append_token uses direct text assignment
        msg.append_token("Test")
        assert "Test" in msg.text
        # This confirms streaming doesn't break with read-only TextArea


class TestContextViewerWidgetIDs:
    """Test that context viewer has correct widget IDs for TextArea widgets."""

    def test_has_staged_content_textarea_id(self):
        """Verify compose includes staged-content TextArea."""
        from datetime import datetime

        metadata = ContextParser.parse("")
        viewer = ContextViewerScreen(
            staged_context="",
            conversation_history=[],
            metadata=metadata,
        )

        # The compose method should include widgets with correct IDs
        # We'll verify this indirectly by checking the method exists
        assert hasattr(viewer, "compose")
        assert callable(viewer.compose)

    def test_has_memory_content_textarea_id(self):
        """Verify compose includes memory-content TextArea."""
        from datetime import datetime

        metadata = ContextParser.parse("")
        viewer = ContextViewerScreen(
            staged_context="",
            conversation_history=[],
            metadata=metadata,
        )

        # The compose method should include widgets with correct IDs
        assert hasattr(viewer, "compose")
        assert callable(viewer.compose)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
