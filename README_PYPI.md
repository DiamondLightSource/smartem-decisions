# smartem-decisions

[![PyPI version](https://img.shields.io/pypi/v/smartem-decisions)](https://pypi.org/project/smartem-decisions/)
[![Python Versions](https://img.shields.io/pypi/pyversions/smartem-decisions)](https://pypi.org/project/smartem-decisions/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/release-smartem-decisions.yml/badge.svg)](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/release-smartem-decisions.yml)

Smart data collection system for cryo-electron microscopy at Diamond Light Source.

## Installation

### SmartEM Agent (data collection)

```bash
pip install smartem-decisions[agent]
```

**Windows executable:** Download the latest `smartem-agent-windows-vX.Y.Z.exe` from [GitHub Releases](https://github.com/DiamondLightSource/smartem-decisions/releases).

### SmartEM Backend (API server)

```bash
pip install smartem-decisions[backend]
```

### All components

```bash
pip install smartem-decisions[all]
```

## Usage

### Agent

Watch a directory for EPU output and send data to the backend:

```bash
# Basic usage
smartem-agent watch /path/to/epu/output --api-url http://localhost:8000

# Dry run (no API calls)
smartem-agent watch /path/to/epu/output --dry-run

# Verbose output
smartem-agent watch /path/to/epu/output -vv
```

Parse EPU data without watching:

```bash
smartem-agent parse dir /path/to/epu/output
smartem-agent parse session /path/to/EpuSession.dm
smartem-agent parse atlas /path/to/Atlas.dm
```

### Backend

Start the API server and message consumer:

```bash
# HTTP API server
python -m smartem_backend.api_server

# Message queue consumer
python -m smartem_backend.consumer -v
```

## Components

| Package | Description |
|---------|-------------|
| `smartem_agent` | Data collection agent that monitors EPU output |
| `smartem_backend` | Core backend with HTTP API and message queue processing |
| `smartem_common` | Shared schemas, types, and utilities |

## Installation Extras

| Extra | Description |
|-------|-------------|
| `[agent]` | Agent dependencies (watchdog, lxml) |
| `[backend]` | Backend dependencies (FastAPI, SQLAlchemy, Pika) |
| `[common]` | Core schemas only (Pydantic) |
| `[images]` | Image processing (Pillow, mrcfile, tifffile) |
| `[dev]` | Development tools (pytest, ruff, pyright) |
| `[all]` | All dependencies |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
ruff format --check src/

# Type check
pyright
```

## Documentation

- [Backend API Server](https://diamondlightsource.github.io/smartem-devtools/docs/backend/api-server)
- [Agent Deployment](https://diamondlightsource.github.io/smartem-devtools/docs/agent/deployment)
- [Kubernetes Deployment](https://diamondlightsource.github.io/smartem-devtools/docs/operations/kubernetes)

## Links

- **PyPI**: https://pypi.org/project/smartem-decisions/
- **Repository**: https://github.com/DiamondLightSource/smartem-decisions
- **Issues**: https://github.com/DiamondLightSource/smartem-decisions/issues
- **Changelog**: [GitHub Releases](https://github.com/DiamondLightSource/smartem-decisions/releases)

## License

Apache-2.0
