# Gateway API Inference Extension (InferencePool)

**Status:** Deferred (low priority) — decided 2026-09-28
**Capability gate:** the Inference Extension `InferencePool` CRD, a gateway implementation that
supports it, and an endpoint picker (EPP) deployment installed in the cluster, **and** model servers
running as pods in-cluster.

## What it is

The Gateway API Inference Extension (Kubernetes SIG Network) adds inference-aware routing on top
of Gateway API:

- **`InferencePool`** — a group of model-server pods, selected by labels, that an `HTTPRoute` can
  target instead of a plain Service.
- An **endpoint picker** (EPP) chooses the backend pod per request using model-server signals such as
  queue depth, KV-cache usage and loaded LoRA adapters, instead of round-robin.

## Why it is deferred

- `InferencePool` selects **pods**. Moirai's Ollamas run outside the cluster on `192.168.1.12`,
  so there is nothing for the pool to select. For external hosts a
  [selectorless Service](k8s-external-ollama-service.md) is the right tool.
- The benefit appears only with **several** model-server replicas where smart routing matters.
  Moirai currently has one general Ollama and one NPU-backed annotation endpoint.
- Cluster state on 2026-09-28 (k3s v1.36.4): Gateway API base CRDs are present (installed via
  Consul), but no Inference Extension CRDs.

## When to revisit

- Ollama (or another model server such as vLLM) runs as multiple pods in-cluster — see
  [In-cluster Ollama](k8s-in-cluster-ollama.md), and
- the cluster's gateway implementation supports the Inference Extension.

## Sketch

```yaml
apiVersion: inference.networking.k8s.io/v1
kind: InferencePool
metadata:
  name: moirai-llm
spec:
  selector:
    matchLabels:
      app: ollama
  targetPorts:
    - number: 11434
  endpointPickerRef:
    name: moirai-llm-epp   # placeholder: the EPP Service, deployed separately
    port:
      number: 9002         # required when kind is Service (the default)
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: moirai-llm
spec:
  parentRefs:
    - name: inference-gateway
  rules:
    - backendRefs:
        - group: inference.networking.k8s.io
          kind: InferencePool
          name: moirai-llm
```

Field names follow the upstream v1 API. Check them against the installed CRD version before use.

Per-workload objectives (`InferenceObjective`, e.g. criticality) are no longer part of this
project upstream; they live in llm-d-router. Moirai does not need them, so they are not part of the
gate.

## Related

- [External Ollama as a Service](k8s-external-ollama-service.md)
- [In-cluster Ollama](k8s-in-cluster-ollama.md)
