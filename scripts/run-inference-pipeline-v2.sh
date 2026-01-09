#!/bin/bash

echo "🌸 SendFlowr v2.0 Inference Pipeline Test"
echo "=========================================="
echo ""

API_PORT=8001

# Check if v2 inference API is running
if ! curl -s http://localhost:${API_PORT}/health > /dev/null 2>&1; then
    echo "⚠️  v2.0 Inference API is not running on port ${API_PORT}!"
    echo ""
    echo "Starting v2.0 Inference API..."
    cd src/SendFlowr.Inference
    source venv/bin/activate
    python -m uvicorn main_v2:app --reload --port ${API_PORT} > /dev/null 2>&1 &
    API_PID=$!
    echo "Started with PID: $API_PID"
    sleep 8
    cd ../..
fi

echo "✅ v2.0 Inference API is running at http://localhost:${API_PORT}"
echo ""

# Step 1: Compute minute-level features
echo "1️⃣  Computing minute-level features for all active users..."
curl -s -X POST http://localhost:${API_PORT}/compute-features | python3 -m json.tool
echo ""

# Step 2: Generate timing decisions for sample users
echo "2️⃣  Generating timing decisions for sample users..."
echo ""

for USER_ID in user_001 user_002 user_003 user_004 user_005; do
    echo "📊 Timing Decision for ${USER_ID}:"
    
    RESULT=$(curl -s -X POST http://localhost:${API_PORT}/timing-decision \
        -H "Content-Type: application/json" \
        -d "{\"recipient_id\": \"${USER_ID}\", \"latency_estimate_seconds\": 300}")
    
    if echo "$RESULT" | grep -q "decision_id"; then
        echo "$RESULT" | python3 -c "
import sys, json

d = json.load(sys.stdin)

# Helper to convert minute slot to readable
def slot_to_readable(slot):
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_idx = slot // 1440
    mins_in_day = slot % 1440
    hour = mins_in_day // 60
    minute = mins_in_day % 60
    return f'{days[day_idx]} {hour:02d}:{minute:02d}'

target_slot = d['target_minute_utc']
print(f\"  ✅ Decision ID: {d['decision_id'][:8]}...\")
print(f\"  🎯 Target: Slot {target_slot} ({slot_to_readable(target_slot)})\")
print(f\"  ⚡ Trigger: {d['trigger_timestamp_utc'][:16]}\")
print(f\"  📊 Confidence: {d['confidence_score']:.1%}\")
print(f\"  🔧 Model: {d['model_version']}\")
print()
"
    else
        echo "  ❌ Failed to get timing decision"
        echo ""
    fi
    
    sleep 0.5
done

echo ""
echo "3️⃣  Detailed timing decision example (user_003):"
echo ""

curl -s -X POST http://localhost:${API_PORT}/timing-decision \
    -H "Content-Type: application/json" \
    -d '{"recipient_id": "user_003", "latency_estimate_seconds": 300}' | \
    python3 -c "
import sys, json
from datetime import datetime

d = json.load(sys.stdin)

def slot_to_readable(slot):
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_idx = slot // 1440
    mins_in_day = slot % 1440
    hour = mins_in_day // 60
    minute = mins_in_day % 60
    return f'{days[day_idx]} {hour:02d}:{minute:02d}'

print('📋 COMPLETE TIMING DECISION')
print('=' * 60)
print(f'Decision ID: {d[\"decision_id\"]}')
print(f'Recipient: {d[\"universal_user_id\"]}')
print(f'Model Version: {d[\"model_version\"]}')
print()

print('🎯 TARGET DELIVERY')
print('-' * 60)
target = d['target_minute_utc']
print(f'Minute Slot: {target} / 10,079')
print(f'Day/Time: {slot_to_readable(target)}')
print(f'Confidence: {d[\"confidence_score\"]:.2%}')
print()

print('⚡ TRIGGER TIME (Latency-Compensated)')
print('-' * 60)
trigger = datetime.fromisoformat(d['trigger_timestamp_utc'].replace('Z', '+00:00'))
print(f'Fire Send At: {trigger.strftime(\"%Y-%m-%d %H:%M:%S UTC\")}')
print(f'Latency Offset: -{d[\"latency_estimate_seconds\"]}s')
print()

print('🔍 DEBUG INFO')
print('-' * 60)
debug = d.get('debug', {})
peak = debug.get('base_curve_peak_minute')
if peak is not None:
    print(f'Curve Peak: {slot_to_readable(peak)}')
print(f'Suppressed: {debug.get(\"suppressed\", False)}')
print()

print('📖 Explanation: {}'.format(d['explanation_ref']))
"

echo ""
echo "4️⃣  Feature metadata (user_003):"
echo ""

curl -s http://localhost:${API_PORT}/features/user_003 | python3 -c "
import sys, json

f = json.load(sys.stdin)

print(f'Recipient: {f[\"recipient_id\"]}')
print(f'Version: {f[\"version\"]}')
print(f'Curve Confidence: {f[\"curve_confidence\"]:.3f}')
print()
print('Top 3 Peak Windows:')
for w in f['peak_windows'][:3]:
    print(f\"  {w['readable']} - Probability: {w['probability']:.4f}\")
print()
print('Engagement Stats:')
print(f\"  Clicks (30d): {f['click_count_30d']}\")
print(f\"  Clicks (7d): {f['click_count_7d']}\")
print(f\"  Last Click: {f['last_click_ts']}\")
"

echo ""
echo "✅ v2.0 Inference pipeline test complete!"
echo ""
echo "🎯 Key Differences from v1.0:"
echo "  • Minute-level precision (10,080 slots vs 24 hours)"
echo "  • Click-based signals (MPP resilient)"
echo "  • Latency-aware triggers (compensates ESP delay)"
echo "  • Spec-compliant TimingDecision output"
echo ""
echo "📖 See: docs/MIGRATION-V2.md for full details"
echo ""
