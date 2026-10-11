# SupportLens — Infrastructure Monitoring & Incident Triage

SupportLens is a Python-based infrastructure monitoring and incident-triage application that simulates infrastructure nodes, collects system metrics, detects potential incidents using rule-based detection, and displays node health and alerts through an interactive dashboard.

The application uses FastAPI to expose REST APIs, SQLite to store metrics and alerts, and Streamlit to visualize node health and incident information. It also generates incident summaries containing evidence, probable causes, and recommended actions.

> **Note:** Incident summaries provide rule-based guidance. They do not guarantee a confirmed root cause.

## Features

- **Node Monitoring:** Simulates multiple infrastructure nodes and collects disk usage, latency, backup status, and backup duration.
- **REST API:** Uses FastAPI to receive metrics and expose node health and alert information.
- **Persistent Storage:** Stores metrics and alerts in an SQLite database.
- **Automated Incident Detection:** Checks incoming metrics against predefined detection rules.
- **Duplicate Alert Prevention:** Prevents repeated creation of the same open alert for a node and rule.
- **Incident Summaries:** Generates incident descriptions, supporting evidence, probable causes, and recommended actions.
- **Interactive Dashboard:** Displays node health, metrics, charts, alerts, and incident summaries.
- **Alert Resolution:** Allows open alerts to be marked as resolved.
- **Automated Testing:** Uses pytest to test database operations and detector behavior.

## Technology Stack

- Python
- FastAPI
- Uvicorn
- SQLite (`sqlite3`)
- Requests
- Streamlit
- Pandas
- Pytest

## Architecture and Data Flow

```text
                 simulator.py
                      |
                      | Sends metrics through HTTP
                      v
                 api.py
                (FastAPI)
                      |
             +--------+--------+
             |                 |
             v                 v
        SQLite Database   detector.py
       (supportlens.db)        |
             ^                 |
             |<----------------+
             |
             v
       summary_generator.py
             |
             v
        api.py endpoints
             |
             | Fetches metrics and alerts
             v
      frontend/app.py
        (Streamlit UI)
```

### How the application works

1. `simulator.py` generates simulated readings for infrastructure nodes.
2. The simulator sends metrics to the `POST /metrics` endpoint.
3. `api.py` validates the incoming data and saves it in the SQLite database.
4. After a metric is successfully stored, the API calls `run_detection()` from `detector.py`.
5. The detector checks the stored metrics against predefined incident rules.
6. Matching incidents are inserted into the alerts table, unless an equivalent open alert already exists.
7. The API exposes node health, alerts, and incident summaries through REST endpoints.
8. `frontend/app.py` fetches this information and displays it in the Streamlit dashboard.

**Important:** Alert detection is triggered by incoming metrics in the current implementation. Refreshing the dashboard retrieves existing data; it does not itself run the detector.

## Project Structure

```text
SupportLens/
│
├── .venv/                    # Python virtual environment
├── db.py                     # Database connection and schema
├── api.py                    # FastAPI application and REST endpoints
├── simulator.py              # Infrastructure metric simulator
├── detector.py               # Rule-based incident detection
├── summary_generator.py      # Incident summary generation
├── supportlens.db            # SQLite database
├── README.md                 # Project documentation
│
├── tests/
│   ├── test_database.py      # Database tests
│   └── test_detector.py      # Detector tests
│
└── frontend/
    └── app.py                # Streamlit dashboard
```

The database file is created or initialized by the application's database setup code. The `.venv` directory is a local environment and generally should not be committed to Git.

## Prerequisites

- Python installed on your machine
- PowerShell or Command Prompt on Windows
- Git (optional, if cloning or version-controlling the project)

The commands below assume the project is located at:

```text
F:\SupportLens
```

Replace this path if your project is stored elsewhere.

## Installation and Setup

### 1. Open the project directory

```powershell
cd F:\SupportLens
```

### 2. Create a virtual environment

If Python 3.14 is installed:

```powershell
py -3.14 -m venv .venv
```

If Python 3.14 is unavailable, check which versions are installed:

```powershell
py --list
```

Then use an installed version, for example:

```powershell
py -3.11 -m venv .venv
```

### 3. Activate the virtual environment

In PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

In Command Prompt:

```bat
.venv\Scripts\activate.bat
```

### 4. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn requests streamlit pandas pytest
```

SQLite is included with Python through the built-in `sqlite3` module, so no separate SQLite pip package is required.

## Running the Application

Run the API, simulator, and dashboard in separate terminal windows.

### Terminal 1: Start the FastAPI server

```powershell
cd F:\SupportLens
.\.venv\Scripts\Activate.ps1
python -m uvicorn api:app --reload
```

Here:

- `api` refers to the Python file `api.py`.
- `app` refers to the FastAPI application instance created in that file, typically with `app = FastAPI()`.
- `--reload` automatically restarts the development server when code changes.

The API is available at:

- API base URL: http://127.0.0.1:8000
- Interactive API documentation: http://127.0.0.1:8000/docs

Keep this terminal running.

### Terminal 2: Start the simulator

```powershell
cd F:\SupportLens
.\.venv\Scripts\Activate.ps1
python simulator.py
```

The simulator sends metrics to the running API. Keep it running to continue generating new readings.

To stop the simulator, press `Ctrl+C`.

Previously stored data remains in the SQLite database.

### Terminal 3: Start the Streamlit dashboard

```powershell
cd F:\SupportLens
.\.venv\Scripts\Activate.ps1
python -m streamlit run frontend/app.py
```

The dashboard is normally available at:

http://localhost:8501

The dashboard displays the node health information, metric history, charts, alerts, and incident summaries returned by the API.

## Simulating Infrastructure Failures

SupportLens provides failure scenarios to demonstrate how the detector responds to abnormal metrics.

Run these commands after starting the API.

### 1. Normal simulation

```powershell
python simulator.py --failure none
```

Generates normal simulated readings.

### 2. Random failure

```powershell
python simulator.py --failure random
```

Runs a randomly selected failure scenario supported by the simulator.

### 3. Disk usage failure on node-2

```powershell
python simulator.py --failure disk --node node-2
```

Simulates increasing disk usage on `node-2`. When disk usage exceeds the critical threshold, the detector can generate a critical alert.

### 4. Backup failure on node-2

```powershell
python simulator.py --failure backup --node node-2
```

Simulates repeated backup failures. A critical backup alert is created when the latest three backup readings are all failed.

### 5. Latency failure on node-2

```powershell
python simulator.py --failure latency --node node-2
```

Simulates increased latency. The latency detector requires enough historical readings to establish a baseline before it can detect a statistical spike.

### 6. Heartbeat failure on node-2

```powershell
python simulator.py --failure heartbeat --node node-2
```

Simulates a node that temporarily stops sending metrics. See the heartbeat limitation in the Detection Rules section below.

To inspect all supported simulator arguments, run:

```powershell
python simulator.py --help
```

## Detection Rules

The detector evaluates stored metrics and creates alerts when its rules match.

| Detection rule | Condition | Severity |
|---|---|---|
| Critical disk usage | Latest disk usage is greater than 95%. | Critical |
| High and increasing disk usage | Disk usage is greater than 85% and higher than the previous reading. | Warning |
| Repeated backup failures | The latest three backup readings are all `failed`. | Critical |
| Missing heartbeat | The latest metric is older than 60 seconds. | Critical |
| Latency spike | At least 30 previous readings are available for the baseline and the current latency has a z-score greater than 3. | Warning |

### Duplicate alert prevention

Before inserting an alert, the detector checks whether an open alert already exists for the same node and detection rule.

If an open alert already exists, another copy is not created. If the alert has been resolved and the incident condition occurs again, a new alert may be created by a later detection run.

### Node health versus incident alerts

Node health and alert generation are separate operations:

- The `/nodes` endpoint calculates the current node status from its latest metrics.
- `detector.py` evaluates the detection rules to determine whether an alert should be stored.
- Therefore, a node can show a critical or warning status without a newly created alert if the detector's specific rule conditions are not met.

### Heartbeat detection limitation

The current API calls the detector after a metric arrives. If a node completely stops sending metrics, no new metric arrives to trigger that call. The detector will not necessarily detect the missing heartbeat at the moment the node goes silent.

A periodic background task or scheduled detector run is needed to reliably identify nodes that stop sending metrics.

## API Endpoints

The following endpoints are available in the current application.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Returns the basic API response. |
| `POST` | `/metrics` | Validates and stores a metric, then invokes the detector. |
| `GET` | `/nodes` | Returns node health information. |
| `GET` | `/metrics/{node_id}?minutes=30` | Returns recent metric history for a node. |
| `GET` | `/alerts?status=open` | Returns alerts filtered by status. |
| `POST` | `/alerts/{alert_id}/resolve` | Marks an open alert as resolved. |
| `GET` | `/alerts/{alert_id}/summary` | Generates a summary for a particular alert. |

You can explore these endpoints and send test requests using:

http://127.0.0.1:8000/docs

### Check node health

Open:

http://127.0.0.1:8000/nodes

### Check open alerts

Open:

http://127.0.0.1:8000/alerts?status=open

You can also use PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/alerts?status=open"
```

### Resolve an alert

Use the actual alert ID returned by the API or shown on the dashboard:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/alerts/1/resolve"
```

Replace `1` with the correct alert ID.

Resolving an alert changes its status; it does not repair the underlying node or stop the simulator from generating abnormal metrics.

## Incident Summary Generation

`summary_generator.py` generates a structured summary for an alert. Depending on the alert and available evidence, the summary includes:

- **Incident:** A description of the detected problem.
- **Evidence:** Metric readings or conditions that support the alert.
- **Probable causes:** Potential explanations for the incident.
- **Recommended actions:** Suggested steps for investigation or remediation.

The summary is intended to help a user understand and investigate an incident more quickly. Probable causes are suggestions, not verified root causes.

## Automated Testing

Tests are written using pytest.

### Run all tests

Run from the project root:

```powershell
python -m pytest -v
```

### Run database tests

```powershell
python -m pytest -v tests/test_database.py
```

### Run detector tests

```powershell
python -m pytest -v tests/test_detector.py
```

Run tests from the project root so Python can resolve the project modules and use the expected database path.

If your test filenames or folder names differ, adjust the commands to match your actual project structure.

## Troubleshooting

### Python version not found

If you see `No suitable Python runtime found`, check the installed versions:

```powershell
py --list
```

Create the virtual environment using one of the versions shown in the output.

### Missing Python package

Activate the virtual environment and install the dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install fastapi uvicorn requests streamlit pandas pytest
```

### Simulator cannot connect to FastAPI

1. Confirm that the API server is running.
2. Open http://127.0.0.1:8000/docs.
3. Check that the simulator is sending requests to the correct API URL and port.
4. Inspect the API terminal for errors.

### Dashboard does not show new readings

1. Confirm that the simulator is running.
2. Confirm that the API is running.
3. Check the `/nodes` and metric endpoints in the API documentation.
4. Remember that the database can contain old readings after the simulator has stopped.

### No alert is created

1. Confirm that the metric was successfully received by `POST /metrics`.
2. Check whether the relevant detection rule's threshold and historical requirements are satisfied.
3. Check whether an open alert already exists for the same node and rule.
4. Inspect the API terminal for exceptions raised during detection.
5. For a disk test, run `python simulator.py --failure disk --node node-2` and wait until disk usage exceeds 95%.

### Refreshing the dashboard does not generate alerts

Dashboard refreshes fetch existing API data. In the current implementation, detection runs after incoming metrics are stored. A periodic background check is needed for time-based conditions such as a node that stops sending metrics.

## Current Limitations

- The project uses simulated metrics rather than monitoring real infrastructure.
- Detection uses predefined rules and thresholds.
- Incident summaries provide suggested explanations and actions rather than verified root-cause analysis.
- SQLite is appropriate for a local demonstration but may not suit high-volume distributed monitoring.
- Reliable heartbeat detection requires a periodic check independent of new metric arrivals.
- Production features such as authentication, authorization, alert delivery integrations, and deployment hardening are outside the current scope.

## Future Improvements

- Add scheduled or background heartbeat detection.
- Add notifications for critical incidents.
- Add configurable thresholds for different nodes.
- Expand tests for API endpoints and failure scenarios.
- Add alert acknowledgement and assignment workflows.
- Add authentication and production deployment configuration.

## License

No license has been specified yet. Add a license if you plan to distribute the project publicly.
