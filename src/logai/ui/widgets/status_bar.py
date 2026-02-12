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
    context_utilization: reactive[float] = reactive(0.0)

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

    def watch_context_utilization(self, new_utilization: float) -> None:
        """
        React to context utilization changes.

        Args:
            new_utilization: New utilization percentage (0-100)
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

        # Format context utilization with color coding
        if self.context_utilization >= 86:
            context_color = "red"
        elif self.context_utilization >= 71:
            context_color = "yellow"
        else:
            context_color = "green"

        context_info = (
            f"Context: [{context_color}]{self.context_utilization:.0f}%[/{context_color}]"
        )

        # Build status line
        status_line = f"Status: {self.status} | {cache_info} | {context_info} | Model: {self.model}"
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

    def update_context_usage(self, utilization_pct: float) -> None:
        """
        Update context usage display.

        Args:
            utilization_pct: Context utilization percentage (0-100)
        """
        self.context_utilization = utilization_pct
