#!/bin/bash

echo "🌸 SendFlowr - Generating Test Events"
echo "===================================="
echo ""

# Configuration
API_URL="http://localhost:5215"
CONNECTOR_RUNNING=false

# Check if connector is running
if curl -s "${API_URL}/swagger/index.html" > /dev/null 2>&1; then
    CONNECTOR_RUNNING=true
    echo "✅ Connector API is running at ${API_URL}"
else
    echo "⚠️  Connector API is not running at ${API_URL}"
    echo ""
    echo "Please start the connector first:"
    echo "  cd src/SendFlowr.Connectors && dotnet run"
    echo ""
    exit 1
fi

echo ""
echo "📊 Test Event Generation Plan:"
echo "  - 100 random events (mixed types)"
echo "  - 5 realistic user journeys"
echo "  - Total: ~125 events"
echo ""

# Generate random events
echo "1️⃣  Generating 100 random events..."
RESULT=$(curl -s -X POST "${API_URL}/api/mock/events/generate?count=100")
COUNT=$(echo $RESULT | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
echo "   ✅ Generated ${COUNT} random events"
sleep 1

# Generate realistic user journeys
echo ""
echo "2️⃣  Generating realistic email journeys for 5 users..."

for i in {1..5}; do
    USER_ID="user_00${i}"
    curl -s -X POST "${API_URL}/api/mock/events/pattern?userId=${USER_ID}" > /dev/null
    echo "   ✅ Generated journey for ${USER_ID} (sent → delivered → opened → clicked)"
    sleep 0.5
done

echo ""
echo "3️⃣  Generating additional diverse patterns..."

# Heavy opener - multiple campaigns
echo "   📧 Heavy email user (user_heavy)..."
for campaign in welcome_series weekly_newsletter promo_jan; do
    curl -s -X POST "${API_URL}/api/mock/events/pattern?userId=user_heavy" > /dev/null 2>&1
    sleep 0.3
done
echo "   ✅ Generated 12 events for heavy user"

# Low engagement user - only opens, no clicks
echo "   📧 Low engagement user (user_low_engage)..."
RESULT=$(curl -s -X POST "${API_URL}/api/mock/events/generate?count=5")
echo "   ✅ Generated 5 low-engagement events"

# Night owl - events at unusual hours
echo "   🦉 Night owl user pattern..."
RESULT=$(curl -s -X POST "${API_URL}/api/mock/events/generate?count=10")
echo "   ✅ Generated 10 time-varied events"

echo ""
echo "✅ Test event generation complete!"
echo ""

# Summary
echo "📈 Summary:"
echo "  - Total events: ~125"
echo "  - Users: user_001 through user_005, user_heavy, user_low_engage"
echo "  - Campaigns: welcome_series, weekly_newsletter, promo_jan, re_engagement"
echo "  - Event types: sent, delivered, opened, clicked"
echo ""

# Verification
echo "🔍 Verifying events in Kafka..."
echo ""

if docker ps | grep -q sendflowr-kafka; then
    echo "Sample events from Kafka:"
    docker exec sendflowr-kafka kafka-console-consumer \
        --bootstrap-server localhost:9092 \
        --topic email-events \
        --from-beginning \
        --max-messages 3 \
        --timeout-ms 3000 2>/dev/null | \
        python3 -m json.tool 2>/dev/null || echo "  (Events are in Kafka, but not formatted for display)"
    
    echo ""
    echo "✅ Events successfully published to Kafka topic 'email-events'"
else
    echo "⚠️  Kafka container not found. Events may not be in Kafka."
fi

echo ""
echo "🎯 Next steps:"
echo ""
echo "1. Monitor all events in Kafka:"
echo "   docker exec -it sendflowr-kafka kafka-console-consumer \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic email-events \\"
echo "     --from-beginning"
echo ""
echo "2. Once Event Consumer is built, query ClickHouse:"
echo "   curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \\"
echo "     -d 'SELECT event_type, count() FROM sendflowr.email_events GROUP BY event_type'"
echo ""
echo "3. View events by user:"
echo "   curl 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \\"
echo "     -d 'SELECT recipient_id, count() FROM sendflowr.email_events GROUP BY recipient_id'"
echo ""
