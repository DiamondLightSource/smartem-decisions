#!/bin/bash
set -e

cd /app
# Only source .env if not in Kubernetes
if [ -z "$KUBERNETES_SERVICE_HOST" ]; then
    if [ -f .env ]; then
        echo "Sourcing .env file for local development"
        source .env
    fi
else
    echo "Running in Kubernetes - using environment variables from ConfigMap/Secrets"
fi

case "${ROLE:-api}" in
    api)
        echo "Starting HTTP API..."
        python -m alembic upgrade head
        exec uvicorn smartem_backend.api_server:app \
            --host 0.0.0.0 --port ${HTTP_API_PORT:-8000} \
            --timeout-graceful-shutdown 30
        ;;
    worker)
        echo "Starting RabbitMQ consumer..."
        exec python -m smartem_backend.consumer
        ;;
    *)
        echo "Unknown role: $ROLE"
        exit 1
        ;;
esac
