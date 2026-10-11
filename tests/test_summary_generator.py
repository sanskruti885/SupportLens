
from datetime import datetime, timezone

import db
import pytest
from summary_generator import generate_alert_summary


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_disk_alert_summary(test_db):
    now = datetime.now(timezone.utc).isoformat()

    with db.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO metrics (
                node_id, timestamp, disk_usage_percent,
                latency_ms, last_backup_status, backup_duration_sec
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("node-1", now, 97, 30, "success", 100),
        )

        cursor = connection.execute(
            """
            INSERT INTO alerts (
                node_id, rule_name, severity, message,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "node-1", "disk_usage", "critical",
                "Disk usage is critically high: 97%.",
                "open", now,
            ),
        )
        alert_id = cursor.lastrowid

    summary = generate_alert_summary(alert_id)

    assert summary["node_id"] == "node-1"
    assert summary["severity"] == "critical"
    assert "97.0%" in summary["evidence"]
    assert len(summary["recommended_actions"]) > 0


def test_missing_alert_returns_none(test_db):
    assert generate_alert_summary(999) is None
