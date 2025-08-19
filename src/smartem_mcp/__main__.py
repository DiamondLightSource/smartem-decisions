"""
SmartEM MCP Command Line Interface

Provides command-line access to SmartEM MCP server and client functionality.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from smartem_mcp._version import __version__
from smartem_mcp.client import SmartEMMCPClient, SmartEMQueryInterface
from smartem_mcp.server import SmartEMMCPServer


async def run_server(args):
    """Run MCP server"""
    logging.basicConfig(level=getattr(logging, args.log_level))

    server = SmartEMMCPServer(api_base_url=args.api_url)
    await server.serve()


async def run_client(args):
    """Run client commands"""
    logging.basicConfig(level=getattr(logging, args.log_level))

    async with SmartEMMCPClient() as client:
        if args.client_command == "parse":
            if not args.path:
                print("Error: --path required for parse command")
                return 1

            result = await client.parse_epu_directory(args.path)
            if args.json:
                print(json.dumps(result.model_dump(), indent=2))
            else:
                if result.success:
                    data = result.data or {}
                    print(f"✅ Successfully parsed EPU directory: {args.path}")
                    print(f"   Grids: {data.get('grid_count', 0)}")
                    print(f"   Grid squares: {data.get('total_gridsquares', 0)}")
                    if data.get("acquisition"):
                        print(f"   Acquisition: {data['acquisition'].get('name', 'Unknown')}")
                else:
                    print(f"❌ Failed to parse directory: {result.error}")
                    return 1

        elif args.client_command == "quality":
            if not args.path:
                print("Error: --path required for quality command")
                return 1

            result = await client.find_low_quality_items(args.path, args.threshold, args.source)
            if args.json:
                print(json.dumps(result.model_dump(), indent=2))
            else:
                if result.success:
                    data = result.data or {}
                    items = data.get("low_quality_items", [])
                    print(f"✅ Quality analysis complete (threshold: {args.threshold})")
                    print(f"   Found {len(items)} low-quality items")
                    if items:
                        for item in items[:5]:  # Show first 5
                            print(f"   - {item}")
                        if len(items) > 5:
                            print(f"   ... and {len(items) - 5} more")
                else:
                    print(f"❌ Quality analysis failed: {result.error}")
                    return 1

        elif args.client_command == "acquisitions":
            result = await client.query_recent_acquisitions(args.limit)
            if args.json:
                print(json.dumps(result.model_dump(), indent=2))
            else:
                if result.success:
                    data = result.data or {}
                    acquisitions = data.get("acquisitions", [])
                    print(f"✅ Found {len(acquisitions)} recent acquisitions")
                    for acq in acquisitions:
                        print(f"   - {acq.get('name', 'Unknown')} (ID: {acq.get('id', 'N/A')})")
                else:
                    print(f"❌ Failed to query acquisitions: {result.error}")
                    return 1

        elif args.client_command == "grid":
            if not args.grid_id:
                print("Error: --grid-id required for grid command")
                return 1

            result = await client.get_grid_status(args.grid_id)
            if args.json:
                print(json.dumps(result.model_dump(), indent=2))
            else:
                if result.success:
                    data = result.data or {}
                    grid = data.get("grid", {})
                    print(f"✅ Grid {args.grid_id} status:")
                    print(f"   Status: {grid.get('status', 'Unknown')}")
                    print(f"   Created: {grid.get('created_at', 'Unknown')}")
                else:
                    print(f"❌ Failed to get grid status: {result.error}")
                    return 1

        else:
            print(f"Unknown client command: {args.client_command}")
            return 1

    return 0


async def run_interactive(args):
    """Run interactive query mode"""
    logging.basicConfig(level=getattr(logging, args.log_level))

    interface = SmartEMQueryInterface()
    print(f"SmartEM Interactive Query Interface v{__version__}")
    print("Ask questions about your microscopy data!")
    print("Examples:")
    print("  - 'Show me a summary of session /path/to/epu'")
    print("  - 'Find low quality items in /path/to/epu with threshold 0.3'")
    print("  - 'What are the recent acquisitions?'")
    print()

    try:
        while True:
            question = input("❓ Your question: ").strip()
            if question.lower() in ["exit", "quit", "q"]:
                break

            if not question:
                continue

            # Extract context from question
            context = {}
            if "/path/to/" in question or question.startswith("/"):
                # Simple path extraction
                words = question.split()
                for word in words:
                    if word.startswith("/") and Path(word).exists():
                        context["path"] = word
                        break

            if "threshold" in question:
                try:
                    # Extract threshold value
                    import re

                    match = re.search(r"threshold\s*(\d*\.?\d+)", question)
                    if match:
                        context["threshold"] = float(match.group(1))
                except ValueError:
                    pass

            try:
                answer = await interface.ask(question, context)
                print(f"🔍 {answer}")
            except Exception as e:
                print(f"❌ Error processing question: {str(e)}")

            print()

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

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
            return asyncio.run(run_server(args))
        elif args.mode == "client":
            return asyncio.run(run_client(args))
        elif args.mode == "interactive":
            return asyncio.run(run_interactive(args))
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
