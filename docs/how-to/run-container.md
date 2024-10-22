# Run in a container

Pre-built containers with cryoem-decision-engine-poc and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/vredchenko/cryoem-decision-engine-poc).

## Starting the container

To pull the container from github container registry and run:

```
$ docker run ghcr.io/vredchenko/cryoem-decision-engine-poc:latest --version
```

To get a released version, use a numbered release instead of `latest`.
