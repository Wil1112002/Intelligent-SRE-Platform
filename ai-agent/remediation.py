import logging

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from config import settings

logger = logging.getLogger(__name__)


def _get_apps_client() -> client.AppsV1Api:
    if settings.in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    return client.AppsV1Api()


def restart_deployment(name: str, namespace: str | None = None) -> str:
    """Perform a rollout restart on a deployment."""
    ns = namespace or settings.remediation_namespace
    try:
        apps = _get_apps_client()
        # Patch the deployment with a restart annotation to trigger rollout
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "sre-agent/restartedAt": __import__("datetime")
                            .datetime.now(__import__("datetime").timezone.utc)
                            .isoformat()
                        }
                    }
                }
            }
        }
        apps.patch_namespaced_deployment(name, ns, body)
        msg = f"Rollout restart triggered for deployment/{name} in {ns}"
        logger.info(msg)
        return msg
    except ApiException as e:
        msg = f"Failed to restart deployment/{name}: {e.reason}"
        logger.error(msg)
        return msg


def scale_deployment(name: str, delta: int = 1, namespace: str | None = None) -> str:
    """Scale a deployment up by delta replicas."""
    ns = namespace or settings.remediation_namespace
    try:
        apps = _get_apps_client()
        deployment = apps.read_namespaced_deployment(name, ns)
        current = deployment.spec.replicas or 1
        new_count = current + delta

        body = {"spec": {"replicas": new_count}}
        apps.patch_namespaced_deployment(name, ns, body)
        msg = f"Scaled deployment/{name} from {current} to {new_count} replicas in {ns}"
        logger.info(msg)
        return msg
    except ApiException as e:
        msg = f"Failed to scale deployment/{name}: {e.reason}"
        logger.error(msg)
        return msg


def determine_and_execute_remediation(
    alert_name: str,
    service: str,
    recommendation: str,
) -> str | None:
    """Based on the alert and AI recommendation, execute a safe remediation action."""
    if not settings.remediation_enabled:
        return None

    alert_lower = alert_name.lower()
    rec_lower = recommendation.lower()

    # Pod crash looping -> restart deployment
    if "crashloop" in alert_lower or "restart" in rec_lower:
        return restart_deployment(service)

    # Memory leak or high memory -> scale up
    if "memory" in alert_lower or "scale" in rec_lower:
        return scale_deployment(service, delta=1)

    # Very high error rate -> restart as last resort
    if "veryhigherrorrate" in alert_lower.replace(" ", ""):
        return restart_deployment(service)

    logger.info("No automated remediation matched for alert=%s", alert_name)
    return None
