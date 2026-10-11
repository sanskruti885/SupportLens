
from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from db import DB_PATH, get_connection, init_db

from summary_generator import generate_alert_summary
from detector import run_detection
app = FastAPI(
    title="SupportLens API",
    description="API for monitoring a simulated backup cluster",
    version="1.0.0",
)


class MetricInput(BaseModel):
    """Validate a metric received from a cluster node."""

    node_id: str = Field(min_length=1, max_length=100)
    timestamp: datetime
    disk_usage_percent: float = Field(ge=0, le=100)
    latency_ms: float = Field(ge=0)
    last_backup_status: Literal["success", "failed"]
    backup_duration_sec: float = Field(ge=0)
    error_code: str | None = None


def initialize_database() -> None:
    """Ensure the database exists before handling requests."""
    try:
        init_db()
    except (RuntimeError, sqlite3.Error) as exc:
        raise RuntimeError("Database initialization failed") from exc


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/")
def root() -> dict:
    return {"message": "SupportLens API is running"}


@app.post("/metrics", status_code=201)
def create_metric(metric: MetricInput) -> dict:
    """Validate and store one node metric."""
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO metrics (
                    node_id,
                    timestamp,
                    disk_usage_percent,
                    latency_ms,
                    last_backup_status,
                    backup_duration_sec,
                    error_code
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric.node_id,
                    metric.timestamp.isoformat(),
                    metric.disk_usage_percent,
                    metric.latency_ms,
                    metric.last_backup_status,
                    metric.backup_duration_sec,
                    metric.error_code,
                ),
            )
            metric_id = cursor.lastrowid

        alerts_created = run_detection()
        return {
            "message": "Metric stored successfully",
            "id": metric_id,
            "node_id": metric.node_id,
            "alerts_created": alerts_created
        }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not store metric",
        ) from exc


@app.get("/nodes")
def get_nodes() -> dict:
    """Return the latest reading and health status for each known node."""
    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT m.*
                FROM metrics AS m
                JOIN (
                    SELECT node_id, MAX(id) AS latest_id
                    FROM metrics
                    GROUP BY node_id
                ) AS latest
                ON m.id = latest.latest_id
                ORDER BY m.node_id
                """
            ).fetchall()

        now = datetime.now(timezone.utc)
        nodes = []

        for row in rows:
            item = dict(row)
            timestamp = datetime.fromisoformat(item["timestamp"])

            # Treat timestamps without a timezone as UTC.
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            age_seconds = (now - timestamp).total_seconds()

            if age_seconds > 60 or item["last_backup_status"] == "failed":
                status = "critical"
            elif item["disk_usage_percent"] > 95:
                status = "critical"
            elif item["disk_usage_percent"] > 85:
                status = "warning"
            else:
                status = "healthy"

            item["status"] = status
            item["last_seen_seconds_ago"] = round(
                max(0, age_seconds), 2
            )
            nodes.append(item)

        return {"nodes": nodes, "count": len(nodes)}

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve nodes",
        ) from exc


@app.get("/metrics/{node_id}")
def get_metrics(
    node_id: str,
    minutes: int = Query(default=30, ge=1, le=10080),
) -> dict:
    """Return a node's metrics from the requested time window."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=minutes)
    ).isoformat()

    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM metrics
                WHERE node_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC, id ASC
                """,
                (node_id, cutoff),
            ).fetchall()

        return {
            "node_id": node_id,
            "minutes": minutes,
            "metrics": [dict(row) for row in rows],
            "count": len(rows),
        }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve metrics",
        ) from exc


@app.get("/alerts")
def get_alerts(
    status: Literal["open", "resolved"] | None = "open",
) -> dict:
    """List alerts, filtering by status when requested."""
    try:
        with get_connection() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM alerts ORDER BY created_at DESC, id DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM alerts
                    WHERE status = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (status,),
                ).fetchall()

        return {
            "alerts": [dict(row) for row in rows],
            "count": len(rows),
        }

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve alerts",
        ) from exc


@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int) -> dict:
    """Mark an open alert as resolved."""
    resolved_at = datetime.now(timezone.utc).isoformat()

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE alerts
                SET status = 'resolved', resolved_at = ?
                WHERE id = ? AND status = 'open'
                """,
                (resolved_at, alert_id),
            )

            if cursor.rowcount == 0:
                existing = connection.execute(
                    "SELECT id FROM alerts WHERE id = ?",
                    (alert_id,),
                ).fetchone()

                if existing is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Alert not found",
                    )

                raise HTTPException(
                    status_code=409,
                    detail="Alert is already resolved",
                )

        return {
            "message": "Alert resolved successfully",
            "id": alert_id,
            "resolved_at": resolved_at,
        }

    except HTTPException:
        raise
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not resolve alert",
        ) from exc



@app.get("/alerts/{alert_id}/summary")
def get_alert_summary(alert_id: int):
    summary = generate_alert_summary(alert_id)

    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found",
        )

    return summary


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000)
