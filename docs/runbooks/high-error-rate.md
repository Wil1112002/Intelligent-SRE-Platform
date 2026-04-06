# Runbook: High Error Rate

## Alert

- **HighErrorRate**: Error rate > 5% over 2 minutes (severity: warning)
- **VeryHighErrorRate**: Error rate > 15% over 2 minutes (severity: critical)

## Symptoms

- Increased 5xx responses from the affected service
- Error rate spike visible on the Service Overview dashboard
- Users may report failures or degraded experience

## Metrics to Check

```promql
# Current error rate
sum(rate(error_count_total[5m])) by (endpoint) / sum(rate(request_count_total[5m])) by (endpoint) * 100

# Request rate (check for traffic spike)
sum(rate(request_count_total[5m])) by (endpoint)

# p99 latency (correlated latency degradation?)
histogram_quantile(0.99, sum(rate(request_latency_seconds_bucket[5m])) by (le))

# Pod restarts (is the service crash looping?)
increase(kube_pod_container_status_restarts_total{namespace="default"}[10m])
```

## Diagnosis Steps

1. **Check Grafana Service Overview dashboard** for the error rate trend. Is it a sudden spike or gradual increase?

2. **Check logs in Grafana Incident View** for error patterns:
   - Are errors concentrated on a specific endpoint?
   - Is there a common error message or stack trace?

3. **Check pod health**:
   ```bash
   kubectl get pods -n default
   kubectl describe pod <pod-name> -n default
   kubectl logs <pod-name> -n default --tail=100
   ```

4. **Check for recent deployments**:
   ```bash
   kubectl rollout history deployment/<service-name> -n default
   ```

5. **Check downstream dependencies**:
   - Is a database or external API down?
   - Are there network connectivity issues?

6. **Check resource pressure**:
   ```bash
   kubectl top pods -n default
   kubectl top nodes
   ```

## Remediation

### Immediate

- If caused by a bad deployment, rollback:
  ```bash
  kubectl rollout undo deployment/<service-name> -n default
  ```

- If a pod is unhealthy, restart the deployment:
  ```bash
  kubectl rollout restart deployment/<service-name> -n default
  ```

- If under high load, scale up:
  ```bash
  kubectl scale deployment/<service-name> --replicas=4 -n default
  ```

### Follow-up

- Review error logs to identify root cause
- Add or improve error handling in the service code
- Consider adding circuit breakers for downstream dependencies
- Update alert thresholds if current ones are too sensitive
- Add integration tests covering the failing code paths
