# Runbook: Pod CrashLooping

## Alert

- **PodCrashLooping**: Pod restarts > 3 in 10 minutes (severity: critical)

## Symptoms

- Pod repeatedly enters CrashLoopBackOff state
- Service becomes unavailable or intermittently reachable
- Kubernetes keeps restarting the container with increasing backoff

## Metrics to Check

```promql
# Pod restart count
increase(kube_pod_container_status_restarts_total[10m])

# Pod status
kube_pod_status_phase

# Container last terminated reason
kube_pod_container_status_last_terminated_reason
```

## Diagnosis Steps

1. **Identify the crashing pod**:
   ```bash
   kubectl get pods -n default --field-selector=status.phase!=Running
   kubectl get pods -n default | grep CrashLoopBackOff
   ```

2. **Check pod events**:
   ```bash
   kubectl describe pod <pod-name> -n default
   ```
   Look for:
   - OOMKilled (out of memory)
   - Error (application crash)
   - ContainerCannotRun (configuration issue)

3. **Check container logs** (current and previous):
   ```bash
   kubectl logs <pod-name> -n default --tail=100
   kubectl logs <pod-name> -n default --previous --tail=100
   ```

4. **Check resource usage** vs limits:
   ```bash
   kubectl top pod <pod-name> -n default
   kubectl get pod <pod-name> -n default -o jsonpath='{.spec.containers[0].resources}'
   ```

5. **Check for recent changes**:
   ```bash
   kubectl rollout history deployment/<deployment-name> -n default
   ```

6. **Check liveness probe configuration** — is the probe timing out before the app starts?

## Remediation

### OOMKilled

The container exceeded its memory limit.

```bash
# Increase memory limits
kubectl patch deployment <name> -n default -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"<container>","resources":{"limits":{"memory":"512Mi"}}}]}}}}'
```

### Application Error

The application is crashing on startup.

- Check logs for the error
- If caused by a bad deploy, rollback:
  ```bash
  kubectl rollout undo deployment/<name> -n default
  ```

### Configuration Issue

Missing environment variables, secrets, or ConfigMaps.

```bash
# Check environment
kubectl exec <pod-name> -n default -- env
# Check mounted secrets/configmaps
kubectl get pod <pod-name> -n default -o jsonpath='{.spec.volumes}'
```

### Liveness Probe Failure

The probe is failing before the app is ready.

- Increase `initialDelaySeconds` on the liveness probe
- Ensure the health endpoint doesn't depend on external services

### Follow-up

- Review memory usage patterns — is there a leak?
- Add startup probes for slow-starting containers
- Set up PodDisruptionBudgets to maintain availability during disruptions
- Investigate root cause of application crash and fix in code
