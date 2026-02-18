#!/usr/bin/env python3
"""Non-interactive spinner demo - shows examples without requiring input."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_spinner_examples():
    """Show examples of recommended spinners."""
    console.print("\n[bold cyan]🎯 RECOMMENDED SPINNER OPTIONS[/bold cyan]\n")

    spinners = [
        ("dots", "⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏", "Classic rotating dots - minimal and clean"),
        ("dots2", "⣾ ⣽ ⣻ ⢿ ⡿ ⣟ ⣯ ⣷", "Braille dots - smooth and elegant"),
        ("line", "- \\ | /", "Rotating line - simple and clear"),
        ("arc", "◜ ◠ ◝ ◞ ◡ ◟", "Arc rotation - modern and smooth"),
        ("circle", "◴ ◷ ◶ ◵", "Circle segments - shows progress feeling"),
        ("simpleDotsScrolling", "⠁ ⠂ ⠄ ⡀ ⢀ ⠠ ⠐ ⠈", "Scrolling dots - shows direction clearly"),
    ]

    table = Table(show_header=True, header_style="bold yellow", box=None)
    table.add_column("Name", style="cyan", width=20)
    table.add_column("Animation Frames", style="dim", width=25)
    table.add_column("Description", width=45)

    for name, frames, desc in spinners:
        table.add_row(name, frames, desc)

    console.print(table)
    console.print()


def show_context_examples():
    """Show how spinners would look in the status footer."""
    console.print("\n[bold cyan]💡 HOW THEY LOOK IN CONTEXT[/bold cyan]\n")

    examples = [
        ("dots", "Status: ⠋ Thinking..."),
        ("dots", "Status: ⠙ Running tool: list_log_groups..."),
        ("dots", "Status: ⠹ Processing results..."),
        ("", ""),
        ("dots2", "Status: ⣾ Thinking..."),
        ("dots2", "Status: ⣽ Running tool: list_log_groups..."),
        ("dots2", "Status: ⣻ Processing results..."),
        ("", ""),
        ("line", "Status: - Thinking..."),
        ("line", "Status: \\ Running tool: list_log_groups..."),
        ("line", "Status: | Processing results..."),
        ("", ""),
        ("arc", "Status: ◜ Thinking..."),
        ("arc", "Status: ◠ Running tool: list_log_groups..."),
        ("arc", "Status: ◝ Processing results..."),
        ("", ""),
        ("circle", "Status: ◴ Thinking..."),
        ("circle", "Status: ◷ Running tool: list_log_groups..."),
        ("circle", "Status: ◶ Processing results..."),
    ]

    for _name, example in examples:
        if example:
            console.print(f"  [dim]{example}[/dim]")
        else:
            console.print()


def show_recommendations():
    """Show detailed recommendations."""
    console.print("\n[bold green]📊 MY RECOMMENDATIONS[/bold green]\n")

    recommendations = [
        {
            "name": "dots2",
            "score": "★★★★★",
            "pros": [
                "Smooth, elegant animation using Braille characters",
                "Works perfectly in all terminal types",
                "Minimal distraction, professional look",
                "Clear indication of activity",
            ],
            "cons": ["Requires Unicode support (universal nowadays)"],
            "best_for": "Best overall choice - recommended default",
        },
        {
            "name": "arc",
            "score": "★★★★☆",
            "pros": [
                "Modern, smooth curved motion",
                "Clear visual progress indication",
                "Professional appearance",
                "Good balance of visibility and subtlety",
            ],
            "cons": ["Slightly more visually prominent than dots"],
            "best_for": "If you want something more modern/visual",
        },
        {
            "name": "dots",
            "score": "★★★★☆",
            "pros": [
                "Classic, familiar pattern",
                "Extremely minimal and subtle",
                "Universal compatibility",
                "Low CPU usage",
            ],
            "cons": ["Less smooth than dots2"],
            "best_for": "If you want the most minimal option",
        },
        {
            "name": "line",
            "score": "★★★☆☆",
            "pros": [
                "Simple ASCII characters",
                "Clear rotation pattern",
                "Works even in basic terminals",
            ],
            "cons": ["Less elegant than Unicode options", "Can feel dated"],
            "best_for": "Maximum compatibility, basic terminals",
        },
    ]

    for rec in recommendations:
        console.print(
            Panel(
                f"[bold yellow]{rec['score']}[/bold yellow] {rec['best_for']}\n\n"
                f"[green]Pros:[/green]\n" + "\n".join(f"  • {p}" for p in rec["pros"]) + "\n\n"
                "[red]Cons:[/red]\n" + "\n".join(f"  • {c}" for c in rec["cons"]),
                title=f"[bold cyan]{rec['name']}[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()


def show_visual_comparison():
    """Show visual comparison of top choices."""
    console.print("\n[bold cyan]🎨 VISUAL COMPARISON - TOP 3[/bold cyan]\n")

    console.print("[bold]Scenario: User submits query, agent is thinking[/bold]\n")

    console.print(
        "  [cyan]dots2:[/cyan]  [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ⣾ [yellow]Thinking...[/yellow]"
    )
    console.print()
    console.print(
        "  [cyan]arc:[/cyan]    [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ◜ [yellow]Thinking...[/yellow]"
    )
    console.print()
    console.print(
        "  [cyan]dots:[/cyan]   [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ⠋ [yellow]Thinking...[/yellow]"
    )
    console.print()

    console.print("\n[bold]Scenario: Tool execution[/bold]\n")

    console.print(
        "  [cyan]dots2:[/cyan]  [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ⣽ [yellow]Running tool: list_log_groups...[/yellow]"
    )
    console.print()
    console.print(
        "  [cyan]arc:[/cyan]    [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ◠ [yellow]Running tool: list_log_groups...[/yellow]"
    )
    console.print()
    console.print(
        "  [cyan]dots:[/cyan]   [dim]Context: 45.2K/100K (45%) | Cache: 12 items | Model: gpt-4[/dim]  ⠙ [yellow]Running tool: list_log_groups...[/yellow]"
    )
    console.print()


def main():
    """Show all spinner information."""
    console.print(
        "\n[bold blue]╔═══════════════════════════════════════════════════════╗[/bold blue]"
    )
    console.print(
        "[bold blue]║           SPINNER SELECTION GUIDE                      ║[/bold blue]"
    )
    console.print(
        "[bold blue]╚═══════════════════════════════════════════════════════╝[/bold blue]\n"
    )

    show_spinner_examples()
    show_visual_comparison()
    show_context_examples()
    show_recommendations()

    console.print("\n[bold green]🎯 FINAL RECOMMENDATION[/bold green]\n")
    console.print("  I recommend: [bold cyan]dots2[/bold cyan]")
    console.print("  Reason: Best balance of smooth animation, visibility, and professionalism")
    console.print("  Fallback: [bold cyan]arc[/bold cyan] if you prefer more visual presence\n")

    console.print(
        "[dim]Note: We can make this configurable so users can choose their preference![/dim]\n"
    )


if __name__ == "__main__":
    main()
