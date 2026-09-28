# In-cluster Ollama (KServe / KubeAI / ollama-operator)

**Status:** Deferred (low priority) — decided 2026-09-28
**Capability gate:** Cluster nodes with enough CPU/RAM (or GPU/NPU access) to run models, plus one
of the operators below installed.

## Problem it would solve

Today the Ollamas are pets on `192.168.1.12`: Kubernetes cannot restart, scale or health-check
them. Running the model server inside the cluster would make it a managed workload.

## Options

| Resource | Project | Fit for Moirai |
|----------|---------|----------------|
| `InferenceService` | KServe | Full model-serving platform (autoscaling, canaries). Heavyweight for a homelab; Ollama would run as a custom runtime. |
| `Model` | KubeAI | Supports Ollama as an engine, scale-to-zero, OpenAI-compatible endpoint. Lightest managed option. |
| `Model` | ollama-operator | Thin operator that runs Ollama and pulls models declaratively. Simplest, fewest features. |
| Plain Deployment | Moirai Helm chart | Ollama as a Deployment + PVC for models. No new CRDs. |

## Why it is deferred

- None of these CRDs are installed (checked 2026-09-28, k3s v1.36.4).
- The Hailo-accelerated annotation path depends on NPU hardware attached to `192.168.1.12`.
  In-cluster Ollama would need that node in the cluster and device access —
  see [DRA for the Hailo NPU](k8s-dra-hailo-npu.md).
- The external setup works. The operational gain does not yet justify the new moving parts.

## Constraints if pursued

- **Models on persisted volumes, never baked into images.** Mount a PVC for `OLLAMA_MODELS`, the
  same rule as for embedding models.
- Moirai keeps talking plain Ollama/OpenAI-compatible HTTP. Only `ollama.endpoint` changes.
- Once there are several replicas, consider the
  [Gateway API Inference Extension](k8s-gateway-inference-extension.md) for routing.

## When to revisit

- A cluster node gains a GPU/NPU usable by pods, or
- the user wants Kubernetes-managed restarts and scaling for the LLM backend.

## Related

- [External Ollama as a Service](k8s-external-ollama-service.md)
- [LLM Configuration](llm-configuration.md)
