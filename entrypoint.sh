#!/bin/bash
set -e

cd /app
source .env

case "${ROLE:-api}" in
    api)
        echo "Starting HTTP API..."
        # TODO we don't want to do it indiscriminately on every container launch:
        python -m smartem_decisions.model.database
        exec uvicorn smartem_decisions.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT
        ;;
    worker)
        echo "Starting RabbitMQ consumer..."
        exec python -m smartem_decisions.mq_consumer
        ;;
    *)
        echo "Unknown role: $ROLE"
        exit 1
        ;;
esac
