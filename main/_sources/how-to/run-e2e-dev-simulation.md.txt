# End-to-End Development Test Runs

This document describes the complete workflow for running repeatable end-to-end tests of the SmartEM system using pre-recorded microscope sessions. It serves as both a runbook for executing tests and a reference for understanding test requirements.

## Quick Start (Resume from Previous Session)

If you've already set up once and just need to run another test:

```bash
# 1. Ensure k3s is running
./tools/dev-k8s.sh status

# 2. Prepare clean environment
unset POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
unset RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USER RABBITMQ_PASSWORD
unset HTTP_API_HOST HTTP_API_PORT
set -a && source .env.local-test-run && set +a

# 3. Create timestamped test directory
TEST_DIR="/tmp/e2e-test-results/$(date +%Y-%m-%d_%H%M%S)_test-type-name"
mkdir -p "$TEST_DIR/logs"

# 4. Kill any running processes
pkill -f "smartem_backend\|smartem_agent\|fsrecorder\|uvicorn\|fastapi" || true

# 5. Restart RabbitMQ (ensures empty queue)
kubectl rollout restart deployment/rabbitmq -n smartem-decisions
kubectl rollout status deployment/rabbitmq -n smartem-decisions

# 6. Reset database
source .venv/bin/activate
python -m smartem_backend.model.database

# 7. Clean playback directory
rm -rf ../epu-test-dir && mkdir -p ../epu-test-dir

# 8. Start services (choose a test type below, or see Test Execution Scenarios section)
# Example: Test Type 1 - Post-acquisition
python -m fastapi dev src/smartem_backend/api_server.py --host 127.0.0.1 --port 8000 2>&1 | tee "$TEST_DIR/logs/api.log" &
python -m smartem_backend.consumer -vv 2>&1 | tee "$TEST_DIR/logs/consumer.log" &
sleep 3

# Run playback (default is --fast mode, no flag needed)
python ./tools/fsrecorder/fsrecorder.py replay \
  ~/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/playback.log"

# Start agent after playback completes
python -m smartem_agent watch --api-url http://localhost:8000 -vv ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/agent.log"
```

**For detailed explanations, first-time setup, or different test scenarios, see sections below.**

---

## Overview

The test setup simulates a complete SmartEM workflow:
- **Local k3s cluster**: Runs PostgreSQL and RabbitMQ services
- **Host OS services**: Runs SmartEM backend API and worker for easier debugging
- **Microscope simulation**: Plays back pre-recorded microscopy sessions
- **Agent monitoring**: SmartEM agent watches for file changes and processes data

## Prerequisites

### Environment Setup
- Python 3.12+ with venv activated: `source .venv/bin/activate`
- Full development install: `pip install -e .[all]`
- Local k3s cluster running: `./tools/dev-k8s.sh up`
- Environment file: `.env.local-test-run` (created manually - see Environment File Setup below)

### Test Data
Pre-recorded microscope sessions are stored in `~/dev/DLS/smartem-decisions-test-recordings/`:
- `bi37600-29_fsrecord.tar.gz`
- `bi37708-42_fsrecord.tar.gz` (recommended for testing, 8389 events)

**Note**: Path should be absolute or relative to working directory (`smartem-decisions/`)

### Directory Structure
```
/tmp/e2e-test-results/           # Test results root (gitignored)
  YYYY-MM-DD_HHmmss_test-type/   # Individual test run
    logs/                        # All log outputs (4 services)
      playback.log               # Microscope recording playback
      agent.log                  # SmartEM agent
      api.log                    # Backend HTTP API
      consumer.log               # Backend worker/consumer
    db-dump.sql                  # Database state after test
    test-params.json             # Test configuration used
```

### Environment File Setup
The `.env.local-test-run` file configures services to run on host OS while connecting to k3s infrastructure.

**Source for initial values**: Copy from `.dev.env` (used by `./tools/dev-k8s.sh` for development cluster)

**Required configuration**:
- PostgreSQL: Point to k3s NodePort `localhost:30432`
- RabbitMQ: Point to k3s NodePort `localhost:30672`
- Backend API: Run on host OS (typically `127.0.0.1:8000`)
- Agent: Run on host OS

**Example `.env.local-test-run`**:
```bash
# Database connection (k3s NodePort)
POSTGRES_HOST=localhost
POSTGRES_PORT=30432
POSTGRES_DB=smartem_db
POSTGRES_USER=username
POSTGRES_PASSWORD=password

# RabbitMQ connection (k3s NodePort)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=30672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Backend API (host OS)
HTTP_API_HOST=127.0.0.1
HTTP_API_PORT=8000
```

**Usage**: `source .env.local-test-run` before starting services

## Database Operations

### Creating Fresh Database
Run `database.py` to drop all tables and recreate schema with indexes:
```bash
source .venv/bin/activate
python -m smartem_backend.model.database
```

**Note**: This script uses `_create_db_and_tables()` which:
1. Drops all existing tables and custom enum types
2. Creates all tables from SQLModel definitions
3. Creates all indexes for optimal query performance
4. Does NOT require Alembic migrations

### Connecting to Database
From host OS (using k3s NodePort mappings):
```bash
# Connection details (from .env.local-test-run)
POSTGRES_HOST=localhost
POSTGRES_PORT=30432
POSTGRES_DB=smartem_db
POSTGRES_USER=username
POSTGRES_PASSWORD=password

# Example: Dump database for test results
pg_dump -h localhost -p 30432 -U username -d smartem_db > /tmp/e2e-test-results/TIMESTAMP/db-dump.sql
```

## RabbitMQ Queue Management

### Queue Behaviour
- Queue name: `smartem_backend` (configured in `src/smartem_backend/appconfig.yml`)
- Queue is declared with `durable=True` by both publisher and consumer
- Queue persists across reconnections but NOT across RabbitMQ service restarts
- **Important**: Queue is NOT recreated empty on each connection - existing messages persist

### Verifying Queue State
Access RabbitMQ management UI:
```bash
# RabbitMQ management interface (if enabled in k3s)
# Check k8s service for management UI port mapping
# Default credentials: guest/guest  # pragma: allowlist secret
```

### Cleaning Queue Between Tests
**Option 1**: Restart RabbitMQ service (recommended for clean state):
```bash
kubectl rollout restart deployment/rabbitmq -n smartem-decisions
kubectl rollout status deployment/rabbitmq -n smartem-decisions
```

**Option 2**: Purge queue programmatically (if needed):
```python
# Add to teardown script if queue purging is required
# This would need to be implemented in utils.py
```

## Service Commands

**IMPORTANT - Environment Variables**:
All services use `load_dotenv(override=False)` which loads `.env` by default but doesn't override already-set variables.
For testing, you MUST export variables from `.env.local-test-run` before starting services:

```bash
# Unset any previously loaded env vars to avoid conflicts
unset POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
unset RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USER RABBITMQ_PASSWORD
unset HTTP_API_HOST HTTP_API_PORT

# Load test environment (exports all variables)
set -a
source .env.local-test-run
set +a
```

### Backend HTTP API

**Option 1: FastAPI CLI (recommended for development)**
```bash
source .venv/bin/activate
python -m fastapi dev src/smartem_backend/api_server.py \
  --host 127.0.0.1 \
  --port 8000 2>&1 | tee /tmp/e2e-test-results/TIMESTAMP/logs/api.log
```
- Auto-reload on code changes
- Default development mode
- Clean output

**Option 2: Uvicorn (more control over logging)**
```bash
source .venv/bin/activate
python -m uvicorn smartem_backend.api_server:app \
  --host 127.0.0.1 \
  --port 8000 \
  --log-level debug 2>&1 | tee /tmp/e2e-test-results/TIMESTAMP/logs/api.log
```
- **Log level options**: `critical`, `error`, `warning`, `info`, `debug`, `trace`
- More verbose logging control
- Use for debugging

**Note**: Both read database and RabbitMQ connection details from environment variables

### Backend Worker/Consumer
```bash
source .venv/bin/activate
export RABBITMQ_URL=amqp://guest:guest@localhost:30672/  # pragma: allowlist secret
python -m smartem_backend.consumer -vv 2>&1 | tee /tmp/e2e-test-results/TIMESTAMP/logs/consumer.log
```
**Verbosity flags**: `-v` for INFO, `-vv` for DEBUG

### SmartEM Agent
```bash
source .venv/bin/activate
python -m smartem_agent watch \
  --api-url http://localhost:30080 \
  --verbose -v \
  ../epu-test-dir 2>&1 | tee /tmp/e2e-test-results/TIMESTAMP/logs/agent.log
```

**Verbosity flags**: `-v` for INFO, `-vv` for DEBUG
**Agent options**:
- `--agent-id TEXT`: Agent identifier for SSE connection
- `--session-id TEXT`: Session identifier for SSE connection
- `--sse-timeout INTEGER`: SSE connection timeout in seconds (default: 30)
- `--heartbeat-interval INTEGER`: Agent heartbeat interval in seconds (default: 60)

### Microscope Playback (fsrecorder)

**Tool location**: `./tools/fsrecorder/fsrecorder.py` (relative to repo root)

**Command syntax**:
```bash
source .venv/bin/activate
python ./tools/fsrecorder/fsrecorder.py replay \
  ~/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz \
  ../epu-test-dir 2>&1 | tee /tmp/e2e-test-results/TIMESTAMP/logs/playback.log
```

**Important**:
- Use `replay` subcommand (NOT `--mode replay` or `--mode player`)
- First positional argument is the recording file (`.tar.gz`, not `.events`)
- Second positional argument is the target directory (no trailing slash needed)
- Recording file path should be absolute (`~/dev/DLS/...`) or relative to current directory

**Speed control options** (from `--help`):
- Default behavior: `--fast` mode (100x speed, 1s max delays) - **enabled by default**
- `--dev-mode`: Maximum speed for rapid iteration (1000x + burst) - quick smoke tests
- `--fast`: Balanced acceleration (100x + 1s delays) - same as default
- `--exact`: Preserve original timing (1x speed) - debug timing issues
- `-s SPEED, --speed SPEED`: Custom speed multiplier
- `--max-delay MAX_DELAY`: Maximum delay between events in seconds
- `--burst`: Process events as fast as possible

**Additional options**:
- `--no-verify`: Skip integrity verification
- `--skip-unreadable`: Skip files that were unreadable during recording

**Example usage**:
```bash
# Default fast mode (no flag needed)
python ./tools/fsrecorder/fsrecorder.py replay recording.tar.gz ../output-dir

# Dev mode for rapid testing
python ./tools/fsrecorder/fsrecorder.py replay --dev-mode recording.tar.gz ../output-dir

# Exact timing for debugging
python ./tools/fsrecorder/fsrecorder.py replay --exact recording.tar.gz ../output-dir
```

## Test Preparation Workflow

### 1. Backup Previous Test Logs
```bash
# If previous test exists, logs are already in /tmp/e2e-test-results/PREVIOUS_TIMESTAMP/
# No action needed - each test creates its own timestamped directory
```

### 2. Prepare Test Environment
```bash
# 1. Unset any previously loaded environment variables
unset POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
unset RABBITMQ_HOST RABBITMQ_PORT RABBITMQ_USER RABBITMQ_PASSWORD
unset HTTP_API_HOST HTTP_API_PORT

# 2. Load test environment variables (export all)
set -a
source .env.local-test-run
set +a

# 3. Create test results directory with timestamp
TEST_DIR="/tmp/e2e-test-results/$(date +%Y-%m-%d_%H%M%S)_test-type-name"
mkdir -p "$TEST_DIR/logs"

# 4. Stop any running services from previous test
pkill -f smartem_backend.api
pkill -f smartem_backend.consumer
pkill -f smartem_agent
pkill -f fsrecorder
pkill -f uvicorn
pkill -f fastapi

# 5. Verify k3s services are running
./tools/dev-k8s.sh status

# 6. Clean RabbitMQ (restart to ensure empty queue)
kubectl rollout restart deployment/rabbitmq -n smartem-decisions
kubectl rollout status deployment/rabbitmq -n smartem-decisions

# 7. Drop and recreate database
source .venv/bin/activate
python -m smartem_backend.model.database

# 8. Clean playback output directory
rm -rf ../epu-test-dir
mkdir -p ../epu-test-dir
```

### 3. Verify Prerequisites
```bash
# Check test recordings exist
ls -lh ~/dev/DLS/smartem-decisions-test-recordings/

# Verify k3s services accessible
curl -s http://localhost:30080/status || echo "API not ready yet"

# Check database connectivity
psql -h localhost -p 30432 -U username -d smartem_db -c "SELECT version();"
```

## Test Execution Scenarios

### Test Type 1: Post-Acquisition Data Intake
**Scenario**: Agent starts watching after playback completes (easiest, should work)

```bash
# 1. Start backend services (ensure env vars are already exported from prep step)
python -m fastapi dev src/smartem_backend/api_server.py --host 127.0.0.1 --port 8000 2>&1 | tee "$TEST_DIR/logs/api.log" &
python -m smartem_backend.consumer -vv 2>&1 | tee "$TEST_DIR/logs/consumer.log" &

# Wait a moment for services to start
sleep 3

# 2. Run playback to completion (no agent watching yet)
python ./tools/fsrecorder/fsrecorder.py replay \
  ~/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/playback.log"

# 3. Wait for playback to finish, then start agent
python -m smartem_agent watch \
  --api-url http://localhost:8000 \
  -vv \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/agent.log"
```

### Test Type 2: Pre-Acquisition Agent Setup
**Scenario**: Agent starts watching before any data exists

```bash
# 1. Start backend services
python -m fastapi dev src/smartem_backend/api_server.py --host 127.0.0.1 --port 8000 2>&1 | tee "$TEST_DIR/logs/api.log" &
python -m smartem_backend.consumer -vv 2>&1 | tee "$TEST_DIR/logs/consumer.log" &

# Wait a moment for services to start
sleep 3

# 2. Start agent watching empty directory
python -m smartem_agent watch \
  --api-url http://localhost:8000 \
  -vv \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/agent.log" &

# 3. Begin playback after agent is watching
python ./tools/fsrecorder/fsrecorder.py replay \
  ~/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/playback.log"
```

### Test Type 3: Mid-Acquisition Agent Start
**Scenario**: Agent starts after playback begins but before completion (tests handling existing + new data)

**Timing considerations**:
- Playback script initially extracts data from recording (no files written yet)
- After extraction, playback begins writing files to output directory
- Agent should start after some files exist but before playback completes
- Use different delays to test at various stages of data availability

```bash
# 1. Start backend services
python -m fastapi dev src/smartem_backend/api_server.py --host 127.0.0.1 --port 8000 2>&1 | tee "$TEST_DIR/logs/api.log" &
python -m smartem_backend.consumer -vv 2>&1 | tee "$TEST_DIR/logs/consumer.log" &

# Wait a moment for services to start
sleep 3

# 2. Start playback first
python ./tools/fsrecorder/fsrecorder.py replay \
  ~/dev/DLS/smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/playback.log" &

# 3. Monitor file creation to choose optimal start time
watch -n 1 "find ../epu-test-dir -type f | wc -l"

# 4. When desired number of files exist, start agent
# Experiment with different timing:
#   - sleep 5   # Very early (minimal files)
#   - sleep 15  # Early-mid stage
#   - sleep 30  # Mid-stage
#   - sleep 60  # Late stage
sleep 15  # Adjust based on monitoring above

python -m smartem_agent watch \
  --api-url http://localhost:8000 \
  -vv \
  ../epu-test-dir 2>&1 | tee "$TEST_DIR/logs/agent.log"
```

## Post-Test Data Collection

After test completion, capture all relevant data for analysis:

```bash
# 1. Database dump (final state after all processing)
pg_dump -h localhost -p 30432 -U username -d smartem_db > "$TEST_DIR/db-dump.sql"

# 2. Create test parameters record
cat > "$TEST_DIR/test-params.json" << EOF
{
  "test_type": "post-acquisition",
  "timestamp": "$(date -Iseconds)",
  "recording": "bi37708-42_fsrecord.tar.gz",
  "playback_mode": "fast",
  "agent_verbosity": "debug",
  "consumer_verbosity": "debug",
  "api_log_level": "debug",
  "notes": "Testing data intake after microscope session completes"
}
EOF

# 3. Verify all 4 service logs were captured
ls -lh "$TEST_DIR/logs/"
# Expected files:
#   - playback.log  (microscope recording playback)
#   - agent.log     (SmartEM agent)
#   - api.log       (backend HTTP API)
#   - consumer.log  (backend worker/consumer)

# 4. Optional: Capture k8s infrastructure logs if debugging issues
kubectl logs deployment/postgres -n smartem-decisions > "$TEST_DIR/logs/postgres.log"
kubectl logs deployment/rabbitmq -n smartem-decisions > "$TEST_DIR/logs/rabbitmq.log"
```

**Critical logs for analysis**:
1. **playback.log**: File creation timeline, extraction timing
2. **agent.log**: File detection, API communication, SSE events
3. **api.log**: HTTP requests, database writes, SSE connections
4. **consumer.log**: RabbitMQ message processing, prediction updates
5. **db-dump.sql**: Final database state (acquisitions, grids, predictions)

## Monitoring and Verification

### During Test Execution

**Check file creation**:
```bash
watch -n 2 "find ../epu-test-dir -type f | wc -l"
```

**Monitor API status**:
```bash
# Check acquisitions being created
curl -s http://localhost:8000/acquisitions | jq

# Check overall status
curl -s http://localhost:8000/status | jq
```

**Watch logs in real-time**:
```bash
tail -f "$TEST_DIR/logs/agent.log"
tail -f "$TEST_DIR/logs/consumer.log"
tail -f "$TEST_DIR/logs/playback.log"
```

### Success Criteria

A successful test should demonstrate:
- ✅ All backend services start without errors
- ✅ RabbitMQ queue is empty at test start
- ✅ Database is freshly created with no leftover data
- ✅ Playback creates expected files in output directory
- ✅ Agent detects file changes and sends data to API
- ✅ API receives and stores data in database
- ✅ Worker processes messages from queue
- ✅ No errors in any service logs
- ✅ Database contains expected entities after test

## Cleanup and Teardown

### Stop Running Services
```bash
# Stop all test-related processes
pkill -f smartem_backend.api
pkill -f smartem_backend.consumer
pkill -f smartem_agent
pkill -f fsrecorder

# Verify processes stopped
pgrep -f "smartem_backend|smartem_agent|fsrecorder"
```

### Optional: Full Teardown
```bash
# Clean playback directory
rm -rf ../epu-test-dir

# Stop k3s cluster (if needed)
./tools/dev-k8s.sh down
```

## Troubleshooting

### Database Connection Issues
```bash
# Verify k3s postgres is accessible
kubectl get pods -n smartem-decisions
kubectl logs deployment/postgres -n smartem-decisions

# Test connection
psql -h localhost -p 30432 -U username -d smartem_db -c "\l"
```

### RabbitMQ Connection Issues
```bash
# Check RabbitMQ pod status
kubectl get pods -n smartem-decisions
kubectl logs deployment/rabbitmq -n smartem-decisions

# Verify connection from host
curl -u guest:guest http://localhost:30673  # pragma: allowlist secret
```

### Agent Not Detecting Files
- Ensure `--api-url http://localhost:8000` points to correct API endpoint
- Check agent logs for connection errors
- Verify playback is writing to the directory agent is watching
- Confirm file permissions allow agent to read files

### Consumer Not Processing Messages
- Verify `RABBITMQ_URL=amqp://guest:guest@localhost:30672/` is correct  <!-- pragma: allowlist secret -->
- Check queue has messages waiting
- Review consumer logs for connection errors
- Ensure database is accessible to worker

## Known Issues and Notes

**RabbitMQ Queue Persistence**:
- Queue `smartem_backend` is durable and persists messages across connections
- **If multiple workers are started, they may compete for messages** - verify this is intended behaviour
- Restarting RabbitMQ service is currently the cleanest way to ensure empty queue between tests
- Consider implementing programmatic queue purging if restart is too slow

## Notes for Future Refinement

This document will evolve as we:
- Complete missing command details
- Identify optimal test parameters
- Discover edge cases during testing
- Convert manual steps into automation scripts
- Potentially create custom slash commands for common workflows
