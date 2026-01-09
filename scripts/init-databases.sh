#!/bin/bash

echo "Initializing SendFlowr databases..."

# Wait for ClickHouse
echo "Waiting for ClickHouse..."
until curl -s http://localhost:8123/ping > /dev/null; do
    sleep 1
done
echo "ClickHouse is ready!"

# Initialize ClickHouse schema
echo "Creating ClickHouse schema..."
cat schemas/clickhouse-schema.sql | curl -X POST 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' --data-binary @-

# Wait for Postgres
echo "Waiting for Postgres..."
until PGPASSWORD=sendflowr_dev psql -h localhost -U sendflowr -d sendflowr -c '\q' 2>/dev/null; do
    sleep 1
done
echo "Postgres is ready!"

# Initialize Postgres schema
echo "Creating Postgres schema..."
PGPASSWORD=sendflowr_dev psql -h localhost -U sendflowr -d sendflowr -f schemas/postgres-schema.sql

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

echo "Database initialization complete!"
