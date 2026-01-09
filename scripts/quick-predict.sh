#!/bin/bash

echo "🌸 SendFlowr - Quick Prediction"
echo "==============================="
echo ""

# Check if user ID provided
if [ -z "$1" ]; then
    echo "Usage: ./scripts/quick-predict.sh <recipient_id> [hours_ahead]"
    echo ""
    echo "Example:"
    echo "  ./scripts/quick-predict.sh user_003"
    echo "  ./scripts/quick-predict.sh user_001 48"
    echo ""
    echo "Available users:"
    curl -s 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
        -d 'SELECT DISTINCT recipient_id FROM sendflowr.email_events ORDER BY recipient_id LIMIT 10' | \
        awk '{print "  - " $0}'
    exit 1
fi

RECIPIENT_ID=$1
HOURS_AHEAD=${2:-24}

echo "🎯 Generating prediction for: ${RECIPIENT_ID}"
echo "⏰ Looking ahead: ${HOURS_AHEAD} hours"
echo ""

# Make prediction
RESULT=$(curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\": \"${RECIPIENT_ID}\", \"hours_ahead\": ${HOURS_AHEAD}}")

# Check if successful
if ! echo "$RESULT" | grep -q "recipient_id"; then
    echo "❌ Failed to get prediction"
    echo "$RESULT"
    exit 1
fi

# Display results
echo "$RESULT" | python3 -c "
import sys, json
from datetime import datetime

d = json.load(sys.stdin)

print('📊 PREDICTION RESULTS')
print('=' * 50)
print(f'Recipient: {d[\"recipient_id\"]}')
print(f'Model: {d[\"model_version\"]}')
print(f'Computed at: {datetime.now().strftime(\"%Y-%m-%d %H:%M:%S\")}')
print()

print('🎯 TOP 3 OPTIMAL SEND WINDOWS')
print('-' * 50)
for i, w in enumerate(d['optimal_windows'][:3], 1):
    start = w['start'][:16].replace('T', ' ')
    end = w['end'][11:16]
    prob = w['probability']
    print(f'{i}. {start} - {end}')
    print(f'   Probability: {prob:.2%}')
    print()

print('⭐ PEAK ENGAGEMENT HOURS')
print('-' * 50)
for p in d['explanation']['peak_hours'][:5]:
    bar = '█' * int(p['probability'] / 2)
    print(f\"{p['time']:15s} {bar} {p['probability']:.1f}%\")
print()

print('📅 PEAK ENGAGEMENT DAYS')
print('-' * 50)
for p in d['explanation']['peak_days'][:3]:
    bar = '█' * int(p['probability'] / 2)
    print(f\"{p['day']:12s} {bar} {p['probability']:.1f}%\")
print()

print('📈 ENGAGEMENT STATS')
print('-' * 50)
print(f\"Opens (30 days):  {d['features_used']['open_count_30d']}\")
print(f\"Clicks (30 days): {d['features_used']['click_count_30d']}\")
print()

print('📉 HOURLY PROBABILITY CURVE (next 12 hours)')
print('-' * 50)
for point in d['curve'][:12]:
    time = point['time'][11:16]
    prob = point['probability']
    bar = '█' * int(prob * 200)
    print(f'{time} | {bar} {prob:.4f}')
"

echo ""
echo "✅ Prediction complete!"
echo ""
echo "💡 TIP: Use this window for your next campaign send!"
