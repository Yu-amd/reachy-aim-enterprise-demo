# Latency Budget and Gesture Tiers

## Overview

The enterprise demo uses a **latency-aware gesture policy** that provides immediate feedback and selects appropriate gestures based on measured response latency. This creates a responsive, professional user experience that demonstrates the system's performance characteristics.

## Latency Budget

**Target E2E Latency: 2500ms** (interactive threshold)

### Budget Breakdown

| Component | Budget | Notes |
|-----------|--------|-------|
| **Input capture + prompt build** | 50ms | User input processing, context assembly |
| **Robot state fetch** (optional) | 50-150ms | Current robot pose for gesture planning |
| **Network hop to inference** | | |
|   - Local LMStudio | <10ms | Same machine, minimal latency |
|   - Remote AIM (SSH forward) | 20-50ms | Localhost via SSH tunnel |
|   - Remote AIM (network) | 50-100+ms | Direct network connection |
| **Model response latency** (dominant) | 400-2000+ms | LLM inference time (varies by model/size) |
| **Post-processing + action decision** | 20-50ms | Response parsing, gesture selection |
| **Robot gesture command** | 50-250ms | Daemon API call + motion execution |

### Typical Scenarios

**Fast Response (<800ms):**
- Local small model (e.g., 1-3B parameters)
- Cached/prompted responses
- Minimal network latency

**Normal Response (800-2500ms):**
- Medium models (e.g., 7-13B parameters)
- Standard network conditions
- Typical production scenario

**Slow Response (>2500ms):**
- Large models (e.g., 20B+ parameters)
- Network congestion
- Complex prompts requiring longer reasoning

## Gesture Tiers

The system uses **3 latency tiers** plus an error state:

### Tier 0: Fast Response (<800ms)
**Gesture**: `nod_fast`  
**Behavior**: Quick, confident nod  
**Message**: "Response received quickly, system is responsive"

### Tier 1: Normal Response (800-2500ms)
**Gesture**: `nod_tilt`  
**Behavior**: Nod with slight head tilt  
**Message**: "Normal processing time, engaged and attentive"

### Tier 2: Slow Response (>2500ms, SLO Miss)
**Gesture**: `thinking_done`  
**Behavior**: Slow head pan indicating processing completed  
**Message**: "Response took longer than target, but completed"

### Error State
**Gesture**: `error`  
**Behavior**: Head shake + slight head down (sad posture)  
**Message**: "Backend unavailable or request failed"

## Immediate Feedback

**Pre-Gesture**: `ack` (acknowledgment)  
**Timing**: Shown immediately when user presses Enter (<100ms)  
**Purpose**: Provides instant feedback that the system is processing the request

## Control Flow

```
User presses Enter
    ↓
[Immediate] robot.gesture("ack")  ← Instant feedback
    ↓
Start E2E timer (t0)
    ↓
Call AIM/LLM endpoint
    ↓
Record AIM latency (t1 → t2)
    ↓
Calculate E2E latency (t0 → now)
    ↓
Select post-gesture based on:
  - Success/failure status
  - E2E latency tier
    ↓
robot.gesture(post_gesture)
robot.speak(response_text)
```

## Metrics

The system exposes the following metrics for monitoring and Grafana dashboards:

### Latency Metrics
- `edge_e2e_ms` (histogram): End-to-end latency distribution
- `aim_call_ms` (histogram): AIM/LLM call latency distribution
- `edge_slo_miss_total` (counter): Count of SLO violations (>2500ms)

### Gesture Metrics
- `gesture_selected_total{gesture="ack"}` (counter): Immediate feedback gestures
- `gesture_selected_total{gesture="nod_fast"}` (counter): Fast response gestures
- `gesture_selected_total{gesture="nod_tilt"}` (counter): Normal response gestures
- `gesture_selected_total{gesture="thinking_done"}` (counter): Slow response gestures
- `gesture_selected_total{gesture="error"}` (counter): Error gestures

### Failure Metrics
- `backend_failures_total` (counter): Total backend/inference failures
- `edge_errors_total` (counter): Total errors in edge client

## Grafana Dashboard Queries

### Latency Percentiles
```promql
# P50 E2E latency
histogram_quantile(0.50, sum(rate(edge_e2e_ms_bucket[5m])) by (le))

# P95 E2E latency
histogram_quantile(0.95, sum(rate(edge_e2e_ms_bucket[5m])) by (le))

# P99 E2E latency
histogram_quantile(0.99, sum(rate(edge_e2e_ms_bucket[5m])) by (le))
```

### SLO Compliance
```promql
# SLO compliance rate (target: >95% under 2500ms)
1 - (sum(rate(edge_slo_miss_total[5m])) / sum(rate(edge_requests_total[5m])))
```

### Gesture Distribution
```promql
# Gesture selection distribution
sum(rate(gesture_selected_total[5m])) by (gesture)
```

### Backend Health
```promql
# Backend failure rate
sum(rate(backend_failures_total[5m])) / sum(rate(edge_requests_total[5m]))
```

## Implementation Details

### Policy Module
- **Location**: `src/reachy_demo/policy/latency_policy.py`
- **Class**: `LatencyPolicy`
- **Methods**:
  - `choose_pre_gesture()`: Returns "ack" for immediate feedback
  - `choose_post_gesture(aim_ms, e2e_ms, ok)`: Selects gesture based on latency and status
  - `get_latency_tier(e2e_ms)`: Returns tier number (0, 1, or 2)

### Gesture Implementations
- **Location**: `src/reachy_demo/adapters/robot_rest.py`
- **Methods**:
  - `_ack_gesture()`: Very quick nod (<100ms)
  - `_nod_fast_gesture()`: Quick nod for fast responses
  - `_nod_tilt_gesture()`: Nod with tilt for normal responses
  - `_thinking_done_gesture()`: Slow pan for slow responses
  - `_error_gesture()`: Shake + sad posture for errors

### Orchestrator Loop
- **Location**: `src/reachy_demo/orchestrator/loop.py`
- **Flow**: Immediate feedback → Inference → Latency-aware gesture → TTS
- **Metrics**: All metrics recorded with proper labels

## Benefits

1. **Immediate Feedback**: Users see instant acknowledgment (<100ms)
2. **Latency Transparency**: Gestures reflect actual system performance
3. **SLO Visibility**: Slow responses are visually distinct
4. **Error Communication**: Failures are clearly indicated
5. **Metrics-Driven**: Grafana dashboards tell the performance story

## Customization

### Adjust Tier Thresholds

Edit `src/reachy_demo/policy/latency_policy.py`:

```python
TIER_0_THRESHOLD = 800   # Fast response threshold
TIER_1_THRESHOLD = 2500  # Normal response threshold (SLO target)
```

### Customize Gestures

Edit gesture implementations in `src/reachy_demo/adapters/robot_rest.py`:
- Modify timing, angles, or sequences
- Add new gesture variations
- Adjust for different robot capabilities

### Change SLO Target

Edit `.env` or `config.py`:

```bash
E2E_SLO_MS=3000  # 3 second target instead of 2.5
```

## Testing

Test different latency scenarios:

```bash
# Fast response (local small model)
AIM_BASE_URL=http://localhost:1234  # LMStudio with small model

# Normal response (medium model)
AIM_BASE_URL=http://localhost:1234  # LMStudio with 7B model

# Slow response (large model or network delay)
AIM_BASE_URL=http://remote-aim:8000  # Large model or add artificial delay
```

Observe how gestures change based on actual measured latency!

