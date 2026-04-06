"""srekit incident — query and interact with incidents from the AI triage agent."""

import os
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

incident_app = typer.Typer(help="Manage and query incidents from the AI triage agent")

AGENT_URL = os.environ.get("SRE_AGENT_URL", "http://localhost:8000")


@incident_app.command("list")
def incident_list(
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Filter by severity"),
    since: Optional[str] = typer.Option(None, "--since", help="Filter incidents since ISO timestamp"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status: open|resolved"),
) -> None:
    """List past incidents from the AI triage agent."""
    params: dict[str, str] = {}
    if severity:
        params["severity"] = severity
    if since:
        params["since"] = since
    if status:
        params["status"] = status

    try:
        resp = httpx.get(f"{AGENT_URL}/incidents", params=params, timeout=10)
        resp.raise_for_status()
        incidents = resp.json()
    except httpx.HTTPError as e:
        console.print(f"[red]Failed to connect to AI agent: {e}[/]")
        raise typer.Exit(1)

    if not incidents:
        console.print("[yellow]No incidents found.[/]")
        return

    table = Table(title="Incidents", show_lines=True)
    table.add_column("ID", style="bold")
    table.add_column("Alert")
    table.add_column("Severity")
    table.add_column("Service")
    table.add_column("Status")
    table.add_column("Time")
    table.add_column("Root Cause (summary)")

    for inc in incidents:
        sev_style = {"critical": "red", "warning": "yellow"}.get(inc["severity"], "white")
        status_style = "green" if inc["status"] == "resolved" else "red"
        root_cause_summary = (inc.get("root_cause") or "")[:80]
        table.add_row(
            str(inc["id"]),
            inc["alert_name"],
            f"[{sev_style}]{inc['severity']}[/]",
            inc["service"],
            f"[{status_style}]{inc['status']}[/]",
            inc["created_at"],
            root_cause_summary,
        )

    console.print(table)


@incident_app.command("get")
def incident_get(
    incident_id: int = typer.Argument(..., help="Incident ID to retrieve"),
) -> None:
    """Show full triage details for a specific incident."""
    try:
        resp = httpx.get(f"{AGENT_URL}/incidents/{incident_id}", timeout=10)
        resp.raise_for_status()
        inc = resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            console.print(f"[red]Incident #{incident_id} not found.[/]")
        else:
            console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)
    except httpx.HTTPError as e:
        console.print(f"[red]Failed to connect to AI agent: {e}[/]")
        raise typer.Exit(1)

    sev_style = {"critical": "red", "warning": "yellow"}.get(inc["severity"], "white")

    console.print(Panel(
        f"[bold]Alert:[/] {inc['alert_name']}\n"
        f"[bold]Severity:[/] [{sev_style}]{inc['severity']}[/]\n"
        f"[bold]Service:[/] {inc['service']}\n"
        f"[bold]Status:[/] {inc['status']}\n"
        f"[bold]Firing since:[/] {inc['firing_since']}\n"
        f"[bold]Created:[/] {inc['created_at']}\n"
        f"[bold]Resolved:[/] {inc.get('resolved_at') or 'N/A'}",
        title=f"Incident #{inc['id']}",
    ))

    console.print(Panel(inc.get("root_cause") or "N/A", title="Root Cause"))
    console.print(Panel(inc.get("recommendation") or "N/A", title="Recommendation"))

    if inc.get("remediation_action"):
        console.print(Panel(inc["remediation_action"], title="Remediation Action Taken"))


@incident_app.command("ask")
def incident_ask(
    question: str = typer.Argument(..., help="Natural language question about incidents"),
) -> None:
    """Ask a freeform question about past incidents using Claude AI."""
    import anthropic

    # Fetch recent incidents for context
    try:
        resp = httpx.get(f"{AGENT_URL}/incidents", params={"limit": "20"}, timeout=10)
        resp.raise_for_status()
        incidents = resp.json()
    except httpx.HTTPError as e:
        console.print(f"[red]Failed to fetch incidents: {e}[/]")
        raise typer.Exit(1)

    if not incidents:
        console.print("[yellow]No incidents found to query against.[/]")
        return

    # Build context from incidents
    context_lines: list[str] = []
    for inc in incidents:
        context_lines.append(
            f"- Incident #{inc['id']}: alert={inc['alert_name']}, severity={inc['severity']}, "
            f"service={inc['service']}, status={inc['status']}, time={inc['created_at']}, "
            f"root_cause={inc.get('root_cause', 'N/A')[:200]}"
        )
    context = "\n".join(context_lines)

    prompt = (
        f"You are an SRE assistant. Below is a summary of recent incidents.\n\n"
        f"Incidents:\n{context}\n\n"
        f"User question: {question}\n\n"
        f"Answer concisely based on the incident data. If the data is insufficient, say so."
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        console.print("[red]ANTHROPIC_API_KEY environment variable is not set.[/]")
        raise typer.Exit(1)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        console.print(Panel(message.content[0].text, title="AI Response"))
    except Exception as e:
        console.print(f"[red]Claude API call failed: {e}[/]")
        raise typer.Exit(1)
