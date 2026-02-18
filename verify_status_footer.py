#!/usr/bin/env python3
"""
Status Footer Code Verification Script

This script verifies the status footer implementation by checking:
1. Code structure and key methods
2. Spinner configuration
3. Status update points in chat screen
4. Test coverage
"""

import re
from pathlib import Path

from rich.console import Console
from rich.table import Table


def check_status_footer_code() -> dict[str, bool]:
    """Check status footer implementation."""
    console = Console()
    results = {}

    console.print("\n[bold cyan]Status Footer Code Verification[/bold cyan]")
    console.print("=" * 70 + "\n")

    # Read status footer source
    footer_path = Path("src/logai/ui/widgets/status_footer.py")
    footer_code = footer_path.read_text()

    # Check 1: Spinner initialization with dots2
    console.print("[bold]1. Spinner Configuration:[/bold]")
    spinner_match = re.search(r'Spinner\("(\w+)".*?style="(\w+)"\)', footer_code)
    if spinner_match:
        spinner_style = spinner_match.group(1)
        spinner_color = spinner_match.group(2)
        console.print(f"   Style: [cyan]{spinner_style}[/cyan]")
        console.print(f"   Color: [cyan]{spinner_color}[/cyan]")
        results["spinner_dots2"] = spinner_style == "dots2"
        results["spinner_yellow"] = spinner_color == "yellow"
        console.print(
            "   ✅ Correct: dots2 style" if results["spinner_dots2"] else "   ❌ Wrong style"
        )
    else:
        console.print("   ❌ Spinner initialization not found")
        results["spinner_dots2"] = False
        results["spinner_yellow"] = False

    # Check 2: No "it" prefix bug
    console.print("\n[bold]2. Status Text (No 'it' Prefix Bug):[/bold]")
    # Look for any place where "it {status}" pattern might occur
    it_prefix_pattern = re.search(r'["\']it\s+\{', footer_code)
    results["no_it_prefix"] = it_prefix_pattern is None
    if results["no_it_prefix"]:
        console.print("   ✅ No 'it' prefix pattern found")
    else:
        console.print("   ❌ Found 'it' prefix pattern")

    # Check 3: Status display with spinner
    console.print("\n[bold]3. Active Status Display:[/bold]")
    active_status_pattern = re.search(
        r'if self\.status and self\.status != "Ready".*?spinner_text', footer_code, re.DOTALL
    )
    results["active_status_spinner"] = active_status_pattern is not None
    if results["active_status_spinner"]:
        console.print("   ✅ Active status shows spinner")
    else:
        console.print("   ❌ Active status spinner logic not found")

    # Check 4: _render_shortcuts method exists
    console.print("\n[bold]4. Keyboard Shortcuts Rendering:[/bold]")
    shortcuts_method = re.search(r"def _render_shortcuts\(self\)", footer_code)
    results["render_shortcuts"] = shortcuts_method is not None
    if results["render_shortcuts"]:
        console.print("   ✅ _render_shortcuts() method exists")
    else:
        console.print("   ❌ _render_shortcuts() method not found")

    # Check 5: Status update methods
    console.print("\n[bold]5. Status Update Methods:[/bold]")
    set_status = re.search(r"def set_status\(self, status: str\)", footer_code)
    update_cache = re.search(r"def update_cache_stats\(self, hits: int, misses: int\)", footer_code)
    update_context = re.search(
        r"def update_context_usage\(self, utilization_pct: float\)", footer_code
    )

    results["set_status_method"] = set_status is not None
    results["update_cache_method"] = update_cache is not None
    results["update_context_method"] = update_context is not None

    console.print(f"   {'✅' if results['set_status_method'] else '❌'} set_status()")
    console.print(f"   {'✅' if results['update_cache_method'] else '❌'} update_cache_stats()")
    console.print(f"   {'✅' if results['update_context_method'] else '❌'} update_context_usage()")

    return results


def check_chat_screen_integration() -> dict[str, bool]:
    """Check chat screen integration."""
    console = Console()
    results = {}

    console.print("\n[bold cyan]Chat Screen Integration[/bold cyan]")
    console.print("=" * 70 + "\n")

    # Read chat screen source
    chat_path = Path("src/logai/ui/screens/chat.py")
    chat_code = chat_path.read_text()

    # Check for status updates
    console.print("[bold]Status Update Points:[/bold]")

    patterns = {
        "thinking": r'set_status\("Thinking\.\.\."\)',
        "ready": r'set_status\("Ready"\)',
        "running_tool": r'set_status\(f"Running tool.*?\{.*?\}\.\.\."\)',
        "tool_counter": r'set_status\(f"Running tool \{tool_index\}/\{total\}',
        "processing": r'set_status\("Processing results\.\.\."\)',
        "error": r"set_status.*?error",
    }

    for name, pattern in patterns.items():
        match = re.search(pattern, chat_code)
        results[f"chat_{name}"] = match is not None
        console.print(
            f"   {'✅' if results[f'chat_{name}'] else '❌'} {name.replace('_', ' ').title()}"
        )

    return results


def check_test_coverage() -> dict[str, bool]:
    """Check test coverage."""
    console = Console()
    results = {}

    console.print("\n[bold cyan]Test Coverage[/bold cyan]")
    console.print("=" * 70 + "\n")

    # Check for test files
    test_files = [
        ("tests/unit/test_status_footer_render.py", "Status footer unit tests"),
        ("tests/unit/test_ui_widgets.py", "UI widgets tests"),
    ]

    console.print("[bold]Test Files:[/bold]")
    for test_file, description in test_files:
        exists = Path(test_file).exists()
        results[f"test_{Path(test_file).stem}"] = exists
        console.print(f"   {'✅' if exists else '❌'} {description}")

    return results


def generate_summary(all_results: dict[str, bool]) -> None:
    """Generate test summary."""
    console = Console()

    console.print("\n[bold cyan]Summary[/bold cyan]")
    console.print("=" * 70 + "\n")

    # Create results table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Category", style="dim")
    table.add_column("Test", min_width=40)
    table.add_column("Result", justify="center")

    categories = {
        "Status Footer": [
            "spinner_dots2",
            "spinner_yellow",
            "no_it_prefix",
            "active_status_spinner",
            "render_shortcuts",
        ],
        "Update Methods": ["set_status_method", "update_cache_method", "update_context_method"],
        "Chat Integration": [
            "chat_thinking",
            "chat_ready",
            "chat_running_tool",
            "chat_tool_counter",
            "chat_processing",
        ],
        "Test Coverage": ["test_test_status_footer_render", "test_test_ui_widgets"],
    }

    for category, keys in categories.items():
        for i, key in enumerate(keys):
            if key in all_results:
                result_icon = "✅" if all_results[key] else "❌"
                cat_display = category if i == 0 else ""
                table.add_row(cat_display, key.replace("_", " ").title(), result_icon)

    console.print(table)

    # Calculate stats
    total = len(all_results)
    passed = sum(1 for v in all_results.values() if v)
    percentage = (passed / total * 100) if total > 0 else 0

    console.print(f"\n[bold]Results: {passed}/{total} checks passed ({percentage:.1f}%)[/bold]")

    if percentage == 100:
        console.print(
            "\n[bold green]✅ All checks passed! Status footer is correctly implemented.[/bold green]\n"
        )
    elif percentage >= 80:
        console.print(
            "\n[bold yellow]⚠️  Most checks passed, but some issues found.[/bold yellow]\n"
        )
    else:
        console.print("\n[bold red]❌ Multiple issues found. Review implementation.[/bold red]\n")


def main() -> None:
    """Run all verification checks."""
    console = Console()

    console.print(
        "\n[bold magenta]╔══════════════════════════════════════════════════════════════════╗[/bold magenta]"
    )
    console.print(
        "[bold magenta]║         Status Footer Implementation Verification            ║[/bold magenta]"
    )
    console.print(
        "[bold magenta]╚══════════════════════════════════════════════════════════════════╝[/bold magenta]\n"
    )

    all_results = {}

    # Run checks
    all_results.update(check_status_footer_code())
    all_results.update(check_chat_screen_integration())
    all_results.update(check_test_coverage())

    # Generate summary
    generate_summary(all_results)


if __name__ == "__main__":
    main()
