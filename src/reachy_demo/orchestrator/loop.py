from __future__ import annotations

import os
import time
import re
import logging
import threading
from typing import List, Dict

from rich.console import Console
from rich.text import Text

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
            try:
                logger.info(f"Executing gesture command: {gesture_name}")
                robot.gesture(gesture_name)
                logger.info(f"Gesture '{gesture_name}' completed successfully")
                # Special feedback for sleep/wake gestures
                if gesture_name == "goto_sleep":
                    console.print(f"[green]✓ Sleep gesture executed - robot is going to sleep[/green]")
                elif gesture_name == "wake_up":
                    console.print(f"[green]✓ Wake gesture executed - robot is waking up[/green]")
                else:
                    console.print(f"[green]✓ Gesture '{gesture_name}' executed[/green]")
            except Exception as e:
                logger.error(f"Gesture '{gesture_name}' failed: {e}", exc_info=True)
                console.print(f"[red]✗ Gesture '{gesture_name}' failed:[/red] {e}")
                # Show more details for debugging
                error_str = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    console.print(f"[red]  Response status: {e.response.status_code}[/red]")
                    console.print(f"[red]  Response body: {e.response.text[:200]}[/red]")
                # For critical gestures, show full error
                if gesture_name in ["goto_sleep", "wake_up"]:
                    console.print(f"[yellow]  Full error details logged (check logs with --log-level DEBUG)[/yellow]")
            
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
    robot_is_asleep = False  # Track if robot is in sleep state

    # Only suppress warnings if not in DEBUG mode (enterprise-ready output)
    # If user set log-level to DEBUG, respect that setting
    current_level = logging.getLogger().getEffectiveLevel()
    if current_level > logging.DEBUG:
        # Suppress warnings for enterprise-ready output (unless DEBUG mode)
        logging.getLogger().setLevel(logging.ERROR)
    
    # Clear terminal for clean start
    os.system('clear' if os.name != 'nt' else 'cls')
    
    # Minimal startup message
    print("Enterprise Demo Ready")
    print("=" * 50)

    while True:
        try:
            # Enterprise header (plain text, no color) - only show once at start
            if not hasattr(run_interactive_loop, '_header_shown'):
                print("reachy-aim-demo")
                print("----------------")
                print()
                run_interactive_loop._header_shown = True
            
            # Get user input with prompt label (cyan)
            console.print("[cyan]Prompt:[/cyan] ", end="")
            try:
                user_text = input().strip()
            except (EOFError, KeyboardInterrupt):
                # Handle EOF (Ctrl+D) or Ctrl+C gracefully
                console.print("\n[bold]Bye.[/bold]")
                return
            if not user_text:
                continue
            
            logger.debug(f"Processing user input: '{user_text[:50]}...' (length: {len(user_text)})")
            
            # Check for direct command (bypasses LLM) - check BEFORE auto-wake
            if user_text.lower().startswith("cmd:"):
                cmd_lower = user_text.lower()
                # Track sleep state BEFORE executing command
                if "goto_sleep" in cmd_lower or "sleep" in cmd_lower:
                    robot_is_asleep = True
                elif "wake_up" in cmd_lower or "wake" in cmd_lower:
                    robot_is_asleep = False
                
                # Execute command (don't auto-wake if user explicitly wants to sleep)
                _handle_direct_command(user_text, robot, console)
                continue
            
            # Auto-wake robot if it's asleep (only for regular prompts, not commands)
            if robot_is_asleep:
                try:
                    robot.gesture("wake_up")
                    robot_is_asleep = False
                    time.sleep(0.5)  # Give wake animation time to start
                except Exception:
                    pass  # Don't break if wake fails

            # Start E2E timer
            t0 = time.perf_counter()
            REQUESTS.inc()

            # Detect backend type for display
            base_url_lower = aim.base_url.lower()
            if ':1234' in base_url_lower or 'lmstudio' in base_url_lower:
                backend_name = "LMStudio"
            elif 'localhost' in base_url_lower or '127.0.0.1' in base_url_lower:
                # Check if it's a port-forwarded remote endpoint (port 8000) vs local
                # Port 8000 is typically used for remote AIM endpoints via SSH port forward
                # Port 1234 is LMStudio (already handled above)
                if ':8000' in base_url_lower:
                    backend_name = "AIM (remote)"
                else:
                    backend_name = "AIM (local)"
            elif 'prod' in base_url_lower or 'production' in base_url_lower:
                backend_name = "AIM (prod)"
            elif any(domain in base_url_lower for domain in ['http://', 'https://']) and not ('localhost' in base_url_lower or '127.0.0.1' in base_url_lower):
                # Has protocol and is not localhost - likely remote
                backend_name = "AIM (remote)"
            else:
                backend_name = "AIM (OpenAI-compatible)"
            
            # Show backend info (prompt already shown in input line) - cyan for headers
            console.print(f"[cyan]Backend:[/cyan] {backend_name}")
            console.print(f"[cyan]Target SLO:[/cyan] < {e2e_slo_ms/1000.0:.1f}s")
            print()
            
            # Immediate feedback: show acknowledgment gesture
            try:
                pre_gesture = policy.choose_pre_gesture()
                robot.gesture(pre_gesture)
                GESTURE_SELECTED.labels(gesture=pre_gesture).inc()
                text = Text()
                text.append("[", style="green")
                text.append("edge", style="green bold")
                text.append("]", style="green")
                text.append(" ACK gesture sent")
                console.print(text)
            except Exception:
                pass  # Don't break on gesture failure

            convo.append({"role": "user", "content": user_text})
            messages = convo[-20:]  # bounded context

            # Call inference endpoint
            text = Text()
            text.append("[", style="blue")
            text.append("inference", style="blue bold")
            text.append("]", style="blue")
            text.append(" Request dispatched")
            console.print(text)
            t1 = time.perf_counter()
            ok = False
            text = ""
            aim_ms = 0.0
            thinking_gesture_started = False
            
            # Start thinking gesture in background if we expect latency > 700ms
            # (We'll check actual latency during the call and start it if needed)
            thinking_thread = None
            
            def start_thinking_if_needed():
                """Start thinking gesture if latency exceeds 700ms."""
                nonlocal thinking_gesture_started
                check_interval = 0.1  # Check every 100ms
                elapsed = 0.0
                while elapsed < 5.0:  # Max 5 seconds
                    time.sleep(check_interval)
                    elapsed = (time.perf_counter() - t1) * 1000.0
                    if elapsed > 700.0 and not thinking_gesture_started:
                        try:
                            robot.gesture("thinking")
                            thinking_gesture_started = True
                        except Exception:
                            pass
                        break
            
            # Start monitoring thread
            thinking_thread = threading.Thread(target=start_thinking_if_needed, daemon=True)
            thinking_thread.start()
            
            try:
                logger.debug(f"Calling AIM client: model={model}, messages={len(messages)}, max_tokens={max_tokens}")
                resp = aim.chat(model=model, messages=messages, temperature=0.2, max_tokens=max_tokens, stream=False)
                logger.debug(f"AIM client returned response: {type(resp)}, has text: {hasattr(resp, 'text') if resp else 'None'}")
                t2 = time.perf_counter()
                ok = True
                aim_ms = (t2 - t1) * 1000.0
                # Record LLM call latency (enterprise metrics)
                LLM_CALL_MS.observe(aim_ms)
                AIM_CALL_MS.observe(aim_ms)  # Backward compatibility
                
                # Show latency in milliseconds with color coding (green/yellow/red by threshold)
                if aim_ms < 800:
                    latency_color = "green"
                elif aim_ms < 2500:
                    latency_color = "yellow"
                else:
                    latency_color = "red"
                
                latency_display = Text()
                latency_display.append("[", style="blue")
                latency_display.append("inference", style="blue bold")
                latency_display.append("]", style="blue")
                latency_display.append(" Response received (")
                latency_display.append(f"{int(aim_ms)} ms", style=latency_color)
                latency_display.append(")")
                console.print(latency_display)
                
                # Extract response text - handle empty or None responses
                if not resp or not hasattr(resp, 'text') or not resp.text:
                    logger.warning(f"Empty response object from AIM: {resp}")
                    text = "I'm sorry, I didn't receive a valid response."
                    original_text = text
                else:
                    text = resp.text.strip()
                    original_text = text
                    
                    # Log if response is suspiciously short
                    if len(text) < 5:
                        logger.warning(f"Very short response from AIM: '{text}' (length: {len(text)})")
                
                # Check if this response contains thinking tokens
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
                
                # Detect if THIS response contains thinking tokens
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
                # This is just for tracking/logging purposes
                if has_thinking_tokens and not is_thinking_model:
                    is_thinking_model = True
                    logger.debug(f"🤖 Detected thinking model: thinking tokens found in response")
                
                # Note: We don't turn the body for thinking pose because:
                # 1. We can't know if there are thinking tokens until after we get the response
                # 2. Turning the body after the response defeats the purpose of showing "thinking"
                # 3. The user reported the body was turning even when there were no thinking tokens
                # So we've removed the thinking pose feature to avoid false positives
                
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
                # These patterns catch thinking text that doesn't have explicit tags
                thinking_markers = [
                    r'let me think[^.!?]*[.!?]?\s*',
                    r'thinking:[^.!?]*[.!?]?\s*',
                    r'reasoning:[^.!?]*[.!?]?\s*',
                    r'considering:[^.!?]*[.!?]?\s*',
                    r'okay,?\s+the\s+user\s+is\s+asking[^.!?]*[.!?]?\s*',  # "Okay, the user is asking..."
                    r'i\s+need\s+to\s+define[^.!?]*[.!?]?\s*',  # "I need to define..."
                    r'let\s+me\s+start\s+by[^.!?]*[.!?]?\s*',  # "Let me start by..."
                    r'i\s+should\s+also\s+consider[^.!?]*[.!?]?\s*',  # "I should also consider..."
                    r'now,?\s+a\s+[^.!?]*\s+in\s+this\s+context[^.!?]*[.!?]?\s*',  # "Now, a ... in this context..."
                ]
                for marker_pattern in thinking_markers:
                    text = re.sub(marker_pattern, '', text, flags=re.IGNORECASE)
                
                # Detect and remove thinking blocks that start with meta-commentary
                # These are common patterns where the model explains its reasoning without tags
                # Pattern: Text that starts with "Okay, the user..." or "I need to..." followed by long reasoning
                thinking_start_patterns = [
                    r'^okay,?\s+the\s+user[^.!?]*?\.\s+[^.!?]*?\.\s+[^.!?]*?\.',  # Multiple sentences starting with "Okay, the user"
                    r'^i\s+need\s+to[^.!?]*?\.\s+[^.!?]*?\.\s+[^.!?]*?\.',  # Multiple sentences starting with "I need to"
                ]
                for pattern in thinking_start_patterns:
                    # Find the thinking block and extract only the final answer
                    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
                    if match:
                        # Try to find where the actual answer starts (usually after "So," or "Therefore," or a definition)
                        answer_start = re.search(r'(?:so,?\s+|therefore,?\s+|in\s+summary,?\s+|to\s+answer[^:]*:\s*)([A-Z][^.!?]*[.!?])', text[match.end():], flags=re.IGNORECASE)
                        if answer_start:
                            text = text[match.end() + answer_start.start() + answer_start.end(1):].strip()
                        else:
                            # If no clear answer marker, try to find the last sentence which is usually the answer
                            sentences = re.split(r'([.!?]+)', text[match.end():])
                            if len(sentences) >= 4:  # At least 2 sentences
                                # Take the last 1-2 sentences as the answer
                                text = ''.join(sentences[-4:]).strip()
                            else:
                                # If no good answer found, just remove the thinking block
                                text = text[match.end():].strip()
                
                # Additional heuristic: If text is very long (>1000 chars) and starts with thinking patterns,
                # try to extract just the final answer (usually the last 2-3 sentences)
                if len(text) > 1000:
                    # Check if it starts with thinking patterns
                    thinking_indicators = [
                        r'^okay,?\s+the\s+user',
                        r'^i\s+need\s+to',
                        r'^let\s+me\s+start\s+by',
                        r'^i\s+should\s+also',
                    ]
                    starts_with_thinking = any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in thinking_indicators)
                    if starts_with_thinking:
                        # Try to find the actual answer - usually starts with "So," "Therefore," or is the last sentence
                        answer_markers = [
                            r'(?:so,?\s+|therefore,?\s+|in\s+summary,?\s+|to\s+answer[^:]*:\s*)([^.!?]+[.!?])',
                            r'(?:the\s+answer\s+is[^.!?]*[.!?])',
                            r'(?:in\s+conclusion[^.!?]*[.!?])',
                        ]
                        answer_found = False
                        for marker in answer_markers:
                            matches = list(re.finditer(marker, text, flags=re.IGNORECASE))
                            if matches:
                                # Take text from the last match onwards
                                text = text[matches[-1].start():].strip()
                                answer_found = True
                                break
                        
                        if not answer_found:
                            # Fallback: take the last 2-3 sentences
                            sentences = re.split(r'([.!?]+)', text)
                            if len(sentences) >= 4:
                                text = ''.join(sentences[-6:]).strip()  # Last 2-3 sentences
                
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
                
                # Ensure we have valid text before appending to conversation
                if not text or not text.strip():
                    logger.warning(f"Empty response from AIM, using fallback message")
                    text = "I'm sorry, I didn't receive a valid response."
                
                # Only append to conversation if we have valid text
                if text and text.strip():
                    convo.append({"role": "assistant", "content": text})
                    logger.debug(f"Added assistant response to conversation (total messages: {len(convo)})")
                else:
                    logger.warning(f"Skipping empty assistant response, not adding to conversation")
            except Exception as inference_error:
                t2 = time.perf_counter()
                aim_ms = (t2 - t1) * 1000.0
                ok = False
                ERRORS.inc()
                BACKEND_FAILURES.inc()
                
                # Log the full error for debugging
                logger.error(f"Inference error: {inference_error}", exc_info=True)
                
                # Note: We don't turn body on error since we never turned it in the first place
                # (We only turn body if we detect thinking tokens in the response)
                
                # Provide more detailed error message
                error_type = type(inference_error).__name__
                error_str = str(inference_error)
                
                # Check for common connection errors
                if "Connection" in error_type or "connection" in error_str.lower():
                    error_message = f"Connection error: Cannot reach AIM endpoint at {aim.base_url}. Check your AIM_BASE_URL in .env file."
                elif "Timeout" in error_type or "timeout" in error_str.lower():
                    error_message = f"Timeout: AIM endpoint at {aim.base_url} did not respond in time. Try increasing AIM_TIMEOUT_MS in .env."
                elif "404" in error_str or "Not Found" in error_str:
                    error_message = f"Endpoint not found: {aim.base_url}{aim.chat_path} may not exist. Check your AIM_BASE_URL and AIM_CHAT_PATH."
                elif "401" in error_str or "403" in error_str or "Unauthorized" in error_str:
                    error_message = f"Authentication error: Check your AIM_API_KEY in .env file."
                else:
                    error_message = f"Backend error: {error_str[:100]}"
                
                # Show error with latency (red for errors)
                error_display = Text()
                error_display.append("[", style="blue")
                error_display.append("inference", style="blue bold")
                error_display.append("]", style="blue")
                error_display.append(" Request failed (")
                error_display.append(f"{int(aim_ms)} ms", style="red")
                error_display.append(")")
                console.print(error_display)
                console.print(f"[red]Error:[/red] {error_message}")
                # Set text to a user-friendly error message for TTS
                text = "Sorry, my inference backend is unavailable."

            # Calculate end-to-end latency
            e2e_ms = (time.perf_counter() - t0) * 1000.0
            EDGE_E2E_MS.observe(e2e_ms)
            if e2e_ms > e2e_slo_ms:
                SLO_MISS.inc()

            # Show completion gesture (enterprise: return to neutral, one small nod)
            try:
                robot.gesture("complete")
                GESTURE_SELECTED.labels(gesture="complete").inc()
            except Exception:
                pass  # Don't break on gesture failure
            
            # Use a different variable name to avoid overwriting the response text
            completion_text = Text()
            completion_text.append("[", style="green")
            completion_text.append("edge", style="green bold")
            completion_text.append("]", style="green")
            completion_text.append(" Completion gesture sent")
            console.print(completion_text)
            print()  # Blank line for readability

            # Speak the response (or error message)
            # Note: speak() is blocking and already waits for TTS to complete
            # No need to wait again after it returns
            try:
                if text and text.strip():
                    # Limit TTS text length to prevent timeouts (max ~500 words or ~3000 chars)
                    # Average speaking rate is ~150 words/min, so 500 words = ~3.3 minutes max
                    max_tts_length = 3000
                    if len(text) > max_tts_length:
                        # Truncate at last complete sentence
                        truncated = text[:max_tts_length]
                        last_period = truncated.rfind('.')
                        last_exclamation = truncated.rfind('!')
                        last_question = truncated.rfind('?')
                        last_sentence_end = max(last_period, last_exclamation, last_question)
                        if last_sentence_end > max_tts_length * 0.7:  # Only truncate if we found a sentence end in the last 30%
                            text = truncated[:last_sentence_end + 1]
                        else:
                            # No good sentence break, just truncate and add ellipsis
                            text = truncated + "..."
                        logger.warning(f"TTS text truncated from {len(text)} to {len(text)} chars to prevent timeout")
                    robot.speak(text)
                    # speak() returns after TTS is complete, so we can reset immediately
                else:
                    logger.warning("TTS: Empty text, skipping speech")
            except Exception as e:
                logger.error(f"TTS failed: {e}", exc_info=True)
                # Don't break on TTS failure, but log it
                console.print(f"[yellow]⚠ TTS error: Text may be too long or contain invalid characters[/yellow]")

            # Reset robot to neutral position immediately after TTS completes
            # speak() already waited for TTS, so no additional wait needed
            try:
                robot.reset()
            except Exception:
                pass  # Don't break on reset failure
        except KeyboardInterrupt:
            console.print("\n[bold]Bye.[/bold]")
            return
        except Exception as e:
            ERRORS.inc()
            BACKEND_FAILURES.inc()
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Loop error: {e}", exc_info=True)
            # Continue the loop - don't exit on errors
            continue
