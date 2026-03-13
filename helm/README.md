# Moirai Helm Chart

Helm chart for deploying Moirai (GenAI Press Review platform).

## Quick Start

### Prerequisites
- Kubernetes cluster (1.24+)
- Helm 3.x
- CouchDB, Redis credentials

### Single Instance (Default)

```bash
helm install moirai . -n moirai --create-namespace \
  --set couchdb.adminPassword=yourpassword \
  --set moirai.adminPassword=yourpassword \
  --set moirai.jwtSecretKey=your-secret-key \
  --set redis.password=yourredispass
```

## Multi-Environment Deployments (Dev + Release)

Use environment-specific values files to run both dev and release instances on the same cluster.

### Architecture
- **Shared:** CouchDB instance (both environments read/write same data)
- **Separate:** Redis, API, Worker, MCP Server, UI (one per environment)

### Deploy Development Instance

```bash
helm install moirai-dev . \
  -f values-dev.yaml \
  -n moirai-dev \
  --create-namespace \
  --set couchdb.adminPassword=yourpassword \
  --set moirai.adminPassword=yourpassword \
  --set moirai.jwtSecretKey=your-secret-key \
  --set redis.password=yourredispass-dev
```

This deployment will:
- Use `:main` images (from docker-dev.yml pushes to main branch)
- Run with 1 API replica (dev sizing)
- Display `environment: development` in config

### Deploy Release Instance

```bash
helm install moirai-release . \
  -f values-release.yaml \
  -n moirai-release \
  --create-namespace \
  --set couchdb.adminPassword=yourpassword \
  --set moirai.adminPassword=yourpassword \
  --set moirai.jwtSecretKey=your-secret-key \
  --set redis.password=yourredispass-release
```

This deployment will:
- Use `:latest` images (or pin to specific version like `:0.6.1`)
- Run with 2 API replicas (HA)
- Display `environment: production` in config

### Update Release to New Version

After pushing a new release tag `v0.6.2`, update the release deployment:

```bash
# Edit values-release.yaml
# Change: api.image.tag: "0.6.2"
#         ui.image.tag: "0.6.2"

helm upgrade moirai-release . \
  -f values-release.yaml \
  -n moirai-release
```

Or directly via command line:

```bash
helm upgrade moirai-release . \
  -f values-release.yaml \
  -n moirai-release \
  --set api.image.tag=0.6.2 \
  --set ui.image.tag=0.6.2
```

## Configuration

### Shared CouchDB
Both dev and release instances connect to the same CouchDB (same `COUCHDB_URI`). Data is stored per-userspace, so users are isolated.

### Separate Redis Instances
Each environment has its own Redis for rate-limiter sync and agent orchestrator locking:
- Dev: `moirai-dev-redis`
- Release: `moirai-release-redis`

Use different Redis passwords for each environment in production.

## Monitoring

Check deployments:

```bash
kubectl get pods -n moirai-dev
kubectl get pods -n moirai-release

# Check logs
kubectl logs -n moirai-dev deployment/moirai-dev-api
kubectl logs -n moirai-release deployment/moirai-release-api

# Port forward to test
kubectl port-forward -n moirai-dev svc/moirai-dev-nginx 8080:80
# Visit: http://localhost:8080
```

## Cleanup

Remove a deployment:

```bash
helm uninstall moirai-dev -n moirai-dev
helm uninstall moirai-release -n moirai-release
```

Delete the namespace (warning: deletes all resources):

```bash
kubectl delete namespace moirai-dev
kubectl delete namespace moirai-release
```
