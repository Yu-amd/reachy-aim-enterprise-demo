"""Simple gesture functions for demo automation."""

import time

def nod():
    """Simple nod gesture indicator."""
    print("🤖 [gesture] nod")
    time.sleep(0.3)

def wait_animation():
    """Thinking/waiting animation indicator."""
    print("🤖 [gesture] thinking...", end="", flush=True)
    for _ in range(3):
        time.sleep(0.4)
        print(".", end="", flush=True)
    print("")

def error_signal():
    """Error signal gesture indicator."""
    print("🤖 [gesture] error signal ⚠️")
    time.sleep(0.4)

