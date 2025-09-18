# Configure Logging and Verbosity

All SmartEM services support configurable logging levels to help with debugging and reduce noise in production environments.

## Command Line Verbosity

Use the `-v` and `-vv` flags to control verbosity across all SmartEM components:

### Backend Services
```bash
# ERROR level only (default - minimal output)
python -m smartem_backend.consumer
python -m smartem_backend.api_server

# INFO level and above (-v flag)
python -m smartem_backend.consumer -v
python -m smartem_backend.api_server -v

# DEBUG level and above (-vv flag - most verbose)
python -m smartem_backend.consumer -vv
python -m smartem_backend.api_server -vv
```

### SmartEM Agent CLI
All agent commands support consistent verbosity flags:

```bash
# ERROR level only (default - minimal output)
python -m smartem_agent watch /path/to/data
python -m smartem_agent validate /path/to/data
python -m smartem_agent parse dir /path/to/data

# INFO level and above (-v flag)
python -m smartem_agent watch /path/to/data -v
python -m smartem_agent validate /path/to/data -v
python -m smartem_agent parse session /path/to/EpuSession.dm -v

# DEBUG level and above (-vv flag - most verbose)
python -m smartem_agent watch /path/to/data -vv
python -m smartem_agent parse dir /path/to/data -vv
```

### Agent-Specific Logging Features

The watch command provides additional logging controls:

```bash
# Custom log file and interval
python -m smartem_agent watch /data \
  --log-file /var/log/smartem/agent.log \
  --log-interval 30.0 \
  -v

# Real-time communication logging
python -m smartem_agent watch /data \
  --agent-id microscope-01 \
  --session-id session-123 \
  --heartbeat-interval 60 \
  -vv  # Shows heartbeat and SSE communication details
```

## Environment Variable Control

For the HTTP API, you can also control logging via environment variables:

```bash
# Set log level via environment variable (equivalent to -v/-vv flags)
SMARTEM_LOG_LEVEL=ERROR python -m smartem_backend.api_server
SMARTEM_LOG_LEVEL=INFO python -m smartem_backend.api_server 
SMARTEM_LOG_LEVEL=DEBUG python -m smartem_backend.api_server
```

## Log Levels

- **ERROR** (default): Only critical errors are shown
- **INFO** (`-v`): Informational messages, warnings, and errors
- **DEBUG** (`-vv`): All messages including detailed debugging information

## Log Content by Component

### Backend Services (ERROR level)
- Database connection errors
- API startup failures
- Critical system errors

### Backend Services (INFO level)
- Service startup and shutdown
- API request summaries
- Database connection status
- Configuration information

### Backend Services (DEBUG level)
- Individual API request details
- Database query execution
- Message queue operations
- Detailed error stack traces

### SmartEM Agent (ERROR level)
- File access permission errors
- API connection failures
- Critical parsing errors

### SmartEM Agent (INFO level)
- File detection and processing
- Grid square and foil hole creation
- API communication status
- SSE connection events
- Heartbeat transmission status

### SmartEM Agent (DEBUG level)
- Individual file parsing details
- Filesystem event monitoring
- Detailed API request/response data
- SSE message content
- Heartbeat timing information
- Connection retry attempts

## Production Logging Recommendations

### Development Environment
```bash
# Use DEBUG level for comprehensive troubleshooting
python -m smartem_agent watch /data -vv
python -m smartem_backend.api_server -vv
```

### Testing Environment
```bash
# Use INFO level for verification without noise
python -m smartem_agent watch /data -v
python -m smartem_backend.api_server -v
```

### Production Environment
```bash
# Use ERROR level (default) for minimal logging overhead
python -m smartem_agent watch /data
python -m smartem_backend.api_server

# Or INFO level with log rotation for operational monitoring
python -m smartem_agent watch /data \
  --log-file /var/log/smartem/agent.log \
  --log-interval 60.0 \
  -v
```

## Log File Management

### Structured Logging
The agent's `--log-file` parameter creates structured JSON logs suitable for analysis:

```json
{
  "timestamp": "2024-01-15T14:30:22.123456",
  "event_count": 5,
  "events": [
    {
      "timestamp": "2024-01-15T14:30:22.120000",
      "event_type": "created",
      "source_path": "/data/Grid_001/EpuSession.dm",
      "relative_path": "Grid_001/EpuSession.dm",
      "size": 2048,
      "modified": "2024-01-15T14:30:22.119000"
    }
  ]
}
```

### Log Rotation and Management
```bash
# Use logrotate or similar tools for production log management
# Example logrotate configuration:
/var/log/smartem/agent.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
}
```

This verbosity control system helps reduce log noise during normal operation while providing detailed output when troubleshooting issues. The structured logging format facilitates automated monitoring and analysis of system behaviour.
