# Configure Logging and Verbosity

All SmartEM Backend services support configurable logging levels to help with debugging and reduce noise in production environments.

## Command Line Verbosity

Use the `-v` and `-vv` flags to control verbosity:

```bash
# ERROR level only (default - minimal output)
python -m smartem_backend.consumer
python -m smartem_backend.run_api
python -m smartem_agent watch /path/to/data

# INFO level and above (-v flag)
python -m smartem_backend.consumer -v
python -m smartem_backend.run_api -v
python -m smartem_agent watch /path/to/data -v

# DEBUG level and above (-vv flag - most verbose)
python -m smartem_backend.consumer -vv
python -m smartem_backend.run_api -vv
python -m smartem_agent watch /path/to/data -vv
```

## Environment Variable Control

For the HTTP API, you can also control logging via environment variables:

```bash
# Set log level via environment variable (equivalent to -v/-vv flags)
SMARTEM_LOG_LEVEL=ERROR python -m smartem_backend.run_api
SMARTEM_LOG_LEVEL=INFO python -m smartem_backend.run_api 
SMARTEM_LOG_LEVEL=DEBUG python -m smartem_backend.run_api
```

## Log Levels

- **ERROR** (default): Only critical errors are shown
- **INFO** (`-v`): Informational messages, warnings, and errors
- **DEBUG** (`-vv`): All messages including detailed debugging information

This verbosity control helps reduce log noise during normal operation while providing detailed output when troubleshooting issues.
