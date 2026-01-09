#!/bin/bash

echo "🌸 SendFlowr - Quick Prediction (v2.0 Timing Layer)"
echo "===================================================="
echo ""

# Check if user ID provided
if [ -z "$1" ]; then
    echo "Usage: ./scripts/quick-predict.sh <recipient_id> [latency_seconds]"
    echo ""
    echo "Example:"
    echo "  ./scripts/quick-predict.sh user_003"
    echo "  ./scripts/quick-predict.sh user_001 300"
    echo ""
    echo "Available users:"
    curl -s 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
        -d 'SELECT DISTINCT recipient_id FROM sendflowr.email_events ORDER BY recipient_id LIMIT 10' | \
        awk '{print "  - " $0}'
    exit 1
fi

RECIPIENT_ID=$1
LATENCY_SECONDS=${2:-300}
API_PORT=${3:-8001}  # Default to v2 API

echo "🎯 Generating timing decision for: ${RECIPIENT_ID}"
echo "⏰ Latency estimate: ${LATENCY_SECONDS} seconds"
echo "🔌 API: http://localhost:${API_PORT}"
echo ""

# Make timing decision
RESULT=$(curl -s -X POST http://localhost:${API_PORT}/timing-decision \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\": \"${RECIPIENT_ID}\", \"latency_estimate_seconds\": ${LATENCY_SECONDS}}")

# Check if successful
if ! echo "$RESULT" | grep -q "decision_id"; then
    echo "❌ Failed to get timing decision"
    echo "$RESULT"
    exit 1
fi

# Display results
echo "$RESULT" | python3 -c "
import sys, json
from datetime import datetime

d = json.load(sys.stdin)

print('📊 TIMING DECISION (v2.0)')
print('=' * 60)
print(f'Decision ID: {d[\"decision_id\"]}')
print(f'Recipient: {d[\"universal_user_id\"]}')
print(f'Model: {d[\"model_version\"]}')
print()

# Target minute slot
from_timing_model = lambda slot: (
    ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][slot // 1440] + ' ' +
    f\"{(slot % 1440) // 60:02d}:{(slot % 1440) % 60:02d}\"
)

target_slot = d['target_minute_utc']
print('🎯 TARGET DELIVERY')
print('-' * 60)
print(f'  Minute Slot: {target_slot} / 10,079')
print(f'  Day/Time: {from_timing_model(target_slot)}')
print(f'  Confidence: {d[\"confidence_score\"]:.1%}')
print()

# Trigger time
trigger_dt = datetime.fromisoformat(d['trigger_timestamp_utc'].replace('Z', '+00:00'))
print('⚡ TRIGGER TIME (Latency-Adjusted)')
print('-' * 60)
print(f'  Fire At: {trigger_dt.strftime(\"%Y-%m-%d %H:%M:%S UTC\")}')
print(f'  Latency Offset: -{d[\"latency_estimate_seconds\"]} seconds')
print()

# Debug info
if 'debug' in d:
    debug = d['debug']
    print('🔍 DEBUG INFO')
    print('-' * 60)
    peak_minute = debug.get('base_curve_peak_minute')
    if peak_minute is not None:
        print(f'  Curve Peak: {from_timing_model(peak_minute)}')
    print(f'  Suppressed: {debug.get(\"suppressed\", False)}')
    print(f'  Applied Weights: {len(debug.get(\"applied_weights\", []))}')
print()

print('📖 Explanation Reference: {}'.format(d['explanation_ref']))
"

echo ""
echo "✅ Timing decision complete!"
echo ""
echo "💡 TIP: Use trigger_timestamp_utc to schedule your send!"
