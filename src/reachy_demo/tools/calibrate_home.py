#!/usr/bin/env python3
"""
Calibrate robot home position.

This tool allows you to manually set the robot's home/neutral position.
Position the robot in the desired neutral pose, then run this tool to capture it.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reachy_demo.config import load_settings
from reachy_demo.adapters.robot_sim import SimRobot
from reachy_demo.adapters.robot_rest import ReachyDaemonREST

app = typer.Typer(add_completion=False)
console = Console()


def _make_robot(settings):
    if settings.robot_mode.lower() == "sim":
        return SimRobot(settings.reachy_daemon_url)
    return ReachyDaemonREST(settings.reachy_daemon_url, audio_device=settings.audio_device)


@app.command()
def calibrate(
    show_current: bool = typer.Option(False, "--show", "-s", help="Show current position without calibrating"),
):
    """Calibrate home position: capture the robot's current position as the home/neutral position.
    
    Instructions:
    1. Position the robot in the desired neutral/home position (no tilt, centered)
    2. Run this command to capture that position
    3. After calibration, reset() will return the robot to this position
    """
    try:
        settings = load_settings()
        robot = _make_robot(settings)
        
        if not robot.health():
            console.print("[red]Error:[/red] Robot daemon not reachable. Make sure the daemon is running.")
            raise typer.Exit(1)
        
        # Get current state
        state = robot.get_state()
        current_pose = state.get("head_pose", {})
        current_antennas = state.get("antennas_position", [0.0, 0.0])
        current_body_yaw = state.get("body_yaw", 0.0)
        
        # Display current position
        table = Table(title="Current Robot Position", show_header=True, header_style="bold cyan")
        table.add_column("Axis", style="yellow")
        table.add_column("Value", style="green", justify="right")
        
        table.add_row("Head Pitch", f"{current_pose.get('pitch', 0.0):.4f}")
        table.add_row("Head Yaw", f"{current_pose.get('yaw', 0.0):.4f}")
        table.add_row("Head Roll", f"{current_pose.get('roll', 0.0):.4f}")
        table.add_row("Antenna Left", f"{current_antennas[0] if len(current_antennas) > 0 else 0.0:.4f}")
        table.add_row("Antenna Right", f"{current_antennas[1] if len(current_antennas) > 1 else 0.0:.4f}")
        table.add_row("Body Yaw", f"{current_body_yaw:.4f}")
        
        console.print(table)
        
        if show_current:
            console.print("\n[yellow]Note:[/yellow] Use --show to view position. Omit it to calibrate.")
            return
        
        # Confirm calibration
        console.print("\n[bold yellow]⚠ Warning:[/bold yellow] This will set the current position as the home position.")
        console.print("Make sure the robot is in the desired neutral position (no tilt, centered).")
        
        confirm = typer.confirm("Calibrate home position with current values?")
        if not confirm:
            console.print("[yellow]Calibration cancelled.[/yellow]")
            return
        
        # Calibrate
        robot.calibrate_home()
        
        console.print(Panel.fit(
            "[bold green]✓ Home position calibrated successfully![/bold green]\n\n"
            "The robot will now reset to this position when reset() is called.",
            title="Calibration Complete"
        ))
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def show():
    """Show current robot position (same as --show flag)."""
    calibrate(show_current=True)


if __name__ == "__main__":
    app()

