# Vigil — Edge Video Security

**Enterprise-grade AI-powered surveillance** with real-time analytics, NISTIR 8161–style chain of custody, and a React dashboard. Built for edge (Jetson, Raspberry Pi) and self-hosted deployment.

**Standards rating: [85/100](docs/STANDARDS_RATING.md)** — aligned with NISTIR 8161, SWGDE, CJIS, and NIST AI 100-4 for evidence and operations.

### Recent improvements

- **Standards & data quality**: 90+ data-point plan ([PLAN_90_PLUS_DATA_POINTS.md](docs/PLAN_90_PLUS_DATA_POINTS.md)), applied improvements (224×224 DeepFace, centroid smoothing, CLAHE for low-light emotion, MOG2/scene tuning); FRVT disclaimer and OSAC image_type in exports.
- **Security & ops**: `ENFORCE_HTTPS=reject` (403 on HTTP when set); legal hold API; deployment checklist and runbooks.
- **Testing**: Unit tests for integrity hashes and geometry (`tests/`); gait/env script (`scripts/test_gait_and_env.py`); DB cleanup so test runs finish without ResourceWarning.
- **Performance**: Reused CLAHE instance for emotion preprocessing; config and docs in [OPTIMIZATION_AUDIT.md](docs/OPTIMIZATION_AUDIT.md) and [CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md).

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
- [Suggested equipment (low / medium / high end)](#suggested-equipment-low--medium--high-end)
- [Project Structure](#project-structure)
- [Operations](#operations)
- [Development & testing](#development--testing)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
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

**Data flow (high level):** Camera/RTSP → frame ingest → (when recording) YOLO + pose + optional emotion/LPR → motion/loiter/line-cross → SQLite (ai_data, events) + optional recording → React/API/export with chain-of-custody headers.

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

- **Python 3.8+** (3.11 or 3.12 recommended; 3.14+ may hit compatibility issues with some deps).
- **System**: Tesseract (for LPR); camera or RTSP source.
- **React dashboard**: Modern browser (Chrome, Firefox, Safari, Edge); JavaScript enabled.
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
| **Security** | `STRICT_TRANSPORT_SECURITY`, `ENFORCE_HTTPS`, `CONTENT_SECURITY_POLICY` | HSTS; `ENFORCE_HTTPS=1` redirect to HTTPS, `=reject` returns 403. Use behind reverse proxy. |
| **MFA** | `ENABLE_MFA=1`, `MFA_ISSUER_NAME` | TOTP (install pyotp); NIST IR 8523 / CJIS. |
| **Scaling** | `REDIS_URL` | Multi-instance WebSocket broadcast. |

**Data quality (90+):** `EMOTION_CLAHE_THRESHOLD`, `SCENE_VAR_MAX_INDOOR`, `CENTROID_SMOOTHING_FRAMES`, `MOTION_MOG2_VAR_THRESHOLD` — see [docs/CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md) §10 and [docs/PLAN_90_PLUS_DATA_POINTS.md](docs/PLAN_90_PLUS_DATA_POINTS.md).

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
- **Standards rating**: [85/100](docs/STANDARDS_RATING.md) — NISTIR 8161, SWGDE, CJIS, NIST AI 100-4; TLS and legal hold implemented; remaining gap: encryption at rest.

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

## Suggested equipment (low / medium / high end)

Research-backed hardware tiers for running Vigil with different budgets, camera counts, and evidence requirements. **Last audited: 2025–2026.** Pricing is approximate (USD); difficulty reflects setup, networking, and ongoing operations.

### Overview

| Tier | Compute | Cameras | Storage (30-day retention guide) | Est. total (hardware) | Setup difficulty |
|------|--------|---------|-----------------------------------|------------------------|------------------|
| **Low end** | Raspberry Pi 4/5 or refurb PC | 1–4 (1080p–4K) | 0.5–2 TB | $250–$700 | Easy |
| **Medium** | Jetson Orin Nano Super / x86 + GPU | 4–12 (1080p–4K) | 2–8 TB | $900–$2,800 | Moderate |
| **High end** | Server + NVIDIA GPU, NVR-grade | 12–64+ (4K/8K) | 16–80+ TB (RAID) | $4,500–$28,000+ | Advanced |

**Storage note:** 24/7 recording ≈ 6–10 GB/day per 1080p camera, ≈ 20–24 GB/day per 4K (H.265 saves ~50% vs H.264; motion-only can cut usage 60–80%). Add 20–30% buffer. Use [Seagate’s surveillance calculator](https://www.seagate.com/solutions/surveillance/surveillance-storage-calculator/) or similar for exact sizing. See [CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md) for retention and recording settings.

**Planning and environment considerations (often missed):**

| Consideration | Guidance |
|---------------|----------|
| **PoE cable length** | Ethernet max 100 m (328 ft); plan runs **&lt; 90 m (295 ft)** to allow for bends and voltage drop. Use **Cat5e or Cat6** (pure copper preferred; avoid thin/Cu-Al cable). Long runs need a voltage-drop check so cameras get enough power (802.3af ≈ 15W, 802.3at ≈ 30W at device). |
| **Network bandwidth** | Per stream: 1080p ~1–4 Mbps, 4K ~4–16 Mbps (H.265 ~half of H.264). Size switch uplink and LAN for total streams (e.g. 12× 4K ≈ 50–100 Mbps). Prefer wired over WiFi for reliability. |
| **Cooling (edge)** | Raspberry Pi and Jetson throttle when hot (Pi 4 from ~80°C). For 24/7 AI workloads use a **heatsink** (passive) or **heatsink + fan**; avoid enclosed cabinets without airflow. |
| **NDAA / TAA (US government)** | Federal and many state contracts require **NDAA-compliant** (and often **TAA-compliant**) cameras. Common consumer brands (e.g. Hikvision, Dahua, some Reolink) are **not** NDAA-compliant. Use vendors such as Axis, Hanwha, Bosch, Vivotek, or other [NDAA/TAA-listed](https://www.ecfr.gov/current/title-48/chapter-2/subchapter-A/part-204/subpart-204.21) options for government or regulated sites. |
| **Placement and privacy** | Do not record bathrooms, bedrooms, or off-property (e.g. into a neighbor's yard). **Audio** is heavily regulated (wiretapping; one- or two-party consent by state). Use privacy zones and notice where required. See [LEGAL_AND_ETHICS.md](docs/LEGAL_AND_ETHICS.md). |
| **Firmware and hardening** | IP cameras and NVRs often have CVEs; **keep firmware updated** and **isolate camera VLAN** from general LAN. Change default passwords; restrict admin access. |

---

### Low-end build

**Goal:** Proof of concept, home, or small site (1–4 cameras) with basic AI (YOLO nano / YOLO11n, motion, optional LPR). Minimal cost and power.

| Component | Suggested | Approx. price (2025–2026) | Notes |
|-----------|------------|---------------------------|--------|
| **Compute** | Raspberry Pi 4 (4GB) or Pi 5 (4–8GB) | $55–$95 | Pi 4: ~5–7 FPS YOLO nano; Pi 5: 2–3× CPU, runs YOLO11; use `YOLO_DEVICE=cpu`, `YOLO_IMGSZ=640`, `yolov8n.pt` or `yolo11n.pt`. Pi 5 16GB has seen large price increases (~$205); 4–8GB usually better value. For 24/7 AI: add heatsink or fan (see cooling above). |
| **Alternative** | Refurbished SFF PC (e.g. Dell OptiPlex, 8GB RAM) | $100–$200 | More headroom than Pi; add low-profile GPU later if needed. |
| **Cameras** | 1–4× 1080p–4K RTSP/ONVIF (Reolink RLC-510A, RLC-810A 4K ~$89; Amcrest IP2M-841, IP8M-2779EW 4K ~$120) | $30–$130 each | Reolink: lowest cost, good RTSP/ONVIF. Amcrest: stronger ONVIF, 3‑yr warranty, US support. Prefer PoE over WiFi. |
| **Network** | 5–8 port unmanaged switch or 8-port PoE (802.3af/at) | $25–$90 | PoE switch if using PoE cameras; else router ports or WiFi. Keep cable runs &lt; 90 m; prefer Cat5e/Cat6. |
| **Storage** | USB SSD or single HDD (0.5–2 TB) | $45–$90 | SD card not recommended for recordings; use external or NAS. |

**Pros:** Very low cost; low power; good for learning and testing; fits Vigil’s edge story (Pi/Jetson in docs).  
**Cons:** Limited AI throughput (low FPS); few simultaneous streams; no redundancy; not suitable for 24/7 evidence-grade or many cameras.

**Setup difficulty: Easy** — Single device, minimal networking. Follow [Quick Start](#quick-start); set `CAMERA_SOURCES` to RTSP URLs or indices. Expect 2–4 hours for first working setup.

---

### Medium-end build

**Goal:** Reliable 4–12 camera deployment with real-time AI (YOLO, pose, optional emotion/LPR), event and recording retention, and optional evidence-style export.

| Component | Suggested | Approx. price (2025–2026) | Notes |
|-----------|------------|---------------------------|--------|
| **Compute** | NVIDIA Jetson Orin Nano Super Developer Kit | $249 | 67 TOPS; TensorRT; `JETSON_MODE=1`, YOLO TensorRT export; 4+ camera inputs. Ideal edge AI for Vigil. Existing Orin Nano 8GB can get “Super” via software update. Use adequate cooling for 24/7. |
| **Alternative** | x86 mini PC or desktop (i5/R5, 16GB RAM) + NVIDIA GPU (RTX 4060 8GB or RTX 4070 12GB) | $450–$1,000 | RTX 4070 ~2× AI throughput of 4060; better for multi-stream YOLO/emotion. Run Docker or bare metal. |
| **Cameras** | 4–12× 1080p–4K PoE, ONVIF (Reolink RLC-810A 4K ~$89; Amcrest 4K ~$120; Dahua/Hikvision entry $200+) | $90–$220 each | 4K increases storage and bandwidth; 1080p often sufficient for analytics. |
| **Network** | 8–16 port PoE switch (802.3af/at, 45–300W budget) | $100–$320 | Ubiquiti USW-Lite-16-PoE ~$199, USW-16-PoE ~$299; TP-Link Omada or managed for VLANs. Size power budget for all cameras; plan bandwidth (e.g. 12× 4K ≈ 50–100 Mbps). |
| **Storage** | 2–8 TB NAS or internal HDD/SSD (surveillance-rated preferred) | $85–$280 | Plan for 30-day retention; H.265 and motion-only reduce needs. See storage note above. |
| **Optional** | Nginx reverse proxy, UPS | $0 (software) + $80–$160 | Recommended for production; see [Security & Compliance](#security--compliance). |

**Pros:** Real-time AI at edge (Jetson) or on GPU; TensorRT/ONNX; scalable to 12 cameras; supports chain-of-custody export and retention.  
**Cons:** Higher cost and setup than low-end; single-server failure still impacts whole system; no built-in RAID unless you add NAS/server.

**Setup difficulty: Moderate** — Network design (VLANs, PoE), YOLO/TensorRT export on Jetson, gunicorn + reverse proxy. Expect 1–2 days for a stable, documented setup.

---

### High-end / enterprise build

**Goal:** 24/7 evidence-grade operation, 12–64+ channels, long retention, redundancy, and alignment with NISTIR 8161 / CJIS-style practices (chain of custody, audit, legal hold).

| Component | Suggested | Approx. price (2025–2026) | Notes |
|-----------|------------|---------------------------|--------|
| **Compute** | Server: 8–16 core Xeon/EPYC or high-end desktop (i7/i9, Ryzen 9), 64–128 GB RAM | $1,300–$4,200 | Run Vigil + gunicorn; optional Redis for multi-instance WebSocket. |
| **GPU** | NVIDIA RTX 4070 (12GB) or RTX 4080 / A2000 / L40 (1–2 cards) for YOLO/emotion/pose at scale | $500–$2,600 | RTX 4070 preferred over 4060 for multi-stream AI (~2× throughput); TensorRT/ONNX; use yolov8s/m for accuracy. |
| **NVR/appliance** | Optional 64-ch NVR: Hikvision DS-9664NI-M8 (8K), DS-7764NI-M4; Milesight MS-N8064-G (~$1,400–$1,700 no HDD) | $700–$3,200+ | 320–640 Mbps incoming; 8+ SATA, RAID; use for ingest or alongside Vigil server. |
| **Cameras** | 12–64× 4K/8K ONVIF, NDAA/TAA-compliant if required (Axis, Hanwha, Bosch, Vivotek; Hikvision/Dahua not NDAA) | $200–$650+ each | Enterprise: WDR, on-camera analytics, PoE+; plan 320–400 Mbps for 64× 4K. Keep firmware updated; use camera VLAN. |
| **Network** | 24–48 port PoE+ switch, 10 GbE uplink; optional second switch for redundancy | $420–$1,300 | Managed; VLANs for cameras vs. management; 30W per port for PTZ/heaters. |
| **Storage** | RAID 5/6/60, 16–80+ TB (surveillance HDDs, e.g. Seagate SkyHawk), hot-swap bays | $850–$4,200+ | Redundancy and growth; 30–90 day retention at 4K; H.265 reduces footprint. |
| **Other** | UPS, dual PSU, encrypted volume (LUKS), NTP, backup for DB and config | $220–$1,100 | See [RUNBOOKS.md](docs/RUNBOOKS.md), [KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md), [BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](docs/BEST_PATH_FORWARD_HIGHEST_STANDARDS.md). |

**Pros:** High channel count; redundancy and retention; supports incident bundles, legal hold, and audit; meets higher bar for evidence and compliance.  
**Cons:** Significant cost and expertise; deployment and hardening (HTTPS, MFA, runbooks) required; ongoing ops and dependency/security audits (e.g. `pip audit`, [INSTALL_AUDIT.md](docs/INSTALL_AUDIT.md)).

**Setup difficulty: Advanced** — Rack/network design, RAID, TLS, MFA, backup/restore, and runbooks. Plan 1–2 weeks for design, install, and documentation. Professional installation for cabling and camera placement typically **$125–$450 per camera** (labor ~$80–$200/camera; 6–8 hours for a 4-camera job common).

---

### Summary and references

- **Vigil-specific:** Use `JETSON_MODE=1` and TensorRT on Jetson; see [YOLO_INTEGRATION.md](docs/YOLO_INTEGRATION.md). For production, follow [.env.example](.env.example) “highest standards” block and [STANDARDS_APPLIED.md](docs/STANDARDS_APPLIED.md).
- **Storage:** 1080p ≈ 6–10 GB/day/cam, 4K ≈ 20–24 GB/day/cam (24/7); H.265 ~50% savings vs H.264; motion-only 60–80% reduction. Add 20–30% buffer. Use [Seagate’s surveillance calculator](https://www.seagate.com/solutions/surveillance/surveillance-storage-calculator/) for exact sizing.
- **Evidence and compliance:** High-end builds should implement encryption at rest, ENFORCE_HTTPS, fixity/checksums, and retention policies as in [AI_DETECTION_LOGS_STANDARDS.md](docs/AI_DETECTION_LOGS_STANDARDS.md) and [RUNBOOKS.md](docs/RUNBOOKS.md).

**Quick planning checklist:** PoE run &lt; 90 m, Cat5e/Cat6 • Switch power budget and uplink bandwidth for all streams • Edge cooling (heatsink/fan) for 24/7 • NDAA/TAA if government or regulated • Camera placement and audio rules per [LEGAL_AND_ETHICS.md](docs/LEGAL_AND_ETHICS.md) • Camera VLAN and firmware updates.

Pricing and product names are indicative (audit 2025–2026); verify with vendors and regional availability. Labor and licensing (e.g. Windows, support contracts) are not included in hardware estimates.

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
| `tests/` | Unit tests (integrity hash, geometry); run: `python -m unittest discover -s tests` or `python -m pytest tests/`. |
| `run.sh` | Start backend; use .venv if present; build React if USE_REACT_APP=1 and dist missing. |

---

## Operations

- **Database**: Back up `surveillance.db` (e.g. `sqlite3 surveillance.db ".backup backup.db"` or copy the file while the app is idle). Retention job prunes ai_data, events, and recordings by `RETENTION_DAYS`; audit log uses `AUDIT_RETENTION_DAYS` (0 = keep forever).
- **Recordings**: Stored in app directory or `RECORDINGS_DIR`; pruned by retention; export via UI or API. Back up the recordings directory for evidence; use manifest and checksums from export endpoints.
- **Monitoring & health**: `GET /health` (liveness), `GET /health/ready` (DB reachable), `GET /api/v1/system_status` (DB, uptime, recording state, cameras, AI status). Use these for load balancers and alerting.
- **Dependency audit**: Run `./scripts/audit-deps.sh` (or `pip-audit` in venv) for CVE checks; recommended for production (BEST_PATH_FORWARD Phase 1). [docs/SYSTEM_RATING.md](docs/SYSTEM_RATING.md).
- **Runbooks**: [docs/RUNBOOKS.md](docs/RUNBOOKS.md) — lost camera, export failed, DB locked, WebSocket, NTP, low disk, evidence/OSAC.
- **Standards applied**: The project follows [docs/BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](docs/BEST_PATH_FORWARD_HIGHEST_STANDARDS.md) and [docs/STANDARDS_APPLIED.md](docs/STANDARDS_APPLIED.md) for evidence, privacy, and security. Data quality roadmap: [docs/PLAN_90_PLUS_DATA_POINTS.md](docs/PLAN_90_PLUS_DATA_POINTS.md).

---

## Development & testing

- **Environment**: Use a virtual environment (e.g. `python3 -m venv .venv && source .venv/bin/activate`); install with `pip install -r requirements.txt`. Optional deps: [requirements-optional.txt](requirements-optional.txt).
- **Gait & env**: `python scripts/test_gait_and_env.py` — checks `ENABLE_GAIT_NOTES`, `_gait_notes_from_pose`, and optional `--live` HTTP health/system_status.
- **Unit tests**: `python -m unittest discover -s tests` or `pytest tests/` (if pytest installed). Covers integrity hashes and geometry (point-in-polygon, segment/line). Run from repo root with venv active.
- **React dev**: Terminal 1: `./run.sh`. Terminal 2: `cd frontend && npm run dev`. Open http://localhost:5173 (Vite proxies to Flask).
- **Codebase**: Main backend is `app.py` (Flask, analysis loop, DB, WebSocket); config in `config.json` and env; see [Project Structure](#project-structure) and [docs/](docs/).

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

## Contributing

- **Tests**: Add or extend tests in `tests/`; run `python -m unittest discover -s tests` before pushing. Use `scripts/test_gait_and_env.py --live` when the backend is running for HTTP checks.
- **Standards**: New features that touch evidence, privacy, or security should align with [STANDARDS_APPLIED.md](docs/STANDARDS_APPLIED.md) and [BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](docs/BEST_PATH_FORWARD_HIGHEST_STANDARDS.md). Document config in [.env.example](.env.example) and [CONFIG_AND_OPTIMIZATION.md](docs/CONFIG_AND_OPTIMIZATION.md) where relevant.
- **Issues & PRs**: Open issues and pull requests on the [GitHub repository](https://github.com/Bwilkie91/camera); for bugs, include Python/env version and steps to reproduce.

---

## Documentation

The `docs/` folder contains 40+ guides grouped below. Start with [STANDARDS_APPLIED.md](docs/STANDARDS_APPLIED.md) and [STANDARDS_RATING.md](docs/STANDARDS_RATING.md) for the project’s standards posture.

### Standards & audit

- [STANDARDS_APPLIED.md](docs/STANDARDS_APPLIED.md) — **Project commitment**: best path integrated and applied going forward.
- [BEST_PATH_FORWARD_HIGHEST_STANDARDS.md](docs/BEST_PATH_FORWARD_HIGHEST_STANDARDS.md) — Phased roadmap to 90+ (config → data quality → security → optional).
- [PLAN_90_PLUS_DATA_POINTS.md](docs/PLAN_90_PLUS_DATA_POINTS.md) — Plan to bring each data point to 90+ with enterprise/LE/journal research and phased implementation.
- [DATA_POINT_ACCURACY_RATING.md](docs/DATA_POINT_ACCURACY_RATING.md) — Per–data-point accuracy (1–100), improvements, and applied changes.
- [STANDARDS_RATING.md](docs/STANDARDS_RATING.md) — Highest-standards rating (85/100), criteria, gaps.
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
