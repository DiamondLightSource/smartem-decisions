# Using SmartEM MCP Interface

The SmartEM MCP (Model Context Protocol) interface provides natural language querying capabilities for microscopy session data. Built with FastMCP 2.0, it supports both filesystem-based parsing and API-based queries for comprehensive data access.

## Overview

The MCP interface consists of:
- **FastMCP Server**: Provides natural language query capabilities via MCP protocol using FastMCP framework
- **MCP Client**: Python client for programmatic access with simplified FastMCP patterns
- **CLI Interface**: Command-line tools for interactive usage

## Installation

Install with MCP dependencies (includes FastMCP 2.0 framework):

```bash
pip install -e .[mcp]
```

This installs the required FastMCP 2.0 framework and SmartEM MCP components.

## Configuration

The MCP server can be configured using environment variables. A template configuration file is provided:

```bash
# Copy the example configuration
cp .env.example.mcp .env.mcp

# Edit .env.mcp with your settings
```

Available configuration options (see `.env.example.mcp` for details):
- `SMARTEM_MCP_DATA_PATH`: Path to EPU sessions directory (for filesystem adapter)
- `SMARTEM_MCP_API_URL`: SmartEM backend API URL (for API adapter)
- `SMARTEM_MCP_ADAPTER`: Data adapter selection (`filesystem` or `api`)
- `SMARTEM_MCP_LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

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
    if result.get("success"):
        print(f"Found {result['grid_count']} grids")
    
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

Query historical and in-flight sessions via SmartEM API:

- **Use case**: Historical analysis, live session monitoring
- **Capabilities**: Acquisition status, grid processing, real-time data
- **Requirements**: Running SmartEM backend service

## Claude Code Integration

The SmartEM MCP server integrates seamlessly with Claude Code, allowing natural language queries about microscopy data directly within your development environment.

### Prerequisites

Ensure MCP dependencies are installed (includes FastMCP 2.0):

```bash
pip install -e .[mcp]
```

Verify the installation:

```bash
python -m smartem_mcp --version
```

### Registration with Claude Code

#### Option 1: Using Claude CLI (Recommended)

Register the SmartEM MCP server using the Claude CLI:

```bash
# Basic registration (user-wide scope)
claude mcp add smartem -- python -m smartem_mcp server

# With custom API URL
claude mcp add smartem -- python -m smartem_mcp server --api-url http://localhost:30080

# Project-scoped registration
claude mcp add smartem --scope project -- python -m smartem_mcp server --api-url http://localhost:30080
```

#### Option 2: Manual Configuration

If you prefer manual configuration, add the server to your Claude Code settings:

**For user-wide registration:**
Edit `~/.config/claude-code/mcp.json`:

```json
{
  "mcpServers": {
    "smartem": {
      "command": "python",
      "args": ["-m", "smartem_mcp", "server", "--api-url", "http://localhost:30080"],
      "env": {
        "SMARTEM_API_URL": "http://localhost:30080",
        "SMARTEM_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**For project-scoped registration:**
Create `.claude/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "smartem": {
      "command": "python",
      "args": ["-m", "smartem_mcp", "server"],
      "env": {
        "SMARTEM_API_URL": "http://localhost:30080"
      }
    }
  }
}
```

### Registration Options

#### Environment Variables

Configure the MCP server behaviour through environment variables:

- `SMARTEM_API_URL`: Base URL for SmartEM API (default: `http://localhost:30080`)
- `SMARTEM_MCP_LOG_LEVEL`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `PYTHON_PATH`: Python executable path if not in system PATH

Example with custom environment:

```bash
claude mcp add smartem --env SMARTEM_API_URL=http://production.server:8080 --env SMARTEM_MCP_LOG_LEVEL=DEBUG -- python -m smartem_mcp server
```

#### Scope Options

- **User scope** (default): Available across all Claude Code projects
- **Project scope**: Only available within the current project directory

```bash
# User-wide (default)
claude mcp add smartem -- python -m smartem_mcp server

# Project-specific
claude mcp add smartem --scope project -- python -m smartem_mcp server
```

### Verification

#### 1. Check Registration Status

```bash
# List all registered MCP servers
claude mcp list

# Check SmartEM server status
claude mcp status smartem
```

#### 2. Test Connection

Start a new Claude Code session and verify the SmartEM tools are available:

```bash
# In Claude Code, type a natural language query:
# "List all available SmartEM tools"
```

You should see the following tools available:
- `parse_epu_directory` - Parse EPU microscopy directories
- `query_quality_metrics` - Find low-quality images and foil holes  
- `query_acquisitions` - Query recent acquisition sessions
- `query_grid_status` - Get grid processing status

**Note**: The client provides high-level methods such as `find_low_quality_items()` which internally call the corresponding MCP tools.

#### 3. Test Basic Functionality

Try a simple query in Claude Code:

> "Parse the EPU directory at /path/to/your/epu/session"

### Usage in Claude Code

Once registered, you can interact with SmartEM data using natural language within Claude Code:

#### Directory Analysis

> "Show me a comprehensive analysis of the EPU session at /data/microscopy/session_001"

> "What grids and grid squares are available in /path/to/epu/directory?"

#### Quality Assessment

> "Find all images with quality scores below 0.4 in the EPU directory /data/session_001"

> "Show me foil holes that need attention from /path/to/epu with quality threshold 0.3"

#### Session Monitoring

> "What are the 5 most recent microscopy acquisitions?"

> "Check the processing status of grid uuid-12345"

#### Advanced Queries

> "Compare quality metrics between /data/session_001 and /data/session_002"

> "Generate a report for all low-quality items found today"

### Server Mode (Standalone)

For advanced users or debugging, run the MCP server in standalone mode:

```bash
python -m smartem_mcp server --api-url http://localhost:30080 --log-level DEBUG
```

This starts the server with stdio communication, primarily useful for:
- Debugging MCP protocol issues
- Custom client integrations
- Development and testing

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
if result.get("success"):
    # Process result data
    data = result.get("data", {})
    pass
else:
    print(f"Error: {result.get('error')}")
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

#### 1. MCP Server Registration Problems

**"SmartEM MCP server not found"**
- Ensure MCP dependencies are installed: `pip install -e .[mcp]` (includes FastMCP 2.0)  
- Verify Python path includes smartem_mcp module: `python -c "import smartem_mcp; print('OK')"`
- Check registration with `claude mcp list`

**"Failed to start MCP server"**
- Verify Python executable is accessible: `which python`
- Test server manually: `python -m smartem_mcp server --api-url http://localhost:30080`
- Check environment variables are properly set

**"MCP server registered but not responding"**
- Remove and re-add the server: `claude mcp remove smartem && claude mcp add smartem -- python -m smartem_mcp server`
- Restart Claude Code completely
- Check server logs: `claude mcp logs smartem`

#### 2. Directory and Data Issues

**"Invalid EPU directory"**
- Verify directory contains EpuSession.dm file
- Check Metadata/ and Images-Disc*/ subdirectories exist  
- Ensure proper file permissions for reading EPU data

**"Permission denied accessing EPU files"**
- Check file permissions: `ls -la /path/to/epu/directory`
- Ensure user has read access to all EPU subdirectories
- For network mounts, verify mount permissions

#### 3. API Connection Issues

**"API connection failed"**
- Verify SmartEM backend is running: `curl http://localhost:30080/health`
- Check API URL is correct in registration command
- Test network connectivity to API endpoint

**"Authentication failed"** (Future feature)
- Verify API tokens are properly configured
- Check token expiration and renewal

#### 4. Claude Code Integration Issues

**"Tools not available in Claude Code"**
- Restart Claude Code after registration
- Check MCP server status: `claude mcp status smartem`
- Verify registration scope (user vs project)

**"Queries return empty results"**
- Test with standalone client: `python -m smartem_mcp client parse --path /path/to/epu`
- Check EPU directory structure and data validity
- Verify API connectivity for acquisition queries

### Debug Mode

#### Enable Debug Logging

For MCP server debugging:
```bash
claude mcp add smartem --env SMARTEM_MCP_LOG_LEVEL=DEBUG -- python -m smartem_mcp server --api-url http://localhost:30080 --log-level DEBUG
```

For client debugging:
```bash
python -m smartem_mcp --log-level DEBUG client parse --path /path/to/epu
```

#### Check Server Logs

View MCP server logs in Claude Code:
```bash
claude mcp logs smartem
```

#### Manual Server Testing

Test the server independently of Claude Code:
```bash
# Start server in stdio mode for testing
python -m smartem_mcp server --log-level DEBUG

# The server uses FastMCP stdio communication protocol
# For testing, use interactive mode or programmatic client instead:
python -m smartem_mcp interactive
```

### Environment-Specific Troubleshooting

#### Development Environment
- Ensure virtual environment is activated when registering
- Use absolute Python paths: `claude mcp add smartem -- /path/to/.venv/bin/python -m smartem_mcp server`

#### Production Environment  
- Verify all dependencies are installed in production Python environment
- Check firewall rules for API connectivity
- Ensure proper logging configuration for production

#### Container Environments
- Mount EPU directories properly in container
- Expose API ports correctly
- Set environment variables in container runtime

### Getting Help

If issues persist:

1. **Gather diagnostic information:**
   ```bash
   # System info
   python --version
   pip list | grep -E "(smartem|mcp)"
   claude mcp list
   claude mcp status smartem
   
   # Test basic functionality
   python -m smartem_mcp --version
   python -c "import smartem_mcp; print('Import successful')"
   ```

2. **Check project documentation:** [SmartEM Decisions README](/README.md)

3. **Review MCP protocol documentation:** [Model Context Protocol Specification](https://modelcontextprotocol.io/)

4. **Submit issue:** Include diagnostic information and specific error messages

## Integration with Claude Code

When properly configured, you can ask Claude Code natural language questions:

> "Show me all grid squares with quality scores below 0.5 from the EPU session at /data/session1"

> "What's the current status of acquisition abc-123?"

> "List micrographs acquired in the last hour with defocus values"

The MCP server will automatically route these queries to the appropriate data sources and return formatted results.
