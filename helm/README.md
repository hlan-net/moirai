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

### AISA (in-cluster inference proxy)

Optional and additive: direct OpenAI/Gemini/Ollama settings keep working. Declare Moirai
as an AISA consumer (target secret `moirai-aisa-key` in this namespace), then:

```yaml
aisa:
  enabled: true
  secretName: moirai-aisa-key
llm:
  provider: aisa          # optional process-wide default (DEFAULT_LLM_PROVIDER)
  model: "qwen3:8b"       # MODEL_NAME; must exist behind the proxy
```

The Secret is mounted at `aisa.keyMountPath` (default `/var/run/secrets/aisa`) and the
key is read from the file via `AISA_API_KEY_FILE` (`aisa.keyFile: true`, the default).
kubelet refreshes the file in place, so AISA key rotations need no restart and no
Reloader. `OPENAI_BASE_URL` / `OPENAI_MODEL` are mapped to the env vars `AISA_BASE_URL` /
`AISA_MODEL`; everything is `optional: true`, so restart the deployments once after
AISA first creates the Secret (env is read at container start).

- `aisa.reloader: true` adds a `secret.reloader.stakater.com/reload` annotation. It
  **requires [Stakater Reloader](https://github.com/stakater/Reloader) in the cluster**;
  the chart neither installs nor checks for it, and without it the annotation does
  nothing. With `keyFile` it is only needed for base URL / model changes.
- `aisa.keyFile: false` falls back to the `AISA_API_KEY` env var, which keeps the old key
  until the pods restart: use it only together with Reloader.
See `docs/llm-configuration.md` for details.

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
