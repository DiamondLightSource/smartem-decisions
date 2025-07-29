#!/usr/bin/env python3
"""
Script to run the SmartEM Decisions HTTP API with verbosity controls.

Usage:
    python -m smartem_decisions.run_api               # ERROR level (default)
    python -m smartem_decisions.run_api -v           # INFO level
    python -m smartem_decisions.run_api -vv          # DEBUG level
"""

import argparse
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Run SmartEM Decisions HTTP API")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v for INFO, -vv for DEBUG)"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")

    args = parser.parse_args()

    # Set log level based on verbosity
    if args.verbose >= 2:  # Debug level -vv
        log_level = "DEBUG"
    elif args.verbose == 1:  # Info level -v
        log_level = "INFO"
    else:  # Default - only errors
        log_level = "ERROR"

    # Set environment variable for the HTTP API
    os.environ["SMARTEM_LOG_LEVEL"] = log_level

    # Get port from environment if set, otherwise use CLI arg
    port = os.getenv("HTTP_API_PORT", str(args.port))

    print(f"Starting SmartEM Decisions API with log level: {log_level}")
    print(f"Server will be available at http://{args.host}:{port}")

    # Run uvicorn with the API
    cmd = [sys.executable, "-m", "uvicorn", "src.smartem_decisions.http_api:app", "--host", args.host, "--port", port]

    # Set uvicorn log level based on our verbosity
    if args.verbose >= 2:
        cmd.extend(["--log-level", "debug"])
    elif args.verbose == 1:
        cmd.extend(["--log-level", "info"])
    else:
        cmd.extend(["--log-level", "error"])

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down API server...")
    except subprocess.CalledProcessError as e:
        print(f"Error running API server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
