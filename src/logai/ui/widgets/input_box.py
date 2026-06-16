"""Chat input widget with shell-style history navigation."""

from collections import deque

from textual import events
from textual.widgets import Input


class ChatInput(Input):
    """Input widget for chat with Up/Down arrow history navigation.

    Maintains a session-scoped, in-memory history of submitted messages.
    Pressing Up/Down while the input is focused navigates through that
    history, identical to how a Unix shell handles command history.  The
    draft text (whatever the user had typed before pressing Up) is saved
    and restored when they navigate back past the most-recent entry.

    History state:
        _history        deque[str]  — session history, newest at the right.
                                      maxlen=100 drops the oldest entry when full.
        _history_index  int         — current browse position.
                                      -1 = "not browsing" (at present).
                                       0 = oldest entry.
                                      len-1 = newest entry.
        _draft          str         — text saved on the first Up press so it can
                                      be restored when Down navigates past newest.
    """

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
        # History deque — appended to the right; index 0 is oldest, -1 is newest.
        self._history: deque[str] = deque(maxlen=100)
        # -1 = not browsing; 0..len-1 = position within history
        self._history_index: int = -1
        # Text present before the user first pressed Up this browse session
        self._draft: str = ""

    def add_to_history(self, message: str) -> None:
        """Add a submitted message to the history store.

        Resets the navigation position back to "not browsing" so the next
        Up keypress starts from the most-recent entry.  Whitespace-only
        strings are ignored — only meaningful content is stored.

        Args:
            message: The submitted message text.
        """
        if message.strip():
            self._history.append(message)
            # Reset browsing state; any unsaved draft is discarded on submit.
            self._history_index = -1
            self._draft = ""

    async def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrows for history navigation.

        Up  — move toward older entries (no wrap at the oldest).
        Down — move toward newer entries; navigating past the newest entry
               restores the draft text and returns to "not browsing" state.

        All other keys are left untouched so normal cursor movement (Left,
        Right, Home, End, …) continues to work as expected.

        Args:
            event: The Textual key event.
        """
        if event.key == "up":
            # Always consume the keypress so Textual's Input widget doesn't
            # do anything unexpected with it (Up has no default action in
            # Input, but we prevent_default for correctness).
            event.prevent_default()

            if not self._history:
                return  # Nothing to browse

            if self._history_index == -1:
                # First Up press this browse session: save current draft and
                # jump to the newest (rightmost) history entry.
                self._draft = self.value
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                # Move one step toward older entries.
                self._history_index -= 1
            # else: already at the oldest entry — silently no-op.

            self.value = self._history[self._history_index]
            self.cursor_position = len(self.value)

        elif event.key == "down":
            event.prevent_default()

            if self._history_index == -1:
                # Not currently browsing — nothing to do.
                return

            if self._history_index < len(self._history) - 1:
                # Move one step toward newer entries.
                self._history_index += 1
                self.value = self._history[self._history_index]
                self.cursor_position = len(self.value)
            else:
                # Navigated past the newest entry: restore draft and exit
                # browsing mode.
                self.value = self._draft
                self.cursor_position = len(self.value)
                self._history_index = -1
