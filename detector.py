
import sqlite3
from datetime import datetime, timezone
from statistics import mean, pstdev

from db import get_connection, init_db


def parse_timestamp(value: str) -> datetime:
    """Convert a stored timestamp into a timezone-aware datetime."""
    timestamp = datetime.fromisoformat(value)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp


def create_alert(
    connection: sqlite3.Connection,
    node_id: str,
    rule_name: str,
    severity: str,
    message: str,
    now: datetime,
) -> bool:
    """Create an alert only if the same rule has no open alert for this node."""

    existing_alert = connection.execute(
        """
        SELECT id
        FROM alerts
        WHERE node_id = ?
          AND rule_name = ?
          AND status = 'open'
        LIMIT 1
        """,
        (node_id, rule_name),
    ).fetchone()

    # Avoid creating duplicate open alerts.
    if existing_alert:
        return False

    connection.execute(
        """
        INSERT INTO alerts (
            node_id, rule_name, severity, message,
            status, created_at
        )
        VALUES (?, ?, ?, ?, 'open', ?)
        """,
        (node_id, rule_name, severity, message, now.isoformat()),
    )

    return True


def run_detection(now: datetime | None = None) -> int:
    """Check stored metrics and create alerts for detected problems."""

    init_db()

    if now is None:
        now = datetime.now(timezone.utc)

    alerts_created = 0

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM metrics
            ORDER BY node_id, timestamp, id
            """
        ).fetchall()

        # Group readings by node.
        nodes = {}

        for row in rows:
            nodes.setdefault(row["node_id"], []).append(dict(row))

        for node_id, metrics in nodes.items():
            latest = metrics[-1]
            previous = metrics[-2] if len(metrics) >= 2 else None

            # Rule 1: Disk usage is critical above 95%.
            disk = latest["disk_usage_percent"]

            if disk > 95:
                if create_alert(
                    connection, node_id, "disk_usage", "critical",
                    f"Disk usage is critically high: {disk}%.", now
                ):
                    alerts_created += 1

            # Otherwise, warn if disk is above 85% and increasing.
            elif (
                disk > 85
                and previous is not None
                and disk > previous["disk_usage_percent"]
            ):
                if create_alert(
                    connection, node_id, "disk_usage", "warning",
                    f"Disk usage is high and increasing: {disk}%.", now
                ):
                    alerts_created += 1

            # Rule 2: Three consecutive failed backups.
            recent_backups = [
                metric["last_backup_status"] for metric in metrics[-3:]
            ]

            if (
                len(recent_backups) == 3
                and all(status == "failed" for status in recent_backups)
            ):
                if create_alert(
                    connection, node_id, "backup_failures", "critical",
                    "The last three backup attempts failed.", now
                ):
                    alerts_created += 1

            # Rule 3: No heartbeat for more than 60 seconds.
            last_seen = parse_timestamp(latest["timestamp"])
            age_seconds = (now - last_seen).total_seconds()

            if age_seconds > 60:
                if create_alert(
                    connection, node_id, "heartbeat_missing", "critical",
                    f"No metrics received for {age_seconds:.0f} seconds.",
                    now,
                ):
                    alerts_created += 1

            # Rule 4: Latest latency is an unusually high spike.
            # Compare it against the 30 readings immediately before it.
            history = metrics[-31:-1]

            if len(history) == 30:
                old_latencies = [
                    metric["latency_ms"] for metric in history
                ]
                current_latency = latest["latency_ms"]

                baseline_mean = mean(old_latencies)
                baseline_std = pstdev(old_latencies)

                if baseline_std == 0:
                    z_score = (
                        float("inf")
                        if current_latency > baseline_mean
                        else 0
                    )
                else:
                    z_score = (
                        current_latency - baseline_mean
                    ) / baseline_std

                if z_score > 3:
                    if create_alert(
                        connection, node_id, "latency_spike", "warning",
                        f"Unusual latency spike detected (z-score: {z_score:.2f}).",
                        now,
                    ):
                        alerts_created += 1

    return alerts_created


if __name__ == "__main__":
    count = run_detection()
    print(f"Detection complete. New alerts created: {count}")
