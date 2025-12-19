#!/usr/bin/env python3
"""
Diagnose latency issues by testing the endpoint directly.
"""

import time
import requests
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def test_endpoint(base_url: str, model: str, chat_path: str = "/v1/chat/completions"):
    """Test endpoint latency directly."""
    url = f"{base_url}{chat_path}"
    
    console.print(f"[cyan]Testing endpoint:[/cyan] {url}")
    console.print(f"[cyan]Model:[/cyan] {model}\n")
    
    # Test 1: Simple request
    console.print("[yellow]Test 1: Simple request (10 tokens)[/yellow]")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
        "temperature": 0.2
    }
    
    try:
        start = time.perf_counter()
        response = requests.post(url, json=payload, timeout=60)
        duration = (time.perf_counter() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            console.print(f"[green]✓ Success:[/green] {duration:.0f}ms ({duration/1000:.2f}s)")
            console.print(f"   Tokens generated: {tokens}")
            console.print(f"   Tokens/second: {tokens / (duration/1000):.1f}\n")
        else:
            console.print(f"[red]✗ Error:[/red] HTTP {response.status_code}")
            console.print(f"   Response: {response.text[:200]}\n")
    except requests.exceptions.Timeout:
        console.print(f"[red]✗ Timeout after 60s[/red]\n")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}\n")
    
    # Test 2: Network latency
    console.print("[yellow]Test 2: Network latency (ping)[/yellow]")
    try:
        start = time.perf_counter()
        response = requests.get(f"{base_url}/health", timeout=5)
        duration = (time.perf_counter() - start) * 1000
        if response.status_code in [200, 404]:  # 404 is OK, means server is responding
            console.print(f"[green]✓ Network latency:[/green] {duration:.0f}ms\n")
        else:
            console.print(f"[yellow]⚠ Network test:[/yellow] HTTP {response.status_code} ({duration:.0f}ms)\n")
    except Exception as e:
        console.print(f"[yellow]⚠ Network test failed:[/yellow] {e}\n")
    
    # Test 3: Model info
    console.print("[yellow]Test 3: Model availability[/yellow]")
    try:
        models_url = f"{base_url}/v1/models"
        response = requests.get(models_url, timeout=5)
        if response.status_code == 200:
            models = response.json()
            model_list = models.get("data", [])
            console.print(f"[green]✓ Found {len(model_list)} model(s)[/green]")
            for m in model_list[:3]:
                console.print(f"   - {m.get('id', 'unknown')}")
            console.print()
        else:
            console.print(f"[yellow]⚠ Models endpoint:[/yellow] HTTP {response.status_code}\n")
    except Exception as e:
        console.print(f"[yellow]⚠ Models endpoint:[/yellow] {e}\n")

def main():
    """Main diagnostic function."""
    from reachy_demo.config import load_settings
    
    try:
        settings = load_settings()
    except Exception as e:
        console.print(f"[red]Error loading settings:[/red] {e}")
        console.print("[yellow]Make sure .env file exists and AIM_BASE_URL is set[/yellow]")
        sys.exit(1)
    
    console.print(Panel.fit(
        "[bold cyan]Latency Diagnostic Tool[/bold cyan]\n\n"
        "This tool tests your endpoint to identify latency bottlenecks.",
        title="Diagnostics"
    ))
    console.print()
    
    test_endpoint(settings.aim_base_url, settings.aim_model, settings.aim_chat_path)
    
    # Recommendations
    console.print(Panel(
        "[bold]Recommendations:[/bold]\n\n"
        "1. [cyan]Reduce max_tokens[/cyan] - Lower AIM_MAX_TOKENS in .env (default: 200)\n"
        "   Example: AIM_MAX_TOKENS=50\n\n"
        "2. [cyan]Check network latency[/cyan] - SSH port forward adds overhead\n"
        "   Consider: Direct connection or local endpoint\n\n"
        "3. [cyan]Model size[/cyan] - Mistral 24B is large, expect 5-15s per request\n"
        "   Consider: Smaller model for faster responses\n\n"
        "4. [cyan]First request[/cyan] - First request is often slower (model loading)\n"
        "   Subsequent requests should be faster\n\n"
        "5. [cyan]Streaming[/cyan] - Enable streaming for faster time-to-first-token\n"
        "   (Not currently implemented in this demo)",
        title="💡 Tips",
        border_style="yellow"
    ))

if __name__ == "__main__":
    main()

