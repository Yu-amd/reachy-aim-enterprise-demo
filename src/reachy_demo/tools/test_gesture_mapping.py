#!/usr/bin/env python3
"""
Test script for gesture mapping system.

This script allows you to test how different LLM response texts
map to robot gestures. Useful for understanding and tuning the mapping.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from reachy_demo.orchestrator.gesture_mapping import select_gesture, analyze_text, GESTURE_MAPPING
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def test_response(text: str, response_time_ms: float = 1000):
    """Test a single response and show the analysis."""
    analysis = analyze_text(text)
    selected_gesture = select_gesture(text, response_time_ms)
    
    # Create analysis table
    table = Table(title="Text Analysis", show_header=True, header_style="bold magenta")
    table.add_column("Feature", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Word Count", str(analysis["word_count"]))
    table.add_row("Has Question", "✓" if analysis["has_question"] else "✗")
    table.add_row("Has Exclamation", "✓" if analysis["has_exclamation"] else "✗")
    table.add_row("Sentence Count", str(analysis["sentence_count"]))
    table.add_row("Sentiment Score", f"{analysis['sentiment_score']:.2f}")
    
    # Show detected categories
    categories = analysis["detected_categories"]
    if categories:
        category_info = "\n".join([
            f"• {cat[0]} (priority: {cat[1].get('priority', 'N/A')})"
            for cat in categories
        ])
        table.add_row("Detected Categories", category_info)
    else:
        table.add_row("Detected Categories", "None (using fallback)")
    
    table.add_row("Selected Gesture", f"[bold yellow]{selected_gesture}[/bold yellow]")
    
    console.print(Panel(table, title=f"Response: \"{text[:60]}{'...' if len(text) > 60 else ''}\""))


def show_category_info():
    """Display all gesture categories and their configurations."""
    table = Table(title="Gesture Mapping Categories", show_header=True, header_style="bold blue")
    table.add_column("Category", style="cyan", width=20)
    table.add_column("Description", style="white", width=30)
    table.add_column("Keywords (sample)", style="yellow", width=25)
    table.add_column("Gestures", style="green", width=20)
    table.add_column("Priority", style="magenta", width=8)
    
    for category, config in sorted(GESTURE_MAPPING.items(), key=lambda x: x[1].get("priority", 99)):
        keywords = config.get("keywords", [])
        keywords_sample = ", ".join(keywords[:3]) + ("..." if len(keywords) > 3 else "")
        gestures = ", ".join(config.get("gestures", []))
        priority = str(config.get("priority", "N/A"))
        
        constraints = []
        if config.get("min_words"):
            constraints.append(f"min:{config['min_words']}w")
        if config.get("max_words"):
            constraints.append(f"max:{config['max_words']}w")
        if config.get("requires"):
            constraints.append(f"req:{config['requires']}")
        
        description = config.get("description", "")
        if constraints:
            description += f" [{', '.join(constraints)}]"
        
        table.add_row(category, description, keywords_sample, gestures, priority)
    
    console.print(table)


def interactive_mode():
    """Interactive mode to test responses."""
    console.print(Panel.fit(
        "[bold cyan]Gesture Mapping Test Tool[/bold cyan]\n\n"
        "Enter LLM response texts to see how they map to gestures.\n"
        "Type 'quit' to exit, 'categories' to see all categories, 'examples' for sample tests.",
        title="Interactive Mode"
    ))
    
    while True:
        try:
            text = console.input("\n[bold green]Enter LLM response:[/bold green] ").strip()
            
            if not text:
                continue
            
            if text.lower() == "quit":
                break
            
            if text.lower() == "categories":
                show_category_info()
                continue
            
            if text.lower() == "examples":
                run_examples()
                continue
            
            # Ask for response time
            try:
                time_str = console.input("[dim]Response time (ms, default 1000):[/dim] ").strip()
                response_time_ms = float(time_str) if time_str else 1000.0
            except ValueError:
                response_time_ms = 1000.0
            
            test_response(text, response_time_ms)
            
        except KeyboardInterrupt:
            console.print("\n[bold]Exiting...[/bold]")
            break
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")


def run_examples():
    """Run example tests to demonstrate the mapping."""
    examples = [
        ("That's a great idea!", 500),
        ("Yes, exactly! You're absolutely right.", 600),
        ("What is machine learning?", 800),
        ("Wow, that's really impressive!", 700),
        ("Maybe we could try that approach.", 1200),
        ("Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.", 1500),
        ("Hello! Nice to meet you.", 400),
        ("Sorry about the confusion.", 900),
        ("Unfortunately, that's not possible right now.", 1100),
        ("OK", 300),
    ]
    
    console.print("\n[bold cyan]Running Example Tests:[/bold cyan]\n")
    
    for text, time_ms in examples:
        test_response(text, time_ms)
        console.print()  # Blank line between examples


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test gesture mapping system for LLM responses"
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Test a specific response text"
    )
    parser.add_argument(
        "--time",
        type=float,
        default=1000.0,
        help="Response time in milliseconds (default: 1000)"
    )
    parser.add_argument(
        "--categories",
        action="store_true",
        help="Show all gesture mapping categories"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Run example tests"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )
    
    args = parser.parse_args()
    
    if args.categories:
        show_category_info()
    elif args.examples:
        run_examples()
    elif args.text:
        test_response(args.text, args.time)
    elif args.interactive:
        interactive_mode()
    else:
        # Default: show categories and run examples
        console.print("[bold]Gesture Mapping System[/bold]\n")
        show_category_info()
        console.print("\n")
        run_examples()
        console.print("\n[dim]Tip: Use --interactive for interactive testing mode[/dim]")


if __name__ == "__main__":
    main()

