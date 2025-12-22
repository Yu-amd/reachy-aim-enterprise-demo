# Audio Troubleshooting: Device Busy Error

If you're getting "Device or resource busy" errors when trying to use the Reachy Mini speaker, this is because PipeWire (or PulseAudio) is managing your audio system and blocking direct ALSA access.

## Quick Fix: Set Default Sink (Easiest)

The simplest solution is to set the Reachy Mini as your default audio output, then the TTS will automatically use it:

```bash
# 1. Find your Reachy Mini sink
pactl list sinks | grep -A 5 -i "reachy\|card.*4"

# 2. Set it as default (replace SINK_NAME with actual name)
pactl set-default-sink SINK_NAME

# 3. Now run the demo - audio will go to default sink
make run
```

## Alternative: Use PulseAudio Sink Name

If you can find the PulseAudio sink name for your Reachy device:

```bash
# Find the sink
pactl list sinks short | grep -i reachy

# Use the sink name in .env
echo "AUDIO_DEVICE=pulse:SINK_NAME" >> .env
```

## Workaround: Temporarily Disable PipeWire (Advanced)

If the above doesn't work, you can temporarily stop PipeWire to allow direct ALSA access:

```bash
# Stop PipeWire
systemctl --user stop pipewire pipewire-pulse wireplumber

# Run your demo
make run

# Restart PipeWire when done
systemctl --user start pipewire pipewire-pulse wireplumber
```

**Warning:** This will stop all audio on your system until you restart PipeWire.

## Check What's Using the Device

To see what's holding the audio device:

```bash
# Check processes using audio devices
lsof /dev/snd/* | grep -i "card.*4\|reachy"

# Or check with fuser
fuser -v /dev/snd/controlC4
```

## Make PipeWire Expose the Device

If the device doesn't show up in PulseAudio sinks, you may need to configure PipeWire:

1. **Check if device is detected:**
   ```bash
   pw-cli list-objects | grep -i reachy
   ```

2. **If not detected, check ALSA:**
   ```bash
   aplay -l | grep -i reachy
   ```

3. **Restart PipeWire to pick up new devices:**
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```

## Current Status

The code now:
- ✅ Detects USB/Reachy audio devices automatically
- ✅ Tries PulseAudio sinks first (PipeWire-compatible)
- ✅ Falls back to ALSA with `plughw:` prefix (PipeWire-compatible)
- ⚠️ Still may fail if device is busy or not exposed by PipeWire

**Recommended Solution:** Set the Reachy Mini as your default PulseAudio sink, then the demo will automatically use it without needing device specification.


