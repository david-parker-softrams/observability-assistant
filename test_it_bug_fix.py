#!/usr/bin/env python3
"""Manual test to verify the 'it' bug fix."""

from logai.ui.widgets.status_footer import StatusFooter
from textual.app import App
from textual.binding import Binding
from textual.widgets import Static


class TestApp(App):
    """Test app to verify status footer fix."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #test-info {
        height: auto;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }

    StatusFooter {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True, show=True),
        Binding("f1", "test_1", "◀ Logs", show=True),
        Binding("f2", "test_2", "Logs ►", show=True),
        Binding("f3", "test_3", "◀ Tools", show=True),
        Binding("f4", "test_4", "Tools ►", show=True),
        Binding("1", "set_ready", "Set Ready", show=True),
        Binding("2", "set_thinking", "Set Thinking", show=True),
        Binding("3", "set_tool", "Set Tool", show=True),
    ]

    def compose(self):
        yield Static(
            "[bold]Status Footer 'it' Bug Fix Test[/bold]\n\n"
            "Check the footer below:\n"
            "1. There should be NO 'it' text between shortcuts and status\n"
            "2. When status is 'Ready', it should appear dimmed (but NOT italic due to our fix)\n"
            "3. When status is active (Thinking/Running tool), it should show with spinner\n\n"
            "Press keys to test:\n"
            "  [cyan]1[/cyan] - Set status to 'Ready' (idle, dimmed)\n"
            "  [cyan]2[/cyan] - Set status to 'Thinking...' (active, with spinner)\n"
            "  [cyan]3[/cyan] - Set status to 'Running tool: test...' (active)\n"
            "  [cyan]Ctrl+C[/cyan] - Quit\n\n"
            "Current status: [yellow]Thinking...[/yellow]",
            id="test-info",
        )
        self.status_footer = StatusFooter(model="test-model-gpt-4")
        self.status_footer.status = "Thinking..."
        self.status_footer.update_cache_stats(hits=10, misses=3)
        self.status_footer.update_context_usage(45.2)
        yield self.status_footer

    def action_set_ready(self) -> None:
        """Set status to Ready."""
        self.status_footer.set_status("Ready")
        info = self.query_one("#test-info", Static)
        info.update(
            info.renderable.plain.replace("Current status: Thinking...", "Current status: Ready")
        )

    def action_set_thinking(self) -> None:
        """Set status to Thinking."""
        self.status_footer.set_status("Thinking...")
        info = self.query_one("#test-info", Static)
        info.update(
            info.renderable.plain.replace("Current status: Ready", "Current status: Thinking...")
        )

    def action_set_tool(self) -> None:
        """Set status to Running tool."""
        self.status_footer.set_status("Running tool: test...")
        info = self.query_one("#test-info", Static)
        info.update(
            info.renderable.plain.replace(
                "Current status: Ready", "Current status: Running tool..."
            )
        )


if __name__ == "__main__":
    app = TestApp()
    app.run()
