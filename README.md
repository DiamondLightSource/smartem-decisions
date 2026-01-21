[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-6366f1?logo=claude)](https://claude.ai/code)
[![CI](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/smartem-decisions/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/smartem-decisions/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/smartem-decisions)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# SmartEM Decisions

A comprehensive system for smart data collection and processing in cryo-electron microscopy, designed to optimise acquisition workflows through intelligent decision-making and real-time data analysis.

## Quick Links

Source          | <https://github.com/DiamondLightSource/smartem-decisions>
:---:           | :---:
Docker          | `docker run ghcr.io/DiamondLightSource/smartem-backend:latest`
Documentation   | <https://DiamondLightSource.github.io/smartem-devtools>
Releases        | <https://github.com/DiamondLightSource/smartem-decisions/releases>
Project Board   | <https://github.com/orgs/DiamondLightSource/projects/33/views/1>

## System Components

- **`smartem_common`**: Shared schemas, types, and utilities used across all components
- **`smartem_backend`**: Core backend service with HTTP API, database operations, and message queue processing
- **`smartem_agent`**: Data collection agent that monitors EPU output and communicates with backend

## Quick Start

```bash
# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# Start services
python -m smartem_backend.api_server      # HTTP API server
python -m smartem_backend.consumer -v     # Message queue consumer
```

## Documentation

Full documentation: <https://DiamondLightSource.github.io/smartem-devtools>

- [Backend API Server](https://diamondlightsource.github.io/smartem-devtools/docs/backend/api-server)
- [Agent Deployment](https://diamondlightsource.github.io/smartem-devtools/docs/agent/deployment)
- [Kubernetes Deployment](https://diamondlightsource.github.io/smartem-devtools/docs/operations/kubernetes)

## Contributing

See the [contribution guide](https://diamondlightsource.github.io/smartem-devtools/docs/development/contributing) for development workflow and code standards.

## Licence

Apache-2.0
