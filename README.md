# Reachy Mini Lite + AMD Inference Microservice (AIM) Enterprise Demo

This repo provides a **fully functional** enterprise demo that connects a Reachy Mini robot to an AIM (OpenAI-compatible) endpoint. You can run it **without the physical robot** using the Reachy Mini daemon simulation, while targeting a real **AIM OpenAI-compatible endpoint** (e.g., running on MI300X in your datacenter).

## Architecture (Edge + Cluster)

```
Strix Halo Host (Edge)
  ├── reachy-mini-daemon (sim now / hardware later)
  └── reachy-demo client (this repo)
        │
        └── HTTP requests
             │
             v
AIM Endpoint (OpenAI-compatible) on MI300X (Cluster)
```

**Data Flow:**
1. User types prompt → Edge client (`reachy-demo`)
2. Edge client → AIM endpoint (LLM inference)
3. AIM response → Edge client
4. Edge client → Reachy daemon (gestures + TTS)
5. Robot performs gesture and speaks response

## Demo Modes

### Mode A (Recommended): Remote AIM Endpoint
- **AIM runs in your cluster** (MI300X datacenter)
- Edge client points to `AIM_BASE_URL` (e.g., via SSH port forward or ingress)
- Reachy daemon runs locally on edge host (sim or hardware)
- **Use case:** Production-like setup, real inference hardware

### Mode B: Local LLM Endpoint
- **Local LLM endpoint runs on the same host** as edge client
- Supports OpenAI-compatible endpoints:
  - **Ollama** (local LLM runner)
  - **LMStudio** (local LLM GUI/server)
  - **Custom OpenAI-compatible endpoint**
- Both LLM endpoint and daemon need different ports (LLM: 8000, daemon: 8001)
- **Note:** AIM (AMD Inference Microservice) requires Instinct GPU hardware and is not supported locally
- **Use case:** Development, testing without cluster access, local experimentation

### Mode C: Offline Stub (Future)
- Run without LLM endpoint; prints canned responses
- Useful for robot-only testing

## Golden Path (No Robot Required)

**Recommended setup** - avoids port conflicts:

```bash
# Setup (one time)
make install
cp .env.example .env
# Edit .env: Set AIM_BASE_URL to your AIM endpoint

# Terminal 1: Start Reachy daemon on port 8001 (avoids AIM port conflicts)
make sim

# Terminal 2: Run the demo
make run
```

The `make sim` command automatically runs the daemon on port 8001, and `.env.example` is pre-configured to use `REACHY_DAEMON_URL=http://127.0.0.1:8001`.

**Why port 8001?** Both AIM and Reachy daemon default to port 8000. Using 8001 for the daemon avoids conflicts when AIM is on 8000 (common with SSH port forwarding).

## Quick Start (One Command Per Terminal)

Same as the [Golden Path](#golden-path-no-robot-required) above:

```bash
# Setup (one time)
make install
cp .env.example .env
# Edit .env and set AIM_BASE_URL to your AIM endpoint

# Terminal 1: Start Reachy daemon simulation (port 8001)
make sim

# Terminal 2: Run the demo
make run
```

That's it! The demo will connect to your AIM endpoint and control the simulated robot.

**Note:** `make install` automatically creates the virtual environment and installs dependencies. If you prefer to do it separately: `make venv` then `make install`.

## Demo Narrative

This demo showcases an **enterprise edge-to-cloud AI architecture**:

- **Reachy Mini** is the edge client (I/O interface) - handles user interaction and robot control
- **AIM (AMD Inference Microservice)** is the inference API (OpenAI-compatible) - runs LLM inference in your datacenter
- **Kubernetes add-ons** provide repeatability - load generator and Grafana dashboards for monitoring

The architecture separates concerns: edge handles I/O and latency-sensitive robot control, while cloud handles compute-intensive LLM inference. This enables real-time robot interactions powered by large language models.

## What you get
- **Edge client** (runs on your Strix Halo host): CLI orchestrator + AIM client + Prometheus metrics
- **Reachy Mini integration** via daemon URL (simulation-friendly, ready for hardware)
- **Helm chart** (`helm/reachy-demo-addons`) for cluster-side demo add-ons:
  - Load generator CronJob (triggerable as a Job)
  - Grafana dashboard JSON shipped as a ConfigMap
  - Optional dependency wiring for `kube-prometheus-stack` (disabled by default)
  
  **Note:** This chart is for add-ons only (loadgen, dashboards). It does not deploy the AIM endpoint itself. Configure `aim.baseUrl` to point to your existing AIM service.

## Prerequisites

- Python 3.10 or higher
- `pip` and `venv` (usually included with Python)
- Access to an AIM (OpenAI-compatible) endpoint
- (Optional) `helm` for Kubernetes deployment
- (Optional) `reachy-mini[mujoco]` for local simulation testing
- (Optional) System TTS backend for speech (automatically installed with Python dependencies):
  - **Linux**: `espeak` or `espeak-ng` (usually pre-installed, or `sudo apt-get install espeak`)
  - **macOS**: Built-in TTS (no additional install needed)
  - **Windows**: SAPI5 (built-in, no additional install needed)

## Quick Start Guide

Follow these steps to test the code locally:

### Step 1: Set up Python environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install -U pip

# Install the package and dependencies
pip install -e .
```

**Verify installation:**
```bash
# Check that the command is available
python -m reachy_demo.main --help
```

### Step 2: Deploy LLM Endpoint

Before configuring the edge client, you need an OpenAI-compatible LLM endpoint. Choose based on your setup:

#### Option A: Remote AIM Endpoint (Mode A - Recommended)

For production setups with Instinct GPU hardware, deploy AIM in your cluster:

```bash
# Clone the AIM-demo repository
git clone https://github.com/Yu-amd/AIM-demo.git
cd AIM-demo

# Follow the Docker deployment instructions in that repository
# Deploy to cluster with Instinct GPUs (MI300X)
```

**Note:** AIM (AMD Inference Microservice) requires Instinct GPU hardware and is typically deployed in a datacenter/cluster environment, not locally.

**Verify the AIM endpoint:**
```bash
# If using SSH port forward: ssh -L 8000:localhost:8000 user@cluster-host
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/docs
```

#### Option B: Local LLM Endpoint (Mode B)

For local development/testing without Instinct GPUs, use an OpenAI-compatible local LLM:

**Ollama:**
```bash
# Install Ollama: https://ollama.ai
ollama serve  # Runs on http://localhost:11434 by default

# Pull a model
ollama pull llama2

# Ollama uses /api/chat endpoint, configure AIM_BASE_URL=http://localhost:11434
# and AIM_CHAT_PATH=/api/chat in .env
```

**LMStudio:**
```bash
# Install LMStudio: https://lmstudio.ai
# Start LMStudio server (usually http://localhost:1234)
# Configure AIM_BASE_URL=http://localhost:1234 in .env
```

**Custom OpenAI-compatible endpoint:**
- Any endpoint that implements the OpenAI chat completions API
- Set `AIM_BASE_URL` and `AIM_CHAT_PATH` accordingly

**Verify local endpoint:**
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "llm-prod", "messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 50}'
```

**Alternative: Using existing endpoint**

If you already have an LLM endpoint running (AIM in cluster, Ollama locally, etc.), skip deployment and proceed to Step 3. Just make sure to set `AIM_BASE_URL` in Step 3 to point to your endpoint.

### Step 3: Configure environment variables

```bash
# Copy the example environment file (never commit .env to git!)
cp .env.example .env

# Edit .env and set your AIM endpoint URL
# REQUIRED: Set AIM_BASE_URL to your AIM endpoint
# Example: AIM_BASE_URL=http://127.0.0.1:8000
# Or: AIM_BASE_URL=https://your-aim-endpoint.example.com
```

**Important:** Never commit `.env` to git. It may contain secrets (API keys, endpoints, etc.). Only `.env.example` should be tracked.

**Edit `.env` file:**
- Set `AIM_BASE_URL` (required) - your AIM endpoint URL
  - For local Docker deployment: `http://127.0.0.1:8000` (default)
  - For SSH port forward: `http://127.0.0.1:8000` (if using `ssh -L 8000:localhost:8000 user@host`)
  - For remote endpoint: `https://<your-ingress-host>`
  - For Kubernetes port-forward: `http://127.0.0.1:8000`
- Set `REACHY_DAEMON_URL` - Reachy daemon URL
  - **Default (recommended):** `http://127.0.0.1:8001` (avoids AIM port conflicts)
  - If you need port 8000, set to `http://127.0.0.1:8000` and ensure AIM uses a different port
- (Optional) Adjust `AIM_MODEL` if different from `llm-prod`
- (Optional) Set `AIM_API_KEY` if your endpoint requires authentication

### Step 4: (Optional) Run Reachy Mini daemon in simulation

If you want to test with the Reachy Mini daemon simulation, open a **new terminal**:

```bash
# Activate the same virtual environment
source .venv/bin/activate

# Install reachy-mini with mujoco support
pip install "reachy-mini[mujoco]"

# Install system libraries (if needed)
# On Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y portaudio19-dev espeak

# On Fedora/RHEL:
# sudo dnf install portaudio-devel espeak

# On macOS (using Homebrew):
# brew install portaudio
# (TTS uses built-in macOS voices, no additional install needed)
```

**Start the daemon in simulation mode:**

```bash
# Standard mode (requires PortAudio) - default port 8000
reachy-mini-daemon --sim

# OR headless mode (no audio, no GUI - recommended if you don't need audio)
reachy-mini-daemon --sim --headless

# OR if port 8000 is already in use (e.g., SSH port forward), use a different port:
reachy-mini-daemon --sim --headless --fastapi-port 8001
```

**Verify daemon is running:**
- Open http://localhost:8000/docs (or http://localhost:8001/docs if using custom port) in your browser
- You should see the API documentation
- Or test with: `curl http://localhost:8000/api/state/full` (or port 8001 if using custom port)

**Note:** If you're using SSH port forwarding for the AIM endpoint on port 8000, run the Reachy daemon on a different port (e.g., 8001) and update `REACHY_DAEMON_URL` in your `.env` file accordingly.

**Note:** The demo will work even if the daemon is not running (it will show a warning and continue). If you encounter PortAudio errors, use `--headless` mode or skip the daemon entirely.

### Step 5: Run the edge demo

In your main terminal (with virtual environment activated):

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Run the interactive demo
python -m reachy_demo.main
```

**What to expect:**
1. You'll see a welcome message and metrics URL
2. Type a prompt and press Enter
3. The app will:
   - Send your prompt to the AIM endpoint
   - Display the model's response
   - Show latency metrics (AIM call time, end-to-end time, SLO status)
   - Trigger an expressive robot gesture based on the response content
   - **Speak the response** using TTS (daemon API or system TTS)

**Example interaction:**
```
You> What is machine learning?
[AIM response appears in a panel with latency metrics]
[Robot performs a gesture - e.g., "thinking" for questions, "excited" for positive responses]
[Robot speaks the response using TTS]
```

**To exit:** Press `Ctrl+C`

### Robot Gestures and Speech in Sim Mode

The demo includes **fully implemented robot gestures and text-to-speech** that work in both simulation and hardware mode. Gestures are automatically selected based on the AIM response characteristics, and the robot will speak the AIM endpoint's responses.

**Available Gestures:**
- **`nod`** - Simple head nod (pitch down then back up)
- **`excited`** - Antennas wiggle rapidly with head bobs (for positive/enthusiastic responses)
- **`thinking`** - Head tilts side to side (for questions or processing)
- **`greeting`** - Friendly nod with antennas raised (for short responses)
- **`happy`** - Bouncy antennas with head bob (for fast, positive responses)
- **`confused`** - Head shakes side to side (for uncertainty or longer responses)
- **`wake_up`** - Wake up animation (uses daemon's built-in animation)
- **`goto_sleep`** - Sleep animation (uses daemon's built-in animation)

**Gesture Selection Logic:**
- Questions (responses containing "?") → `thinking`
- Positive keywords ("great", "excellent") → `excited`
- Short responses (< 10 words) → `greeting`
- Fast responses (< 500ms) → `happy`
- Otherwise → Random selection from `nod`, `thinking`, `confused`

All gestures use the Reachy Mini daemon's `/api/move/goto` endpoint to control head pose (pitch, yaw, roll), antennas, and body yaw. The gestures are smooth and expressive, making the robot interaction feel natural even in simulation mode.

**Text-to-Speech:**
- The robot will speak the AIM endpoint's responses automatically
- TTS method is auto-detected: tries daemon API first (`/api/speak`, `/api/tts`, etc.), falls back to system TTS (pyttsx3)
- **In sim mode:** Typically uses system TTS (pyttsx3) which plays through your computer's speakers
- **In hardware mode:** Will use daemon API if available (robot's speakers), otherwise falls back to system TTS
- System TTS works offline and cross-platform (Windows, Linux, macOS)
- You'll see a startup message indicating which TTS method is being used (e.g., `✓ TTS: Using system TTS (pyttsx3)`)

### Step 6: (Optional) Check Prometheus metrics

While the demo is running, you can view metrics in another terminal:

```bash
# View metrics endpoint
curl http://127.0.0.1:9100/metrics
```

Or open in browser: http://127.0.0.1:9100/metrics

**Available metrics:**
- `edge_e2e_ms` - End-to-end latency histogram
- `aim_call_ms` - AIM API call latency histogram
- `edge_requests_total` - Total request counter
- `edge_errors_total` - Error counter
- `edge_slo_miss_total` - SLO violation counter

### Step 7: (Optional) Test local load generator

You can also run a local load test:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run load generator (8 concurrent workers, 30 seconds)
python -m reachy_demo.tools.loadgen_local --concurrency 8 --duration-s 30
```

This will send concurrent requests to your AIM endpoint and display latency statistics (p50, p95, mean).

## AIM Endpoint Deployment Reference

For detailed Docker deployment instructions, see **Step 2** in the [Quick Start Guide](#quick-start-guide) above.

**Quick reference:**
- Clone: `git clone https://github.com/Yu-amd/AIM-demo.git`
- Deploy: Follow instructions in the AIM-demo repository
- Verify: `curl http://127.0.0.1:8000/docs`
- Configure: Set `AIM_BASE_URL=http://127.0.0.1:8000` in `.env`

For the most up-to-date deployment instructions, refer to the [AIM-demo repository](https://github.com/Yu-amd/AIM-demo).

## Testing the Code

### Quick Test (Without AIM Endpoint)

To verify the code structure and imports work correctly:

```bash
# Activate virtual environment
source .venv/bin/activate

# Test configuration loading (will fail without AIM_BASE_URL, which is expected)
python -c "from reachy_demo.config import load_settings; print('Config module OK')" 2>&1 || echo "Expected: AIM_BASE_URL required"

# Test with environment variable
AIM_BASE_URL=http://test.example.com python -c "from reachy_demo.config import load_settings; s = load_settings(); print(f'Config loaded: {s.aim_base_url}')"

# Test imports
python -c "from reachy_demo.aim.client import AIMClient; from reachy_demo.orchestrator.loop import run_interactive_loop; print('All imports successful')"
```

### Full Integration Test

1. **Set up environment** (Steps 1-2 above)
2. **Configure AIM endpoint** in `.env`
3. **Run the demo** (Step 5 above)
4. **Verify metrics** (Step 6 above)

### Troubleshooting

**Issue: Port conflicts (both AIM and daemon on port 8000)**
- **Problem:** Both AIM endpoint and Reachy daemon default to port 8000
- **Solution:** Use the golden path configuration:
  - Daemon on port 8001: `make sim` (automatically uses `--fastapi-port 8001`)
  - `.env.example` is pre-configured with `REACHY_DAEMON_URL=http://127.0.0.1:8001`
  - AIM endpoint stays on port 8000 (or your configured port)
- **Manual override:** If you need different ports, update `REACHY_DAEMON_URL` in `.env` and run daemon with matching `--fastapi-port`

**Issue: "AIM_BASE_URL is required"**
- Solution: Make sure you've created `.env` from `.env.example` and set `AIM_BASE_URL`

**Issue: "ModuleNotFoundError: No module named 'dotenv'"**
- Solution: Make sure you've activated the virtual environment and run `pip install -e .`

**Issue: "Connection refused" or timeout errors**
- Solution: Verify your `AIM_BASE_URL` is correct and the endpoint is accessible
- Check network connectivity: `curl $AIM_BASE_URL/health` (if health endpoint exists)

**Issue: "Reachy daemon not reachable" warning**
- This is expected if you're not running the daemon. The demo will continue without robot control.

**Issue: "PortAudio library not found" or "OSError: PortAudio library not found"**
- **Solution 1:** Install PortAudio system library:
  ```bash
  # Ubuntu/Debian:
  sudo apt-get update && sudo apt-get install -y portaudio19-dev
  
  # Fedora/RHEL:
  sudo dnf install portaudio-devel
  
  # macOS (Homebrew):
  brew install portaudio
  ```
- **Solution 2:** Run daemon in headless mode (no audio required):
  ```bash
  reachy-mini-daemon --sim --headless
  ```
- **Solution 3:** Skip the daemon entirely - the demo works without it (you'll just see a warning)

**Issue: TTS not working or "No module named 'pyttsx3'"**
- **Solution:** Install Python dependencies:
  ```bash
  pip install -e .
  ```
  This will install `pyttsx3` automatically (it's in `pyproject.toml`)

**Issue: TTS works but no sound (Linux)**
- **Solution:** Install system TTS backend:
  ```bash
  # Ubuntu/Debian:
  sudo apt-get install espeak
  
  # Fedora/RHEL:
  sudo dnf install espeak
  ```
  macOS and Windows have built-in TTS, so no additional install needed.

**Issue: "Read timed out" or "AIM request failed after retries"**
- **Cause:** The AIM endpoint is taking longer than the configured timeout to respond
- **Solution:** Increase `AIM_TIMEOUT_MS` in your `.env` file:
  ```bash
  # Default is 2200ms (2.2 seconds)
  # Increase for slower models or longer responses:
  AIM_TIMEOUT_MS=30000  # 30 seconds
  # Or even longer for complex prompts:
  AIM_TIMEOUT_MS=60000  # 60 seconds
  ```
- **Note:** Restart the application after changing the timeout value

## Cluster Deployment via Helm

This Helm chart is **not for installing a Kubernetes cluster** on your host.
It installs **demo add-ons in your existing Kubernetes cluster** (loadgen, dashboard configmap).

**Chart Mode: URL-only** - The chart uses `aim.baseUrl` to connect to your AIM endpoint. This can be:
- A Kubernetes Service URL (e.g., `http://aim.default.svc.cluster.local:8000`)
- An external URL (e.g., `https://aim.example.com`)
- A port-forward URL (e.g., `http://localhost:8000`)

The chart does **not** deploy or manage the AIM endpoint itself - it only configures the load generator and dashboards to connect to your existing AIM service.

### Prerequisites

- Kubernetes cluster with `kubectl` configured
- `helm` 3.x installed
- Access to the cluster where AIM endpoint is running

### Installation Steps

**Step 1: Update Helm dependencies (if using optional monitoring)**
```bash
cd helm/reachy-demo-addons
helm dependency update
cd ../..
```

**Step 2: Install the chart**
```bash
helm upgrade --install reachy-demo \
  helm/reachy-demo-addons \
  -n reachy-demo \
  --create-namespace \
  --set aim.baseUrl="http://aim.default.svc.cluster.local:8000" \
  --set aim.model="llm-prod"
```

**Customize values:**
- Edit `helm/reachy-demo-addons/values.yaml` or use `--set` flags
- Common customizations:
  - `aim.baseUrl` - Your AIM service URL in cluster
  - `aim.model` - Model name to use
  - `loadgen.schedule` - Cron schedule for load generator
  - `loadgen.concurrency` - Number of concurrent workers

**Step 3: Verify installation**
```bash
# Check resources
kubectl -n reachy-demo get all

# Check CronJob
kubectl -n reachy-demo get cronjob
```

### Trigger Load Generator Manually

The load generator runs on a schedule, but you can trigger it manually:

```bash
# Create a one-off job from the CronJob
kubectl -n reachy-demo create job --from=cronjob/reachy-demo-addons-loadgen reachy-demo-loadgen-manual

# Watch the logs
kubectl -n reachy-demo logs -f job/reachy-demo-loadgen-manual
```

**Expected output:** Statistics showing request count, p50, p95, and mean latency.

## Project Structure

```
reachy-aim-enterprise-demo/
├── src/reachy_demo/          # Main Python package
│   ├── main.py               # CLI entry point
│   ├── config.py             # Configuration management
│   ├── aim/                  # AIM client (OpenAI-compatible)
│   │   ├── client.py         # HTTP client with retries
│   │   ├── models.py         # Pydantic models
│   │   └── errors.py          # Error handling
│   ├── adapters/             # Robot abstraction layer
│   │   ├── robot_base.py     # Abstract base class
│   │   ├── robot_rest.py     # REST adapter (implements health/state)
│   │   └── robot_sim.py      # Simulation mode alias
│   ├── orchestrator/         # Main interaction loop
│   │   ├── loop.py           # Interactive conversation loop
│   │   └── prompts.py        # System prompts
│   ├── obs/                  # Observability
│   │   └── metrics.py        # Prometheus metrics
│   └── tools/                # Utilities
│       └── loadgen_local.py  # Local load generator
├── helm/reachy-demo-addons/  # Kubernetes Helm chart
│   ├── Chart.yaml            # Chart metadata
│   ├── values.yaml           # Default values
│   └── templates/            # Kubernetes manifests
├── tests/                    # Test suite
├── .env.example              # Environment variable template
├── Makefile                  # Convenience commands
├── pyproject.toml            # Python package config
└── README.md                # This file
```

## Implementation Status

✅ **Fully Implemented:**
- AIM client with retry logic and error handling
- Interactive conversation loop with context management
- Prometheus metrics collection and export
- Configuration management with environment variables
- Local and Kubernetes load generators
- Helm charts for cluster deployment
- Robot health checks and state queries
- **Robot gestures** - **Fully functional** gestures implemented via `/api/move/goto` endpoint
  - Works in both simulation and hardware mode
  - Supports: `nod`, `excited`, `thinking`, `greeting`, `happy`, `confused`, `random`, `wake_up`, `goto_sleep`
  - Gestures are automatically selected based on response characteristics for more natural interactions
  - All gestures make real API calls to control head pose, antennas, and body movements
- **Text-to-Speech (TTS)** - **Fully implemented** with automatic fallback
  - Priority 1: Reachy daemon API (if `/api/speak` or similar endpoint available)
  - Priority 2: System TTS (pyttsx3) - offline, cross-platform fallback
  - Automatically detects available method at startup
  - Robot will speak the AIM endpoint's responses

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AIM_BASE_URL` | ✅ Yes | - | AIM endpoint URL (e.g., `http://127.0.0.1:8000`) |
| `AIM_CHAT_PATH` | No | `/v1/chat/completions` | Chat completions API path |
| `AIM_MODEL` | No | `llm-prod` | Model name to use |
| `AIM_API_KEY` | No | - | API key for authentication |
| `AIM_TIMEOUT_MS` | No | `2200` | Request timeout in milliseconds (increase if getting timeout errors, e.g., `30000` for 30 seconds) |
| `AIM_MAX_RETRIES` | No | `1` | Maximum retry attempts |
| `REACHY_DAEMON_URL` | No | `http://127.0.0.1:8001` | Reachy Mini daemon URL (default 8001 to avoid AIM port conflicts) |
| `ROBOT_MODE` | No | `sim` | Robot mode: `sim` or `hardware` |
| `E2E_SLO_MS` | No | `2500` | End-to-end SLO in milliseconds |
| `EDGE_METRICS_HOST` | No | `127.0.0.1` | Metrics server host |
| `EDGE_METRICS_PORT` | No | `9100` | Metrics server port |

## Next Steps When Physical Robot Arrives

1. **Connect to physical robot:**
   ```bash
   # Run daemon with serial port instead of simulation
   reachy-mini-daemon -p /dev/ttyUSB0  # or your serial port
   ```
   The existing gesture implementation will work with the physical robot - no code changes needed!

2. **Customize gestures (optional):**
   - All gestures are already implemented and working in sim mode
   - Current gestures: `nod`, `excited`, `thinking`, `greeting`, `happy`, `confused`, `wake_up`, `goto_sleep`
   - Gestures automatically selected based on response content and timing
   - Add more gestures by extending `gesture()` method in `src/reachy_demo/adapters/robot_rest.py`
   - Use `/api/move/goto` for custom head/body/antenna movements
   - Use `/api/move/play/recorded-move-dataset/{dataset}/{move}` for pre-recorded gestures
   - Modify gesture selection logic in `orchestrator/loop.py` to customize when gestures are triggered

3. **Customize speech (optional):**
   - TTS is already implemented with daemon API + system TTS fallback
   - Robot automatically speaks AIM responses
   - To customize: see `docs/tts-implementation.md` for advanced options (cloud TTS, async, etc.)
   - Current implementation: daemon API (if available) → system TTS (pyttsx3) fallback

## Additional Notes

- **Reachy Mini daemon:** Exposes a REST API (docs at `/docs`). The current adapter implements health checks and state queries. Motion endpoints can be added once validated.
- **AIM API key:** Optional. If required, set `AIM_API_KEY` in `.env` and enable `loadgen.apiKey.enabled=true` in Helm values.
- **Metrics:** Edge metrics are exposed at `http://127.0.0.1:9100/metrics` by default. Use Prometheus to scrape and Grafana to visualize.
- **Load testing:** Both local (`loadgen_local.py`) and Kubernetes (CronJob) load generators are available.

## License

Apache-2.0 (recommended; change as needed).
