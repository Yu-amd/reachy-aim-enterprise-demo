"""Automated demo suite for showcasing enterprise features."""

import time
import random
from reachy_demo.aim.client import AIMClient
from reachy_demo.aim.errors import AIMTimeout, AIMHTTPError
from reachy_demo.aim.models import Message
from reachy_demo.gestures.motion import nod, wait_animation, error_signal
from reachy_demo.util.logger import get_logger

logger = get_logger("demo_suite")

AIM_ENDPOINTS = {
    "local": "http://localhost:11434",
    "staging": "http://aim.staging.cluster.svc:8000",
    "prod": "http://aim.prod.cluster.svc:8000"
}

DEMO_SCENARIOS = [
    {
        "name": "Latency-aware gesture",
        "prompt": "Summarize the last deployment to production.",
        "env": "local"
    },
    {
        "name": "Retry with failure tolerance",
        "prompt": "What services failed readiness probe in last hour?",
        "env": "staging"
    },
    {
        "name": "Role-based persona",
        "prompt": "Explain how our load balancer handles failover.",
        "env": "prod",
        "persona": "You are a senior SRE assistant helping a DevOps engineer."
    },
    {
        "name": "Model switch test",
        "prompt": "List the pods currently in CrashLoopBackOff.",
        "env": "prod",
        "model": "gpt-4",
    }
]


def run_scenario(scenario):
    """Run a single demo scenario."""
    print(f"\n--- DEMO: {scenario['name']} ---")

    client = AIMClient(
        base_url=AIM_ENDPOINTS[scenario["env"]],
        timeout_ms=2000,
        max_retries=1
    )

    messages = [{"role": "user", "content": scenario["prompt"]}]
    if "persona" in scenario:
        messages.insert(0, {"role": "system", "content": scenario["persona"]})

    try:
        start = time.time()
        wait_animation()
        resp = client.chat(
            model=scenario.get("model", "gpt-3.5-turbo"),
            messages=messages,
            temperature=0.2,
            max_tokens=180
        )
        duration = time.time() - start
        nod()
        print(f"\n🧠 Response ({duration*1000:.0f}ms):\n{resp.choices[0].message.content.strip()}")
        logger.info({"event": "aim_response", "latency_ms": int(duration * 1000)})

    except (AIMTimeout, AIMHTTPError) as e:
        error_signal()
        print(f"⚠️ AIM Error: {e}")
        logger.error({"event": "aim_failure", "error": str(e)})


def run_demo_suite():
    """Run the complete demo suite."""
    print("🏁 Starting Reachy-AIM Enterprise Demo Suite")
    for scenario in DEMO_SCENARIOS:
        run_scenario(scenario)
        time.sleep(1.5)


if __name__ == "__main__":
    run_demo_suite()

