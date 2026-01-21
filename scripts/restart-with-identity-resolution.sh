#!/bin/bash

echo "🔄 Restarting SendFlowr with Identity Resolution"
echo "==============================================="
echo ""

# Step 1: Stop running services
echo "1️⃣  Stopping existing services..."
pkill -f "SendFlowr.Connectors" 2>/dev/null && echo "   ✅ Stopped Connector" || echo "   ℹ️  Connector not running"
pkill -f "SendFlowr.Consumer" 2>/dev/null && echo "   ✅ Stopped Consumer" || echo "   ℹ️  Consumer not running"
sleep 2

# Step 2: Clear existing data (fresh start)
echo ""
echo "2️⃣  Clearing existing data..."
docker exec sendflowr-clickhouse clickhouse-client --query "DROP TABLE IF EXISTS sendflowr.email_events" 2>/dev/null
echo "   ✅ Dropped old email_events table"

# Step 3: Create new schema
echo ""
echo "3️⃣  Creating new schema..."
docker exec -i sendflowr-clickhouse clickhouse-client --multiquery < schemas/clickhouse-schema.sql 2>/dev/null
echo "   ✅ Created email_events table with universal_id and recipient_email_hash"

# Step 4: Verify schema
echo ""
echo "4️⃣  Verifying schema..."
COLUMNS=$(docker exec sendflowr-clickhouse clickhouse-client --query "SELECT name FROM system.columns WHERE database='sendflowr' AND table='email_events' AND name IN ('universal_id', 'recipient_email_hash')" 2>/dev/null | wc -l)
if [ "$COLUMNS" -ge 2 ]; then
    echo "   ✅ Schema correct (has universal_id and recipient_email_hash)"
else
    echo "   ❌ Schema incorrect - missing required columns"
    exit 1
fi

# Step 5: Build services
echo ""
echo "5️⃣  Building services..."
cd src/SendFlowr.Connectors
dotnet build -v quiet > /dev/null 2>&1 && echo "   ✅ Built Connector" || (echo "   ❌ Connector build failed" && exit 1)
cd ../SendFlowr.Consumer
dotnet build -v quiet > /dev/null 2>&1 && echo "   ✅ Built Consumer" || (echo "   ❌ Consumer build failed" && exit 1)
cd ../..

# Step 6: Check inference service
echo ""
echo "6️⃣  Checking inference service..."
if curl -s http://localhost:8001/docs > /dev/null; then
    echo "   ✅ Inference service is running on port 8001"
else
    echo "   ❌ Inference service NOT running"
    echo "   Please start it with:"
    echo "   cd src/SendFlowr.Inference && uvicorn main:app --host 0.0.0.0 --port 8001"
    exit 1
fi

echo ""
echo "✅ Setup complete! Services are ready to start."
echo ""
echo "📋 Next steps:"
echo ""
echo "   Terminal 1 - Start Connector:"
echo "   $ cd src/SendFlowr.Connectors && dotnet run"
echo ""
echo "   Terminal 2 - Start Consumer:"
echo "   $ cd src/SendFlowr.Consumer && dotnet run"
echo ""
echo "   Terminal 3 - Generate test events:"
echo "   $ ./scripts/generate-test-events.sh"
echo ""
echo "   Then verify:"
echo "   $ docker exec sendflowr-clickhouse clickhouse-client --query \"SELECT universal_id, recipient_email_hash, event_type FROM sendflowr.email_events LIMIT 5\""
echo ""
