"""
SmartEM MCP Command Line Interface using FastMCP

Provides command-line access to SmartEM MCP server and client functionality.
"""

import argparse
import asyncio
import json
import logging
import sys

from smartem_mcp._version import __version__
from smartem_mcp.client import SmartEMMCPClient


async def run_client(args):
    """Run client commands"""
    logging.basicConfig(level=getattr(logging, args.log_level))

    async with SmartEMMCPClient() as client:
        if args.client_command == "parse":
            if not args.path:
                print("Error: --path required for parse command")
                return 1

            try:
                result = await client.parse_epu_directory(args.path)
                if args.json:
                    print(json.dumps(result, indent=2, default=str))
                else:
                    print(f"Successfully parsed EPU directory: {args.path}")
                    print(f"   Grids: {result.get('grid_count', 0)}")
                    print(f"   Grid squares: {result.get('total_gridsquares', 0)}")
                    if result.get("acquisition"):
                        print(f"   Acquisition: {result['acquisition'].get('name', 'Unknown')}")
            except Exception as e:
                print(f"Failed to parse directory: {str(e)}")
                return 1

        elif args.client_command == "quality":
            if not args.path:
                print("Error: --path required for quality command")
                return 1

            try:
                result = await client.find_low_quality_items(args.path, args.threshold, args.source)
                if args.json:
                    print(json.dumps(result, indent=2, default=str))
                else:
                    items = result.get("low_quality_items", [])
                    print(f"Quality analysis complete (threshold: {args.threshold})")
                    print(f"   Found {len(items)} low-quality items")
                    if items:
                        for item in items[:5]:  # Show first 5
                            print(f"   - {item}")
                        if len(items) > 5:
                            print(f"   ... and {len(items) - 5} more")
            except Exception as e:
                print(f"Quality analysis failed: {str(e)}")
                return 1

        elif args.client_command == "acquisitions":
            try:
                result = await client.query_recent_acquisitions(args.limit)
                if args.json:
                    print(json.dumps(result, indent=2, default=str))
                else:
                    acquisitions = result.get("acquisitions", [])
                    print(f"Found {len(acquisitions)} recent acquisitions")
                    for acq in acquisitions:
                        print(f"   - {acq.get('name', 'Unknown')} (ID: {acq.get('id', 'N/A')})")
            except Exception as e:
                print(f"Failed to query acquisitions: {str(e)}")
                return 1

        elif args.client_command == "grid":
            if not args.grid_id:
                print("Error: --grid-id required for grid command")
                return 1

            try:
                result = await client.get_grid_status(args.grid_id)
                if args.json:
                    print(json.dumps(result, indent=2, default=str))
                else:
                    grid = result.get("grid", {})
                    print(f"Grid {args.grid_id} status:")
                    print(f"   Status: {grid.get('status', 'Unknown')}")
                    print(f"   Created: {grid.get('created_at', 'Unknown')}")
            except Exception as e:
                print(f"Failed to get grid status: {str(e)}")
                return 1

        else:
            print(f"Unknown client command: {args.client_command}")
            return 1

    return 0


async def run_interactive(args):
    """Run interactive query mode"""
    logging.basicConfig(level=getattr(logging, args.log_level))

    print(f"SmartEM Interactive Query Interface v{__version__}")
    print("Execute direct tool calls against the MCP server!")
    print("Available tools: parse_epu_directory, query_quality_metrics, query_acquisitions, query_grid_status")
    print("Examples:")
    print("  parse /path/to/epu")
    print("  quality /path/to/epu 0.3")
    print("  acquisitions 10")
    print("  grid <grid-id>")
    print()

    client = SmartEMMCPClient()

    try:
        while True:
            command = input("❓ Tool command: ").strip()
            if command.lower() in ["exit", "quit", "q"]:
                break

            if not command:
                continue

            parts = command.split()
            tool_cmd = parts[0].lower()

            try:
                if tool_cmd == "parse" and len(parts) >= 2:
                    path = parts[1]
                    result = await client.parse_epu_directory(path)
                    grid_count = result.get("grid_count", 0)
                    total_squares = result.get("total_gridsquares", 0)
                    print(f"   Parsed {grid_count} grids, {total_squares} grid squares")

                elif tool_cmd == "quality" and len(parts) >= 2:
                    path = parts[1]
                    threshold = float(parts[2]) if len(parts) > 2 else 0.5
                    result = await client.find_low_quality_items(path, threshold)
                    items = result.get("low_quality_items", [])
                    print(f"   Found {len(items)} low-quality items (threshold: {threshold})")

                elif tool_cmd == "acquisitions":
                    limit = int(parts[1]) if len(parts) > 1 else 10
                    result = await client.query_recent_acquisitions(limit)
                    acquisitions = result.get("acquisitions", [])
                    print(f"   Found {len(acquisitions)} recent acquisitions")

                elif tool_cmd == "grid" and len(parts) >= 2:
                    grid_id = parts[1]
                    result = await client.get_grid_status(grid_id)
                    grid = result.get("grid", {})
                    print(f"   Grid {grid_id}: {grid.get('status', 'Unknown')}")

                else:
                    print("Invalid command format")
                    print("Use: parse <path> | quality <path> [threshold] | acquisitions [limit] | grid <id>")

            except Exception as e:
                print(f"Error: {str(e)}")

            print()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        await client.disconnect()

    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SmartEM MCP - Natural language interface to microscopy data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start MCP server
  python -m smartem_mcp server --api-url http://localhost:30080

  # Parse EPU directory
  python -m smartem_mcp client parse --path /path/to/epu/session

  # Find low quality items
  python -m smartem_mcp client quality --path /path/to/epu --threshold 0.3

  # Query recent acquisitions
  python -m smartem_mcp client acquisitions --limit 10

  # Interactive mode
  python -m smartem_mcp interactive
        """,
    )

    parser.add_argument("--version", action="version", version=f"SmartEM MCP v{__version__}")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Logging level"
    )

    subparsers = parser.add_subparsers(dest="mode", help="Mode to run")

    # Server mode
    server_parser = subparsers.add_parser("server", help="Run MCP server")
    server_parser.add_argument("--api-url", default="http://localhost:30080", help="SmartEM API base URL")

    # Client mode
    client_parser = subparsers.add_parser("client", help="Run client commands")
    client_subparsers = client_parser.add_subparsers(dest="client_command", help="Client command")

    # Parse command
    parse_parser = client_subparsers.add_parser("parse", help="Parse EPU directory")
    parse_parser.add_argument("--path", required=True, help="Path to EPU directory")
    parse_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Quality command
    quality_parser = client_subparsers.add_parser("quality", help="Analyze quality metrics")
    quality_parser.add_argument("--path", required=True, help="Path to EPU directory")
    quality_parser.add_argument("--threshold", type=float, default=0.5, help="Quality threshold")
    quality_parser.add_argument("--source", choices=["filesystem", "api"], default="filesystem", help="Data source")
    quality_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Acquisitions command
    acq_parser = client_subparsers.add_parser("acquisitions", help="Query acquisitions")
    acq_parser.add_argument("--limit", type=int, default=10, help="Number of acquisitions")
    acq_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Grid command
    grid_parser = client_subparsers.add_parser("grid", help="Get grid status")
    grid_parser.add_argument("--grid-id", required=True, help="Grid UUID")
    grid_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Interactive mode
    subparsers.add_parser("interactive", help="Interactive query mode")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        return 1

    try:
        if args.mode == "server":
            # Run server with proper argument passing
            from smartem_mcp.server import init_api_client

            logging.basicConfig(level=getattr(logging, args.log_level))

            # Initialize API client
            api_connected = init_api_client(args.api_url)
            if api_connected:
                logger = logging.getLogger(__name__)
                logger.info("Initialized SmartEM API client")
            else:
                logger = logging.getLogger(__name__)
                logger.warning("Could not initialize SmartEM API client - some features may be limited")

            # Import the mcp instance and run it
            from smartem_mcp.server import mcp

            return asyncio.run(mcp.run())
        elif args.mode == "client":
            return asyncio.run(run_client(args))
        elif args.mode == "interactive":
            return asyncio.run(run_interactive(args))
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
