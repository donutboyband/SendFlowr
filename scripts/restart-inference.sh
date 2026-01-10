#!/bin/bash

echo "🔄 SendFlowr Inference Service - Restart"
echo "========================================"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
INFERENCE_DIR="${PROJECT_ROOT}/src/SendFlowr.Inference"
API_PORT=8001

# Check if already running
if lsof -ti:${API_PORT} > /dev/null 2>&1; then
    PID=$(lsof -ti:${API_PORT})
    echo "⚠️  Inference service already running on port ${API_PORT} (PID: ${PID})"
    echo "   Stopping..."
    kill ${PID}
    sleep 2
    
    # Force kill if still running
    if lsof -ti:${API_PORT} > /dev/null 2>&1; then
        echo "   Force stopping..."
        kill -9 ${PID}
        sleep 1
    fi
    echo "   ✅ Stopped"
    echo ""
fi

# Start the service
echo "🚀 Starting Inference API on port ${API_PORT}..."
cd "${INFERENCE_DIR}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and start
source venv/bin/activate

# Check dependencies
if ! python -c "import uvicorn" 2>/dev/null; then
    echo "   Installing dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt scipy
fi

echo "   Starting uvicorn..."
python -m uvicorn main:app --reload --port ${API_PORT} > /tmp/inference.log 2>&1 &
API_PID=$!

# Wait for startup
sleep 3

# Verify it started
if lsof -ti:${API_PORT} > /dev/null 2>&1; then
    echo ""
    echo "✅ Inference API started successfully!"
    echo ""
    echo "   PID: ${API_PID}"
    echo "   Port: ${API_PORT}"
    echo "   Health: http://localhost:${API_PORT}/health"
    echo "   Docs: http://localhost:${API_PORT}/docs"
    echo ""
    
    # Quick health check
    if curl -s http://localhost:${API_PORT}/health > /dev/null 2>&1; then
        echo "   🟢 Health check: PASSED"
    else
        echo "   🟡 Health check: API starting..."
    fi
    echo ""
    echo "To stop: kill ${API_PID}"
    echo "To view logs: tail -f /tmp/inference.log"
else
    echo ""
    echo "❌ Failed to start Inference API"
    echo "   Check logs or try manual start:"
    echo "   cd ${INFERENCE_DIR}"
    echo "   source venv/bin/activate"
    echo "   python -m uvicorn main:app --reload --port ${API_PORT}"
    exit 1
fi
