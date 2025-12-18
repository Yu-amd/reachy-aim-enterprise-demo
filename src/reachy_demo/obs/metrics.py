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
BACKEND_FAILURES = Counter("backend_failures_total", "Total backend/inference failures")
GESTURE_SELECTED = Counter(
    "gesture_selected_total",
    "Total gestures selected by latency policy",
    ["gesture"]
)

def _is_port_in_use(port: int, host: str = '0.0.0.0') -> bool:
    """Check if a port is already in use on the specified host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

def start_metrics_server(host: str, port: int) -> None:
    """
    Start the Prometheus metrics HTTP server.
    
    Note: prometheus_client.start_http_server() always binds to 0.0.0.0,
    making it accessible from all interfaces. The host parameter is kept
    for configuration consistency but doesn't affect binding.
    
    In Kubernetes: The server will be accessible within the pod. To access
    from outside, use port-forwarding or expose via a Service.
    """
    # Check if port is already in use (check 0.0.0.0 since that's what start_http_server uses)
    if _is_port_in_use(port, '0.0.0.0'):
        logger.warning(f"Metrics server port {port} is already in use on 0.0.0.0. Assuming metrics server is already running.")
        return
    try:
        # prometheus_client.start_http_server always binds to 0.0.0.0 by default
        start_http_server(port)
        logger.info(f"Started metrics server on 0.0.0.0:{port} (accessible at http://{host}:{port}/metrics)")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.warning(f"Metrics server port {port} is already in use. Assuming metrics server is already running.")
        else:
            logger.error(f"Failed to start metrics server on port {port}: {e}")
            raise
