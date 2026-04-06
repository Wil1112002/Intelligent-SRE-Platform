# Runbook: Memory Leak

## Alert

- **MemoryLeak**: memory_usage_bytes growing > 20% over 10 minutes (severity: warning)

## Symptoms

- Steadily increasing memory consumption in the worker-service
- Memory gauge on the Service Overview dashboard trending upward
- Eventually leads to OOMKilled pods and CrashLoopBackOff

## Metrics to Check

```promql
# Current memory usage (application-reported)
memory_usage_bytes

# Memory growth rate
deriv(memory_usage_bytes[30m])

# Container memory from cAdvisor
container_memory_usage_bytes{container="worker-service"}

# Memory limit
kube_pod_container_resource_limits{resource="memory"}

# Memory usage as percentage of limit
container_memory_usage_bytes{container="worker-service"}
/
kube_pod_container_resource_limits{resource="memory", container="worker-service"} * 100
```

## Diagnosis Steps

1. **Check the memory trend** on the Service Overview dashboard. Is it a linear increase or stepped growth?

2. **Correlate with traffic**:
   ```promql
   # Is memory growth proportional to request volume?
   rate(job_count_total[5m])
   ```

3. **Check all replicas** — is the leak happening on all pods or just one?
   ```bash
   kubectl top pods -n default -l app=worker-service
   ```

4. **Check container-level memory**:
   ```bash
   kubectl exec <pod-name> -n default -- cat /proc/meminfo
   ```

5. **Review recent code changes** — was new functionality added that accumulates data?

6. **Check for known patterns**:
   - Unbounded caches or lists
   - Event listeners not being cleaned up
   - Database connection pools growing

## Remediation

### Immediate

- **Scale up** to distribute load and buy time:
  ```bash
  kubectl scale deployment/worker-service --replicas=4 -n default
  ```

- **Rolling restart** to reset memory on all pods:
  ```bash
  kubectl rollout restart deployment/worker-service -n default
  ```

- If memory is critical and pods are about to OOM, restart immediately.

### Short-term

- Set or reduce memory limits to trigger faster OOM restarts (prevents node-level impact):
  ```yaml
  resources:
    limits:
      memory: 256Mi
  ```

- Add a sidecar or CronJob that restarts the deployment on a schedule as a temporary bandaid.

### Long-term

- **Profile memory usage** using Python tools:
  ```python
  # Add to the service temporarily
  import tracemalloc
  tracemalloc.start()
  # ... later snapshot and compare
  ```

- **Identify the leak source** — in the worker-service, the `_leak_store` list grows unbounded on every request. In production, this pattern manifests as:
  - Growing caches without eviction
  - Appending to global lists
  - Circular references preventing garbage collection

- **Fix the root cause** and deploy a patched version

- **Add memory monitoring** as a standard metric for all services

### Follow-up

- Implement bounded data structures (LRU cache, ring buffers)
- Add memory profiling to CI for regression detection
- Consider setting memory-based HPA (Horizontal Pod Autoscaler)
- Review all services for similar patterns
