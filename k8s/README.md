# Deploying to k8s

## Setup GitHub personal access token

Create a GitHub token with `read:packages` permission:

- Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate new token with `read:packages` scope

```bash
echo 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 | docker login ghcr.io -u vredchenko --password-stdin
```

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=vredchenko \
  --docker-password=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 \
  --docker-email=val.redchenko@diamond.ac.uk \
  --namespace=smartem-decisions
```
