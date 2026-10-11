
from datetime import datetime, timedelta, timezone

import db
import pytest
from detector import run_detection


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    # Give each test its own temporary database.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def add_metric(
    node_id="node-1",
    timestamp=None,
    disk=60,
    latency=30,
    backup="success",
    duration=100,
    error_code=None,
):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    with db.get_connection() as connection:
        connection.execute(
            """
            INSERT INTO metrics (
                node_id, timestamp, disk_usage_percent, latency_ms,
                last_backup_status, backup_duration_sec, error_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                timestamp.isoformat(),
                disk,
                latency,
                backup,
                duration,
                error_code,
            ),
        )


def get_alerts():
    with db.get_connection() as connection:
        return connection.execute(
            "SELECT * FROM alerts"
        ).fetchall()


def test_critical_disk_usage(test_db):
    add_metric(disk=97)

    assert run_detection() == 1
    alert = get_alerts()[0]
    assert alert["rule_name"] == "disk_usage"
    assert alert["severity"] == "critical"


def test_increasing_disk_usage_warning(test_db):
    now = datetime.now(timezone.utc)
    add_metric(timestamp=now - timedelta(seconds=3), disk=88)
    add_metric(timestamp=now, disk=90)

    assert run_detection() == 1
    assert get_alerts()[0]["severity"] == "warning"


def test_three_failed_backups(test_db):
    now = datetime.now(timezone.utc)

    for seconds_ago in [3, 2, 1]:
        add_metric(
            timestamp=now - timedelta(seconds=seconds_ago),
            backup="failed",
            error_code="BACKUP_FAILED",
        )

    assert run_detection() == 1
    assert get_alerts()[0]["rule_name"] == "backup_failures"


def test_missing_heartbeat(test_db):
    old_time = datetime.now(timezone.utc) - timedelta(seconds=65)
    add_metric(timestamp=old_time)

    assert run_detection() == 1
    assert get_alerts()[0]["rule_name"] == "heartbeat_missing"


def test_latency_spike(test_db):
    now = datetime.now(timezone.utc)

    # Establish a baseline of 30 normal readings.
    for seconds_ago in range(31, 1, -1):
        add_metric(
            timestamp=now - timedelta(seconds=seconds_ago),
            latency=30,
        )

    # The latest reading is much higher than the baseline.
    add_metric(timestamp=now, latency=200)

    assert run_detection() == 1
    assert get_alerts()[0]["rule_name"] == "latency_spike"


def test_duplicate_open_alert_is_prevented(test_db):
    add_metric(disk=97)

    assert run_detection() == 1
    assert run_detection() == 0
    assert len(get_alerts()) == 1


def test_healthy_node_creates_no_alert(test_db):
    add_metric(disk=60, latency=30, backup="success")

    assert run_detection() == 0
    assert len(get_alerts()) == 0


def test_only_two_failed_backups_create_no_backup_alert(test_db):
    now = datetime.now(timezone.utc)
    add_metric(timestamp=now - timedelta(seconds=2), backup="failed")
    add_metric(timestamp=now - timedelta(seconds=1), backup="failed")

    assert run_detection() == 0
    assert len(get_alerts()) == 0
