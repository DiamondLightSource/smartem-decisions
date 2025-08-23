#!/bin/bash
set -e

cd /app
# Only source .env if not in Kubernetes
if [ -z "$KUBERNETES_SERVICE_HOST" ]; then
    echo "Sourcing .env file for local development"
    source .env
else
    echo "Running in Kubernetes - using environment variables from ConfigMap/Secrets"
fi

case "${ROLE:-api}" in
    api)
        echo "Starting HTTP API..."
        # TODO we don't want to do it indiscriminately on every container launch:
        python -m smartem_backend.model.database
        exec uvicorn smartem_backend.api_server:app --host 0.0.0.0 --port ${HTTP_API_PORT:-8000}
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
