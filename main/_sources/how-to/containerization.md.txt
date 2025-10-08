# Containerization

This guide covers building and managing SmartEM Decisions container images.

## Docker/Podman Operations

### Basic Build (Default Configuration)

Build the container with default settings (runs as root):

```bash
# Docker
docker build -t smartem-decisions .

# Podman
podman build --format docker -t smartem-decisions .
```

### Build with Custom User (DLS Deployment)

For production deployment at Diamond Light Source, build with custom UID/GID to enable `/dls` filesystem access:

```bash
# Docker
docker build \
  --build-arg groupid=1000 \
  --build-arg userid=1000 \
  --build-arg groupname=smartem \
  -t smartem-decisions:dls .

# Podman
podman build --format docker \
  --build-arg groupid=1000 \
  --build-arg userid=1000 \
  --build-arg groupname=smartem \
  -t smartem-decisions:dls .
```

See [Container User Configuration](container-user-configuration.md) for detailed information about build arguments and deployment scenarios.

### Running Containers

```bash
# Docker - run API service
docker run -p 8000:8000 -e ROLE=api smartem-decisions

# Podman - run API service
podman run -p 8000:8000 -e ROLE=api localhost/smartem-decisions
```

### Cleanup

```bash
# Docker
docker image rm smartem-decisions -f

# Podman
podman image rm localhost/smartem-decisions -f
```

## Tagging and Pushing Images

### GitHub Container Registry (Current)

```bash
# Tag the image
docker tag smartem-decisions ghcr.io/diamondlightsource/smartem-decisions:latest

# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Push the image
docker push ghcr.io/diamondlightsource/smartem-decisions:latest
```

### Tagging Strategies

```bash
# Development/staging build
docker tag smartem-decisions ghcr.io/diamondlightsource/smartem-decisions:dev
docker tag smartem-decisions ghcr.io/diamondlightsource/smartem-decisions:staging

# Production build with version
docker tag smartem-decisions ghcr.io/diamondlightsource/smartem-decisions:1.0.0
docker tag smartem-decisions ghcr.io/diamondlightsource/smartem-decisions:latest

# Production build with custom user
docker tag smartem-decisions:dls ghcr.io/diamondlightsource/smartem-decisions:production
```

## Multi-Stage Build Architecture

The Dockerfile uses a multi-stage build process:

1. **developer** stage: Base Python image with system dependencies
2. **build** stage: Installs Python packages and application code
3. **runtime** stage: Slim image with only runtime dependencies and built application

This approach:
- Minimizes final image size
- Separates build tools from runtime environment
- Enables efficient layer caching

## Build Arguments Reference

| Argument | Default | Purpose |
|----------|---------|---------|
| `PYTHON_VERSION` | `3.12` | Python version for base images |
| `groupid` | `0` | Group ID for container user (0 = root) |
| `userid` | `0` | User ID for container user (0 = root) |
| `groupname` | `root` | Name for group and user |

## Related Documentation

- [Container User Configuration](container-user-configuration.md) - Detailed guide on UID/GID configuration
- [Run in a Container](run-container.md) - Using pre-built containers
- [Kubernetes Deployment](deploy-kubernetes.md) - Deploying to Kubernetes

## References

- [GitHub Container Registry](https://ghcr.io/diamondlightsource/smartem-decisions)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Podman Documentation](https://docs.podman.io/)
