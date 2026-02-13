"""Combined footer with keyboard shortcuts and status information."""

import time

from rich.spinner import Spinner
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets._footer import FooterKey


class StatusFooter(Widget):
    """Footer showing keyboard shortcuts (left) and status info (right)."""

    DEFAULT_CSS = """
    StatusFooter {
        dock: bottom;
        height: 1;
        background: $panel;
        layout: horizontal;
    }

    StatusFooter > Horizontal {
        width: auto;
        height: 1;
        padding-right: 2;
    }

    StatusFooter FooterKey {
        margin-right: 1;
    }

    StatusFooter > Static {
        width: 1fr;
        height: 1;
        background: $panel;
        padding-left: 2;
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

    def compose(self) -> ComposeResult:
        """Create the footer structure with FooterKey widgets and status display."""
        # Create a horizontal container for shortcuts
        with Horizontal():
            # Get active bindings and create FooterKey widgets
            try:
                active_bindings = self.screen.active_bindings
                bindings = [
                    (binding, enabled)
                    for (_, binding, enabled, _) in active_bindings.values()
                    if binding.show
                ]

                for binding, enabled in bindings:
                    key_display = self.app.get_key_display(binding)
                    yield FooterKey(
                        key=binding.key,
                        key_display=key_display,
                        description=binding.description,
                        action=binding.action,
                        disabled=not enabled,
                    )
            except Exception:
                # If we can't get bindings during compose, that's okay
                # They might not be available yet
                pass

        # Create Static widget for status and context info
        yield Static(self._render_status_context(), id="status-context")

    def on_mount(self) -> None:
        """Start spinner timer when widget is mounted."""
        # Only set interval when mounted (event loop is running)
        if not self._spinner_timer_active:
            self.set_interval(0.1, self._update_spinner)  # Update spinner every 100ms
            self._spinner_timer_active = True

        # Update shortcuts after mount when bindings are available
        self._update_shortcuts()

    def on_unmount(self) -> None:
        """Cleanup timer when widget is unmounted."""
        # Textual automatically cancels timers set via set_interval,
        # but we reset our flag for proper state management
        self._spinner_timer_active = False

    def _update_spinner(self) -> None:
        """Update spinner animation (Phase 2)."""
        # Only refresh if status is active (not Ready or empty)
        if self.status and self.status != "Ready":
            # Update the status display Static widget
            self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the status/context display Static widget."""
        try:
            static = self.query_one("#status-context", Static)
            static.update(self._render_status_context())
        except Exception:
            # Widget might not be mounted yet
            pass

    def _update_shortcuts(self) -> None:
        """Update the shortcuts display when bindings change."""
        try:
            # Remove existing shortcuts
            shortcuts_container = self.query_one(Horizontal)
            shortcuts_container.remove_children()

            # Add new shortcuts
            active_bindings = self.screen.active_bindings
            bindings = [
                (binding, enabled)
                for (_, binding, enabled, _) in active_bindings.values()
                if binding.show
            ]

            for binding, enabled in bindings:
                key_display = self.app.get_key_display(binding)
                shortcuts_container.mount(
                    FooterKey(
                        key=binding.key,
                        key_display=key_display,
                        description=binding.description,
                        action=binding.action,
                        disabled=not enabled,
                    )
                )
        except Exception:
            # If we can't update shortcuts, that's okay
            pass

    def _is_status_active(self) -> bool:
        """Check if status indicates active work (Phase 2)."""
        return bool(self.status and self.status != "Ready")

    def watch_status(self, new_status: str) -> None:
        """
        React to status changes.

        Args:
            new_status: New status value
        """
        self._update_status_display()

    def watch_cache_hits(self, new_hits: int) -> None:
        """
        React to cache hits changes.

        Args:
            new_hits: New cache hits value
        """
        self._update_status_display()

    def watch_cache_misses(self, new_misses: int) -> None:
        """
        React to cache misses changes.

        Args:
            new_misses: New cache misses value
        """
        self._update_status_display()

    def watch_model(self, new_model: str) -> None:
        """
        React to model changes.

        Args:
            new_model: New model value
        """
        self._update_status_display()

    def watch_context_utilization(self, new_utilization: float) -> None:
        """
        React to context utilization changes.

        Args:
            new_utilization: New utilization percentage (0-100)
        """
        self._update_status_display()

    def _render_status_context(self) -> Text:
        """Render the status and context information for the Static widget."""
        # Build status message (Phase 1 + Phase 2 with spinner)
        status_display = Text()
        if self.status and self.status != "Ready":
            # Active status - show with spinner animation (Phase 2)
            current_time = time.time()
            spinner_text = self._spinner.render(time=current_time)
            # Extract just the spinner character
            if isinstance(spinner_text, Text):
                spinner_str = spinner_text.plain[0] if spinner_text.plain else "⠋"
            else:
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

        # Combine status and context with proper spacing
        result = Text()
        if len(status_display.plain) > 0:
            result.append_text(status_display)
            result.append("  ")
        result.append_text(context_text)

        return result

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
