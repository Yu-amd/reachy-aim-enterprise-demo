from __future__ import annotations

import time
from typing import List, Dict

from rich.console import Console
from rich.panel import Panel

from ..aim.client import AIMClient
from ..obs.metrics import EDGE_E2E_MS, AIM_CALL_MS, REQUESTS, ERRORS, SLO_MISS
from ..adapters.robot_base import RobotAdapter
from .prompts import SYSTEM_PROMPT
from .gesture_mapping import select_gesture

console = Console()

def run_interactive_loop(
    aim: AIMClient,
    robot: RobotAdapter,
    model: str,
    e2e_slo_ms: int = 2500,
) -> None:
    convo: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    console.print(Panel.fit(
        "Reachy Enterprise Demo (sim-ready)\n"
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

            t0 = time.perf_counter()
            REQUESTS.inc()

            convo.append({"role": "user", "content": user_text})
            messages = convo[-20:]  # bounded context

            t1 = time.perf_counter()
            resp = aim.chat(model=model, messages=messages, temperature=0.2, max_tokens=180, stream=False)
            t2 = time.perf_counter()

            aim_ms = (t2 - t1) * 1000.0
            AIM_CALL_MS.observe(aim_ms)

            text = resp.text.strip()
            convo.append({"role": "assistant", "content": text})

            try:
                # Select gesture using intuitive mapping system based on LLM response analysis
                gesture_name = select_gesture(text, aim_ms)
                robot.gesture(gesture_name)
                robot.speak(text)
            except Exception:
                pass

            e2e_ms = (time.perf_counter() - t0) * 1000.0
            EDGE_E2E_MS.observe(e2e_ms)
            if e2e_ms > e2e_slo_ms:
                SLO_MISS.inc()

            console.print(Panel(
                text,
                title=f"AIM ({model})",
                subtitle=f"aim_call={aim_ms:.0f}ms  e2e={e2e_ms:.0f}ms  slo={e2e_slo_ms}ms"
            ))
        except KeyboardInterrupt:
            console.print("\n[bold]Bye.[/bold]")
            return
        except Exception as e:
            ERRORS.inc()
            console.print(f"[red]Error:[/red] {e}")
