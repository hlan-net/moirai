# Moirai Helm Chart

Helm chart for deploying Moirai (GenAI Press Review platform).

## Quick Start

### Prerequisites
- Kubernetes cluster (1.24+)
- Helm 3.x
- CouchDB, Redis credentials

### Installation

```bash
helm install moirai . -n moirai --create-namespace \
  --set couchdb.adminPassword=yourpassword \
  --set moirai.adminPassword=yourpassword \
  --set moirai.jwtSecretKey=your-secret-key \
  --set redis.password=yourredispass
```

### Update to Specific Release

Pin to a release version:

```bash
helm upgrade moirai . \
  -n moirai \
  --set api.image.tag=0.6.1 \
  --set ui.image.tag=0.6.1
```

## Configuration

See `values.yaml` for all available options:

- **Image tags:** `api.image.tag`, `ui.image.tag` (default: `main`)
- **Replicas:** `api.replicaCount`, `ui.replicaCount`
- **Environment:** `environment` (development/production)
- **Resources:** CPU/memory requests and limits per service
- **Probes:** Readiness and liveness probe settings

## Storage

CouchDB uses persistent volumes for data. Configure:
- `couchdb.persistentVolume.enabled` (default: true)
- `couchdb.persistentVolume.size` (default: 10Gi)
- `couchdb.persistentVolume.storageClass` (must match your cluster)

## Multi-Namespace Deployments

To run multiple instances (e.g., dev and release), deploy to separate namespaces with different configurations:

```bash
# Release instance
helm install moirai-release . \
  -f values-release.yaml \
  -n moirai-release \
  --create-namespace

# Dev instance (internal use only)
# Uses: values-dev.yaml (not in public repo)
# Deploy with custom image tags and environment settings as needed
```

Each instance has its own Redis for isolation. CouchDB data is scoped per userspace, so instances can share the same database safely.
