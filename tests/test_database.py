
import sqlite3

from db import init_db, get_connection


def test_database_tables_exist():
    init_db()

    with get_connection() as connection:
        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """).fetchall()

    table_names = {row["name"] for row in tables}

    assert "metrics" in table_names
    assert "alerts" in table_names


def test_metrics_table_has_expected_columns():
    init_db()

    with get_connection() as connection:
        columns = connection.execute(
            "PRAGMA table_info(metrics)"
        ).fetchall()

    column_names = {row["name"] for row in columns}

    assert {
        "node_id",
        "timestamp",
        "disk_usage_percent",
        "latency_ms",
        "last_backup_status",
        "backup_duration_sec",
        "error_code",
    }.issubset(column_names)


def test_alerts_start_with_open_status_by_default():
    init_db()

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO alerts (
                node_id, rule_name, severity, message, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            "node-1",
            "high_disk_usage",
            "warning",
            "Disk usage is high",
            "2026-10-10T10:00:00Z",
        ))

        alert = connection.execute("""
            SELECT status, resolved_at
            FROM alerts
            WHERE node_id = ?
        """, ("node-1",)).fetchone()

        assert alert["status"] == "open"
        assert alert["resolved_at"] is None

        # Keep this test from leaving test data behind.
        connection.execute(
            "DELETE FROM alerts WHERE node_id = ?",
            ("node-1",),
        )
