from __future__ import annotations

import requests
import time
import random
import logging
from typing import Dict, Any, Optional
from .robot_base import RobotAdapter

logger = logging.getLogger(__name__)

# Try to import pyttsx3 for fallback TTS
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    pyttsx3 = None

class ReachyDaemonREST(RobotAdapter):
    """REST adapter against reachy-mini-daemon.

    Implements robot control via the Reachy Mini daemon REST API.
    Supports gestures, state queries, and health checks.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._startup_logged = False
        self._tts_method: Optional[str] = None  # "daemon" or "system" or None
        self._tts_engine = None
        self._tts_checked = False
        self._tts_daemon_endpoint: Optional[str] = None

    def _get(self, path: str) -> requests.Response:
        return requests.get(f"{self.base_url}{path}", timeout=1.0)

    def _post(self, path: str, json: Dict[str, Any] = None) -> requests.Response:
        return requests.post(f"{self.base_url}{path}", json=json, timeout=5.0)

    def health(self) -> bool:
        try:
            is_healthy = self._get("/api/state/full").status_code == 200
            if not self._startup_logged:
                if is_healthy:
                    # Check TTS availability
                    self._check_tts_availability()
                    tts_status = f"TTS: {self._tts_method}" if self._tts_method else "TTS: unavailable"
                    logger.info(f"✓ Reachy daemon connected at {self.base_url} - robot gestures fully functional, {tts_status}")
                else:
                    logger.warning(f"⚠ Reachy daemon not reachable at {self.base_url} - gestures will be attempted but may fail")
                self._startup_logged = True
            return is_healthy
        except Exception:
            if not self._startup_logged:
                logger.warning(f"⚠ Reachy daemon not reachable at {self.base_url} - gestures will be attempted but may fail")
                self._startup_logged = True
            return False
    
    def _check_tts_availability(self) -> None:
        """Check which TTS method is available: daemon API first, then system TTS."""
        if self._tts_checked:
            return
        
        self._tts_checked = True
        
        # Try daemon API endpoints (common patterns)
        daemon_endpoints = [
            "/api/speak",
            "/api/tts",
            "/api/audio/speak",
            "/api/audio/tts",
        ]
        
        for endpoint in daemon_endpoints:
            try:
                # Try a HEAD or GET request to check if endpoint exists
                # Some APIs might require POST, so we'll try a minimal POST too
                test_response = self._post(endpoint, json={"text": "test"})
                if test_response.status_code in [200, 201, 202, 204]:
                    self._tts_method = "daemon"
                    self._tts_daemon_endpoint = endpoint
                    logger.info(f"✓ TTS: Using Reachy daemon API ({endpoint})")
                    return
            except Exception:
                continue
        
        # Fall back to system TTS (pyttsx3)
        if PYTTSX3_AVAILABLE:
            try:
                self._tts_engine = pyttsx3.init()
                self._tts_engine.setProperty('rate', 150)  # Speed (words per minute)
                self._tts_engine.setProperty('volume', 0.8)  # Volume (0.0 to 1.0)
                self._tts_method = "system"
                logger.info("✓ TTS: Using system TTS (pyttsx3) - daemon API not available")
            except Exception as e:
                logger.warning(f"⚠ TTS: System TTS initialization failed: {e}")
                self._tts_method = None
        else:
            logger.warning("⚠ TTS: pyttsx3 not available. Install with: pip install pyttsx3")
            self._tts_method = None

    def get_state(self) -> Dict[str, Any]:
        r = self._get("/api/state/full")
        r.raise_for_status()
        return r.json()

    def gesture(self, name: str) -> None:
        """Execute a robot gesture.
        
        Fully implemented gestures (work in sim and hardware mode):
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
        logger.debug(f"🤖 Gesture (implemented): {name}")
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
        """Speak text using available TTS method.
        
        Priority:
        1. Reachy daemon API (if available) - uses robot's built-in audio
        2. System TTS (pyttsx3) - fallback for offline TTS
        
        The method is automatically detected at startup.
        """
        if not text or not text.strip():
            return
        
        # Check TTS availability if not already checked
        if not self._tts_checked:
            self._check_tts_availability()
        
        if self._tts_method == "daemon":
            self._speak_via_daemon(text)
        elif self._tts_method == "system":
            self._speak_via_system(text)
        else:
            logger.debug(f"🔊 TTS unavailable: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
    def _speak_via_daemon(self, text: str) -> None:
        """Speak text via Reachy daemon API."""
        try:
            logger.debug(f"🔊 Speaking via daemon: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            response = self._post(
                self._tts_daemon_endpoint,
                json={"text": text}
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"⚠ Daemon TTS error, falling back to system TTS: {e}")
            # Fall back to system TTS if daemon fails
            if PYTTSX3_AVAILABLE and self._tts_engine is None:
                try:
                    self._tts_engine = pyttsx3.init()
                    self._tts_engine.setProperty('rate', 150)
                    self._tts_engine.setProperty('volume', 0.8)
                except Exception:
                    pass
            if self._tts_engine is not None:
                self._speak_via_system(text)
            else:
                logger.error("⚠ TTS failed: daemon error and system TTS not available")
    
    def _speak_via_system(self, text: str) -> None:
        """Speak text via system TTS (pyttsx3)."""
        if self._tts_engine is None:
            logger.debug(f"🔊 System TTS unavailable: '{text[:50]}...'")
            return
        
        try:
            logger.debug(f"🔊 Speaking via system TTS: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        except Exception as e:
            logger.warning(f"⚠ System TTS error: {e}")
