# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} AS developer

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer AS build
COPY . /context
WORKDIR /context
COPY pyproject.toml .
RUN pip install --no-cache-dir . uvicorn

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime
# Add apt-get system dependecies for runtime here if needed
COPY --from=build /venv/ /venv/
COPY --from=build /context/ /app/
ENV PATH=/venv/bin:$PATH

# Copy .env.example as .env
COPY .env.example /.env

# change this entrypoint if it is not the same as the repo
#ENTRYPOINT ["smartem-decisions"]
#CMD ["--version"]

# Use a shell form of ENTRYPOINT to allow for environment variable expansion
ENTRYPOINT ["/bin/bash", "-c"]
# Combine the source command with uvicorn in the CMD instruction
CMD ["source /.env && cd /app && uvicorn src.smartem_decisions.http_api:app --host 0.0.0.0 --port $HTTP_API_PORT"]
