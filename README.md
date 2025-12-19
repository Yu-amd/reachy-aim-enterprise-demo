# Reachy Mini Lite + AMD Inference Microservice (AIM) Enterprise Demo

This repo provides a fully functional enterprise demo that connects a Reachy Mini robot to an AMD Inference Microservice (AIM) endpoint. You can run it without the physical robot using the Reachy Mini daemon simulation, while targeting a real OpenAI-compatible AIM endpoint (e.g., running on MI300X in your datacenter), or alocal LLM endpoint.

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

### Mode A: Local LMStudio (Recommended for Quick Start)
- **LLM Endpoint**: LMStudio running locally on your laptop
- **Port**: LMStudio defaults to `:1234`
- **Reachy Daemon**: Runs on port `:8001` (to avoid conflicts)
- **Use Case**: Quick local testing, development, demos
- **Setup**: Just start LMStudio, then run the demo

### Mode B: Remote AIM Endpoint (Production)
- **LLM Endpoint**: AIM running in Kubernetes cluster (MI300X datacenter)
- **Port**: AIM typically on `:8000` (via SSH port forward or ingress)
- **Reachy Daemon**: Runs on port `:8001` (to avoid conflicts)
- **Use Case**: Production-like setup, real inference hardware
- **Setup**: Requires cluster access and SSH port forwarding

## Quick Start Guide (Golden Path)

### Prerequisites
- Python 3.10+
- LMStudio installed and running (Mode A) OR access to AIM endpoint (Mode B)
- Reachy Mini daemon installed (`pip install reachy-mini[mujoco]`)

### Port Rules
- **LMStudio**: Default port `:1234`
- **AIM Endpoint**: Default port `:8000` (or configured port)
- **Reachy Daemon**: Uses port `:8001` (avoids conflicts with LLM endpoints)
- **Metrics**: Port `:9100` (Prometheus metrics)

### Step-by-Step Setup

**1. One-time setup:**
```bash
make install
cp .env.example .env
```

**2. Configure `.env` file:**
```bash
# For Mode A (LMStudio local):
AIM_BASE_URL=http://localhost:1234

# For Mode B (AIM remote via SSH port forward):
AIM_BASE_URL=http://127.0.0.1:8000
```

**3. Start the demo (two terminals):**

**Terminal 1 - Start Reachy daemon:**
```bash
# For hardware robot:
reachy-mini-daemon -p /dev/ttyACM0 --fastapi-port 8001

# OR for simulation:
make sim
```

**Terminal 2 - Run demo app:**
```bash
make run
```

That's it! The demo will:
- Connect to your LLM endpoint (LMStudio or AIM)
- Control the robot (gestures + speech)
- Display metrics at `http://127.0.0.1:9100/metrics`

**Note:** The `.env.example` is pre-configured with `REACHY_DAEMON_URL=http://127.0.0.1:8001` to match the daemon port.

### Direct Robot Commands

You can control the robot directly without going through the LLM by using the `cmd:` prefix:

- `cmd:gesture <name>` - Execute a gesture directly (e.g., `cmd:gesture nod`)
- `cmd:reset` - Reset robot to home position
- `cmd:calibrate` - Calibrate current position as home
- `cmd:state` - Show current robot state
- `cmd:help` - Show all available commands

See [docs/direct-commands.md](docs/direct-commands.md) for full documentation.

## Demo Narrative

This demo showcases an enterprise edge-to-cloud AI architecture:

- Reachy Mini is the edge client (I/O interface) - handles user interaction and robot control
- AIM (AMD Inference Microservice) is the inference API (OpenAI-compatible) - runs LLM inference in your datacenter
- Kubernetes add-ons provide repeatability - load generator and Grafana dashboards for monitoring

The architecture separates concerns: edge handles I/O and latency-sensitive robot control, while cloud handles compute-intensive LLM inference. This enables real-time robot interactions powered by large language models.

## What you get
- Edge client (runs on your laptop or desktop): CLI orchestrator + AIM client + Prometheus metrics
- Reachy Mini integration via daemon URL (simulation-friendly, ready for hardware)
- Helm chart (`helm/reachy-demo-addons`) for cluster-side demo add-ons:
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
  - Linux: `espeak` or `espeak-ng` (usually pre-installed, or `sudo apt-get install espeak`)
  - macOS: Built-in TTS (no additional install needed)
  - Windows: SAPI5 (built-in, no additional install needed)

## Step-by-step Guide

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

Verify installation:
```bash
# Check that the command is available
python -m reachy_demo.main --help
```

### Step 2: Deploy LLM Endpoint

Before configuring the edge client, you need an OpenAI-compatible LLM endpoint. Choose based on your setup:

#### Option A: Remote AIM Endpoint (Mode A - Enterprise-Ready)

For production setups with Instinct GPU hardware, deploy AIM in your cluster:

```bash
# Clone the AIM-demo repository
git clone https://github.com/Yu-amd/AIM-demo.git
cd AIM-demo

# Follow the Docker deployment instructions in that repository
# Deploy to cluster with Instinct GPUs (MI300X)
```

**Note**: AIM (AMD Inference Microservice) requires Instinct GPU hardware and is typically deployed in a datacenter/cluster environment, not locally.

Verify the AIM endpoint:
```bash
# If using SSH port forward: ssh -L 8000:localhost:8000 user@cluster-host
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/docs
```

#### Option B: Local LLM Endpoint (Mode B - Local Development)

For local development/testing without Instinct GPUs, use an OpenAI-compatible local LLM:

Ollama:
```bash
# Install Ollama: https://ollama.ai
ollama serve  # Runs on http://localhost:11434 by default

# Pull a model
ollama pull llama2

# Ollama uses /api/chat endpoint, configure AIM_BASE_URL=http://localhost:11434
# and AIM_CHAT_PATH=/api/chat in .env
```

LMStudio:
```bash
# Install LMStudio: https://lmstudio.ai
# Start LMStudio server (usually http://localhost:1234 or network )
# Configure AIM_BASE_URL=http://localhost:1234 in .env
```

Custom OpenAI-compatible endpoint:
- Any endpoint that implements the OpenAI chat completions API
- Set `AIM_BASE_URL` and `AIM_CHAT_PATH` accordingly

Verify local endpoint:
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
  - Default (recommended): `http://127.0.0.1:8001` (avoids AIM port conflicts)
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

Start the daemon in simulation mode:

```bash
# Standard mode (requires PortAudio) - default port 8000
reachy-mini-daemon --sim

# OR headless mode (no audio, no GUI - recommended if you don't need audio)
reachy-mini-daemon --sim --headless

# OR if port 8000 is already in use (e.g., SSH port forward), use a different port:
reachy-mini-daemon --sim --headless --fastapi-port 8001
```

Verify daemon is running:
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
   - Speak the response using TTS (daemon API or system TTS)

Example interaction:
```
You> What is machine learning?
[AIM response appears in a panel with latency metrics]
[Robot performs a gesture - e.g., "thinking" for questions, "excited" for positive responses]
[Robot speaks the response using TTS]
```

**To exit:** Press `Ctrl+C`

### Robot Gestures and Speech in Sim Mode

The demo includes fully implemented robot gestures and text-to-speech that work in both simulation and hardware mode. Gestures are automatically selected based on the AIM response characteristics, and the robot will speak the AIM endpoint's responses.

Available Gestures:
- `nod` - Simple head nod (pitch down then back up)
- `excited` - Antennas wiggle rapidly with head bobs (for positive/enthusiastic responses)
- `thinking` - Head tilts side to side (for questions or processing)
- `greeting` - Friendly nod with antennas raised (for short responses)
- `happy` - Bouncy antennas with head bob (for fast, positive responses)
- `confused` - Head shakes side to side (for uncertainty or longer responses)
- `wake_up` - Wake up animation (uses daemon's built-in animation)
- `goto_sleep` - Sleep animation (uses daemon's built-in animation)

Gesture Selection Logic:
- Questions (responses containing "?") → `thinking`
- Positive keywords ("great", "excellent") → `excited`
- Short responses (< 10 words) → `greeting`
- Fast responses (< 500ms) → `happy`
- Otherwise → Random selection from `nod`, `thinking`, `confused`

All gestures use the Reachy Mini daemon's `/api/move/goto` endpoint to control head pose (pitch, yaw, roll), antennas, and body yaw. The gestures are smooth and expressive, making the robot interaction feel natural even in simulation mode.

Text-to-Speech:
- The robot will speak the AIM endpoint's responses automatically
- TTS method is auto-detected: tries daemon API first (`/api/speak`, `/api/tts`, etc.), falls back to system TTS (pyttsx3)
- In sim mode: Typically uses system TTS (pyttsx3) which plays through your computer's speakers
- In hardware mode: Will use daemon API if available (robot's speakers), otherwise falls back to system TTS
- System TTS works offline and cross-platform (Windows, Linux, macOS)
- You'll see a startup message indicating which TTS method is being used (e.g., `✓ TTS: Using system TTS (pyttsx3)`)

### Step 6: (Optional) Check Prometheus metrics

While the demo is running, you can view metrics in another terminal:

```bash
# View metrics endpoint
curl http://127.0.0.1:9100/metrics
```

Or open in browser: http://127.0.0.1:9100/metrics

Available metrics:
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

For detailed Docker deployment instructions, see Step 2 in the [Quick Start Guide](#Quick-Start-Guide-Recommended-for-testing-without-a-robot) above.

Quick reference:
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

### Troubleshooting

Issue: Port conflicts (both AIM and daemon on port 8000)
- Problem: Both AIM endpoint and Reachy daemon default to port 8000
- Solution: Use the golden path configuration:
  - Daemon on port 8001: `make sim` (automatically uses `--fastapi-port 8001`)
  - `.env.example` is pre-configured with `REACHY_DAEMON_URL=http://127.0.0.1:8001`
  - AIM endpoint stays on port 8000 (or your configured port)
- Manual override: If you need different ports, update `REACHY_DAEMON_URL` in `.env` and run daemon with matching `--fastapi-port`

Issue: "AIM_BASE_URL is required"
- Solution: Make sure you've created `.env` from `.env.example` and set `AIM_BASE_URL`

Issue: "ModuleNotFoundError: No module named 'dotenv'"
- Solution: Make sure you've activated the virtual environment and run `pip install -e .`

Issue: "Connection refused" or timeout errors
- Solution: Verify your `AIM_BASE_URL` is correct and the endpoint is accessible
- Check network connectivity:
  ```bash
  # Test if endpoint is reachable
  curl $AIM_BASE_URL/health  # If health endpoint exists
  
  # For LMStudio, test the chat endpoint directly:
  curl -X POST http://localhost:1234/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "test", "messages": [{"role": "user", "content": "hi"}]}'
  ```
- LMStudio-specific: 
  - Ensure LMStudio server is running (check the LMStudio UI)
  - Verify a model is loaded in LMStudio
  - If using a network IP, check firewall settings
  - LMStudio default port is 1234, but it may be different - check LMStudio settings

Issue: "Reachy daemon not reachable" warning
- This is expected if you're not running the daemon. The demo will continue without robot control.

Issue: "PortAudio library not found" or "OSError: PortAudio library not found"
- Solution 1: Install PortAudio system library:
  ```bash
  # Ubuntu/Debian:
  sudo apt-get update && sudo apt-get install -y portaudio19-dev
  
  # Fedora/RHEL:
  sudo dnf install portaudio-devel
  
  # macOS (Homebrew):
  brew install portaudio
  ```
- Solution 2: Run daemon in headless mode (no audio required):
  ```bash
  reachy-mini-daemon --sim --headless
  ```
- Solution 3: Skip the daemon entirely - the demo works without it (you'll just see a warning)

Issue: TTS not working or "No module named 'pyttsx3'"
- Solution: Install Python dependencies:
  ```bash
  pip install -e .
  ```
  This will install `pyttsx3` automatically (it's in `pyproject.toml`)

Issue: TTS works but no sound (Linux)
- Solution: Install system TTS backend:
  ```bash
  # Ubuntu/Debian:
  sudo apt-get install espeak
  
  # Fedora/RHEL:
  sudo dnf install espeak
  ```
  macOS and Windows have built-in TTS, so no additional install needed.

Issue: "Read timed out" or "AIM request failed after retries"
- Cause: The LLM endpoint is taking longer than the configured timeout to respond
- Common with local LLMs (Ollama, LMStudio): Local models often need 10-60 seconds for inference, especially on first request
- Solution: Increase `AIM_TIMEOUT_MS` in your `.env` file:
  ```bash
  # Default is now 30000ms (30 seconds)
  # For slower models or longer responses, increase further:
  AIM_TIMEOUT_MS=60000  # 60 seconds
  # For very slow models or complex prompts:
  AIM_TIMEOUT_MS=120000  # 2 minutes
  ```
- LMStudio-specific:
  - Ensure LMStudio server is running and a model is loaded
  - Check that the server is accessible: `curl http://localhost:1234/v1/chat/completions`
  - First request may be slower (model loading), subsequent requests should be faster
  - If using LMStudio on a network IP (e.g., `192.168.1.131:1234`), ensure firewall allows connections
- **Note:** Restart the application after changing the timeout value

## Cluster Deployment via Helm

This Helm chart is not for installing a Kubernetes cluster on your host. It installs demo add-ons in your existing Kubernetes cluster (loadgen, dashboard configmap).

Chart Mode: URL-only - The chart uses `aim.baseUrl` to connect to your AIM endpoint. This can be:
- A Kubernetes Service URL (e.g., `http://aim.default.svc.cluster.local:8000`)
- An external URL (e.g., `https://aim.example.com`)
- A port-forward URL (e.g., `http://localhost:8000`)

The chart does not deploy or manage the AIM endpoint itself - it only configures the load generator and dashboards to connect to your existing AIM service.

### Prerequisites

- Kubernetes cluster with `kubectl` configured
- `helm` 3.x installed
- Access to the cluster where AIM endpoint is running
- AIM endpoint already deployed and accessible (Docker deployment or Kubernetes service)

### Installation Steps

Step 1: Update Helm dependencies (if using optional monitoring)
```bash
cd helm/reachy-demo-addons
helm dependency update
cd ../..
```

Step 2: Determine your AIM endpoint URL

Before installing, identify how to reach your AIM endpoint from within the cluster:

- If AIM is deployed in Kubernetes: Use the Service URL (e.g., `http://aim.default.svc.cluster.local:8000`)
- If AIM is deployed via Docker on a remote node: Use the node's IP or hostname (e.g., `http://192.168.1.100:8000`)
- If AIM is external: Use the external URL (e.g., `https://aim.example.com`)

Step 3: Install the chart

For AIM deployed in Kubernetes (same cluster):
```bash
helm upgrade --install reachy-demo \
  helm/reachy-demo-addons \
  -n reachy-demo \
  --create-namespace \
  --set aim.baseUrl="http://aim.default.svc.cluster.local:8000" \
  --set aim.model="llm-prod"
```

For AIM deployed via Docker on remote node:
```bash
helm upgrade --install reachy-demo \
  helm/reachy-demo-addons \
  -n reachy-demo \
  --create-namespace \
  --set aim.baseUrl="http://<remote-node-ip>:8000" \
  --set aim.model="llm-prod" \
  --set loadgen.timeoutSeconds=60
```

**Note:** If your AIM endpoint takes longer than 30 seconds to respond, increase `loadgen.timeoutSeconds` (default is 30s, matching edge client default).

Step 4: Verify installation
```bash
# Check resources
kubectl -n reachy-demo get all

# Check CronJob
kubectl -n reachy-demo get cronjob

# Check ConfigMaps
kubectl -n reachy-demo get configmap
```

Step 5: Test the load generator

Trigger a manual test run:
```bash
# Create a one-off job from the CronJob
kubectl -n reachy-demo create job --from=cronjob/reachy-demo-addons-loadgen reachy-demo-loadgen-manual

# Watch the logs (wait for job to start)
kubectl -n reachy-demo wait --for=condition=ready pod -l job-name=reachy-demo-loadgen-manual --timeout=60s
kubectl -n reachy-demo logs -f job/reachy-demo-loadgen-manual
```

Expected output:
```
requests=120 successful, 0 errors, p50=450ms p95=1200ms mean=550ms url=http://aim.default.svc.cluster.local:8000/v1/chat/completions
```

Step 6: Check job status
```bash
# View job details
kubectl -n reachy-demo describe job reachy-demo-loadgen-manual

# Check if job completed successfully
kubectl -n reachy-demo get job reachy-demo-loadgen-manual
```

### Customization

Edit `helm/reachy-demo-addons/values.yaml` or use `--set` flags:

Common customizations:
- `aim.baseUrl` - Your AIM service URL (required)
- `aim.model` - Model name to use (default: `llm-prod`)
- `aim.chatPath` - Chat completions path (default: `/v1/chat/completions`)
- `loadgen.schedule` - Cron schedule (default: `*/30 * * * *` - every 30 minutes)
- `loadgen.concurrency` - Number of concurrent workers (default: `8`)
- `loadgen.durationSeconds` - Test duration (default: `60`)
- `loadgen.timeoutSeconds` - Request timeout (default: `30`, increase if AIM is slow)
- `loadgen.qpsPerWorker` - Requests per second per worker (default: `1`)

Example with custom values:
```bash
helm upgrade --install reachy-demo \
  helm/reachy-demo-addons \
  -n reachy-demo \
  --create-namespace \
  --set aim.baseUrl="http://aim.default.svc.cluster.local:8000" \
  --set loadgen.concurrency=16 \
  --set loadgen.durationSeconds=120 \
  --set loadgen.timeoutSeconds=60
```

### Troubleshooting Kubernetes Deployment

Issue: Job fails with "No successful requests"
- Check AIM endpoint accessibility: Verify the `aim.baseUrl` is correct and reachable from within the cluster
- Check network policies: Ensure pods can reach the AIM endpoint
- Check timeout: Increase `loadgen.timeoutSeconds` if AIM responses are slow
- Check logs: `kubectl -n reachy-demo logs job/reachy-demo-loadgen-manual` for detailed errors

Issue: "Connection refused" or timeout errors
- For remote Docker deployment: Ensure the AIM endpoint is accessible from cluster nodes (check firewall, network routing)
- For Kubernetes Service: Verify the Service exists and has correct selectors: `kubectl get svc -n <aim-namespace>`
- Test connectivity: Run a test pod: `kubectl run -it --rm test-pod --image=curlimages/curl --restart=Never -- curl http://aim.default.svc.cluster.local:8000/health`

Issue: CronJob not running
- Check schedule: Verify the cron schedule is correct: `kubectl -n reachy-demo get cronjob -o yaml`
- Check CronJob status: `kubectl -n reachy-demo describe cronjob reachy-demo-addons-loadgen`
- Check recent jobs: `kubectl -n reachy-demo get jobs`

Issue: ConfigMap not found
- Verify ConfigMap exists: `kubectl -n reachy-demo get configmap reachy-demo-addons-prompts`
- Check volume mount: Verify the volume mount in the CronJob template matches the ConfigMap name

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

Fully Implemented:
- AIM client with retry logic and error handling
- Interactive conversation loop with context management
- Prometheus metrics collection and export
- Configuration management with environment variables
- Local and Kubernetes load generators
- Helm charts for cluster deployment
- Robot health checks and state queries
- Robot gestures - Fully functional gestures implemented via `/api/move/goto` endpoint
  - Works in both simulation and hardware mode
  - Supports: `nod`, `excited`, `thinking`, `greeting`, `happy`, `confused`, `random`, `wake_up`, `goto_sleep`
  - Gestures are automatically selected based on response characteristics for more natural interactions
  - All gestures make real API calls to control head pose, antennas, and body movements
- Text-to-Speech (TTS) - Fully implemented with automatic fallback
  - Priority 1: Reachy daemon API (if `/api/speak` or similar endpoint available)
  - Priority 2: System TTS (pyttsx3) - offline, cross-platform fallback
  - Automatically detects available method at startup
  - Robot will speak the AIM endpoint's responses

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AIM_BASE_URL` | **Yes** | - | AIM endpoint URL (e.g., `http://127.0.0.1:8000`) |
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

## Connect to a Physical Robot

1. Connect to physical robot:
   ```bash
   # Run daemon with serial port instead of simulation
   reachy-mini-daemon -p /dev/ttyUSB0  # or your serial port
   ```
   The existing gesture implementation will work with the physical robot - no code changes needed!

2. Customize gestures (optional):
   - All gestures are already implemented and working in sim mode
   - Current gestures: `nod`, `excited`, `thinking`, `greeting`, `happy`, `confused`, `wake_up`, `goto_sleep`
   - Gestures automatically selected based on response content and timing
   - Add more gestures by extending `gesture()` method in `src/reachy_demo/adapters/robot_rest.py`
   - Use `/api/move/goto` for custom head/body/antenna movements
   - Use `/api/move/play/recorded-move-dataset/{dataset}/{move}` for pre-recorded gestures
   - Modify gesture selection logic in `orchestrator/loop.py` to customize when gestures are triggered

3. Customize speech (optional):
   - TTS is already implemented with daemon API + system TTS fallback
   - Robot automatically speaks AIM responses
   - To customize: see `docs/tts-implementation.md` for advanced options (cloud TTS, async, etc.)
   - Current implementation: daemon API (if available) → system TTS (pyttsx3) fallback

## Additional Notes

- Reachy Mini daemon: Exposes a REST API (docs at `/docs`). The current adapter implements health checks and state queries. Motion endpoints can be added once validated.
- AIM API key: Optional. If required, set `AIM_API_KEY` in `.env` and enable `loadgen.apiKey.enabled=true` in Helm values.
- Metrics: Edge metrics are exposed at `http://127.0.0.1:9100/metrics` by default. Use Prometheus to scrape and Grafana to visualize.
- Load testing: Both local (`loadgen_local.py`) and Kubernetes (CronJob) load generators are available.

## License

Apache-2.0.
