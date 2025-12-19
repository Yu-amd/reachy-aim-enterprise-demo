from __future__ import annotations

import time
import re
import logging
from typing import List, Dict

from rich.console import Console
from rich.panel import Panel

logger = logging.getLogger(__name__)

from ..aim.client import AIMClient
from ..obs.metrics import (
    EDGE_E2E_MS, LLM_CALL_MS, AIM_CALL_MS, REQUESTS, ERRORS, SLO_MISS,
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
                # Debug: Initial state (removed for cleaner output)
                
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
                # Debug: Final state and antennas (removed for cleaner output)
            except Exception as e:
                import traceback
                console.print(f"[red]✗ Reset failed:[/red] {e}")
                logger.debug(traceback.format_exc())
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
    is_thinking_model = False  # Track if model is a thinking model (False = assume non-thinking until detected)

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

            # Turn body to side to indicate thinking (only if model is a thinking model)
            # We start assuming it's NOT a thinking model, and only turn body if we detect thinking tokens
            if is_thinking_model:
                try:
                    robot.thinking_pose()
                except Exception:
                    pass  # Don't break on thinking pose failure

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
                # Record LLM call latency (enterprise metrics)
                LLM_CALL_MS.observe(aim_ms)
                AIM_CALL_MS.observe(aim_ms)  # Backward compatibility
                
                text = resp.text.strip()
                original_text = text
                
                # Check if this is a thinking model by detecting thinking tokens in the raw response
                thinking_patterns = [
                    r'\[thinking\].*?\[/thinking\]',  # [thinking]...[/thinking]
                    r'<think>.*?</think>',  # <think>...</think>
                    r'<thinking>.*?</thinking>',  # <thinking>...</thinking>
                    r'```thinking.*?```',  # ```thinking...```
                    r'\[thinking\].*',  # [thinking]... (unclosed, to end of text)
                    r'<thinking>.*',  # <thinking>... (unclosed, to end of text)
                ]
                
                thinking_delimiters = [
                    r'\[/thinking\]',
                    r'</thinking>',
                    r'</think>',
                ]
                
                # Detect if this response contains thinking tokens
                has_thinking_tokens = False
                for pattern in thinking_patterns:
                    if re.search(pattern, original_text, flags=re.DOTALL | re.IGNORECASE):
                        has_thinking_tokens = True
                        break
                if not has_thinking_tokens:
                    for delimiter in thinking_delimiters:
                        if re.search(delimiter, original_text, flags=re.IGNORECASE):
                            has_thinking_tokens = True
                            break
                
                # Update thinking model detection: if we find thinking tokens, mark as thinking model
                if has_thinking_tokens and not is_thinking_model:
                    is_thinking_model = True
                    logger.debug(f"🤖 Detected thinking model: thinking tokens found in response")
                
                # Return body from thinking pose (only if we turned it)
                if is_thinking_model:
                    try:
                        robot.return_from_thinking()
                    except Exception:
                        pass  # Don't break on return from thinking failure
                
                # Aggressively strip ALL thinking tokens (handle multiple occurrences)
                # Some models wrap thinking in tags like [thinking]...[/thinking] or <think>...</think>
                # We need to remove ALL occurrences, not just the first one
                # Apply patterns multiple times until no more matches (handle nested/overlapping)
                max_iterations = 10
                for iteration in range(max_iterations):
                    text_before = text
                    for pattern in thinking_patterns:
                        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
                    # Stop if no more changes
                    if text == text_before:
                        break
                
                # Also remove thinking markers at the start or anywhere
                thinking_markers = [
                    r'let me think[^.!?]*[.!?]?\s*',
                    r'thinking:[^.!?]*[.!?]?\s*',
                    r'reasoning:[^.!?]*[.!?]?\s*',
                    r'considering:[^.!?]*[.!?]?\s*',
                ]
                for marker_pattern in thinking_markers:
                    text = re.sub(marker_pattern, '', text, flags=re.IGNORECASE)
                
                text = text.strip()
                
                # If we have multiple sentences and thinking might have appeared in the middle,
                # take only the last part (after the last thinking block)
                # Split by common thinking delimiters and take the last meaningful part
                # BUT: Only do this if we actually found thinking blocks, to avoid corrupting normal text
                # Check if any thinking delimiters exist before splitting
                has_thinking = any(re.search(delimiter, text, flags=re.IGNORECASE) for delimiter in thinking_delimiters)
                
                if has_thinking:
                    # Only split if we actually have thinking blocks
                    for delimiter in thinking_delimiters:
                        parts = re.split(delimiter, text, flags=re.IGNORECASE)
                        if len(parts) > 1:
                            # Take the last part (after the last thinking block)
                            text = parts[-1].strip()
                
                # Clean up: remove any remaining thinking artifacts
                text = re.sub(r'\s*\[thinking\]\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*<thinking>\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*\[/thinking\]\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*</thinking>\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*<think>\s*', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s*</think>\s*', '', text, flags=re.IGNORECASE)
                
                # Normalize whitespace (but be careful not to create duplicates)
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Final check: ensure text doesn't contain duplicate sentences
                # Split by sentence boundaries and remove duplicates
                sentences = re.split(r'([.!?]+)', text)
                if len(sentences) > 3:
                    # Reconstruct, but skip obvious duplicates
                    seen = set()
                    unique_sentences = []
                    for i in range(0, len(sentences) - 1, 2):
                        if i + 1 < len(sentences):
                            sentence = (sentences[i] + sentences[i + 1]).strip()
                            sentence_lower = sentence.lower()
                            # Only add if we haven't seen this sentence before (fuzzy match)
                            if sentence_lower not in seen and len(sentence) > 5:
                                seen.add(sentence_lower)
                                unique_sentences.append(sentence)
                    if unique_sentences:
                        text = ' '.join(unique_sentences).strip()
                
                # If we stripped thinking but got empty or very short text, use original
                # But try to extract just the final response part
                if not text or len(text) < 10:
                    # Try to find the last complete sentence that doesn't look like thinking
                    sentences = re.split(r'([.!?]+)', original_text)
                    # Reconstruct sentences
                    clean_sentences = []
                    for i in range(0, len(sentences) - 1, 2):
                        if i + 1 < len(sentences):
                            sentence = (sentences[i] + sentences[i + 1]).strip()
                            # Skip sentences that look like thinking
                            sentence_lower = sentence.lower()
                            if not any(marker in sentence_lower for marker in ['thinking', 'reasoning', 'considering', '[thinking', '<thinking']):
                                clean_sentences.append(sentence)
                    
                    if clean_sentences:
                        # Take last 2-3 sentences
                        text = ' '.join(clean_sentences[-3:]).strip()
                    else:
                        # Last resort: use original but try to clean it
                        text = original_text.strip()
                        # Remove obvious thinking markers
                        for marker in ['[thinking]', '[/thinking]', '<thinking>', '</thinking>']:
                            text = text.replace(marker, '')
                        text = re.sub(r'\s+', ' ', text).strip()
                
                # Final cleanup: ensure we have valid text
                if not text or len(text.strip()) < 5:
                    text = original_text.strip()
                
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
                
                # Return body from thinking pose even on error (only if we turned it)
                if is_thinking_model:
                    try:
                        robot.return_from_thinking()
                    except Exception:
                        pass  # Don't break on return from thinking failure
                
                text = "Sorry, my inference backend is unavailable."
                console.print(f"[red]Inference error:[/red] {inference_error}")

            # Calculate end-to-end latency
            e2e_ms = (time.perf_counter() - t0) * 1000.0
            EDGE_E2E_MS.observe(e2e_ms)
            if e2e_ms > e2e_slo_ms:
                SLO_MISS.inc()

            # Note: Post-gesture removed - only ack gesture and reset are used
            # Metrics still tracked for monitoring
            try:
                post_gesture = policy.choose_post_gesture(aim_ms, e2e_ms, ok)
                GESTURE_SELECTED.labels(gesture=post_gesture).inc()  # Track for metrics only
            except Exception:
                pass  # Don't break on metrics failure

            # Speak the response (or error message)
            # Log the final text being spoken to debug duplicate audio issues
            # Debug: Final text to speak (removed for cleaner output)
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
