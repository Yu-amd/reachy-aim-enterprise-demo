# Troubleshooting Guide

## Common Issues and Solutions

### Port Conflicts

#### Issue: "Address already in use" or port conflicts

**Symptoms:**
- Daemon fails to start
- Demo app can't connect to daemon
- Multiple services trying to use the same port

**Solution:**
Follow the port rules:
- **LMStudio**: Port `:1234` (default)
- **AIM Endpoint**: Port `:8000` (default, or configured)
- **Reachy Daemon**: Port `:8001` (configured to avoid conflicts)
- **Metrics**: Port `:9100` (Prometheus)

**Check what's using a port:**
```bash
# Check if port is in use
lsof -i :8001
# or
netstat -tlnp | grep 8001
# or
ss -tlnp | grep 8001
```

**Kill process using a port:**
```bash
# Find PID
lsof -ti :8001
# Kill it
kill $(lsof -ti :8001)
```

### Reachy Daemon Issues

#### Issue: Daemon won't start

**Symptoms:**
- `reachy-mini-daemon` command fails
- Permission denied errors
- "Device or resource busy" errors

**Solutions:**

1. **Permission denied (hardware mode):**
   ```bash
   # Add user to dialout group
   sudo usermod -a -G dialout $USER
   # Log out and back in, or:
   newgrp dialout
   ```

2. **Device busy:**
   ```bash
   # Stop any existing daemon processes
   make stop-daemon
   # Or manually:
   pkill -f reachy-mini-daemon
   ```

3. **Port already in use:**
   ```bash
   # Use a different port
   reachy-mini-daemon -p /dev/ttyACM0 --fastapi-port 8002
   # Update .env: REACHY_DAEMON_URL=http://127.0.0.1:8002
   ```

#### Issue: Daemon not reachable

**Symptoms:**
- Demo app shows "Reachy daemon not reachable" warning
- Gestures don't work
- Health check fails

**Solutions:**

1. **Verify daemon is running:**
   ```bash
   curl http://127.0.0.1:8001/api/state/full
   ```

2. **Check daemon URL in .env:**
   ```bash
   grep REACHY_DAEMON_URL .env
   # Should match the port daemon is using
   ```

3. **Check firewall:**
   ```bash
   # If using non-localhost URL, check firewall
   sudo ufw status
   ```

### LMStudio Issues

#### Issue: Can't connect to LMStudio

**Symptoms:**
- "Connection refused" errors
- Timeout errors
- Demo app can't reach LLM endpoint

**Solutions:**

1. **Verify LMStudio is running:**
   - Check LMStudio UI - server should show "Running"
   - Verify a model is loaded

2. **Check LMStudio URL:**
   ```bash
   # Test connection
   curl http://localhost:1234/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "test", "messages": [{"role": "user", "content": "hi"}]}'
   ```

3. **Check .env configuration:**
   ```bash
   # For local LMStudio
   AIM_BASE_URL=http://localhost:1234
   
   # For LMStudio on network
   AIM_BASE_URL=http://192.168.1.131:1234
   ```

4. **LMStudio on different port:**
   - Check LMStudio settings for the actual port
   - Update `AIM_BASE_URL` in `.env` to match

5. **Firewall (network LMStudio):**
   ```bash
   # If LMStudio is on another machine, check firewall
   # On LMStudio machine, allow incoming connections on port 1234
   ```

#### Issue: LMStudio responses are slow

**Symptoms:**
- Long wait times for responses
- Timeout errors
- SLO misses

**Solutions:**

1. **Increase timeout in .env:**
   ```bash
   AIM_TIMEOUT_MS=60000  # 60 seconds (default is 30)
   ```

2. **Check model size:**
   - Smaller models respond faster
   - Large models (7B+) may need more time

3. **Check system resources:**
   - Ensure LMStudio has enough RAM/VRAM
   - Close other applications

### AIM Endpoint Issues

#### Issue: Can't connect to remote AIM endpoint

**Symptoms:**
- Connection refused
- Timeout errors
- SSH port forward not working

**Solutions:**

1. **SSH Port Forward:**
   ```bash
   # Forward remote AIM to local port
   ssh -L 8000:localhost:8000 user@cluster-host
   # Then in .env:
   AIM_BASE_URL=http://127.0.0.1:8000
   ```

2. **Verify endpoint is accessible:**
   ```bash
   curl http://127.0.0.1:8000/health
   # or
   curl http://127.0.0.1:8000/docs
   ```

3. **Check network connectivity:**
   ```bash
   ping cluster-host
   telnet cluster-host 8000
   ```

### TTS (Text-to-Speech) Issues

#### Issue: No audio / robot doesn't speak

**Symptoms:**
- Robot performs gestures but no sound
- TTS errors in logs

**Solutions:**

1. **Check system audio:**
   ```bash
   # Test system audio
   aplay /usr/share/sounds/alsa/Front_Center.wav
   ```

2. **Check TTS engine:**
   ```bash
   # Test espeak
   espeak "test"
   ```

3. **Check TTS in demo:**
   ```bash
   # Run TTS test tool
   python src/reachy_demo/tools/test_tts.py
   ```

4. **Note**: Audio plays on laptop speakers, not robot speakers (daemon limitation)

#### Issue: Wrong voice / accent

**Solutions:**

1. **Check available voices:**
   ```bash
   python -c "import pyttsx3; [print(v.name) for v in pyttsx3.init().getProperty('voices')[:10]]"
   ```

2. **System tries to use American English by default**
   - If wrong voice, check system TTS configuration
   - The code automatically selects best available English voice

### Configuration Issues

#### Issue: "AIM_BASE_URL is required"

**Symptoms:**
- Demo app fails to start
- Configuration error

**Solutions:**

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Set AIM_BASE_URL:**
   ```bash
   # Edit .env and set:
   AIM_BASE_URL=http://localhost:1234  # For LMStudio
   # or
   AIM_BASE_URL=http://127.0.0.1:8000  # For AIM via SSH forward
   ```

3. **Verify .env is not in .gitignore:**
   - `.env` should be ignored (not committed)
   - `.env.example` should be committed

### Metrics Issues

#### Issue: Can't access metrics endpoint

**Symptoms:**
- `curl http://127.0.0.1:9100/metrics` fails
- Connection refused

**Solutions:**

1. **Verify metrics server started:**
   - Check demo app logs for "Started metrics server"
   - Default port is 9100

2. **Check if port is in use:**
   ```bash
   lsof -i :9100
   ```

3. **Change metrics port in .env:**
   ```bash
   EDGE_METRICS_PORT=9101
   ```

### Gesture Issues

#### Issue: Robot doesn't perform gestures

**Symptoms:**
- Robot doesn't move
- Gesture errors in logs

**Solutions:**

1. **Verify daemon is running:**
   ```bash
   curl http://127.0.0.1:8001/api/state/full
   ```

2. **Check robot mode in .env:**
   ```bash
   # For hardware:
   ROBOT_MODE=hardware
   
   # For simulation:
   ROBOT_MODE=sim
   ```

3. **Test gesture directly:**
   ```bash
   curl -X POST http://127.0.0.1:8001/api/move/goto \
     -H "Content-Type: application/json" \
     -d '{"head_pose": {"pitch": 0.2}, "duration": 0.5}'
   ```

### Python Environment Issues

#### Issue: Module not found errors

**Symptoms:**
- `ModuleNotFoundError`
- Import errors

**Solutions:**

1. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

2. **Reinstall package:**
   ```bash
   pip install -e .
   ```

3. **Check Python version:**
   ```bash
   python --version  # Should be 3.10+
   ```

### Network Issues

#### Issue: Can't reach endpoints

**Solutions:**

1. **Check DNS/hostname resolution:**
   ```bash
   ping localhost
   ping 127.0.0.1
   ```

2. **Check firewall:**
   ```bash
   sudo ufw status
   # Allow localhost connections (usually allowed by default)
   ```

3. **Use IP addresses instead of hostnames:**
   ```bash
   # In .env, use:
   AIM_BASE_URL=http://127.0.0.1:1234
   # instead of:
   AIM_BASE_URL=http://localhost:1234
   ```

## Getting Help

### Check Logs

1. **Demo app logs:**
   - Look for error messages in terminal output
   - Check for warnings about daemon/TTS/connections

2. **Daemon logs:**
   - Check daemon terminal output
   - Look for startup errors or connection issues

### Debug Mode

Enable verbose logging:
```bash
# Set log level
export PYTHONPATH=src
python -m reachy_demo.main --help
```

### Test Individual Components

1. **Test daemon:**
   ```bash
   curl http://127.0.0.1:8001/api/state/full
   ```

2. **Test LLM endpoint:**
   ```bash
   curl -X POST http://localhost:1234/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "test", "messages": [{"role": "user", "content": "hi"}]}'
   ```

3. **Test TTS:**
   ```bash
   python src/reachy_demo/tools/test_tts.py
   ```

4. **Test gesture mapping:**
   ```bash
   python src/reachy_demo/tools/test_gesture_mapping.py --text "That's great!"
   ```

## Quick Reference

### Port Summary
- **8000**: AIM endpoint (default)
- **8001**: Reachy daemon (configured)
- **1234**: LMStudio (default)
- **9100**: Metrics (Prometheus)

### Key Files
- **`.env`**: Configuration (not committed)
- **`.env.example`**: Configuration template (committed)
- **`Makefile`**: Convenience commands
- **`docs/`**: Documentation

### Key Commands
- `make install`: Setup environment
- `make sim`: Start daemon in simulation
- `make run`: Run demo app
- `make stop-daemon`: Stop daemon processes
- `make stop`: Stop demo app processes

