# SmartEM Decision Core Module

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

# run HTTP API with verbosity controls:
python -m smartem_backend.run_api                  # ERROR level (default)
python -m smartem_backend.run_api -v               # INFO level
python -m smartem_backend.run_api -vv              # DEBUG level

# run HTTP API in development (FastAPI CLI):
fastapi dev src/smartem_backend/http_api.py # Note: FastAPI CLI gets installed by pip as one of dev dependencies
# run HTTP API in production (traditional):
source .env && uvicorn src.smartem_backend.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT
# run HTTP API with environment variable:
SMARTEM_LOG_LEVEL=ERROR uvicorn src.smartem_backend.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT
# smoke test the API:
./tests/check_smartem_core_http_api.py http://localhost:8000 -v

python -m smartem_backend --version
```
