"""Status bar widget for displaying app status."""

from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Static):
    """Status bar showing connection status, cache stats, and model info."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 2;
    }
    """

    # Reactive attributes for dynamic updates
    status: reactive[str] = reactive("Ready")
    cache_hits: reactive[int] = reactive(0)
    cache_misses: reactive[int] = reactive(0)
    model: reactive[str] = reactive("Unknown")

    def __init__(self, model: str = "Unknown") -> None:
        """
        Initialize status bar.

        Args:
            model: LLM model name
        """
        super().__init__()
        self.model = model

    def on_mount(self) -> None:
        """Set up the status bar when mounted."""
        self.update_display()

    def watch_status(self, new_status: str) -> None:
        """
        React to status changes.

        Args:
            new_status: New status value
        """
        self.update_display()

    def watch_cache_hits(self, new_hits: int) -> None:
        """
        React to cache hits changes.

        Args:
            new_hits: New cache hits value
        """
        self.update_display()

    def watch_cache_misses(self, new_misses: int) -> None:
        """
        React to cache misses changes.

        Args:
            new_misses: New cache misses value
        """
        self.update_display()

    def watch_model(self, new_model: str) -> None:
        """
        React to model changes.

        Args:
            new_model: New model value
        """
        self.update_display()

    def update_display(self) -> None:
        """Update the status bar display."""
        # Calculate cache hit rate
        total = self.cache_hits + self.cache_misses
        if total > 0:
            hit_rate = (self.cache_hits / total) * 100
            cache_info = f"Cache: {self.cache_hits} hits ({hit_rate:.0f}%)"
        else:
            cache_info = "Cache: 0 hits"

        # Build status line
        status_line = f"Status: {self.status} | {cache_info} | Model: {self.model}"
        self.update(status_line)

    def set_status(self, status: str) -> None:
        """
        Set the connection status.

        Args:
            status: Status message
        """
        self.status = status

    def update_cache_stats(self, hits: int, misses: int) -> None:
        """
        Update cache statistics.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses
        """
        self.cache_hits = hits
        self.cache_misses = misses
