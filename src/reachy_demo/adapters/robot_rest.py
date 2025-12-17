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
            elif name == "random":
                gestures = ["nod", "excited", "thinking", "greeting", "happy", "listening", "agreeing", "curious"]
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
        """Perform a more engaging head nod gesture with smoother movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            
            # More pronounced nod: down then up with slight pause
            # Down - smoother and more natural
            self._post("/api/move/goto", {
                "head_pose": {
                    **current_pose,
                    "pitch": current_pitch - 0.35,  # Slightly more pronounced
                },
                "duration": 0.25,  # Faster down movement
                "interpolation": "minjerk"
            })
            time.sleep(0.08)  # Brief pause at bottom
            
            # Up - energetic return
            self._post("/api/move/goto", {
                "head_pose": {
                    **current_pose,
                    "pitch": current_pitch + 0.15,  # Slight overshoot for natural feel
                },
                "duration": 0.25,
                "interpolation": "minjerk"
            })
            time.sleep(0.05)
            
            # Smooth return to neutral
            self._post("/api/move/goto", {
                "head_pose": current_pose,
                "duration": 0.2,
                "interpolation": "minjerk"
            })
        except Exception:
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
        """Enhanced excited gesture: more dynamic antennas wiggle with energetic head bobs and body movement."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Energetic head bob up with slight body turn
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.25},
                body_yaw=current_body_yaw + 0.1,
                duration=0.12
            )
            time.sleep(0.08)
            
            # Rapid antennas wiggle (4 movements for more energy)
            for i in range(4):
                # Antennas spread wide
                self._move_to_pose(
                    antennas=[0.4, -0.4],
                    duration=0.08
                )
                time.sleep(0.03)
                # Antennas cross
                self._move_to_pose(
                    antennas=[-0.3, 0.3],
                    duration=0.08
                )
                time.sleep(0.03)
            
            # Head bob down with body return
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.12},
                body_yaw=current_body_yaw - 0.05,
                duration=0.15
            )
            time.sleep(0.08)
            
            # Bounce back up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.1},
                duration=0.12
            )
            time.sleep(0.05)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.2
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
        """Enhanced happy gesture: more bouncy antennas with energetic head bobs."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # More bouncy movements (3 cycles for more energy)
            for i in range(3):
                # Head up with antennas raised and slight body turn
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.18},
                    antennas=[0.35, 0.35],
                    body_yaw=current_body_yaw + (0.05 if i % 2 == 0 else -0.05),
                    duration=0.12
                )
                time.sleep(0.08)
                # Head down with antennas lower
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) - 0.12},
                    antennas=[0.15, 0.15],
                    duration=0.12
                )
                time.sleep(0.08)
            
            # Final bounce up
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.1},
                antennas=[0.25, 0.25],
                duration=0.1
            )
            time.sleep(0.05)
            
            # Return to original
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                body_yaw=current_body_yaw,
                duration=0.2
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
        """Agreeing gesture: multiple quick nods (emphatic agreement)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_pitch = current_pose.get("pitch", 0.0)
            
            # Three quick nods
            for _ in range(3):
                # Nod down
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch - 0.25},
                    duration=0.15
                )
                time.sleep(0.05)
                # Nod up
                self._move_to_pose(
                    head_pose={**current_pose, "pitch": current_pitch + 0.1},
                    duration=0.15
                )
                time.sleep(0.1)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                duration=0.2
            )
        except Exception:
            pass

    def _surprised_gesture(self) -> None:
        """Surprised gesture: head jerks back with antennas spread wide."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_antennas = state.get("antennas_position", [0.0, 0.0])
            
            # Quick head jerk back with antennas spread
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pose.get("pitch", 0.0) + 0.3},
                antennas=[0.5, -0.5],  # Antennas spread wide
                duration=0.15
            )
            time.sleep(0.2)  # Hold surprised pose
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                antennas=current_antennas,
                duration=0.25
            )
        except Exception:
            pass

    def _curious_gesture(self) -> None:
        """Curious gesture: head tilts with slight body turn (inquisitive posture)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            
            # Head tilt right with body turn
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_pose.get("yaw", 0.0) + 0.2,
                    "roll": current_pose.get("roll", 0.0) + 0.15
                },
                body_yaw=current_body_yaw + 0.15,
                duration=0.3
            )
            time.sleep(0.3)
            
            # Slight adjustment (like thinking)
            self._move_to_pose(
                head_pose={
                    **current_pose,
                    "yaw": current_pose.get("yaw", 0.0) - 0.15,
                    "roll": current_pose.get("roll", 0.0) - 0.1
                },
                duration=0.25
            )
            time.sleep(0.2)
            
            # Return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
                duration=0.3
            )
        except Exception:
            pass

    def _emphatic_gesture(self) -> None:
        """Emphatic gesture: strong nod with body movement (emphasis)."""
        try:
            state = self.get_state()
            current_pose = state.get("head_pose", {})
            current_body_yaw = state.get("body_yaw", 0.0)
            current_pitch = current_pose.get("pitch", 0.0)
            
            # Strong nod down with body lean
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch - 0.4},
                body_yaw=current_body_yaw + 0.1,
                duration=0.2
            )
            time.sleep(0.1)
            
            # Strong return up with body return
            self._move_to_pose(
                head_pose={**current_pose, "pitch": current_pitch + 0.2},
                body_yaw=current_body_yaw - 0.05,
                duration=0.2
            )
            time.sleep(0.1)
            
            # Final return to neutral
            self._move_to_pose(
                head_pose=current_pose,
                body_yaw=current_body_yaw,
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
