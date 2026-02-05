# Vigil — Edge Video Security

**Enterprise-grade AI-powered surveillance platform** with real-time video analytics, multi-sensor fusion, PTZ control (GPIO or ONVIF), and a React dashboard. Designed for edge deployment (NVIDIA Jetson, Raspberry Pi) with optional cloud alerting and compliance-ready export.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Installation & Requirements](#installation--requirements)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Dashboard & UI](#dashboard--ui)
- [Security & Compliance](#security--compliance)
- [Deployment](#deployment)
- [Maintenance & Operations](#maintenance--operations)

---

## Overview

This system provides:

- **Real-time video feeds**: RGB and thermal (mock or FLIR Lepton via flirpy) over MJPEG; multi-camera via `CAMERA_SOURCES` (OpenCV indices or RTSP URLs).
- **AI analytics**: Ultralytics YOLO object detection (configurable model; see **docs/YOLO_INTEGRATION.md**), **MediaPipe** pose (Standing/Person down, fall detection, gait_notes; supports legacy and Tasks API), DeepFace/EmotiEffLib emotion (optional), LPR on vehicle ROI, **real motion detection**, **loitering** and **line-crossing** (configurable zones/lines in `config.json`), thermal signature.
- **Events & alerts**: Events table with types (motion, loitering, line_cross); WebSocket push to dashboard; optional SMS via Node.js + Twilio or `ALERT_SMS_URL`.
- **PTZ**: GPIO (RPi) or **ONVIF** (when `ONVIF_HOST`/credentials set).
- **Auth & RBAC**: Session-based login, bcrypt passwords, roles (viewer, operator, admin); audit log; **retention job** (env `RETENTION_DAYS`).
- **Dashboards**: Legacy HTML in `templates/index.html`, or **React app** in `frontend/` (Live, Events, Timeline, Map, Export, Settings) with login.

---

## Architecture

- **Flask (port 5000)**: Serves REST API, MJPEG streams, WebSocket `/ws`, and either the legacy HTML dashboard or the React build (when `USE_REACT_APP=1` and `frontend/dist` exists).
- **React (Vite)**: In dev, run `npm run dev` in `frontend/` and use the proxy to Flask; in production, run `npm run build` and set `USE_REACT_APP=1` so Flask serves `frontend/dist`.
- **SQLite**: `surveillance.db` — `ai_data`, `events`, `sites`, `camera_positions`, `users`, `audit_log`.
- **Optional**: Node.js (port 3000) for Twilio SMS; env `ALERT_SMS_URL` can point to it for server-triggered alerts.

---

## Features

### Video & streaming

| Feature | Description |
|--------|-------------|
| **Cameras** | `CAMERA_SOURCES=0,1` or RTSP URLs; `/video_feed`, `/video_feed/<id>`. |
| **Thermal** | Mock or flirpy/Lepton; `/thermal_feed`. |
| **Streams API** | `GET /streams` returns list of MJPEG streams for the dashboard. |
| **Recording** | `POST /toggle_recording`; AVI to app directory. |

### AI (when recording)

- **Motion**: Frame-diff detection (no random).
- **LPR**: OCR on YOLO vehicle bounding boxes only.
- **Loitering / line-crossing**: Zones and lines in `config.json`; person centroids and crossing detection.
- **Individual/facial**: Stored as "Unidentified" and pose/emotion attributes. Emotion from DeepFace or **EmotiEffLib** (TensorFlow-free); see **docs/EMOTION_INTEGRATION.md**.
- **Optional**: DeepFace, MediaPipe, PyTesseract; audio (PyAudio/SpeechRecognition) and Wi‑Fi (Scapy) in separate threads with timeouts.

### PTZ

- **ONVIF**: Set `ONVIF_HOST`, `ONVIF_USER`, `ONVIF_PASS`; ContinuousMove/Stop.
- **GPIO**: Fallback on Pi/Jetson when `USE_GPIO=1` or on ARM (pins 23, 24, 25).

### Auth & RBAC

- **Login**: `POST /login` with bcrypt; default user `admin` (password from `ADMIN_PASSWORD` or `admin`) created on first login.
- **Roles**: viewer, operator, admin. Export and acknowledge require login; audit log for admins.
- **Endpoints**: `/me`, `POST /logout`, `GET /audit_log` (admin).

### Retention & alerts

- **Retention**: Set `RETENTION_DAYS`; background job every 6 hours deletes old `ai_data`, events, and `recording_*.avi`.
- **Alerts**: Set `ALERT_SMS_URL` (e.g. Node `/send-sms-alert`) and `ALERT_PHONE`; motion/loitering/line_cross or high severity trigger POST.

### Scaling & enterprise

- **API v1**: `GET /api/v1/analytics/aggregates` (time-series by event/camera), `POST /api/v1/search` (keyword search over events and AI data; extension point for NL/LLM).
- **Health**: `GET /health` (liveness), `GET /health/ready` (readiness; DB check) for load balancers and Kubernetes.
- **Multi-instance**: Set `REDIS_URL` to broadcast WebSocket events across instances via Redis pub/sub (`vms:events`).
- **Sites**: Events support `site_id`; filter with `?site_id=` on `/events` and aggregates.
- See **docs/ENTERPRISE_ROADMAP.md** for best-in-class comparison, AI/ML roadmap, and Docker/K8s scaling path.

### New features (Surveillance 2026 plan)

| Feature | Env / config | Description |
|--------|---------------|-------------|
| **Predictive threat (live)** | `ENABLE_PREDICTIVE_THREAT=1` | Integrates proactive predictor rule-based escalation into the live pipeline; updates `threat_score` / `predicted_intent` in ai_data. |
| **Auto PTZ tracking** | `AUTO_PTZ_FOLLOW=1` | ONVIF camera follows the largest person bbox with pan/tilt; cooldown to reduce jitter. |
| **Perimeter actions** | `PERIMETER_ACTION_URL`, `ALERT_GPIO_PIN` | On line_cross/loitering: POST to URL and/or set GPIO high (e.g. spotlight/siren). See **docs/LEGAL_AND_ETHICS.md**. |
| **Fall detection** | (always on when MediaPipe + one person) | Pose heuristic sets event "Fall Detected" and notable reason `person_down`; event type `fall` in recording config. |
| **Zone dwell heatmap** | — | `GET /api/v1/analytics/zone_dwell` returns person-seconds per zone per hour; ai_data stores `zone_presence`. |
| **NL / semantic search** | `NL_SEARCH_WEBHOOK_URL` | `POST /api/v1/search` can call webhook with query; webhook returns `event_ids` / `ai_data_rowids` for merged results. |
| **Familiar vs stranger** | `ENABLE_WATCHLIST=1`, `WATCHLIST_SIMILARITY_THRESHOLD` | DeepFace embedding vs local watchlist; tag `individual` and `face_match_confidence`. `GET/POST/DELETE /api/v1/watchlist`. |
| **YOLO filtering** | `YOLO_IGNORE_CLASSES`, `YOLO_CLASS_CONF` | Ignore classes (e.g. bird, cat) and per-class confidence to reduce false alarms. |
| **Autonomous action webhook** | `AUTONOMOUS_ACTION_URL`, `AUTONOMOUS_ACTION_THRESHOLD`, `AUTONOMOUS_ACTION_EVENT_TYPES` | When threat_score ≥ threshold and event in list, POST to URL (e.g. lock API). Opt-in; see **docs/LEGAL_AND_ETHICS.md**. |
| **Crowd density alert** | `CROWD_DENSITY_ALERT_THRESHOLD` (0 = off) | When person count ≥ threshold, insert `crowding` event and trigger alert webhook/SMS/MQTT. |
| **Vehicle activity (LPR)** | — | `GET /api/v1/analytics/vehicle_activity` returns license-plate sightings and per-plate summary (cross-camera, date range). |
| **Idle skip (efficiency)** | `ANALYZE_IDLE_SKIP_SECONDS`, `ANALYZE_IDLE_INTERVAL_MULTIPLIER` | When no motion for N seconds, sleep longer between analysis cycles to save CPU. |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask, flask-sock, bcrypt, OpenCV, Ultralytics YOLO, DeepFace (optional), MediaPipe (optional), PyTesseract, SQLite |
| Optional | RPi.GPIO, PyAudio, SpeechRecognition, Scapy, flirpy, onvif-zeep |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query |
| Optional | Node.js, Express, Twilio (SMS) |

---

## Quick start

```bash
# Backend only (legacy HTML dashboard at http://localhost:5000)
pip install -r requirements.txt
python app.py
# Or: npm run start

# React dashboard (dev: Vite proxy to Flask)
npm run install:frontend && npm run frontend    # Terminal 1: npm run start
# Open http://localhost:5173, login admin / admin

# Production: serve React from Flask
npm run frontend:build && USE_REACT_APP=1 npm run start
# Open http://localhost:5000

# Or use the run script (uses .venv if present; builds React if USE_REACT_APP=1 and dist missing)
./run.sh
```

Copy `.env.example` to `.env` and adjust (optional). For production and evidence-grade deployment see the **Highest standards** block in `.env.example` and **docs/STANDARDS_RATING.md** (rating 80/100).

---

## Installation & Requirements

### Backend

1. **Python 3.8+** and system deps (Tesseract, etc. as needed).

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

   Optional (install when needed): `RPi.GPIO`, `pyaudio`, `SpeechRecognition`, `scapy`, `flirpy`, `onvif-zeep`.

3. **Templates**: The repo includes `templates/index.html` (legacy dashboard). Flask serves it at `/` unless React build is used (see below).

4. **Run**:

   ```bash
   python app.py
   ```

   App listens on `0.0.0.0:5000`. AI loop and (if set) retention job run in background threads.

### React dashboard (recommended)

1. **Build**:

   ```bash
   cd frontend && npm install && npm run build
   ```

2. **Production (single server)**: From project root, run Flask with React build served at `/`:

   ```bash
   USE_REACT_APP=1 python app.py
   ```

   Open `http://localhost:5000` and log in (default `admin` / `ADMIN_PASSWORD` or `admin`).

3. **Development**: Run Flask and Vite in two terminals:

   ```bash
   python app.py
   cd frontend && npm run dev
   ```

   Open `http://localhost:5173`; Vite proxies API and streams to port 5000.

### Optional: Node.js SMS

```bash
npm install express cors body-parser twilio
TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_PHONE_NUMBER=... node index.js
```

---

## Configuration

| Item | Env / location | Description |
|------|----------------|-------------|
| **Cameras** | `CAMERA_SOURCES` | Comma-separated: `0`, `1` or RTSP URLs. Set `yaml` to load from `config/cameras.yaml` (requires PyYAML). Omit or set `auto` to **auto-detect** laptop/device cameras at startup. |
| **GPIO** | `USE_GPIO` | `1` to enable RPi.GPIO PTZ. |
| **Audio** | `ENABLE_AUDIO` | `0` to disable microphone. Microphones are listed at `/api/v1/audio/detect` for setup. |
| **Wi‑Fi** | `ENABLE_WIFI_SNIFF`, `WIFI_INTERFACE` | Scapy; default interface `wlan0mon`. |
| **ONVIF** | `ONVIF_HOST`, `ONVIF_PORT`, `ONVIF_USER`, `ONVIF_PASS` | PTZ via ONVIF. |
| **Auth** | `FLASK_SECRET_KEY`, `ADMIN_PASSWORD` | Session secret; default admin password. |
| **Auto-login** | `AUTO_LOGIN=1` | Skip login page: frontend auto-logs in as admin (dev/local only). |
| **Retention** | `RETENTION_DAYS` | Delete ai_data, events, recordings older than N days. |
| **Alerts** | `ALERT_SMS_URL`, `ALERT_PHONE` | POST URL and phone for server-triggered SMS. Optional: `ALERT_WEBHOOK_URL` (POST event JSON), `ALERT_MQTT_BROKER` + `ALERT_MQTT_TOPIC` (paho-mqtt). |
| **Zones/lines** | `config.json` | `loiter_zones`, `loiter_seconds`, `crossing_lines`. |
| **YOLO** | `YOLO_MODEL`, `YOLO_DEVICE`, `YOLO_IMGSZ` | Model (default `yolov8n.pt`); device; inference size (default 640). See **docs/YOLO_INTEGRATION.md**. |
| **Stream** | `STREAM_JPEG_QUALITY`, `STREAM_MAX_WIDTH` | MJPEG quality (1–100, default 82); max width for stream (0 = full; 640 = lighter). Recording unchanged. |
| **Emotion** | `EMOTION_BACKEND` | `auto` (default), `deepface`, or `emotiefflib`. TensorFlow-free option: **emotiefflib**. See **docs/EMOTION_INTEGRATION.md**. |
| **React UI** | `USE_REACT_APP=1` | Serve `frontend/dist` at `/` when set. |
| **Scaling** | `REDIS_URL` | Optional; multi-instance WebSocket broadcast. |
| **Session** | `SESSION_TIMEOUT_MINUTES` | Inactivity timeout (default 60). |
| **Lockout** | `LOCKOUT_MAX_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES` | Account lockout after N failed logins (default 5, 15 min). |
| **Audit retention** | `AUDIT_RETENTION_DAYS` | Separate retention for audit_log (0 = never delete). |
| **Password policy** | `PASSWORD_MIN_LENGTH`, `PASSWORD_REQUIRE_DIGIT`, `PASSWORD_REQUIRE_SPECIAL` | Min length 8; require digit/special. |
| **Security** | `STRICT_TRANSPORT_SECURITY`, `CONTENT_SECURITY_POLICY`, `ENFORCE_HTTPS` | HSTS; CSP; redirect HTTP→HTTPS when behind proxy. |
| **MFA** | `ENABLE_MFA=1`, `MFA_ISSUER_NAME` | Optional TOTP (install pyotp); NIST IR 8523 / CJIS 6.0. |

For inference optimization (ONNX/TensorRT/OpenVINO), speech backends (Vosk/Whisper), RTSP tuning, and full config matrix see **docs/TECHNOLOGY_RESEARCH_AND_CONFIG.md**.

### Performance tuning

- **YOLO**: Set `YOLO_DEVICE=0` (or `cuda`) on GPU hosts; use `YOLO_MODEL=yolov8n.pt` for speed (default). Inference uses `YOLO_IMGSZ` (default 640) and `verbose=False`.
- **Stream**: Lower bandwidth with `STREAM_JPEG_QUALITY=75` and `STREAM_MAX_WIDTH=640`; recording stays full resolution.
- **DB**: Indexes and list caps are in place; see **docs/OPTIMIZATION_AUDIT.md** for batch commits, retention, and full recommendations.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard (legacy HTML or React index when `USE_REACT_APP=1`). |
| GET | `/streams` | List of streams (id, name, type, url). |
| GET | `/health` | Liveness `{ status, recording }`. |
| GET | `/health/ready` | Readiness (DB check) for load balancers. |
| GET | `/recording` | Current recording state `{ recording: bool }`. |
| GET | `/video_feed`, `/video_feed/<id>` | MJPEG. |
| GET | `/thermal_feed` | MJPEG thermal. |
| GET | `/get_data` | AI data (params: limit, offset, date_from, date_to, event_type). |
| GET | `/events` | Events (params: limit, offset, camera_id, event_type, severity, acknowledged). |
| POST | `/events` | Create event (body: event_type, camera_id, metadata, severity). |
| POST | `/events/<id>/acknowledge` | Acknowledge (auth). |
| GET | `/export_data` | CSV download (auth: operator/admin). |
| GET | `/recordings` | List recording files (name, size, created_utc). |
| GET | `/recordings/<name>/export` | Download recording with metadata + SHA-256 headers (operator/admin). |
| GET | `/recordings/<name>/manifest` | JSON manifest (metadata + SHA-256) for a recording. |
| POST | `/toggle_recording` | Toggle recording. |
| POST | `/move_camera` | PTZ (body: direction left/right/stop). |
| GET | `/sites`, `/camera_positions` | Map data. |
| POST | `/login`, `GET /me`, `POST /logout` | Auth. |
| GET | `/audit_log` | Audit log (admin). |
| GET | `/audit_log/export` | Audit log CSV with SHA-256 (admin). |
| GET | `/config` | Analytics config (loiter_zones, crossing_lines). |
| PATCH | `/config` | Update analytics config (admin); audited. |
| GET | `/api/v1/analytics/aggregates` | Time-series by event/camera (params: date_from, date_to, camera_id, site_id). |
| POST | `/api/v1/search` | Keyword search over events and AI data (body: q, limit). |
| GET | `/api/v1/system_status` | DB, uptime, recording, per-camera status, **AI superpowers** (yolo, emotion, mediapipe, stream settings). |
| GET | `/api/v1/cameras/detect` | Auto-detect cameras (indices, names, resolution). |
| GET | `/api/v1/audio/detect` | Auto-detect microphones (index, name, sample_rate). |
| GET | `/api/v1/devices` | Unified cameras + microphones for setup/dashboard. |
| WebSocket | `/ws` | New-event notifications. |

---

## Dashboard & UI

- **Legacy**: `templates/index.html` — multi-camera, AI log from `/get_data`, exports. Use when not using React.
- **React**: **Dashboard** (at-a-glance: recording, events today, unacknowledged, streams, health), Live (stream grid + recording/PTZ with tooltips), Events (list + search + real-time toast), **Timeline** (date-range filter, severity badges), **Map** (site selector, camera positions), Analytics, Export (AI data + recordings evidence), Settings. Login required; export and acknowledge respect RBAC. See **docs/GOVERNMENT_STANDARDS_AUDIT.md** § Frontend & UX for best-in-class alignment.

---

## Security & Compliance

- Use env for Twilio, ONVIF, and Flask secret; never commit secrets. See **docs/KEY_MANAGEMENT.md** for key and secrets inventory, storage, and rotation.
- Auth is session-based with bcrypt; set strong `ADMIN_PASSWORD` and `FLASK_SECRET_KEY` in production.
- Run behind HTTPS and a reverse proxy; restrict network as needed.
- Retention and audit log support compliance; document retention purpose (e.g. GDPR/CCPA).
- **Data collection & chain of custody**: AI detections and events are collected only while recording is on. Each row uses a **canonical schema** (consistent columns for export and analytics); centroid and extended attributes refer to the **same primary person** (largest bbox). Exports and recordings use NISTIR 8161–style integrity hashes (per-row and file-level SHA-256); speech is transcribed and logged when audio is enabled (and recording on). See **docs/AUDIT_DATA_COLLECTION.md** and **docs/DATA_COLLECTION_RESEARCH.md** for the full audit and collection improvements.

**Enterprise / government alignment** (see **docs/GOVERNMENT_STANDARDS_AUDIT.md**):
- **Session timeout** (NIST/CJIS), **account lockout** (5 attempts, 15 min), **password policy** (min length, digit, special).
- **Optional TOTP MFA** (NIST IR 8523 / CJIS 6.0): set `ENABLE_MFA=1`, install pyotp; setup in Settings, verify at login.
- **Audit**: failed login includes IP/User-Agent; audit log never deleted by data retention; separate `AUDIT_RETENTION_DAYS`.
- **Export integrity**: CSV export includes SHA-256 in footer and `X-Export-SHA256` header (NISTIR 8161–style chain of custody).
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`; optional HSTS; **CSP via `CONTENT_SECURITY_POLICY`**.
- **HTTPS enforcement**: Set `ENFORCE_HTTPS=1` when behind a reverse proxy (redirects HTTP to HTTPS; respect `X-Forwarded-Proto`).
- **Config change audit**: PATCH `/config` (admin) updates `config.json` and is logged (AU-2).
- **Audit log export**: GET `/audit_log/export` returns CSV with SHA-256 footer and header (AU-9 verifiable export).
- **Video export (NISTIR 8161–style)**: GET `/recordings` lists recordings; GET `/recordings/<name>/export` returns the file with headers **X-Export-UTC**, **X-Operator**, **X-System-ID**, **X-Camera-ID**, **X-Export-SHA256**; GET `/recordings/<name>/manifest` returns JSON with same metadata and hash for chain of custody.

**Encryption at rest**: For regulated or high-assurance deployments, use an encrypted volume (e.g. LUKS) for the application directory containing `surveillance.db` and recording files. Alternatively, configure your orchestrator or vault to provide keys for application-level encryption of the database and recordings; document key lifecycle per ISO 27001 A.8.24.

**FIPS 140-2 / crypto compliance scope**: Hashing (SHA-256) and password hashing (bcrypt) use Python’s standard library and OpenSSL where available. For FIPS 140-2 alignment, use a FIPS-validated OpenSSL build and a Python build linked against it; restrict to approved algorithms (e.g. SHA-256). Document your runtime’s crypto module validation status; application code does not implement custom crypto. TLS for HTTPS should use FIPS-approved ciphers when required (configure at reverse proxy or server).

---

## Deployment

### Docker (recommended for edge / self-hosted)

Deploy with `docker compose up`. Configure via **cameras.yaml** or **.env**. Volumes persist config, snapshots, data, and recordings. Use the **Export** view (or API) for data and recordings.

```bash
# Copy env and set cameras
cp .env.example .env
# Edit .env: CAMERA_SOURCES=rtsp://user:pass@ip/stream, PORT=5000, etc.
# Optional: add config/cameras.yaml (see config/cameras.example.yaml) and config/config.json for analytics

docker compose up --build
# Open http://localhost:5000 (or host:PORT from .env)
```

- **Config**: Use **.env** for cameras (`CAMERA_SOURCES`), auth, YOLO, retention, etc. Optionally put `config/config.json` (loiter zones, lines) and `config/cameras.yaml` (reference for RTSP URLs) in the **config** volume; the image includes `config/cameras.example.yaml`.
- **Volumes**: `vigil_data` (DB and app files), `vigil_recordings` (clips), `vigil_config` (config + cameras.yaml), `vigil_snapshots` (notable behavior screenshots). To use a host folder for config: add `- ./config:/app/config` under `volumes` in `docker-compose.yml`.
- **Data & recordings**: Use the **Export** view in the UI for AI data CSV and recording downloads (chain-of-custody headers). API: `GET /export_data`, `GET /recordings`, `GET /recordings/<name>/export`.
- **GPU (NVIDIA)**: Use a CUDA base image and uncomment the `deploy.resources.reservations.devices` block in `docker-compose.yml`; set `YOLO_DEVICE=0` in `.env`.
- **Adding cameras**: Set `CAMERA_SOURCES` in `.env` (comma-separated indices or RTSP URLs), or follow `config/cameras.example.yaml` and set the same URLs in `.env`. See **Configuration** and **docs/REALTIME_AI_EDGE_AUDIT.md** for multi-RTSP and tuning.

### Production server (gunicorn)

For production, run Flask behind a WSGI server such as **gunicorn** (recommended on Linux) instead of the development server:

```bash
# Install gunicorn
pip install gunicorn

# Serve with 4 workers; set PORT and USE_REACT_APP=1 as needed
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 app:app
```

Use Nginx (or Caddy) as a reverse proxy for HTTPS, static caching, and WebSocket forwarding (`/ws`). See **docs/KEY_MANAGEMENT.md** for secrets and key rotation.

### Production HTTPS (recommended)

For production, serve the app over HTTPS and enforce it so all traffic is encrypted:

1. **Reverse proxy**: Put Nginx or Caddy in front of Flask; terminate TLS at the proxy and set `X-Forwarded-Proto: https` (or equivalent).
2. **Enforce HTTPS**: Set **`ENFORCE_HTTPS=1`** in `.env`. The app will redirect HTTP to HTTPS when it detects a non-secure request (using `X-Forwarded-Proto` when behind a proxy).
3. **HSTS** (optional): Set **`STRICT_TRANSPORT_SECURITY=1`** to send the `Strict-Transport-Security` header.
4. **CSP**: Configure **`CONTENT_SECURITY_POLICY`** if you need a strict Content-Security-Policy.

See **docs/KEY_MANAGEMENT.md** for TLS certificates and key rotation.

### Other

1. **Edge (Pi/Jetson)**: Run `app.py` or `gunicorn` under systemd/supervisord; optionally Nginx in front. Use `USE_REACT_APP=1` and `frontend/dist` to serve the React app from Flask.
2. **SMS**: Run Node `index.js` where Twilio env vars are set; set `ALERT_SMS_URL` to its `/send-sms-alert` for server-triggered alerts.
3. **Scaling**: Multiple cameras via `CAMERA_SOURCES`; multiple sites via `sites` and `camera_positions` tables.

---

## Maintenance & Operations

- **Database**: Back up `surveillance.db`; use retention job for pruning.
- **Recordings**: `recording_*.avi` in app directory; pruned by retention when `RETENTION_DAYS` is set.
- **Thermal**: Use flirpy/Lepton when hardware is present; mock otherwise.
- **Dependency audit (CVE)**: Run **`./scripts/audit-deps.sh`** from the project root to check for known vulnerabilities in Python dependencies. The script uses `pip audit` (Python 3.11+) or installs and runs `pip-audit`. Run this periodically and in CI; see **docs/SYSTEM_RATING.md** and **docs/APP_REVIEW_AND_RATING.md**.

---

## Troubleshooting

- **Flask: "No module named 'RPi.GPIO'"** — Run on a non-Pi machine without GPIO: the app skips GPIO unless `USE_GPIO=1` or ARM. Install only the core deps from `requirements.txt`; optional packages (RPi.GPIO, pyaudio, scapy, etc.) are documented there.
- **Flask: camera open fails** — Ensure a camera is connected or use a RTSP URL in `CAMERA_SOURCES`. On headless servers, use a dummy or RTSP source.
- **React: "Failed to fetch" / blank after login** — Ensure Flask is running on port 5000. In dev, use `npm run frontend` so Vite proxies to Flask. If the frontend is on another host, set `ENABLE_CORS=1` and use `VITE_API_URL=http://flask-host:5000`.
- **Login fails (admin/admin)** — Default user is created on first successful login. If the DB was reset, try again once. Set `ADMIN_PASSWORD` before first run to choose a different default password.
- **Export returns 403** — Export requires operator or admin role. Log in with an account that has the correct role.
- **WebSocket not updating events** — Ensure `flask-sock` is installed and no proxy is stripping WebSocket headers. In dev, the Vite proxy forwards `/ws` with `ws: true`.
- **USE_REACT_APP=1 but still see legacy dashboard** — Run `cd frontend && npm run build` so `frontend/dist` exists, then start Flask with `USE_REACT_APP=1`.
- **Python crashes with SIGSEGV (e.g. on macOS, Python 3.14)** — The app uses thread-local SQLite connections to avoid concurrent access. If you still see crashes in `_sqlite3` or under heavy load, use **Python 3.11 or 3.12** (e.g. `pyenv install 3.12` and run with `python3.12 app.py`).

---

## Further reading

| Doc | Description |
|-----|-------------|
| **docs/OPTIMIZATION_AUDIT.md** | Performance, DB indexes, YOLO/stream tuning, limit caps. |
| **docs/KEY_MANAGEMENT.md** | Secrets inventory, storage, and rotation (FLASK_SECRET_KEY, ADMIN_PASSWORD, ONVIF, Twilio). |
| **docs/SYSTEM_RATING.md** | Security score vs NIST/CJIS; next steps (encryption, TLS, pip audit). |
| **docs/ENTERPRISE_ROADMAP.md** | Best-in-class comparison, scalability path, AI/ML extension points. |
| **docs/GOVERNMENT_STANDARDS_AUDIT.md** | NIST/CJIS alignment, audit, export, frontend UX. |
| **docs/YOLO_INTEGRATION.md** | Model and inference configuration. |
| **docs/DEVICE_AUTODETECT.md** | Camera auto-detection and naming. |
| **docs/AI_DETECTION_LOGS_STANDARDS.md** | AI detection logs alignment with NISTIR 8161, SWGDE, NIST AI 100-4 (UTC, provenance, integrity). |
| **docs/REALTIME_AI_EDGE_AUDIT.md** | Audit vs ultra-fast real-time AI edge stack; Docker, confidence/class UI, ONNX/TensorRT, FPS/latency. |
| **docs/RUNBOOKS.md** | Short runbooks for lost camera, export failed, DB locked, WebSocket, NTP, low disk. |
| **docs/APP_REVIEW_AND_RATING.md** | Application review, rating (78/100), and suggested improvements. |
| **docs/STANDARDS_RATING.md** | Highest-standards rating (80/100) vs NISTIR 8161, SWGDE, CJIS; chain of custody, auth, collection, gaps. |
| **docs/DATA_COLLECTION_RESEARCH.md** | Collection pipeline, canonical row shape, primary-person consistency, height scaling, next steps. |
| **docs/CONFIG_AND_OPTIMIZATION.md** | Env presets for speed, accuracy, production; YOLO, RTSP, MJPEG, gunicorn. |
| **docs/MAPPING_OPTIMIZATION_RESEARCH.md** | Mapping, homography, spatial heatmaps, and multi-camera roadmap. |

**Dependency audit**: Run `./scripts/audit-deps.sh` (or `pip audit` / `pip-audit`) periodically for CVE checks.

---

## License & Disclaimer

Use in compliance with local laws regarding surveillance, privacy, and data retention. No warranty; production use at your own risk.
