from __future__ import annotations

from prometheus_client import Histogram, Counter, start_http_server

EDGE_E2E_MS = Histogram(
    "edge_e2e_ms",
    "End-to-end latency from user input to response",
    buckets=(50,100,200,400,800,1200,2000,3000,5000,8000),
)
AIM_CALL_MS = Histogram(
    "aim_call_ms",
    "Latency of AIM API call",
    buckets=(50,100,200,400,800,1200,2000,3000,5000,8000),
)
REQUESTS = Counter("edge_requests_total", "Total requests handled by edge client")
ERRORS = Counter("edge_errors_total", "Total errors in edge client")
SLO_MISS = Counter("edge_slo_miss_total", "Count of e2e latency SLO misses")

def start_metrics_server(host: str, port: int) -> None:
    # prometheus_client binds to 0.0.0.0 on that port; we keep host in config for readability.
    start_http_server(port)
