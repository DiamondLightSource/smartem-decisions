# Kubernetes Deployment

This directory contains Kubernetes deployment configurations for SmartEM Decisions across different environments.

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
- **📡 SmartEM HTTP API**: http://localhost:30080/health
- **📚 API Documentation**: http://localhost:30080/docs

> **Note**: The script automatically handles GitHub Container Registry authentication and waits for all pods to be ready.

## Structure

```
k8s/
├── environments/
│   ├── development/          # Local development (k3s)
│   ├── staging/             # Staging environment (pollux)
│   └── production/          # Production environment (argos?)
└── README.md
```

## Environments

### Development
- **Purpose**: Local development using k3s
- **Features**: 
  - Includes all services (postgres, rabbitmq, mongodb, elasticsearch, adminer)
  - NodePort services for external access
  - Single replicas with modest resource limits
  - Includes Adminer for database management
- **Namespace**: `smartem-decisions`

### Staging
- **Purpose**: Pre-production testing
- **Features**:
  - Production-like setup without development tools
  - ClusterIP services (no external NodePort)
  - No Adminer
  - Single replicas with moderate resource limits
- **Namespace**: `smartem-decisions-staging`

### Production
- **Purpose**: Production deployment
- **Features**:
  - Multiple replicas for high availability (3 API, 2 workers)
  - Higher resource limits
  - ClusterIP services only
  - No development tools
- **Namespace**: `smartem-decisions-production`

## Prerequisites

### GitHub Container Registry Access
Create a GitHub token with `read:packages` permission and configure Docker registry access:

```bash
# Login to GHCR
echo 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 | docker login ghcr.io -u vredchenko --password-stdin
```

## Deployment

### Deploy to Development (Local k3s)
```bash
# Create GHCR secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=vredchenko \
  --docker-password=YOUR_TOKEN \
  --docker-email=val.redchenko@diamond.ac.uk \
  --namespace=smartem-decisions

# Deploy application
kubectl apply -k k8s/environments/development/
```

### Deploy to Staging
```bash
# Create GHCR secret  
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=vredchenko \
  --docker-password=YOUR_TOKEN \
  --docker-email=val.redchenko@diamond.ac.uk \
  --namespace=smartem-decisions-staging

# Deploy application
kubectl apply -k k8s/environments/staging/
```

### Deploy to Production
```bash
# Create GHCR secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=vredchenko \
  --docker-password=YOUR_TOKEN \
  --docker-email=val.redchenko@diamond.ac.uk \
  --namespace=smartem-decisions-production

# Deploy application
kubectl apply -k k8s/environments/production/
```

## Configuration

Each environment contains:
- `namespace.yaml` - Namespace definition
- `configmap.yaml` - Configuration values
- `secrets.yaml` - Secret values (base64 encoded)
- `postgres.yaml` - PostgreSQL database
- `rabbitmq.yaml` - RabbitMQ message broker
- `mongodb.yaml` - MongoDB document store
- `elasticsearch.yaml` - Elasticsearch search engine
- `smartem-http-api.yaml` - HTTP API service
- `smartem-worker.yaml` - Background worker service
- `adminer.yaml` - Database admin tool (development only)
- `kustomization.yaml` - Kustomize configuration

## Secrets Management

Before deploying, update the secrets in each environment:

1. Create your secret values:

```bash
echo -n "your_username" | base64
echo -n "your_password" | base64
```

2. Update the base64 encoded values in `secrets.yaml` for each environment

## Service Access

### Development Environment
- HTTP API: http://localhost:30080
- Postgres: localhost:30432
- RabbitMQ Management: http://localhost:30673
- Adminer: http://localhost:30808

### Staging/Production
Services are only accessible within the cluster via ClusterIP. Use port-forwarding for access:

```bash
# Forward HTTP API
kubectl port-forward -n smartem-decisions-staging svc/smartem-http-api-service 8080:80

# Forward RabbitMQ Management
kubectl port-forward -n smartem-decisions-staging svc/rabbitmq-service 15672:15672
```

## Debugging

Access running containers:
```bash
# Development
kubectl exec -it -n smartem-decisions deployment/smartem-http-api -- /bin/bash
kubectl exec -it -n smartem-decisions deployment/smartem-worker -- /bin/bash

# Check environment variables
kubectl exec -it -n smartem-decisions deployment/smartem-http-api -- env | grep -E '(RABBIT|POSTGRES)'
```

## Monitoring

Check deployment status:
```bash
# Development
kubectl get all -n smartem-decisions

# Staging  
kubectl get all -n smartem-decisions-staging

# Production
kubectl get all -n smartem-decisions-production
```

## Cleanup

Remove a deployment:

```bash
kubectl delete -k k8s/environments/development/
kubectl delete -k k8s/environments/staging/
kubectl delete -k k8s/environments/production/
```

## Reference Files (Not Yet Implemented)

The following files provide examples of advanced production features that are not currently integrated into the environment-specific deployments:

### `secret.example.yaml` - Secrets Template

Provides a template for creating production secrets with the correct structure and required keys:

- Documents all required secret keys (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`)
- Shows proper base64 encoding format
- Serves as reference for external secret management systems
- Template for production secret creation

**Usage**: Copy and modify with actual production credentials, ensuring proper base64 encoding.

### `ingress.yaml` - External Access Configuration

Production-ready ingress configuration for exposing the HTTP API externally:

- **Currently missing** from staging and production environments (they use ClusterIP only)
- Configures NGINX ingress controller with proper routing
- Enables external domain access to the API
- Includes path rewriting for proper request handling

**Key considerations**:
- Update `host: smartem-api.your-domain.com` with actual production domain
- Requires NGINX ingress controller installed in cluster
- Should be integrated into production environment when external access is needed

### `hpa.yaml` - Horizontal Pod Autoscaler

Automatic scaling configuration based on resource utilisation:

- **Currently missing** from production environment (uses fixed 3 API replicas)
- Auto-scales HTTP API from 2-10 replicas based on 70% CPU utilisation
- Essential for handling variable workloads in production
- Modern Kubernetes autoscaling best practices

**Integration notes**:
- Should be added to production `kustomization.yaml` when autoscaling is required
- Requires metrics server to be installed in cluster
- May need resource requests/limits tuning based on actual usage patterns

### Future Integration

These reference files should be integrated into the appropriate environments when the following production features are needed:

1. **External API access** → Add `ingress.yaml` to production/staging
2. **Variable load handling** → Add `hpa.yaml` to production  
3. **Secret management** → Use `secret.example.yaml` as template for production secrets
