# Deploying to k8s

## Setup GitHub personal access token

Create a GitHub token with `read:packages` permission:

- Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate new token with `read:packages` scope

```bash
echo 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 | docker login ghcr.io -u vredchenko --password-stdin
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=vredchenko \
  --docker-password=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 \
  --docker-email=val.redchenko@diamond.ac.uk \
  --namespace=smartem-decisions

kubectl delete namespace smartem-decisions && \
kubectl create namespace smartem-decisions

kubectl delete deployments --all -n smartem-decisions
kubectl apply -f k8s/local-test.yaml

kubectl get services -n smartem-decisions

kubectl exec -it -n smartem-decisions deployment/smartem-http-api -- /bin/bash
kubectl exec -it -n smartem-decisions deployment/smartem-worker -- /bin/bash

# check env:
env | grep -E '(RABBIT|POSTGRES)'
```
