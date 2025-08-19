# Using SmartEM MCP Interface

The SmartEM MCP (Model Context Protocol) interface provides natural language querying capabilities for microscopy session data. It supports both filesystem-based parsing and API-based queries for comprehensive data access.

## Overview

The MCP interface consists of:
- **MCP Server**: Provides natural language query capabilities via MCP protocol
- **MCP Client**: Python client for programmatic access
- **CLI Interface**: Command-line tools for interactive usage

## Installation

Install with MCP dependencies:

```bash
pip install -e .[mcp]
```

## Quick Start

### 1. Interactive Query Mode

Start interactive mode for natural language questions:

```bash
python -m smartem_mcp interactive
```

Example questions:
- "Show me a summary of session /path/to/epu/directory"
- "Find low quality items in /path/to/epu with threshold 0.3"  
- "What are the recent acquisitions?"

### 2. Command Line Usage

Parse EPU directory:
```bash
python -m smartem_mcp client parse --path /path/to/epu/session
```

Find low quality items:
```bash
python -m smartem_mcp client quality --path /path/to/epu --threshold 0.3
```

Query recent acquisitions (requires API):
```bash
python -m smartem_mcp client acquisitions --limit 10
```

### 3. Programmatic Usage

```python
from smartem_mcp.client import SmartEMMCPClient

async with SmartEMMCPClient() as client:
    # Parse EPU directory
    result = await client.parse_epu_directory("/path/to/epu")
    if result.success:
        print(f"Found {result.data['grid_count']} grids")
    
    # Find low quality items
    quality_result = await client.find_low_quality_items(
        "/path/to/epu", 
        threshold=0.3
    )
    
    # Query API data
    acquisitions = await client.query_recent_acquisitions(limit=5)
```

## Data Sources

### Filesystem Queries

Direct parsing of EPU XML files using existing `smartem_agent` tools:

- **Use case**: Ad-hoc analysis, debugging, development
- **Capabilities**: Full EPU directory parsing, quality analysis
- **Requirements**: Direct filesystem access to EPU data

### API Queries

Query historical and in-flight sessions via `smartem_api`:

- **Use case**: Historical analysis, live session monitoring
- **Capabilities**: Acquisition status, grid processing, real-time data
- **Requirements**: Running SmartEM backend service

## Server Mode

Run standalone MCP server for Claude Code integration:

```bash
python -m smartem_mcp server --api-url http://localhost:30080
```

Configure in Claude Code settings:
```json
{
  "mcpServers": {
    "smartem": {
      "command": "python",
      "args": ["-m", "smartem_mcp.server"]
    }
  }
}
```

## Available Tools

### `parse_epu_directory`
Parse EPU microscopy directory and extract comprehensive session data.

**Parameters:**
- `path` (required): Path to EPU output directory containing EpuSession.dm

**Returns:** Acquisition data, grids, grid squares, and statistics

### `query_quality_metrics`
Find foil holes and micrographs with quality scores below threshold.

**Parameters:**
- `path` (required): Path to EPU directory
- `threshold` (optional): Quality threshold (default: 0.5)
- `source` (optional): "filesystem" or "api" (default: filesystem)

**Returns:** List of low-quality items with metadata

### `query_acquisitions`
Query recent microscopy acquisition sessions from API.

**Parameters:**
- `limit` (optional): Number of acquisitions to return (default: 10)

**Returns:** List of acquisitions with status and metadata

### `query_grid_status`
Get detailed status and processing state for specific grid.

**Parameters:**
- `grid_id` (required): Grid UUID or identifier

**Returns:** Grid details and processing status

## Future Enhancements

The following capabilities are scaffolded for future implementation:

### Real-time Event Streaming
```python
# Future capability - real-time updates via RabbitMQ
events = await client.subscribe_to_events("acquisition.*.quality_updated")
```

### Direct Database Querying
```python
# Future capability - direct read-only database access
result = await client.query_database("SELECT * FROM micrographs WHERE quality < 0.3")
```

## Error Handling

All operations return structured results with success indicators:

```python
result = await client.parse_epu_directory("/path/to/epu")
if result.success:
    # Process result.data
    pass
else:
    print(f"Error: {result.error}")
```

## Configuration

### Environment Variables

- `SMARTEM_API_URL`: Base URL for SmartEM API (default: http://localhost:30080)
- `SMARTEM_MCP_LOG_LEVEL`: Logging level (default: INFO)

### API Authentication

For authenticated API access (future):
```python
client = SmartEMMCPClient(api_token="your_token_here")
```

## Troubleshooting

### Common Issues

1. **"Could not connect to MCP server"**
   - Ensure MCP dependencies are installed: `pip install -e .[mcp]`
   - Check Python path includes smartem_mcp module

2. **"Invalid EPU directory"**
   - Verify directory contains EpuSession.dm file
   - Check Metadata/ and Images-Disc*/ subdirectories exist

3. **"API connection failed"**
   - Verify SmartEM backend is running
   - Check API URL and network connectivity

### Debug Mode

Enable debug logging:
```bash
python -m smartem_mcp --log-level DEBUG client parse --path /path/to/epu
```

## Integration with Claude Code

When properly configured, you can ask Claude Code natural language questions:

> "Show me all grid squares with quality scores below 0.5 from the EPU session at /data/session1"

> "What's the current status of acquisition abc-123?"

> "List micrographs acquired in the last hour with defocus values"

The MCP server will automatically route these queries to the appropriate data sources and return formatted results.
