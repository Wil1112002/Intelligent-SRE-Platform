"""srekit audit — security and best-practice audit."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from srekit.k8s_client import get_clients

console = Console()


def audit(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Kubernetes namespace to audit"),
    export: Optional[str] = typer.Option(None, "--export", help="Export report to markdown file"),
) -> None:
    """Audit cluster for missing resource limits, root containers, missing probes, and exposed services."""
    core, apps, ns = get_clients(namespace)

    findings: list[dict[str, str]] = []

    findings.extend(_audit_resource_limits(apps, ns))
    findings.extend(_audit_root_containers(apps, ns))
    findings.extend(_audit_missing_probes(apps, ns))
    findings.extend(_audit_exposed_services(core, ns))

    # Display
    table = Table(title=f"Audit Findings ({ns})", show_lines=True)
    table.add_column("Severity", style="bold")
    table.add_column("Resource")
    table.add_column("Finding")
    table.add_column("Recommendation")

    for f in findings:
        sev_style = {"critical": "red", "warning": "yellow", "info": "blue"}.get(
            f["severity"], "white"
        )
        table.add_row(
            f"[{sev_style}]{f['severity'].upper()}[/]",
            f["resource"],
            f["finding"],
            f["recommendation"],
        )

    console.print(table)
    console.print(f"\nTotal findings: {len(findings)}")

    if export:
        _export_markdown(findings, ns, export)
        console.print(f"Report exported to {export}")


def _audit_resource_limits(apps, ns: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for dep in apps.list_namespaced_deployment(ns).items:
        for container in dep.spec.template.spec.containers:
            if not container.resources or not container.resources.requests:
                findings.append({
                    "severity": "warning",
                    "resource": f"deploy/{dep.metadata.name}:{container.name}",
                    "finding": "Missing resource requests",
                    "recommendation": "Set CPU and memory requests for scheduling reliability",
                })
            if not container.resources or not container.resources.limits:
                findings.append({
                    "severity": "warning",
                    "resource": f"deploy/{dep.metadata.name}:{container.name}",
                    "finding": "Missing resource limits",
                    "recommendation": "Set CPU and memory limits to prevent resource starvation",
                })
    return findings


def _audit_root_containers(apps, ns: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for dep in apps.list_namespaced_deployment(ns).items:
        pod_sec = dep.spec.template.spec.security_context
        for container in dep.spec.template.spec.containers:
            sec = container.security_context
            runs_as_root = False

            if sec and sec.run_as_user == 0:
                runs_as_root = True
            elif sec and sec.run_as_non_root is True:
                runs_as_root = False
            elif pod_sec and pod_sec.run_as_non_root is True:
                runs_as_root = False
            elif not sec or sec.run_as_non_root is None:
                runs_as_root = True  # No explicit non-root constraint

            if runs_as_root:
                findings.append({
                    "severity": "critical",
                    "resource": f"deploy/{dep.metadata.name}:{container.name}",
                    "finding": "Container may run as root",
                    "recommendation": "Set securityContext.runAsNonRoot: true",
                })
    return findings


def _audit_missing_probes(apps, ns: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for dep in apps.list_namespaced_deployment(ns).items:
        for container in dep.spec.template.spec.containers:
            if not container.liveness_probe:
                findings.append({
                    "severity": "warning",
                    "resource": f"deploy/{dep.metadata.name}:{container.name}",
                    "finding": "Missing liveness probe",
                    "recommendation": "Add livenessProbe to detect stuck containers",
                })
            if not container.readiness_probe:
                findings.append({
                    "severity": "warning",
                    "resource": f"deploy/{dep.metadata.name}:{container.name}",
                    "finding": "Missing readiness probe",
                    "recommendation": "Add readinessProbe to prevent routing to unready pods",
                })
    return findings


def _audit_exposed_services(core, ns: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for svc in core.list_namespaced_service(ns).items:
        if svc.spec.type in ("NodePort", "LoadBalancer"):
            findings.append({
                "severity": "info",
                "resource": f"svc/{svc.metadata.name}",
                "finding": f"Service exposed via {svc.spec.type}",
                "recommendation": "Verify this exposure is intentional; prefer ClusterIP + Ingress",
            })
    return findings


def _export_markdown(findings: list[dict[str, str]], ns: str, path: str) -> None:
    lines = [
        f"# Audit Report — namespace: {ns}\n",
        f"Total findings: {len(findings)}\n",
        "| Severity | Resource | Finding | Recommendation |",
        "|----------|----------|---------|----------------|",
    ]
    for f in findings:
        lines.append(
            f"| {f['severity'].upper()} | {f['resource']} | {f['finding']} | {f['recommendation']} |"
        )
    Path(path).write_text("\n".join(lines) + "\n")
