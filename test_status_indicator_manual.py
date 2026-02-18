#!/usr/bin/env python3
"""
Manual Testing Script for Status Indicator Feature

This script provides a controlled environment to test the status footer
without needing to run full queries. It simulates different status states
and allows visual inspection of the status indicator behavior.
"""

import asyncio
import time
from typing import Any

from logai.ui.widgets.status_footer import StatusFooter
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Header, Static


class StatusTestApp(App[None]):
    """Test app for status footer."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #content {
        height: 1fr;
        padding: 2;
    }

    .test-section {
        margin: 1 0;
        padding: 1 2;
        border: solid $primary;
    }
    """

    BINDINGS = [
        Binding("1", "test_ready", "Test Ready", show=True),
        Binding("2", "test_thinking", "Test Thinking", show=True),
        Binding("3", "test_single_tool", "Test Single Tool", show=True),
        Binding("4", "test_multi_tool", "Test Multi Tool", show=True),
        Binding("5", "test_processing", "Test Processing", show=True),
        Binding("6", "test_error", "Test Error", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        """Initialize test app."""
        super().__init__()
        self.status_footer: StatusFooter | None = None
        self.test_log: list[str] = []
        self.multi_tool_task: asyncio.Task[Any] | None = None

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()

        with VerticalScroll(id="content"):
            yield Static(
                "[bold cyan]Status Footer Manual Test[/bold cyan]\n\n"
                "Press the numbered keys to test different status states:\n\n"
                "[yellow]1[/yellow] - Ready state (idle, dimmed)\n"
                "[yellow]2[/yellow] - Thinking... (active with spinner)\n"
                "[yellow]3[/yellow] - Running tool: list_log_groups... (single tool)\n"
                "[yellow]4[/yellow] - Running tool 1/3... (multi-tool simulation)\n"
                "[yellow]5[/yellow] - Processing results... (after tool completion)\n"
                "[yellow]6[/yellow] - Tool error: search_logs (error state)\n"
                "[yellow]Q[/yellow] - Quit\n\n"
                "[dim]Watch the footer below to see status changes.[/dim]",
                classes="test-section",
            )

            # Log section
            self.log_display = Static(
                "[bold]Test Log:[/bold]\n" + self._format_log(),
                classes="test-section",
            )
            yield self.log_display

        # Status footer at bottom
        self.status_footer = StatusFooter(model="qwen3:32b (test)")
        yield self.status_footer

    def _format_log(self) -> str:
        """Format log messages."""
        if not self.test_log:
            return "[dim]No tests run yet...[/dim]"
        return "\n".join(f"  • {msg}" for msg in self.test_log[-10:])

    def _add_log(self, message: str) -> None:
        """Add log message and update display."""
        timestamp = time.strftime("%H:%M:%S")
        self.test_log.append(f"[dim]{timestamp}[/dim] {message}")
        if hasattr(self, "log_display"):
            self.log_display.update("[bold]Test Log:[/bold]\n" + self._format_log())

    def action_test_ready(self) -> None:
        """Test Ready state."""
        if self.status_footer:
            self.status_footer.set_status("Ready")
            self._add_log("✓ Set status to [italic]Ready[/italic] (should be dim)")

    def action_test_thinking(self) -> None:
        """Test Thinking state."""
        if self.status_footer:
            self.status_footer.set_status("Thinking...")
            self._add_log("✓ Set status to [yellow]Thinking...[/yellow] (should show spinner)")

    def action_test_single_tool(self) -> None:
        """Test single tool running."""
        if self.status_footer:
            self.status_footer.set_status("Running tool: list_log_groups...")
            self._add_log("✓ Set status to [yellow]Running tool: list_log_groups...[/yellow]")

    def action_test_multi_tool(self) -> None:
        """Test multi-tool progress."""
        if self.multi_tool_task and not self.multi_tool_task.done():
            self._add_log("⚠ Multi-tool test already running")
            return

        self.multi_tool_task = asyncio.create_task(self._run_multi_tool_test())

    async def _run_multi_tool_test(self) -> None:
        """Simulate multi-tool execution."""
        if not self.status_footer:
            return

        tools = [
            "list_log_groups",
            "search_logs",
            "fetch_logs",
        ]

        for i, tool in enumerate(tools, 1):
            self.status_footer.set_status(f"Running tool {i}/{len(tools)}: {tool}...")
            self._add_log(
                f"✓ Set status to [yellow]Running tool {i}/{len(tools)}: {tool}...[/yellow]"
            )
            await asyncio.sleep(2)  # Simulate tool execution time

        self.status_footer.set_status("Processing results...")
        self._add_log("✓ Set status to [yellow]Processing results...[/yellow]")
        await asyncio.sleep(1)

        self.status_footer.set_status("Ready")
        self._add_log("✓ Set status to [italic]Ready[/italic]")

    def action_test_processing(self) -> None:
        """Test processing state."""
        if self.status_footer:
            self.status_footer.set_status("Processing results...")
            self._add_log("✓ Set status to [yellow]Processing results...[/yellow]")

    def action_test_error(self) -> None:
        """Test error state."""
        if self.status_footer:
            self.status_footer.set_status("Tool error: search_logs")
            self._add_log("✓ Set status to [red]Tool error: search_logs[/red]")

    def action_quit(self) -> None:
        """Quit the app."""
        self.exit()

    def on_mount(self) -> None:
        """Initialize status footer after mount."""
        if self.status_footer:
            # Set initial status
            self.status_footer.set_status("Ready")

            # Set some cache stats for visual testing
            self.status_footer.update_cache_stats(hits=12, misses=5)

            # Set context utilization (45%)
            self.status_footer.update_context_usage(45.2)

            self._add_log("✓ Status footer initialized with test data")


def main() -> None:
    """Run the test app."""
    print("\n" + "=" * 70)
    print("STATUS FOOTER MANUAL TEST")
    print("=" * 70)
    print("\nThis app will launch a TUI to test the status footer behavior.")
    print("Use the numbered keys to test different status states.")
    print("Watch the footer at the bottom for status changes.\n")
    print("Press ENTER to continue...")
    input()

    app = StatusTestApp()
    app.run()

    print("\n" + "=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)
    print("\nTest log:")
    for log in app.test_log:
        # Strip Rich markup for console output
        import re

        clean_log = re.sub(r"\[.*?\]", "", log)
        print(f"  {clean_log}")
    print()


if __name__ == "__main__":
    main()
