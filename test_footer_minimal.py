#!/usr/bin/env python3
"""Minimal test to see if Footer adds extra text to our render() output."""

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer


class MinimalFooter(Footer):
    """Minimal footer that just returns a simple text string."""

    def render(self) -> Text:
        """Return a simple text object."""
        result = Text("EXACT_TEXT_NO_IT")
        print(f"MinimalFooter.render() returning: {repr(result.plain)}")
        return result


class TestApp(App):
    """Test app with bindings."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("f1", "test", "Test", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield MinimalFooter()


if __name__ == "__main__":
    app = TestApp()
    app.run()
