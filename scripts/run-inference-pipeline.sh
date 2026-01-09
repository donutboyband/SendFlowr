#!/bin/bash

echo "🌸 SendFlowr Inference Pipeline"
echo "================================"
echo ""

# Check if inference API is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  Inference API is not running!"
    echo ""
    echo "Starting Inference API..."
    cd src/SendFlowr.Inference
    source venv/bin/activate
    python -m uvicorn main:app --reload --port 8000 > /dev/null 2>&1 &
    API_PID=$!
    echo "Started with PID: $API_PID"
    sleep 5
    cd ../..
fi

echo "✅ Inference API is running at http://localhost:8000"
echo ""

# Step 1: Compute features for all users
echo "1️⃣  Computing features for all active users..."
curl -s -X POST http://localhost:8000/compute-all-features | python3 -m json.tool
echo ""

# Step 2: Get predictions for a few users
echo "2️⃣  Generating predictions for sample users..."
echo ""

for USER_ID in user_001 user_002 user_003 user_004 user_005; do
    echo "📊 Prediction for ${USER_ID}:"
    
    RESULT=$(curl -s -X POST http://localhost:8000/predict \
        -H "Content-Type: application/json" \
        -d "{\"recipient_id\": \"${USER_ID}\", \"hours_ahead\": 24}")
    
    if echo "$RESULT" | grep -q "recipient_id"; then
        echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"  ✅ Recipient: {d['recipient_id']}\")
print(f\"  📈 Model: {d['model_version']}\")
print(f\"  🎯 Top Window: {d['optimal_windows'][0]['start'][:16]} (prob: {d['optimal_windows'][0]['probability']:.3f})\")
peaks = d['explanation']['peak_hours'][:3]
print(f\"  ⭐ Peak Hours: {', '.join([p['time'] for p in peaks])}\")
print()
"
    else
        echo "  ❌ Failed to get prediction"
        echo ""
    fi
    
    sleep 0.5
done

echo ""
echo "3️⃣  Detailed prediction example (user_003):"
echo ""

curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"recipient_id": "user_003", "hours_ahead": 48}' | \
    python3 -c "
import sys, json
d = json.load(sys.stdin)

print(f\"Recipient: {d['recipient_id']}\")
print(f\"Model: {d['model_version']}\")
print()
print('📊 Top 3 Optimal Send Windows:')
for i, w in enumerate(d['optimal_windows'][:3], 1):
    print(f\"  {i}. {w['start'][:16]} - {w['end'][11:16]} (probability: {w['probability']:.1%})\")

print()
print('⭐ Peak Engagement Hours:')
for p in d['explanation']['peak_hours'][:5]:
    print(f\"  {p['time']:12s} - {p['probability']}% probability\")

print()
print('📅 Peak Engagement Days:')
for p in d['explanation']['peak_days'][:3]:
    print(f\"  {p['day']:10s} - {p['probability']}% probability\")

print()
print(f\"📈 Engagement Stats:\")
print(f\"  Opens (30d): {d['features_used']['open_count_30d']}\")
print(f\"  Clicks (30d): {d['features_used']['click_count_30d']}\")
"

echo ""
echo "4️⃣  Sample probability curve (first 12 hours):"
echo ""

curl -s -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"recipient_id": "user_003", "hours_ahead": 12}' | \
    python3 -c "
import sys, json
d = json.load(sys.stdin)

print('Time           | Probability')
print('---------------|------------')
for point in d['curve']:
    time = point['time'][11:16]
    prob = point['probability']
    bar = '█' * int(prob * 500)
    print(f\"{time}          | {bar} {prob:.4f}\")
"

echo ""
echo "✅ Inference pipeline complete!"
echo ""
echo "🎯 Next steps:"
echo "  • View API docs: http://localhost:8000/docs"
echo "  • Get features: curl http://localhost:8000/features/user_003"
echo "  • Make predictions: curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{\"recipient_id\": \"user_003\"}'"
echo ""
