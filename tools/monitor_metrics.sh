#!/bin/bash
# Real-time metrics monitoring script
# Usage: ./tools/monitor_metrics.sh [interval_seconds]

INTERVAL=${1:-2}
METRICS_URL="http://127.0.0.1:9100/metrics"

echo "🔍 Real-time Metrics Monitor (refreshing every ${INTERVAL}s)"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "════════════════════════════════════════════════════════════"
    echo "📊 Metrics Snapshot - $(date '+%H:%M:%S')"
    echo "════════════════════════════════════════════════════════════"
    echo ""
    
    # Get metrics
    METRICS=$(curl -s "$METRICS_URL" 2>/dev/null)
    
    if [ -z "$METRICS" ]; then
        echo "❌ Cannot connect to metrics server at $METRICS_URL"
        echo "   Make sure 'make run' is running"
        sleep $INTERVAL
        continue
    fi
    
    # Extract key metrics
    echo "📈 Request Counters:"
    echo "$METRICS" | grep -E "^edge_requests_total|^edge_errors_total|^backend_failures_total|^edge_slo_miss_total" | sed 's/^/   /'
    echo ""
    
    echo "⏱️  Latency (Current):"
    echo "$METRICS" | grep -E "^llm_call_ms_sum|^edge_e2e_ms_sum" | sed 's/^/   /'
    echo "$METRICS" | grep -E "^llm_call_ms_count|^edge_e2e_ms_count" | sed 's/^/   /'
    echo ""
    
    echo "🎭 Gesture Selection:"
    echo "$METRICS" | grep "^gesture_selected_total" | sed 's/^/   /'
    echo ""
    
    echo "📊 Latency Percentiles (from buckets):"
    echo "$METRICS" | grep -E "^llm_call_ms_bucket.*le=\"(800|1200|2000|2500)\"" | sed 's/^/   /'
    echo ""
    
    echo "🔄 Refreshing in ${INTERVAL}s... (Ctrl+C to stop)"
    sleep $INTERVAL
done

