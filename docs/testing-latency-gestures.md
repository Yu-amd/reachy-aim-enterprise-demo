# Testing Latency-Aware Gestures

## Quick Test

Run the test script to verify the policy logic:

```bash
source .venv/bin/activate
python src/reachy_demo/tools/test_latency_gestures.py
```

This will test the latency policy with various scenarios and show which gestures are selected.

## Testing with Real Demo

### Step 1: Start the Demo

**Terminal 1 - Start daemon:**
```bash
# Simulation mode
make sim

# OR hardware mode (if robot connected)
reachy-mini-daemon -p /dev/ttyACM0 --fastapi-port 8001
```

**Terminal 2 - Run demo:**
```bash
make run
```

### Step 2: Observe Immediate Feedback

When you type a question and press Enter, you should see:
- **Immediate gesture**: Robot performs a quick `ack` nod (<100ms)
- This provides instant feedback that the system is processing

### Step 3: Observe Post-Gesture Based on Latency

After the LLM responds, the robot will perform a gesture based on the measured latency:

#### Fast Response (<800ms)
- **Gesture**: `nod_fast` - Quick, confident nod
- **When**: Small models, cached responses, very fast inference
- **Test**: Use a small model in LMStudio or ask a simple question

#### Normal Response (800-2500ms)
- **Gesture**: `nod_tilt` - Nod with slight head tilt
- **When**: Medium models (7-13B), typical production scenario
- **Test**: Use a medium model, ask normal questions

#### Slow Response (>2500ms)
- **Gesture**: `thinking_done` - Slow head pan
- **When**: Large models, network delays, complex prompts
- **Test**: Use a large model or add artificial delay

#### Error Response
- **Gesture**: `error` - Head shake + sad posture
- **When**: Backend unavailable, network errors, timeout
- **Test**: Stop LMStudio or disconnect network

### Step 4: Check Metrics

View the metrics to see gesture selection:

```bash
# View all metrics
curl http://127.0.0.1:9100/metrics

# Filter for gesture metrics
curl http://127.0.0.1:9100/metrics | grep gesture_selected

# Filter for latency metrics
curl http://127.0.0.1:9100/metrics | grep -E "edge_e2e_ms|aim_call_ms|slo_miss"
```

Example output:
```
gesture_selected_total{gesture="ack"} 5.0
gesture_selected_total{gesture="nod_fast"} 2.0
gesture_selected_total{gesture="nod_tilt"} 3.0
gesture_selected_total{gesture="thinking_done"} 0.0
gesture_selected_total{gesture="error"} 0.0
```

### Step 5: Test Different Scenarios

#### Scenario 1: Fast Response
```bash
# Use small model in LMStudio
# Ask simple question: "Hello"
# Expected: ack → nod_fast
```

#### Scenario 2: Normal Response
```bash
# Use medium model (7-13B)
# Ask normal question: "What is machine learning?"
# Expected: ack → nod_tilt
```

#### Scenario 3: Slow Response
```bash
# Use large model (20B+)
# Ask complex question: "Explain quantum computing in detail"
# Expected: ack → thinking_done
```

#### Scenario 4: Error
```bash
# Stop LMStudio or set wrong URL
# Ask any question
# Expected: ack → error
# Robot speaks: "Sorry, my inference backend is unavailable."
```

## What to Look For

### Immediate Feedback
- ✅ Robot nods **immediately** when you press Enter (<100ms)
- ✅ This happens **before** the LLM call starts
- ✅ Provides instant acknowledgment

### Latency Reflection
- ✅ Gesture changes based on **actual measured latency**
- ✅ Fast responses → quick nod
- ✅ Normal responses → nod with tilt
- ✅ Slow responses → thinking gesture
- ✅ Errors → error gesture

### Metrics
- ✅ `gesture_selected_total` counters increment
- ✅ `edge_e2e_ms` histogram shows latency distribution
- ✅ `edge_slo_miss_total` increments for slow responses (>2500ms)
- ✅ `backend_failures_total` increments on errors

## Verification Checklist

- [ ] Immediate `ack` gesture appears when pressing Enter
- [ ] Post-gesture matches latency tier:
  - [ ] Fast (<800ms) → `nod_fast`
  - [ ] Normal (800-2500ms) → `nod_tilt`
  - [ ] Slow (>2500ms) → `thinking_done`
  - [ ] Error → `error`
- [ ] Metrics are recorded correctly
- [ ] Console shows latency tier in subtitle
- [ ] Robot speaks the response (or error message)

## Console Output

You should see output like:

```
AIM (mistralai/Mistral-Small-3.2-24B-Instruct-2506)
aim_call=1200ms  e2e=1500ms  slo=2500ms  tier=1
```

The `tier=1` indicates Tier 1 (normal response), which should trigger `nod_tilt`.

## Troubleshooting

### No immediate gesture
- Check robot daemon is running
- Check robot health: `curl http://127.0.0.1:8001/api/state/full`
- Check logs for gesture errors

### Wrong gesture selected
- Check actual latency in console output
- Verify tier thresholds in policy
- Check metrics: `curl http://127.0.0.1:9100/metrics | grep gesture_selected`

### Gestures not working
- Verify daemon is reachable
- Check robot mode in `.env`: `ROBOT_MODE=sim` or `ROBOT_MODE=hardware`
- Test gesture directly: `curl -X POST http://127.0.0.1:8001/api/move/goto ...`

## Advanced Testing

### Test with Artificial Delays

You can test different latency tiers by adding delays:

```python
# In your test, add sleep to simulate latency
import time
time.sleep(0.5)  # 500ms - should trigger nod_fast
time.sleep(1.5)  # 1500ms - should trigger nod_tilt
time.sleep(3.0)  # 3000ms - should trigger thinking_done
```

### Monitor Metrics in Real-Time

```bash
# Watch metrics update
watch -n 1 'curl -s http://127.0.0.1:9100/metrics | grep -E "gesture_selected|edge_e2e_ms_bucket"'
```

## Expected Behavior Summary

| Latency | Pre-Gesture | Post-Gesture | Metrics |
|---------|-------------|--------------|---------|
| Any | `ack` (immediate) | Based on tier | `gesture_selected{gesture="ack"}` |
| <800ms | `ack` | `nod_fast` | `gesture_selected{gesture="nod_fast"}` |
| 800-2500ms | `ack` | `nod_tilt` | `gesture_selected{gesture="nod_tilt"}` |
| >2500ms | `ack` | `thinking_done` | `gesture_selected{gesture="thinking_done"}`, `slo_miss++` |
| Error | `ack` | `error` | `gesture_selected{gesture="error"}`, `backend_failures++` |

