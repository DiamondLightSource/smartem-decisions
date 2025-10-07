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
RUN pip install --no-cache-dir ".[backend,images]" && \
    rm -rf .git

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime
# Build args for if you need the image to run as non-root
ARG groupid=0
ARG userid=0
ARG groupname=root
# Add apt-get system dependencies for runtime here if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*
RUN if [ "${groupid}" != "0" ]; then \
        groupadd -r -g "${groupid}" "${groupname}" && \
        useradd -r -M "${groupname}" -u "${userid}" -g "${groupname}"; \
    fi
COPY --from=build --chown="${userid}:${groupname}" /venv/ /venv/
COPY --from=build --chown="${userid}:${groupname}" /app/ /app/
ENV PATH=/venv/bin:$PATH

COPY --chown="${userid}:${groupname}" entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
