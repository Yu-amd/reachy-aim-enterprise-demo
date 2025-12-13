from __future__ import annotations

import time, statistics, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import typer
from rich.console import Console

from ..config import load_settings
from ..aim.client import AIMClient

app = typer.Typer(add_completion=False)
console = Console()

PROMPTS = [
    "Explain why HBM capacity matters for LLM inference in 4 sentences.",
    "Summarize what Kubernetes-native inference means.",
    "What is time-to-first-token and why does it matter?"
]

@app.command()
def run(concurrency: int = 8, duration_s: int = 30):
    s = load_settings()
    aim = AIMClient(s.aim_base_url, s.aim_chat_path, s.aim_api_key, s.aim_timeout_ms, s.aim_max_retries)
    end = time.time() + duration_s
    lat = []
    errors = 0

    console.print(f"[cyan]Starting load test:[/cyan] {concurrency} workers, {duration_s}s duration")
    console.print(f"[cyan]Target:[/cyan] {s.aim_base_url}{s.aim_chat_path}")
    console.print(f"[cyan]Model:[/cyan] {s.aim_model}\n")

    def one():
        t0 = time.perf_counter()
        try:
            aim.chat(
                model=s.aim_model,
                messages=[{"role":"user","content":random.choice(PROMPTS)}],
                max_tokens=120
            )
            return (time.perf_counter() - t0) * 1000.0, None
        except Exception as e:
            return None, str(e)

    futures = []
    start_time = time.time()
    last_progress = start_time
    request_count = 0
    
    # Calculate request interval based on concurrency and desired QPS
    # Default: 1 request per second per worker
    qps_per_worker = 1.0
    interval = 1.0 / (concurrency * qps_per_worker)
    
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        while time.time() < end:
            futures.append(ex.submit(one))
            request_count += 1
            # Rate limiting: wait between submissions
            time.sleep(interval)
            
            # Show progress every 5 seconds
            if time.time() - last_progress >= 5:
                elapsed = int(time.time() - start_time)
                remaining = int(end - time.time())
                completed = len(lat)
                in_flight = len([f for f in futures if not f.done()])
                console.print(f"[yellow]Progress:[/yellow] {elapsed}s elapsed, {remaining}s remaining, {request_count} submitted, {completed} successful, {in_flight} in-flight")
                last_progress = time.time()
        
        console.print(f"[cyan]Waiting for {len(futures)} requests to complete...[/cyan]")
        completed_count = 0
        for f in as_completed(futures):
            try:
                result, error = f.result()
                if result is not None:
                    lat.append(result)
                else:
                    errors += 1
                completed_count += 1
                # Show progress while waiting
                if completed_count % 100 == 0:
                    console.print(f"[yellow]Completed:[/yellow] {completed_count}/{len(futures)} requests")
            except Exception as e:
                errors += 1
                completed_count += 1

    if not lat:
        console.print(f"[red]No successful requests. {errors} errors occurred.[/red]")
        console.print("[yellow]Check your AIM_BASE_URL and ensure the endpoint is accessible.[/yellow]")
        raise typer.Exit(1)

    lat.sort()
    p50 = lat[int(0.50 * (len(lat)-1))]
    p95 = lat[int(0.95 * (len(lat)-1))]
    console.print(f"\n[green]Results:[/green]")
    console.print(f"  requests={len(lat)} successful, {errors} errors")
    console.print(f"  p50={p50:.0f}ms  p95={p95:.0f}ms  mean={statistics.mean(lat):.0f}ms")

if __name__ == "__main__":
    app()
