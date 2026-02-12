"""Combined footer with keyboard shortcuts and status information."""

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Footer


class StatusFooter(Footer):
    """Footer showing keyboard shortcuts (left) and status info (right)."""

    # Reactive attributes for dynamic status updates
    status: reactive[str] = reactive("Ready")
    cache_hits: reactive[int] = reactive(0)
    cache_misses: reactive[int] = reactive(0)
    model: reactive[str] = reactive("Unknown")
    context_utilization: reactive[float] = reactive(0.0)

    def __init__(self, model: str = "Unknown") -> None:
        """
        Initialize status footer.

        Args:
            model: LLM model name
        """
        super().__init__()
        self.model = model

    def watch_status(self, new_status: str) -> None:
        """
        React to status changes.

        Args:
            new_status: New status value
        """
        self.refresh()

    def watch_cache_hits(self, new_hits: int) -> None:
        """
        React to cache hits changes.

        Args:
            new_hits: New cache hits value
        """
        self.refresh()

    def watch_cache_misses(self, new_misses: int) -> None:
        """
        React to cache misses changes.

        Args:
            new_misses: New cache misses value
        """
        self.refresh()

    def watch_model(self, new_model: str) -> None:
        """
        React to model changes.

        Args:
            new_model: New model value
        """
        self.refresh()

    def watch_context_utilization(self, new_utilization: float) -> None:
        """
        React to context utilization changes.

        Args:
            new_utilization: New utilization percentage (0-100)
        """
        self.refresh()

    def render(self) -> Text:
        """Render the footer with shortcuts on left and status on right."""
        # Get the base footer rendering (keyboard shortcuts)
        base_render = super().render()

        # Build status info for right side
        # Calculate cache hit rate
        total = self.cache_hits + self.cache_misses
        if total > 0:
            hit_rate = (self.cache_hits / total) * 100
            cache_info = f"Cache: {self.cache_hits}/{total} ({hit_rate:.0f}%)"
        else:
            cache_info = "Cache: 0/0"

        # Format context utilization with color coding
        if self.context_utilization >= 86:
            context_color = "red"
        elif self.context_utilization >= 71:
            context_color = "yellow"
        else:
            context_color = "green"

        # Build status text
        status_text = Text()
        status_text.append(cache_info, style="dim")
        status_text.append(" | ", style="dim")
        status_text.append("Context: ", style="dim")
        status_text.append(f"{self.context_utilization:.0f}%", style=context_color)
        status_text.append(" | ", style="dim")
        status_text.append(self.model, style="dim")

        # Get terminal width to calculate spacing
        width = self.size.width
        shortcuts_width = len(base_render.plain)
        status_width = len(status_text.plain)

        # Calculate padding needed to push status to the right
        padding_needed = width - shortcuts_width - status_width

        if padding_needed > 0:
            # Add padding to base render and append status
            result = Text(base_render)
            result.append(" " * padding_needed)
            result.append(status_text)
            return result
        else:
            # Not enough space, just show shortcuts (footer takes priority)
            return base_render

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
