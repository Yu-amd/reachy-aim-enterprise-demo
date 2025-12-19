#!/usr/bin/env python3
"""
Discover recorded moves available in the Reachy Mini daemon.

This tool queries the daemon API to find available recorded moves and datasets.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

import typer
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from reachy_demo.config import load_settings

app = typer.Typer(add_completion=False)
console = Console()


def discover_recorded_moves(base_url: str) -> dict:
    """Discover available recorded moves from the daemon using the API."""
    base_url = base_url.rstrip("/")
    discovered = {
        "datasets": [],
        "moves": {}
    }
    
    # Known datasets from reachy_mini project (HuggingFace datasets)
    known_datasets = [
        "pollen-robotics/reachy-mini-dances-library",  # 20 dance moves
        "pollen-robotics/reachy-mini-emotions-library",  # Emotion gestures
        "default",  # Fallback
        "dances",  # Short name fallback
        "emotions",  # Short name fallback
    ]
    
    console.print("[cyan]Discovering recorded moves from daemon API...[/cyan]\n")
    
    # Use the daemon's list endpoint if available
    for dataset in known_datasets:
        try:
            # Try the list endpoint first
            url = f"{base_url}/api/move/recorded-move-datasets/list/{dataset}"
            response = requests.get(url, timeout=2.0)
            if response.status_code == 200:
                moves = response.json()
                if moves:
                    discovered["datasets"].append(dataset)
                    discovered["moves"][dataset] = moves
                    console.print(f"[green]✓[/green] Found dataset: [bold]{dataset}[/bold]")
                    console.print(f"  [dim]Contains {len(moves)} move(s)[/dim]")
                    for move in moves[:5]:  # Show first 5
                        console.print(f"    - {move}")
                    if len(moves) > 5:
                        console.print(f"    ... and {len(moves) - 5} more")
        except requests.exceptions.RequestException:
            # Endpoint doesn't exist or dataset not available
            pass
    
    # If no datasets found via API, try common patterns as fallback
    if not discovered["datasets"]:
        console.print("[yellow]API list endpoint not available, trying common patterns...[/yellow]")
        common_datasets = ["default", "dances", "gestures", "moves", "animations"]
        common_moves = [
            "jackson_square", "interwoven_spirals", "polyrhythm_combo",
            "dizzy_spin", "wave_combo", "shoulder_pop", "head_bob",
            "antenna_wiggle", "body_sway", "nod_sequence",
        ]
        
        for dataset in common_datasets:
            found_moves = []
            for move in common_moves:
                try:
                    url = f"{base_url}/api/move/play/recorded-move-dataset/{dataset}/{move}"
                    response = requests.post(url, timeout=1.0)
                    if response.status_code == 200:
                        found_moves.append(move)
                        console.print(f"[green]✓[/green] Found: {dataset}/{move}")
                except Exception:
                    pass
            
            if found_moves:
                discovered["datasets"].append(dataset)
                discovered["moves"][dataset] = found_moves
    
    return discovered


@app.command()
def discover(
    daemon_url: str = typer.Option(None, "--daemon-url", "-u", help="Daemon URL (defaults to config)"),
    test: bool = typer.Option(False, "--test", "-t", help="Test moves by actually playing them"),
):
    """Discover recorded moves available in the Reachy Mini daemon."""
    try:
        if daemon_url:
            base_url = daemon_url
        else:
            settings = load_settings()
            base_url = settings.reachy_daemon_url
        
        console.print(f"[cyan]Connecting to daemon at:[/cyan] {base_url}")
        
        # Check if daemon is accessible
        try:
            response = requests.get(f"{base_url}/api/state/full", timeout=1.0)
            response.raise_for_status()
            console.print("[green]✓ Daemon is accessible[/green]\n")
        except Exception as e:
            console.print(f"[red]✗ Cannot connect to daemon:[/red] {e}")
            console.print("[yellow]Make sure the daemon is running.[/yellow]")
            raise typer.Exit(1)
        
        # Discover moves
        discovered = discover_recorded_moves(base_url)
        
        # Display results
        if discovered["datasets"]:
            table = Table(title="Discovered Recorded Moves", show_header=True, header_style="bold cyan")
            table.add_column("Dataset", style="yellow")
            table.add_column("Moves", style="green")
            
            for dataset in discovered["datasets"]:
                moves = discovered["moves"][dataset]
                moves_str = ", ".join(moves)
                table.add_row(dataset, moves_str)
            
            console.print(table)
            console.print(f"\n[green]Found {len(discovered['datasets'])} dataset(s) with {sum(len(moves) for moves in discovered['moves'].values())} move(s)[/green]")
            
            # Show usage examples
            console.print("\n[bold]Usage Examples:[/bold]")
            for dataset in discovered["datasets"]:
                for move in discovered["moves"][dataset][:3]:  # Show first 3
                    console.print(f"  [cyan]cmd:gesture recorded:{dataset}:{move}[/cyan]")
                    if test:
                        console.print(f"    [dim]Testing move...[/dim]")
                        try:
                            requests.post(f"{base_url}/api/move/play/recorded-move-dataset/{dataset}/{move}", timeout=5.0)
                            console.print(f"    [green]✓ Move played successfully[/green]")
                        except Exception as e:
                            console.print(f"    [red]✗ Failed to play: {e}[/red]")
        else:
            console.print(Panel.fit(
                "[yellow]No recorded moves discovered.[/yellow]\n\n"
                "This could mean:\n"
                "1. The daemon doesn't have recorded moves configured\n"
                "2. The moves use different dataset/move names\n"
                "3. The daemon API structure is different\n\n"
                "[dim]You can still use custom gestures via /api/move/goto[/dim]",
                title="No Moves Found"
            ))
        
        # Show how to check daemon docs
        console.print(f"\n[dim]Tip: Check daemon API docs at {base_url}/docs for available endpoints[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

