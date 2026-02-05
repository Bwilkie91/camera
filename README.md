# Vigil — Edge Video Security

**Enterprise-grade AI-powered surveillance** with real-time analytics, NISTIR 8161–style chain of custody, and a React dashboard. Built for edge (Jetson, Raspberry Pi) and self-hosted deployment.

**Standards rating: [80/100](docs/STANDARDS_RATING.md)** — aligned with NISTIR 8161, SWGDE, CJIS, and NIST AI 100-4 for evidence and operations.

---

## Table of Contents

- [What is Vigil](#what-is-vigil)
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Features](#features)
- [API Reference](#api-reference)
- [Dashboard & UI](#dashboard--ui)
- [Security & Compliance](#security--compliance)
- [Deployment](#deployment)
- [Project Structure](#project-structure)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)

---

## What is Vigil

Vigil is a **Flask backend** plus **React frontend** that:

- **Ingests video** from local cameras (OpenCV indices) or RTSP, with optional thermal (FLIR Lepton).
- **Runs AI only while recording**: YOLO object detection, MediaPipe pose (standing/person-down, fall, gait notes), optional emotion (DeepFace or EmotiEffLib), LPR on vehicles, motion/loitering/line-crossing from `config.json`.
- **Stores detections and events** in SQLite with a **canonical schema**, per-row integrity hashes, and UTC timestamps for chain of custody.
- **Exports** AI data CSV and recordings with SHA-256 and NISTIR 8161–style headers (operator/admin).
- **Serves** a React dashboard (Live, Events, Timeline, Map, Analytics, Export, Settings) or legacy HTML; WebSocket for real-time events; optional MFA, RBAC, and audit log.

Data is collected **only when recording is on**; export and retention support compliance and evidence workflows.

---

## Quick Start

```bash
git clone https://github.com/Bwilkie91/camera.git && cd camera
cp .env.example .env
# Edit .env: CAMERA_SOURCES=0 (or rtsp://…), ADMIN_PASSWORD, etc.

python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./run.sh
```

- **Backend only**: Open **http://localhost:5000** for the legacy HTML dashboard.
- **React UI**: From project root, `cd frontend && npm install && npm run build`, then `USE_REACT_APP=1 ./run.sh`. Open **http://localhost:5000** and log in (default `admin` / value of `ADMIN_PASSWORD` or `admin`).
- **Development**: Terminal 1: `./run.sh`. Terminal 2: `cd frontend && npm run dev`. Open **http://localhost:5173** (Vite proxies to Flask).

For **production and evidence-grade** settings, see the *Highest standards* block in [.env.example](.env.example) and [docs/STANDARDS_RATING.md](docs/STANDARDS_RATING.md).

---

## Requirements

- **Python 3.8+**
- **System**: Tesseract (for LPR); camera or RTSP source.
- **Optional**: RPi.GPIO (Pi/Jetson PTZ), PyAudio + SpeechRecognition (audio), Scapy (Wi‑Fi), flirpy (thermal), onvif-zeep (ONVIF PTZ), Redis (multi-instance WebSocket), pyotp (MFA). See [requirements.txt](requirements.txt) and [requirements-optional.txt](requirements-optional.txt).

---

## Installation

### Backend

```bash
pip install -r requirements.txt
# Optional: pip install -r requirements-optional.txt (PyYAML, Redis, MFA, etc.)
python app.py
```

Listens on `0.0.0.0:5000`. Use a [virtual environment](.venv) and [run.sh](run.sh) so the script can activate it and, when `USE_REACT_APP=1`, build the frontend if `frontend/dist` is missing.

### React dashboard (recommended)

```bash
cd frontend && npm install && npm run build
USE_REACT_APP=1 python app.py
```

### Optional: Node.js SMS relay

If you use Twilio, run your own Node server and set `ALERT_SMS_URL` and `ALERT_PHONE` in `.env`. The app POSTs to that URL on motion/loitering/line_cross/crowding.

---

## Configuration

| Area | Where | Description |
|------|--------|-------------|
| **Cameras** | `CAMERA_SOURCES` | Comma-separated indices (`0`, `1`) or RTSP URLs. `auto` = auto-detect; `yaml` = load from `config/cameras.yaml` (see [config/README.md](config/README.md)). |
| **Analytics** | `config.json` | `loiter_zones`, `loiter_seconds`, `crossing_lines` (normalized 0–1). Override path with `CONFIG_DIR`. |
| **Homography** | `config/homography.json` | Per-camera 3×3 matrix for floor-plane mapping; enables `world_x`, `world_y` in ai_data. See [docs/MAPPING_OPTIMIZATION_RESEARCH.md](docs/MAPPING_OPTIMIZATION_RESEARCH.md). |
| **Auth** | `FLASK_SECRET_KEY`, `ADMIN_PASSWORD` | Session secret and default admin password. Change in production. |
| **Session / lockout** | `SESSION_TIMEOUT_MINUTES`, `LOCKOUT_MAX_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES` | NIST/CJIS-style; defaults 60 min, 5 attempts, 15 min. |
| **YOLO** | `YOLO_MODEL`, `YOLO_DEVICE`, `YOLO_IMGSZ`, `YOLO_CONF` | Model (default `yolov8n.pt`), device (e.g. `0` for GPU), size (640/1280), confidence. [docs/YOLO_INTEGRATION.md](docs/YOLO_INTEGRATION.md). |
| **Stream** | `STREAM_JPEG_QUALITY`, `STREAM_MAX_WIDTH` | MJPEG quality and max width; recording is full resolution. |
| **Emotion** | `EMOTION_BACKEND` | `auto`, `deepface`, or `emotiefflib`. [docs/EMOTION_INTEGRATION.md](docs/EMOTION_INTEGRATION.md). |
| **MediaPipe** | `ENABLE_GAIT_NOTES`, `MEDIAPIPE_POSE_MODEL_PATH` | Pose/gait and optional path to `pose_landmarker.task`; else auto-download to `models/`. |
| **Recording** | UI *Recording* or `POST /recording_config` | Event types (motion, loitering, line_cross, fall), capture_audio/thermal/wifi, ai_detail (minimal/full). |
| **Retention** | `RETENTION_DAYS`, `AUDIT_RETENTION_DAYS` | Prune ai_data, events, recordings; audit log has separate retention (0 = never). |
| **Alerts** | `ALERT_WEBHOOK_URL`, `ALERT_SMS_URL`, `ALERT_MQTT_BROKER`, `ALERT_MQTT_TOPIC` | Webhook POST, SMS relay, or MQTT. |
| **Security** | `STRICT_TRANSPORT_SECURITY`, `ENFORCE_HTTPS`, `CONTENT_SECURITY_POLICY` | HSTS, redirect to HTTPS, CSP. Use behind reverse proxy. |
| **MFA** | `ENABLE_MFA=1`, `MFA_ISSUER_NAME` | TOTP (install pyotp); NIST IR 8523 / CJIS. |
| **Scaling** | `REDIS_URL` | Multi-instance WebSocket broadcast. |

Full matrix and presets: [docs/CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md).

---

## Features

### Video & streaming

- **Cameras**: `CAMERA_SOURCES` (indices or RTSP); `/video_feed`, `/video_feed/<id>` (MJPEG).
- **Thermal**: Mock or flirpy/Lepton; `/thermal_feed`.
- **Streams**: `GET /streams` for dashboard; configurable quality and max width.
- **Recording**: Start/stop via UI or `POST /toggle_recording`; AVI (optionally MP4 with ffmpeg); NISTIR 8161–style export headers.

### AI (when recording is on)

- **Object detection**: YOLO (configurable model, device, size, confidence and per-class conf); class filter via `YOLO_IGNORE_CLASSES`.
- **Pose**: MediaPipe (Standing / Person down); fall detection (one person, horizontal torso); optional gait_notes (posture, symmetry). Supports legacy and Tasks API (0.10.30+).
- **Emotion**: DeepFace or EmotiEffLib on person crop; optional.
- **Scene**: Indoor/Outdoor heuristic; optional extended attributes (height, build, hair, clothing) when `ai_detail=full`.
- **LPR**: PyTesseract on YOLO vehicle ROIs; stored in ai_data; vehicle activity API.
- **Motion**: Frame-diff; triggers Motion Detected event.
- **Loitering / line-crossing**: Zones and crossing lines in `config.json`; person centroids; configurable dwell and debounce.
- **Crowding**: Optional alert when person count ≥ `CROWD_DENSITY_ALERT_THRESHOLD`.
- **Data quality**: Canonical ai_data schema; primary person (largest bbox) used for centroid and extended attributes; resolution-scaled height estimate. [docs/DATA_COLLECTION_RESEARCH.md](docs/DATA_COLLECTION_RESEARCH.md).

### Events & alerts

- **Events table**: motion, loitering, line_cross, fall, crowding; metadata JSON; acknowledge; WebSocket push.
- **Alerts**: Webhook, SMS relay, or MQTT on event types and severity.
- **Optional**: Perimeter action URL and GPIO on line_cross/loitering; autonomous action URL when threat_score ≥ threshold. [docs/LEGAL_AND_ETHICS.md](docs/LEGAL_AND_ETHICS.md).

### PTZ

- **ONVIF**: `ONVIF_HOST`, `ONVIF_USER`, `ONVIF_PASS`; ContinuousMove/Stop.
- **GPIO**: RPi/Jetson when `USE_GPIO=1` (pins 23, 24, 25).
- **Auto follow**: `AUTO_PTZ_FOLLOW=1` (ONVIF) follows largest person bbox.

### Auth & access control

- **Login**: bcrypt; session timeout; lockout after N failed attempts.
- **Roles**: viewer, operator, admin; per-site roles; export and acknowledge by role.
- **MFA**: Optional TOTP; setup in Settings.
- **Password policy**: Min length, digit, special, expiry, history (configurable).
- **Audit log**: Login, export, config change, recording; export with SHA-256; verify endpoint.
- **Civilian mode**: `EXPORT_REQUIRES_APPROVAL=1` so only admin can export. [docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md](docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md).

### Evidence & export

- **AI data**: CSV with canonical columns; per-row `integrity_hash`; export metadata and `X-Export-SHA256`, `X-Export-UTC`, `X-Operator`, `X-System-ID`; verify at `GET /api/v1/ai_data/verify`.
- **Recordings**: List, download with chain-of-custody headers, manifest (SHA-256).
- **Incident bundle**: `GET /api/v1/export/incident_bundle` (date range): recordings list, AI CSV URL, manifest, checksums.
- **Legal hold**: API to preserve time ranges from retention. [docs/AI_DETECTION_LOGS_STANDARDS.md](docs/AI_DETECTION_LOGS_STANDARDS.md).

### Optional modules

- **Predictive threat**: `ENABLE_PREDICTIVE_THREAT=1` — rule-based escalation in pipeline.
- **Watchlist**: `ENABLE_WATCHLIST=1` — DeepFace embedding vs watchlist; tag `individual` and `face_match_confidence`; `GET/POST/DELETE /api/v1/watchlist`.
- **NL search**: `NL_SEARCH_WEBHOOK_URL` — `POST /api/v1/search` can call webhook; webhook returns event/ai_data IDs for merged results.
- **Idle skip**: `ANALYZE_IDLE_SKIP_SECONDS` — when no motion for N seconds, longer sleep between analysis cycles to save CPU.

---

## API Reference

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard (legacy HTML or React when `USE_REACT_APP=1`). |
| GET | `/streams` | List MJPEG streams (id, name, type, url). |
| GET | `/health`, `/health/ready` | Liveness; readiness (DB). |
| GET | `/recording` | Current recording state. |
| GET | `/video_feed`, `/video_feed/<id>` | MJPEG. |
| GET | `/thermal_feed` | MJPEG thermal. |
| GET | `/get_data` | AI data (params: limit, offset, date_from, date_to, event_type). |
| GET | `/events` | Events (params: limit, offset, camera_id, event_type, severity, acknowledged). |
| POST | `/events`, `POST /events/<id>/acknowledge` | Create event; acknowledge. |
| GET | `/export_data` | AI data CSV (auth: operator/admin); chain-of-custody headers. |
| GET | `/recordings` | List recordings. |
| GET | `/recordings/<name>/export` | Download with X-Export-* headers. |
| GET | `/recordings/<name>/manifest` | JSON manifest + SHA-256. |
| GET | `/recordings/<name>/play` | Stream for playback. |
| POST | `/toggle_recording` | Start/stop recording. |
| GET, POST | `/recording_config` | Get/set event types, capture_audio/thermal/wifi, ai_detail. |
| POST | `/move_camera` | PTZ (body: direction). |
| GET | `/config`, PATCH `/config` | Analytics config (zones, lines); PATCH audited (admin). |
| GET | `/sites`, `/camera_positions` | Map data. |
| POST | `/login`, GET `/me`, POST `/logout` | Auth. |
| GET | `/audit_log`, GET `/audit_log/export` | Audit log; CSV export (admin). |
| WebSocket | `/ws` | New-event notifications. |

### API v1

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/system_status` | DB, uptime, recording, cameras, AI status (yolo, emotion, mediapipe). |
| GET | `/api/v1/what_we_collect` | Privacy: list of collected data points. |
| GET | `/api/v1/config/public` | Public config (map tile, default center/zoom). |
| GET | `/api/v1/cameras/detect`, `/api/v1/audio/detect`, `/api/v1/devices` | Auto-detect cameras, mics, unified devices. |
| GET | `/api/v1/notable_screenshots`, `/api/v1/notable_screenshots/<id>/image` | Notable behavior screenshots. |
| GET | `/api/v1/analytics/aggregates` | Time-series by event/camera (date_from, date_to). |
| GET | `/api/v1/analytics/heatmap` | Binned heatmap (hour × day). |
| GET | `/api/v1/analytics/spatial_heatmap` | Camera-view occupancy (centroid_nx/ny). |
| GET | `/api/v1/analytics/world_heatmap` | Floor-plane heatmap (world_x/world_y; requires homography). |
| GET | `/api/v1/analytics/zone_dwell` | Person-seconds per zone per hour. |
| GET | `/api/v1/analytics/vehicle_activity` | LPR sightings and per-plate summary. |
| GET, POST | `/api/v1/search` | Keyword search over events and ai_data (body: q, limit); optional NL webhook. |
| GET | `/api/v1/export/incident_bundle` | Incident bundle (recordings, AI export URL, manifest). |
| GET, POST, DELETE | `/api/v1/legal_hold` | Legal hold list; add; remove. |
| GET, POST, DELETE | `/api/v1/saved_searches` | Saved searches. |
| GET, POST, DELETE | `/api/v1/watchlist` | Watchlist (when ENABLE_WATCHLIST=1). |
| GET | `/api/v1/ai_data/verify` | Verify per-row integrity_hash (operator/admin). |
| GET | `/api/v1/users`, `/api/v1/users/<id>/sites` | Users; user site roles (admin). |
| POST | `/api/v1/reset_data` | Delete all events and ai_data (admin). |

---

## Dashboard & UI

- **Legacy**: `templates/index.html` — multi-camera, AI log, exports. Served at `/` when React build is not used.
- **React** (recommended): Dashboard, Live (stream grid, recording, PTZ), Events, Timeline, Map (sites, camera positions), Analytics, Export (AI CSV + recordings), Settings, Behaviors. Login required; RBAC for export and acknowledge. Build: `cd frontend && npm run build`; run with `USE_REACT_APP=1`.
- **Plotly Dash** (optional): [dashboard/](dashboard/) — SOC-style multi-page app (Overview, Live, Timeline, Persons, Alerts, Map, Settings); can use Vigil API or CSV/SQLite. See [dashboard/README.md](dashboard/README.md).

---

## Security & Compliance

- **Secrets**: Use `.env` for `FLASK_SECRET_KEY`, `ADMIN_PASSWORD`, ONVIF, Twilio; never commit `.env`. [docs/KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md).
- **Auth**: Session-based; bcrypt; strong password and MFA in production.
- **Chain of custody**: Per-row and export-level SHA-256; UTC timestamps; `system_id` and `model_version` in ai_data; export headers (X-Export-SHA256, X-Operator, X-System-ID). [docs/AI_DETECTION_LOGS_STANDARDS.md](docs/AI_DETECTION_LOGS_STANDARDS.md).
- **Data collection**: Only while recording is on; canonical schema; primary-person consistency. [docs/AUDIT_DATA_COLLECTION.md](docs/AUDIT_DATA_COLLECTION.md), [docs/DATA_COLLECTION_RESEARCH.md](docs/DATA_COLLECTION_RESEARCH.md).
- **Audit**: Login, export, config change, recording; audit log export with SHA-256; separate audit retention.
- **HTTPS**: Run behind a reverse proxy; set `ENFORCE_HTTPS=1`, `STRICT_TRANSPORT_SECURITY=1` in production.
- **Encryption at rest**: Use an encrypted volume (e.g. LUKS) for DB and recordings, or document key management for app-level encryption. [docs/SYSTEM_RATING.md](docs/SYSTEM_RATING.md).
- **Standards rating**: [80/100](docs/STANDARDS_RATING.md) — NISTIR 8161, SWGDE, CJIS, NIST AI 100-4; gaps: encryption at rest, enforced TLS, formal legal-hold workflow.

---

## Deployment

### Docker (recommended for edge / self-hosted)

```bash
cp .env.example .env
# Edit .env: CAMERA_SOURCES, PORT, etc.
docker compose up --build
```

Volumes: `vigil_data` (DB), `vigil_recordings`, `vigil_config` (config.json, cameras.yaml), `vigil_snapshots`. Use Export in the UI or `GET /export_data`, `GET /recordings/<name>/export` for downloads. GPU: uncomment `deploy.resources.reservations.devices` in [docker-compose.yml](docker-compose.yml) and set `YOLO_DEVICE=0`.

### Production server (gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -k gthread --threads 4 --bind 0.0.0.0:5000 --timeout 120 app:app
```

Use Nginx or Caddy as reverse proxy for HTTPS and WebSocket (`/ws`). See [docs/CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md).

### Edge (Pi / Jetson)

Run `app.py` or gunicorn under systemd/supervisord; optionally Nginx. Set `JETSON_MODE=1` and use TensorRT export for YOLO when applicable.

---

## Project Structure

| Path | Purpose |
|------|---------|
| `app.py` | Flask app: API, streams, analysis loop, DB, WebSocket. |
| `frontend/` | React (Vite, TypeScript, Tailwind) dashboard. |
| `templates/` | Legacy HTML dashboard and settings. |
| `config/` | Optional config.json, cameras.yaml, homography.json; see [config/README.md](config/README.md). |
| `docs/` | 40+ guides: standards, audit, config, AI, legal, research. |
| `dashboard/` | Optional Plotly Dash SOC-style dashboard. |
| `proactive/` | Optional proactive predictor and log parsing. |
| `vigil_upgrade/` | Optional upgrade path (tracker, ReID, storage). |
| `scripts/` | audit-deps.sh, surveillance_log_parser, test_gait_and_env. |
| `run.sh` | Start backend; use .venv if present; build React if USE_REACT_APP=1 and dist missing. |

---

## Operations

- **Database**: Back up `surveillance.db`; retention job prunes ai_data, events, and recordings by `RETENTION_DAYS`.
- **Recordings**: Stored in app directory or `RECORDINGS_DIR`; pruned by retention; export via UI or API.
- **Dependency audit**: Run `./scripts/audit-deps.sh` (or `pip audit`) for CVE checks. [docs/SYSTEM_RATING.md](docs/SYSTEM_RATING.md).
- **Runbooks**: [docs/RUNBOOKS.md](docs/RUNBOOKS.md) — lost camera, export failed, DB locked, WebSocket, NTP, low disk.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| No module 'RPi.GPIO' | Install only core deps; GPIO optional unless `USE_GPIO=1` or on ARM. |
| Camera open fails | Check camera or set `CAMERA_SOURCES` to RTSP URL; on headless use RTSP or dummy. |
| React blank / Failed to fetch | Ensure Flask on 5000; in dev use Vite proxy; cross-origin: `ENABLE_CORS=1`, `VITE_API_URL`. |
| Login fails (admin/admin) | Default user created on first successful login; set `ADMIN_PASSWORD` before first run. |
| Export 403 | Export requires operator or admin role. |
| USE_REACT_APP=1 but legacy UI | Run `cd frontend && npm run build` so `frontend/dist` exists. |
| Python SIGSEGV (e.g. 3.14) | Prefer Python 3.11 or 3.12; thread-local SQLite in use. |

More: [docs/RUNBOOKS.md](docs/RUNBOOKS.md).

---

## Documentation

### Standards & audit

- [STANDARDS_RATING.md](docs/STANDARDS_RATING.md) — Highest-standards rating (80/100), criteria, gaps.
- [AI_DETECTION_LOGS_STANDARDS.md](docs/AI_DETECTION_LOGS_STANDARDS.md) — NISTIR 8161, SWGDE, NIST AI 100-4.
- [AUDIT_DATA_COLLECTION.md](docs/AUDIT_DATA_COLLECTION.md) — Data collection and chain-of-custody audit.
- [DATA_COLLECTION_RESEARCH.md](docs/DATA_COLLECTION_RESEARCH.md) — Collection pipeline, schema, primary-person, improvements.
- [GOVERNMENT_STANDARDS_AUDIT.md](docs/GOVERNMENT_STANDARDS_AUDIT.md) — NIST/CJIS alignment, frontend UX.
- [SYSTEM_RATING.md](docs/SYSTEM_RATING.md) — Security score (74/100), encryption, TLS, pip audit.

### Configuration & operations

- [CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md) — Env presets, YOLO, RTSP, MJPEG, gunicorn.
- [KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md) — Secrets, storage, rotation, TLS.
- [RUNBOOKS.md](docs/RUNBOOKS.md) — Operational runbooks.
- [INSTALL_AUDIT.md](docs/INSTALL_AUDIT.md) — Install and dependency audit.

### AI & analytics

- [YOLO_INTEGRATION.md](docs/YOLO_INTEGRATION.md) — Model, device, export (ONNX, TensorRT, OpenVINO).
- [EMOTION_INTEGRATION.md](docs/EMOTION_INTEGRATION.md) — DeepFace vs EmotiEffLib.
- [GAIT_AND_POSE_OPEN_SOURCE.md](docs/GAIT_AND_POSE_OPEN_SOURCE.md) — MediaPipe, gait notes, fall detection.
- [ACCURACY_RESEARCH_AND_IMPROVEMENTS.md](docs/ACCURACY_RESEARCH_AND_IMPROVEMENTS.md) — Per-field accuracy and research.
- [MAPPING_OPTIMIZATION_RESEARCH.md](docs/MAPPING_OPTIMIZATION_RESEARCH.md) — Homography, spatial/world heatmaps.
- [DEVICE_AUTODETECT.md](docs/DEVICE_AUTODETECT.md) — Camera and microphone detection.

### Frontend & UX

- [APP_REVIEW_AND_RATING.md](docs/APP_REVIEW_AND_RATING.md) — Application review (78/100), features, design.
- [FRONTEND_UI_AUDIT.md](docs/FRONTEND_UI_AUDIT.md) — React UI audit.

### Legal & ethics

- [LEGAL_AND_ETHICS.md](docs/LEGAL_AND_ETHICS.md) — Perimeter/autonomous actions, liability.
- [CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md](docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md) — Civilian mode, privacy.

### Research & roadmap

- [ENTERPRISE_ROADMAP.md](docs/ENTERPRISE_ROADMAP.md) — Best-in-class comparison, scaling, AI/ML.
- [TECHNOLOGY_RESEARCH_AND_CONFIG.md](docs/TECHNOLOGY_RESEARCH_AND_CONFIG.md) — Speech backends, RTSP, inference.
- [OPTIMIZATION_AUDIT.md](docs/OPTIMIZATION_AUDIT.md) — Performance, DB, limits.

---

## License

Use in compliance with local laws regarding surveillance, privacy, and data retention. No warranty; production use at your own risk.
