#!/usr/bin/env python3
"""
Test script for latency-aware gestures.

This script simulates different latency scenarios to verify that
the latency policy correctly selects appropriate gestures.
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from reachy_demo.policy.latency_policy import LatencyPolicy
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def test_latency_policy():
    """Test the latency policy with various scenarios."""
    policy = LatencyPolicy()
    
    console.print(Panel.fit(
        "[bold cyan]Latency-Aware Gesture Policy Test[/bold cyan]\n\n"
        "Testing gesture selection based on latency tiers",
        title="Policy Test"
    ))
    
    # Test scenarios
    test_cases = [
        # (description, aim_ms, e2e_ms, ok, expected_gesture)
        ("Fast response - Tier 0", 300, 500, True, "nod_fast"),
        ("Fast response (edge) - Tier 0", 600, 750, True, "nod_fast"),
        ("Normal response - Tier 1", 1200, 1500, True, "nod_tilt"),
        ("Normal response (edge) - Tier 1", 2000, 2400, True, "nod_tilt"),
        ("Slow response - Tier 2", 2500, 3000, True, "thinking_done"),
        ("Very slow response - Tier 2", 5000, 6000, True, "thinking_done"),
        ("Error case", 0, 100, False, "error"),
        ("Error with latency", 500, 800, False, "error"),
    ]
    
    table = Table(title="Latency Policy Test Results", show_header=True, header_style="bold magenta")
    table.add_column("Scenario", style="cyan", width=25)
    table.add_column("AIM (ms)", style="yellow", justify="right")
    table.add_column("E2E (ms)", style="yellow", justify="right")
    table.add_column("Status", style="green", width=8)
    table.add_column("Expected", style="blue", width=15)
    table.add_column("Selected", style="green", width=15)
    table.add_column("Match", style="bold", width=8)
    
    all_passed = True
    
    for description, aim_ms, e2e_ms, ok, expected_gesture in test_cases:
        selected = policy.choose_post_gesture(aim_ms, e2e_ms, ok)
        tier = policy.get_latency_tier(e2e_ms)
        match = "✓" if selected == expected_gesture else "✗"
        
        if selected != expected_gesture:
            all_passed = False
        
        status = "OK" if ok else "ERROR"
        status_style = "green" if ok else "red"
        
        table.add_row(
            description,
            str(int(aim_ms)),
            str(int(e2e_ms)),
            f"[{status_style}]{status}[/{status_style}]",
            expected_gesture,
            selected,
            f"[{'green' if match == '✓' else 'red'}]{match}[/{'green' if match == '✓' else 'red'}]"
        )
    
    console.print(table)
    
    # Test pre-gesture
    console.print("\n[bold]Pre-Gesture Test:[/bold]")
    pre_gesture = policy.choose_pre_gesture()
    console.print(f"  Pre-gesture (immediate feedback): [green]{pre_gesture}[/green]")
    if pre_gesture == "ack":
        console.print("  [green]✓[/green] Correct - should always be 'ack' for immediate feedback")
    else:
        console.print(f"  [red]✗[/red] Expected 'ack', got '{pre_gesture}'")
        all_passed = False
    
    # Summary
    console.print("\n" + "="*60)
    if all_passed:
        console.print("[bold green]✓ All tests passed![/bold green]")
    else:
        console.print("[bold red]✗ Some tests failed[/bold red]")
    
    return all_passed


def test_with_real_demo():
    """Instructions for testing with the actual demo."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Testing with Real Demo[/bold cyan]\n\n"
        "To test latency-aware gestures with the actual demo:\n\n"
        "1. Start daemon (Terminal 1):\n"
        "   make sim  # or hardware mode\n\n"
        "2. Run demo (Terminal 2):\n"
        "   make run\n\n"
        "3. Observe gestures:\n"
        "   - Immediate 'ack' when you press Enter\n"
        "   - Post-gesture based on response latency:\n"
        "     • Fast (<800ms): nod_fast\n"
        "     • Normal (800-2500ms): nod_tilt\n"
        "     • Slow (>2500ms): thinking_done\n"
        "     • Error: error\n\n"
        "4. Check metrics:\n"
        "   curl http://127.0.0.1:9100/metrics | grep gesture_selected\n\n"
        "5. Test different scenarios:\n"
        "   - Fast: Use small model or cached response\n"
        "   - Normal: Use medium model (7-13B)\n"
        "   - Slow: Use large model or add network delay",
        title="Real Demo Testing"
    ))


def show_gesture_tiers():
    """Display the gesture tier thresholds."""
    policy = LatencyPolicy()
    
    console.print("\n[bold]Gesture Tier Thresholds:[/bold]")
    console.print(f"  Tier 0 (Fast): < {policy.TIER_0_THRESHOLD}ms → nod_fast")
    console.print(f"  Tier 1 (Normal): {policy.TIER_0_THRESHOLD}-{policy.TIER_1_THRESHOLD}ms → nod_tilt")
    console.print(f"  Tier 2 (Slow): > {policy.TIER_1_THRESHOLD}ms → thinking_done")
    console.print(f"  Error: Any failure → error")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test latency-aware gestures")
    parser.add_argument(
        "--tiers",
        action="store_true",
        help="Show gesture tier thresholds"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Show instructions for testing with real demo"
    )
    
    args = parser.parse_args()
    
    if args.tiers:
        show_gesture_tiers()
    elif args.demo:
        test_with_real_demo()
    else:
        # Run policy tests
        test_latency_policy()
        show_gesture_tiers()
        test_with_real_demo()


if __name__ == "__main__":
    main()

