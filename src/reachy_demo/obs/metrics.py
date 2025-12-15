from __future__ import annotations
import socket
import logging

from prometheus_client import Histogram, Counter, start_http_server

logger = logging.getLogger(__name__)

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

def _is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True

def start_metrics_server(host: str, port: int) -> None:
    # prometheus_client binds to 0.0.0.0 on that port; we keep host in config for readability.
    if _is_port_in_use(port):
        logger.warning(f"Metrics server port {port} is already in use. Assuming metrics server is already running.")
        return
    try:
        start_http_server(port)
        logger.info(f"Started metrics server on port {port}")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.warning(f"Metrics server port {port} is already in use. Assuming metrics server is already running.")
        else:
            raise
