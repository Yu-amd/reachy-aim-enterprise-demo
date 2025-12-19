from __future__ import annotations

import time
import re
from typing import List, Dict

from rich.console import Console
from rich.panel import Panel

from ..aim.client import AIMClient
from ..obs.metrics import (
    EDGE_E2E_MS, AIM_CALL_MS, REQUESTS, ERRORS, SLO_MISS,
    BACKEND_FAILURES, GESTURE_SELECTED
)
from ..adapters.robot_base import RobotAdapter
from .prompts import SYSTEM_PROMPT
from .gesture_mapping import select_gesture
from ..policy.latency_policy import LatencyPolicy

console = Console()

# Available gestures for command help
AVAILABLE_GESTURES = [
    "ack", "nod_fast", "nod_tilt", "thinking_done", "error",
    "nod", "excited", "thinking", "greeting", "happy", "confused",
    "listening", "agreeing", "surprised", "curious", "emphatic",
    "no", "random", "wake_up", "goto_sleep",
    # Recorded moves (examples - actual moves depend on daemon datasets)
    "recorded:default:jackson_square",  # Example format
    "recorded:default:interwoven_spirals",  # Example format
]

def _handle_direct_command(cmd_text: str, robot: RobotAdapter, console: Console) -> None:
    """Handle direct robot commands (bypasses LLM).
    
    Commands:
    - cmd:gesture <name> - Execute a gesture directly
    - cmd:reset - Reset robot to home position
    - cmd:calibrate - Calibrate current position as home
    - cmd:state - Show current robot state
    - cmd:help - Show available commands
    """
    cmd_text = cmd_text[4:].strip()  # Remove "cmd:" prefix
    
    if not cmd_text:
        console.print("[yellow]Usage:[/yellow] cmd:<command>")
        console.print("Type [cyan]cmd:help[/cyan] for available commands")
        return
    
    parts = cmd_text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    try:
        if command == "gesture":
            if not args:
                console.print("[red]Error:[/red] Gesture name required")
                console.print(f"Available gestures: {', '.join(AVAILABLE_GESTURES)}")
                return
            
            gesture_name = args.strip()
            console.print(f"[cyan]Executing gesture:[/cyan] {gesture_name}")
            robot.gesture(gesture_name)
            console.print(f"[green]✓ Gesture '{gesture_name}' executed[/green]")
            
        elif command == "reset":
            console.print("[cyan]Resetting robot to home position...[/cyan]")
            try:
                # Get initial state
                initial_state = robot.get_state()
                initial_pose = initial_state.get("head_pose", {})
                console.print(f"[dim]Initial state: pitch={initial_pose.get('pitch', 0.0):.3f}, yaw={initial_pose.get('yaw', 0.0):.3f}, roll={initial_pose.get('roll', 0.0):.3f}[/dim]")
                
                robot.reset()
                
                # Get final state to show user
                state = robot.get_state()
                head_pose = state.get("head_pose", {})
                antennas = state.get("antennas_position", [0.0, 0.0])
                body_yaw = state.get("body_yaw", 0.0)
                
                # Calculate movement
                pitch_change = abs(head_pose.get('pitch', 0.0) - initial_pose.get('pitch', 0.0))
                yaw_change = abs(head_pose.get('yaw', 0.0) - initial_pose.get('yaw', 0.0))
                roll_change = abs(head_pose.get('roll', 0.0) - initial_pose.get('roll', 0.0))
                max_change = max(pitch_change, yaw_change, roll_change)
                
                if max_change < 0.01:
                    console.print(f"[yellow]⚠ Warning: Robot barely moved (max change: {max_change:.3f})[/yellow]")
                    console.print("[yellow]This suggests the reset commands may not be working. Check daemon logs.[/yellow]")
                else:
                    console.print(f"[green]✓ Robot reset complete (moved: pitch={pitch_change:.3f}, yaw={yaw_change:.3f}, roll={roll_change:.3f})[/green]")
                
                # Calculate antenna errors for display
                antenna_left = antennas[0] if len(antennas) > 0 else 0.0
                antenna_right = antennas[1] if len(antennas) > 1 else 0.0
                console.print(f"[dim]Final state: pitch={head_pose.get('pitch', 0.0):.3f}, yaw={head_pose.get('yaw', 0.0):.3f}, roll={head_pose.get('roll', 0.0):.3f}[/dim]")
                console.print(f"[dim]Antennas: left={antenna_left:.3f}, right={antenna_right:.3f}, body={body_yaw:.3f}[/dim]")
            except Exception as e:
                import traceback
                console.print(f"[red]✗ Reset failed:[/red] {e}")
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
                console.print("[yellow]Tip: Check that the daemon is running and accessible. Try 'cmd:state' to verify connection.[/yellow]")
                console.print("[yellow]Enable debug logging with: export PYTHONPATH=src && python -m reachy_demo.main --log-level DEBUG[/yellow]")
            
        elif command == "calibrate":
            console.print("[cyan]Calibrating home position...[/cyan]")
            console.print("[yellow]Make sure the robot is in the desired neutral position![/yellow]")
            robot.calibrate_home()
            console.print("[green]✓ Home position calibrated[/green]")
            
        elif command == "state":
            state = robot.get_state()
            head_pose = state.get("head_pose", {})
            antennas = state.get("antennas_position", [0.0, 0.0])
            body_yaw = state.get("body_yaw", 0.0)
            
            from rich.table import Table
            table = Table(title="Robot State", show_header=True, header_style="bold cyan")
            table.add_column("Axis", style="yellow")
            table.add_column("Value", style="green", justify="right")
            
            table.add_row("Head Pitch", f"{head_pose.get('pitch', 0.0):.4f}")
            table.add_row("Head Yaw", f"{head_pose.get('yaw', 0.0):.4f}")
            table.add_row("Head Roll", f"{head_pose.get('roll', 0.0):.4f}")
            table.add_row("Antenna Left", f"{antennas[0] if len(antennas) > 0 else 0.0:.4f}")
            table.add_row("Antenna Right", f"{antennas[1] if len(antennas) > 1 else 0.0:.4f}")
            table.add_row("Body Yaw", f"{body_yaw:.4f}")
            
            console.print(table)
            
        elif command == "help":
            from rich.table import Table
            table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
            table.add_column("Command", style="yellow")
            table.add_column("Description", style="green")
            
            table.add_row("cmd:gesture <name>", "Execute a gesture directly (bypasses LLM)")
            table.add_row("cmd:reset", "Reset robot to home position")
            table.add_row("cmd:calibrate", "Calibrate current position as home")
            table.add_row("cmd:state", "Show current robot state")
            table.add_row("cmd:help", "Show this help message")
            
            console.print(table)
            console.print(f"\n[bold]Available gestures:[/bold] {', '.join(AVAILABLE_GESTURES)}")
            
        else:
            console.print(f"[red]Unknown command:[/red] {command}")
            console.print("Type [cyan]cmd:help[/cyan] for available commands")
            
    except Exception as e:
        console.print(f"[red]Command failed:[/red] {e}")

def run_interactive_loop(
    aim: AIMClient,
    robot: RobotAdapter,
    model: str,
    e2e_slo_ms: int = 2500,
    max_tokens: int = 80,
) -> None:
    """
    Enterprise-responsive interactive loop with latency-aware gestures.
    
    Provides immediate feedback and selects gestures based on measured latency
    to create a responsive, professional user experience.
    """
    convo: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    policy = LatencyPolicy()

    console.print(Panel.fit(
        "Reachy Enterprise Demo (Enterprise-Responsive)\n"
        "Type a prompt and press Enter. Ctrl+C to quit.\n"
        "[dim]Use 'cmd:help' for direct robot control commands[/dim]",
        title="Ready"
    ))

    if not robot.health():
        console.print("[yellow]Warning:[/yellow] Reachy daemon not reachable at configured URL. Continuing without robot control.")

    while True:
        try:
            user_text = console.input("\n[bold cyan]You> [/bold cyan]").strip()
            if not user_text:
                continue

            # Check for direct command (bypasses LLM)
            if user_text.lower().startswith("cmd:"):
                _handle_direct_command(user_text, robot, console)
                continue

            # Start E2E timer
            t0 = time.perf_counter()
            REQUESTS.inc()

            # Immediate feedback: show acknowledgment gesture
            try:
                pre_gesture = policy.choose_pre_gesture()
                robot.gesture(pre_gesture)
                GESTURE_SELECTED.labels(gesture=pre_gesture).inc()
            except Exception:
                pass  # Don't break on gesture failure

            convo.append({"role": "user", "content": user_text})
            messages = convo[-20:]  # bounded context

            # Call inference endpoint
            t1 = time.perf_counter()
            ok = False
            text = ""
            aim_ms = 0.0
            
            try:
                resp = aim.chat(model=model, messages=messages, temperature=0.2, max_tokens=max_tokens, stream=False)
                t2 = time.perf_counter()
                ok = True
                aim_ms = (t2 - t1) * 1000.0
                AIM_CALL_MS.observe(aim_ms)
                text = resp.text.strip()
                
                # Strip thinking tokens if present (common formats)
                # Some models wrap thinking in tags like [thinking]...[/thinking] or <think>...</think>
                thinking_patterns = [
                    r'\[thinking\].*?\[/thinking\]',
                    r'<think>.*?</think>',
                    r'<thinking>.*?</thinking>',
                    r'```thinking.*?```',
                ]
                
                original_text = text
                for pattern in thinking_patterns:
                    import re
                    text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
                
                # Also check for common thinking markers at the start
                # If text starts with thinking-like patterns, try to find where actual response begins
                thinking_markers = [
                    'let me think',
                    'thinking:',
                    'reasoning:',
                    'considering:',
                ]
                text_lower = text.lower()
                for marker in thinking_markers:
                    if text_lower.startswith(marker):
                        # Try to find where thinking ends (look for sentence breaks or newlines)
                        # Find first sentence after thinking
                        sentences = re.split(r'[.!?]\s+', text, maxsplit=2)
                        if len(sentences) > 1:
                            # Skip first sentence if it's clearly thinking
                            if marker in sentences[0].lower():
                                text = '. '.join(sentences[1:])
                                break
                
                text = text.strip()
                
                # If we stripped thinking but got empty text, use original
                if not text or len(text) < 10:
                    text = original_text.strip()
                    # Last resort: take last 2-3 sentences
                    sentences = re.split(r'[.!?]+', text)
                    if len(sentences) > 2:
                        text = '. '.join(sentences[-3:]).strip()
                        if text and not text.endswith('.'):
                            text += '.'
                
                # Check if response was truncated (hit token limit)
                # Some models include thinking tokens that count toward max_tokens
                if resp.completion_tokens is not None and resp.completion_tokens >= max_tokens * 0.9:
                    # Response likely hit token limit - truncate at last complete sentence
                    sentences = text.rsplit('.', 1)
                    if len(sentences) > 1 and sentences[0]:
                        text = sentences[0] + '.'
                        console.print("[yellow]Note: Response truncated to fit token limit[/yellow]")
                
                convo.append({"role": "assistant", "content": text})
            except Exception as inference_error:
                t2 = time.perf_counter()
                aim_ms = (t2 - t1) * 1000.0
                ok = False
                ERRORS.inc()
                BACKEND_FAILURES.inc()
                text = "Sorry, my inference backend is unavailable."
                console.print(f"[red]Inference error:[/red] {inference_error}")

            # Calculate end-to-end latency
            e2e_ms = (time.perf_counter() - t0) * 1000.0
            EDGE_E2E_MS.observe(e2e_ms)
            if e2e_ms > e2e_slo_ms:
                SLO_MISS.inc()

            # Select post-gesture based on latency and success
            try:
                post_gesture = policy.choose_post_gesture(aim_ms, e2e_ms, ok)
                robot.gesture(post_gesture)
                GESTURE_SELECTED.labels(gesture=post_gesture).inc()
                # Wait a bit for gesture to complete (gestures have internal timing)
                time.sleep(0.5)  # Give gesture time to finish
            except Exception:
                pass  # Don't break on gesture failure

            # Speak the response (or error message)
            try:
                robot.speak(text)
            except Exception:
                pass  # Don't break on TTS failure

            # Reset robot to neutral position after response
            # Wait a bit more to ensure gesture is fully complete
            time.sleep(0.3)
            try:
                robot.reset()
            except Exception:
                pass  # Don't break on reset failure

            # Display response with metrics
            console.print(Panel(
                text,
                title=f"AIM ({model})",
                subtitle=f"aim_call={aim_ms:.0f}ms  e2e={e2e_ms:.0f}ms  slo={e2e_slo_ms}ms  tier={policy.get_latency_tier(e2e_ms)}"
            ))
        except KeyboardInterrupt:
            console.print("\n[bold]Bye.[/bold]")
            return
        except Exception as e:
            ERRORS.inc()
            BACKEND_FAILURES.inc()
            console.print(f"[red]Error:[/red] {e}")
