from __future__ import annotations

import requests
import time
import random
import logging
import threading
import subprocess
import re
import math
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

# Try to import piper-tts for natural voice (best quality)
# Optional dependency: pip install piper-tts pyaudio
try:
    from piper import PiperVoice  # type: ignore
    from piper.download import ensure_voice_exists, find_voice  # type: ignore
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    PiperVoice = None

class ReachyDaemonREST(RobotAdapter):
    """REST adapter against reachy-mini-daemon.

    Implements robot control via the Reachy Mini daemon REST API.
    Supports gestures, state queries, and health checks.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._startup_logged = False
        self._tts_method: Optional[str] = None  # "daemon", "piper", "system", or None
        self._tts_engine = None
        self._tts_checked = False
        self._tts_daemon_endpoint: Optional[str] = None
        self._piper_voice = None  # Piper voice model
        self._talk_motion_active = False  # Track if talk motion is running
        self._tts_lock = threading.Lock()  # Prevent concurrent TTS calls
        self._current_tts_processes = []  # Track running TTS processes to kill on overlap
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
        """Check which TTS method is available: daemon API first, then Piper, then espeak fallback."""
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
        
        # Try Piper TTS (best quality, natural voice)
        if PIPER_AVAILABLE:
            try:
                # Try to load a default voice (en_US-lessac-medium)
                voice_name = "en_US-lessac-medium"
                try:
                    ensure_voice_exists(voice_name, ["./voices", "~/.local/share/piper/voices"])
                    voice_path = find_voice(voice_name, ["./voices", "~/.local/share/piper/voices"])
                    if voice_path:
                        self._piper_voice = PiperVoice.load(voice_path)
                        self._tts_method = "piper"
                        logger.info(f"✓ TTS: Using Piper (natural voice: {voice_name})")
                        return
                except Exception as e:
                    logger.debug(f"Piper voice {voice_name} not found: {e}, trying espeak fallback")
            except Exception as e:
                logger.debug(f"Piper initialization failed: {e}, trying espeak fallback")
        
        # Fall back to espeak (just works)
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
                logger.info("✓ TTS: Using system TTS (pyttsx3/espeak) - daemon API and Piper not available")
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
                try:
                    logger.debug("🤖 Executing wake_up gesture...")
                    response = self._post("/api/move/play/wake_up")
                    response.raise_for_status()  # Raise exception if HTTP error
                    logger.debug("🤖 Wake up gesture API call successful")
                    # Give wake animation time to complete (wake_up animation is typically 2-3 seconds)
                    # The daemon returns immediately with a UUID, but the animation takes time
                    time.sleep(3.0)  # Wait for full wake animation to complete
                    logger.debug("🤖 Wake animation should be complete")
                except requests.exceptions.RequestException as e:
                    logger.error(f"🤖 Failed to execute wake_up gesture: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.error(f"Response status: {e.response.status_code}, body: {e.response.text[:200]}")
                    raise
            elif name == "goto_sleep":
                try:
                    response = self._post("/api/move/play/goto_sleep")
                    response.raise_for_status()  # Raise exception if HTTP error
                    logger.debug("🤖 Sleep gesture executed successfully")
                    # Give sleep animation time to complete
                    time.sleep(1.0)
                except requests.exceptions.RequestException as e:
                    logger.error(f"🤖 Failed to execute goto_sleep gesture: {e}")
                    raise
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
            # Ensure roll is always explicitly set (default to 0.0 if not specified)
            if "roll" not in head_pose:
                head_pose = {**head_pose, "roll": 0.0}
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
    
    def _return_to_clean_pose(self, current_pose: Dict[str, float], current_antennas: list = None, 
                              current_body_yaw: float = None, duration: float = 0.3) -> None:
        """Helper to return to a clean pose with roll=0.0 (prevents head tilt)."""
        clean_head_pose = {
            "pitch": current_pose.get("pitch", 0.0),
            "yaw": current_pose.get("yaw", 0.0),
            "roll": 0.0  # Always zero roll - no tilt
        }
        self._move_to_pose(
            head_pose=clean_head_pose,
            antennas=current_antennas,
            body_yaw=current_body_yaw,
            duration=duration
        )

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
            
            # Smooth return to original - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.35)
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
            
            # Return to center - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_body_yaw=current_body_yaw, duration=0.3)
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
            
            # Return to original - explicitly set roll to 0.0 to prevent tilt
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.3)
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
            
            # Smooth return to original - explicitly set roll to 0.0 to prevent tilt
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.4)
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
            
            # Return to center with slight pause - explicitly set roll to 0.0
            time.sleep(0.1)
            self._return_to_clean_pose(current_pose, duration=0.25)
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
            
            # Return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, duration=0.3)
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
            
            # Return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.4)
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
            
            # Return to neutral with smooth, slow recovery - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.45)
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
            
            # Return to neutral with antennas - slower, explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.45)
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
            
            # Smooth, slow return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_antennas, current_body_yaw, duration=0.45)
        except Exception:
            pass

    def _ack_gesture(self) -> None:
        """Acknowledgment gesture: very quick antenna wiggle for immediate feedback (<100ms)."""
        try:
            state = self.get_state()
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Very quick, small antenna wiggle
            self._move_to_pose(
                antennas=[
                    current_antennas[0] + 0.1 if len(current_antennas) > 0 else 0.1,
                    current_antennas[1] - 0.1 if len(current_antennas) > 1 else -0.1
                ],
                duration=0.08  # Very fast
            )
            time.sleep(0.02)
            
            # Quick return
            self._move_to_pose(
                antennas=current_antennas,
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
            
            # Return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, duration=0.1)
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
            
            # Return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_body_yaw=current_body_yaw, duration=0.4)
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
            
            # Return to center with confidence - slower, explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_body_yaw=current_body_yaw, duration=0.5)
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
            
            # Return to center - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, current_body_yaw=current_body_yaw, duration=0.3)
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
            
            # Return to neutral - explicitly set roll to 0.0
            self._return_to_clean_pose(current_pose, duration=0.25)
        except Exception:
            pass

    def speak(self, text: str) -> float:
        """Speak text using available TTS method and return audio duration in seconds.
        
        Priority:
        1. Reachy daemon API (if available) - uses robot's built-in audio
        2. Piper TTS (best quality, natural voice) - default for host speaker
        3. Espeak (just works) - fallback
        
        Also runs speech-synced robot motion (micro-movements, antenna wiggles) during speech.
        This makes it look like the robot is talking even when audio comes from host.
        
        Returns:
            float: Estimated audio duration in seconds
        """
        if not text or not text.strip():
            logger.debug("TTS: Empty text, skipping")
            return 0.0
        
        # Clean markdown formatting for natural speech
        # Remove asterisks (*) used for bold/italic, underscores (_), and other markdown
        text = re.sub(r'\*+', '', text)  # Remove asterisks
        text = re.sub(r'_+', '', text)   # Remove underscores
        text = re.sub(r'`+', '', text)   # Remove backticks
        text = re.sub(r'#+\s*', '', text)  # Remove markdown headers
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Convert [link](url) to just "link"
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = text.strip()
        
        if not text:
            logger.debug("TTS: Text became empty after cleaning, skipping")
            return 0.0
        
        # Use lock to prevent concurrent TTS calls (which cause overlapping audio)
        with self._tts_lock:
            # Kill any existing TTS processes to prevent overlap
            self._kill_tts_processes()
            
            # Log the full text being spoken for debugging (only in debug mode)
            logger.debug(f"🔊 TTS: Speaking full text ({len(text)} chars): '{text}'")
            
            # Check TTS availability if not already checked
            if not self._tts_checked:
                self._check_tts_availability()
            
            # Estimate duration based on text length (rough: ~150 words per minute = 2.5 words/sec)
            # Average word length ~5 chars, so ~12.5 chars/sec, or ~0.08 sec/char
            estimated_duration = max(0.5, len(text) * 0.08)
            
            # Start speech-synced motion loop in parallel
            motion_thread = None
            if self.health():
                motion_thread = threading.Thread(
                    target=self._talk_motion_loop,
                    args=(estimated_duration,),
                    daemon=True
                )
                motion_thread.start()
            
            # Speak using available method
            actual_duration = estimated_duration
            if self._tts_method == "daemon":
                actual_duration = self._speak_via_daemon(text)
            elif self._tts_method == "piper":
                actual_duration = self._speak_via_piper(text)
            elif self._tts_method == "system":
                actual_duration = self._speak_via_system(text)
            else:
                logger.warning(f"🔊 TTS unavailable: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Stop motion loop before returning
            self._talk_motion_active = False
            
            # Wait for motion thread to finish
            if motion_thread and motion_thread.is_alive():
                # Wait a bit for the motion loop to see the flag and stop
                time.sleep(0.2)
                # If still running, wait a bit more (motion loop checks flag every 0.1s)
                if motion_thread.is_alive():
                    time.sleep(0.3)
            
            return actual_duration
    
    def _kill_tts_processes(self) -> None:
        """Kill any running TTS processes to prevent audio overlap."""
        try:
            for proc in self._current_tts_processes:
                try:
                    if proc.poll() is None:  # Process is still running
                        proc.kill()
                        proc.wait(timeout=1.0)
                except Exception:
                    pass
            self._current_tts_processes.clear()
        except Exception:
            pass
    
    def _talk_motion_loop(self, duration: float) -> None:
        """Run speech-synced robot motion during speech.
        
        Creates small head micro-movements and antenna wiggles to make it look
        like the robot is talking, even when audio comes from host speakers.
        """
        self._talk_motion_active = True
        start_time = time.time()
        
        try:
            # Get initial state
            state = self.get_state()
            initial_pose = state.get("head_pose", {})
            initial_antennas = state.get("antennas_position", [0.0, 0.0])
            initial_pitch = initial_pose.get("pitch", 0.0)
            initial_yaw = initial_pose.get("yaw", 0.0)
            initial_roll = initial_pose.get("roll", 0.0)
            
            # Motion parameters
            micro_movement_range = 0.08  # Small head movements
            antenna_wiggle_range = 0.15  # Antenna wiggle range
            motion_interval = 0.4  # Move every 400ms
            pause_between_phrases = 0.3  # Pause between phrases
            
            motion_count = 0
            last_motion_time = start_time
            
            while self._talk_motion_active and (time.time() - start_time) < duration:
                current_time = time.time()
                elapsed = current_time - start_time
                remaining = duration - elapsed
                
                # Check if we should pause (between phrases)
                if motion_count > 0 and (current_time - last_motion_time) < pause_between_phrases:
                    time.sleep(0.1)
                    continue
                
                # Antenna wiggles only (no head movements)
                if (current_time - last_motion_time) >= motion_interval:
                    try:
                        # Antenna wiggles (if safe - check current position)
                        antenna_left = initial_antennas[0] if len(initial_antennas) > 0 else 0.0
                        antenna_right = initial_antennas[1] if len(initial_antennas) > 1 else 0.0
                        
                        # Safe antenna wiggle (don't go too far)
                        if abs(antenna_left) < 0.3 and abs(antenna_right) < 0.3:
                            antenna_left_variation = random.uniform(-antenna_wiggle_range, antenna_wiggle_range)
                            antenna_right_variation = random.uniform(-antenna_wiggle_range, antenna_wiggle_range)
                            new_antennas = [
                                max(-0.4, min(0.4, antenna_left + antenna_left_variation)),
                                max(-0.4, min(0.4, antenna_right + antenna_right_variation))
                            ]
                        else:
                            # Keep antennas close to current position if already far
                            new_antennas = initial_antennas
                        
                        # Apply antenna movement only (no head movement)
                        self._move_to_pose(
                            antennas=new_antennas,
                            duration=0.15  # Quick, subtle movements
                        )
                        
                        motion_count += 1
                        last_motion_time = current_time
                    except Exception as e:
                        logger.debug(f"Talk motion error (non-critical): {e}")
                
                time.sleep(0.1)  # Small sleep to avoid busy-waiting
            
            # Return to initial position
            try:
                self._move_to_pose(
                    head_pose=initial_pose,
                    antennas=initial_antennas,
                    duration=0.2
                )
            except Exception:
                pass
                
        except Exception as e:
            logger.debug(f"Talk motion loop error (non-critical): {e}")
        finally:
            self._talk_motion_active = False
    
    def _speak_via_daemon(self, text: str) -> float:
        """Speak text via Reachy daemon API. Returns audio duration in seconds."""
        try:
            logger.debug(f"🔊 Speaking via daemon: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            response = self._post(
                self._tts_daemon_endpoint,
                json={"text": text}
            )
            response.raise_for_status()
            # Estimate duration (daemon doesn't return it)
            return max(0.5, len(text) * 0.08)
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
                return self._speak_via_system(text)
            else:
                logger.error("⚠ TTS failed: daemon error and system TTS not available")
                return max(0.5, len(text) * 0.08)
    
    def _speak_via_piper(self, text: str) -> float:
        """Speak text via Piper TTS (best quality, natural voice). Returns audio duration in seconds."""
        if not PIPER_AVAILABLE or self._piper_voice is None:
            logger.warning("⚠ Piper TTS not available, falling back to espeak")
            return self._speak_via_espeak(text)
        
        try:
            import io
            import wave
            try:
                import pyaudio  # type: ignore
            except ImportError:
                pyaudio = None
            
            logger.debug(f"🔊 Speaking via Piper TTS: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Generate audio with Piper
            audio_stream = io.BytesIO()
            self._piper_voice.synthesize(text, audio_stream)
            audio_stream.seek(0)
            
            # Play audio using pyaudio
            try:
                if pyaudio is None:
                    raise ImportError("pyaudio not available")
                p = pyaudio.PyAudio()
                wf = wave.open(audio_stream, 'rb')
                
                # Open audio stream
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
                
                # Play audio
                start_time = time.time()
                data = wf.readframes(1024)
                while data:
                    stream.write(data)
                    data = wf.readframes(1024)
                
                # Cleanup
                stream.stop_stream()
                stream.close()
                p.terminate()
                wf.close()
                
                duration = time.time() - start_time
                logger.debug(f"✓ Piper TTS completed in {duration:.2f}s")
                return duration
            except ImportError:
                # pyaudio not available, try aplay fallback
                logger.debug("pyaudio not available, trying aplay fallback")
                audio_stream.seek(0)
                aplay_proc = subprocess.Popen(
                    ['aplay', '-q'],
                    stdin=audio_stream,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                # Track process
                self._current_tts_processes = [aplay_proc]
                aplay_proc.wait(timeout=30)
                self._current_tts_processes.clear()
                if aplay_proc.returncode == 0:
                    return max(0.5, len(text) * 0.08)
                else:
                    raise
        except Exception as e:
            logger.warning(f"⚠ Piper TTS error: {e}, falling back to espeak")
            self._kill_tts_processes()
            return self._speak_via_espeak(text)
    
    def _speak_via_espeak(self, text: str) -> float:
        """Speak text via espeak (just works fallback). Returns audio duration in seconds."""
        try:
            logger.debug(f"🔊 Speaking via espeak: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Clean text
            cleaned_text = re.sub(r'\s+', ' ', text.strip())
            
            start_time = time.time()
            
            # Try espeak with aplay (best quality)
            espeak_proc = None
            aplay_proc = None
            try:
                espeak_cmd = ['espeak', '-s', '175', '-a', '150', '--stdout', cleaned_text]
                aplay_cmd = ['aplay', '-q']
                
                espeak_proc = subprocess.Popen(
                    espeak_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                aplay_proc = subprocess.Popen(
                    aplay_cmd,
                    stdin=espeak_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                espeak_proc.stdout.close()
                
                # Track processes so we can kill them if needed
                self._current_tts_processes = [espeak_proc, aplay_proc]
                
                espeak_proc.wait(timeout=30)
                aplay_proc.wait(timeout=30)
                
                duration = time.time() - start_time
                if espeak_proc.returncode == 0 and aplay_proc.returncode == 0:
                    logger.debug(f"✓ Espeak TTS completed in {duration:.2f}s")
                    self._current_tts_processes.clear()
                    return duration
                else:
                    # Kill processes if they failed
                    self._kill_tts_processes()
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                # Kill any running processes before fallback
                if espeak_proc:
                    try:
                        espeak_proc.kill()
                    except:
                        pass
                if aplay_proc:
                    try:
                        aplay_proc.kill()
                    except:
                        pass
                self._current_tts_processes.clear()
                logger.debug(f"espeak+aplay failed: {e}, trying direct espeak")
            except Exception as e:
                self._kill_tts_processes()
                logger.debug(f"espeak+aplay error: {e}, trying direct espeak")
            
            # Fallback: espeak directly (only if first attempt failed)
            # Make sure no processes are running before starting fallback
            self._kill_tts_processes()
            time.sleep(0.1)  # Brief pause to ensure audio device is free
            
            try:
                result = subprocess.run(
                    ['espeak', '-s', '175', '-a', '150', cleaned_text],
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                duration = time.time() - start_time
                if result.returncode == 0:
                    logger.debug(f"✓ Espeak TTS completed in {duration:.2f}s")
                    return duration
                else:
                    return max(0.5, len(text) * 0.08)
            except Exception as e:
                logger.error(f"⚠ Espeak fallback error: {e}")
                return max(0.5, len(text) * 0.08)
        except Exception as e:
            logger.error(f"⚠ Espeak TTS error: {e}")
            self._kill_tts_processes()
            return max(0.5, len(text) * 0.08)
    
    def _speak_via_system(self, text: str) -> float:
        """Speak text via system TTS (espeak) - non-blocking.
        
        Note: Audio plays on laptop speakers, not robot speakers.
        The Reachy Mini daemon does not have TTS endpoints.
        
        Returns audio duration in seconds.
        """
        # Use espeak directly (more reliable than pyttsx3)
        return self._speak_via_espeak(text)
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
                
                logger.debug(f"🔊 Speaking via system TTS ({len(input_text)} chars): '{input_text[:100]}{'...' if len(input_text) > 100 else ''}'")
                
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
                        logger.debug(f"✓ TTS completed via espeak fallback")
                        return
                    except Exception:
                        logger.error("⚠ All TTS methods failed")
                        return
                
                # Default speech rate (200 WPM is typical default)
                engine.setProperty('rate', 200)  # Default speed
                # Set volume to maximum (1.0 = 100%)
                engine.setProperty('volume', 1.0)  # Max volume
                logger.debug(f"TTS properties - rate: {engine.getProperty('rate')}, volume: {engine.getProperty('volume')}")
                
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
                
                logger.debug(f"TTS engine saying ({len(cleaned_text)} chars): '{cleaned_text[:100]}{'...' if len(cleaned_text) > 100 else ''}'")
                
                # Try multiple TTS methods to work around audio system issues
                speech_text = str(cleaned_text)
                tts_success = False
                
                # Method 1: Try pyttsx3 first
                try:
                    logger.debug(f"Speaking via pyttsx3: '{speech_text[:50]}...'")
                    current_voice = engine.getProperty('voice')
                    logger.debug(f"Using voice: {current_voice}")
                    engine.say(speech_text)
                    engine.runAndWait()
                    logger.debug(f"✓ TTS playback completed via pyttsx3 for {len(cleaned_text)} character text")
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
                            logger.debug(f"✓ TTS playback completed via espeak+aplay for {len(cleaned_text)} character text")
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
                                logger.debug(f"✓ TTS playback completed via espeak (errors suppressed) for {len(cleaned_text)} character text")
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
                        logger.debug(f"✓ TTS playback completed via pyttsx3 retry for {len(cleaned_text)} character text")
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
        """Reset robot to neutral/home position.
        
        Moves directly to neutral position (0.0 for all axes) without any animations or tilts.
        Uses calibrated home position if available, otherwise uses explicit zeros.
        """
        # Stop any ongoing motion loops first
        self._talk_motion_active = False
        time.sleep(0.1)  # Give motion loop time to see the flag
        
        logger.info("🤖 Resetting robot to neutral position (no tilt)...")
        
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
        
        # Move directly to neutral position (no animations, no tilt)
        # ALWAYS explicitly set roll to 0.0 to prevent head tilt
        try:
            if self._home_pose_captured and self._home_pose is not None:
                # Use calibrated home position, but ensure roll is 0.0
                home_head_pose = self._home_pose.get("head_pose", {})
                target_head_pose = {
                    "pitch": home_head_pose.get("pitch", 0.0),
                    "yaw": home_head_pose.get("yaw", 0.0),
                    "roll": 0.0  # Always zero roll - no tilt
                }
                target_antennas = self._home_pose.get("antennas", [0.0, 0.0])
                target_body_yaw = self._home_pose.get("body_yaw", 0.0)
                logger.info("🤖 Using calibrated home position for reset (roll=0.0)")
            else:
                # Use explicit zeros for true neutral - ALWAYS zero roll
                target_head_pose = {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
                target_antennas = [0.0, 0.0]
                target_body_yaw = 0.0
                logger.info("🤖 Using explicit zero position for reset (roll=0.0)")
            
            # Move to neutral position smoothly
            # Use a slightly longer duration to ensure smooth, complete movement
            self._move_to_pose(
                head_pose=target_head_pose,
                antennas=target_antennas,
                body_yaw=target_body_yaw,
                duration=0.8  # Smooth movement with enough time to complete
            )
            # Wait for movement to complete, plus a small buffer
            time.sleep(1.0)  # Ensure movement fully completes
            
            # Double-check: move again to ensure roll is definitely 0.0
            # This handles any cases where the first move didn't fully complete
            self._move_to_pose(
                head_pose={"pitch": target_head_pose["pitch"], "yaw": target_head_pose["yaw"], "roll": 0.0},
                duration=0.3
            )
            time.sleep(0.4)
            
        except Exception as e:
            logger.error(f"🤖 Failed to reset robot: {e}")
            raise
        
        # Verify final position
        try:
            after_state = self.get_state()
            after_pose = after_state.get("head_pose", {})
            after_antennas = after_state.get("antennas_position", [0.0, 0.0])
            after_body_yaw = after_state.get("body_yaw", 0.0)
            
            logger.info(f"🤖 After reset: pitch={after_pose.get('pitch', 0.0):.3f}, yaw={after_pose.get('yaw', 0.0):.3f}, roll={after_pose.get('roll', 0.0):.3f}, antennas=[{after_antennas[0] if len(after_antennas) > 0 else 0.0:.3f},{after_antennas[1] if len(after_antennas) > 1 else 0.0:.3f}], body={after_body_yaw:.3f}")
            
            # Calculate movement change
            pitch_change = abs(after_pose.get('pitch', 0.0) - before_pose.get('pitch', 0.0))
            yaw_change = abs(after_pose.get('yaw', 0.0) - before_pose.get('yaw', 0.0))
            roll_change = abs(after_pose.get('roll', 0.0) - before_pose.get('roll', 0.0))
            max_change = max(pitch_change, yaw_change, roll_change)
            
            logger.info(f"🤖 Reset complete! Movement: pitch={pitch_change:.3f}, yaw={yaw_change:.3f}, roll={roll_change:.3f}, max={max_change:.3f}")
        except Exception as e:
            logger.warning(f"Could not verify reset state: {e}")
            # Still consider it successful since move completed
    
    def thinking_pose(self) -> None:
        """Turn body and head 90 degrees to the side to indicate thinking (very prominent)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            current_head_yaw = current_pose.get("yaw", 0.0)
            
            # Turn both body and head 90 degrees (π/2 radians) to the side
            # This is a very prominent, clear thinking pose
            # Explicitly set roll to 0 to prevent any side tilt
            ninety_degrees = math.pi / 2  # ~1.57 radians
            thinking_body_yaw = current_body_yaw + ninety_degrees
            thinking_head_yaw = current_head_yaw + ninety_degrees
            
            logger.debug(f"🤖 Turning body and head 90° to thinking pose: body={thinking_body_yaw:.3f}, head_yaw={thinking_head_yaw:.3f}")
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": thinking_head_yaw,
                    "roll": 0.0,  # Explicitly no side tilt
                    "pitch": current_pose.get("pitch", 0.0)  # Keep current pitch
                },
                body_yaw=thinking_body_yaw,
                duration=0.6  # Smooth turn for 90 degree movement
            )
        except Exception as e:
            logger.debug(f"Thinking pose error (non-critical): {e}")
    
    def return_from_thinking(self) -> None:
        """Return body and head from thinking pose to neutral."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Return to neutral (0.0) or use calibrated home if available
            if self._home_pose_captured and self._home_pose is not None:
                target_body_yaw = self._home_pose.get("body_yaw", 0.0)
                home_head_pose = self._home_pose.get("head_pose", {})
                target_head_yaw = home_head_pose.get("yaw", 0.0)
                target_head_roll = home_head_pose.get("roll", 0.0)
                target_head_pitch = home_head_pose.get("pitch", 0.0)
            else:
                target_body_yaw = 0.0
                target_head_yaw = 0.0
                target_head_roll = 0.0
                target_head_pitch = current_pose.get("pitch", 0.0)  # Keep current pitch
            
            logger.debug(f"🤖 Returning body and head from thinking pose: body={current_body_yaw:.3f} -> {target_body_yaw:.3f}, head_yaw={current_pose.get('yaw', 0.0):.3f} -> {target_head_yaw:.3f}, roll -> {target_head_roll:.3f}")
            self._move_to_pose(
                head_pose={
                    "yaw": target_head_yaw,
                    "roll": target_head_roll,  # Explicitly reset roll to 0 (or home)
                    "pitch": target_head_pitch
                },
                body_yaw=target_body_yaw,
                duration=0.5  # Smooth return
            )
        except Exception as e:
            logger.debug(f"Return from thinking error (non-critical): {e}")
