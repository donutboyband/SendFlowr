#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
SCHEMA_DIR="${PROJECT_ROOT}/schemas"

echo "Initializing SendFlowr databases..."

# Wait for ClickHouse
echo "Waiting for ClickHouse..."
until curl -s http://localhost:8123/ping > /dev/null; do
    sleep 1
done
echo "ClickHouse is ready!"

# Initialize ClickHouse - one statement at a time
echo "Creating ClickHouse database..."
echo "CREATE DATABASE IF NOT EXISTS sendflowr" | curl -sS -X POST 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' --data-binary @-

echo "Creating ClickHouse table..."
cat "${SCHEMA_DIR}/clickhouse-table.sql" | curl -sS -X POST 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' --data-binary @-
echo "Creating ClickHouse timing explanations table..."
cat "${SCHEMA_DIR}/clickhouse-explanations.sql" | curl -sS -X POST 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' --data-binary @-

# Wait for Postgres
echo "Waiting for Postgres..."
POSTGRES_CONTAINER="sendflowr-postgres"
POSTGRES_READY=false
for i in {1..60}; do
    if docker exec "${POSTGRES_CONTAINER}" pg_isready -U sendflowr > /dev/null 2>&1; then
        POSTGRES_READY=true
        break
    fi
    sleep 1
done

if [ "${POSTGRES_READY}" != true ]; then
    echo "❌ Postgres is not responding inside container ${POSTGRES_CONTAINER}"
    exit 1
fi
echo "Postgres is ready!"

# Initialize Postgres schema
echo "Creating Postgres schema..."
cat "${SCHEMA_DIR}/postgres-schema.sql" | docker exec -i "${POSTGRES_CONTAINER}" psql -U sendflowr -d sendflowr > /dev/null

# Create Kafka topics
echo "Creating Kafka topics..."
docker exec sendflowr-kafka kafka-topics --create --if-not-exists \
    --topic email-events \
    --bootstrap-server localhost:9092 \
    --partitions 3 \
    --replication-factor 1

docker exec sendflowr-kafka kafka-topics --create --if-not-exists \
    --topic email-events-dlq \
    --bootstrap-server localhost:9092 \
    --partitions 1 \
    --replication-factor 1

echo ""
echo "✅ Database initialization complete!"
