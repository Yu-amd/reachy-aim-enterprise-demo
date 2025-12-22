# Fix: Audio Routing to Reachy Mini Speaker

## The Problem

PipeWire detects the Reachy Mini audio card but doesn't automatically create a PulseAudio sink for it. This causes "Device or resource busy" errors when trying to use direct ALSA access.

## Solution: Create and Use PulseAudio Sink

### Step 1: Enable the Card Profile

```bash
# Enable output profile for Reachy Mini card
pactl set-card-profile alsa_card.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00 output:analog-stereo
```

**Note:** Your card name might be slightly different. Find it with:
```bash
pactl list cards short | grep -i reachy
```

### Step 2: Check if Sink Was Created

```bash
pactl list sinks short | grep -i reachy
```

If you see a sink, note its name (e.g., `alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00.analog-stereo`)

### Step 3: Set as Default Sink (Easiest)

```bash
# Replace SINK_NAME with the actual sink name from Step 2
pactl set-default-sink SINK_NAME

# Verify it's set
pactl get-default-sink
```

### Step 4: Run the Demo

Now run the demo **without** specifying `--audio-device`. It will automatically use the default sink:

```bash
source .venv/bin/activate
make run
```

## Alternative: Use Sink Name in Code

If you don't want to change your default sink, you can specify the PulseAudio sink name in `.env`:

```bash
# Find the sink name
pactl list sinks | grep -A 2 "Reachy\|Pollen"

# Add to .env (use pulse: prefix)
echo "AUDIO_DEVICE=pulse:alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00.analog-stereo" >> .env
```

## Quick Test

Test if audio routes correctly:

```bash
# Test with paplay (uses default sink if set)
espeak "Testing robot speaker" --stdout | paplay

# Or test with specific sink
espeak "Testing robot speaker" --stdout | paplay --device=alsa_output.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00.analog-stereo
```

## If Sink Still Doesn't Appear

If enabling the profile doesn't create a sink, you may need to:

1. **Restart PipeWire:**
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```

2. **Check card profiles:**
   ```bash
   pactl list cards | grep -A 20 "Card #58" | grep -E "Profile:|Part of"
   ```

3. **Try different profile:**
   ```bash
   # List available profiles
   pactl list cards | grep -A 30 "Card #58" | grep "Profile:"
   
   # Try a different one (e.g., if analog-stereo doesn't work)
   pactl set-card-profile alsa_card.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00 output:iec958-stereo
   ```

## Permanent Fix

To make this persistent across reboots, add to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
# Auto-enable Reachy Mini audio on login
pactl set-card-profile alsa_card.usb-Pollen_Robotics_Reachy_Mini_Audio_100025004254700534-00 output:analog-stereo 2>/dev/null
pactl set-default-sink $(pactl list sinks short | grep -i reachy | head -1 | cut -f2) 2>/dev/null
```

Or create a systemd user service to do this automatically.


