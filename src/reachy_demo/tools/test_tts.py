#!/usr/bin/env python3
"""
Test script to verify TTS functionality for hardware demo.

Tests both daemon TTS (if available) and system TTS fallback.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from reachy_demo.adapters.robot_rest import ReachyDaemonREST
from reachy_demo.config import load_settings
from rich.console import Console
from rich.panel import Panel

console = Console()


def test_tts(daemon_url: str = "http://127.0.0.1:8001", audio_device: str | None = None):
    """Test TTS functionality."""
    console.print(Panel.fit(
        "[bold cyan]TTS Test Tool[/bold cyan]\n\n"
        f"Testing TTS with daemon at: {daemon_url}",
        title="TTS Test"
    ))
    
    try:
        robot = ReachyDaemonREST(daemon_url, audio_device=audio_device)
        
        # Check robot health and TTS availability
        console.print("\n[bold]Step 1: Checking robot connection...[/bold]")
        if robot.health():
            console.print("[green]✓[/green] Robot daemon is reachable")
        else:
            console.print("[yellow]⚠[/yellow] Robot daemon not reachable, but continuing...")
        
        # Check TTS method
        console.print("\n[bold]Step 2: Checking TTS availability...[/bold]")
        if not robot._tts_checked:
            robot._check_tts_availability()
        
        tts_method = robot._tts_method
        if tts_method == "daemon":
            console.print(f"[green]✓[/green] TTS Method: [bold]Daemon API[/bold] (robot speakers)")
            console.print(f"   Endpoint: {robot._tts_daemon_endpoint}")
        elif tts_method == "system":
            console.print(f"[yellow]⚠[/yellow] TTS Method: [bold]System TTS[/bold] (laptop speakers)")
            console.print("   Note: Audio will play on your laptop, not the robot")
        else:
            console.print(f"[red]✗[/red] TTS Method: [bold]Unavailable[/bold]")
            console.print("   TTS will not work")
            return
        
        # Test TTS
        console.print("\n[bold]Step 3: Testing TTS...[/bold]")
        test_texts = [
            "Hello, this is a test.",
            "The robot voice is working correctly.",
            "Testing one, two, three.",
        ]
        
        for i, text in enumerate(test_texts, 1):
            console.print(f"\n[cyan]Test {i}:[/cyan] {text}")
            console.print("[dim]Speaking...[/dim]")
            try:
                robot.speak(text)
                console.print("[green]✓[/green] TTS call completed")
            except Exception as e:
                console.print(f"[red]✗[/red] TTS error: {e}")
        
        # Summary
        console.print("\n" + "="*60)
        console.print("[bold]Summary:[/bold]")
        console.print(f"  TTS Method: {tts_method}")
        if tts_method == "system":
            console.print("\n[yellow]⚠ Important:[/yellow]")
            console.print("  System TTS plays on your laptop speakers, not the robot.")
            console.print("  The Reachy Mini daemon does not have TTS endpoints.")
            console.print("  To use robot speakers, you would need to:")
            console.print("  1. Generate audio file using TTS")
            console.print("  2. Send audio to robot via daemon (if supported)")
            console.print("  3. Or use external audio routing")
        elif tts_method == "daemon":
            console.print("\n[green]✓[/green] TTS is configured to use robot speakers!")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}", exc_info=True)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TTS functionality")
    parser.add_argument(
        "--daemon-url",
        type=str,
        default="http://127.0.0.1:8001",
        help="Reachy daemon URL (default: http://127.0.0.1:8001)"
    )
    parser.add_argument(
        "--audio-device",
        type=str,
        default=None,
        help="ALSA audio device (e.g., hw:1,0). If not specified, will auto-detect or use system default."
    )
    
    args = parser.parse_args()
    # If audio_device not provided, try to load from settings
    audio_device = args.audio_device
    if audio_device is None:
        try:
            settings = load_settings()
            audio_device = settings.audio_device
        except Exception:
            pass
    
    test_tts(args.daemon_url, audio_device=audio_device)

