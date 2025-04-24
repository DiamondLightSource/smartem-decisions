# SmartEM Decision Core Module

```bash
# create env and launch service stack locally:
docker compose up -d

# launch RabbitMQ worker (consumer)
python -m smartem_decisions.consumer

# simulating an system event: 
python -m smartem_decisions.simulate_msg --help # to see a list of options
./tools/simulate-messages.sh # run a simulation, triggering system events in sequence

# run HTTP API in development:
fastapi dev src/smartem_decisions/http_api.py # Note: FastAPI CLI gets installed by pip as one of dev dependencies
# run HTTP API in  production:
source .env && uvicorn src.smartem_decisions.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT
# smoke test the API:
./tests/check_smartem_core_http_api.py http://localhost:8000 -v

python -m smartem_decisions --version
```

> Note: when debugging Graylog traffic: `nc -klu 12209`
