from __future__ import annotations

import requests
import time
import random
from typing import Dict, Any
from .robot_base import RobotAdapter

class ReachyDaemonREST(RobotAdapter):
    """REST adapter against reachy-mini-daemon.

    Implements robot control via the Reachy Mini daemon REST API.
    Supports gestures, state queries, and health checks.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str) -> requests.Response:
        return requests.get(f"{self.base_url}{path}", timeout=1.0)

    def _post(self, path: str, json: Dict[str, Any] = None) -> requests.Response:
        return requests.post(f"{self.base_url}{path}", json=json, timeout=5.0)

    def health(self) -> bool:
        try:
            return self._get("/api/state/full").status_code == 200
        except Exception:
            return False

    def get_state(self) -> Dict[str, Any]:
        r = self._get("/api/state/full")
        r.raise_for_status()
        return r.json()

    def gesture(self, name: str) -> None:
        """Execute a robot gesture.
        
        Supported gestures:
        - "nod": Simple head nod (pitch down then back up)
        - "excited": Antennas wiggle with head bobs (energetic response)
        - "thinking": Head tilts side to side (processing/thinking)
        - "greeting": Friendly nod with antennas raised
        - "happy": Bouncy antennas with head bob (positive response)
        - "confused": Head shakes side to side (uncertainty)
        - "random": Randomly selects from available gestures
        - "wake_up": Wake up animation
        - "goto_sleep": Sleep animation
        """
        try:
            if name == "nod":
                self._nod_gesture()
            elif name == "excited":
                self._excited_gesture()
            elif name == "thinking":
                self._thinking_gesture()
            elif name == "greeting":
                self._greeting_gesture()
            elif name == "happy":
                self._happy_gesture()
            elif name == "confused":
                self._confused_gesture()
            elif name == "random":
                gestures = ["nod", "excited", "thinking", "greeting", "happy"]
                self.gesture(random.choice(gestures))
            elif name == "wake_up":
                self._post("/api/move/play/wake_up")
            elif name == "goto_sleep":
                self._post("/api/move/play/goto_sleep")
            else:
                # Unknown gesture, fall back to nod
                self._nod_gesture()
        except Exception:
            # Fail silently - don't break the demo if gesture fails
            pass

    def _nod_gesture(self) -> None:
        """Perform a head nod gesture by moving head pitch down and back up."""
        try:
            # Get current head pose
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            
            # Extract current pitch (or default to 0)
            current_pitch = current_pose.get("pitch", 0.0)
            
            # Nod down: pitch -0.3 radians (~17 degrees down)
            nod_down_pitch = current_pitch - 0.3
            
            # Nod up: pitch +0.2 radians (~11 degrees up from original)
            nod_up_pitch = current_pitch + 0.2
            
            # Perform nod: down then up
            # Down
            self._post("/api/move/goto", {
                "head_pose": {
                    "x": current_pose.get("x", 0.0),
                    "y": current_pose.get("y", 0.0),
                    "z": current_pose.get("z", 0.0),
                    "roll": current_pose.get("roll", 0.0),
                    "pitch": nod_down_pitch,
                    "yaw": current_pose.get("yaw", 0.0),
                },
                "duration": 0.3,  # 300ms to nod down
                "interpolation": "minjerk"
            })
            
            # Small delay
            time.sleep(0.1)
            
            # Back up
            self._post("/api/move/goto", {
                "head_pose": {
                    "x": current_pose.get("x", 0.0),
                    "y": current_pose.get("y", 0.0),
                    "z": current_pose.get("z", 0.0),
                    "roll": current_pose.get("roll", 0.0),
                    "pitch": nod_up_pitch,
                    "yaw": current_pose.get("yaw", 0.0),
                },
                "duration": 0.3,  # 300ms to nod up
                "interpolation": "minjerk"
            })
            
            # Return to original position
            time.sleep(0.1)
            self._post("/api/move/goto", {
                "head_pose": current_pose,
                "duration": 0.2,  # 200ms to return
                "interpolation": "minjerk"
            })
        except Exception:
            # Fail silently if gesture fails
            pass

    def _move_to_pose(self, head_pose: Dict[str, float] = None, antennas: list = None, 
                      body_yaw: float = None, duration: float = 0.3) -> None:
        """Helper method to move robot to a specific pose."""
        payload = {}
        if head_pose is not None:
            payload["head_pose"] = head_pose
        if antennas is not None:
            payload["antennas"] = antennas
        if body_yaw is not None:
            payload["body_yaw"] = body_yaw
        if payload:
            payload["duration"] = duration
            payload["interpolation"] = "minjerk"
            self._post("/api/move/goto", payload)

    def _excited_gesture(self) -> None:
        """Excited gesture: antennas wiggle rapidly with head bobs."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Quick head bob up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.2},
                duration=0.15
            )
            time.sleep(0.1)
            
            # Antennas wiggle (3 quick movements)
            for i in range(3):
                # Antennas spread
                self._move_to_pose(
                    antennas=[0.3, -0.3],
                    duration=0.1
                )
                time.sleep(0.05)
                # Antennas together
                self._move_to_pose(
                    antennas=[-0.2, 0.2],
                    duration=0.1
                )
                time.sleep(0.05)
            
            # Head bob down then return
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.15},
                duration=0.2
            )
            time.sleep(0.1)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                duration=0.2
            )
        except Exception:
            pass

    def _thinking_gesture(self) -> None:
        """Thinking gesture: head tilts side to side (like thinking)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Tilt right
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw + 0.25, "roll": 0.1},
                duration=0.3
            )
            time.sleep(0.2)
            
            # Tilt left
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw - 0.25, "roll": -0.1},
                duration=0.3
            )
            time.sleep(0.2)
            
            # Return to center
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.3
            )
        except Exception:
            pass

    def _greeting_gesture(self) -> None:
        """Greeting gesture: friendly nod with antennas raised."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Raise antennas
            self._move_to_pose(
                antennas=[0.4, 0.4],
                duration=0.2
            )
            time.sleep(0.1)
            
            # Nod down
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.25},
                duration=0.25
            )
            time.sleep(0.15)
            
            # Nod up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.15},
                duration=0.25
            )
            time.sleep(0.1)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                duration=0.3
            )
        except Exception:
            pass

    def _happy_gesture(self) -> None:
        """Happy gesture: bouncy antennas with head bob."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Head up, antennas bounce
            for i in range(2):
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.15},
                    antennas=[0.3, 0.3],
                    duration=0.15
                )
                time.sleep(0.1)
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.1},
                    antennas=[0.1, 0.1],
                    duration=0.15
                )
                time.sleep(0.1)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                duration=0.2
            )
        except Exception:
            pass

    def _confused_gesture(self) -> None:
        """Confused gesture: head shakes side to side."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Shake right-left-right
            for yaw_offset in [0.3, -0.3, 0.2, -0.2]:
                self._move_to_pose(
                    head_pose={**current_pose, "yaw": current_yaw + yaw_offset},
                    duration=0.15
                )
                time.sleep(0.1)
            
            # Return to center
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.2
            )
        except Exception:
            pass

    def speak(self, text: str) -> None:
        """Speak text (placeholder - TTS not implemented).
        
        For now, this is a no-op. In the future, this could:
        - Use robot's built-in TTS if available
        - Use system TTS (e.g., espeak, festival)
        - Send audio to robot speakers
        """
        # TODO: Implement TTS integration
        # For now, just a placeholder
        pass
