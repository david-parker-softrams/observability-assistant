"""Combined footer with keyboard shortcuts and status information."""

import time

from rich.spinner import Spinner
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class StatusFooter(Widget):
    """Footer showing keyboard shortcuts (left) and status info (right)."""

    DEFAULT_CSS = """
    StatusFooter {
        dock: bottom;
        height: 1;
        background: $panel;
    }
    """

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
        # Get terminal width to calculate spacing
        width = self.size.width

        # Handle extremely narrow terminals gracefully
        if width < 10:
            return Text(self.status or "Ready", style="dim")

        # Build keyboard shortcuts text manually
        # Footer uses compose() with child widgets, but we need everything in one Text for our layout
        shortcuts_text = self._render_shortcuts()

        # Build status message for center (Phase 1 + Phase 2 with spinner)
        # Display agent activity status prominently
        status_display = Text()
        if self.status and self.status != "Ready":
            # Active status - show with spinner animation (Phase 2)
            # Use current time for spinner animation
            current_time = time.time()
            spinner_text = self._spinner.render(time=current_time)
            # Extract just the spinner character (first character of rendered output)
            # Spinner.render() returns a Text object, use .plain to get text without style markup
            if isinstance(spinner_text, Text):
                spinner_str = spinner_text.plain[0] if spinner_text.plain else "⠋"
            else:
                # Fallback: convert to string and take first character
                spinner_str_full = str(spinner_text).strip()
                spinner_str = spinner_str_full[0] if spinner_str_full else "⠋"
            status_display.append(f"{spinner_str} ", style="yellow")
            status_display.append(self.status, style="bold yellow")
        elif self.status:
            # Idle status - show dimmed
            status_display.append(self.status, style="dim")

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

        # Calculate widths
        shortcuts_width = len(shortcuts_text.plain) if shortcuts_text else 0
        status_width = len(status_display.plain)
        context_width = len(context_text.plain)

        # Calculate layout: [shortcuts] [status] [padding] [context]
        # Minimum spacing between sections
        min_spacing = 2

        # Calculate required space
        sections_with_content = sum(
            [
                1 if shortcuts_width > 0 else 0,
                1 if status_width > 0 else 0,
                1,  # context always shown
            ]
        )
        required_spacing = max(0, sections_with_content - 1) * min_spacing
        total_content_width = shortcuts_width + status_width + context_width + required_spacing

        if total_content_width <= width:
            # Enough space for everything
            result = Text()

            # Add shortcuts
            if shortcuts_text and shortcuts_width > 0:
                result.append_text(shortcuts_text)

            # Add status with spacing
            if status_width > 0:
                if shortcuts_width > 0:
                    result.append("  ")  # Spacing after shortcuts
                result.append_text(status_display)

            # Add padding before context info
            used_width = len(result.plain)
            padding_needed = width - used_width - context_width
            if padding_needed > 0:
                result.append(" " * padding_needed)

            # Add context info
            result.append_text(context_text)
            return result
        else:
            # Limited space - prioritize: shortcuts > status > context
            if shortcuts_width == 0:
                # No shortcuts - show status if present, otherwise context
                if status_width > 0 and status_width <= width:
                    return status_display
                else:
                    return context_text
            else:
                # Have shortcuts (shortcuts_text is not None if shortcuts_width > 0)
                available_after_shortcuts = width - shortcuts_width - min_spacing

                if status_width > 0 and status_width <= available_after_shortcuts:
                    # Can fit shortcuts + status
                    result = Text()
                    if shortcuts_text:  # Type guard for mypy
                        result.append_text(shortcuts_text)
                    result.append("  ")
                    result.append_text(status_display)

                    # Try to fit context too if there's space
                    available_after_status = width - len(result.plain) - min_spacing
                    if context_width <= available_after_status:
                        result.append("  ")
                        result.append_text(context_text)

                    return result
                else:
                    # Only room for shortcuts, maybe context
                    available_after_shortcuts = width - shortcuts_width - min_spacing
                    if context_width <= available_after_shortcuts:
                        result = Text()
                        if shortcuts_text:  # Type guard for mypy
                            result.append_text(shortcuts_text)
                        # Add padding
                        padding = width - shortcuts_width - context_width
                        if padding > 0:
                            result.append(" " * padding)
                        result.append_text(context_text)
                        return result
                    else:
                        # Just show shortcuts
                        if shortcuts_text:  # Type guard for mypy
                            return shortcuts_text
                        else:
                            # Shouldn't reach here, but return context as fallback
                            return context_text

    def _render_shortcuts(self) -> Text | None:
        """
        Render keyboard shortcuts into a Text object.

        Returns:
            Text object with keyboard shortcuts, or None if no shortcuts available
        """
        try:
            # Get active bindings from screen (same as Footer does)
            active_bindings = self.screen.active_bindings
            bindings = [
                (binding, enabled)
                for (_, binding, enabled, _) in active_bindings.values()
                if binding.show
            ]

            if not bindings:
                return None

            # Build shortcuts text
            shortcuts = Text()
            for i, (binding, enabled) in enumerate(bindings):
                if i > 0:
                    shortcuts.append(" ")

                # Get key display (same as Footer does)
                key_display = self.app.get_key_display(binding)

                # Format: KEY Description
                # Use styles similar to Footer
                if enabled:
                    shortcuts.append(key_display, style="bold cyan")
                    shortcuts.append(" ")
                    shortcuts.append(binding.description, style="white")
                else:
                    shortcuts.append(key_display, style="dim")
                    shortcuts.append(" ")
                    shortcuts.append(binding.description, style="dim")

            return shortcuts
        except Exception:
            # If anything goes wrong getting bindings, return None
            return None

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
