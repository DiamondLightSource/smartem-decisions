ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG SMARTEM_VERSION

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
#   PyPI install:       docker build --build-arg SMARTEM_VERSION=1.0.0 -t smartem-decisions .
#   DLS deployment:     docker build --build-arg SMARTEM_VERSION=1.0.0 \
#                                    --build-arg groupid=1000 \
#                                    --build-arg userid=1000 \
#                                    --build-arg groupname=smartem \
#                                    -t smartem-decisions .
# ============================================================================
ARG groupid=0
ARG userid=0
ARG groupname=root

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "${groupid}" != "0" ]; then \
        groupadd -r -g "${groupid}" "${groupname}" && \
        useradd -r -M "${groupname}" -u "${userid}" -g "${groupname}"; \
    fi

RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

RUN pip install --no-cache-dir "smartem-decisions[backend,images]==${SMARTEM_VERSION}"

WORKDIR /app
COPY alembic.ini .
COPY --chown="${userid}:${groupname}" entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
