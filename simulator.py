# Simulator that generates the 5 node data every 3 seconds, chooses failure scenerio
# from random list 
import argparse
import random
import time
from datetime import datetime, timezone

import requests

API_URL = "http://127.0.0.1:8000"
NODE_IDS = [f"node-{i}" for i in range(1, 6)] # 5 nodes generation
INTERVAL_SECONDS = 3

# Use this to randomly select a failure scenario by default.
FAILURES = ["disk", "backup", "latency", "heartbeat"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulate five backup cluster nodes."
    )
    parser.add_argument(
        "--failure",
        choices=["random", "disk", "backup", "latency", "heartbeat", "none"],
        default="random",
        help="Failure scenario to demonstrate (default: random).",
    )
    parser.add_argument(
        "--node",
        choices=NODE_IDS,
        default="node-1",
        help="Node affected by the selected failure.",
    )
    return parser.parse_args()


def create_metric(
    node_id: str,
    cycle: int,
    failure: str,
    target_node: str,
    started_at: float,
) -> dict | None:
    """Generate one node reading, or None if its heartbeat is paused."""

    # Simulate a node that stops reporting for 65 seconds.
    if (
        failure == "heartbeat"
        and node_id == target_node
        and cycle > 0
        and time.monotonic() - started_at < 65
    ):
        return None

    # Small random variations make normal readings look realistic.
    disk_usage = round(random.uniform(55, 75), 2)
    latency = round(random.uniform(25, 45), 2)
    backup_status = "success"
    backup_duration = round(random.uniform(60, 150), 2)
    error_code = None

    if node_id == target_node:
        if failure == "disk":
            # Start high and gradually increase beyond 95%.
            disk_usage = min(82 + cycle * 1.5, 98)

        elif failure == "backup":
            # Every report for this node fails.
            backup_status = "failed"
            error_code = "BACKUP_FAILED"

        elif failure == "latency" and cycle >= 1:
            # Sudden latency spike.
            latency = 250.0
            error_code = "HIGH_LATENCY"

    return {
        "node_id": node_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disk_usage_percent": disk_usage,
        "latency_ms": latency,
        "last_backup_status": backup_status,
        "backup_duration_sec": backup_duration,
        "error_code": error_code,
    }


def send_metric(metric: dict) -> None:
    """Send a metric to FastAPI and report the outcome."""
    try:
        response = requests.post(
            f"{API_URL}/metrics",
            json=metric,
            timeout=5,
        )
        response.raise_for_status()
        print(
            f"[SENT] {metric['node_id']}: "
            f"disk={metric['disk_usage_percent']}%, "
            f"latency={metric['latency_ms']}ms, "
            f"backup={metric['last_backup_status']}"
        )
    except requests.RequestException as exc:
        print(f"[ERROR] Could not send {metric['node_id']}: {exc}")


def main() -> None:
    args = parse_args()

    failure = args.failure
    if failure == "random":
        failure = random.choice(FAILURES)

    print(f"SupportLens simulator starting")
    print(f"API: {API_URL}")
    print(f"Failure scenario: {failure}")
    print(f"Target node: {args.node}")
    print("Press Ctrl+C to stop.\n")

    started_at = time.monotonic()
    cycle = 0

# Generate the nodes
    try:
        while True:
            cycle_started = time.monotonic()

            for node_id in NODE_IDS:
                metric = create_metric(
                    node_id=node_id,
                    cycle=cycle,
                    failure=failure,
                    target_node=args.node,
                    started_at=started_at,
                )

                if metric is None:
                    print(f"[PAUSED] {node_id}: heartbeat stopped")
                    continue

                send_metric(metric)

            cycle += 1

            # Maintain a roughly 3-second interval between cycles.
            elapsed = time.monotonic() - cycle_started 
            time.sleep(max(0, INTERVAL_SECONDS - elapsed))

    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
