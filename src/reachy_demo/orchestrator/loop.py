from __future__ import annotations

import time
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

def run_interactive_loop(
    aim: AIMClient,
    robot: RobotAdapter,
    model: str,
    e2e_slo_ms: int = 2500,
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
        "Type a prompt and press Enter. Ctrl+C to quit.",
        title="Ready"
    ))

    if not robot.health():
        console.print("[yellow]Warning:[/yellow] Reachy daemon not reachable at configured URL. Continuing without robot control.")

    while True:
        try:
            user_text = console.input("\n[bold cyan]You> [/bold cyan]").strip()
            if not user_text:
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
                resp = aim.chat(model=model, messages=messages, temperature=0.2, max_tokens=180, stream=False)
                t2 = time.perf_counter()
                ok = True
                aim_ms = (t2 - t1) * 1000.0
                AIM_CALL_MS.observe(aim_ms)
                text = resp.text.strip()
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
            except Exception:
                pass  # Don't break on gesture failure

            # Speak the response (or error message)
            try:
                robot.speak(text)
            except Exception:
                pass  # Don't break on TTS failure

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
