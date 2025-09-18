# Run SmartEM Backend

The core backend service providing HTTP API, database operations, and message queue processing for intelligent cryo-EM data collection.

## Backend Operations

```bash
# create env and launch service stack locally:
./tools/dev-k8s.sh up

# launch RabbitMQ worker (consumer)
python -m smartem_backend.consumer              # ERROR level (default)
python -m smartem_backend.consumer -v           # INFO level  
python -m smartem_backend.consumer -vv          # DEBUG level

# simulating an system event: 
python -m smartem_backend.simulate_msg --help # to see a list of options
./tools/simulate-messages.sh # run a simulation, triggering system events in sequence

# run HTTP API (recommended - uses proper module entry point):
python -m smartem_backend.api_server

# run HTTP API in development with FastAPI CLI:
fastapi dev src/smartem_backend/api_server.py # Note: FastAPI CLI gets installed by pip as one of dev dependencies

# run HTTP API with uvicorn directly:
source .env && uvicorn smartem_backend.api_server:app --host 0.0.0.0 --port $HTTP_API_PORT

# run HTTP API with environment variable:
SMARTEM_LOG_LEVEL=ERROR uvicorn smartem_backend.api_server:app --host 0.0.0.0 --port $HTTP_API_PORT
# customize HTTP API host/port with environment variables:
HTTP_API_PORT=9000 python -m smartem_backend.api_server
HTTP_API_HOST=0.0.0.0 HTTP_API_PORT=8080 python -m smartem_backend.api_server

# smoke test the API:
./tests/check_smartem_core_http_api.py http://localhost:8000 -v

python -m smartem_backend --version
```
