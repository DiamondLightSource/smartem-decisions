#!/usr/bin/env python
"""
SmartEM MCP Demo - Show off the natural language interface

This is a demonstration script showcasing MCP capabilities.
Run with: python tools/mcp_demo.py

For actual testing, see tests/smartem_mcp/
"""

import asyncio

from smartem_mcp.client import SmartEMQueryInterface
from smartem_mcp.server import FilesystemAdapter


class MockMCPClient:
    """Mock client that bypasses MCP protocol for demo purposes"""

    async def session_summary(self, path):
        adapter = FilesystemAdapter()
        result = await adapter.parse_epu_directory(path)

        if result.success and result.data:
            data = result.data
            return {
                "session_path": path,
                "acquisition_name": data.get("acquisition", {}).get("name", "Unknown"),
                "grid_count": data.get("grid_count", 0),
                "total_gridsquares": data.get("total_gridsquares", 0),
                "success": True,
            }
        else:
            return {"error": result.error, "success": False}

    async def quality_report(self, path, threshold):
        adapter = FilesystemAdapter()
        result = await adapter.query_quality_metrics(path, threshold)

        if result.success and result.data:
            data = result.data
            return {
                "quality_threshold": threshold,
                "low_quality_count": len(data.get("low_quality_items", [])),
                "items": data.get("low_quality_items", []),
                "success": True,
            }
        else:
            return {"error": result.error, "success": False}

    async def query_recent_acquisitions(self, limit):
        return {"success": False, "error": "API not available in demo mode - would normally query SmartEM API"}


async def demo_natural_language_queries():
    """Demonstrate natural language querying capabilities"""

    print("🎭 SmartEM MCP Natural Language Interface Demo")
    print("=" * 60)

    # Use test dataset
    test_path = (
        "/home/vredchenko/dev/DLS/smartem-decisions-test-datasets/bi37708-28-copy/"
        "Supervisor_20250129_134723_36_bi37708-28_grid7_EPU"
    )

    interface = SmartEMQueryInterface(client=MockMCPClient())

    # Demo queries
    queries = [
        {
            "question": "Show me a session summary",
            "context": {"path": test_path},
            "description": "Get high-level overview of microscopy session",
        },
        {
            "question": "Find low quality items with threshold 0.5",
            "context": {"path": test_path, "threshold": 0.5},
            "description": "Analyze quality metrics for troubleshooting",
        },
        {
            "question": "What are the recent acquisitions?",
            "context": {},
            "description": "Query recent microscopy sessions (would use API)",
        },
    ]

    for i, query in enumerate(queries, 1):
        print(f"\nExample {i}: {query['description']}")
        print(f' Question: "{query["question"]}"')

        try:
            answer = await interface.ask(query["question"], query["context"])
            print(f" Answer: {answer}")
        except Exception as e:
            print(f" Error: {str(e)}")

        print("-" * 40)


async def demo_direct_queries():
    """Show direct filesystem adapter queries"""

    print("\n Direct SmartEM Data Queries")
    print("=" * 60)

    adapter = FilesystemAdapter()
    test_path = (
        "/home/vredchenko/dev/DLS/smartem-decisions-test-datasets/bi37708-28-copy/"
        "Supervisor_20250129_134723_36_bi37708-28_grid7_EPU"
    )

    # 1. Parse EPU directory
    print("\n Parsing EPU Directory Structure...")
    result = await adapter.parse_epu_directory(test_path)

    if result.success:
        data = result.data or {}
        print("   Success!")
        print(f"      Grids: {data.get('grid_count', 0)}")
        print(f"      Grid squares: {data.get('total_gridsquares', 0)}")

        if data.get("grids"):
            grid = data["grids"][0]
            print(f"      Grid UUID: {grid.get('uuid', 'N/A')}")
            print(f"      Data directory: {grid.get('data_dir', 'N/A')}")
    else:
        print(f" Failed: {result.error}")

    # 2. Quality analysis
    print("\n Quality Metrics Analysis...")
    for threshold in [0.3, 0.5, 0.8]:
        quality_result = await adapter.query_quality_metrics(test_path, threshold)
        if quality_result.success:
            quality_data = quality_result.data or {}
            count = len(quality_data.get("low_quality_items", []))
            print(f"   Threshold {threshold}: {count} low-quality items")


def show_mcp_capabilities():
    """Show what the MCP interface can do"""

    print("\n   SmartEM MCP Capabilities")
    print("=" * 60)

    capabilities = [
        " Parse EPU microscopy directories",
        " Natural language querying of session data",
        " Quality metrics analysis and filtering",
        "  Grid square and foil hole enumeration",
        " Integration with SmartEM API (when available)",
        " Interactive command-line interface",
        " Claude Code MCP protocol integration",
        " Both filesystem and API data sources",
    ]

    for capability in capabilities:
        print(f"  {capability}")

    print("\n   Available Tools:")
    tools = [
        "parse_epu_directory - Extract comprehensive session data",
        "query_quality_metrics - Find low-quality items",
        "query_acquisitions - Get recent microscopy sessions (API)",
        "query_grid_status - Check specific grid processing state (API)",
    ]

    for tool in tools:
        print(f"  • {tool}")

    print("\n  Usage Examples:")
    examples = [
        'smartem-mcp client parse --path "/path/to/epu"',
        'smartem-mcp client quality --path "/path/to/epu" --threshold 0.3',
        "smartem-mcp interactive  # Natural language mode",
        "python -m smartem_mcp server  # Start MCP server for Claude Code",
    ]

    for example in examples:
        print(f"  $ {example}")


async def main():
    """Main demo function"""

    show_mcp_capabilities()
    await demo_direct_queries()
    await demo_natural_language_queries()

    print("\n🎉 SmartEM MCP Demo Complete!")
    print("💡 Try: 'smartem-mcp interactive' for hands-on natural language queries")


if __name__ == "__main__":
    asyncio.run(main())
