# Configure Environment Variables

This guide explains the different environment configuration files used in the SmartEM Decisions project and their specific purposes.

## Overview

The project uses multiple environment configuration patterns for different deployment scenarios:

| File Pattern | Purpose | Gitignored | Created From |
|--------------|---------|------------|--------------|
| `.env.example` | Template for local development | No (committed) | N/A |
| `.env` | Local development on host OS | Yes | Copy from `.env.example` |
| `.env.example.k8s.development` | Template for K8s development | No (committed) | N/A |
| `.env.k8s.development` | K8s development cluster config | Yes | Copy from `.env.example.k8s.development` |
| `.env.example.k8s.staging` | Template for K8s staging | No (committed) | N/A |
| `.env.k8s.staging` | K8s staging cluster config | Yes | Copy from `.env.example.k8s.staging` |
| `.env.example.k8s.production` | Template for K8s production | No (committed) | N/A |
| `.env.k8s.production` | K8s production cluster config | Yes | Copy from `.env.example.k8s.production` |
| `.env.example.mcp` | Template for MCP configuration | No (committed) | N/A |
| `.env.mcp` | MCP server configuration | Yes | Copy from `.env.example.mcp` |

## Environment File Types

### 1. Local Development: `.env`

**Use Case**: Running backend services directly on your host OS (outside containers) while connecting to K8s infrastructure.

**When to Use**:
- Day-to-day development with `python -m smartem_backend.consumer`
- Running API server locally with `python -m smartem_backend.api_server`
- E2E testing with `./tools/run-e2e-test.sh`
- Manual debugging and development workflows

**Setup**:
```bash
cp .env.example .env
# Edit .env with your local credentials
```

**Key Configuration**:
```bash
# Connect to K8s infrastructure via NodePorts
POSTGRES_HOST=localhost
POSTGRES_PORT=30432          # K8s NodePort for PostgreSQL
RABBITMQ_HOST=localhost
RABBITMQ_PORT=30672          # K8s NodePort for RabbitMQ

# Run services on host OS
HTTP_API_PORT=8000
```

**Used By**:
- Python code via `load_dotenv()` in `smartem_backend/consumer.py`, `smartem_backend/utils.py`
- Docker `entrypoint.sh` when running containers outside Kubernetes
- E2E test scripts (`./tools/run-e2e-test.sh`)

### 2. Kubernetes Development: `.env.k8s.development`

**Use Case**: Deploying SmartEM to local K8s cluster (k3s) for development.

**When to Use**:
- Running `./tools/dev-k8s.sh up`
- Setting up local development cluster with all services

**Setup**:
```bash
cp .env.example.k8s.development .env.k8s.development
# Add your DOCKER_USERNAME, DOCKER_EMAIL, DOCKER_PASSWORD (GitHub token)
```

**Key Configuration**:
```bash
# Docker/GHCR credentials for pulling container images
DOCKER_USERNAME=your-github-username
DOCKER_EMAIL=your-email@example.com
DOCKER_PASSWORD=ghp_your_github_token

# K8s internal service names (not localhost)
POSTGRES_HOST=postgres-service
POSTGRES_PORT=5432
RABBITMQ_HOST=rabbitmq-service
RABBITMQ_PORT=5672

# Credentials (can be simple for local dev)
POSTGRES_USER=username
POSTGRES_PASSWORD=password
RABBITMQ_USER=username
RABBITMQ_PASSWORD=password
```

**Used By**:
- `./tools/dev-k8s.sh` script to create K8s Secrets and ConfigMaps

### 3. Kubernetes Staging: `.env.k8s.staging`

**Use Case**: Deploying to staging Kubernetes cluster.

**Setup**:
```bash
cp .env.example.k8s.staging .env.k8s.staging
# Add production-like credentials and configuration
```

**Key Differences from Development**:
- Real credentials (not test values)
- Production-like service names and ports
- Staging-specific CORS origins
- May use sealed secrets instead of plain credentials

**Used By**:
- CI/CD pipelines for staging deployments
- `DEPLOY_ENV=staging ./tools/dev-k8s.sh up` (if adapted for remote clusters)

### 4. Kubernetes Production: `.env.k8s.production`

**Use Case**: Deploying to production Kubernetes cluster.

**Setup**:
```bash
cp .env.example.k8s.production .env.k8s.production
# Add production credentials (should use Sealed Secrets in practice)
```

**Security Considerations**:
- Should use Sealed Secrets (encrypted) instead of plain `.env` files
- Credentials should be rotated regularly
- Access to this file should be strictly controlled
- See [Manage Kubernetes Secrets](manage-kubernetes-secrets.md) for best practices

**Used By**:
- Production CI/CD pipelines
- Production deployment automation

### 5. MCP Configuration: `.env.mcp`

**Use Case**: Configuring Model Context Protocol (MCP) server for Claude Code integration.

**Setup**:
```bash
cp .env.example.mcp .env.mcp
# Configure paths and adapter settings
```

**Key Configuration**:
```bash
SMARTEM_MCP_DATA_PATH=/path/to/epu/sessions    # Filesystem adapter
SMARTEM_MCP_API_URL=http://backend:8000        # API adapter
SMARTEM_MCP_ADAPTER=filesystem                 # Adapter selection
SMARTEM_MCP_LOG_LEVEL=INFO
```

**Used By**:
- MCP server when run via Claude Code
- See [Use MCP Interface](use-mcp-interface.md) for details

## Quick Start: First-Time Setup

For local development on a new machine:

```bash
# 1. Copy environment templates
cp .env.example .env
cp .env.example.k8s.development .env.k8s.development

# 2. Edit .env.k8s.development with your GitHub credentials
# Required: DOCKER_USERNAME, DOCKER_EMAIL, DOCKER_PASSWORD
nano .env.k8s.development

# 3. Start K8s cluster (creates infrastructure)
./tools/dev-k8s.sh up

# 4. .env is already configured to connect to K8s NodePorts
# No changes needed unless you want custom ports

# 5. Test local development
source .venv/bin/activate
python -m smartem_backend.api_server
```

## How Environment Variables Are Loaded

### Python Services

All Python services use `load_dotenv(override=False)`:

```python
from dotenv import load_dotenv
load_dotenv(override=False)  # Loads .env but doesn't override existing env vars
```

**Loading Priority** (first wins):
1. Already exported environment variables (from `export` or `source .env`)
2. Variables in `.env` file (loaded by `load_dotenv()`)
3. Hardcoded defaults in code (if any)

**Important for Testing**:
When running E2E tests or manual services, you must export variables BEFORE starting services:

```bash
# Export all variables from .env
set -a && source .env && set +a

# Now start services
python -m smartem_backend.api_server
python -m smartem_backend.consumer
```

### Docker Containers

Container behaviour depends on runtime environment:

```bash
# entrypoint.sh checks for Kubernetes
if [ -z "$KUBERNETES_SERVICE_HOST" ]; then
    # Running locally - source .env file
    source .env
else
    # Running in K8s - use ConfigMap/Secrets
    # Variables already injected by K8s
fi
```

### Kubernetes Deployments

When running in Kubernetes:
- ConfigMaps provide non-sensitive configuration (hosts, ports, URLs)
- Secrets provide sensitive data (passwords, tokens)
- `.env` files are NOT used inside containers
- All configuration comes from K8s resources created by `dev-k8s.sh`

## Common Scenarios

### Scenario 1: Local Development with K8s Infrastructure

**Goal**: Run backend/agent on host OS, connect to K8s database/RabbitMQ.

```bash
# 1. Start K8s cluster
./tools/dev-k8s.sh up

# 2. Use .env (already configured for NodePorts)
cat .env
# POSTGRES_HOST=localhost
# POSTGRES_PORT=30432
# RABBITMQ_HOST=localhost
# RABBITMQ_PORT=30672

# 3. Run services on host
source .venv/bin/activate
python -m smartem_backend.api_server    # Uses .env via load_dotenv()
python -m smartem_backend.consumer -vv  # Uses .env via load_dotenv()
```

### Scenario 2: Full K8s Deployment

**Goal**: Everything runs in K8s (no host OS services).

```bash
# 1. Configure K8s environment
cp .env.example.k8s.development .env.k8s.development
# Edit with your credentials

# 2. Deploy
./tools/dev-k8s.sh up

# 3. All services run in pods
kubectl get pods -n smartem-decisions
# Access via NodePorts:
# - API: http://localhost:30080
# - Adminer: http://localhost:30808
# - RabbitMQ UI: http://localhost:30673
```

### Scenario 3: E2E Testing

**Goal**: Run automated E2E tests with recorded microscope data.

```bash
# 1. Ensure .env exists and is configured
test -f .env || cp .env.example .env

# 2. Start K8s cluster
./tools/dev-k8s.sh up

# 3. Run E2E test (script loads .env automatically)
./tools/run-e2e-test.sh

# The script does:
# - source .env (loads variables)
# - Starts services on host OS
# - Runs recorded data playback
# - Collects results
```

## Troubleshooting

### Issue: Services can't connect to database

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Check**:
1. Is K8s cluster running? `kubectl get pods -n smartem-decisions`
2. Are NodePorts accessible? `curl http://localhost:30432` (should refuse connection but not timeout)
3. Is `.env` configured correctly?
   ```bash
   grep POSTGRES .env
   # Should show localhost:30432 for K8s NodePort
   ```

### Issue: Docker password invalid in dev-k8s.sh

**Symptom**: `DOCKER_PASSWORD does not appear to be a valid GitHub token`

**Solution**:
```bash
# Generate token: https://github.com/settings/tokens
# Or use GitHub CLI
gh auth token

# Add to .env.k8s.development
DOCKER_PASSWORD=ghp_your_token_here
```

### Issue: Services using wrong database

**Symptom**: Services connect to different database than expected.

**Check loading priority**:
```bash
# Unset ALL environment variables first
unset POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD

# Then load .env
set -a && source .env && set +a

# Verify variables
env | grep POSTGRES
```

## Related Documentation

- [Run Backend Services](run-backend.md) - Starting backend API and consumer
- [Run E2E Development Simulation](run-e2e-dev-simulation.md) - E2E testing workflows
- [Deploy to Kubernetes](deploy-kubernetes.md) - K8s deployment guide
- [Manage Kubernetes Secrets](manage-kubernetes-secrets.md) - Sealed Secrets and security
- [Database Migrations](database-migrations.md) - Alembic migration workflow
- [Use MCP Interface](use-mcp-interface.md) - Claude Code MCP integration
