from __future__ import annotations

import requests
import time
import random
import logging
import threading
import subprocess
import re
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
        self._home_pose: Optional[Dict[str, Any]] = None  # Cache home position
        self._home_pose_captured = False  # Track if we've captured home pose

    def _get(self, path: str) -> requests.Response:
        return requests.get(f"{self.base_url}{path}", timeout=1.0)

    def _post(self, path: str, json: Dict[str, Any] = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        logger.debug(f"POST {url} with payload: {json}")
        response = requests.post(url, json=json, timeout=5.0)
        logger.debug(f"POST {url} response: {response.status_code}")
        return response

    def health(self) -> bool:
        try:
            is_healthy = self._get("/api/state/full").status_code == 200
            if not self._startup_logged:
                if is_healthy:
                    # Check TTS availability
                    self._check_tts_availability()
                    tts_status = f"TTS: {self._tts_method}" if self._tts_method else "TTS: unavailable"
                    logger.info(f"✓ Reachy daemon connected at {self.base_url} - robot gestures fully functional, {tts_status}")
                    
                    # Don't auto-capture home position - user should calibrate manually
                    # This prevents capturing an incorrect position on startup
                    logger.debug("Home position not yet calibrated - will use explicit zeros until calibration")
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
                # Slower rate for clearer speech (default is usually 200, 100-110 is more natural)
                self._tts_engine.setProperty('rate', 200)  # Speed (words per minute) - default speed
                self._tts_engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0) - max volume
                # Try to set a better voice if available
                voices = self._tts_engine.getProperty('voices')
                if voices:
                    selected_voice = None
                    
                    # First: Prefer American female voices
                    for voice in voices:
                        voice_name_lower = voice.name.lower()
                        voice_id_lower = voice.id.lower()
                        # Explicitly avoid Chinese voices
                        if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                            continue
                        # Avoid Belarusian and other non-English languages
                        if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                            continue
                        # Look for American voices (prioritize American over other English accents)
                        if (any(x in voice_name_lower or x in voice_id_lower for x in ['american', 'us', 'usa', 'english_us', 'en_us', 'english-us', 'united states']) and 
                            ('female' in voice_name_lower or 'f' in voice_id_lower)):
                            selected_voice = voice
                            break
                    
                    # Second: American male voices
                    if selected_voice is None:
                        for voice in voices:
                            voice_name_lower = voice.name.lower()
                            voice_id_lower = voice.id.lower()
                            # Explicitly avoid Chinese voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                                continue
                            # Avoid Belarusian and other non-English languages
                            if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                                continue
                            # Look for American voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['american', 'us', 'usa', 'english_us', 'en_us', 'english-us', 'united states']):
                                selected_voice = voice
                                break
                    
                    # Third: Other English voices (prefer over non-English)
                    if selected_voice is None:
                        for voice in voices:
                            voice_name_lower = voice.name.lower()
                            voice_id_lower = voice.id.lower()
                            # Explicitly avoid Chinese voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                                continue
                            # Avoid Belarusian and other non-English languages
                            if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                                continue
                            # Look for English indicators - be more specific
                            # Check for "english" in name or "en" as language code (en-us, en-gb, etc.)
                            if ('english' in voice_name_lower or 
                                voice_id_lower.startswith('en') or 
                                '/en' in voice_id_lower or
                                voice_id_lower.startswith('en-')):
                                selected_voice = voice
                                break
                    
                    # Fourth: Use default English voice if available, otherwise skip
                    # Don't use random non-English voices
                    if selected_voice is None:
                        logger.warning("⚠ TTS: No suitable English voice found, will use system default")
                    
                    if selected_voice:
                        self._tts_engine.setProperty('voice', selected_voice.id)
                        logger.info(f"✓ TTS: Using American English voice: {selected_voice.name} (ID: {selected_voice.id})")
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
        
        Latency-aware gestures (enterprise-responsive):
        - "ack": Quick acknowledgment nod (immediate feedback)
        - "nod_fast": Fast nod for quick responses (<800ms)
        - "nod_tilt": Nod with head tilt for normal responses (800-2500ms)
        - "thinking_done": Thinking gesture for slow responses (>2500ms)
        - "error": Error gesture for failures (shake/no)
        
        Expressive gestures (content-aware):
        - "yes": Positive response (uses agreeing/happy/nod gestures)
        - "no": Clear head shake for negative responses
        - "nod": Simple head nod (pitch down then back up)
        - "excited": Antennas wiggle with head bobs (energetic response)
        - "thinking": Head tilts side to side (processing/thinking)
        - "greeting": Friendly nod with antennas raised
        - "happy": Bouncy antennas with head bob (positive response)
        - "confused": Head shakes side to side (uncertainty)
        - "listening": Leans forward slightly with antennas perked (attentive)
        - "agreeing": Multiple quick nods (emphatic agreement)
        - "surprised": Head jerks back with antennas spread (surprise)
        - "curious": Head tilts with slight body turn (inquisitive)
        - "emphatic": Strong nod with body movement (emphasis)
        - "random": Randomly selects from available gestures
        - "wake_up": Wake up animation
        - "goto_sleep": Sleep animation
        
        Recorded moves (from Reachy Mini daemon):
        - "recorded:dataset:move": Play a recorded move from a dataset
          Example: "recorded:default:jackson_square"
        - Or use move name directly (will try default dataset first)
          Example: "jackson_square" (tries "recorded:default:jackson_square")
        """
        logger.debug(f"🤖 Gesture (implemented): {name}")
        try:
            # Latency-aware gestures (enterprise-responsive)
            if name == "ack":
                self._ack_gesture()
            elif name == "nod_fast":
                self._nod_fast_gesture()
            elif name == "nod_tilt":
                self._nod_tilt_gesture()
            elif name == "thinking_done":
                self._thinking_done_gesture()
            elif name == "error":
                self._error_gesture()
            # Expressive gestures (content-aware)
            elif name == "nod":
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
            elif name == "listening":
                self._listening_gesture()
            elif name == "agreeing":
                self._agreeing_gesture()
            elif name == "surprised":
                self._surprised_gesture()
            elif name == "curious":
                self._curious_gesture()
            elif name == "emphatic":
                self._emphatic_gesture()
            elif name == "no":
                self._no_gesture()
            elif name == "random":
                gestures = ["nod", "excited", "thinking", "greeting", "happy", "listening", "agreeing", "curious", "surprised", "emphatic"]
                self.gesture(random.choice(gestures))
            elif name == "wake_up":
                self._post("/api/move/play/wake_up")
            elif name == "goto_sleep":
                self._post("/api/move/play/goto_sleep")
            elif name.startswith("recorded:"):
                # Support for recorded moves: "recorded:dataset_name:move_name"
                # Example: "recorded:default:jackson_square"
                parts = name.split(":", 2)
                if len(parts) == 3:
                    dataset = parts[1]
                    move = parts[2]
                    self._play_recorded_move(dataset, move)
                else:
                    logger.warning(f"Invalid recorded move format: {name}. Use 'recorded:dataset:move'")
                    self._nod_gesture()
            else:
                # Try as recorded move (fallback: assume default dataset)
                # This allows using move names directly if they exist in the default dataset
                try:
                    self._play_recorded_move("default", name)
                    logger.debug(f"Executed recorded move: {name}")
                except Exception:
                    # If recorded move fails, fall back to nod
                    logger.debug(f"Recorded move '{name}' not found, falling back to nod")
                    self._nod_gesture()
        except Exception:
            # Fail silently - don't break the demo if gesture fails
            pass

    def _nod_gesture(self) -> None:
        """Long, prominent head nod gesture with smooth, pronounced movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Very pronounced nod: down then up with longer pauses
            # Down - more pronounced and slower
            self._post("/api/move/goto", {
                "head_pose": {
                    **current_pose,
                    "pitch": current_pitch - 0.5,  # Much more pronounced
                },
                "body_yaw": current_body_yaw + 0.1,  # Add body movement
                "duration": 0.35,  # Slower, more deliberate
                "interpolation": "minjerk"
            })
            time.sleep(0.15)  # Longer pause at bottom
            
            # Up - energetic return with overshoot
            self._post("/api/move/goto", {
                "head_pose": {
                    **current_pose,
                    "pitch": current_pitch + 0.25,  # More overshoot for energy
                },
                "body_yaw": current_body_yaw - 0.05,
                "duration": 0.35,
                "interpolation": "minjerk"
            })
            time.sleep(0.15)  # Longer pause
            
            # Second smaller nod for emphasis
            self._post("/api/move/goto", {
                "head_pose": {
                    **current_pose,
                    "pitch": current_pitch - 0.25,
                },
                "duration": 0.25,
                "interpolation": "minjerk"
            })
            time.sleep(0.1)
            
            # Return to neutral smoothly and slowly
            self._post("/api/move/goto", {
                "head_pose": current_pose,
                "body_yaw": current_body_yaw,
                "duration": 0.4,
                "interpolation": "minjerk"
            })
        except Exception:
            pass

    def _play_recorded_move(self, dataset: str, move: str) -> None:
        """Play a recorded move from a dataset.
        
        Args:
            dataset: Name of the move dataset (e.g., "default", "dances")
            move: Name of the move within the dataset
        """
        try:
            path = f"/api/move/play/recorded-move-dataset/{dataset}/{move}"
            logger.debug(f"Playing recorded move: {dataset}/{move}")
            response = self._post(path)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to play recorded move {dataset}/{move}: {e}")
            raise

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
            try:
                logger.debug(f"Moving to pose: {payload}")
                response = self._post("/api/move/goto", payload)
                response.raise_for_status()  # Raise exception if HTTP error
                logger.debug(f"Move command successful: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to move robot to pose: {e}")
                logger.error(f"Payload was: {payload}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, body: {e.response.text}")
                raise

    def _excited_gesture(self) -> None:
        """Highly dynamic excited gesture: long, prominent energetic dance with rapid antennas, head bobs, and body movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Very dramatic initial pose: head way up, antennas spread very wide, body turn
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.45, "yaw": current_yaw + 0.25},
                antennas=[0.7, -0.7],  # Very wide spread
                body_yaw=current_body_yaw + 0.2,
                duration=0.25
            )
            time.sleep(0.2)  # Hold dramatic pose longer
            
            # Extended energetic sequence: 5 cycles for more prominence
            for i in range(5):
                # Head down with antennas cross - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch - 0.35, "yaw": current_yaw + (0.15 if i % 2 == 0 else -0.15)},
                    antennas=[-0.5, 0.5],
                    body_yaw=current_body_yaw + (0.15 if i % 2 == 0 else -0.15),
                    duration=0.15
                )
                time.sleep(0.1)  # Longer pause
                
                # Head up with antennas spread - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch + 0.35, "yaw": current_yaw + (-0.1 if i % 2 == 0 else 0.1)},
                    antennas=[0.6, -0.6],
                    duration=0.15
                )
                time.sleep(0.1)  # Longer pause
            
            # Big final flourish: very big head bob with very wide antennas
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.45, "yaw": current_yaw + 0.2},
                antennas=[0.7, 0.7],
                body_yaw=current_body_yaw + 0.18,
                duration=0.2
            )
            time.sleep(0.15)  # Hold longer
            
            # Bounce back up with antennas spread very wide
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.35, "yaw": current_yaw - 0.1},
                antennas=[0.65, -0.65],
                duration=0.2
            )
            time.sleep(0.15)  # Hold longer
            
            # One more bounce for emphasis
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.25},
                antennas=[0.5, 0.5],
                duration=0.18
            )
            time.sleep(0.1)
            
            # Smooth return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.35
            )
        except Exception:
            pass

    def _thinking_gesture(self) -> None:
        """Enhanced thinking gesture: more expressive head tilts with slight body movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Tilt right with slight body turn
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw + 0.3, "roll": 0.12, "pitch": current_pose.get("pitch", 0.0) - 0.05},
                body_yaw=current_body_yaw + 0.08,
                duration=0.25
            )
            time.sleep(0.25)
            
            # Tilt left with opposite body turn
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw - 0.3, "roll": -0.12, "pitch": current_pose.get("pitch", 0.0) - 0.05},
                body_yaw=current_body_yaw - 0.08,
                duration=0.25
            )
            time.sleep(0.25)
            
            # One more tilt right (like deep thinking)
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw + 0.2, "roll": 0.08},
                duration=0.2
            )
            time.sleep(0.15)
            
            # Return to center
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
                duration=0.3
            )
        except Exception:
            pass

    def _greeting_gesture(self) -> None:
        """Enhanced greeting gesture: more welcoming nod with antennas raised and slight body movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Raise antennas with slight body turn (welcoming)
            self._move_to_pose(
                antennas=[0.45, 0.45],
                body_yaw=current_body_yaw + 0.1,
                duration=0.2
            )
            time.sleep(0.1)
            
            # Nod down (respectful greeting)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.28},
                duration=0.22
            )
            time.sleep(0.15)
            
            # Nod up with body return (friendly)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.18},
                body_yaw=current_body_yaw - 0.05,
                duration=0.22
            )
            time.sleep(0.1)
            
            # Hold antennas up briefly
            time.sleep(0.1)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.3
            )
        except Exception:
            pass

    def _happy_gesture(self) -> None:
        """Highly expressive happy gesture: long, prominent joyful bouncy dance with synchronized antennas and body movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Extended joyful sequence: 6 bouncy cycles with increasing energy and more prominent movements
            for i in range(6):
                # Head up with antennas raised very high and body sway - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch + 0.35, "yaw": current_yaw + (0.15 if i % 2 == 0 else -0.15)},
                    antennas=[0.55, 0.55],  # Higher antennas
                    body_yaw=current_body_yaw + (0.12 if i % 2 == 0 else -0.12),
                    duration=0.15
                )
                time.sleep(0.12)  # Longer pause
                
                # Head down with antennas lower and opposite body sway - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch - 0.25},
                    antennas=[0.25, 0.25],
                    body_yaw=current_body_yaw + (-0.08 if i % 2 == 0 else 0.08),
                    duration=0.15
                )
                time.sleep(0.12)  # Longer pause
            
            # Very big final celebration: head way up high with antennas spread very wide
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.45, "yaw": current_yaw + 0.18},
                antennas=[0.7, 0.7],  # Very wide
                body_yaw=current_body_yaw + 0.15,
                duration=0.2
            )
            time.sleep(0.25)  # Hold longer
            
            # Extended bounce sequence (celebration)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.3},
                antennas=[0.4, 0.4],
                duration=0.15
            )
            time.sleep(0.1)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.3},
                antennas=[0.5, 0.5],
                duration=0.15
            )
            time.sleep(0.1)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.2},
                antennas=[0.35, 0.35],
                duration=0.15
            )
            time.sleep(0.1)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.25},
                antennas=[0.45, 0.45],
                duration=0.15
            )
            time.sleep(0.15)
            
            # Smooth return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.4
            )
        except Exception:
            pass

    def _confused_gesture(self) -> None:
        """Enhanced confused gesture: more pronounced head shake with slight tilt."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            
            # More pronounced shake: right-left-right-left with slight roll
            shake_pattern = [
                (0.35, 0.08),   # Right with slight tilt
                (-0.35, -0.08),  # Left with opposite tilt
                (0.25, 0.05),   # Right again
                (-0.25, -0.05),  # Left again
            ]
            
            for yaw_offset, roll_offset in shake_pattern:
                self._move_to_pose(
                    head_pose={
                        **current_pose,
                        "yaw": current_yaw + yaw_offset,
                        "roll": current_pose.get("roll", 0.0) + roll_offset
                    },
                    duration=0.12
                )
                time.sleep(0.08)
            
            # Return to center with slight pause
            time.sleep(0.1)
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.25
            )
        except Exception:
            pass

    def _listening_gesture(self) -> None:
        """Listening gesture: leans forward slightly with antennas perked up (attentive posture)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Lean forward (pitch down slightly) with antennas perked
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.15},
                antennas=[0.25, 0.25],  # Antennas perked up
                duration=0.3
            )
            time.sleep(0.4)  # Hold attentive pose
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                duration=0.3
            )
        except Exception:
            pass

    def _agreeing_gesture(self) -> None:
        """Long, prominent agreeing gesture: emphatic multiple nods with body movement and antennas."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Extended sequence: 6 emphatic nods with increasing energy and more prominent movements
            for i in range(6):
                # Nod down with body lean and antennas - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch - 0.4, "yaw": current_yaw + (0.1 if i % 2 == 0 else -0.1)},
                    antennas=[0.25 + i * 0.06, 0.25 + i * 0.06],  # Progressive increase
                    body_yaw=current_body_yaw + (0.1 if i % 2 == 0 else -0.1),
                    duration=0.18
                )
                time.sleep(0.08)  # Longer pause
                # Nod up with body return - more pronounced
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch + 0.2},
                    body_yaw=current_body_yaw + (-0.05 if i % 2 == 0 else 0.05),
                    duration=0.18
                )
                time.sleep(0.12)  # Longer pause
            
            # Very strong final nod for emphasis
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.45, "yaw": current_yaw + 0.12},
                antennas=[0.6, 0.6],  # Very high
                body_yaw=current_body_yaw + 0.15,
                duration=0.2
            )
            time.sleep(0.15)  # Hold longer
            
            # Second final nod
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.25},
                antennas=[0.5, 0.5],
                duration=0.18
            )
            time.sleep(0.12)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.4
            )
        except Exception:
            pass

    def _surprised_gesture(self) -> None:
        """Very dramatic, long surprised gesture: prominent head jerk back with very wide antennas and body recoil."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Very dramatic head jerk back with antennas spread extremely wide and body recoil
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.55, "yaw": current_yaw + 0.2},
                antennas=[0.8, -0.8],  # Extremely wide spread
                body_yaw=current_body_yaw - 0.2,  # More body recoil
                duration=0.15  # Slightly slower for more prominence
            )
            time.sleep(0.4)  # Hold surprised pose much longer
            
            # Slight forward lean (processing the surprise) - more pronounced
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.35, "yaw": current_yaw - 0.1},
                antennas=[0.5, -0.5],
                body_yaw=current_body_yaw - 0.1,
                duration=0.25
            )
            time.sleep(0.3)  # Longer pause
            
            # Another processing movement
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.2, "yaw": current_yaw + 0.05},
                antennas=[0.4, -0.4],
                body_yaw=current_body_yaw - 0.05,
                duration=0.25
            )
            time.sleep(0.25)
            
            # Return to neutral with smooth, slow recovery
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.45
            )
        except Exception:
            pass

    def _curious_gesture(self) -> None:
        """Expressive curious gesture: dynamic head tilts with body movement and antennas perked (inquisitive posture)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Head tilt right with body turn and antennas perked
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_yaw + 0.25,
                    "roll": current_pose.get("roll", 0.0) + 0.18,
                    "pitch": current_pose.get("pitch", 0.0) - 0.08
                },
                antennas=[0.3, 0.3],  # Antennas perked up
                body_yaw=current_body_yaw + 0.18,
                duration=0.28
            )
            time.sleep(0.35)
            
            # Tilt left with opposite movement
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_yaw - 0.2,
                    "roll": current_pose.get("roll", 0.0) - 0.15,
                    "pitch": current_pose.get("pitch", 0.0) - 0.08
                },
                body_yaw=current_body_yaw - 0.15,
                duration=0.28
            )
            time.sleep(0.3)
            
            # Extended adjustment sequence (like deep thinking)
            current_pitch = current_pose.get("pitch", 0.0)
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_yaw - 0.2,
                    "roll": current_pose.get("roll", 0.0) - 0.12,
                    "pitch": current_pitch - 0.1
                },
                body_yaw=current_body_yaw - 0.12,
                duration=0.3
            )
            time.sleep(0.3)  # Longer pause
            
            # Another tilt for extended curiosity
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_yaw + 0.15,
                    "roll": current_pose.get("roll", 0.0) + 0.1
                },
                body_yaw=current_body_yaw + 0.1,
                duration=0.3
            )
            time.sleep(0.25)
            
            # Return to neutral with antennas - slower
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.45
            )
        except Exception:
            pass

    def _emphatic_gesture(self) -> None:
        """Very long, highly emphatic gesture: powerful extended nod sequence with dramatic body movement and antennas (strong emphasis)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Very powerful nod down with body lean forward and antennas raised high
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.55, "yaw": current_yaw + 0.15},
                antennas=[0.6, 0.6],  # Very high
                body_yaw=current_body_yaw + 0.25,  # More body movement
                duration=0.25
            )
            time.sleep(0.2)  # Hold longer
            
            # Strong return up with body return and antennas spread very wide
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.35, "yaw": current_yaw - 0.1},
                antennas=[0.65, -0.65],  # Very wide
                body_yaw=current_body_yaw - 0.15,
                duration=0.25
            )
            time.sleep(0.2)  # Hold longer
            
            # Second very emphatic nod for extra emphasis
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.5, "yaw": current_yaw + 0.12},
                antennas=[0.55, 0.55],
                body_yaw=current_body_yaw + 0.2,
                duration=0.22
            )
            time.sleep(0.18)
            
            # Third nod for maximum emphasis
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.4},
                antennas=[0.5, 0.5],
                body_yaw=current_body_yaw + 0.15,
                duration=0.2
            )
            time.sleep(0.15)
            
            # Final return up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.3, "yaw": current_yaw - 0.08},
                antennas=[0.4, -0.4],
                body_yaw=current_body_yaw - 0.1,
                duration=0.2
            )
            time.sleep(0.15)
            
            # Smooth, slow return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.45
            )
        except Exception:
            pass

    def _ack_gesture(self) -> None:
        """Acknowledgment gesture: very quick nod for immediate feedback (<100ms)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            
            # Very quick, small nod down
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.15},
                duration=0.08  # Very fast
            )
            time.sleep(0.02)
            
            # Quick return
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.08
            )
        except Exception:
            pass

    def _nod_fast_gesture(self) -> None:
        """Fast nod gesture: quick nod for fast responses (<800ms)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            
            # Quick nod down
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.25},
                duration=0.15
            )
            time.sleep(0.05)
            
            # Quick return up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.1},
                duration=0.15
            )
            time.sleep(0.05)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.1
            )
        except Exception:
            pass

    def _nod_tilt_gesture(self) -> None:
        """Long, prominent nod with tilt gesture: expressive extended nod with dynamic head tilt and body movement for normal responses (800-2500ms)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            current_yaw = current_pose.get("yaw", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Very pronounced nod down with prominent tilt and body movement
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "pitch": current_pitch - 0.45,
                    "yaw": current_yaw + 0.25,
                    "roll": current_pose.get("roll", 0.0) + 0.12
                },
                body_yaw=current_body_yaw + 0.15,
                duration=0.3
            )
            time.sleep(0.2)  # Hold longer
            
            # Return up with opposite tilt and body return - more pronounced
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "pitch": current_pitch + 0.25,
                    "yaw": current_yaw - 0.15,
                    "roll": current_pose.get("roll", 0.0) - 0.08
                },
                body_yaw=current_body_yaw - 0.1,
                duration=0.3
            )
            time.sleep(0.15)  # Longer pause
            
            # Second nod for emphasis - more pronounced
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "pitch": current_pitch - 0.3,
                    "yaw": current_yaw + 0.1
                },
                body_yaw=current_body_yaw + 0.08,
                duration=0.25
            )
            time.sleep(0.12)
            
            # Third small nod
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "pitch": current_pitch + 0.2,
                    "yaw": current_yaw - 0.05
                },
                duration=0.22
            )
            time.sleep(0.1)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
                duration=0.4
            )
        except Exception:
            pass

    def _thinking_done_gesture(self) -> None:
        """Long, prominent thinking done gesture: extended deliberate head movement sequence indicating processing completed (>2500ms)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Extended thoughtful sequence: very slow pan right with more pronounced pitch down
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw + 0.35, "pitch": current_pitch - 0.2, "roll": current_pose.get("roll", 0.0) + 0.1},
                body_yaw=current_body_yaw + 0.2,
                duration=0.6  # Slower, more deliberate
            )
            time.sleep(0.4)  # Hold longer
            
            # Very slow pan left with opposite tilt - more pronounced
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw - 0.35, "pitch": current_pitch - 0.2, "roll": current_pose.get("roll", 0.0) - 0.1},
                body_yaw=current_body_yaw - 0.2,
                duration=0.6  # Slower
            )
            time.sleep(0.4)  # Hold longer
            
            # Another pan right for extended thinking
            self._move_to_pose(
                head_pose={**current_pose, "yaw": current_yaw + 0.25, "pitch": current_pitch - 0.15},
                body_yaw=current_body_yaw + 0.15,
                duration=0.5
            )
            time.sleep(0.3)
            
            # Final prominent nod up (understanding achieved)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.3, "yaw": current_yaw + 0.1},
                body_yaw=current_body_yaw + 0.1,
                duration=0.4
            )
            time.sleep(0.3)  # Hold longer
            
            # Return to center with confidence - slower
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
                duration=0.5
            )
        except Exception:
            pass

    def _no_gesture(self) -> None:
        """Clear head shake gesture for negative/no responses: prominent left-right shake."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Prominent head shake: left-right-left-right (clear "no" gesture)
            shake_pattern = [
                (0.4, -0.05),   # Right with slight body turn
                (-0.4, 0.05),   # Left with opposite body turn
                (0.35, -0.03),  # Right again
                (-0.35, 0.03),  # Left again
            ]
            
            for yaw_offset, body_offset in shake_pattern:
                self._move_to_pose(
                    head_pose={**current_pose, "yaw": current_yaw + yaw_offset},
                    body_yaw=current_body_yaw + body_offset,
                    duration=0.15
                )
                time.sleep(0.1)  # Clear pause between shakes
            
            # Return to center
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
                duration=0.3
            )
        except Exception:
            pass

    def _error_gesture(self) -> None:
        """Error gesture: shake/no or sad posture for failures."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_yaw = current_pose.get("yaw", 0.0)
            
            # Quick shake left-right-left (no gesture)
            for yaw_offset in [0.25, -0.25, 0.15]:
                self._move_to_pose(
                    head_pose={**current_pose, "yaw": current_yaw + yaw_offset},
                    duration=0.12
                )
                time.sleep(0.08)
            
            # Slight head down (sad posture)
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.2},
                duration=0.2
            )
            time.sleep(0.2)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.25
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
            logger.debug("TTS: Empty text, skipping")
            return
        
        # Log the full text being spoken for debugging
        logger.info(f"🔊 TTS: Speaking full text ({len(text)} chars): '{text}'")
        
        # Check TTS availability if not already checked
        if not self._tts_checked:
            self._check_tts_availability()
        
        if self._tts_method == "daemon":
            self._speak_via_daemon(text)
        elif self._tts_method == "system":
            self._speak_via_system(text)
        else:
            logger.warning(f"🔊 TTS unavailable: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
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
                    self._tts_engine.setProperty('rate', 200)  # Default speed
                    self._tts_engine.setProperty('volume', 1.0)
                except Exception:
                    pass
            if self._tts_engine is not None:
                self._speak_via_system(text)
            else:
                logger.error("⚠ TTS failed: daemon error and system TTS not available")
    
    def _speak_via_system(self, text: str) -> None:
        """Speak text via system TTS (pyttsx3) - non-blocking.
        
        Note: Audio plays on laptop speakers, not robot speakers.
        The Reachy Mini daemon does not have TTS endpoints.
        """
        if self._tts_engine is None:
            logger.warning(f"🔊 System TTS unavailable: '{text[:50]}...'")
            return
        
        # Capture text in closure to avoid scoping issues
        text_to_speak = text
        
        def _speak_async():
            """Run TTS in background thread to avoid blocking."""
            try:
                # Clean and normalize text before speaking
                # Ensure text is a string, not a list or iterable
                if not isinstance(text_to_speak, str):
                    input_text = str(text_to_speak)
                else:
                    input_text = text_to_speak
                
                logger.info(f"🔊 Speaking via system TTS ({len(input_text)} chars): '{input_text[:100]}{'...' if len(input_text) > 100 else ''}'")
                
                # Use pyttsx3 with thread lock to prevent crashes from multiple engine instances
                # Create a new engine instance for this thread (pyttsx3 is not thread-safe)
                # Use a simple approach to avoid voice list exhaustion issues
                try:
                    engine = pyttsx3.init()
                except Exception as init_error:
                    logger.error(f"⚠ Failed to initialize TTS engine: {init_error}")
                    # Fallback to espeak directly
                    try:
                        import subprocess
                        cleaned_text = re.sub(r'\s+', ' ', input_text.strip())
                        subprocess.run(['espeak', '-s', '175', '-a', '150', cleaned_text],
                                     timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger.info(f"✓ TTS completed via espeak fallback")
                        return
                    except Exception:
                        logger.error("⚠ All TTS methods failed")
                        return
                
                # Default speech rate (200 WPM is typical default)
                engine.setProperty('rate', 200)  # Default speed
                # Set volume to maximum (1.0 = 100%)
                engine.setProperty('volume', 1.0)  # Max volume
                logger.info(f"TTS properties - rate: {engine.getProperty('rate')}, volume: {engine.getProperty('volume')}")
                
                # Try to set an American English voice explicitly (avoid Chinese, prefer American over other accents)
                voices = engine.getProperty('voices')
                if voices:
                    selected_voice = None
                    
                    # First: Prefer American female voices
                    for voice in voices:
                        voice_name_lower = voice.name.lower()
                        voice_id_lower = voice.id.lower()
                        # Explicitly avoid Chinese voices
                        if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                            continue
                        # Avoid Belarusian and other non-English languages
                        if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                            continue
                        # Look for American voices (prioritize American over other English accents)
                        if (any(x in voice_name_lower or x in voice_id_lower for x in ['american', 'us', 'usa', 'english_us', 'en_us', 'english-us', 'united states']) and 
                            ('female' in voice_name_lower or 'f' in voice_id_lower)):
                            selected_voice = voice
                            break
                    
                    # Second: American male voices
                    if selected_voice is None:
                        for voice in voices:
                            voice_name_lower = voice.name.lower()
                            voice_id_lower = voice.id.lower()
                            # Explicitly avoid Chinese voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                                continue
                            # Avoid Belarusian and other non-English languages
                            if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                                continue
                            # Look for American voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['american', 'us', 'usa', 'english_us', 'en_us', 'english-us', 'united states']):
                                selected_voice = voice
                                break
                    
                    # Third: Other English voices (prefer over non-English)
                    if selected_voice is None:
                        for voice in voices:
                            voice_name_lower = voice.name.lower()
                            voice_id_lower = voice.id.lower()
                            # Explicitly avoid Chinese voices
                            if any(x in voice_name_lower or x in voice_id_lower for x in ['chinese', 'zh', 'cn', 'mandarin', 'cantonese']):
                                continue
                            # Avoid Belarusian and other non-English languages
                            if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                                continue
                            # Look for English indicators - be more specific
                            # Check for "english" in name or "en" as language code (en-us, en-gb, etc.)
                            if ('english' in voice_name_lower or 
                                voice_id_lower.startswith('en') or 
                                '/en' in voice_id_lower or
                                voice_id_lower.startswith('en-')):
                                selected_voice = voice
                                break
                    
                    # Fourth: Use default English voice if available, otherwise skip
                    # Don't use random non-English voices
                    if selected_voice is None:
                        logger.warning("⚠ TTS: No suitable English voice found, will use system default")
                    
                    if selected_voice:
                        # Double-check we didn't accidentally select a non-English voice
                        voice_id_lower = selected_voice.id.lower()
                        voice_name_lower = selected_voice.name.lower()
                        if any(x in voice_id_lower for x in ['/be', '/ru', '/de', '/fr', '/es', '/it', '/pl', '/uk']) or 'belarusian' in voice_name_lower:
                            logger.error(f"⚠ ERROR: Selected non-English voice {selected_voice.name} (ID: {selected_voice.id}) - rejecting!")
                            selected_voice = None
                        
                        if selected_voice:
                            engine.setProperty('voice', selected_voice.id)
                            logger.info(f"✓ TTS: Using American English voice: {selected_voice.name} (ID: {selected_voice.id})")
                        else:
                            logger.warning("⚠ TTS: Selected voice was rejected, using system default")
                
                # Remove any special formatting that might cause TTS to spell letters
                cleaned_text = input_text.strip()
                # Normalize whitespace (replace multiple spaces/tabs/newlines with single space)
                cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
                # Remove any zero-width or invisible characters that might confuse TTS
                cleaned_text = re.sub(r'[\u200b-\u200f\u2028-\u202f]', '', cleaned_text)
                # Ensure text ends with punctuation for natural speech
                if cleaned_text and cleaned_text[-1] not in '.!?,:;':
                    cleaned_text += '.'
                
                # Ensure we have valid text to speak
                if not cleaned_text or len(cleaned_text.strip()) == 0:
                    logger.warning("⚠ TTS: Empty text after cleaning, skipping")
                    return
                
                logger.info(f"TTS engine saying ({len(cleaned_text)} chars): '{cleaned_text[:100]}{'...' if len(cleaned_text) > 100 else ''}'")
                
                # Try multiple TTS methods to work around audio system issues
                speech_text = str(cleaned_text)
                tts_success = False
                
                # Method 1: Try pyttsx3 first
                try:
                    logger.info(f"Speaking via pyttsx3: '{speech_text[:50]}...'")
                    current_voice = engine.getProperty('voice')
                    logger.debug(f"Using voice: {current_voice}")
                    engine.say(speech_text)
                    engine.runAndWait()
                    logger.info(f"✓ TTS playback completed via pyttsx3 for {len(cleaned_text)} character text")
                    tts_success = True
                except Exception as pyttsx_error:
                    logger.warning(f"⚠ pyttsx3 failed: {pyttsx_error}, trying espeak directly...")
                
                # Method 2: Try espeak directly with ALSA workaround
                if not tts_success:
                    try:
                        logger.info(f"Trying espeak directly with ALSA workaround: '{speech_text[:50]}...'")
                        import os
                        env = os.environ.copy()
                        
                        # Workaround for ALSA issues: pipe espeak output through aplay
                        # This bypasses ALSA configuration problems
                        espeak_cmd = ['espeak', '-s', '175', '-a', '150', '--stdout', speech_text]
                        aplay_cmd = ['aplay', '-q']  # -q suppresses ALSA errors
                        
                        # Run espeak and pipe to aplay
                        espeak_proc = subprocess.Popen(
                            espeak_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            env=env
                        )
                        aplay_proc = subprocess.Popen(
                            aplay_cmd,
                            stdin=espeak_proc.stdout,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        espeak_proc.stdout.close()
                        
                        # Wait for both processes
                        espeak_proc.wait(timeout=30)
                        aplay_proc.wait(timeout=30)
                        
                        if espeak_proc.returncode == 0 and aplay_proc.returncode == 0:
                            logger.info(f"✓ TTS playback completed via espeak+aplay for {len(cleaned_text)} character text")
                            tts_success = True
                        else:
                            logger.warning(f"⚠ espeak+aplay failed (espeak: {espeak_proc.returncode}, aplay: {aplay_proc.returncode})")
                    except FileNotFoundError as e:
                        logger.error(f"⚠ espeak or aplay not found: {e}")
                    except subprocess.TimeoutExpired:
                        logger.error("⚠ espeak+aplay timed out")
                        try:
                            espeak_proc.kill()
                            aplay_proc.kill()
                        except:
                            pass
                    except Exception as espeak_error:
                        logger.warning(f"⚠ espeak+aplay failed: {espeak_error}")
                        
                        # Fallback: Try espeak directly (ignore ALSA errors)
                        try:
                            logger.info("Trying espeak directly (ignoring ALSA errors)...")
                            env['AUDIODEV'] = 'default'
                            result = subprocess.run(
                                ['espeak', '-s', '175', '-a', '150', speech_text],
                                env=env,
                                timeout=30,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL  # Suppress ALSA errors
                            )
                            if result.returncode == 0:
                                logger.info(f"✓ TTS playback completed via espeak (errors suppressed) for {len(cleaned_text)} character text")
                                tts_success = True
                        except Exception:
                            pass
                
                # Method 3: Try to fix audio and retry pyttsx3
                if not tts_success:
                    try:
                        logger.info("Attempting to fix audio settings and retry...")
                        # Try to ensure audio is unmuted
                        try:
                            subprocess.run(['amixer', 'set', 'Master', 'unmute'], 
                                         timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            subprocess.run(['amixer', 'set', 'Master', '50%'], 
                                         timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except Exception:
                            pass  # Ignore amixer errors
                        
                        # Retry pyttsx3
                        retry_engine = pyttsx3.init()
                        retry_engine.setProperty('rate', 200)
                        retry_engine.setProperty('volume', 1.0)
                        retry_engine.say(speech_text)
                        retry_engine.runAndWait()
                        logger.info(f"✓ TTS playback completed via pyttsx3 retry for {len(cleaned_text)} character text")
                        tts_success = True
                    except Exception as retry_error:
                        logger.error(f"⚠ Audio fix and retry failed: {retry_error}")
                
                if not tts_success:
                    logger.error(f"⚠ All TTS methods failed - audio may not be working. Text was: '{speech_text[:50]}...'")
            except Exception as e:
                logger.error(f"⚠ System TTS error: {e}", exc_info=True)
        
        # Run TTS in background thread to avoid blocking the main loop
        thread = threading.Thread(target=_speak_async, daemon=True)
        thread.start()

    def calibrate_home(self) -> None:
        """Calibrate home position: capture the robot's current position as the home/neutral position.
        
        Use this when the robot is in the desired neutral position (no tilt, centered).
        After calibration, reset() will return the robot to this position.
        """
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Store the current state as the home position
            self._home_pose = {
                "head_pose": {
                    "pitch": current_pose.get("pitch", 0.0),
                    "yaw": current_pose.get("yaw", 0.0),
                    "roll": current_pose.get("roll", 0.0)
                },
                "antennas": list(current_antennas) if current_antennas else [0.0, 0.0],
                "body_yaw": current_body_yaw
            }
            self._home_pose_captured = True
            
            logger.info(f"✓ Home position calibrated: pitch={self._home_pose['head_pose']['pitch']:.3f}, yaw={self._home_pose['head_pose']['yaw']:.3f}, roll={self._home_pose['head_pose']['roll']:.3f}, antennas={self._home_pose['antennas']}, body={self._home_pose['body_yaw']:.3f}")
        except Exception as e:
            logger.error(f"Failed to calibrate home position: {e}")
            raise

    def reset(self) -> None:
        """Reset robot to the final position of wake_up gesture.
        
        The wake_up gesture ends at the correct neutral position (head, antennas, body).
        This is simpler and more reliable than doing multiple adjustment passes.
        """
        logger.info("🤖 Resetting robot using wake_up gesture (ends at correct neutral position)...")
        
        try:
            # Get state before reset to log the change
            before_state = self.get_state()
            before_pose = before_state.get("head_pose", {})
            before_antennas = before_state.get("antennas_position", [0.0, 0.0])
            before_body_yaw = before_state.get("body_yaw", 0.0)
            logger.info(f"🤖 Before reset: pitch={before_pose.get('pitch', 0.0):.3f}, yaw={before_pose.get('yaw', 0.0):.3f}, roll={before_pose.get('roll', 0.0):.3f}, antennas=[{before_antennas[0] if len(before_antennas) > 0 else 0.0:.3f},{before_antennas[1] if len(before_antennas) > 1 else 0.0:.3f}], body={before_body_yaw:.3f}")
        except Exception as e:
            logger.warning(f"Could not get state before reset: {e}")
            before_pose = {}
            before_antennas = [0.0, 0.0]
            before_body_yaw = 0.0
        
        # Call wake_up gesture - it ends at the correct neutral position
        try:
            self._post("/api/move/play/wake_up")
            logger.info("🤖 Wake_up gesture started, waiting for completion...")
        except Exception as e:
            logger.error(f"🤖 Failed to start wake_up gesture: {e}")
            raise
        
        # Wait for wake_up to complete
        # wake_up includes: initial move to INIT_HEAD_POSE, sound, roll animation (20° left then back), return to INIT_HEAD_POSE
        # Total duration is approximately: initial move (adaptive) + 0.1s + sound + 0.2s roll + 0.2s return = ~1-2 seconds
        # Add extra buffer for safety
        time.sleep(2.5)
        
        # Verify final position
        try:
            after_state = self.get_state()
            after_pose = after_state.get("head_pose", {})
            after_antennas = after_state.get("antennas_position", [0.0, 0.0])
            after_body_yaw = after_state.get("body_yaw", 0.0)
            
            logger.info(f"🤖 After wake_up: pitch={after_pose.get('pitch', 0.0):.3f}, yaw={after_pose.get('yaw', 0.0):.3f}, roll={after_pose.get('roll', 0.0):.3f}, antennas=[{after_antennas[0] if len(after_antennas) > 0 else 0.0:.3f},{after_antennas[1] if len(after_antennas) > 1 else 0.0:.3f}], body={after_body_yaw:.3f}")
            
            # Calculate movement change
            pitch_change = abs(after_pose.get('pitch', 0.0) - before_pose.get('pitch', 0.0))
            yaw_change = abs(after_pose.get('yaw', 0.0) - before_pose.get('yaw', 0.0))
            roll_change = abs(after_pose.get('roll', 0.0) - before_pose.get('roll', 0.0))
            max_change = max(pitch_change, yaw_change, roll_change)
            
            logger.info(f"🤖 Reset complete! Movement: pitch={pitch_change:.3f}, yaw={yaw_change:.3f}, roll={roll_change:.3f}, max={max_change:.3f}")
        except Exception as e:
            logger.warning(f"Could not verify reset state: {e}")
            # Still consider it successful since wake_up completed
