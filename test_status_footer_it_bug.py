#!/usr/bin/env python3
"""Test script to debug the 'it' text appearing in status footer."""

from logai.ui.widgets.status_footer import StatusFooter
from rich.console import Console
from rich.text import Text
from textual.app import App
from textual.binding import Binding


class TestApp(App):
    """Test app to debug status footer."""

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True, show=True),
        Binding("f1", "shrink_left_sidebar", "◀ Logs", show=True),
        Binding("f2", "expand_left_sidebar", "Logs ►", show=True),
        Binding("f3", "expand_right_sidebar", "◀ Tools", show=True),
        Binding("f4", "shrink_right_sidebar", "Tools ►", show=True),
    ]

    def compose(self):
        footer = StatusFooter(model="test-model")
        footer.status = "Thinking..."
        yield footer


def test_text_building():
    """Test building the text to find where 'it' comes from."""
    Console()

    print("=" * 80)
    print("TEST 1: Direct Text building")
    print("=" * 80)

    # Simulate what status_footer does
    shortcuts = Text()
    shortcuts.append("f4", style="bold cyan")
    shortcuts.append(" ")
    shortcuts.append("Tools ►", style="white")

    status_display = Text()
    status_display.append("⣾ ", style="yellow")
    status_display.append("Thinking...", style="bold yellow")

    result = Text()
    result.append_text(shortcuts)
    result.append("  ")
    result.append_text(status_display)

    print(f"Result plain: {repr(result.plain)}")
    print(f"Contains 'it': {'it' in result.plain}")
    print()

    print("=" * 80)
    print("TEST 2: Check if 'dim italic' style leaks")
    print("=" * 80)

    # Test the idle status path
    status_idle = Text()
    status_idle.append("Ready", style="dim italic")

    print(f"Idle status plain: {repr(status_idle.plain)}")
    print(f"Contains 'it': {'it' in status_idle.plain}")
    print()

    # What if we accidentally extract from style string?
    style_str = "dim italic"
    words = style_str.split()
    print(f"Style string: {repr(style_str)}")
    print(f"Split words: {words}")
    for i, word in enumerate(words):
        print(f"  Word {i} ({repr(word)}): first 2 chars = {repr(word[:2])}")
    print()

    print("=" * 80)
    print("TEST 3: Check binding rendering")
    print("=" * 80)

    # Simulate binding rendering
    bindings_data = [
        ("f1", "◀ Logs"),
        ("f2", "Logs ►"),
        ("f3", "◀ Tools"),
        ("f4", "Tools ►"),
    ]

    shortcuts2 = Text()
    for i, (key, desc) in enumerate(bindings_data):
        if i > 0:
            shortcuts2.append("    ")  # Spaces between bindings
        shortcuts2.append(key, style="bold cyan")
        shortcuts2.append(" ")
        shortcuts2.append(desc, style="white")

    print(f"Shortcuts plain: {repr(shortcuts2.plain)}")
    print(f"Length: {len(shortcuts2.plain)}")
    print(f"Contains 'it': {'it' in shortcuts2.plain}")

    # Print character by character
    for i, char in enumerate(shortcuts2.plain):
        if char.isalpha() and i > 0 and shortcuts2.plain[i - 1] == " ":
            # Found start of a word
            word_start = i
            word_end = i
            while word_end < len(shortcuts2.plain) and shortcuts2.plain[word_end] not in " \t\n":
                word_end += 1
            word = shortcuts2.plain[word_start:word_end]
            if "it" in word or word == "it":
                print(f"  Found 'it' at position {i}: word={repr(word)}")


if __name__ == "__main__":
    test_text_building()

    print("\n" + "=" * 80)
    print("To test the actual app rendering, run the main app and check the footer")
    print("=" * 80)
