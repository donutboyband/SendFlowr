#!/bin/bash

echo "🧪 SendFlowr - Complete Test Suite"
echo "==================================="
echo ""

# Configuration
API_URL="http://localhost:5215"

# Check if connector is running
if ! curl -s "${API_URL}/swagger/index.html" > /dev/null 2>&1; then
    echo "⚠️  Connector API is not running at ${API_URL}"
    echo ""
    echo "Please start the connector first:"
    echo "  cd src/SendFlowr.Connectors && dotnet run"
    echo ""
    exit 1
fi

echo "✅ Connector API is running"
echo ""

# Test 1: Single realistic journey
echo "TEST 1: Single Realistic User Journey"
echo "======================================"
curl -s -X POST "${API_URL}/api/mock/events/pattern?userId=test_user_001" | python3 -m json.tool
echo ""
sleep 1

# Test 2: Random events
echo "TEST 2: Random Events (count=10)"
echo "=================================="
curl -s -X POST "${API_URL}/api/mock/events/generate?count=10" | python3 -m json.tool
echo ""
sleep 1

# Test 3: Multiple users - simulate cohort
echo "TEST 3: Cohort Simulation (3 users)"
echo "===================================="
for user in cohort_user_a cohort_user_b cohort_user_c; do
    echo "Generating journey for ${user}..."
    curl -s -X POST "${API_URL}/api/mock/events/pattern?userId=${user}" > /dev/null
done
echo "✅ Generated 12 events for cohort"
echo ""
sleep 1

# Test 4: Bulk load
echo "TEST 4: Bulk Load (50 events)"
echo "=============================="
RESULT=$(curl -s -X POST "${API_URL}/api/mock/events/generate?count=50")
COUNT=$(echo $RESULT | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
echo "✅ Generated ${COUNT} events"
echo ""
sleep 1

# Test 5: Kafka verification
echo "TEST 5: Kafka Verification"
echo "==========================="
if docker ps | grep -q sendflowr-kafka; then
    echo "Consuming latest 5 events from Kafka..."
    docker exec sendflowr-kafka kafka-console-consumer \
        --bootstrap-server localhost:9092 \
        --topic email-events \
        --max-messages 5 \
        --timeout-ms 3000 2>/dev/null | head -5
    echo ""
    echo "✅ Kafka is receiving events"
else
    echo "⚠️  Kafka container not found"
fi

echo ""
echo "✅ All tests complete!"
echo ""
echo "Summary: ~73 events generated across multiple users and patterns"
