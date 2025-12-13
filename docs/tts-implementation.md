# TTS (Text-to-Speech) Implementation Guide

The `speak()` method in `src/reachy_demo/adapters/robot_rest.py` is currently a placeholder. Here are several implementation options:

## Option 1: System TTS (Simplest - Recommended for Quick Start)

Use Python's `pyttsx3` library for offline, cross-platform TTS:

### Installation

```bash
pip install pyttsx3
```

### Implementation

Update `src/reachy_demo/adapters/robot_rest.py`:

```python
import pyttsx3

class ReachyDaemonREST(RobotAdapter):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._startup_logged = False
        # Initialize TTS engine
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty('rate', 150)  # Speed (words per minute)
            self._tts_engine.setProperty('volume', 0.8)  # Volume (0.0 to 1.0)
            logger.info("✓ TTS engine initialized (pyttsx3)")
        except Exception as e:
            logger.warning(f"⚠ TTS engine initialization failed: {e}")
            self._tts_engine = None

    def speak(self, text: str) -> None:
        """Speak text using system TTS."""
        if self._tts_engine is None:
            logger.debug(f"🔊 TTS unavailable: '{text[:50]}...'")
            return
        
        try:
            logger.debug(f"🔊 Speaking: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        except Exception as e:
            logger.warning(f"⚠ TTS error: {e}")
```

**Pros:**
- Works offline (no internet required)
- Cross-platform (Windows, Linux, macOS)
- Simple to implement
- No API keys needed

**Cons:**
- Quality depends on system TTS (may sound robotic)
- Blocks execution while speaking (use threading for async)

## Option 2: Reachy Daemon API (If Available)

Check if the Reachy daemon exposes a TTS endpoint:

```bash
# Check daemon API docs
curl http://localhost:8000/docs
# Or browse: http://localhost:8000/docs
```

If there's a `/api/speak` or `/api/tts` endpoint:

```python
def speak(self, text: str) -> None:
    """Speak text via Reachy daemon API."""
    try:
        logger.debug(f"🔊 Speaking via daemon: '{text[:50]}...'")
        self._post("/api/speak", json={"text": text})
        # Or if it's a different endpoint:
        # self._post("/api/tts", json={"text": text, "language": "en"})
    except Exception as e:
        logger.warning(f"⚠ TTS API error: {e}")
```

**Pros:**
- Uses robot's built-in audio system
- Consistent with other robot controls
- May support robot-specific features

**Cons:**
- Requires daemon to support TTS endpoint
- May not be available in simulation

## Option 3: Cloud TTS Services (Best Quality)

Use cloud TTS services for high-quality, natural-sounding speech:

### Google Cloud TTS

```bash
pip install google-cloud-texttospeech
```

```python
from google.cloud import texttospeech
import io

class ReachyDaemonREST(RobotAdapter):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._startup_logged = False
        # Initialize Google TTS client
        try:
            self._tts_client = texttospeech.TextToSpeechClient()
            logger.info("✓ Google Cloud TTS initialized")
        except Exception as e:
            logger.warning(f"⚠ Google TTS initialization failed: {e}")
            self._tts_client = None

    def speak(self, text: str) -> None:
        """Speak text using Google Cloud TTS."""
        if self._tts_client is None:
            logger.debug(f"🔊 TTS unavailable: '{text[:50]}...'")
            return
        
        try:
            logger.debug(f"🔊 Speaking (Google TTS): '{text[:50]}...'")
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = self._tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            
            # Play audio (requires pygame or similar)
            # Or send to robot speakers if daemon supports it
            # For now, save to file and play:
            with open("/tmp/tts_output.mp3", "wb") as out:
                out.write(response.audio_content)
            # Play using system player or send to robot
        except Exception as e:
            logger.warning(f"⚠ Google TTS error: {e}")
```

**Other Cloud Options:**
- **AWS Polly**: `boto3` + `polly` service
- **Azure Cognitive Services**: `azure-cognitiveservices-speech`
- **OpenAI TTS**: `openai` library (if you have API access)

**Pros:**
- High-quality, natural-sounding speech
- Multiple voice options
- Language support

**Cons:**
- Requires internet connection
- May have API costs
- Requires API keys/credentials

## Option 4: Async TTS (Non-Blocking)

To prevent TTS from blocking the main loop, use threading:

```python
import threading

def speak(self, text: str) -> None:
    """Speak text asynchronously (non-blocking)."""
    def _speak_async():
        try:
            logger.debug(f"🔊 Speaking: '{text[:50]}...'")
            self._tts_engine.say(text)
            self._tts_engine.runAndWait()
        except Exception as e:
            logger.warning(f"⚠ TTS error: {e}")
    
    # Run TTS in background thread
    thread = threading.Thread(target=_speak_async, daemon=True)
    thread.start()
```

## Option 5: Send Audio to Robot Speakers

If the Reachy daemon supports audio playback, you could:

1. Generate audio file (using any TTS method above)
2. Send audio file to daemon
3. Daemon plays on robot speakers

```python
def speak(self, text: str) -> None:
    """Generate TTS and send to robot speakers."""
    # Generate audio (using any TTS method)
    audio_file = self._generate_tts_audio(text)
    
    # Send to robot daemon
    try:
        with open(audio_file, 'rb') as f:
            files = {'audio': f}
            self._post("/api/audio/play", files=files)
    except Exception as e:
        logger.warning(f"⚠ Audio playback error: {e}")
```

## Recommended Implementation Path

1. **Start with Option 1 (System TTS)** - Quick to implement, works offline
2. **If daemon has TTS endpoint** - Use Option 2 for robot-native audio
3. **For production quality** - Use Option 3 (Cloud TTS) with Option 4 (async)

## Testing TTS

After implementing, test with:

```python
# In Python shell or test script
from reachy_demo.adapters.robot_rest import ReachyDaemonREST

robot = ReachyDaemonREST("http://127.0.0.1:8000")
robot.speak("Hello, this is a test of the text to speech system.")
```

## Configuration

Consider adding TTS configuration to `config.py`:

```python
# In Settings dataclass
tts_enabled: bool = True
tts_provider: str = "system"  # "system", "google", "aws", etc.
tts_voice: str = "default"
tts_rate: int = 150
tts_volume: float = 0.8
```

Then load from `.env`:

```ini
TTS_ENABLED=true
TTS_PROVIDER=system
TTS_RATE=150
TTS_VOLUME=0.8
```

