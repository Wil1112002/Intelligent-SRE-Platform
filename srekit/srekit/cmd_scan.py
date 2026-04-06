"""srekit scan — cluster health overview."""

import json
from enum import Enum
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from srekit.k8s_client import get_clients

console = Console()


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


def scan(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Kubernetes namespace to scan"),
    output: OutputFormat = typer.Option(OutputFormat.table, "--output", "-o", help="Output format"),
) -> None:
    """Scan cluster health: deployments, services, and nodes."""
    core, apps, ns = get_clients(namespace)

    deployments = _scan_deployments(apps, ns)
    services = _scan_services(core, ns)
    nodes = _scan_nodes(core)

    if output == OutputFormat.json:
        console.print_json(data={"deployments": deployments, "services": services, "nodes": nodes})
        return

    # Deployments table
    dep_table = Table(title=f"Deployments ({ns})", show_lines=True)
    dep_table.add_column("Name", style="bold")
    dep_table.add_column("Ready")
    dep_table.add_column("Restarts")
    dep_table.add_column("Resource Limits")
    dep_table.add_column("Status")

    for d in deployments:
        status_style = "green" if d["status"] == "Healthy" else "red"
        limits_style = "green" if d["has_limits"] else "yellow"
        dep_table.add_row(
            d["name"],
            d["ready"],
            str(d["restarts"]),
            f"[{limits_style}]{'Yes' if d['has_limits'] else 'Missing'}[/]",
            f"[{status_style}]{d['status']}[/]",
        )
    console.print(dep_table)

    # Services table
    svc_table = Table(title=f"Services ({ns})", show_lines=True)
    svc_table.add_column("Name", style="bold")
    svc_table.add_column("Type")
    svc_table.add_column("Endpoints")
    svc_table.add_column("Status")

    for s in services:
        status_style = "green" if s["status"] == "Healthy" else "red"
        svc_table.add_row(
            s["name"],
            s["type"],
            str(s["endpoints"]),
            f"[{status_style}]{s['status']}[/]",
        )
    console.print(svc_table)

    # Nodes table
    node_table = Table(title="Nodes", show_lines=True)
    node_table.add_column("Name", style="bold")
    node_table.add_column("Status")
    node_table.add_column("CPU (allocatable)")
    node_table.add_column("Memory (allocatable)")

    for n in nodes:
        status_style = "green" if n["status"] == "Ready" else "red"
        node_table.add_row(
            n["name"],
            f"[{status_style}]{n['status']}[/]",
            n["cpu"],
            n["memory"],
        )
    console.print(node_table)


def _scan_deployments(apps, ns: str) -> list[dict]:
    results: list[dict] = []
    deployments = apps.list_namespaced_deployment(ns)

    for dep in deployments.items:
        ready = dep.status.ready_replicas or 0
        desired = dep.spec.replicas or 0
        status = "Healthy" if ready == desired else "Degraded"

        # Check resource limits
        has_limits = all(
            c.resources and c.resources.limits
            for c in dep.spec.template.spec.containers
        )

        # Get restart count from pods
        restarts = 0
        try:
            from kubernetes import client as k8s_client
            core = k8s_client.CoreV1Api()
            selector = ",".join(
                f"{k}={v}" for k, v in (dep.spec.selector.match_labels or {}).items()
            )
            pods = core.list_namespaced_pod(ns, label_selector=selector)
            for pod in pods.items:
                for cs in pod.status.container_statuses or []:
                    restarts += cs.restart_count
        except Exception:
            pass

        results.append({
            "name": dep.metadata.name,
            "ready": f"{ready}/{desired}",
            "restarts": restarts,
            "has_limits": has_limits,
            "status": status,
        })
    return results


def _scan_services(core, ns: str) -> list[dict]:
    results: list[dict] = []
    services = core.list_namespaced_service(ns)

    for svc in services.items:
        endpoint_count = 0
        try:
            ep = core.read_namespaced_endpoints(svc.metadata.name, ns)
            for subset in ep.subsets or []:
                endpoint_count += len(subset.addresses or [])
        except Exception:
            pass

        status = "Healthy" if endpoint_count > 0 else "No Endpoints"

        results.append({
            "name": svc.metadata.name,
            "type": svc.spec.type,
            "endpoints": endpoint_count,
            "status": status,
        })
    return results


def _scan_nodes(core) -> list[dict]:
    results: list[dict] = []
    nodes = core.list_node()

    for node in nodes.items:
        status = "Unknown"
        for condition in node.status.conditions or []:
            if condition.type == "Ready":
                status = "Ready" if condition.status == "True" else "NotReady"
                break

        allocatable = node.status.allocatable or {}
        results.append({
            "name": node.metadata.name,
            "status": status,
            "cpu": allocatable.get("cpu", "N/A"),
            "memory": allocatable.get("memory", "N/A"),
        })
    return results
