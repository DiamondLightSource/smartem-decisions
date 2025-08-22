# Managing Kubernetes Secrets

This guide explains how to securely manage secrets in the SmartEM Decisions project using Bitnami Sealed Secrets.

## Overview

The SmartEM Decisions project uses [Bitnami Sealed Secrets](https://sealed-secrets.netlify.app/) to securely manage sensitive 
configuration data such as database credentials and message queue passwords. Sealed Secrets provide a secure alternative to 
storing plain-text secrets in version control.

### Why Sealed Secrets?

Sealed Secrets offer several security advantages over traditional Kubernetes secrets:

- **Version Control Safe**: Sealed secrets are encrypted and safe to commit to Git repositories
- **Asymmetric Encryption**: Uses public/private key cryptography for maximum security  
- **Cluster-Specific**: Secrets are encrypted for a specific cluster and cannot be used elsewhere
- **Automatic Decryption**: The sealed-secrets controller automatically decrypts secrets in the cluster
- **Audit Trail**: All secret changes are tracked in version control with proper attribution

### How It Works

1. **Public Key Encryption**: Secrets are encrypted using the cluster's public key
2. **Safe Storage**: Encrypted sealed secrets are committed to version control
3. **Automatic Decryption**: The sealed-secrets controller watches for sealed secrets and creates regular Kubernetes secrets
4. **Application Access**: Applications access secrets normally via environment variables or mounted volumes

## Prerequisites

Before managing sealed secrets, ensure you have the required tools installed:

### Required Tools

- **kubectl**: Kubernetes command-line tool with cluster access
- **kubeseal**: Bitnami Sealed Secrets CLI tool
- **openssl**: For secure password generation (development environments)

### Installing kubeseal

```bash
# Download latest release (Linux)
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/kubeseal-0.18.0-linux-amd64.tar.gz
tar -xvzf kubeseal-0.18.0-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal

# Verify installation
kubeseal --version
```

### Cluster Requirements

The sealed-secrets controller must be installed in your Kubernetes cluster. For Diamond Light Source clusters, this is 
typically pre-installed. Verify the controller is running:

```bash
kubectl get pods -n kube-system -l name=sealed-secrets-controller
```

## Quick Start

The project includes a convenient script that handles the entire sealed secret generation process:

```bash
# Generate secrets for development (auto-generated passwords)
./tools/generate-sealed-secrets.sh development

# Generate secrets for production (interactive prompts)
./tools/generate-sealed-secrets.sh production

# Generate secrets for all environments
./tools/generate-sealed-secrets.sh all
```

## Environment-Specific Workflows

### Development Environment

Development environments use automatically generated secure passwords for convenience:

```bash
./tools/generate-sealed-secrets.sh development
```

This will:
- Generate cryptographically secure random passwords
- Create sealed secrets for the `smartem-decisions` namespace  
- Display a summary of generated usernames (passwords remain sealed)
- Update `k8s/environments/development/secrets.yaml`

### Staging and Production Environments

Production and staging environments require interactive credential input for security:

```bash
./tools/generate-sealed-secrets.sh production
```

You'll be prompted to provide:
- PostgreSQL username and password
- RabbitMQ username and password

**Security Note**: Passwords are entered without echo (not displayed on screen) and never appear in shell history.

## Manual Secret Management

For advanced use cases, you can manually create sealed secrets:

### 1. Create Temporary Secret

```bash
# Create temporary secret file
kubectl create secret generic smartem-secrets \
    --namespace=smartem-decisions-production \
    --from-literal=POSTGRES_USER="secure_postgres_user" \
    --from-literal=POSTGRES_PASSWORD="secure_postgres_password" \  # pragma: allowlist secret
    --from-literal=RABBITMQ_USER="secure_rabbitmq_user" \
    --from-literal=RABBITMQ_PASSWORD="secure_rabbitmq_password" \  # pragma: allowlist secret
    --dry-run=client \
    --output=yaml > temp-secret.yaml
```

### 2. Generate Sealed Secret

```bash
# Seal the secret using cluster's public key
kubeseal --format=yaml --namespace=smartem-decisions-production < temp-secret.yaml > sealed-secret.yaml

# Clean up temporary file
rm temp-secret.yaml
```

### 3. Apply Sealed Secret

```bash
# Apply sealed secret to cluster
kubectl apply -f sealed-secret.yaml

# Verify secret was created
kubectl get secrets -n smartem-decisions-production
```

## Secret Rotation

Regular secret rotation is essential for security. Follow these steps to rotate secrets:

### 1. Generate New Credentials

```bash
# Use the generation script with new credentials
./tools/generate-sealed-secrets.sh production
```

### 2. Apply Updated Secrets

```bash
# Apply to cluster using kustomize
kubectl apply -k k8s/environments/production/
```

### 3. Restart Applications

Restart application pods to pick up new secrets:

```bash
# Restart SmartEM API pods
kubectl rollout restart deployment smartem-http-api -n smartem-decisions-production

# Restart worker pods
kubectl rollout restart deployment smartem-worker -n smartem-decisions-production
```

### 4. Verify Application Health

```bash
# Check pod status
kubectl get pods -n smartem-decisions-production

# Check application logs
kubectl logs -n smartem-decisions-production deployment/smartem-http-api --tail=50
```

## Integration with Kustomize

Sealed secrets integrate seamlessly with the project's Kustomize structure:

### Directory Structure

```
k8s/environments/
├── development/
│   ├── kustomization.yaml    # References secrets.yaml
│   └── secrets.yaml          # Sealed secret for development
├── staging/
│   ├── kustomization.yaml    # References secrets.yaml  
│   └── secrets.yaml          # Sealed secret for staging
└── production/
    ├── kustomization.yaml    # References secrets.yaml
    └── secrets.yaml          # Sealed secret for production
```

### Applying Changes

```bash
# Deploy entire environment including sealed secrets
kubectl apply -k k8s/environments/production/

# Apply only secrets
kubectl apply -f k8s/environments/production/secrets.yaml
```

## Troubleshooting

### Common Issues

**kubeseal command not found**
```bash
# Install kubeseal CLI tool
wget https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/kubeseal-linux-amd64
sudo install -m 755 kubeseal-linux-amd64 /usr/local/bin/kubeseal
```

**cannot fetch certificate error**
```bash
# Verify sealed-secrets controller is running
kubectl get pods -n kube-system -l name=sealed-secrets-controller

# Check controller logs
kubectl logs -n kube-system -l name=sealed-secrets-controller
```

**secret not being decrypted**
```bash
# Check sealed secret status
kubectl describe sealedsecret smartem-secrets -n smartem-decisions

# Verify secret was created
kubectl get secret smartem-secrets -n smartem-decisions

# Check controller events
kubectl get events -n smartem-decisions --sort-by=.metadata.creationTimestamp
```

### Sealed Secret Validation

Verify sealed secrets are correctly formatted:

```bash
# Check sealed secret structure
kubectl get sealedsecret smartem-secrets -n smartem-decisions -o yaml

# Validate with dry-run
kubectl apply --dry-run=client -f k8s/environments/development/secrets.yaml
```

### Application Connection Issues

If applications cannot connect after secret rotation:

```bash
# Check secret contents (base64 encoded)
kubectl get secret smartem-secrets -n smartem-decisions -o yaml

# Test database connection
kubectl exec -it deployment/smartem-http-api -n smartem-decisions -- \
    python -c "from smartem_backend.utils import setup_postgres_connection; setup_postgres_connection()"

# Check environment variable injection
kubectl exec -it deployment/smartem-http-api -n smartem-decisions -- env | grep POSTGRES
```

### Script Debugging

For issues with the generation script:

```bash
# Run with verbose output
bash -x ./tools/generate-sealed-secrets.sh development

# Check prerequisites manually
kubectl cluster-info
kubeseal --version
openssl version
```

## Security Best Practices

### Secret Generation

1. **Use Strong Passwords**: Generate passwords with sufficient entropy (minimum 24 characters)
2. **Unique Credentials**: Use different credentials for each environment
3. **Regular Rotation**: Rotate secrets quarterly or after security incidents
4. **Principle of Least Privilege**: Grant minimal required database/queue permissions

### Access Control

1. **Namespace Isolation**: Deploy sealed secrets to appropriate namespaces
2. **RBAC Controls**: Restrict access to sealed secret resources
3. **Audit Logging**: Monitor sealed secret creation and modification
4. **Backup Strategy**: Maintain secure backups of unsealed credentials

### Development Workflow

1. **Never Commit Plain Secrets**: Always use sealed secrets in version control
2. **Validate Before Commit**: Verify sealed secrets are properly encrypted
3. **Environment Separation**: Keep development and production secrets separate
4. **Code Review**: Review all secret-related changes before merging

## Advanced Usage

### Custom Secret Names

To use different secret names:

```bash
# Modify script variables or create custom sealed secret
kubectl create secret generic custom-secret-name \
    --namespace=smartem-decisions \
    --from-literal=API_KEY="secure_api_key" \  # pragma: allowlist secret
    --dry-run=client -o yaml | \
kubeseal --format=yaml --namespace=smartem-decisions > custom-sealed-secret.yaml
```

### Multiple Secret Sources

For complex applications requiring multiple secret sources:

```bash
# Database secrets
./tools/generate-sealed-secrets.sh production

# Additional API secrets
kubectl create secret generic api-secrets \
    --namespace=smartem-decisions-production \
    --from-literal=EXTERNAL_API_KEY="api_key_here" \  # pragma: allowlist secret
    --dry-run=client -o yaml | \
kubeseal --format=yaml --namespace=smartem-decisions-production > api-sealed-secrets.yaml
```

### Cross-Cluster Migration

When moving between clusters, sealed secrets must be regenerated:

```bash
# Export existing secret from source cluster  
kubectl get secret smartem-secrets -n smartem-decisions -o yaml > plain-secret.yaml

# Remove cluster-specific metadata
# Re-seal for target cluster
kubeseal --format=yaml --namespace=smartem-decisions < plain-secret.yaml > new-sealed-secret.yaml

# Clean up plain secret file
rm plain-secret.yaml
```

## Files and Structure

```
├── tools/generate-sealed-secrets.sh         # Main secret generation script
├── k8s/environments/
│   ├── development/
│   │   ├── secrets.yaml                     # Development sealed secrets
│   │   └── kustomization.yaml               # References secrets.yaml
│   ├── staging/
│   │   ├── secrets.yaml                     # Staging sealed secrets  
│   │   └── kustomization.yaml               # References secrets.yaml
│   └── production/
│       ├── secrets.yaml                     # Production sealed secrets
│       └── kustomization.yaml               # References secrets.yaml
└── k8s/secret.example.yaml                  # Example plain secret structure
```

## Further Reading

- [Bitnami Sealed Secrets Documentation](https://sealed-secrets.netlify.app/)
- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Diamond Light Source Kubernetes Standards](https://confluence.diamond.ac.uk/display/DASCM/Kubernetes)
- [Security Best Practices for Kubernetes](https://kubernetes.io/docs/concepts/security/)
