import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

# -------------------- Page Setup --------------------
st.set_page_config(
    page_title="SupportLens | Monitoring",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 SupportLens")
st.caption("Production Support & Incident Monitoring Dashboard")


# -------------------- API Helper --------------------
def fetch_data(endpoint, params=None):
    """Fetch JSON data from FastAPI."""
    try:
        response = requests.get(
            f"{API_URL}{endpoint}",
            params=params,
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"API request failed for {endpoint}: {exc}")
        return None


def extract_list(data, key=None):
    """Extract a list from a list or dictionary API response."""
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if key and isinstance(data.get(key), list):
            return data[key]

        for value in data.values():
            if isinstance(value, list):
                return value

    return []


# -------------------- Refresh --------------------
if st.button("🔄 Refresh dashboard"):
    st.rerun()


# -------------------- Load Dashboard Data --------------------
nodes_response = fetch_data("/nodes")
open_response = fetch_data("/alerts", {"status": "open"})
resolved_response = fetch_data("/alerts", {"status": "resolved"})

if (
    nodes_response is None
    or open_response is None
    or resolved_response is None
):
    st.warning("Ensure FastAPI is running, then refresh the dashboard.")
    st.stop()

nodes = extract_list(nodes_response, "nodes")
open_alerts = extract_list(open_response, "alerts")
resolved_alerts = extract_list(resolved_response, "alerts")

nodes_df = pd.DataFrame(nodes)
open_df = pd.DataFrame(open_alerts)
resolved_df = pd.DataFrame(resolved_alerts)


# -------------------- Cluster Overview --------------------
st.header("Cluster Overview")

total_nodes = len(nodes_df)

if total_nodes > 0 and "status" in nodes_df.columns:
    healthy = int((nodes_df["status"] == "healthy").sum())
    warning = int((nodes_df["status"] == "warning").sum())
    critical = int((nodes_df["status"] == "critical").sum())
else:
    healthy = warning = critical = 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Nodes", total_nodes)
col2.metric("🟢 Healthy", healthy)
col3.metric("🟡 Warning", warning)
col4.metric("🔴 Critical", critical)
col5.metric("Open Alerts", len(open_df))

st.divider()


# -------------------- Node Monitoring Table --------------------
st.header("Node Monitoring")

if nodes_df.empty:
    st.info("No nodes have reported metrics yet.")
else:
    preferred_columns = [
        "node_id",
        "status",
        "disk_usage_percent",
        "latency_ms",
        "last_backup_status",
        "backup_duration_sec",
        "last_seen_seconds_ago",
        "timestamp",
        "error_code",
    ]

    visible_columns = [
        column for column in preferred_columns
        if column in nodes_df.columns
    ]

    st.dataframe(
        nodes_df[visible_columns],
        width="stretch",
        hide_index=True,
    )

st.divider()


# -------------------- Resource Monitoring --------------------
st.header("Resource Monitoring")

if not nodes_df.empty and {
    "node_id", "disk_usage_percent"
}.issubset(nodes_df.columns):
    st.subheader("Disk Usage by Node")

    disk_df = nodes_df[
        ["node_id", "disk_usage_percent"]
    ].copy().set_index("node_id")

    st.bar_chart(
        disk_df,
        y="disk_usage_percent",
        color="#4C78A8",
    )

    st.caption(
        "Warning: above 85%. Critical: above 95%. "
        "The API's status rules determine the actual node status."
    )

if not nodes_df.empty and {
    "node_id", "latency_ms"
}.issubset(nodes_df.columns):
    st.subheader("Latency by Node")

    latency_df = nodes_df[
        ["node_id", "latency_ms"]
    ].copy().set_index("node_id")

    st.bar_chart(
        latency_df,
        y="latency_ms",
        color="#F58518",
    )

if not nodes_df.empty and {
    "node_id", "backup_duration_sec"
}.issubset(nodes_df.columns):
    st.subheader("Backup Duration by Node (seconds)")

    backup_df = nodes_df[
        ["node_id", "backup_duration_sec"]
    ].copy().set_index("node_id")

    st.bar_chart(
        backup_df,
        y="backup_duration_sec",
        color="#54A24B",
    )


# -------------------- Node Health Chart --------------------
st.subheader("Node Health Distribution")

if not nodes_df.empty and "status" in nodes_df.columns:
    health_df = (
        nodes_df["status"]
        .value_counts()
        .rename_axis("status")
        .reset_index(name="count")
    )

    st.vega_lite_chart(
        health_df,
        {
            "mark": {"type": "arc", "innerRadius": 50},
            "encoding": {
                "theta": {
                    "field": "count",
                    "type": "quantitative",
                },
                "color": {
                    "field": "status",
                    "type": "nominal",
                    "scale": {
                        "domain": ["healthy", "warning", "critical"],
                        "range": ["#2E8B57", "#E3A008", "#D62728"],
                    },
                },
                "tooltip": [
                    {"field": "status", "type": "nominal"},
                    {"field": "count", "type": "quantitative"},
                ],
            },
            "width": 350,
            "height": 300,
        },
        width="stretch",
    )

st.divider()


# -------------------- Historical Metrics --------------------
st.header("Metric History")

if not nodes_df.empty and "node_id" in nodes_df.columns:
    selected_node = st.selectbox(
        "Select a node",
        sorted(nodes_df["node_id"].dropna().unique().tolist()),
    )

    minutes = st.selectbox(
        "History window",
        [5, 15, 30, 60],
        index=2,
        format_func=lambda value: f"Last {value} minutes",
    )

    if st.button("Load Metric History"):
        st.session_state["history_node"] = selected_node
        st.session_state["history_minutes"] = minutes

    if "history_node" in st.session_state:
        history_node = st.session_state["history_node"]
        history_minutes = st.session_state["history_minutes"]

        history_response = fetch_data(
            f"/metrics/{history_node}",
            {"minutes": history_minutes},
        )

        if history_response is not None:
            history = extract_list(history_response, "metrics")
            history_df = pd.DataFrame(history)

            if (
                not history_df.empty
                and "timestamp" in history_df.columns
            ):
                history_df["timestamp"] = pd.to_datetime(
                    history_df["timestamp"],
                    errors="coerce",
                    utc=True,
                )

                history_df = history_df.dropna(subset=["timestamp"])
                history_df = history_df.sort_values("timestamp")

                chart_columns = [
                    column
                    for column in [
                        "disk_usage_percent",
                        "latency_ms",
                    ]
                    if column in history_df.columns
                ]

                if chart_columns:
                    st.subheader(f"History for {history_node}")

                    st.line_chart(
                        history_df.set_index("timestamp")[chart_columns],
                        width="stretch",
                    )
                else:
                    st.info("No supported metric columns were returned.")
            else:
                st.info(
                    "No historical readings found. "
                    "Keep the simulator running and try again."
                )

st.divider()


# -------------------- Incident Alerts --------------------
st.header("Incident Alerts")

alert_filter = st.radio(
    "Choose alerts to display",
    ["Open", "Resolved", "All"],
    horizontal=True,
)

if alert_filter == "Open":
    displayed_alerts = open_df
elif alert_filter == "Resolved":
    displayed_alerts = resolved_df
else:
    displayed_alerts = pd.concat(
        [open_df, resolved_df],
        ignore_index=True,
    )

if displayed_alerts.empty:
    st.info("No alerts found for this filter.")

else:
    st.dataframe(
        displayed_alerts,
        width="stretch",
        hide_index=True,
    )

    if "id" in displayed_alerts.columns:
        alert_ids = displayed_alerts["id"].tolist()

        selected_alert_id = st.selectbox(
            "Select an alert to investigate",
            alert_ids,
        )

        # Find the selected alert's current status.
        selected_rows = displayed_alerts[
            displayed_alerts["id"] == selected_alert_id
        ]

        selected_status = (
            selected_rows.iloc[0]["status"]
            if not selected_rows.empty
            and "status" in selected_rows.columns
            else None
        )

        # Button 1: View the incident summary.
        if st.button("Generate / View Incident Summary"):
            summary = fetch_data(
                f"/alerts/{selected_alert_id}/summary"
            )

            if summary is not None:
                st.subheader("Incident Summary")
                st.write(f"**Node:** {summary['node_id']}")
                st.write(f"**Severity:** {summary['severity']}")
                st.write(f"**Status:** {summary['status']}")
                st.write(f"**Incident:** {summary['incident']}")
                st.write(f"**Evidence:** {summary['evidence']}")

                st.markdown("**Probable Causes**")
                for cause in summary["probable_causes"]:
                    st.write(f"- {cause}")

                st.markdown("**Recommended Actions**")
                for action in summary["recommended_actions"]:
                    st.write(f"- {action}")

        # Button 2: Resolve the alert independently.
        if selected_status == "open":
            if st.button("Resolve Selected Alert"):
                try:
                    response = requests.post(
                        f"{API_URL}/alerts/{selected_alert_id}/resolve",
                        timeout=5,
                    )
                    response.raise_for_status()

                    st.success(
                        f"Alert {selected_alert_id} resolved successfully."
                    )

                    # Clear the dashboard's previous history of this action.
                    st.rerun()

                except requests.RequestException as exc:
                    st.error(f"Could not resolve alert: {exc}")

        elif selected_status == "resolved":
            st.info("This alert is already resolved.")


# -------------------- Footer --------------------
st.divider()
st.caption(
    "SupportLens | FastAPI • SQLite • pandas • Streamlit"
)
