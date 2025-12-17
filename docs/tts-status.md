# TTS (Text-to-Speech) Status for Hardware Demo

## Current Status

✅ **TTS is working** - The robot voice system is functional and usable.

### How It Works

1. **System TTS (pyttsx3)**: The demo uses system TTS as a fallback since the Reachy Mini daemon doesn't have TTS endpoints
2. **Audio Output**: Currently plays on **laptop speakers**, not robot speakers
3. **Non-blocking**: TTS runs in background threads so it doesn't block the main interaction loop

## Testing TTS

Test the TTS functionality:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run TTS test tool
python src/reachy_demo/tools/test_tts.py

# Or test with a specific daemon URL
python src/reachy_demo/tools/test_tts.py --daemon-url http://127.0.0.1:8001
```

## Current Behavior

### What Works ✅

- ✅ TTS speaks LLM responses automatically
- ✅ Non-blocking (doesn't freeze the demo)
- ✅ Uses American English voices when available
- ✅ Handles text cleaning and normalization
- ✅ Multiple fallback methods (pyttsx3 → espeak → direct espeak)

### Limitations ⚠️

- ⚠️ **Audio plays on laptop speakers**, not robot speakers
- ⚠️ The Reachy Mini daemon (v1.2.0) doesn't have TTS endpoints
- ⚠️ System TTS quality depends on your system's TTS engine

## Why Robot Speakers Don't Work

The Reachy Mini daemon API doesn't expose TTS endpoints:
- ❌ `/api/speak` - Not found
- ❌ `/api/tts` - Not found  
- ❌ `/api/audio/speak` - Not found
- ✅ `/api/volume/test-sound` - Works (but only plays a test sound)

The daemon can play sounds (test-sound works), but there's no endpoint to send custom TTS audio.

## Solutions for Robot Speakers

### Option 1: Use System TTS (Current - Works)

**Pros:**
- ✅ Works immediately
- ✅ No additional setup
- ✅ Offline capable

**Cons:**
- ❌ Plays on laptop, not robot

### Option 2: Audio Routing (Advanced)

If you want audio on robot speakers, you could:

1. **Generate audio file** using TTS
2. **Route audio** to robot via:
   - PulseAudio routing
   - ALSA device selection
   - Network audio streaming

This requires system-level audio configuration.

### Option 3: Wait for Daemon Update

Future versions of `reachy-mini-daemon` might add TTS endpoints. When available, the code will automatically detect and use them.

## Verification

To verify TTS is working:

1. **Run the demo**: `make run`
2. **Ask a question**: The robot should speak the response
3. **Check logs**: Look for `🔊 Speaking via system TTS` messages
4. **Listen**: Audio should play on your laptop speakers

## Troubleshooting

### No Audio

1. **Check system audio**: `aplay /usr/share/sounds/alsa/Front_Center.wav`
2. **Check TTS**: `espeak "test"` (should speak)
3. **Check logs**: Look for TTS error messages

### Wrong Voice

The system tries to use American English voices. If you hear a different accent:
- Check available voices: `python -c "import pyttsx3; [print(v.name) for v in pyttsx3.init().getProperty('voices')[:10]]"`
- The system will use the best available English voice

### Audio Quality

System TTS quality depends on:
- Your Linux distribution's TTS engine
- Available voices (espeak, festival, etc.)
- System audio configuration

For better quality, consider cloud TTS services (see `docs/tts-implementation.md`).

## Summary

**TTS Status**: ✅ **Working and Usable**

- The robot voice system is functional
- Audio plays on laptop speakers (not robot speakers)
- This is expected behavior given daemon limitations
- The demo works well for presentations and testing

For production use with robot speakers, you would need:
1. Daemon TTS support (not available in v1.2.0), OR
2. Custom audio routing solution

