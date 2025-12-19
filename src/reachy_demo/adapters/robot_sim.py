from __future__ import annotations
from .robot_rest import ReachyDaemonREST

class SimRobot(ReachyDaemonREST):
    """Alias for clarity: sim mode still uses the daemon REST API."""
    pass  # Inherits calibrate_home() from ReachyDaemonREST
