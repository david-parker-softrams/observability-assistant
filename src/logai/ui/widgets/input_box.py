"""Chat input widget with history support."""

from textual.widgets import Input


class ChatInput(Input):
    """Enhanced input widget for chat with command history."""

    DEFAULT_CSS = """
    ChatInput {
        dock: bottom;
        border: solid $primary;
        padding: 1 2;
        height: auto;
        background: $surface;
    }
    """

    def __init__(self) -> None:
        """Initialize chat input."""
        super().__init__(placeholder="Type your message (Enter to send, Ctrl+C to quit)...")
        self._history: list[str] = []
        self._history_index: int = -1
        self._current_input: str = ""

    def add_to_history(self, message: str) -> None:
        """
        Add a message to input history.

        Args:
            message: Message to add to history
        """
        if message.strip():
            self._history.append(message)
            self._history_index = len(self._history)

    def on_key(self, event: object) -> None:
        """
        Handle key events for history navigation.

        Args:
            event: Key event
        """
        # Note: For MVP, basic input history can be added post-MVP
        # Textual Input doesn't expose key events easily, so we'll keep it simple
        pass
