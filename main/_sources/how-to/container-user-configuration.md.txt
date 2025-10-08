# Container User Configuration

This guide explains how to configure the SmartEM Decisions container to run as a non-root user with specific UID/GID, which is essential for certain deployment scenarios at Diamond Light Source (DLS).

## Overview

The SmartEM Decisions Dockerfile supports two distinct operational modes:

1. **Default Mode (Root User)**: For CI/CD pipelines and local development
2. **Custom User Mode**: For production deployments requiring filesystem access with specific permissions

## Why Non-Root Users?

At Diamond Light Source, the HTTP API service needs to access microscopy images stored on the `/dls` filesystem. This filesystem:

- Contains electron microscopy data from EPU sessions
- Cannot be mounted in containers with root privileges due to security policies
- Requires the container to run with a specific UID/GID that has read permissions
- Is accessed by image serving endpoints in the HTTP API

Without proper user configuration, the container cannot access `/dls` and image serving endpoints will fail.

## Build Arguments

The Dockerfile accepts three build arguments that control user/group creation:

| Argument | Default | Description |
|----------|---------|-------------|
| `groupid` | `0` | Group ID for the container user. When set to `0`, no custom user is created (runs as root). |
| `userid` | `0` | User ID for the container user. Should match the required UID for filesystem access. |
| `groupname` | `root` | Name for both the group and user. Used for identification in container processes. |

## Default Behavior: Root User

When build arguments are not specified (or explicitly set to defaults), the container runs as root:

```bash
# Build with defaults (runs as root)
docker build -t smartem-decisions .

# This is equivalent to:
docker build \
  --build-arg groupid=0 \
  --build-arg userid=0 \
  --build-arg groupname=root \
  -t smartem-decisions .
```

**Use cases for root mode:**
- CI/CD pipelines (GitHub Actions, GitLab CI)
- Local development environments
- Environments without specific filesystem permission requirements
- Testing and debugging

**Implications:**
- Container has full privileges
- No user creation step is executed
- All files owned by root (UID 0, GID 0)
- Cannot mount DLS filesystem in production

## Custom User Mode: DLS Deployment

For production deployment at DLS, build the container with specific UID/GID:

```bash
# Build with custom user (example values)
docker build \
  --build-arg groupid=1000 \
  --build-arg userid=1000 \
  --build-arg groupname=smartem \
  -t smartem-decisions:dls .
```

**What happens during build:**
1. A group is created with the specified `groupid` and `groupname`
2. A user is created with the specified `userid`, belonging to the group
3. All application files (`/venv`, `/app`, `/entrypoint.sh`) are set to be owned by this user
4. The container will execute processes as this user (not root)

**Use cases for custom user mode:**
- DLS production/staging deployments
- Any environment requiring specific filesystem permissions
- Security-hardened deployments following least-privilege principles

**Implications:**
- Container runs with limited privileges
- Can access `/dls` filesystem when mounted with matching permissions
- Image serving endpoints function correctly
- More secure than running as root

## Volume Mounting Considerations

### The /dls Directory

The `/dls` directory is **not** created in the Docker image. It should be mounted at runtime:

```bash
# Mount /dls directory (example)
docker run -v /path/to/dls:/dls smartem-decisions:dls
```

In Kubernetes, this is typically done via a PersistentVolume or hostPath mount:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smartem-http-api
spec:
  template:
    spec:
      containers:
      - name: smartem-http-api
        image: ghcr.io/diamondlightsource/smartem-decisions:dls
        volumeMounts:
        - name: dls-data
          mountPath: /dls
          readOnly: true
      volumes:
      - name: dls-data
        hostPath:
          path: /dls
          type: Directory
```

### When /dls is Not Mounted

If the `/dls` directory is not mounted or does not exist:

- The container will start normally
- Most API endpoints will function correctly
- Image serving endpoints will return 404 errors when image paths reference `/dls`
- Error messages will indicate that the file cannot be found

This is by design - the container is operational without `/dls`, but image serving functionality is unavailable.

### Optional Mount Strategy

The `/dls` mount should be considered **optional for development** but **required for production**:

- **Development/Testing**: Run without `/dls` mount for testing non-image features
- **Staging**: Mount a subset of `/dls` or test data directory
- **Production**: Mount full `/dls` filesystem with proper permissions

## Image Serving Endpoints

The HTTP API provides endpoints for serving microscopy images:

- `GET /grids/{grid_uuid}/atlas_image` - Serve grid atlas images
- `GET /gridsquares/{gridsquare_uuid}/gridsquare_image` - Serve grid square images

These endpoints:
1. Query the database for image file paths
2. Read image files from the filesystem (typically `/dls`)
3. Process and return images in PNG format

**Requirements:**
- Container must run as user with read access to image files
- Image paths in database must be accessible by the container user
- Filesystem must be mounted at the correct path

**Error handling:**
- If image path is not in database: Returns 404 "Grid square image unknown"
- If file doesn't exist: Returns 404 or file system error
- If permissions denied: Returns 500 error with permission details

## Security Considerations

### Principle of Least Privilege

Running containers as non-root is a security best practice:

- **Risk Reduction**: Limited damage if container is compromised
- **Policy Compliance**: Many organizations require non-root containers
- **Audit Trail**: Clear user identity in logs and process lists

### Choosing UID/GID

When selecting UID/GID for custom user mode:

1. **Match Filesystem Permissions**: Use UID/GID that has read access to required files
2. **Avoid System IDs**: Don't use UIDs below 1000 (reserved for system users)
3. **Document Values**: Keep a record of which UID/GID is used in each environment
4. **Consistency**: Use the same UID/GID across all pods in the same environment

### File Ownership

All files in the container are owned by the specified user:

```bash
# Inside container running as custom user
ls -la /app
# Output: drwxr-xr-x 2 smartem smartem 4096 Oct 7 12:00 .

ls -la /venv
# Output: drwxr-xr-x 2 smartem smartem 4096 Oct 7 12:00 .
```

This ensures the application can read its own files while running as non-root.

## Building for Different Environments

### Local Development

```bash
# Simple build for local development
docker build -t smartem-decisions:dev .

# Run with local database
docker run -p 8000:8000 \
  -e ROLE=api \
  -e POSTGRES_HOST=host.docker.internal \
  smartem-decisions:dev
```

### CI/CD Pipeline

```bash
# GitHub Actions (runs as root by default)
docker build -t smartem-decisions:$GITHUB_SHA .
docker push ghcr.io/diamondlightsource/smartem-decisions:$GITHUB_SHA
```

### Staging Environment

```bash
# Build with staging UID/GID
docker build \
  --build-arg groupid=1001 \
  --build-arg userid=1001 \
  --build-arg groupname=smartem-staging \
  -t smartem-decisions:staging .

# Tag and push
docker tag smartem-decisions:staging \
  ghcr.io/diamondlightsource/smartem-decisions:staging
docker push ghcr.io/diamondlightsource/smartem-decisions:staging
```

### Production Environment

```bash
# Build with production UID/GID (example values)
docker build \
  --build-arg groupid=5000 \
  --build-arg userid=5000 \
  --build-arg groupname=smartem \
  -t smartem-decisions:production .

# Tag and push
docker tag smartem-decisions:production \
  ghcr.io/diamondlightsource/smartem-decisions:production
docker push ghcr.io/diamondlightsource/smartem-decisions:production
```

## Kubernetes Deployment Configuration

### Example: HTTP API with Custom User

If you've built the image with custom UID/GID, deploy it in Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smartem-http-api
  namespace: smartem-decisions-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: smartem-http-api
  template:
    metadata:
      labels:
        app: smartem-http-api
    spec:
      # Optional: Explicitly set security context to match build args
      securityContext:
        runAsUser: 5000
        runAsGroup: 5000
        fsGroup: 5000

      containers:
      - name: smartem-http-api
        image: ghcr.io/diamondlightsource/smartem-decisions:production

        # Mount /dls filesystem
        volumeMounts:
        - name: dls-data
          mountPath: /dls
          readOnly: true

        env:
        - name: ROLE
          value: "api"
        # ... other environment variables ...

      volumes:
      - name: dls-data
        hostPath:
          path: /dls
          type: Directory
```

### Security Context in Kubernetes

While the Dockerfile sets ownership, Kubernetes `securityContext` provides additional enforcement:

- `runAsUser`: Ensures container runs as specific UID
- `runAsGroup`: Sets primary group ID
- `fsGroup`: Sets group ownership for mounted volumes
- `runAsNonRoot`: Enforces non-root execution (Kubernetes validates)

Example with security context:

```yaml
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 5000
        runAsGroup: 5000
        fsGroup: 5000
      containers:
      - name: smartem-http-api
        image: ghcr.io/diamondlightsource/smartem-decisions:production
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
```

## Troubleshooting

### Image Serving Endpoints Return 404

**Symptoms:**
- API starts successfully
- Most endpoints work
- Image endpoints return 404

**Possible causes:**
1. `/dls` not mounted
2. Image paths in database incorrect
3. Permission denied (check with 403/500 errors)

**Solution:**
```bash
# Check if /dls is mounted
kubectl exec -it <pod-name> -- ls -la /dls

# Check container user
kubectl exec -it <pod-name> -- id

# Check file permissions
kubectl exec -it <pod-name> -- ls -la /dls/path/to/images
```

### Permission Denied Errors

**Symptoms:**
- Container starts but cannot read files
- Errors like "Permission denied" in logs

**Possible causes:**
1. UID/GID mismatch between container and filesystem
2. Files owned by different user

**Solution:**
```bash
# Verify container UID/GID
docker run --rm smartem-decisions:dls id
# Output: uid=5000(smartem) gid=5000(smartem) groups=5000(smartem)

# Verify filesystem permissions
ls -lan /path/to/dls/data
# Ensure UID 5000 has read access
```

### Container Fails to Start

**Symptoms:**
- Container exits immediately
- Error about user creation

**Possible causes:**
1. Invalid UID/GID values
2. Conflicting user/group names

**Solution:**
```bash
# Check build arguments
docker inspect smartem-decisions:dls | grep -A 5 "Args"

# Rebuild with correct arguments
docker build --build-arg groupid=5000 --build-arg userid=5000 \
  --build-arg groupname=smartem -t smartem-decisions:dls .
```

## Best Practices

1. **Document UID/GID Choices**: Keep a record of which UID/GID is used in each environment
2. **Use Consistent Values**: Don't change UID/GID between builds for the same environment
3. **Test Both Modes**: Ensure the application works in both root and non-root modes
4. **Validate Permissions**: Before deploying, verify the container user can access required files
5. **Plan Volume Mounts**: Design mount strategy before building custom images
6. **Monitor Logs**: Watch for permission-related errors during deployment
7. **Use Security Context**: Combine Dockerfile user config with Kubernetes securityContext
8. **Graceful Degradation**: Ensure the application handles missing `/dls` gracefully

## Related Documentation

- [Run in a Container](run-container.md) - Basic container usage
- [Kubernetes Deployment](deploy-kubernetes.md) - Full deployment guide
- [Containerization](containerization.md) - Building and pushing images
- [Managing Kubernetes Secrets](manage-kubernetes-secrets.md) - Secure credential management

## References

- [Docker USER instruction](https://docs.docker.com/engine/reference/builder/#user)
- [Kubernetes Security Context](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Best practices for running containers](https://docs.docker.com/develop/dev-best-practices/)
