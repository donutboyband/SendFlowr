#!/bin/bash
# SendFlowr - Initialize Docker Environment

set -e

echo "🌸 Starting SendFlowr Services"
echo "==============================="
echo ""

# Start all services
echo "📦 Starting Docker containers..."
docker-compose up -d

# Wait for Kafka to be healthy (macOS compatible)
echo "⏳ Waiting for Kafka to be ready..."
MAX_WAIT=60
ELAPSED=0
until docker exec sendflowr-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 &>/dev/null; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "❌ Kafka failed to start within ${MAX_WAIT}s"
        exit 1
    fi
done

# Create Kafka topic if it doesn't exist
echo "📊 Creating Kafka topics..."
docker exec sendflowr-kafka kafka-topics --create --topic email-events --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists

# Wait for ClickHouse to be healthy (macOS compatible)
echo "⏳ Waiting for ClickHouse to be ready..."
MAX_WAIT=30
ELAPSED=0
until docker exec sendflowr-clickhouse clickhouse-client --query "SELECT 1" &>/dev/null; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "❌ ClickHouse failed to start within ${MAX_WAIT}s"
        exit 1
    fi
done

# Create ClickHouse schema if needed
echo "🗄️  Setting up ClickHouse schema..."
if [ -f schemas/clickhouse-schema.sql ]; then
    docker exec sendflowr-clickhouse clickhouse-client --multiquery < schemas/clickhouse-schema.sql 2>/dev/null || echo "Schema already exists"
else
    echo "Schema file not found, skipping (table may already exist)"
fi

# Wait for Connector to be ready
echo "⏳ Waiting for Connector API to be ready..."
MAX_WAIT=30
ELAPSED=0
until curl -s http://localhost:5215/scalar/v1 > /dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "⚠️  Connector API not responding within ${MAX_WAIT}s (may still be starting)"
        break
    fi
done

# Wait for Inference to be ready
echo "⏳ Waiting for Inference API to be ready..."
MAX_WAIT=30
ELAPSED=0
until curl -s http://localhost:8001/health > /dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "⚠️  Inference API not responding within ${MAX_WAIT}s (may still be starting)"
        break
    fi
done

echo ""
echo "✅ SendFlowr is ready!"
echo ""
echo "Services:"
echo "  - Inference API:  http://localhost:8001"
echo "  - Connector API:  http://localhost:5215"
echo "  - ClickHouse:     http://localhost:8123"
echo "  - Redis:          localhost:6379"
echo "  - Kafka:          localhost:9092"
echo "  - Postgres:       localhost:5432"
echo ""
echo "Test it:"
echo "  curl http://localhost:8001/health"
echo "  python3 scripts/generate-synthetic-data.py --count 100"
echo ""
echo "Logs:"
echo "  docker-compose logs -f inference"
echo "  docker-compose logs -f connector"
echo "  docker-compose logs -f consumer"
