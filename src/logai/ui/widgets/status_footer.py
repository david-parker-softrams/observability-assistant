"""Combined footer with keyboard shortcuts and status information."""

import logging
import time

from rich.spinner import Spinner
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets._footer import FooterKey

logger = logging.getLogger(__name__)


class ClickableContextLabel(Static):
    """Clickable label for status and context display with hover feedback."""

    # Enable focus to allow hover pseudo-class to work properly
    can_focus = False  # Keep False but enable mouse interaction via CSS

    DEFAULT_CSS = """
    ClickableContextLabel {
        width: auto;
        max-width: 999;
        content-align: right top;
        &:hover {
            background: $block-hover-background;
        }
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the clickable context label."""
        super().__init__(*args, **kwargs)

    def on_click(self, event: Click) -> None:
        """Handle click - emit request to view context only if clicking on text.

        Args:
            event: Click event with position information
        """
        # Get the actual rendered text content
        renderable = self.render()
        if hasattr(renderable, "plain"):
            text_length = len(renderable.plain)
        else:
            text_length = len(str(renderable))

        # Calculate the actual text width including padding
        # The widget has padding: 0 2 (left and right padding of 2)
        padding_left = 2

        # Click position is relative to the widget (0-indexed from left edge)
        click_x = event.x

        # Text starts after left padding and ends at: padding_left + text_length
        text_start = padding_left
        text_end = padding_left + text_length

        # Only trigger if click is within the actual text bounds
        if text_start <= click_x < text_end:
            # Post the message to parent (StatusFooter)
            self.post_message(StatusFooter.ContextViewRequested())
        else:
            # Stop event propagation to prevent any parent widgets from handling it
            event.stop()


class StatusFooter(Widget):
    """Footer showing keyboard shortcuts (left) and status info (right)."""

    class ContextViewRequested(Message):
        """Emitted when user clicks the context label to view context."""

        pass

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
        content-align: left middle;
    }

    StatusFooter FooterKey {
        margin-right: 1;
    }

    StatusFooter > Static#status-info {
        width: auto;
        height: 1;
        background: $panel;
        padding: 0 2;
    }

    StatusFooter > ClickableContextLabel {
        width: auto;
        height: 1;
        background: $panel;
        padding: 0 2;
    }
    """

    # Reactive attributes for dynamic status updates
    status: reactive[str] = reactive("Ready")
    cache_hits: reactive[int] = reactive(0)
    cache_misses: reactive[int] = reactive(0)
    model: reactive[str] = reactive("Unknown")
    context_utilization: reactive[float] = reactive(0.0)
    context_used_tokens: reactive[int] = reactive(0)  # NEW
    context_total_tokens: reactive[int] = reactive(0)  # NEW

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
        # Create a horizontal container for shortcuts (left side)
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

        # Non-clickable status info in middle-right (Ready + Cache stats)
        yield Static(self._render_status_info(), id="status-info")

        # Clickable context info on far right (Context utilization + Model)
        yield ClickableContextLabel(self._render_context_info(), id="context-clickable")

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
        """Update both the status info and context info display widgets."""
        try:
            # Update non-clickable status info widget
            status_widget = self.query_one("#status-info", Static)
            status_widget.update(self._render_status_info())

            # Update clickable context info widget
            context_widget = self.query_one("#context-clickable", ClickableContextLabel)
            context_widget.update(self._render_context_info())
        except NoMatches:
            # Widget not yet mounted, skip update
            pass
        except Exception as e:
            # Unexpected error - log it
            logger.error(f"Unexpected error updating status display: {e}")

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

    def _render_status_info(self) -> Text:
        """Render non-clickable status information (Ready + Cache stats)."""
        result = Text()

        # Build status message (Phase 1 + Phase 2 with spinner)
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
            result.append(f"{spinner_str} ", style="yellow")
            result.append(self.status, style="bold yellow")
        elif self.status:
            # Idle status - show dimmed
            result.append(self.status, style="dim")

        # Add cache stats
        total = self.cache_hits + self.cache_misses
        if total > 0:
            hit_rate = (self.cache_hits / total) * 100
            cache_info = f"Cache: {self.cache_hits}/{total} ({hit_rate:.0f}%)"
        else:
            cache_info = "Cache: 0/0"

        if len(result.plain) > 0:
            result.append("  ", style="dim")
        result.append(cache_info, style="dim")

        return result

    def _render_context_info(self) -> Text:
        """Render clickable context information (Context utilization + Model name)."""
        # Format context utilization with enhanced color coding
        if self.context_utilization >= 95:
            context_color = "red bold"
            context_prefix = "(!!) "
        elif self.context_utilization >= 85:
            # Aligned with the 85% toast notification in _log_budget_status():
            # both the visual color change and the user-facing warning fire together.
            context_color = "red"
            context_prefix = "(!) "
        elif self.context_utilization >= 71:
            context_color = "yellow"
            context_prefix = ""
        else:
            context_color = "green"
            context_prefix = ""

        # Build context text with absolute values
        context_text = Text()
        context_text.append("Context: ", style="dim")

        # Show tokens in K format (e.g., "25.5K/32K") if available
        if self.context_total_tokens > 0:
            used_k = self.context_used_tokens / 1000
            total_k = self.context_total_tokens / 1000
            context_text.append(context_prefix, style=context_color)
            context_text.append(f"{used_k:.1f}K/{total_k:.0f}K ", style=context_color)
            context_text.append(f"({self.context_utilization:.0f}%)", style=context_color)
        else:
            # Fallback to percentage-only display if absolute values not available
            context_text.append(context_prefix, style=context_color)
            context_text.append(f"{self.context_utilization:.0f}%", style=context_color)
        context_text.append(" | ", style="dim")
        context_text.append(self.model, style="dim")

        return context_text

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

    def update_context_usage(
        self, utilization_pct: float, used_tokens: int = 0, total_tokens: int = 0
    ) -> None:
        """
        Update context usage display.

        Args:
            utilization_pct: Context utilization percentage (0-100)
            used_tokens: Currently used tokens (optional)
            total_tokens: Total available tokens (optional)
        """
        self.context_utilization = utilization_pct
        self.context_used_tokens = used_tokens
        self.context_total_tokens = total_tokens
