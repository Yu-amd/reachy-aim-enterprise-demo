from __future__ import annotations

import logging
import typer
from rich.console import Console

from .config import load_settings, Settings
from .aim.client import AIMClient
from .adapters.robot_sim import SimRobot
from .adapters.robot_rest import ReachyDaemonREST
from .obs.metrics import start_metrics_server
from .orchestrator.loop import run_interactive_loop

# Configure logging for robot adapter
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

app = typer.Typer(add_completion=False)
console = Console()

def _make_robot(settings: Settings):
    if settings.robot_mode.lower() == "sim":
        return SimRobot(settings.reachy_daemon_url)
    return ReachyDaemonREST(settings.reachy_daemon_url)

@app.command()
def run(
    aim_base_url: str = typer.Option(None, "--aim-base-url", help="Override AIM_BASE_URL"),
    reachy_daemon_url: str = typer.Option(None, "--reachy-daemon-url", help="Override REACHY_DAEMON_URL"),
    model: str = typer.Option(None, "--model", help="Override AIM_MODEL"),
):
    """Run the interactive edge demo (sim-ready)."""
    s = load_settings()
    if aim_base_url:
        s = Settings(**{**s.__dict__, "aim_base_url": aim_base_url.rstrip("/")})
    if reachy_daemon_url:
        s = Settings(**{**s.__dict__, "reachy_daemon_url": reachy_daemon_url.rstrip("/")})
    if model:
        s = Settings(**{**s.__dict__, "aim_model": model})

    start_metrics_server(s.metrics_host, s.metrics_port)
    console.print(f"[green]Edge metrics:[/green] http://{s.metrics_host}:{s.metrics_port}/metrics")

    aim = AIMClient(
        base_url=s.aim_base_url,
        chat_path=s.aim_chat_path,
        api_key=s.aim_api_key,
        timeout_ms=s.aim_timeout_ms,
        max_retries=s.aim_max_retries,
    )
    robot = _make_robot(s)
    run_interactive_loop(aim=aim, robot=robot, model=s.aim_model, e2e_slo_ms=s.e2e_slo_ms, max_tokens=s.aim_max_tokens)

if __name__ == "__main__":
    app()
