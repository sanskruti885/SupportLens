# This function will:
# 1. Find the alert in the database.
# 2. Fetch the latest metrics for the affected node.
# 3. Choose evidence and recommended actions based on the alert's rule.
# 4. Return a structured summary that our API can send as JSON.


from datetime import datetime, timezone

from db import get_connection


def generate_alert_summary(alert_id: int) -> dict | None:
    """Build a human-readable summary for an existing alert."""

    with get_connection() as connection:
        # Find the alert.
        alert = connection.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,),
        ).fetchone()

        if alert is None:
            return None

        # Find the latest metrics for the affected node.
        latest = connection.execute(
            """
            SELECT *
            FROM metrics
            WHERE node_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (alert["node_id"],),
        ).fetchone()

        rule = alert["rule_name"]

        # Prepare a summary based on the incident type.
        if rule == "disk_usage":
            evidence = (
                f"Latest disk usage is "
                f"{latest['disk_usage_percent']}%."
                if latest else alert["message"]
            )
            probable_causes = [
                "Large files or logs consuming disk space",
                "Unexpected growth in stored data",
            ]
            recommended_actions = [
                "Inspect disk usage and identify large files.",
                "Check logs for unexpected data growth.",
                "Free space safely after verifying what can be removed.",
            ]

        elif rule == "backup_failures":
            evidence = (
                "The last three backup attempts failed."
            )
            probable_causes = [
                "Backup service or configuration problem",
                "Insufficient storage or connectivity issues",
            ]
            recommended_actions = [
                "Inspect backup logs and error codes.",
                "Verify storage availability and connectivity.",
                "Retry the backup after addressing the cause.",
            ]

        elif rule == "heartbeat_missing":
            evidence = (
                "The node has stopped reporting metrics."
            )
            probable_causes = [
                "Node or monitoring service may be unavailable",
                "Network connectivity problem",
            ]
            recommended_actions = [
                "Check node availability and monitoring service logs.",
                "Verify network connectivity.",
                "Confirm that metrics reporting has resumed.",
            ]

        elif rule == "latency_spike":
            evidence = (
                f"Latest observed latency is {latest['latency_ms']} ms."
                if latest else alert["message"]
            )
            probable_causes = [
                "Increased workload or resource contention",
                "Network delays or a slow downstream dependency",
            ]
            recommended_actions = [
                "Compare latency with historical readings.",
                "Check CPU, memory, network and dependency health.",
                "Investigate whether the spike is repeated.",
            ]

        else:
            evidence = alert["message"]
            probable_causes = [
                "The alert requires further investigation."
            ]
            recommended_actions = [
                "Inspect relevant logs and recent metrics.",
                "Investigate the reported condition.",
            ]

        return {
            "alert_id": alert["id"],
            "node_id": alert["node_id"],
            "rule_name": rule,
            "severity": alert["severity"],
            "status": alert["status"],
            "incident": alert["message"],
            "evidence": evidence,
            "probable_causes": probable_causes,
            "recommended_actions": recommended_actions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
