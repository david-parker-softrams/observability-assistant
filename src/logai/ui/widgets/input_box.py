"""Chat input widget."""

from textual.widgets import Input


class ChatInput(Input):
    """Input widget for chat."""

    DEFAULT_CSS = """
    ChatInput {
        border: solid $primary;
        padding: 1 2;
        height: auto;
        background: $surface;
    }
    """

    def __init__(self) -> None:
        """Initialize chat input."""
        super().__init__(
            placeholder="Type your question... (Ctrl+Q to quit, Cmd+V/Ctrl+Shift+V to paste)"
        )

    def add_to_history(self, message: str) -> None:
        """
        Add a message to input history.

        Args:
            message: Message to add to history
        """
        if message.strip():
            # TODO: Implement history navigation (deferred to future milestone)
            pass
