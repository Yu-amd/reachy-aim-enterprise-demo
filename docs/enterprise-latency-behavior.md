# Enterprise Latency-Aware Behavior

This demo implements **enterprise-grade latency-aware behavior** that provides immediate feedback and appropriate gestures based on response latency, making it production-ready rather than a toy.

## Latency Tiers

The system automatically selects gestures based on measured end-to-end latency:

### Tier 0: Fast Response (<800ms)
- **Pre-gesture**: `ack` - Immediate acknowledgment
- **Post-gesture**: `nod_fast` - Quick nod
- **Behavior**: Fast, confident response

### Tier 1: Normal Response (800-2500ms)
- **Pre-gesture**: `ack` - Immediate acknowledgment
- **Post-gesture**: `nod_tilt` - Engaged nod with head tilt
- **Behavior**: Normal, engaged response within SLO

### Tier 2: Slow Response (>2500ms)
- **Pre-gesture**: `ack` - Immediate acknowledgment
- **Post-gesture**: `thinking_done` - "Thinking hold" then done gesture
- **Behavior**: Indicates processing took longer than SLO

### Error State
- **Pre-gesture**: `ack` - Immediate acknowledgment
- **Post-gesture**: `error` - Shake/no or sad posture
- **Behavior**: Indicates inference backend failure

## Enterprise Metrics

All metrics are exposed at `http://127.0.0.1:9100/metrics` (Prometheus format):

### `llm_call_ms` (Histogram)
- **Description**: Latency of LLM inference call in milliseconds
- **Buckets**: 50, 100, 200, 400, 800, 1200, 2000, 3000, 5000, 8000
- **Use Case**: Track LLM performance, identify slow models

### `edge_e2e_ms` (Histogram)
- **Description**: End-to-end latency from user input to response in milliseconds
- **Buckets**: 50, 100, 200, 400, 800, 1200, 2000, 3000, 5000, 8000
- **Use Case**: Track overall system performance, SLO monitoring

### `gesture_selected_total{gesture="..."}` (Counter)
- **Description**: Total gestures selected by latency policy
- **Labels**: `gesture` (e.g., "ack", "nod_fast", "nod_tilt", "thinking_done", "error")
- **Use Case**: Track gesture distribution, understand user experience patterns

### `backend_failures_total` (Counter)
- **Description**: Total backend/inference failures
- **Use Case**: Track system reliability, identify backend issues

### Additional Metrics (for completeness)
- `edge_requests_total` - Total requests handled
- `edge_errors_total` - Total errors in edge client
- `edge_slo_miss_total` - Count of e2e latency SLO misses
- `aim_call_ms` - Alias for `llm_call_ms` (backward compatibility)

## How It Works

1. **User Input**: User types a message and presses Enter
2. **Immediate Feedback**: `ack` gesture is shown instantly (provides immediate feedback)
3. **Thinking Pose**: Body and head turn 90° to indicate processing
4. **LLM Call**: Request sent to inference endpoint, latency measured
5. **Return from Thinking**: Body and head return to neutral
6. **Latency-Based Gesture**: Post-gesture selected based on measured latency
7. **Speech**: Robot speaks the response with speech-synced motion
8. **Reset**: Robot returns to neutral position

## Example Metrics Output

```prometheus
# LLM call latency
llm_call_ms_bucket{le="800"} 45
llm_call_ms_bucket{le="1200"} 78
llm_call_ms_sum 125000
llm_call_ms_count 100

# End-to-end latency
edge_e2e_ms_bucket{le="2500"} 92
edge_e2e_ms_sum 180000
edge_e2e_ms_count 100

# Gesture selection
gesture_selected_total{gesture="ack"} 100
gesture_selected_total{gesture="nod_fast"} 35
gesture_selected_total{gesture="nod_tilt"} 50
gesture_selected_total{gesture="thinking_done"} 12
gesture_selected_total{gesture="error"} 3

# Backend failures
backend_failures_total 3
```

## Integration with Monitoring

These metrics can be scraped by Prometheus and visualized in Grafana for:
- **SLO Monitoring**: Track `edge_e2e_ms` against 2500ms SLO
- **Performance Analysis**: Analyze `llm_call_ms` distribution
- **User Experience**: Monitor gesture distribution to understand response patterns
- **Reliability**: Track `backend_failures_total` for system health

## Why This Makes It "Enterprise"

1. **Immediate Feedback**: Users always get instant acknowledgment (`ack` gesture)
2. **Latency Awareness**: System adapts behavior based on actual performance
3. **Observability**: Full metrics exposure for monitoring and alerting
4. **SLO Tracking**: Built-in SLO monitoring and violation tracking
5. **Production-Ready**: Not just a demo - suitable for real deployments

This transforms the demo from a simple toy into an enterprise-grade system that provides professional user experience and full observability.

