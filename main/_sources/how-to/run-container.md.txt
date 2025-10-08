# Run in a container

Pre-built containers with smartem-decisions and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/DiamondLightSource/smartem-decisions).

## Starting the container

To pull the container from github container registry and run:

```bash
# Check version
$ docker run ghcr.io/DiamondLightSource/smartem-decisions:latest --version
```

To get a released version, use a numbered release instead of `latest`.

## Running services

The container can run in different modes controlled by the `ROLE` environment variable:

### HTTP API Service

```bash
# Run API with default ERROR logging
$ docker run -p 8000:8000 -e ROLE=api ghcr.io/DiamondLightSource/smartem-decisions:latest

# Run API with INFO logging (equivalent to -v flag)
$ docker run -p 8000:8000 -e ROLE=api -e SMARTEM_LOG_LEVEL=INFO ghcr.io/DiamondLightSource/smartem-decisions:latest

# Run API with DEBUG logging (equivalent to -vv flag)
$ docker run -p 8000:8000 -e ROLE=api -e SMARTEM_LOG_LEVEL=DEBUG ghcr.io/DiamondLightSource/smartem-decisions:latest

# Custom port
$ docker run -p 9000:9000 -e ROLE=api -e HTTP_API_PORT=9000 ghcr.io/DiamondLightSource/smartem-decisions:latest
```

### Message Queue Worker

```bash
# Run worker with default ERROR logging
$ docker run -e ROLE=worker ghcr.io/DiamondLightSource/smartem-decisions:latest

# Run worker with INFO logging
$ docker run -e ROLE=worker -e SMARTEM_LOG_LEVEL=INFO ghcr.io/DiamondLightSource/smartem-decisions:latest

# Run worker with DEBUG logging
$ docker run -e ROLE=worker -e SMARTEM_LOG_LEVEL=DEBUG ghcr.io/DiamondLightSource/smartem-decisions:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ROLE` | `api` | Service role: `api` or `worker` |
| `HTTP_API_PORT` | `8000` | Port for HTTP API service |
| `SMARTEM_LOG_LEVEL` | `ERROR` | Log level: `ERROR`, `INFO`, or `DEBUG` |

## Complete Development Stack

For a complete development environment with database and message queue, see the [Kubernetes deployment guide](../../k8s/README.md) which provides a docker-compose-like experience.

## Advanced Configuration

### Custom User/Group for Production Deployments

The pre-built containers run as root by default, which is suitable for development and CI/CD. For production deployments at Diamond Light Source that require access to the `/dls` filesystem, you'll need to build custom images with specific UID/GID.

See [Container User Configuration](container-user-configuration.md) for:
- Building containers with custom user/group settings
- Mounting the `/dls` filesystem for image serving
- Security considerations and best practices
- Troubleshooting permission issues
