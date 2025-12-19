#!/usr/bin/env python3
"""
Query and analyze latency metrics from the Prometheus endpoint.
"""

import requests
import sys
import re
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

METRICS_URL = "http://127.0.0.1:9100/metrics"

def parse_metrics(metrics_text: str) -> Dict[str, float]:
    """Parse Prometheus metrics into a dictionary."""
    metrics = {}
    
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

def calculate_percentile(metrics: Dict[str, float], metric_name: str, percentile: float) -> float:
    """Calculate percentile from histogram buckets."""
    buckets = []
    for key, value in metrics.items():
        if key.startswith(f"{metric_name}_bucket"):
            match = re.search(r'le="([\d.]+)"', key)
            if match:
                le = float(match.group(1))
                buckets.append((le, value))
    
    if not buckets:
        return 0.0
    
    buckets.sort(key=lambda x: x[0])
    total = metrics.get(f"{metric_name}_count", 0.0)
    
    if total == 0:
        return 0.0
    
    target = total * (percentile / 100.0)
    cumulative = 0.0
    
    for le, count in buckets:
        cumulative = count
        if cumulative >= target:
            return le
    
    return buckets[-1][0] if buckets else 0.0

def get_metric_value(metrics: Dict[str, float], pattern: str) -> float:
    """Get metric value by pattern matching."""
    for key, value in metrics.items():
        if pattern in key:
            return value
    return 0.0

def query_latency_metrics() -> Optional[Dict]:
    """Query and analyze latency metrics."""
    try:
        response = requests.get(METRICS_URL, timeout=2)
        if response.status_code != 200:
            console.print(f"[red]Error:[/red] HTTP {response.status_code}")
            return None
        
        metrics = parse_metrics(response.text)
        
        # Extract key metrics
        llm_sum = get_metric_value(metrics, "llm_call_ms_sum")
        llm_count = get_metric_value(metrics, "llm_call_ms_count")
        e2e_sum = get_metric_value(metrics, "edge_e2e_ms_sum")
        e2e_count = get_metric_value(metrics, "edge_e2e_ms_count")
        
        requests_total = get_metric_value(metrics, "edge_requests_total")
        errors_total = get_metric_value(metrics, "edge_errors_total")
        slo_misses = get_metric_value(metrics, "edge_slo_miss_total")
        backend_failures = get_metric_value(metrics, "backend_failures_total")
        
        # Calculate statistics
        llm_avg = (llm_sum / llm_count * 1000) if llm_count > 0 else 0
        e2e_avg = (e2e_sum / e2e_count * 1000) if e2e_count > 0 else 0
        
        llm_p50 = calculate_percentile(metrics, "llm_call_ms", 50)
        llm_p95 = calculate_percentile(metrics, "llm_call_ms", 95)
        llm_p99 = calculate_percentile(metrics, "llm_call_ms", 99)
        
        e2e_p50 = calculate_percentile(metrics, "edge_e2e_ms", 50)
        e2e_p95 = calculate_percentile(metrics, "edge_e2e_ms", 95)
        e2e_p99 = calculate_percentile(metrics, "edge_e2e_ms", 99)
        
        # Gesture counts
        gestures = {}
        for key, value in metrics.items():
            if key.startswith("gesture_selected_total{"):
                match = re.search(r'gesture="([^"]+)"', key)
                if match:
                    gestures[match.group(1)] = int(value)
        
        return {
            "llm": {
                "count": int(llm_count),
                "sum": llm_sum,
                "avg": llm_avg,
                "p50": llm_p50,
                "p95": llm_p95,
                "p99": llm_p99,
            },
            "e2e": {
                "count": int(e2e_count),
                "sum": e2e_sum,
                "avg": e2e_avg,
                "p50": e2e_p50,
                "p95": e2e_p95,
                "p99": e2e_p99,
            },
            "requests": int(requests_total),
            "errors": int(errors_total),
            "slo_misses": int(slo_misses),
            "backend_failures": int(backend_failures),
            "gestures": gestures,
        }
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Cannot connect to metrics server:[/red] {e}")
        console.print(f"[yellow]Make sure 'make run' is running and metrics server is at {METRICS_URL}[/yellow]")
        return None

def display_metrics(data: Dict):
    """Display metrics in a nice format."""
    # Latency table
    latency_table = Table(title="⏱️  Latency Metrics", show_header=True, header_style="bold cyan", box=box.ROUNDED)
    latency_table.add_column("Metric", style="cyan", width=20)
    latency_table.add_column("Average", style="green", width=12)
    latency_table.add_column("P50", style="yellow", width=12)
    latency_table.add_column("P95", style="yellow", width=12)
    latency_table.add_column("P99", style="red", width=12)
    latency_table.add_column("Count", style="dim", width=10)
    
    latency_table.add_row(
        "LLM Call",
        f"{data['llm']['avg']:.0f}ms",
        f"{data['llm']['p50']:.0f}ms",
        f"{data['llm']['p95']:.0f}ms",
        f"{data['llm']['p99']:.0f}ms",
        str(data['llm']['count'])
    )
    
    latency_table.add_row(
        "End-to-End",
        f"{data['e2e']['avg']:.0f}ms",
        f"{data['e2e']['p50']:.0f}ms",
        f"{data['e2e']['p95']:.0f}ms",
        f"{data['e2e']['p99']:.0f}ms",
        str(data['e2e']['count'])
    )
    
    # Request statistics
    stats_table = Table(title="📊 Request Statistics", show_header=True, header_style="bold magenta", box=box.ROUNDED)
    stats_table.add_column("Metric", style="cyan", width=25)
    stats_table.add_column("Value", style="green", width=15)
    
    stats_table.add_row("Total Requests", f"{data['requests']:,}")
    stats_table.add_row("Errors", f"{data['errors']:,}")
    stats_table.add_row("SLO Misses (>2500ms)", f"{data['slo_misses']:,}")
    stats_table.add_row("Backend Failures", f"{data['backend_failures']:,}")
    
    if data['requests'] > 0:
        error_rate = (data['errors'] / data['requests']) * 100
        slo_compliance = ((data['requests'] - data['slo_misses']) / data['requests']) * 100
        stats_table.add_row("Error Rate", f"{error_rate:.1f}%")
        stats_table.add_row("SLO Compliance", f"{slo_compliance:.1f}%")
    
    # Gesture distribution
    gesture_table = Table(title="🎭 Gesture Selection", show_header=True, header_style="bold blue", box=box.ROUNDED)
    gesture_table.add_column("Gesture", style="cyan", width=20)
    gesture_table.add_column("Count", style="green", width=15)
    
    if data['gestures']:
        for gesture, count in sorted(data['gestures'].items(), key=lambda x: x[1], reverse=True):
            gesture_table.add_row(gesture, f"{count:,}")
    else:
        gesture_table.add_row("(no gestures yet)", "-")
    
    # Display
    console.print(latency_table)
    console.print()
    console.print(stats_table)
    console.print()
    console.print(gesture_table)
    
    # SLO status
    if data['e2e']['avg'] > 0:
        slo_target = 2500  # From config
        slo_status = "✓" if data['e2e']['avg'] <= slo_target else "❌"
        console.print()
        console.print(Panel(
            f"[bold]SLO Status:[/bold] {slo_status}\n"
            f"Target: {slo_target}ms\n"
            f"Current Average: {data['e2e']['avg']:.0f}ms\n"
            f"P95: {data['e2e']['p95']:.0f}ms",
            title="🎯 SLO Compliance",
            border_style="green" if data['e2e']['avg'] <= slo_target else "red"
        ))

def main():
    """Main function."""
    console.print(Panel.fit(
        "[bold cyan]Latency Metrics Query Tool[/bold cyan]\n\n"
        "Querying metrics from Prometheus endpoint...",
        title="Query"
    ))
    console.print()
    
    data = query_latency_metrics()
    if data:
        display_metrics(data)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

