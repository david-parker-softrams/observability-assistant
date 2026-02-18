#!/usr/bin/env python3
"""Demo script to show different spinner types available in Rich library.

Run this to see animated spinners and choose which style you prefer.
"""

import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

console = Console()

# All available spinner types in Rich
SPINNER_TYPES = [
    "dots",
    "dots2",
    "dots3",
    "dots4",
    "dots5",
    "dots6",
    "dots7",
    "dots8",
    "dots9",
    "dots10",
    "dots11",
    "dots12",
    "line",
    "line2",
    "pipe",
    "simpleDots",
    "simpleDotsScrolling",
    "star",
    "star2",
    "flip",
    "hamburger",
    "growVertical",
    "growHorizontal",
    "balloon",
    "balloon2",
    "noise",
    "bounce",
    "boxBounce",
    "boxBounce2",
    "triangle",
    "arc",
    "circle",
    "squareCorners",
    "circleQuarters",
    "circleHalves",
    "squish",
    "toggle",
    "toggle2",
    "toggle3",
    "toggle4",
    "toggle5",
    "toggle6",
    "toggle7",
    "toggle8",
    "toggle9",
    "toggle10",
    "toggle11",
    "toggle12",
    "toggle13",
    "arrow",
    "arrow2",
    "arrow3",
    "bouncingBar",
    "bouncingBall",
    "smiley",
    "monkey",
    "hearts",
    "clock",
    "earth",
    "moon",
    "runner",
    "pong",
    "shark",
    "dqpb",
    "weather",
    "christmas",
]

# Recommended spinners for terminal apps (professional, clear, work well in all terminals)
RECOMMENDED = [
    "dots",  # Simple dots - classic, minimal
    "dots2",  # Braille dots - smooth, elegant
    "line",  # Rotating line - clean, simple
    "arc",  # Arc rotation - modern, smooth
    "circle",  # Circle segments - clear progress feel
    "simpleDotsScrolling",  # Scrolling dots - clear direction
    "toggle",  # Toggle dots - minimal, clear
    "bouncingBar",  # Progress bar style - intuitive
]


def show_recommended():
    """Show recommended spinners with descriptions."""
    console.print("\n[bold cyan]🎯 RECOMMENDED SPINNERS FOR STATUS FOOTER[/bold cyan]\n")
    console.print("These work well in all terminals and provide clear visual feedback.\n")

    for spinner_name in RECOMMENDED:
        description = {
            "dots": "Classic rotating dots - minimal and clean",
            "dots2": "Braille dots - smooth and elegant",
            "line": "Rotating line - simple and clear",
            "arc": "Arc rotation - modern and smooth",
            "circle": "Circle segments - shows progress feeling",
            "simpleDotsScrolling": "Scrolling dots - shows direction clearly",
            "toggle": "Toggle pattern - minimal distraction",
            "bouncingBar": "Bouncing bar - intuitive progress feel",
        }.get(spinner_name, "")

        spinner = Spinner(spinner_name, text=f"[dim]{spinner_name:20s}[/dim] {description}")
        console.print(spinner)
        time.sleep(1.5)

    console.print()


def show_all_grid():
    """Show all spinners in a grid format for 3 seconds each."""
    console.print("\n[bold cyan]📋 ALL AVAILABLE SPINNER TYPES[/bold cyan]\n")
    console.print("Showing each spinner for 3 seconds...\n")

    for spinner_name in SPINNER_TYPES:
        with Live(
            Spinner(spinner_name, text=f"[bold]{spinner_name}[/bold] - Thinking..."),
            console=console,
            refresh_per_second=10,
        ):
            time.sleep(3)

    console.print("\n[green]✓[/green] Demo complete!\n")


def show_context_examples():
    """Show spinners in context of how they'd appear in the status footer."""
    console.print("\n[bold cyan]💡 SPINNERS IN CONTEXT[/bold cyan]\n")
    console.print("Here's how different spinners would look in your status footer:\n")

    status_messages = [
        "Thinking...",
        "Running tool: list_log_groups...",
        "Processing results...",
        "Analyzing 1,247 log events...",
    ]

    test_spinners = ["dots", "dots2", "line", "arc", "circle"]

    for spinner_name in test_spinners:
        console.print(f"\n[bold yellow]Spinner: {spinner_name}[/bold yellow]")
        for msg in status_messages:
            spinner = Spinner(spinner_name, text=msg)
            console.print(f"  {spinner}")
            time.sleep(1)
        time.sleep(0.5)

    console.print()


def interactive_chooser():
    """Let user see each spinner and choose their favorite."""
    console.print("\n[bold green]🎨 INTERACTIVE SPINNER CHOOSER[/bold green]\n")
    console.print("Watch each recommended spinner for 5 seconds.\n")
    console.print("Note which one you prefer!\n")

    for i, spinner_name in enumerate(RECOMMENDED, 1):
        console.print(f"\n[bold]Option {i}: {spinner_name}[/bold]")

        with Live(
            Panel(
                Spinner(spinner_name, text="Thinking..."),
                title=f"Spinner: {spinner_name}",
                border_style="cyan",
            ),
            console=console,
            refresh_per_second=10,
        ):
            time.sleep(5)

    console.print("\n[bold green]Which one did you like best?[/bold green]")
    console.print("\nRecommendations:")
    console.print("  • [cyan]dots[/cyan] or [cyan]dots2[/cyan] - Most minimal, least distracting")
    console.print("  • [cyan]line[/cyan] or [cyan]arc[/cyan] - Clean and professional")
    console.print("  • [cyan]circle[/cyan] - Clear sense of progress")
    console.print()


def show_comparison_table():
    """Show a comparison table of recommended spinners."""
    table = Table(title="Spinner Comparison", show_header=True, header_style="bold cyan")
    table.add_column("Spinner", style="yellow", width=20)
    table.add_column("Style", width=30)
    table.add_column("Best For", width=40)

    table.add_row("dots", "Classic dots", "Minimal UI, low distraction")
    table.add_row("dots2", "Braille pattern dots", "Smooth animation, elegant")
    table.add_row("line", "Rotating line", "Simple, clear indication")
    table.add_row("arc", "Curved arc rotation", "Modern look, smooth motion")
    table.add_row("circle", "Circle segments", "Progress feeling, clear visual")
    table.add_row("simpleDotsScrolling", "Scrolling dots", "Shows direction, clear motion")
    table.add_row("toggle", "Toggle pattern", "Very minimal, subtle")
    table.add_row("bouncingBar", "Bouncing progress bar", "Intuitive progress indication")

    console.print("\n")
    console.print(table)
    console.print()


def main():
    """Run the spinner demo."""
    console.print(
        "\n[bold blue]╔═══════════════════════════════════════════════════════╗[/bold blue]"
    )
    console.print(
        "[bold blue]║                 SPINNER TYPE DEMO                      ║[/bold blue]"
    )
    console.print(
        "[bold blue]╚═══════════════════════════════════════════════════════╝[/bold blue]\n"
    )

    console.print("This demo will show you different spinner animations.")
    console.print("Choose which one you'd like for the LogAI status indicator.\n")

    console.print("[dim]Press Ctrl+C at any time to exit[/dim]\n")

    try:
        # Show comparison table first
        show_comparison_table()

        input("Press Enter to see recommended spinners in action...")

        # Show recommended spinners
        show_recommended()

        input("Press Enter to see spinners in context...")

        # Show context examples
        show_context_examples()

        input("Press Enter for interactive chooser (5 seconds each)...")

        # Interactive chooser
        interactive_chooser()

        console.print("[bold green]✨ Demo complete![/bold green]")
        console.print(
            "\nMy recommendation: [bold cyan]'dots2'[/bold cyan] or [bold cyan]'arc'[/bold cyan]"
        )
        console.print("  • dots2: Smooth, minimal, works everywhere")
        console.print("  • arc: Modern, professional, clear motion\n")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Demo interrupted. No problem![/yellow]\n")


if __name__ == "__main__":
    main()
