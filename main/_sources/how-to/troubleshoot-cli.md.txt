# SmartEM CLI Troubleshooting Guide

This guide provides solutions for common issues encountered when using the SmartEM Agent command-line interface. For comprehensive parameter documentation, see the [CLI Reference](../reference/cli-reference.md).

## Quick Diagnostics

### Check CLI Installation
```bash
# Verify the CLI is accessible
python -m smartem_agent --help

# Check version and dependencies
python -c "import smartem_agent; print('SmartEM Agent available')"
```

### Test Basic Functionality
```bash
# Test with a known good directory
python -m smartem_agent validate /path/to/test/data

# Test API connectivity
python -m smartem_agent watch /tmp --dry-run --verbose
```

## Common Issues and Solutions

### 1. Command Not Found Errors

#### Error: `No module named 'smartem_agent'`

**Cause:** SmartEM Agent package is not installed or not in Python path.

**Solutions:**
```bash
# Install in development mode
pip install -e .

# Install with all dependencies
pip install -e .[all]

# Verify installation
pip list | grep smartem
```

**Alternative:** Use the full path to the module:
```bash
PYTHONPATH=/path/to/smartem-decisions/src python -m smartem_agent --help
```

#### Error: `python: can't open file 'smartem_agent'`

**Cause:** Trying to run as a script instead of a module.

**Solution:** Use the module syntax:
```bash
# Correct
python -m smartem_agent watch /data

# Incorrect
python smartem_agent watch /data
```

### 2. Directory and File Access Issues

#### Error: `Directory /path/to/data does not exist`

**Diagnosis:**
```bash
# Check if directory exists
ls -la /path/to/data

# Check parent directory
ls -la /path/to/

# Verify current working directory
pwd
```

**Solutions:**
- Use absolute paths: `/full/path/to/directory`
- Verify directory spelling and case sensitivity
- Check directory permissions: `ls -ld /path/to/data`

#### Error: `Permission denied`

**Cause:** Insufficient permissions to read directories or write log files.

**Solutions:**
```bash
# Check directory permissions
ls -la /path/to/data

# Check write permissions for log file location
touch /path/to/logfile.log && rm /path/to/logfile.log

# Run with appropriate permissions
sudo python -m smartem_agent watch /data  # Use sparingly

# Better: Fix directory permissions
chmod -R 755 /path/to/data
chown -R $USER:$GROUP /path/to/data
```

#### Error: Files not being detected during watch

**Diagnosis:**
```bash
# Test with verbose output
python -m smartem_agent watch /data --dry-run -vv

# Check file patterns match
find /data -name "EpuSession.dm" -o -name "*.xml"

# Monitor filesystem events manually
inotifywait -m -r /data
```

**Solutions:**
- Verify file patterns match EPU naming conventions
- Check for symbolic links that might not be followed
- Ensure files are completely written before processing
- Consider filesystem-specific issues (NFS, network drives)

### 3. API Connection Problems

#### Error: `API at http://127.0.0.1:8000 is not reachable`

**Diagnosis:**
```bash
# Test basic connectivity
curl -v http://127.0.0.1:8000/status

# Check if service is running
netstat -tlnp | grep 8000

# Test from Python
python -c "import requests; print(requests.get('http://127.0.0.1:8000/status').json())"
```

**Solutions:**

1. **Start the backend API:**
   ```bash
   cd /path/to/smartem-decisions
   python -m smartem_backend.api_server
   ```

2. **Use correct API URL:**
   ```bash
   # Local development
   python -m smartem_agent watch /data --api-url http://localhost:8000

   # Remote server
   python -m smartem_agent watch /data --api-url https://smartem.example.com/api
   ```

3. **Network connectivity issues:**
   - Check firewall settings
   - Verify proxy configuration
   - Test with different network interfaces
   - Use `--dry-run` for offline testing

#### Error: `SSE connection failed` or `Failed to send heartbeat`

**Diagnosis:**
```bash
# Test SSE endpoint manually
curl -H "Accept: text/event-stream" \
     http://127.0.0.1:8000/agent/test-agent/session/test-session/instructions/stream

# Check heartbeat endpoint
curl -X POST \
     -H "Content-Type: application/json" \
     http://127.0.0.1:8000/agent/test-agent/session/test-session/heartbeat
```

**Solutions:**

1. **Verify agent and session IDs:**
   ```bash
   # Ensure IDs exist in backend
   python -m smartem_agent watch /data \
     --agent-id valid-agent-id \
     --session-id valid-session-id
   ```

2. **Adjust timeout settings:**
   ```bash
   # Increase timeouts for unstable connections
   python -m smartem_agent watch /data \
     --agent-id agent-01 \
     --session-id session-01 \
     --sse-timeout 120 \
     --heartbeat-interval 30
   ```

3. **Check backend logs:**
   - Monitor backend API logs for connection errors
   - Verify database connectivity
   - Check for authentication issues

### 4. Parsing and Validation Errors

#### Error: `Grid data dir is structurally invalid`

**Diagnosis:**
```bash
# Get detailed validation errors
python -m smartem_agent validate /path/to/grid -vv

# Check directory structure
find /path/to/grid -type f -name "*.dm" -o -name "*.xml" | head -20
```

**Common Issues:**
- Missing `EpuSession.dm` file
- Incorrect directory naming conventions
- Incomplete or corrupted files
- Wrong directory structure (not EPU format)

**Solutions:**
- Verify the directory contains valid EPU data
- Check for required files: `EpuSession.dm`, `Atlas/Atlas.dm`
- Ensure directory structure matches EPU conventions
- Use `parse dir` command to identify specific parsing issues

#### Error: `Could not extract instrument info` or parsing failures

**Diagnosis:**
```bash
# Test individual file parsing
python -m smartem_agent parse session /path/to/EpuSession.dm -vv

# Check file integrity
file /path/to/EpuSession.dm
hexdump -C /path/to/EpuSession.dm | head -5
```

**Solutions:**
- Verify files are not corrupted or partially written
- Check file permissions and accessibility
- Ensure files are in expected format (not binary corrupted)
- Look for encoding issues or special characters in paths

### 5. Performance and Resource Issues

#### Issue: High memory usage or slow processing

**Diagnosis:**
```bash
# Monitor resource usage
top -p $(pgrep -f "smartem_agent")
htop

# Check directory size
du -sh /path/to/data
find /path/to/data -type f | wc -l
```

**Solutions:**

1. **Optimise logging settings:**
   ```bash
   # Reduce logging frequency
   python -m smartem_agent watch /data --log-interval 30.0

   # Reduce verbosity
   python -m smartem_agent watch /data  # No -v flags
   ```

2. **Process smaller datasets:**
   ```bash
   # Process single grids instead of entire sessions
   python -m smartem_agent watch /data/Grid_001
   ```

3. **System resource limits:**
   ```bash
   # Increase file descriptor limits
   ulimit -n 4096

   # Monitor disk space
   df -h /path/to/data
   ```

#### Issue: `OSError: [Errno 24] Too many open files`

**Solutions:**
```bash
# Check current limits
ulimit -a

# Increase file descriptor limit temporarily
ulimit -n 4096

# Increase permanently (add to ~/.bashrc)
echo "ulimit -n 4096" >> ~/.bashrc
```

### 6. Logging and Output Issues

#### Issue: No log output or missing log files

**Diagnosis:**
```bash
# Check log file permissions
ls -la fs_changes.log

# Verify log directory exists
ls -la $(dirname /path/to/custom.log)

# Test with different log location
python -m smartem_agent watch /data --log-file /tmp/test.log
```

**Solutions:**
- Ensure log directory exists and is writable
- Use absolute paths for log files
- Check disk space availability
- Verify SELinux/AppArmor policies if applicable

#### Issue: Verbose output not showing

**Solutions:**
```bash
# Ensure correct verbose syntax
python -m smartem_agent watch /data -v      # INFO level
python -m smartem_agent watch /data -vv     # DEBUG level

# Check if output is being redirected
python -m smartem_agent watch /data -v 2>&1 | tee output.log
```

### 7. Signal Handling and Process Management

#### Issue: Process doesn't stop gracefully with Ctrl+C

**Solutions:**
```bash
# Send SIGTERM for graceful shutdown
pkill -TERM -f "smartem_agent"

# Force kill if necessary
pkill -9 -f "smartem_agent"

# Use timeout for automatic termination
timeout 3600 python -m smartem_agent watch /data  # Stop after 1 hour
```

#### Issue: Background process monitoring

**Solutions:**
```bash
# Run in background with nohup
nohup python -m smartem_agent watch /data > smartem.log 2>&1 &

# Use screen or tmux for persistent sessions
screen -S smartem
python -m smartem_agent watch /data

# Monitor process status
ps aux | grep smartem_agent
```

## Advanced Troubleshooting

### Debug Mode Activation

Enable maximum debugging output:
```bash
python -m smartem_agent watch /data \
  --dry-run \
  --verbose --verbose \
  --log-interval 1.0 \
  --heartbeat-interval 10 \
  --sse-timeout 10
```

### Network Debugging

**Test connectivity chain:**
```bash
# 1. Basic network connectivity
ping backend-host

# 2. Port connectivity
telnet backend-host 8000

# 3. HTTP connectivity
curl -v http://backend-host:8000/status

# 4. SSE connectivity
curl -v -H "Accept: text/event-stream" \
     http://backend-host:8000/agent/test/session/test/instructions/stream
```

### File System Monitoring Debug

**Manual file monitoring:**
```bash
# Install inotify-tools (Linux)
sudo apt-get install inotify-tools

# Monitor directory changes
inotifywait -m -r --format '%w%f %e %T' --timefmt '%Y-%m-%d %H:%M:%S' /data

# Compare with agent detection
python -m smartem_agent watch /data --dry-run -vv
```

### Database Connectivity Issues

**Test database connection (if using persistent storage):**
```bash
# Check database connectivity
psql -h database-host -U username -d smartem_db -c "SELECT 1;"

# Verify tables exist
psql -h database-host -U username -d smartem_db -c "\\dt"

# Check for connection pooling issues
netstat -an | grep :5432
```

## Environment-Specific Issues

### Windows Specific

**Path separator issues:**
```bash
# Use forward slashes or raw strings
python -m smartem_agent watch "C:/data/microscopy"
python -m smartem_agent watch C:\\data\\microscopy
```

**Service account permissions:**
- Ensure service account has appropriate file system access
- Check Windows Defender exclusions for monitoring directories
- Verify no Group Policy restrictions on file access

### Linux/Unix Specific

**Permission issues:**
```bash
# Check SELinux status
sestatus

# Check AppArmor status
sudo apparmor_status

# Verify no systemd restrictions
systemctl status user@$(id -u).service
```

**NFS mounted directories:**
```bash
# Check mount options
mount | grep nfs

# Test with local directory first
python -m smartem_agent watch /tmp/test_data --dry-run
```

### Container/Docker Environments

**Volume mounting issues:**
```bash
# Verify volume mounts
docker exec container-id ls -la /data

# Check container permissions
docker exec container-id id
docker exec container-id ls -la /data
```

**Network connectivity in containers:**
```bash
# Test from within container
docker exec container-id curl http://backend:8000/status

# Check container networking
docker network ls
docker inspect network-name
```

## Getting Additional Help

### Collecting Diagnostic Information

Create a diagnostic script:
```bash
#!/bin/bash
echo "=== System Information ==="
uname -a
python --version

echo "=== SmartEM Agent Status ==="
python -c "import smartem_agent; print('Available')" 2>&1

echo "=== Directory Information ==="
ls -la /path/to/data

echo "=== Network Connectivity ==="
curl -s http://127.0.0.1:8000/status 2>&1 || echo "API not reachable"

echo "=== Process Information ==="
ps aux | grep smartem

echo "=== Resource Usage ==="
free -h
df -h
```

### Log Analysis

**Extract relevant log entries:**
```bash
# Filter for errors
grep -i error fs_changes.log

# Filter by time range
awk '/2024-01-15 14:00:00/,/2024-01-15 15:00:00/' fs_changes.log

# Analyse patterns
grep "Heartbeat sent" fs_changes.log | tail -20
```

### Reporting Issues

When reporting issues, include:

1. **Command used:** Full command line with parameters
2. **Error message:** Complete error output
3. **Environment:** OS, Python version, installation method
4. **Directory structure:** Sample of the directory being processed
5. **Logs:** Relevant log entries with timestamps
6. **Network information:** API URLs, connectivity status
7. **System resources:** Available memory, disk space

**Example issue report:**
```
Command: python -m smartem_agent watch /data/Grid_001 --agent-id microscope-01 --session-id session-123 -v

Error: SSE connection failed: Connection refused

Environment:
- OS: Ubuntu 20.04 LTS
- Python: 3.12.1
- Installation: pip install -e .[all]

Directory: /data/Grid_001 (contains EpuSession.dm, 15 GridSquare directories)

API Status: curl http://127.0.0.1:8000/status returns {"status": "ok"}

Logs: (attach relevant log entries)
```

This comprehensive troubleshooting guide should resolve most common CLI issues. For backend-specific problems, consult the SmartEM Backend documentation.
