import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str) -> None:
    conn = _get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            service TEXT NOT NULL,
            firing_since TEXT NOT NULL,
            root_cause TEXT,
            recommendation TEXT,
            remediation_action TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_incident(
    db_path: str,
    alert_name: str,
    severity: str,
    service: str,
    firing_since: str,
    root_cause: str,
    recommendation: str,
    remediation_action: str | None = None,
) -> int:
    conn = _get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO incidents
            (alert_name, severity, service, firing_since, root_cause, recommendation, remediation_action, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
        """,
        (
            alert_name,
            severity,
            service,
            firing_since,
            root_cause,
            recommendation,
            remediation_action,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    incident_id = cursor.lastrowid
    conn.close()
    return incident_id  # type: ignore[return-value]


def get_incident(db_path: str, incident_id: int) -> dict[str, Any] | None:
    conn = _get_connection(db_path)
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_incidents(
    db_path: str,
    severity: str | None = None,
    status: str | None = None,
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conn = _get_connection(db_path)
    query = "SELECT * FROM incidents WHERE 1=1"
    params: list[str | int] = []

    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if status:
        query += " AND status = ?"
        params.append(status)
    if since:
        query += " AND created_at >= ?"
        params.append(since)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def resolve_incident(db_path: str, incident_id: int) -> bool:
    conn = _get_connection(db_path)
    cursor = conn.execute(
        "UPDATE incidents SET status = 'resolved', resolved_at = ? WHERE id = ? AND status = 'open'",
        (datetime.now(timezone.utc).isoformat(), incident_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated
