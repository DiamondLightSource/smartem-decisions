#!/usr/bin/env python3

import argparse
import json
import sys
from datetime import datetime

import httpx

"""Usage: `./tests/check_smartem_core_http_api.py http://localhost:8000 -v`"""


def check_api_status(base_url, timeout=5, verbose=False):
    endpoints = [f"{base_url.rstrip('/')}/status", f"{base_url.rstrip('/')}/health"]

    for endpoint in endpoints:
        try:
            if verbose:
                print(f"Checking {endpoint}...")

            start_time = datetime.now()
            response = httpx.get(endpoint, timeout=timeout)
            elapsed = (datetime.now() - start_time).total_seconds()

            if response.status_code < 400:
                if verbose:
                    print(f"SUCCESS: {endpoint} responded with status code {response.status_code} in {elapsed:.3f}s")
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                return True, endpoint, response.status_code, elapsed, response.json()
            else:
                if verbose:
                    print(f"ERROR: {endpoint} responded with status code {response.status_code}")
                continue

        except httpx.RequestError as e:
            if verbose:
                print(f"ERROR: Failed to connect to {endpoint}: {str(e)}")
            continue

    return False, None, None, None, None


def main():
    parser = argparse.ArgumentParser(description="Check if SmartEM API is up and running")
    parser.add_argument("url", help="Base URL of the API (e.g. http://localhost:8000)")
    parser.add_argument("-t", "--timeout", type=int, default=5, help="Timeout in seconds (default: 5)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    is_up, endpoint, status_code, response_time, response_data = check_api_status(
        args.url, timeout=args.timeout, verbose=args.verbose
    )

    if is_up:
        status = response_data.get("status", "unknown")
        version = response_data.get("version", "unknown")
        timestamp = response_data.get("timestamp", "unknown")

        print(f"SmartEM API is UP - {endpoint} responded with {status_code} in {response_time:.3f}s")
        print(f"   Status: {status}, Version: {version}, Time: {timestamp}")
        sys.exit(0)
    else:
        print("SmartEM API is DOWN - all endpoints failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
