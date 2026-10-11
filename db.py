
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "supportlens.db"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Commit successful transactions and always close the connection."""
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row

    try:
        with connection:
            yield connection
    finally:
        connection.close()



def init_db() -> None:
    """Create tables and indexes if they do not exist."""
    try:
        with get_connection() as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        disk_usage_percent REAL NOT NULL
                            CHECK (disk_usage_percent BETWEEN 0 AND 100),
                        latency_ms REAL NOT NULL
                            CHECK (latency_ms >= 0),
                        last_backup_status TEXT NOT NULL
                            CHECK (last_backup_status IN ('success', 'failed')),
                        backup_duration_sec REAL NOT NULL
                            CHECK (backup_duration_sec >= 0),
                        error_code TEXT
                    )
                """)

                connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_node_timestamp
                    ON metrics (node_id, timestamp)
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT NOT NULL,
                        rule_name TEXT NOT NULL,
                        severity TEXT NOT NULL
                            CHECK (severity IN ('warning', 'critical')),
                        message TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'resolved')),
                        created_at TEXT NOT NULL,
                        resolved_at TEXT
                    )
                """)

                connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_alerts_status
                    ON alerts (status)
                """)

    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Could not initialize database: {exc}"
        ) from exc


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
