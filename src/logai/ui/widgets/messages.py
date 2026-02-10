"""Message widgets for chat interface."""

from textual.widgets import Static


class ChatMessage(Static):
    """Base class for chat messages."""

    pass


class UserMessage(ChatMessage):
    """Display user messages."""

    DEFAULT_CSS = """
    UserMessage {
        background: $primary;
        color: $text;
        padding: 1 2;
        margin: 1 0 1 4;
        border: solid $primary-darken-2;
    }
    """

    def __init__(self, content: str) -> None:
        """
        Initialize user message.

        Args:
            content: Message content
        """
        super().__init__(f"[bold]You:[/bold] {content}")
        self.add_class("user-message")


class AssistantMessage(ChatMessage):
    """Display assistant messages."""

    DEFAULT_CSS = """
    AssistantMessage {
        background: $panel;
        color: $text;
        padding: 1 2;
        margin: 1 4 1 0;
        border: solid $panel-darken-2;
    }
    """

    def __init__(self, content: str = "") -> None:
        """
        Initialize assistant message.

        Args:
            content: Message content (can be empty initially for streaming)
        """
        super().__init__(f"[bold cyan]Assistant:[/bold cyan] {content}")
        self.add_class("assistant-message")
        self._content = content

    def append_token(self, token: str) -> None:
        """
        Append a token to the message (for streaming).

        Args:
            token: Token to append
        """
        self._content += token
        self.update(f"[bold cyan]Assistant:[/bold cyan] {self._content}")


class SystemMessage(ChatMessage):
    """Display system notifications."""

    DEFAULT_CSS = """
    SystemMessage {
        background: $surface;
        color: $text-muted;
        padding: 1 2;
        margin: 1;
        text-align: center;
        text-style: italic;
    }
    """

    def __init__(self, content: str) -> None:
        """
        Initialize system message.

        Args:
            content: Message content
        """
        super().__init__(f"[dim]{content}[/dim]")
        self.add_class("system-message")


class LoadingIndicator(ChatMessage):
    """Animated loading indicator."""

    DEFAULT_CSS = """
    LoadingIndicator {
        background: $panel;
        color: $text-muted;
        padding: 1 2;
        margin: 1 4 1 0;
        border: solid $panel-darken-2;
    }
    """

    def __init__(self) -> None:
        """Initialize loading indicator."""
        super().__init__("[bold cyan]Assistant:[/bold cyan] [dim]Thinking...[/dim]")
        self.add_class("loading-indicator")


class ErrorMessage(ChatMessage):
    """Display error messages."""

    DEFAULT_CSS = """
    ErrorMessage {
        background: $error;
        color: $text;
        padding: 1 2;
        margin: 1;
        border: solid $error-darken-2;
    }
    """

    def __init__(self, content: str) -> None:
        """
        Initialize error message.

        Args:
            content: Error message content
        """
        super().__init__(f"[bold red]Error:[/bold red] {content}")
        self.add_class("error-message")
