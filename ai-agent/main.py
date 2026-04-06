import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import settings
from database import get_incident, init_db, list_incidents, resolve_incident, save_incident
from observability_client import (
    get_error_rate,
    get_p99_latency,
    get_pod_restarts,
    query_loki_errors,
)
from remediation import determine_and_execute_remediation
from triage import triage_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.db_path)
    logger.info("Database initialized at %s", settings.db_path)
    yield


app = FastAPI(title="SRE AI Triage Agent", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Alertmanager webhook models
# ---------------------------------------------------------------------------

class AlertLabel(BaseModel):
    alertname: str = ""
    severity: str = "unknown"
    service: str = ""
    namespace: str = "default"


class AlertAnnotation(BaseModel):
    summary: str = ""
    description: str = ""


class Alert(BaseModel):
    status: str
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}
    startsAt: str = ""
    endsAt: str = ""


class AlertmanagerPayload(BaseModel):
    status: str
    alerts: list[Alert]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/webhook")
async def webhook(payload: AlertmanagerPayload) -> dict[str, Any]:
    """Receive Alertmanager webhook, triage each alert, and return results."""
    results: list[dict[str, Any]] = []

    for alert in payload.alerts:
        # Skip resolved alerts
        if alert.status == "resolved":
            logger.info("Skipping resolved alert: %s", alert.labels.get("alertname"))
            continue

        alert_name = alert.labels.get("alertname", "Unknown")
        severity = alert.labels.get("severity", "unknown")
        service = alert.labels.get("service", alert.labels.get("job", "unknown"))
        firing_since = alert.startsAt

        logger.info(
            "Processing alert: %s severity=%s service=%s",
            alert_name, severity, service,
        )

        # Gather observability context
        error_rate = await get_error_rate(settings.prometheus_url, service)
        p99_latency = await get_p99_latency(settings.prometheus_url, service)
        restart_count = await get_pod_restarts(
            settings.prometheus_url,
            alert.labels.get("namespace", "default"),
        )
        log_lines = await query_loki_errors(settings.loki_url, service)

        # Call Claude for triage
        triage_result = await triage_alert(
            alert_name=alert_name,
            severity=severity,
            service=service,
            firing_time=firing_since,
            error_rate=error_rate,
            p99_latency=p99_latency,
            restart_count=restart_count,
            log_lines=log_lines,
        )

        # Attempt automated remediation
        remediation_action = determine_and_execute_remediation(
            alert_name=alert_name,
            service=service,
            recommendation=triage_result["recommendation"],
        )

        # Save to database
        incident_id = save_incident(
            db_path=settings.db_path,
            alert_name=alert_name,
            severity=severity,
            service=service,
            firing_since=firing_since,
            root_cause=triage_result["root_cause"],
            recommendation=triage_result["recommendation"],
            remediation_action=remediation_action,
        )

        result = {
            "incident_id": incident_id,
            "alert_name": alert_name,
            "severity": severity,
            "root_cause": triage_result["root_cause"],
            "recommendation": triage_result["recommendation"],
            "remediation_action": remediation_action,
        }
        results.append(result)
        logger.info("Incident #%d created for alert %s", incident_id, alert_name)

    return {"processed": len(results), "incidents": results}


# ---------------------------------------------------------------------------
# REST API for srekit CLI
# ---------------------------------------------------------------------------

@app.get("/incidents")
async def list_incidents_endpoint(
    severity: str | None = None,
    status: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return list_incidents(
        settings.db_path,
        severity=severity,
        status=status,
        since=since,
        limit=limit,
    )


@app.get("/incidents/{incident_id}")
async def get_incident_endpoint(incident_id: int) -> dict[str, Any]:
    incident = get_incident(settings.db_path, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/incidents/{incident_id}/resolve")
async def resolve_incident_endpoint(incident_id: int) -> dict[str, str]:
    if resolve_incident(settings.db_path, incident_id):
        return {"status": "resolved"}
    raise HTTPException(status_code=404, detail="Incident not found or already resolved")
