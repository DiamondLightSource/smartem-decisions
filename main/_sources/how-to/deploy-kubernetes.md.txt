# Kubernetes Deployment

This directory contains Kubernetes deployment configurations for SmartEM Backend across different environments.

## Quick Start (Development)

For local development, use the convenient script that provides a docker-compose-like experience:

```bash
# Start the development environment (equivalent to docker-compose up -d)
./tools/dev-k8s.sh

# Check status (equivalent to docker ps)
./tools/dev-k8s.sh status

# View logs for a service
./tools/dev-k8s.sh logs smartem-http-api

# Stop the environment (equivalent to docker-compose down)
./tools/dev-k8s.sh down

# Restart everything
./tools/dev-k8s.sh restart

# Get help
./tools/dev-k8s.sh --help
```

### Access URLs
Once the environment is running, you can access:
- **📊 Adminer (Database UI)**: http://localhost:30808
- **🐰 RabbitMQ Management**: http://localhost:30673
- **📡 SmartEM Backend HTTP API**: http://localhost:30080/health
- **📚 API Documentation**: http://localhost:30080/docs

> **Note**: The script automatically handles GitHub Container Registry authentication and waits for all pods to be ready.

## Kubernetes Structure

```
k8s/
├── environments/
│   ├── development/          # Local development (k3s)
│   ├── staging/             # Staging environment (pollux)
│   └── production/          # Production environment (argos?)
└── README.md
```

For detailed Kubernetes deployment instructions, environment configurations, and troubleshooting, see the [k8s directory documentation](k8s/).
