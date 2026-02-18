#!/usr/bin/env python3
"""
Quick validation script to verify status footer is working.
This simulates the key status transitions without full TUI interaction.
"""

from unittest.mock import Mock

from logai.ui.widgets.status_footer import StatusFooter
from rich.console import Console


def test_status_footer_states() -> None:
    """Test different status states and verify output."""
    console = Console()

    console.print("\n[bold cyan]Status Footer State Testing[/bold cyan]")
    console.print("=" * 70)

    # Create footer instance
    footer = StatusFooter(model="qwen3:32b")

    # Mock the required attributes for rendering using object.__setattr__
    mock_size = Mock(width=120)
    object.__setattr__(footer, "_size", mock_size)

    mock_screen = Mock()
    mock_screen.active_bindings = {}  # No bindings for this test
    object.__setattr__(footer, "_screen", mock_screen)

    mock_app = Mock()
    object.__setattr__(footer, "app", mock_app)

    # Test states
    test_cases = [
        ("Ready", "Idle state (should be dim italic)"),
        ("Thinking...", "Active state with spinner (should be yellow)"),
        ("Running tool: list_log_groups...", "Single tool execution"),
        ("Running tool 1/3: search_logs...", "Multi-tool execution with counter"),
        ("Running tool 2/3: fetch_logs...", "Second tool in sequence"),
        ("Processing results...", "Post-tool processing"),
        ("Tool error: search_logs", "Error state"),
    ]

    console.print("\n[bold]Testing Status States:[/bold]\n")

    for status, description in test_cases:
        footer.set_status(status)

        # Get rendered output
        rendered = footer.render()

        # Check key properties
        has_status = status in rendered.plain
        is_active = status != "Ready"

        # Display results
        console.print(f"  Status: [yellow]{status}[/yellow]")
        console.print(f"    Description: {description}")
        console.print(f"    In output: {'✅' if has_status else '❌'}")
        console.print(f"    Active: {'✅' if is_active else '❌'}")
        console.print(f"    Length: {len(rendered.plain)} chars")
        console.print()

    # Test context info updates
    console.print("\n[bold]Testing Context Info Updates:[/bold]\n")

    footer.update_cache_stats(hits=12, misses=5)
    footer.update_context_usage(45.2)

    rendered = footer.render()

    console.print(f"  Cache Stats: {'✅ Present' if 'Cache:' in rendered.plain else '❌ Missing'}")
    console.print(f"  Context %: {'✅ Present' if 'Context:' in rendered.plain else '❌ Missing'}")
    console.print(f"  Model: {'✅ Present' if 'qwen3:32b' in rendered.plain else '❌ Missing'}")
    console.print()

    # Test spinner style
    console.print("\n[bold]Spinner Configuration:[/bold]\n")
    console.print(f"  Style: {footer._spinner.name}")
    console.print("  Expected: dots2")
    console.print(f"  Match: {'✅' if footer._spinner.name == 'dots2' else '❌'}")
    console.print()

    # Verify no "it" prefix bug
    console.print("\n[bold]Bug Verification:[/bold]\n")

    footer.set_status("Thinking...")
    rendered = footer.render()

    has_it_prefix = "it Thinking" in rendered.plain
    console.print(f"  'it' prefix bug: {'❌ FOUND' if has_it_prefix else '✅ Not present'}")
    console.print()

    console.print("=" * 70)
    console.print("[bold green]✅ Validation Complete[/bold green]\n")


if __name__ == "__main__":
    test_status_footer_states()
