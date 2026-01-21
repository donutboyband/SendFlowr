#!/bin/bash

echo "🌸 SendFlowr - Complete Setup & Test"
echo "====================================="
echo ""

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "${PROJECT_ROOT}"

# Step 1: Check Docker
echo "1️⃣  Checking Docker services..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

docker-compose ps --format "table {{.Service}}\t{{.Status}}" 2>/dev/null | head -10
echo ""

# Start services if needed
if ! docker-compose ps | grep -q "Up"; then
    echo "Starting Docker services..."
    docker-compose up -d
    sleep 10
fi

echo "✅ Docker services running"
echo ""

# Step 2: Verify databases
echo "2️⃣  Verifying databases..."

# ClickHouse
if curl -s http://localhost:8123/ping > /dev/null; then
    EVENT_COUNT=$(curl -s 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
        -d 'SELECT count() FROM sendflowr.email_events')
    echo "  ✅ ClickHouse: $EVENT_COUNT events"
else
    echo "  ❌ ClickHouse not responding"
    exit 1
fi

# Redis
if docker exec sendflowr-redis redis-cli ping > /dev/null 2>&1; then
    echo "  ✅ Redis: Running"
else
    echo "  ❌ Redis not responding"
    exit 1
fi

# Kafka
if docker exec sendflowr-kafka kafka-topics --list --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "  ✅ Kafka: Running"
else
    echo "  ❌ Kafka not responding"
    exit 1
fi

echo ""

# Step 3: Check Python environment
echo "3️⃣  Checking Python environment..."
cd src/SendFlowr.Inference

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install/update dependencies
echo "  Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt scipy

echo "  ✅ Python environment ready"
echo ""
cd ../..

# Step 4: Start Connector API
echo "4️⃣  Starting Connector API (port 8000)..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    cd src/SendFlowr.Connectors
    dotnet run > /dev/null 2>&1 &
    CONNECTOR_PID=$!
    echo "  Started Connector API (PID: $CONNECTOR_PID)"
    cd ../..
    sleep 3
else
    echo "  ✅ Connector API already running"
fi

# Step 5: Start Timing Layer API
echo "5️⃣  Starting Timing Layer API (port 8001)..."
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    cd src/SendFlowr.Inference
    source venv/bin/activate
    python -m uvicorn main:app --reload --port 8001 > /dev/null 2>&1 &
    TIMING_PID=$!
    echo "  Started Timing API (PID: $TIMING_PID)"
    cd ../..
    sleep 5
else
    echo "  ✅ Timing API already running"
fi

# Step 6: Start Event Consumer
echo "6️⃣  Checking Event Consumer..."
if ! ps aux | grep -v grep | grep "SendFlowr.Consumer" > /dev/null; then
    echo "  Starting Event Consumer..."
    cd src/SendFlowr.Consumer
    dotnet run > /dev/null 2>&1 &
    CONSUMER_PID=$!
    echo "  Started Consumer (PID: $CONSUMER_PID)"
    cd ../..
    sleep 2
else
    echo "  ✅ Event Consumer already running"
fi

echo ""

# Step 7: Health checks
echo "7️⃣  Running health checks..."

# Connector API
CONNECTOR_HEALTH=$(curl -s http://localhost:8000/swagger/index.html 2>&1)
if echo "$CONNECTOR_HEALTH" | grep -q "html"; then
    echo "  ✅ Connector API: http://localhost:8000"
else
    echo "  ⚠️  Connector API: Not responding"
fi

# Timing API
TIMING_HEALTH=$(curl -s http://localhost:8001/health)
if echo "$TIMING_HEALTH" | grep -q "healthy"; then
    echo "  ✅ Timing API: http://localhost:8001"
else
    echo "  ⚠️  Timing API: Not responding"
fi

echo ""

# Step 8: Run tests
echo "8️⃣  Running pipeline test..."
echo ""
./scripts/run-inference-pipeline.sh

echo ""
echo "✅ SendFlowr Setup Complete!"
echo ""
echo "📊 Services Running:"
echo "  • ClickHouse: http://localhost:8123"
echo "  • Redis: localhost:6379"
echo "  • Kafka: localhost:9092"
echo "  • Connector API: http://localhost:8000"
echo "  • Timing Layer API: http://localhost:8001"
echo "  • Event Consumer: Running in background"
echo ""
echo "🎯 Quick Tests:"
echo "  • Generate events: ./scripts/generate-test-events.sh"
echo "  • Timing decision: ./scripts/quick-predict.sh user_003 300 8001"
echo "  • Full pipeline: ./scripts/run-inference-pipeline.sh"
echo ""
echo "📖 Documentation:"
echo "  • Architecture: docs/MIGRATION.md"
echo "  • Testing: docs/TESTING.md"
echo "  • Synthetic Data: docs/SYNTHETIC-DATA.md"
echo "  • Architecture Spec: LLM-Ref/LLM-spec.md"
echo "  • API Docs: http://localhost:8001/docs"
echo ""
