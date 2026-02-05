# Enterprise Surveillance Dashboard (SOC)

Verkada/Rhombus/Avigilon-style web UI for forensic review, real-time monitoring, and analytics. Built with **Plotly Dash** and **dash-bootstrap-components**. Combines elements from the **Flask** and **React** dashboards: live streams, system status, and map/sites when using the Vigil API.

## Features

- **Multi-page:** Overview, **Live**, Timeline, Persons & Tracks, Alerts & Anomalies, **Map**, Settings
- **Data sources:** CSV, SQLite, or **API** (live data from Vigil Flask backend at `api_base_url`)
- **When using API:** Overview shows **System status** (recording, DB, uptime, cameras); **Live** shows MJPEG stream grid; **Map** shows sites and camera positions from Vigil
- **Dark/light theme** (CYBORG / FLATLY) with header toggle
- **Global filters:** Date range, scene (Indoor/Outdoor), object type, event (loitering/motion), threat threshold, clothing search
- **Visualizations:** KPI cards, heatmap (hour × day), occupancy trend, threat distribution, anomaly scatter, event timeline table
- **Persons:** Proxy identity by clothing + height (stub for ReID)
- **Detail modal:** Click a timeline row to see full event details (timestamp, object, clothing, threat, hash)
- **Export:** CSV / JSON from Timeline
- **Polling:** Configurable interval (default 30s) for near-real-time updates

## Setup

From the **project root** (camera-main):

```bash
pip install -r dashboard/requirements.txt
```

## Run

From the **project root**:

```bash
python -m dashboard.app
# or
python dashboard/app.py
```

Then open **http://127.0.0.1:8050**.

## Config

Edit `dashboard/config.yaml`:

- **data.source:** `csv`, `sqlite`, or `api`
- **data.csv_path** / **data.sqlite_path:** path to file (relative to project root)
- **data.api_base_url:** when `source: api`, Vigil Flask URL (e.g. `http://localhost:5000`) for live data, Live streams, Map, and system status
- **data.api_get_data_limit:** max rows from `/get_data` when using API (default 5000)
- **polling.interval_ms:** refresh interval (e.g. 30000)
- **theme.default:** `dark` or `light`

## Deploy

For production, use gunicorn (e.g. `gunicorn dashboard.app:server -b 0.0.0.0:8050`) or Docker. Add auth and role-based views for multi-user SOC use.
