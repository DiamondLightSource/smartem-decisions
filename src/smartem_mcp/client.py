"""
SmartEM MCP Client

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

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MCPQueryResult(BaseModel):
    """Wrapper for MCP query results with metadata"""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    source: str | None = None
    tool_name: str | None = None


class SmartEMMCPClient:
    """Client for interacting with SmartEM MCP Server"""

    def __init__(self, server_command: list[str] | None = None):
        """
        Initialize MCP client

        Args:
            server_command: Command to start MCP server. Defaults to local server.
        """
        self.server_command = server_command or ["python", "-m", "smartem_mcp.server"]
        self.session: ClientSession | None = None
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Connect to SmartEM MCP server"""
        try:
            self.logger.info(f"Connecting to SmartEM MCP server: {' '.join(self.server_command)}")

            # Start server process and create client session
            async with stdio_client(self.server_command) as streams:
                self.session = ClientSession(streams[0], streams[1])

                # Initialize connection
                init_result = await self.session.initialize()
                self.logger.info(
                    f"Connected to server: {init_result.server_info.name} v{init_result.server_info.version}"
                )

                return True

        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server: {str(e)}")
            self.session = None
            return False

    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.session:
            await self.session.close()
            self.session = None
            self.logger.info("Disconnected from MCP server")

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPQueryResult:
        """Execute MCP tool with error handling"""
        if not self.session:
            if not await self.connect():
                return MCPQueryResult(success=False, error="Could not connect to MCP server", tool_name=tool_name)

        try:
            result = await self.session.call_tool(tool_name, arguments)

            # Parse result content
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, "text"):
                    response_text = content.text

                    # Try to parse JSON data from response
                    if "✅ Query successful" in response_text:
                        # Extract JSON part after the success message
                        json_start = response_text.find("\n") + 1
                        if json_start < len(response_text):
                            try:
                                data = json.loads(response_text[json_start:])
                                return MCPQueryResult(success=True, data=data, tool_name=tool_name)
                            except json.JSONDecodeError:
                                pass

                    # Handle error responses
                    elif "❌ Query failed" in response_text:
                        error_msg = response_text.split(": ", 1)[1] if ": " in response_text else response_text
                        return MCPQueryResult(success=False, error=error_msg, tool_name=tool_name)

                    # Return raw text if can't parse
                    return MCPQueryResult(success=True, data={"raw_response": response_text}, tool_name=tool_name)

            return MCPQueryResult(success=False, error="Empty response from server", tool_name=tool_name)

        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name}: {str(e)}")
            return MCPQueryResult(success=False, error=str(e), tool_name=tool_name)

    # High-level query methods

    async def parse_epu_directory(self, path: str) -> MCPQueryResult:
        """
        Parse EPU microscopy directory and extract comprehensive session data

        Args:
            path: Path to EPU output directory containing EpuSession.dm

        Returns:
            MCPQueryResult with parsed acquisition data, grids, and statistics
        """
        return await self._call_tool("parse_epu_directory", {"path": path})

    async def find_low_quality_items(
        self, path: str, threshold: float = 0.5, source: str = "filesystem"
    ) -> MCPQueryResult:
        """
        Find foil holes and micrographs with quality scores below threshold

        Args:
            path: Path to EPU directory (for filesystem) or ignored (for API)
            threshold: Quality threshold (0.0 to 1.0)
            source: Data source - "filesystem" or "api"

        Returns:
            MCPQueryResult with low quality items and statistics
        """
        return await self._call_tool("query_quality_metrics", {"path": path, "threshold": threshold, "source": source})

    async def query_recent_acquisitions(self, limit: int = 10) -> MCPQueryResult:
        """
        Query recent microscopy acquisition sessions from API

        Args:
            limit: Number of acquisitions to return

        Returns:
            MCPQueryResult with acquisition list and metadata
        """
        return await self._call_tool("query_acquisitions", {"limit": limit})

    async def get_grid_status(self, grid_id: str) -> MCPQueryResult:
        """
        Get detailed status and processing state for a specific grid

        Args:
            grid_id: Grid UUID or identifier

        Returns:
            MCPQueryResult with grid details and processing status
        """
        return await self._call_tool("query_grid_status", {"grid_id": grid_id})

    # Convenience methods for common queries

    async def session_summary(self, path: str) -> dict[str, Any]:
        """Get high-level summary of microscopy session"""
        result = await self.parse_epu_directory(path)
        if not result.success:
            return {"error": result.error}

        data = result.data or {}
        return {
            "session_path": path,
            "acquisition_name": data.get("acquisition", {}).get("name", "Unknown"),
            "grid_count": data.get("grid_count", 0),
            "total_gridsquares": data.get("total_gridsquares", 0),
            "success": True,
        }

    async def quality_report(self, path: str, threshold: float = 0.5) -> dict[str, Any]:
        """Generate quality assessment report for session"""
        result = await self.find_low_quality_items(path, threshold)
        if not result.success:
            return {"error": result.error}

        data = result.data or {}
        return {
            "quality_threshold": threshold,
            "low_quality_count": len(data.get("low_quality_items", [])),
            "items": data.get("low_quality_items", []),
            "success": True,
        }

    # Context manager support

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


class SmartEMQueryInterface:
    """High-level interface for natural language queries"""

    def __init__(self, client: SmartEMMCPClient | None = None):
        self.client = client or SmartEMMCPClient()

    async def ask(self, question: str, context: dict[str, Any] | None = None) -> str:
        """
        Process natural language questions about microscopy data

        Args:
            question: Natural language question
            context: Additional context (e.g., paths, IDs)

        Returns:
            Human-readable answer
        """
        context = context or {}

        # Simple pattern matching for common questions
        question_lower = question.lower()

        if "session" in question_lower and "summary" in question_lower:
            if "path" in context:
                summary = await self.client.session_summary(context["path"])
                if summary.get("success"):
                    return (
                        f"Session '{summary['acquisition_name']}' contains {summary['grid_count']} grids "
                        f"with {summary['total_gridsquares']} total grid squares."
                    )
                else:
                    return f"Error analyzing session: {summary.get('error')}"

        elif "quality" in question_lower and ("low" in question_lower or "bad" in question_lower):
            if "path" in context:
                threshold = context.get("threshold", 0.5)
                report = await self.client.quality_report(context["path"], threshold)
                if report.get("success"):
                    return f"Found {report['low_quality_count']} items below quality threshold {threshold}"
                else:
                    return f"Error analyzing quality: {report.get('error')}"

        elif "recent" in question_lower and "acquisition" in question_lower:
            result = await self.client.query_recent_acquisitions(limit=5)
            if result.success and result.data:
                count = result.data.get("count", 0)
                return f"Found {count} recent acquisitions"
            else:
                return f"Error querying acquisitions: {result.error}"

        else:
            return (
                f"I don't understand the question: '{question}'. "
                "Try asking about session summaries, quality metrics, or recent acquisitions."
            )


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
            print(json.dumps(result.model_dump(), indent=2))

        elif args.command == "quality" and args.path:
            result = await client.find_low_quality_items(args.path, args.threshold)
            print(json.dumps(result.model_dump(), indent=2))

        elif args.command == "acquisitions":
            result = await client.query_recent_acquisitions()
            print(json.dumps(result.model_dump(), indent=2))

        else:
            print("Usage examples:")
            print("  python -m smartem_mcp.client --command parse --path /path/to/epu")
            print("  python -m smartem_mcp.client --command quality --path /path/to/epu --threshold 0.3")
            print("  python -m smartem_mcp.client --command acquisitions")


if __name__ == "__main__":
    asyncio.run(main())
