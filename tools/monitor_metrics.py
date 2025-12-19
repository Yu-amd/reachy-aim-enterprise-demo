#!/usr/bin/env python3
"""
Real-time metrics monitoring with rich formatting.
Shows live metrics updates in a nice terminal dashboard.
"""

import time
import requests
import re
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

console = Console()

METRICS_URL = "http://127.0.0.1:9100/metrics"

def parse_metrics(metrics_text: str) -> dict:
    """Parse Prometheus metrics text into a dictionary."""
    metrics = {}
    
    # Parse counters and histograms
    for line in metrics_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # Match metric_name{labels} value or metric_name value
        match = re.match(r'^(\w+)(?:\{([^}]+)\})?\s+([\d.]+)', line)
        if match:
            name = match.group(1)
            labels = match.group(2) if match.group(2) else ""
            value = float(match.group(3))
            
            key = f"{name}{{{labels}}}" if labels else name
            metrics[key] = value
    
    return metrics

def get_metric_value(metrics: dict, pattern: str) -> float:
    """Get metric value by pattern matching."""
    for key, value in metrics.items():
        if pattern in key:
            return value
    return 0.0

def calculate_percentile(metrics: dict, metric_name: str, percentile: float) -> float:
    """Calculate percentile from histogram buckets."""
    # Find buckets
    buckets = []
    for key, value in metrics.items():
        if key.startswith(f"{metric_name}_bucket"):
            # Extract le value from labels
            match = re.search(r'le="([\d.]+)"', key)
            if match:
                le = float(match.group(1))
                buckets.append((le, value))
    
    if not buckets:
        return 0.0
    
    buckets.sort(key=lambda x: x[0])
    total = get_metric_value(metrics, f"{metric_name}_count")
    
    if total == 0:
        return 0.0
    
    target = total * (percentile / 100.0)
    cumulative = 0.0
    
    for le, count in buckets:
        cumulative = count
        if cumulative >= target:
            return le
    
    return buckets[-1][0] if buckets else 0.0

def create_dashboard(metrics: dict) -> Layout:
    """Create a rich dashboard layout."""
    layout = Layout()
    
    # Header
    header = Panel(
        Text("🔍 Real-time Metrics Dashboard", style="bold cyan"),
        style="bold"
    )
    
    # Stats table
    stats_table = Table(show_header=True, header_style="bold magenta", box=None)
    stats_table.add_column("Metric", style="cyan", width=30)
    stats_table.add_column("Value", style="green", width=20)
    
    # Request counters
    requests = get_metric_value(metrics, "edge_requests_total")
    errors = get_metric_value(metrics, "edge_errors_total")
    slo_misses = get_metric_value(metrics, "edge_slo_miss_total")
    backend_failures = get_metric_value(metrics, "backend_failures_total")
    
    stats_table.add_row("Total Requests", f"{int(requests):,}")
    stats_table.add_row("Errors", f"{int(errors):,}")
    stats_table.add_row("SLO Misses (>2500ms)", f"{int(slo_misses):,}")
    stats_table.add_row("Backend Failures", f"{int(backend_failures):,}")
    
    # Latency table
    latency_table = Table(show_header=True, header_style="bold yellow", box=None)
    latency_table.add_column("Metric", style="cyan", width=30)
    latency_table.add_column("Value", style="green", width=20)
    
    llm_sum = get_metric_value(metrics, "llm_call_ms_sum")
    llm_count = get_metric_value(metrics, "llm_call_ms_count")
    e2e_sum = get_metric_value(metrics, "edge_e2e_ms_sum")
    e2e_count = get_metric_value(metrics, "edge_e2e_ms_count")
    
    llm_avg = (llm_sum / llm_count * 1000) if llm_count > 0 else 0
    e2e_avg = (e2e_sum / e2e_count * 1000) if e2e_count > 0 else 0
    
    llm_p50 = calculate_percentile(metrics, "llm_call_ms", 50)
    llm_p95 = calculate_percentile(metrics, "llm_call_ms", 95)
    e2e_p50 = calculate_percentile(metrics, "edge_e2e_ms", 50)
    e2e_p95 = calculate_percentile(metrics, "edge_e2e_ms", 95)
    
    latency_table.add_row("LLM Call - Average", f"{llm_avg:.0f}ms")
    latency_table.add_row("LLM Call - P50", f"{llm_p50:.0f}ms")
    latency_table.add_row("LLM Call - P95", f"{llm_p95:.0f}ms")
    latency_table.add_row("E2E Latency - Average", f"{e2e_avg:.0f}ms")
    latency_table.add_row("E2E Latency - P50", f"{e2e_p50:.0f}ms")
    latency_table.add_row("E2E Latency - P95", f"{e2e_p95:.0f}ms")
    
    # Gesture table
    gesture_table = Table(show_header=True, header_style="bold blue", box=None)
    gesture_table.add_column("Gesture", style="cyan", width=20)
    gesture_table.add_column("Count", style="green", width=15)
    
    for key, value in metrics.items():
        if key.startswith("gesture_selected_total{"):
            # Extract gesture name
            match = re.search(r'gesture="([^"]+)"', key)
            if match:
                gesture = match.group(1)
                gesture_table.add_row(gesture, f"{int(value):,}")
    
    # Combine into layout
    layout.split_column(
        Layout(header, size=3),
        Layout(Panel(stats_table, title="📊 Request Statistics", border_style="magenta"), name="stats"),
        Layout(Panel(latency_table, title="⏱️  Latency Metrics", border_style="yellow"), name="latency"),
        Layout(Panel(gesture_table, title="🎭 Gesture Selection", border_style="blue"), name="gestures"),
    )
    
    return layout

def main():
    """Main monitoring loop."""
    console.print("[bold green]Starting real-time metrics monitor...[/bold green]")
    console.print(f"[dim]Metrics URL: {METRICS_URL}[/dim]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    
    try:
        with Live(create_dashboard({}), refresh_per_second=2, screen=True) as live:
            while True:
                try:
                    response = requests.get(METRICS_URL, timeout=1)
                    if response.status_code == 200:
                        metrics = parse_metrics(response.text)
                        live.update(create_dashboard(metrics))
                    else:
                        console.print(f"[red]Error: HTTP {response.status_code}[/red]")
                except requests.exceptions.RequestException as e:
                    live.update(Panel(
                        f"[red]Cannot connect to metrics server[/red]\n"
                        f"Error: {e}\n\n"
                        f"Make sure 'make run' is running and metrics server is accessible at:\n"
                        f"{METRICS_URL}",
                        title="❌ Connection Error",
                        border_style="red"
                    ))
                
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Monitoring stopped.[/bold yellow]")

if __name__ == "__main__":
    main()

