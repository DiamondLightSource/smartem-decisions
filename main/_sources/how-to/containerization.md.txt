# Containerization

## Podman Operations

```bash
# podman image/container operations:
podman build --format docker . -t smartem_backend # build image
podman run -p 8000:8000 localhost/smartem_backend # run container (TODO debug Postgres connection)
podman image rm localhost/smartem_backend -f # clean up before rebuild

# TODO but we should push to Github not Gitlab
# Once built, tagging and pushing is done like so:
# Refs:
#  - https://confluence.diamond.ac.uk/display/CLOUD/Container+Registry
#  - https://dev-portal.diamond.ac.uk/guide/kubernetes/tutorials/containers/
podman tag 55646974a136 gcr.io/diamond-pubreg/smartem_backend/smartem_backend:latest
podman push gcr.io/diamond-pubreg/smartem_backend/smartem_backend:latest
```
