#!/bin/bash

set -euo pipefail

echo "🌸 SendFlowr - End-to-End Timing Layer Test"
echo "============================================"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
LOG_DIR="${PROJECT_ROOT}/.e2e-logs"
mkdir -p "${LOG_DIR}"

pushd "${PROJECT_ROOT}" > /dev/null

cleanup() {
    if [[ -n "${CONNECTOR_PID:-}" ]]; then
        echo "🛑 Stopping Connector API (PID ${CONNECTOR_PID})"
        kill "${CONNECTOR_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${INFERENCE_PID:-}" ]]; then
        echo "🛑 Stopping Timing API (PID ${INFERENCE_PID})"
        kill "${INFERENCE_PID}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${CONSUMER_PID:-}" ]]; then
        echo "🛑 Stopping Event Consumer (PID ${CONSUMER_PID})"
        kill "${CONSUMER_PID}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# 1. Ensure Docker services are running
echo "1️⃣  Ensuring Docker services are up..."
if ! docker-compose ps | grep -q "sendflowr-clickhouse"; then
    docker-compose up -d
    sleep 10
fi
echo "   ✅ Docker services ready"
echo ""

# 2. Start Connector API (publishes test events)
if ! curl -s http://localhost:5215/swagger/index.html > /dev/null 2>&1; then
    echo "2️⃣  Starting Connector API..."
    pushd src/SendFlowr.Connectors > /dev/null
    dotnet build >/dev/null
    dotnet run > "${LOG_DIR}/connector.log" 2>&1 &
    CONNECTOR_PID=$!
    popd > /dev/null
    sleep 5
else
    echo "2️⃣  Connector API already running"
fi
echo ""

# 3. Start Timing API
if ! curl -s http://localhost:8001/health | grep -q healthy; then
    echo "3️⃣  Starting Timing Layer API..."
    pushd src/SendFlowr.Inference > /dev/null
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt scipy
    python -m uvicorn main:app --reload --port 8001 > "${LOG_DIR}/timing-api.log" 2>&1 &
    INFERENCE_PID=$!
    deactivate
    popd > /dev/null
    sleep 8
else
    echo "3️⃣  Timing API already running"
fi
echo ""

# 4. Start Event Consumer (Kafka -> ClickHouse)
if ! ps aux | grep -v grep | grep -q "SendFlowr.Consumer"; then
    echo "4️⃣  Starting Event Consumer..."
    pushd src/SendFlowr.Consumer > /dev/null
    dotnet build >/dev/null
    dotnet run > "${LOG_DIR}/consumer.log" 2>&1 &
    CONSUMER_PID=$!
    popd > /dev/null
    sleep 5
else
    echo "4️⃣  Event Consumer already running"
fi
echo ""

# 5. Record baseline ClickHouse event count
BASE_COUNT=$(curl -s 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
    -d 'SELECT count() FROM sendflowr.email_events' | tr -d '\r')
echo "📦 Baseline ClickHouse events: ${BASE_COUNT}"
echo ""

# 6. Generate fresh Kafka events via Connector mock endpoints
echo "5️⃣  Generating test events via Connector API..."
./scripts/generate-test-events.sh
echo ""

echo "⏳ Waiting for consumer to ingest events..."
sleep 10

# 7. Verify ClickHouse ingested new events
NEW_COUNT=$(curl -s 'http://localhost:8123/?user=sendflowr&password=sendflowr_dev' \
    -d 'SELECT count() FROM sendflowr.email_events' | tr -d '\r')
echo "📦 Updated ClickHouse events: ${NEW_COUNT}"

if [[ "${NEW_COUNT}" -le "${BASE_COUNT}" ]]; then
    echo "❌ No new events detected in ClickHouse. Check consumer logs in ${LOG_DIR}."
    exit 1
fi
echo "   ✅ New events ingested successfully"
echo ""

# 8. Run v2 inference pipeline test (computes features + timing decisions)
echo "6️⃣  Running inference pipeline..."
./scripts/run-inference-pipeline-v2.sh
echo ""

# 9. Run a quick timing decision for a known user
echo "7️⃣  Running quick timing decision for user_001..."
./scripts/quick-predict.sh user_001 300 8001
echo ""

echo "🎉 End-to-end timing layer test completed successfully!"
echo "   Logs: ${LOG_DIR}"

popd > /dev/null
