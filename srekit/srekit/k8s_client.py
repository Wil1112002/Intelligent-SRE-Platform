"""Shared Kubernetes client loader."""

from kubernetes import client, config


def get_clients(
    namespace: str | None = None,
) -> tuple[client.CoreV1Api, client.AppsV1Api, str]:
    """Load kubeconfig and return (core_v1, apps_v1, resolved_namespace)."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    ns = namespace or "default"
    return client.CoreV1Api(), client.AppsV1Api(), ns
