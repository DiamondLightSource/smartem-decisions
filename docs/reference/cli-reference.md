# SmartEM Agent CLI Reference

The SmartEM Agent provides a comprehensive command-line interface for parsing, validating, and monitoring EPU (Electron Physical User) microscopy data. This reference documents all available commands, parameters, and usage patterns.

## Command Overview

```bash
python -m smartem_agent [COMMAND] [OPTIONS]
```

The CLI is organised into the following command groups:

- **[parse](#parse-commands)** - Parse various EPU data files and structures
- **[validate](#validate-command)** - Validate EPU project directory structure
- **[watch](#watch-command)** - Monitor directories for real-time data processing

## Global Options

All commands support the following verbosity options:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--verbose` | `-v` | count | 0 | Increase verbosity (-v for INFO, -vv for DEBUG) |

**Verbosity Levels:**
- **0 (default)**: ERROR level - Only critical errors are shown
- **1 (-v)**: INFO level - General information and warnings
- **2 (-vv)**: DEBUG level - Detailed debugging information

## Parse Commands

Parse commands extract and process data from EPU files without persisting to the backend API. These are primarily used for development, debugging, and data validation purposes.

### parse dir

Parse an entire EPU output directory structure that may contain multiple grids.

```bash
python -m smartem_agent parse dir [OPTIONS] EPU_OUTPUT_DIR
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `epu_output_dir` | str | Yes | Path to EPU output directory containing multiple grid directories |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse dir /data/microscopy/session_20240115 -v
```

**Use Cases:**
- Batch processing of multiple grid datasets
- Session-level data analysis and validation
- Quality control across entire microscopy sessions

### parse grid

Parse a single grid data directory containing EPU acquisition files.

```bash
python -m smartem_agent parse grid [OPTIONS] GRID_DATA_DIR
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `grid_data_dir` | str | Yes | Path to individual grid data directory |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse grid /data/microscopy/session_20240115/Grid_001 -vv
```

**Use Cases:**
- Single grid analysis and debugging
- Grid-specific data extraction
- Verification of individual acquisition datasets

### parse session

Parse an EPU session manifest file (typically `EpuSession.dm`).

```bash
python -m smartem_agent parse session [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to EPU session manifest file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse session /data/microscopy/Grid_001/EpuSession.dm
```

**Output:** Session metadata including acquisition parameters, timestamps, and instrument configuration.

### parse atlas

Parse an atlas manifest file (typically `Atlas/Atlas.dm`).

```bash
python -m smartem_agent parse atlas [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to atlas manifest file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse atlas /data/microscopy/Grid_001/Sample*/Atlas/Atlas.dm
```

**Output:** Atlas information including grid square positions, tile arrangements, and overview image metadata.

### parse gridsquare-metadata

Parse grid square metadata files (typically `Metadata/GridSquare_*.dm`).

```bash
python -m smartem_agent parse gridsquare-metadata [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to grid square metadata file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse gridsquare-metadata /data/microscopy/Grid_001/Metadata/GridSquare_12345.dm
```

**Output:** Grid square-specific metadata including foil hole positions and targeting information.

### parse gridsquare

Parse grid square manifest files (typically `Images-Disc*/GridSquare_*/GridSquare_*.xml`).

```bash
python -m smartem_agent parse gridsquare [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to grid square manifest file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse gridsquare /data/microscopy/Grid_001/Images-Disc1/GridSquare_12345/GridSquare_20240115_143022.xml
```

**Output:** Grid square acquisition details and image collection parameters.

### parse foilhole

Parse foil hole manifest files (typically `Images-Disc*/GridSquare_*/Data/FoilHole_*.xml`).

```bash
python -m smartem_agent parse foilhole [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to foil hole manifest file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse foilhole /data/microscopy/Grid_001/Images-Disc1/GridSquare_12345/Data/FoilHole_1234567_Data_20240115_143045_fractions.xml
```

**Output:** Foil hole targeting information and acquisition metadata.

### parse micrograph

Parse micrograph manifest files (typically `Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*.xml`).

```bash
python -m smartem_agent parse micrograph [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | str | Yes | Path to micrograph manifest file |
| `--verbose` | count | No | Verbosity level (see [Global Options](#global-options)) |

**Example:**
```bash
python -m smartem_agent parse micrograph /data/microscopy/Grid_001/Images-Disc1/GridSquare_12345/FoilHoles/FoilHole_1234567_20240115_143045.xml
```

**Output:** Individual micrograph metadata including exposure parameters and image quality metrics.

## Validate Command

The validate command checks EPU project directory structure for completeness and compliance with expected formats.

```bash
python -m smartem_agent validate [OPTIONS] PATH
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | str | Yes | - | Path to EPU project directory to validate |
| `--verbose` | count | No | 0 | Verbosity level (see [Global Options](#global-options)) |

**Exit Codes:**
- **0**: Directory structure is valid
- **1**: Directory structure is invalid (validation errors found)

**Example:**
```bash
python -m smartem_agent validate /data/microscopy/Grid_001 -v
```

**Validation Checks:**
- Presence of required EPU session files
- Directory structure compliance
- File naming convention adherence
- Metadata file accessibility

**Output:**
- **Valid structure**: Confirmation message with no errors
- **Invalid structure**: Detailed list of structural issues and missing components

## Watch Command

The watch command provides real-time monitoring of EPU data directories, automatically processing new files and communicating with the SmartEM backend.

```bash
python -m smartem_agent watch [OPTIONS] PATH
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | Path | Yes | - | Directory to monitor for file changes |
| `--dry-run` | bool | No | False | Run without making API calls to backend |
| `--api-url` | str | No | `http://127.0.0.1:8000` | Backend API endpoint URL |
| `--log-file` | str | No | `fs_changes.log` | Log file path for change events |
| `--log-interval` | float | No | 10.0 | Logging interval in seconds |
| `--agent-id` | str | No | None | Agent identifier for SSE connection |
| `--session-id` | str | No | None | Session identifier for SSE connection |
| `--sse-timeout` | int | No | 30 | SSE connection timeout in seconds |
| `--heartbeat-interval` | int | No | 60 | Agent heartbeat interval in seconds (0 to disable) |
| `--verbose` | count | No | 0 | Verbosity level (see [Global Options](#global-options)) |

### Core Parameters

#### path
**Type:** Path (required)
**Description:** The root directory to monitor for EPU data files. Must be an existing directory containing or expected to contain EPU acquisition data.

**Example:**
```bash
python -m smartem_agent watch /data/microscopy/active_session
```

#### --dry-run
**Type:** Boolean flag
**Default:** False
**Description:** Run the agent in simulation mode without making API calls to the backend. Useful for testing file monitoring and parsing without affecting production systems.

**Example:**
```bash
python -m smartem_agent watch /data/test --dry-run
```

**Behaviour:**
- File monitoring and parsing operate normally
- No data is sent to the backend API
- Uses in-memory data storage only
- Ideal for development and testing scenarios

### API Integration Parameters

#### --api-url
**Type:** String
**Default:** `http://127.0.0.1:8000`
**Description:** URL of the SmartEM backend API endpoint. The agent will attempt to connect to this URL for data persistence and real-time communication.

**Examples:**
```bash
# Local development
python -m smartem_agent watch /data --api-url http://localhost:8000

# Production deployment
python -m smartem_agent watch /data --api-url https://smartem.facility.ac.uk/api
```

**Connection Validation:** The agent validates API connectivity at startup and exits with error code 1 if the API is unreachable (unless using `--dry-run`).

#### --agent-id
**Type:** String (optional)
**Description:** Unique identifier for this agent instance. Required for real-time communication with the backend via Server-Sent Events (SSE).

**Format Recommendations:**
- Use descriptive names: `microscope-01`, `titan-krios-lab2`
- Include facility/location information for multi-site deployments
- Ensure uniqueness across all agent instances

#### --session-id
**Type:** String (optional)
**Description:** Session identifier linking this agent to a specific microscopy session. Required for real-time communication with the backend.

**Usage:** Typically generated by the backend or provided by the acquisition software. Used to group related data and instructions.

### Real-Time Communication Parameters

#### --sse-timeout
**Type:** Integer
**Default:** 30 seconds
**Description:** Timeout for Server-Sent Events (SSE) connections to the backend. Controls how long the agent waits for backend responses.

**Recommendations:**
- **Local networks:** 10-30 seconds
- **Remote/unstable connections:** 60-120 seconds
- **High-latency networks:** 120+ seconds

#### --heartbeat-interval
**Type:** Integer
**Default:** 60 seconds
**Description:** Interval between heartbeat messages sent to the backend to maintain connection health monitoring. Set to 0 to disable heartbeats.

**Connection Health:** The backend considers connections stale after 2 minutes without heartbeats, so values should be well below 120 seconds.

**Examples:**
```bash
# Standard monitoring (every minute)
python -m smartem_agent watch /data --agent-id agent-01 --session-id session-123

# Frequent monitoring (every 30 seconds)
python -m smartem_agent watch /data --agent-id agent-01 --session-id session-123 --heartbeat-interval 30

# Disable heartbeats (not recommended for production)
python -m smartem_agent watch /data --agent-id agent-01 --session-id session-123 --heartbeat-interval 0
```

### Logging Parameters

#### --log-file
**Type:** String
**Default:** `fs_changes.log`
**Description:** Path to log file for filesystem change events. The agent writes structured JSON logs of all detected file changes to this file.

**Log Content:** File creation, modification events, timestamps, file sizes, and processing status.

#### --log-interval
**Type:** Float
**Default:** 10.0 seconds
**Description:** Batching interval for filesystem change logging. Events are collected and written to the log file at this interval to improve performance.

**Performance Impact:**
- **Lower values (1-5s):** More responsive logging, higher I/O overhead
- **Higher values (30-60s):** Better performance, less frequent updates
- **Very high values (>60s):** Risk of log loss on unexpected shutdown

### Usage Examples

#### Basic Monitoring
```bash
# Monitor directory with default settings
python -m smartem_agent watch /data/microscopy/Grid_001
```

#### Production Deployment with Real-Time Communication
```bash
python -m smartem_agent watch /data/microscopy/active_session \
  --api-url https://smartem-backend.facility.ac.uk \
  --agent-id microscope-titan-01 \
  --session-id session-20240115-001 \
  --heartbeat-interval 45 \
  --verbose
```

#### Development and Testing
```bash
# Dry run with debug logging
python -m smartem_agent watch /data/test_data \
  --dry-run \
  --log-interval 5.0 \
  --verbose --verbose
```

#### High-Performance Production Setup
```bash
python -m smartem_agent watch /data/high_throughput \
  --api-url http://backend:8000 \
  --agent-id facility-workstation-03 \
  --session-id batch-processing-session \
  --log-interval 30.0 \
  --sse-timeout 120 \
  --heartbeat-interval 30
```

## File Pattern Matching

All commands that process EPU data use consistent file pattern matching to identify relevant files:

**Supported Patterns:**
- `EpuSession.dm` - EPU session files
- `Metadata/GridSquare_*.dm` - Grid square metadata
- `Images-Disc*/GridSquare_*/GridSquare_*_*.xml` - Grid square manifests
- `Images-Disc*/GridSquare_*/Data/FoilHole_*_Data_*_*_*_*.xml` - Foil hole data
- `Images-Disc*/GridSquare_*/FoilHoles/FoilHole_*_*_*.xml` - Foil hole positions
- `Sample*/Atlas/Atlas.dm` - Atlas files

**Pattern Matching Rules:**
- Recursive directory traversal for nested structures
- Case-sensitive matching
- Wildcards support standard shell globbing patterns
- Both Windows and Linux path separators are supported

## Exit Codes

| Code | Condition | Description |
|------|-----------|-------------|
| 0 | Success | Command completed successfully |
| 1 | Validation Error | Directory validation failed (validate command) |
| 1 | API Connection Error | Unable to connect to backend API |
| 1 | Directory Not Found | Specified directory does not exist |
| 1 | Permission Error | Insufficient permissions to access directory or files |
| 2 | Keyboard Interrupt | User terminated command with Ctrl+C |

## Integration Notes

### Backend API Requirements

The watch command requires a compatible SmartEM backend API with the following endpoints:

- **Status endpoint**: `GET /status` - For connectivity validation
- **Data persistence**: Various endpoints for storing parsed EPU data
- **SSE endpoint**: `GET /agent/{agent_id}/session/{session_id}/instructions/stream` - For real-time communication
- **Heartbeat endpoint**: `POST /agent/{agent_id}/session/{session_id}/heartbeat` - For connection health

### Environment Considerations

**File System Permissions:**
- Read access to EPU data directories
- Write access to log file location
- Appropriate permissions for recursive directory traversal

**Network Requirements:**
- HTTP/HTTPS connectivity to backend API
- Stable connection for SSE streaming (when using real-time features)
- Consideration of firewall and proxy configurations

**Resource Requirements:**
- Memory usage scales with directory size and file count
- CPU usage depends on file processing frequency
- Network bandwidth for real-time data transmission

### Performance Considerations

**Large Directory Structures:**
- Initial directory parsing can be resource-intensive
- Consider using `--log-interval` tuning for high-frequency file changes
- Monitor memory usage with very large datasets

**Network Latency:**
- Adjust `--sse-timeout` for high-latency connections
- Consider `--heartbeat-interval` tuning based on network stability
- Use `--dry-run` for local testing and development

This CLI reference provides comprehensive coverage of all SmartEM Agent command-line functionality. For additional help with specific use cases or troubleshooting, refer to the [CLI Troubleshooting Guide](troubleshoot-cli.md).
