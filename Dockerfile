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

# ============================================================================
# User/Group Configuration for Container Security
# ============================================================================
# These build arguments allow the container to run as a non-root user with
# specific UID/GID, which is required for certain deployment environments.
#
# Default behavior (groupid=0, userid=0, groupname=root):
#   - Container runs as root user
#   - Suitable for CI/CD pipelines and local development
#   - No custom user creation is performed
#
# DLS deployment (custom groupid/userid):
#   - Container runs as non-root user with specified UID/GID
#   - Required for mounting the /dls filesystem in Kubernetes pods
#   - The /dls filesystem contains microscopy images that cannot be
#     accessed by root due to permissions constraints
#   - Enables image serving endpoints to access stored microscopy data
#
# Build arguments:
#   groupid:   Group ID for the container user (default: 0 = root)
#   userid:    User ID for the container user (default: 0 = root)
#   groupname: Name for the group and user (default: root)
#
# Example builds:
#   Default (root):     docker build -t smartem-decisions .
#   DLS deployment:     docker build --build-arg groupid=1000 \
#                                    --build-arg userid=1000 \
#                                    --build-arg groupname=smartem \
#                                    -t smartem-decisions .
# ============================================================================
ARG groupid=0
ARG userid=0
ARG groupname=root

# Add apt-get system dependencies for runtime here if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Conditionally create a non-root user and group.
# This is skipped when groupid=0 (default), allowing the container to run as root.
# When groupid != 0, a custom user is created for environments requiring
# specific permissions (e.g., DLS filesystem access).
RUN if [ "${groupid}" != "0" ]; then \
        groupadd -r -g "${groupid}" "${groupname}" && \
        useradd -r -M "${groupname}" -u "${userid}" -g "${groupname}"; \
    fi

# Copy application files and virtual environment with proper ownership.
# The ownership is set based on the userid/groupname build args, ensuring
# that files are accessible by the user the container will run as.
COPY --from=build --chown="${userid}:${groupname}" /venv/ /venv/
COPY --from=build --chown="${userid}:${groupname}" /app/ /app/
ENV PATH=/venv/bin:$PATH

# Copy entrypoint script with proper ownership and make it executable.
# The entrypoint handles different service roles (api, worker) and
# environment-specific configuration (Kubernetes vs local).
COPY --chown="${userid}:${groupname}" entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
