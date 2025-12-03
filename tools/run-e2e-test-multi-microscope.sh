#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/../.." && pwd)"
cd "$PROJECT_ROOT"

# Defaults assume multi-repo workspace structure:
#   <workspace>/DiamondLightSource/smartem-decisions/  (this repo)
#   <workspace>/testdata/recordings/                   (test recordings)
#   <workspace>/tmp/                                   (scratch space)
# Override with env vars: SMARTEM_TEST_RECORDING, SMARTEM_EPU_DIR
DEFAULT_RECORDING="$WORKSPACE_ROOT/testdata/recordings/bi37708-42_fsrecord.tar.gz"
DEFAULT_EPU_DIR="$WORKSPACE_ROOT/tmp/epu-test-dir"

NUM_MICROSCOPES="${1:-3}"
RECORDING="${2:-${SMARTEM_TEST_RECORDING:-$DEFAULT_RECORDING}}"
EPU_BASE_DIR="${3:-${SMARTEM_EPU_DIR:-$DEFAULT_EPU_DIR}}"
MAX_DELAY="${4:-0.1}"
TEST_DIR="$PROJECT_ROOT/logs/e2e-tests/$(date +%Y-%m-%d_%H%M%S)_multi-microscope-test"

echo "===== SmartEM Multi-Microscope E2E Test Runner ====="
echo "Number of Microscopes: $NUM_MICROSCOPES"
echo "Recording: $RECORDING"
echo "EPU Base Directory: $EPU_BASE_DIR"
echo "Max Delay: ${MAX_DELAY}s"
echo "Test Results: $TEST_DIR"
echo "===================================================="

declare -a EPU_DIRS
declare -a AGENT_IDS
declare -a SESSION_IDS
declare -a PLAYBACK_PIDS
declare -a AGENT_PIDS

cleanup() {
    echo ""
    echo "Cleaning up background processes..."
    pkill -f "smartem_backend|smartem_agent|fsrecorder|uvicorn" || true

    echo "Cleaning up playback data directories..."
    for epu_dir in "${EPU_DIRS[@]}"; do
        rm -rf "$epu_dir" || true
    done

    echo "Cleanup complete"
}

trap cleanup EXIT

echo ""
echo "[1/11] Setting up test environment..."
mkdir -p "$TEST_DIR/logs"

for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    epu_dir="${EPU_BASE_DIR}-microscope-${i}"
    mkdir -p "$epu_dir"
    rm -rf "$epu_dir"/*
    EPU_DIRS+=("$epu_dir")

    AGENT_IDS+=("microscope-titan-$(printf "%02d" $i)")
    SESSION_IDS+=("session-$(date +%Y%m%d-%H%M%S)-$(printf "%03d" $i)")

    echo "  Microscope $i:"
    echo "    Agent ID: ${AGENT_IDS[$((i-1))]}"
    echo "    Session ID: ${SESSION_IDS[$((i-1))]}"
    echo "    EPU Directory: ${EPU_DIRS[$((i-1))]}"
done

echo ""
echo "[2/11] Activating virtual environment..."
source .venv/bin/activate

echo "[3/11] Loading environment variables..."
set -a
source .env.local-test-run
set +a

echo "[4/11] Resetting database..."
POSTGRES_HOST=localhost POSTGRES_PORT=30432 POSTGRES_DB=postgres \
    POSTGRES_USER=username POSTGRES_PASSWORD=password \
    python -m smartem_backend.model.database

echo "[5/11] Running database migrations..."
POSTGRES_HOST=localhost POSTGRES_PORT=30432 POSTGRES_DB=smartem_db \
    POSTGRES_USER=username POSTGRES_PASSWORD=password \
    python -m alembic upgrade head

echo "[6/11] Checking if port 8000 is free..."
if lsof -ti:8000 >/dev/null 2>&1; then
    echo "ERROR: Port 8000 is already in use!"
    echo "Killing process on port 8000..."
    lsof -ti:8000 | xargs kill -9
    sleep 2
fi

echo "[7/11] Starting backend API server..."
python -m uvicorn smartem_backend.api_server:app \
    --host 127.0.0.1 --port 8000 --log-level debug \
    > "$TEST_DIR/logs/api.log" 2>&1 &
API_PID=$!
sleep 3

if ! curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "ERROR: API failed to start! Check $TEST_DIR/logs/api.log"
    tail -20 "$TEST_DIR/logs/api.log"
    exit 1
fi
echo "API started successfully (PID: $API_PID)"

echo "[8/11] Starting backend consumer..."
python -m smartem_backend.consumer -vv \
    > "$TEST_DIR/logs/consumer.log" 2>&1 &
CONSUMER_PID=$!
sleep 2
echo "Consumer started (PID: $CONSUMER_PID)"

echo "[9/11] Starting $NUM_MICROSCOPES agent instances..."
for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    agent_id="${AGENT_IDS[$((i-1))]}"
    session_id="${SESSION_IDS[$((i-1))]}"
    epu_dir="${EPU_DIRS[$((i-1))]}"

    echo "  Starting agent $i: $agent_id / $session_id"
    python -m smartem_agent watch \
        --api-url http://localhost:8000 \
        --agent-id "$agent_id" \
        --session-id "$session_id" \
        -vv \
        "$epu_dir" \
        > "$TEST_DIR/logs/agent-${i}.log" 2>&1 &
    AGENT_PIDS+=($!)

    sleep 1
done

echo "[10/11] Starting $NUM_MICROSCOPES concurrent playback instances..."
for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    epu_dir="${EPU_DIRS[$((i-1))]}"

    echo "  Starting playback $i to $epu_dir"
    python ./tools/fsrecorder/fsrecorder.py replay \
        --max-delay "$MAX_DELAY" \
        "$RECORDING" \
        "$epu_dir" \
        > "$TEST_DIR/logs/playback-${i}.log" 2>&1 &
    PLAYBACK_PIDS+=($!)

    sleep 0.5
done

echo ""
echo "All playback instances started. Waiting for completion..."
for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    playback_pid="${PLAYBACK_PIDS[$((i-1))]}"
    echo "  Waiting for playback $i (PID: $playback_pid)..."
    wait "$playback_pid" || echo "  Warning: Playback $i exited with non-zero status"
done

echo ""
echo "All playback complete. Waiting for agents to finish processing (60 seconds)..."
sleep 60

echo ""
echo "[11/11] Collecting test results..."
echo ""
echo "===== Test Results ====="

echo ""
echo "Filesystem Counts:"
for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    epu_dir="${EPU_DIRS[$((i-1))]}"
    agent_id="${AGENT_IDS[$((i-1))]}"

    EPU_SESSIONS=$(find "$epu_dir" -name "EpuSession.dm" 2>/dev/null | wc -l)
    GRIDSQUARES=$(find "$epu_dir" -type d -name "GridSquare_*" 2>/dev/null | wc -l)

    echo "  Microscope $i ($agent_id):"
    echo "    EPU Sessions: $EPU_SESSIONS"
    echo "    GridSquare directories: $GRIDSQUARES"
done

echo ""
echo "Database Counts (per acquisition):"
python -c "
import requests
import sys

try:
    acq_response = requests.get('http://127.0.0.1:8000/acquisitions')
    acquisitions = acq_response.json()

    if not acquisitions:
        print('  No acquisitions found')
        sys.exit(0)

    print(f'  Total acquisitions: {len(acquisitions)}')
    print()

    for idx, acq in enumerate(acquisitions, 1):
        acq_uuid = acq['uuid']
        instrument_id = acq.get('instrument_id', 'unknown')

        stats_response = requests.get(f'http://127.0.0.1:8000/acquisitions/{acq_uuid}/stats')
        stats = stats_response.json()

        print(f'  Acquisition {idx} ({instrument_id}):')
        print(f'    UUID: {acq_uuid}')
        print(f'    Grids: {stats.get(\"grids\", 0)}')
        print(f'    Grid Squares: {stats.get(\"gridsquares\", 0)}')
        print(f'    Foil Holes: {stats.get(\"foilholes\", 0)}')
        print()

except Exception as e:
    print(f'  Error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "Agent Session Information:"
python -c "
import requests
import sys

try:
    response = requests.get('http://127.0.0.1:8000/agent/sessions')
    sessions = response.json()

    if not sessions:
        print('  No agent sessions found')
        sys.exit(0)

    print(f'  Total agent sessions: {len(sessions)}')
    print()

    for idx, session in enumerate(sessions, 1):
        print(f'  Session {idx}:')
        print(f'    Agent ID: {session.get(\"agent_id\")}')
        print(f'    Session ID: {session.get(\"session_id\")}')
        print(f'    Acquisition UUID: {session.get(\"acquisition_uuid\")}')
        print(f'    Status: {session.get(\"status\")}')
        print()

except Exception as e:
    print(f'  Error: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "===== Data Separation Verification ====="
echo ""
python -c "
import requests
import sys

try:
    acq_response = requests.get('http://127.0.0.1:8000/acquisitions')
    acquisitions = acq_response.json()

    if len(acquisitions) < 2:
        print('  Warning: Less than 2 acquisitions found. Cannot verify data separation.')
        sys.exit(0)

    print(f'  Found {len(acquisitions)} acquisitions.')
    print()

    grids_by_acq = {}
    for acq in acquisitions:
        acq_uuid = acq['uuid']
        grids_response = requests.get(f'http://127.0.0.1:8000/acquisitions/{acq_uuid}/grids')
        grids = grids_response.json()
        grids_by_acq[acq_uuid] = set(g['uuid'] for g in grids)

    all_grids = [grid_uuid for grids in grids_by_acq.values() for grid_uuid in grids]
    if len(all_grids) != len(set(all_grids)):
        print('  ERROR: Found duplicate grids across acquisitions!')
        sys.exit(1)

    overlap_found = False
    acq_list = list(grids_by_acq.items())
    for i in range(len(acq_list)):
        for j in range(i+1, len(acq_list)):
            acq_uuid_1, grids_1 = acq_list[i]
            acq_uuid_2, grids_2 = acq_list[j]
            overlap = grids_1 & grids_2
            if overlap:
                print(f'  ERROR: Acquisitions {acq_uuid_1[:8]} and {acq_uuid_2[:8]} share {len(overlap)} grids!')
                overlap_found = True

    if not overlap_found:
        print('  SUCCESS: All acquisitions have completely separate data.')
        print('  No grid UUID overlaps detected between acquisitions.')

except Exception as e:
    print(f'  Error during verification: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
echo "===== Test Summary ====="
echo ""
echo "Test completed. Results saved to: $TEST_DIR"
echo ""
echo "Log files:"
for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    echo "  Agent $i log: $TEST_DIR/logs/agent-${i}.log"
    echo "  Playback $i log: $TEST_DIR/logs/playback-${i}.log"
done
echo "  API log: $TEST_DIR/logs/api.log"
echo "  Consumer log: $TEST_DIR/logs/consumer.log"
echo ""

for ((i=1; i<=NUM_MICROSCOPES; i++)); do
    AGENT_LOG_SIZE=$(wc -c < "$TEST_DIR/logs/agent-${i}.log")
    if [ "$AGENT_LOG_SIZE" -lt 1000 ]; then
        echo "WARNING: Agent $i log is very small ($AGENT_LOG_SIZE bytes) - agent may have failed to start!"
        echo "Check $TEST_DIR/logs/agent-${i}.log for errors"
    fi
done

echo ""
echo "To review detailed results, examine:"
echo "  - Database counts per acquisition"
echo "  - Agent session associations"
echo "  - Data separation verification"
echo ""
