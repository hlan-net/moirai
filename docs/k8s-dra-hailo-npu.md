# Dynamic Resource Allocation (DRA) for the Hailo NPU

**Status:** Deferred (low priority) — decided 2026-09-28
**Capability gate:** `192.168.1.12` joined to the cluster as a node, **and** a DRA driver (or at
minimum a device plugin) for Hailo devices available.

## What it is

DRA is the Kubernetes mechanism for modelling hardware devices as first-class resources:

- **`DeviceClass`** — a kind of device (e.g. "Hailo-8L NPU"), published by a DRA driver.
- **`ResourceClaim` / `ResourceClaimTemplate`** — a pod's request for a device. The scheduler
  places the pod on a node that has a matching free device.

DRA is GA in the Kubernetes line the cluster runs (k3s v1.36.4). It replaces the older
device-plugin model (`resources.limits: vendor.com/device: 1`) with richer selection and sharing.

## Why it matters for Moirai

Article annotation can run on hailo-ollama (`llm.annotation.*` in Helm) on the Hailo NPU. Today
that is an external process on `192.168.1.12`. With DRA, the annotation model server could be a pod
that **requests the NPU**, so Kubernetes schedules, restarts and monitors it.

## Why it is deferred

- `192.168.1.12` is not a cluster node.
- No Hailo DRA driver is known to exist. A device plugin may be needed instead, or written.
- The external setup works. See [External Ollama as a Service](k8s-external-ollama-service.md)
  for the low-cost improvement available now.

## Sketch (once a driver exists)

```yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaimTemplate
metadata:
  name: hailo-npu
spec:
  spec:
    devices:
      requests:
        - name: npu
          exactly:
            deviceClassName: hailo.ai   # published by the driver
---
# in the hailo-ollama pod spec
spec:
  resourceClaims:
    - name: npu
      resourceClaimTemplateName: hailo-npu
  containers:
    - name: hailo-ollama
      resources:
        claims:
          - name: npu
```

The device class name is a placeholder. Use whatever the eventual driver publishes, and check API
versions against the installed cluster.

## When to revisit

- Hailo (or the community) ships a DRA driver or device plugin, and
- `192.168.1.12` (or another NPU host) is joined to the cluster.

## Related

- [In-cluster Ollama](k8s-in-cluster-ollama.md)
- [External Ollama as a Service](k8s-external-ollama-service.md)
