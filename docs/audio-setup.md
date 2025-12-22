# Audio Setup Guide: Using Reachy Mini Speaker for TTS

This guide will help you configure the demo to use the Reachy Mini's built-in speaker for text-to-speech output instead of your laptop speakers.

## Step 1: Connect Your Reachy Mini

1. **Connect the Reachy Mini** to your computer via USB
2. **Power on** the robot
3. Wait a few seconds for the system to recognize the USB audio device

## Step 2: Find Your Audio Device

Open a terminal and run:

```bash
aplay -l
```

You should see output like:

```
**** List of PLAYBACK Hardware Devices ****
card 0: Generic [HD-Audio Generic], device 3: HDMI 0 [DELL U3417W]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 1: USB [USB Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

Look for entries containing:
- **"USB"** in the name
- **"Reachy"** in the name (if your device shows up with that name)
- Any USB audio device that appears when you plug in the robot

**Note the card number and device number** from the output. For example:
- If you see `card 1: USB [USB Audio Device], device 0`, your device is `hw:1,0`
- Format: `hw:CARD_NUMBER,DEVICE_NUMBER`

## Step 3: Test Audio Device Detection (Optional)

The system will automatically detect USB audio devices. To verify detection:

```bash
# Activate your virtual environment
source .venv/bin/activate

# Run the TTS test tool (use one of these methods)
python3 src/reachy_demo/tools/test_tts.py
# OR
python3 -m reachy_demo.tools.test_tts
```

The output will show:
- `✓ Detected Reachy Mini audio device: hw:1,0` (if auto-detection works)
- Or it will use the system default if no device is found

## Step 4: Configure Audio Device (If Auto-Detection Doesn't Work)

If auto-detection doesn't find your device, you can manually configure it:

1. **Open or create** `.env` file in the project root:

```bash
nano .env
# or
vim .env
```

2. **Add the audio device configuration**:

```bash
# Audio device for Reachy Mini speaker
# Format: hw:CARD_NUMBER,DEVICE_NUMBER
# Example: AUDIO_DEVICE=hw:1,0
AUDIO_DEVICE=hw:1,0
```

Replace `hw:1,0` with your actual device from Step 2.

3. **Save the file** and exit

## Step 5: Test TTS with Specific Device

Test that TTS works with your configured device:

```bash
# Activate virtual environment
source .venv/bin/activate

# Test with auto-detection
python3 src/reachy_demo/tools/test_tts.py
# OR
python3 -m reachy_demo.tools.test_tts

# OR test with specific device
python3 src/reachy_demo/tools/test_tts.py --audio-device hw:1,0
# OR
python3 -m reachy_demo.tools.test_tts --audio-device hw:1,0
```

You should hear the test phrases through the Reachy Mini speaker.

## Step 6: Run the Full Demo

Once audio is configured, run the full demo:

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Make sure the Reachy daemon is running
# (In another terminal or background)
reachy-mini-daemon -p /dev/ttyACM0 --fastapi-port 8001

# Run the demo
make run
# or
python -m reachy_demo.main run
```

When you interact with the demo, the robot's responses will play through the Reachy Mini speaker.

## Troubleshooting

### No Sound from Robot Speaker

1. **Check device is connected**:
   ```bash
   aplay -l | grep -i usb
   ```

2. **Test the device directly**:
   ```bash
   # Generate a test sound
   espeak "Testing robot speaker" --stdout | aplay -D hw:1,0
   ```
   Replace `hw:1,0` with your device.

3. **Check device permissions**:
   ```bash
   ls -l /dev/snd/
   ```
   Your user should have access to audio devices.

4. **Try different device numbers**:
   - If `hw:1,0` doesn't work, try `hw:1,1` or `hw:2,0`
   - Check `aplay -l` output for all available devices

### Auto-Detection Not Working

If auto-detection doesn't find your device:

1. **Check device name**: The detection looks for "USB" or "Reachy" in the device name
2. **Manual configuration**: Use Step 4 to manually set `AUDIO_DEVICE` in `.env`
3. **Verify device**: Make sure the device shows up in `aplay -l` output

### Audio Plays on Wrong Device

1. **Check `.env` file**: Make sure `AUDIO_DEVICE` is set correctly
2. **Restart the demo**: Configuration is loaded at startup
3. **Verify device**: Run `aplay -l` again to confirm device numbers haven't changed

### Device Not Found After Reconnecting

USB device numbers can change when you reconnect devices:

1. **Run `aplay -l` again** to get the new device number
2. **Update `.env`** if you're using manual configuration
3. **Or rely on auto-detection** which will find the device automatically

## Advanced: Using PulseAudio Device Names

If you're using PulseAudio, you can also use PulseAudio device names:

```bash
# List PulseAudio sinks
pactl list short sinks

# Use PulseAudio device in .env
AUDIO_DEVICE=pulse:1
```

However, ALSA device names (`hw:X,Y`) are more reliable for direct hardware access.

## Summary

**Quick Setup (Auto-Detection)**:
1. Connect Reachy Mini
2. Run `make run`
3. Audio should automatically route to robot speaker

**Manual Setup**:
1. Connect Reachy Mini
2. Run `aplay -l` to find device
3. Add `AUDIO_DEVICE=hw:X,Y` to `.env`
4. Run `make run`

The system will prioritize:
1. Explicitly configured `AUDIO_DEVICE` from `.env`
2. Auto-detected USB audio device
3. System default audio device

