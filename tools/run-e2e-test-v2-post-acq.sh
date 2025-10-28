#!/usr/bin/env bash
set -euo pipefail

# E2E Test Runner for SmartEM Decisions - Agent V2 POST-ACQUISITION
# This script replays files FIRST, then starts agent v2 to process existing files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
RECORDING="${1:-/home/vredchenko/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz}"
EPU_DIR="${2:-/home/vredchenko/dev/DLS/epu-test-dir}"
MAX_DELAY="${3:-0.1}"  # Default to 0.1s max delay (slower than no limit)
TEST_DIR="$PROJECT_ROOT/logs/e2e-tests/$(date +%Y-%m-%d_%H%M%S)_post-acquisition-test"

echo "===== SmartEM E2E Test Runner ====="
echo "Recording: $RECORDING"
echo "EPU Directory: $EPU_DIR"
echo "Max Delay: ${MAX_DELAY}s"
echo "Test Results: $TEST_DIR"
echo "===================================="

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up background processes..."
    pkill -f "smartem_backend|smartem_agent|fsrecorder|uvicorn" || true
    echo "Cleaning up playback data directory..."
    rm -rf "$EPU_DIR" || true
    echo "Cleanup complete"
}

trap cleanup EXIT

# Setup
echo ""
echo "[1/9] Setting up test environment..."
mkdir -p "$TEST_DIR/logs"
mkdir -p "$EPU_DIR"
rm -rf "$EPU_DIR"/*

echo "[2/9] Activating virtual environment..."
source .venv/bin/activate

echo "[3/9] Loading environment variables..."
set -a
source .env.local-test-run
set +a

echo "[4/9] Resetting database..."
POSTGRES_HOST=localhost POSTGRES_PORT=30432 POSTGRES_DB=postgres \
    POSTGRES_USER=username POSTGRES_PASSWORD=password \
    python -m smartem_backend.model.database

echo "[5/10] Running database migrations..."
POSTGRES_HOST=localhost POSTGRES_PORT=30432 POSTGRES_DB=smartem_db \
    POSTGRES_USER=username POSTGRES_PASSWORD=password \
    python -m alembic upgrade head

echo "[6/10] Replaying files FIRST (post-acquisition mode)..."
python ./tools/fsrecorder/fsrecorder.py replay \
    --max-delay "$MAX_DELAY" \
    "$RECORDING" \
    "$EPU_DIR" \
    > "$TEST_DIR/logs/playback.log" 2>&1
echo "Playback complete. Files are now in place."

echo "[7/10] Checking if port 8000 is free..."
if lsof -ti:8000 >/dev/null 2>&1; then
    echo "ERROR: Port 8000 is already in use!"
    echo "Killing process on port 8000..."
    lsof -ti:8000 | xargs kill -9
    sleep 2
fi

echo "[8/10] Starting API and consumer..."
python -m uvicorn smartem_backend.api_server:app \
    --host 127.0.0.1 --port 8000 --log-level debug \
    > "$TEST_DIR/logs/api.log" 2>&1 &
API_PID=$!
sleep 3

# Verify API started successfully
if ! curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "ERROR: API failed to start! Check $TEST_DIR/logs/api.log"
    tail -20 "$TEST_DIR/logs/api.log"
    exit 1
fi
echo "API started successfully"

python -m smartem_backend.consumer -vv \
    > "$TEST_DIR/logs/consumer.log" 2>&1 &
CONSUMER_PID=$!
sleep 2

echo "[9/10] Starting agent v2 to process existing files..."
python -m smartem_agent watch \
    --api-url http://localhost:8000 \
    -vv \
    "$EPU_DIR" \
    > "$TEST_DIR/logs/agent.log" 2>&1 &
AGENT_PID=$!

echo "Agent v2 started. Waiting for processing to complete (60 seconds)..."
sleep 60

echo ""
echo "===== Test Results ====="

# Count filesystem entities
echo "Filesystem Counts:"
EPU_SESSIONS=$(find "$EPU_DIR" -name "EpuSession.dm" 2>/dev/null | wc -l)
GRIDSQUARES=$(find "$EPU_DIR" -type d -name "GridSquare_*" 2>/dev/null | wc -l)
echo "  EPU Sessions: $EPU_SESSIONS"
echo "  GridSquare directories: $GRIDSQUARES"

# Get database counts
echo ""
echo "Database Counts:"
python -c "
import requests
try:
    acq_response = requests.get('http://127.0.0.1:8000/acquisitions')
    acquisitions = acq_response.json()
    if acquisitions:
        acq_uuid = acquisitions[0]['uuid']
        stats_response = requests.get(f'http://127.0.0.1:8000/acquisitions/{acq_uuid}/stats')
        stats = stats_response.json()
        print(f'  Acquisitions: {len(acquisitions)}')
        print(f'  Grids: {stats.get(\"grids\", 0)}')
        print(f'  Grid Squares: {stats.get(\"gridsquares\", 0)}')
        print(f'  Foil Holes: {stats.get(\"foilholes\", 0)}')
    else:
        print('  No acquisitions found')
except Exception as e:
    print(f'  Error: {e}')
"

echo ""
echo "Test completed. Results saved to: $TEST_DIR"
echo "Agent log: $TEST_DIR/logs/agent.log"
echo ""

# Check for common issues
AGENT_LOG_SIZE=$(wc -c < "$TEST_DIR/logs/agent.log")
if [ "$AGENT_LOG_SIZE" -lt 1000 ]; then
    echo "WARNING: Agent log is very small ($AGENT_LOG_SIZE bytes) - agent may have failed to start!"
    echo "Check $TEST_DIR/logs/agent.log for errors"
fi
