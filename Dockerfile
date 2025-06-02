# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer AS build
WORKDIR /app
# Copy the entire repository content to /app (not /context)
COPY . .
# Install the package using pyproject.toml and setup.py
# This will also handle copying _version.py files and .env.example → .env
RUN pip install --no-cache-dir -e ".[core]" uvicorn

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime
# Add apt-get system dependencies for runtime here if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /venv/ /venv/
COPY --from=build /app/ /app/
ENV PATH=/venv/bin:$PATH

# Use a shell form of ENTRYPOINT to allow for environment variable expansion
ENTRYPOINT ["/bin/bash", "-c"]
# Run database initialization and then start the API server
CMD ["cd /app && source .env && python -m smartem_decisions.model.database && uvicorn smartem_decisions.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT"]
