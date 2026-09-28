# External Ollama as a Kubernetes Service

**Status:** Deferred (low priority) — decided 2026-09-28
**Capability gate:** None — works on the current cluster. This is the only option in the
[Kubernetes-native inference](../ROADMAP.md#kubernetes-native-inference-capability-gated) group
that can be done today.

## Problem

Moirai's Ollama backends run outside the cluster on host `192.168.1.12`:

| Port | API | Notes |
|------|-----|-------|
| `11434` | Ollama 0.31.1 | General-purpose models (chat, default annotation fallback) |
| `8000` | Ollama-compatible, reports `0.5.1` | Presumably hailo-ollama on the Hailo NPU (not verified) |

The Helm chart points at them with raw URLs (`ollama.endpoint`, `llm.annotation.endpoint`), which
are injected as `OLLAMA_BASE_URL` / `ANNOTATION_OLLAMA_BASE_URL` into the api, worker, scheduler
and MCP server deployments. Moving Ollama to another host means editing values and redeploying
every component.

## Proposal

Represent each external Ollama as a **selectorless Service** with a manually managed
**EndpointSlice**. Pods then reach it by cluster DNS (`http://ollama:11434`) and the IP lives in
exactly one place.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ollama
spec:
  ports:
    - name: http
      port: 11434
      targetPort: 11434
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: ollama-1
  labels:
    kubernetes.io/service-name: ollama   # binds the slice to the Service
addressType: IPv4
ports:
  - name: http
    port: 11434
endpoints:
  - addresses: ["192.168.1.12"]
```

A second pair (`ollama-hailo`, port `8000`) covers the annotation backend. Helm values then become:

```yaml
ollama:
  endpoint: "http://ollama:11434"
llm:
  annotation:
    endpoint: "http://ollama-hailo:8000"
```

### Helm integration sketch

Optional `externalOllama` block; templates render one Service + EndpointSlice per entry:

```yaml
externalOllama:
  - name: ollama
    port: 11434
    addresses: ["192.168.1.12"]
  - name: ollama-hailo
    port: 8000
    addresses: ["192.168.1.12"]
```

## Benefits

- No IPs in application config; relocating Ollama is a single EndpointSlice edit.
- Several addresses in one slice give simple kube-proxy load balancing across Ollama hosts.
- NetworkPolicies and service naming behave like any other in-cluster service.

## Limitations

- **No health checking.** Kubernetes does not probe external endpoints; a dead host stays in the
  slice until removed.
- `ExternalName` Services are not an alternative — they require a DNS name, not an IP.
- This only gives the Ollama host a Service name. Kubernetes still cannot schedule workloads onto
  the NPU; see [DRA for the Hailo NPU](k8s-dra-hailo-npu.md).

## Acceptance criteria

- `helm template` renders the Service/EndpointSlice pairs only when `externalOllama` is set.
- From a Moirai pod: `curl http://ollama:11434/api/version` and
  `curl http://ollama-hailo:8000/api/version` succeed.
- Chat and article annotation work unchanged after switching values to service names.

## Related

- [Gateway API Inference Extension](k8s-gateway-inference-extension.md)
- [In-cluster Ollama](k8s-in-cluster-ollama.md)
- [LLM Configuration](llm-configuration.md)
