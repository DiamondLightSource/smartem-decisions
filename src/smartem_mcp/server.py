"""
SmartEM MCP Server using FastMCP

Provides MCP (Model Context Protocol) server for natural language querying of
microscopy session data. Supports both filesystem-based parsing and API-based
querying with read-only access to scientific data.

Architecture:
- Direct filesystem parsing using smartem_agent tools
- API querying via smartem_api client
- FastMCP decorators for simplified tool and resource registration
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from smartem_agent.fs_parser import EpuParser
from smartem_agent.model.store import InMemoryDataStore
from smartem_api.client import SmartEMAPIClient
from smartem_mcp._version import __version__

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("smartem-mcp")

# Global API client instance
api_client: SmartEMAPIClient | None = None


def init_api_client(api_base_url: str = "http://localhost:30080") -> bool:
    """Initialize global API client"""
    global api_client
    try:
        api_client = SmartEMAPIClient(base_url=api_base_url)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize API client: {e}")
        return False


@mcp.tool()
async def parse_epu_directory(path: str) -> dict[str, Any]:
    """
    Parse EPU microscopy directory and extract comprehensive session data

    Args:
        path: Path to EPU output directory containing EpuSession.dm

    Returns:
        Comprehensive acquisition data including grids and statistics
    """
    try:
        epu_path = Path(path)
        if not epu_path.exists():
            raise ValueError(f"Path does not exist: {path}")

        # Validate EPU directory structure
        is_valid, errors = EpuParser.validate_project_dir(epu_path)
        if not is_valid:
            raise ValueError(f"Invalid EPU directory: {'; '.join(errors)}")

        # Parse the directory
        datastore = InMemoryDataStore(root_dir=epu_path)
        datastore = EpuParser.parse_epu_output_dir(datastore)

        # Convert to serializable format
        return {
            "acquisition": datastore.acquisition.model_dump() if datastore.acquisition else None,
            "grids": [grid.model_dump() for grid in datastore.grids.values()],
            "grid_count": len(datastore.grids),
            "total_gridsquares": sum(
                len(grid_data.gridsquares)
                for grid_data in datastore.grids.values()
                if hasattr(grid_data, "gridsquares")
            ),
            "source": "filesystem",
        }

    except Exception as e:
        logger.error(f"Error parsing EPU directory {path}: {str(e)}")
        raise RuntimeError(f"Failed to parse EPU directory: {str(e)}") from e


@mcp.tool()
async def query_quality_metrics(path: str, threshold: float = 0.5, source: str = "filesystem") -> dict[str, Any]:
    """
    Find foil holes and micrographs with quality scores below threshold

    Args:
        path: Path to EPU directory (for filesystem queries)
        threshold: Quality threshold (0.0 to 1.0)
        source: Data source - "filesystem" or "api"

    Returns:
        Low quality items and statistics
    """
    if source == "api":
        raise NotImplementedError("API-based quality queries not yet implemented")

    try:
        # Get parsed directory data
        directory_data = await parse_epu_directory(path)

        # This is a simplified example - would need proper quality metric extraction
        # from the parsed EPU data structures
        low_quality_items = []
        for _grid in directory_data.get("grids", []):
            # Future implementation: extract actual quality metrics
            pass

        return {
            "low_quality_items": low_quality_items,
            "threshold": threshold,
            "source": source,
        }

    except Exception as e:
        logger.error(f"Error querying quality metrics: {str(e)}")
        raise RuntimeError(f"Failed to query quality metrics: {str(e)}") from e


@mcp.tool()
async def query_acquisitions(limit: int = 10) -> dict[str, Any]:
    """
    Query recent microscopy acquisition sessions from API

    Args:
        limit: Number of acquisitions to return

    Returns:
        List of recent acquisitions with metadata
    """
    global api_client

    if not api_client:
        raise RuntimeError("API client not initialized")

    try:
        # Test connection first
        health = await api_client.get_health()
        if health.get("status") != "healthy":
            raise RuntimeError("API is not healthy")

        acquisitions = await api_client.get_acquisitions(limit=limit)

        return {
            "acquisitions": acquisitions,
            "count": len(acquisitions),
            "source": "api",
        }

    except Exception as e:
        logger.error(f"Error querying acquisitions: {str(e)}")
        raise RuntimeError(f"Failed to query acquisitions: {str(e)}") from e


@mcp.tool()
async def query_grid_status(grid_id: str) -> dict[str, Any]:
    """
    Get detailed status and processing state for a specific grid

    Args:
        grid_id: Grid UUID or identifier

    Returns:
        Grid details and processing status
    """
    global api_client

    if not api_client:
        raise RuntimeError("API client not initialized")

    try:
        grid = await api_client.get_grid(grid_id)
        if not grid:
            raise ValueError(f"Grid {grid_id} not found")

        return {
            "grid": grid,
            "source": "api",
        }

    except Exception as e:
        logger.error(f"Error querying grid {grid_id}: {str(e)}")
        raise RuntimeError(f"Failed to query grid status: {str(e)}") from e


@mcp.resource("smartem://acquisitions")
async def get_acquisitions_resource() -> str:
    """Current and recent microscopy acquisition sessions"""
    try:
        result = await query_acquisitions(limit=5)
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return json.dumps({"error": "Failed to fetch acquisitions"})


@mcp.resource("smartem://quality-metrics")
async def get_quality_metrics_resource() -> str:
    """Image and foil hole quality assessment data"""
    return json.dumps({"message": "Quality metrics resource - requires specific query parameters"})


@mcp.resource("smartem://events")
async def get_events_resource() -> str:
    """Live event stream from microscopy sessions (Future)"""
    return json.dumps({"message": "Resource not yet implemented - planned for future release"})


@mcp.resource("smartem://database")
async def get_database_resource() -> str:
    """Direct read-only database queries (Future)"""
    return json.dumps({"message": "Resource not yet implemented - planned for future release"})


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
    logger.info(f"Starting SmartEM MCP Server v{__version__}")

    # Initialize API client
    api_connected = init_api_client(args.api_url)
    if api_connected:
        logger.info("Initialized SmartEM API client")
    else:
        logger.warning("Could not initialize SmartEM API client - some features may be limited")

    # Run FastMCP server
    await mcp.run()


if __name__ == "__main__":
    asyncio.run(main())
