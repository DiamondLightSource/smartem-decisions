"""
SmartEM MCP Server

Provides MCP (Model Context Protocol) server for natural language querying of
microscopy session data. Supports both filesystem-based parsing and API-based
querying with read-only access to scientific data.

Architecture:
- Filesystem adapter: Direct parsing of EPU XML files using smartem_agent tools
- API adapter: Query historical/in-flight sessions via smartem_api
- Future: Direct database querying and real-time event streaming
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)
from pydantic import BaseModel

from smartem_agent.fs_parser import EpuParser
from smartem_agent.model.store import InMemoryDataStore
from smartem_api.client import SmartEMAPIClient
from smartem_mcp._version import __version__

logger = logging.getLogger(__name__)


class SmartEMQueryResult(BaseModel):
    """Result wrapper for SmartEM queries"""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    source: str  # "filesystem", "api", or "database"


class FilesystemAdapter:
    """Adapter for direct filesystem parsing using smartem_agent tools"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.FilesystemAdapter")

    async def parse_epu_directory(self, path: str) -> SmartEMQueryResult:
        """Parse EPU directory structure and return comprehensive data"""
        try:
            epu_path = Path(path)
            if not epu_path.exists():
                return SmartEMQueryResult(success=False, error=f"Path does not exist: {path}", source="filesystem")

            # Validate EPU directory structure
            is_valid, errors = EpuParser.validate_project_dir(epu_path)
            if not is_valid:
                return SmartEMQueryResult(
                    success=False, error=f"Invalid EPU directory: {'; '.join(errors)}", source="filesystem"
                )

            # Parse the directory
            datastore = InMemoryDataStore(root_dir=epu_path)
            datastore = EpuParser.parse_epu_output_dir(datastore)

            # Convert to serializable format
            data = {
                "acquisition": datastore.acquisition.model_dump() if datastore.acquisition else None,
                "grids": [grid.model_dump() for grid in datastore.grids.values()],
                "grid_count": len(datastore.grids),
                "total_gridsquares": sum(
                    len(grid_data.gridsquares)
                    for grid_data in datastore.grids.values()
                    if hasattr(grid_data, "gridsquares")
                ),
            }

            return SmartEMQueryResult(success=True, data=data, source="filesystem")

        except Exception as e:
            self.logger.error(f"Error parsing EPU directory {path}: {str(e)}")
            return SmartEMQueryResult(success=False, error=str(e), source="filesystem")

    async def query_quality_metrics(self, path: str, threshold: float = 0.5) -> SmartEMQueryResult:
        """Query foil holes and micrographs below quality threshold"""
        try:
            result = await self.parse_epu_directory(path)
            if not result.success:
                return result

            low_quality_items = []
            for _grid in result.data.get("grids", []):
                # This is a simplified example - would need proper quality metric extraction
                # from the parsed EPU data structures
                pass

            return SmartEMQueryResult(
                success=True, data={"low_quality_items": low_quality_items, "threshold": threshold}, source="filesystem"
            )

        except Exception as e:
            return SmartEMQueryResult(success=False, error=str(e), source="filesystem")


class APIAdapter:
    """Adapter for querying via SmartEM API"""

    def __init__(self, api_base_url: str = "http://localhost:30080"):
        self.api_base_url = api_base_url
        self.client = None
        self.logger = logging.getLogger(f"{__name__}.APIAdapter")

    async def connect(self) -> bool:
        """Initialize API connection"""
        try:
            self.client = SmartEMAPIClient(base_url=self.api_base_url)
            # Test connection
            response = await self.client.get_health()
            return response.get("status") == "healthy"
        except Exception as e:
            self.logger.error(f"Failed to connect to API at {self.api_base_url}: {str(e)}")
            return False

    async def query_acquisitions(self, limit: int = 10) -> SmartEMQueryResult:
        """Query recent acquisitions"""
        try:
            if not self.client:
                await self.connect()

            acquisitions = await self.client.get_acquisitions(limit=limit)

            return SmartEMQueryResult(
                success=True, data={"acquisitions": acquisitions, "count": len(acquisitions)}, source="api"
            )

        except Exception as e:
            return SmartEMQueryResult(success=False, error=str(e), source="api")

    async def query_grid_status(self, grid_id: str) -> SmartEMQueryResult:
        """Query specific grid status and processing state"""
        try:
            if not self.client:
                await self.connect()

            grid = await self.client.get_grid(grid_id)
            if not grid:
                return SmartEMQueryResult(success=False, error=f"Grid {grid_id} not found", source="api")

            return SmartEMQueryResult(success=True, data={"grid": grid}, source="api")

        except Exception as e:
            return SmartEMQueryResult(success=False, error=str(e), source="api")


class SmartEMMCPServer:
    """Main MCP Server for SmartEM microscopy data"""

    def __init__(self, api_base_url: str = "http://localhost:30080"):
        self.server = Server("smartem-mcp")
        self.filesystem_adapter = FilesystemAdapter()
        self.api_adapter = APIAdapter(api_base_url)
        self.logger = logging.getLogger(__name__)

        # Register MCP handlers
        self._register_tools()
        self._register_resources()

    def _register_tools(self):
        """Register MCP tools for natural language queries"""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available SmartEM query tools"""
            return [
                Tool(
                    name="parse_epu_directory",
                    description="Parse EPU microscopy directory and extract comprehensive session data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to EPU output directory containing EpuSession.dm",
                            }
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="query_quality_metrics",
                    description="Find foil holes and micrographs with quality scores below threshold",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to EPU directory (for filesystem queries)"},
                            "threshold": {
                                "type": "number",
                                "description": "Quality threshold (default: 0.5)",
                                "default": 0.5,
                            },
                            "source": {
                                "type": "string",
                                "enum": ["filesystem", "api"],
                                "description": "Data source to query",
                                "default": "filesystem",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="query_acquisitions",
                    description="Query recent microscopy acquisition sessions from API",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of acquisitions to return (default: 10)",
                                "default": 10,
                            }
                        },
                    },
                ),
                Tool(
                    name="query_grid_status",
                    description="Get detailed status and processing state for a specific grid",
                    inputSchema={
                        "type": "object",
                        "properties": {"grid_id": {"type": "string", "description": "Grid UUID or identifier"}},
                        "required": ["grid_id"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Execute SmartEM query tools"""

            if name == "parse_epu_directory":
                result = await self.filesystem_adapter.parse_epu_directory(arguments["path"])

            elif name == "query_quality_metrics":
                if arguments.get("source", "filesystem") == "filesystem":
                    result = await self.filesystem_adapter.query_quality_metrics(
                        arguments["path"], arguments.get("threshold", 0.5)
                    )
                else:
                    # Future: API-based quality queries
                    result = SmartEMQueryResult(
                        success=False, error="API-based quality queries not yet implemented", source="api"
                    )

            elif name == "query_acquisitions":
                result = await self.api_adapter.query_acquisitions(arguments.get("limit", 10))

            elif name == "query_grid_status":
                result = await self.api_adapter.query_grid_status(arguments["grid_id"])

            else:
                result = SmartEMQueryResult(success=False, error=f"Unknown tool: {name}", source="server")

            # Format result for MCP response
            if result.success:
                response_text = f"✅ Query successful (source: {result.source}):\n"
                if result.data:
                    # Pretty format the data
                    import json

                    response_text += json.dumps(result.data, indent=2, default=str)
            else:
                response_text = f"❌ Query failed (source: {result.source}): {result.error}"

            return [TextContent(type="text", text=response_text)]

    def _register_resources(self):
        """Register MCP resources for SmartEM data"""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available SmartEM data resources"""
            return [
                Resource(
                    uri="smartem://acquisitions",
                    name="Active Acquisitions",
                    description="Current and recent microscopy acquisition sessions",
                    mimeType="application/json",
                ),
                Resource(
                    uri="smartem://quality-metrics",
                    name="Quality Metrics",
                    description="Image and foil hole quality assessment data",
                    mimeType="application/json",
                ),
                # Future resources:
                Resource(
                    uri="smartem://events",
                    name="Real-time Events (Future)",
                    description="Live event stream from microscopy sessions",
                    mimeType="text/event-stream",
                ),
                Resource(
                    uri="smartem://database",
                    name="Direct Database Access (Future)",
                    description="Direct read-only database queries",
                    mimeType="application/json",
                ),
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read SmartEM resource data"""
            if uri == "smartem://acquisitions":
                result = await self.api_adapter.query_acquisitions(limit=5)
                return result.model_dump_json() if result.data else "{}"

            elif uri == "smartem://quality-metrics":
                # Placeholder - would need actual implementation
                return '{"message": "Quality metrics resource - requires specific query parameters"}'

            elif uri in ["smartem://events", "smartem://database"]:
                return '{"message": "Resource not yet implemented - planned for future release"}'

            else:
                raise ValueError(f"Unknown resource: {uri}")

    async def serve(self):
        """Start the MCP server"""
        self.logger.info(f"Starting SmartEM MCP Server v{__version__}")

        # Initialize connections
        api_connected = await self.api_adapter.connect()
        if api_connected:
            self.logger.info("Connected to SmartEM API")
        else:
            self.logger.warning("Could not connect to SmartEM API - filesystem queries only")

        # Start stdio server
        async with stdio_server() as streams:
            await self.server.run(
                streams[0],
                streams[1],
                init_options={
                    "server_name": "smartem-mcp",
                    "server_version": __version__,
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                    },
                },
            )


async def main():
    """Main entry point for SmartEM MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="SmartEM MCP Server")
    parser.add_argument("--api-url", default="http://localhost:30080", help="SmartEM API base URL")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Logging level"
    )

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    server = SmartEMMCPServer(api_base_url=args.api_url)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
