# Run an end-to-end simulation in development

To simulate all system components running together in a development environment, follow these steps in order. Each component should be run in a separate terminal tab/window and left running in the background.

## Prerequisites

1. **Activate virtual environment** in every terminal before proceeding:
   ```bash
   source .venv/bin/activate
   ```

2. **Verify test recordings exist**:
   ```bash
   ls -la ../smartem-decisions-test-recordings/
   ```
   Available recordings:
   - `bi37600-29_fsrecord.tar.gz`
   - `bi37708-42_fsrecord.tar.gz` (recommended for testing)

3. **Prepare output directory** for playback:
   ```bash
   mkdir -p ../epu-test-dir
   ```

## Step 1: Launch backend infrastructure services

Deploy PostgreSQL, RabbitMQ, and containerised API/worker services:

```bash
./tools/dev-k8s.sh up
```

**Expected output**: All pods should show as "Running" with services accessible on:
- SmartEM API: http://localhost:30080/docs
- RabbitMQ Management: http://localhost:30673
- Adminer Database UI: http://localhost:30808

**Verification**:
```bash
curl -s http://localhost:30080/status
```

## Step 2: Launch local consumer (optional)

If you want to run a local consumer instead of the containerised worker:

```bash
RABBITMQ_URL=amqp://guest:guest@localhost:30672/ python -m smartem_backend.consumer  # pragma: allowlist secret
```

**Note**: The containerised deployment already includes a worker, so this step is optional.

## Step 3: Launch SmartEM agent in watch mode

Configure the agent to connect to the containerised API:

```bash
python -m smartem_agent watch --api-url http://localhost:30080 ../epu-test-dir
```

**Expected output**:
```
INFO - Initialized SmartEM API client with base URL: http://localhost:30080
INFO - API is reachable at http://localhost:30080 - Status: ...
```

## Step 4: Start session recording playback

Begin the microscopy data simulation:

```bash
python ./tools/fsrecorder/fsrecorder.py replay ../smartem-decisions-test-recordings/bi37708-42_fsrecord.tar.gz ../epu-test-dir/ | tee epu-test-dir.log
```

**Expected behaviour**:
- Progress updates showing file creation events
- Files being created in `../epu-test-dir/atlas/...`
- SmartEM agent detecting file changes and sending data to API
- Database records being created (visible via API endpoints)

## Monitoring the simulation

1. **Check API status and data**:
   ```bash
   curl -s http://localhost:30080/status | jq
   curl -s http://localhost:30080/acquisitions | jq
   ```

2. **Monitor file system activity**:
   ```bash
   watch -n 2 "find ../epu-test-dir -type f | wc -l"
   ```

3. **View logs**:
   - Recording playback: `tail -f epu-test-dir.log`
   - Kubernetes pods: `kubectl logs -f deployment/smartem-http-api -n smartem-decisions`

## Troubleshooting

### Agent connection issues
- Ensure agent uses `--api-url http://localhost:30080` (not the default port 8000)
- Check API accessibility: `curl http://localhost:30080/status`

### Backend services not starting
- Check k3s permissions: ensure you can run `kubectl get pods`
- Verify Docker registry access in `.dev.env` configuration
- Check pod status: `kubectl get pods -n smartem-decisions`

### Consumer connection issues
- Use correct RabbitMQ URL: `RABBITMQ_URL=amqp://guest:guest@localhost:30672/` <!-- pragma: allowlist secret -->
- Verify RabbitMQ is accessible: `curl http://localhost:30673` (management UI)

### Recording playback issues
- Ensure recording file exists and is readable
- Check target directory permissions: `ls -la ../epu-test-dir`
- Monitor playback progress in log file

## Success criteria

A successful end-to-end simulation should show:

1. ✅ All backend services running (check with `kubectl get pods -n smartem-decisions`)
2. ✅ SmartEM agent connected to API (check agent logs)
3. ✅ Recording playback creating files (check `../epu-test-dir` contents)
4. ✅ API receiving data (check `curl http://localhost:30080/acquisitions`)
5. ✅ Files being processed and stored in database

## Cleanup

To stop all services:

```bash
# Stop backend services
./tools/dev-k8s.sh down

# Kill background processes
pkill -f smartem_agent
pkill -f smartem_backend.consumer
pkill -f fsrecorder

# Clean up test data (optional)
rm -rf ../epu-test-dir
rm -f epu-test-dir.log
```
