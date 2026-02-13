"""Combined footer with keyboard shortcuts and status information."""

import time

from rich.spinner import Spinner
from rich.text import Text
from textual.reactive import reactive
from textual.renderables.blank import Blank
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
        # Phase 2: Spinner for active status indication
        self._spinner = Spinner("dots2", style="yellow")
        self._spinner_timer_active = False

    def on_mount(self) -> None:
        """Start spinner timer when widget is mounted."""
        # Only set interval when mounted (event loop is running)
        if not self._spinner_timer_active:
            self.set_interval(0.1, self._update_spinner)  # Update spinner every 100ms
            self._spinner_timer_active = True

    def _update_spinner(self) -> None:
        """Update spinner animation (Phase 2)."""
        # Only refresh if status is active (not Ready or empty)
        if self.status and self.status != "Ready":
            self.refresh()

    def _is_status_active(self) -> bool:
        """Check if status indicates active work (Phase 2)."""
        return bool(self.status and self.status != "Ready")

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
        """Render the footer with shortcuts on left, status center, and info on right."""
        # Get the base footer rendering (keyboard shortcuts)
        base_render = super().render()

        # Build status message for left/center (Phase 1 + Phase 2 with spinner)
        # Display agent activity status prominently
        status_display = Text()
        if self.status and self.status != "Ready":
            # Active status - show with spinner animation (Phase 2)
            # Use current time for spinner animation
            current_time = time.time()
            spinner_text = self._spinner.render(time=current_time)
            # Extract just the spinner character (first character of rendered output)
            spinner_str = str(spinner_text).strip() if spinner_text else "⠋"
            status_display.append(f"{spinner_str} ", style="yellow")
            status_display.append(self.status, style="bold yellow")
        elif self.status:
            # Idle status - show dimmed
            status_display.append(self.status, style="dim italic")

        # Build context info for right side
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

        # Build context text for right side
        context_text = Text()
        context_text.append(cache_info, style="dim")
        context_text.append(" | ", style="dim")
        context_text.append("Context: ", style="dim")
        context_text.append(f"{self.context_utilization:.0f}%", style=context_color)
        context_text.append(" | ", style="dim")
        context_text.append(self.model, style="dim")

        # Get terminal width to calculate spacing
        width = self.size.width

        # Handle different render types from parent Footer
        # Footer returns Blank when there are no bindings to show
        # Footer returns Text when there are keyboard shortcuts
        if isinstance(base_render, Blank):
            # No shortcuts to show
            shortcuts_width = 0
            shortcuts_text = None
        elif isinstance(base_render, Text):
            # base_render is a Text object with keyboard shortcuts
            shortcuts_width = len(base_render.plain)
            shortcuts_text = base_render
        else:
            # Fallback for unknown types - assume no shortcuts
            shortcuts_width = 0
            shortcuts_text = None

        status_width = len(status_display.plain)
        context_width = len(context_text.plain)

        # Calculate layout: [shortcuts] [status] [padding] [context]
        # Minimum spacing between sections
        min_spacing = 2
        total_content_width = shortcuts_width + status_width + context_width + (min_spacing * 2)

        if total_content_width <= width:
            # Enough space for everything
            padding_needed = width - shortcuts_width - status_width - context_width - min_spacing

            result = Text()
            if shortcuts_text:
                result.append_text(shortcuts_text)

            # Add status with spacing
            if status_width > 0:
                result.append("  ")  # Min spacing
                result.append_text(status_display)

            # Add padding before context info
            if padding_needed > 0:
                result.append(" " * padding_needed)

            # Add context info
            result.append_text(context_text)
            return result
        else:
            # Limited space - prioritize status over context info
            if not shortcuts_text:
                # No shortcuts - show status if present, otherwise context
                if status_width > 0:
                    return status_display
                else:
                    return context_text
            else:
                # Have shortcuts - try to fit status, fallback to shortcuts only
                available = width - shortcuts_width - min_spacing
                if status_width > 0 and status_width <= available:
                    result = Text()
                    result.append_text(shortcuts_text)
                    result.append("  ")
                    result.append_text(status_display)
                    return result
                else:
                    # Just show shortcuts
                    return shortcuts_text

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
