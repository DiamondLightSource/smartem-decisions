"""
SmartEM MCP Client using FastMCP

Provides client interface for connecting to SmartEM MCP server and executing
natural language queries against microscopy data.

Usage Examples:
    # Filesystem queries
    client = SmartEMMCPClient()
    result = await client.parse_epu_directory("/path/to/epu/session")

    # API queries
    result = await client.query_recent_acquisitions(limit=5)

    # Quality analysis
    low_quality = await client.find_low_quality_items("/path/to/epu", threshold=0.3)
"""

import asyncio
import json
import logging
from typing import Any

from fastmcp.client import Client

logger = logging.getLogger(__name__)


class SmartEMMCPClient:
    """Client for interacting with SmartEM MCP Server using FastMCP"""

    def __init__(self, server_command: list[str] | None = None):
        """
        Initialize MCP client

        Args:
            server_command: Command to start MCP server. Defaults to local server.
        """
        self.server_command = server_command or ["python", "-m", "smartem_mcp.server"]
        self.client = None
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Connect to SmartEM MCP server"""
        try:
            self.logger.info(f"Connecting to SmartEM MCP server: {' '.join(self.server_command)}")
            self.client = Client(self.server_command)
            self.logger.info("Connected to SmartEM MCP server")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server: {str(e)}")
            self.client = None
            return False

    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.client:
            await self.client.close()
            self.client = None
            self.logger.info("Disconnected from MCP server")

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute MCP tool with error handling"""
        if not self.client:
            await self.connect()

        try:
            async with self.client:
                result = await self.client.call_tool(tool_name, arguments)
                return result

        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {str(e)}")
            raise RuntimeError(f"Tool call failed: {str(e)}") from e

    # High-level query methods

    async def parse_epu_directory(self, path: str) -> dict[str, Any]:
        """
        Parse EPU microscopy directory and extract comprehensive session data

        Args:
            path: Path to EPU output directory containing EpuSession.dm

        Returns:
            Parsed acquisition data, grids, and statistics
        """
        return await self._call_tool("parse_epu_directory", {"path": path})

    async def find_low_quality_items(
        self, path: str, threshold: float = 0.5, source: str = "filesystem"
    ) -> dict[str, Any]:
        """
        Find foil holes and micrographs with quality scores below threshold

        Args:
            path: Path to EPU directory (for filesystem) or ignored (for API)
            threshold: Quality threshold (0.0 to 1.0)
            source: Data source - "filesystem" or "api"

        Returns:
            Low quality items and statistics
        """
        return await self._call_tool("query_quality_metrics", {"path": path, "threshold": threshold, "source": source})

    async def query_recent_acquisitions(self, limit: int = 10) -> dict[str, Any]:
        """
        Query recent microscopy acquisition sessions from API

        Args:
            limit: Number of acquisitions to return

        Returns:
            Acquisition list and metadata
        """
        return await self._call_tool("query_acquisitions", {"limit": limit})

    async def get_grid_status(self, grid_id: str) -> dict[str, Any]:
        """
        Get detailed status and processing state for a specific grid

        Args:
            grid_id: Grid UUID or identifier

        Returns:
            Grid details and processing status
        """
        return await self._call_tool("query_grid_status", {"grid_id": grid_id})

    # Context manager support

    async def __aenter__(self):
        """Async context manager entry"""
        if not self.client:
            await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


# Utility functions for CLI usage


async def main():
    """Example usage of SmartEM MCP Client"""
    import argparse

    parser = argparse.ArgumentParser(description="SmartEM MCP Client")
    parser.add_argument("--path", help="Path to EPU directory")
    parser.add_argument("--command", help="Command to execute")
    parser.add_argument("--threshold", type=float, default=0.5, help="Quality threshold")

    args = parser.parse_args()

    async with SmartEMMCPClient() as client:
        if args.command == "parse" and args.path:
            result = await client.parse_epu_directory(args.path)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "quality" and args.path:
            result = await client.find_low_quality_items(args.path, args.threshold)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "acquisitions":
            result = await client.query_recent_acquisitions()
            print(json.dumps(result, indent=2, default=str))

        else:
            print("Usage examples:")
            print("  python -m smartem_mcp.client --command parse --path /path/to/epu")
            print("  python -m smartem_mcp.client --command quality --path /path/to/epu --threshold 0.3")
            print("  python -m smartem_mcp.client --command acquisitions")


if __name__ == "__main__":
    asyncio.run(main())
