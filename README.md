# Jetson AGX Orin Surveillance System

**Enterprise-grade AI-powered surveillance platform** combining real-time video analytics, multi-sensor fusion, PTZ control, and a unified dashboard for security operations. Designed for edge deployment on NVIDIA Jetson AGX Orin and Raspberry Pi with optional cloud alerting.

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

- **Real-time video feeds**: RGB and thermal (mock/FLIR-ready) streams over MJPEG.
- **AI analytics**: Object detection (YOLO), pose estimation (MediaPipe), emotion analysis (DeepFace), OCR (license plates), and thermal signature detection.
- **Multi-sensor fusion**: Video, audio (speech/events), Wi‑Fi device presence (Scapy), and thermal data, persisted to SQLite.
- **PTZ control**: GPIO-driven pan/tilt motor control for camera movement.
- **Recording & export**: On-demand recording (AVI), CSV export of AI data, and dashboard-driven log/snapshot exports.
- **Alerting**: Optional Twilio SMS integration and in-dashboard alert controls.

The backend is a **Flask** application intended for **Raspberry Pi / Jetson** (GPIO, camera). The primary dashboard is a **static HTML/JS** front end with multi-camera views, filtering, and export; an optional **Node.js** service provides SMS preferences and send endpoints.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT (Browser)                                   │
│  index.html / Jetson-dashboard.html  │  Optional: Node.js (port 3000)        │
│  • Multi-camera feeds & snapshots     │  • /sms-preferences, /send-sms-alert │
│  • Logs, filters, exports (ZIP/TXT)  │  • Twilio integration                │
│  • System status, alerts              │                                       │
└───────────────────────────┬─────────────────────────────┬───────────────────┘
                            │ HTTP / MJPEG                 │
                            ▼                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLASK APP (app.py — port 5000)                             │
│  • /video_feed, /thermal_feed (MJPEG streams)                                │
│  • /toggle_recording, /toggle_motion, /move_camera (control)                  │
│  • /get_data, /export_data (AI data), /login                                 │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬──────────────────┐
        ▼                   ▼                   ▼                  ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐
│ Camera (CV2)  │   │ GPIO (RPi)    │   │ SQLite       │   │ Audio / WiFi     │
│ 1280×720      │   │ Motor PTZ     │   │ surveillance │   │ PyAudio, Scapy   │
│ Recording AVI │   │ PWM pin 25     │   │ .db          │   │ (wlan0mon)       │
└───────────────┘   └───────────────┘   └──────────────┘   └──────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AI PIPELINE (background thread, ~10s interval when recording)               │
│  YOLO → objects | MediaPipe → pose | DeepFace → emotion | Tesseract → plate   │
│  Scene (indoor/outdoor), motion event, crowd count, audio event, device MAC,  │
│  thermal signature → INSERT into ai_data                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Flask** serves the web UI and all device/recording/data APIs.
- **Camera** and **thermal** (mock) streams are MJPEG over HTTP.
- **AI pipeline** runs in a daemon thread and writes only when recording is active.
- **SQLite** holds all AI-generated records; CSV export is provided by the Flask app.
- **Node.js** is optional and used only for Twilio SMS (preferences + send).

---

## Features

### 1. Video Capture & Streaming

| Feature | Description |
|--------|-------------|
| **Primary camera** | OpenCV `VideoCapture(0)`, 1280×720, MJPEG stream at `/video_feed`. |
| **Thermal feed** | Mock thermal stream at `/thermal_feed` (80×60 random placeholder; replace with FLIR Lepton SDK for real hardware). |
| **Recording** | Toggle via `/toggle_recording`. When on, frames are written to `recording_<timestamp>.avi` (XVID, 20 fps, 1280×720). |

### 2. AI Analytics (when recording is active)

| Component | Role |
|----------|------|
| **YOLO (Ultralytics)** | Object detection; detected classes and count used for “object” and “crowd_count”. |
| **MediaPipe Pose** | Pose estimation; outputs simplified “Standing” / “Unknown”. |
| **DeepFace** | Emotion analysis on frame; “dominant_emotion” or fallback “Neutral”. |
| **PyTesseract** | OCR on frame (e.g. license plates); sampled probabilistically in current logic. |
| **Scene** | Heuristic: mean pixel intensity &lt; 100 → “Indoor”, else “Outdoor”. |
| **Motion / event** | Placeholder “Motion Detected” / “None” (extensible for real motion logic). |
| **Audio event** | Microphone → Google Speech recognition; result or “None” stored as `audio_event`. |
| **Wi‑Fi devices** | Scapy sniffs on `wlan0mon`; new MACs stored as `device_mac` (one per cycle). |
| **Thermal signature** | Mock: mean of thermal frame &gt; 100 → “Human”, else “None”. |

All results are written to the **SQLite** table `ai_data` (see schema below) every ~10 seconds while recording.

### 3. PTZ (Pan–Tilt–Zoom) Control

- **GPIO (BCM)**: pins 23 (direction A), 24 (direction B), 25 (PWM speed).
- **Endpoint**: `POST /move_camera` with JSON `{ "direction": "left" | "right" | "stop" }`.
- **Behavior**: “left”/“right” set motor direction and 50% duty cycle; “stop” sets duty cycle to 0.

*Note: Requires Raspberry Pi (or compatible) and correct motor wiring.*

### 4. Data Persistence & Export

- **SQLite** database: `surveillance.db`, table `ai_data`:

  - `date`, `time`, `individual`, `facial_features`, `object`, `pose`, `emotion`, `scene`, `license_plate`, `event`, `crowd_count`, `audio_event`, `device_mac`, `thermal_signature`.

- **Flask**:
  - `GET /get_data` → JSON array of all `ai_data` rows.
  - `GET /export_data` → CSV download of full table; filename `ai_data_YYYYMMDD.csv`.

### 5. Authentication (minimal)

- `POST /login` with JSON `{ "username", "password" }` returns `{ "success": true }` if both are non-empty (placeholder; replace with proper auth in production).

### 6. Dashboard (HTML/JS)

- **Multi-camera**: Thermal (FLIR FX34), PTZ Dome (Axis 4K), Low-Light (Sony Alpha 7S III) — placeholder video sources; can be wired to `/video_feed` and `/thermal_feed`.
- **Per-camera**: snapshot from video element, audio mute/unmute, “Export All Data + Snapshots” (JSZip: weekly logs, extended logs, snapshots, video links).
- **System status**: battery, solar, storage, LTE, camera connectivity, firmware, uptime (static/simulated).
- **AI Detection Log**: list of events with “Export AI Detection Log (.txt)”.
- **Alert controls**: “Send SMS Alert”, “Export Extended Logs”.
- **Weekly surveillance logs**: category filters and search; “Export Filtered Logs” (TXT).
- **Extended security logs**: live list with export.
- **Security**: CSRF token (simulated), text sanitization for XSS, safe video path validation, debounced filters.

### 7. SMS Alerting (Node.js, optional)

- **index.js** (Express, port 3000):
  - `POST /sms-preferences`: store `phone` and `preferences` in memory.
  - `POST /send-sms-alert`: send SMS via Twilio (`phone`, `message`).
- Requires Twilio Account SID, Auth Token, and Twilio phone number in env or code (use env in production).

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask, OpenCV, Ultralytics YOLO, DeepFace, MediaPipe, PyTesseract, PyAudio, SpeechRecognition, Scapy, RPi.GPIO, SQLite3 |
| Optional backend | Node.js, Express, Twilio |
| Frontend | HTML5, CSS3, JavaScript, JSZip (exports) |
| Hardware (intended) | Raspberry Pi / Jetson AGX Orin, USB/local camera, FLIR Lepton (thermal), GPIO for PTZ motors, Wi‑Fi adapter (monitor mode for Scapy) |

---

## Installation & Requirements

### Backend (Flask on Pi/Jetson)

1. **System**

   - Raspberry Pi OS or JetPack (Jetson); Python 3.8+.
   - Camera accessible as `/dev/video0` (or adjust `VideoCapture` index).
   - For PTZ: GPIO and motor driver wiring as per BCM pins above.
   - For Wi‑Fi device detection: interface `wlan0mon` in monitor mode.

2. **Python dependencies** (example; versions to be pinned per environment):

   ```bash
   pip install flask opencv-python numpy ultralytics deepface pytesseract mediapipe RPi.GPIO pyaudio SpeechRecognition scapy Pillow
   ```

   - Install Tesseract OCR and (if needed) `libportaudio` for PyAudio.
   - For Jetson, prefer JetPack-provided or documented builds for OpenCV/camera.

3. **Templates**

   - Flask uses `render_template('index.html')`. Place your dashboard `index.html` inside a `templates` directory in the app root:

   ```text
   camera-main/
   ├── app.py
   ├── templates/
   │   └── index.html   # copy from index.html or Jetson-dashboard.html
   └── ...
   ```

4. **Run**

   ```bash
   python app.py
   ```

   - App listens on `0.0.0.0:5000`. Background thread starts automatically for the AI analysis loop.

### Optional: Node.js SMS service

```bash
cd /path/to/camera-main
npm install express cors body-parser twilio
node index.js
```

- Set `accountSid`, `authToken`, `twilioPhone` via environment variables or config (never commit secrets).

### YOLO model

- On first run, Ultralytics will download `yolov8n.pt` if missing. Ensure network access or pre-download the model.

---

## Configuration

| Item | Location | Description |
|------|----------|-------------|
| Camera index | `app.py` | `cv2.VideoCapture(0)` — change for different device. |
| Resolution | `app.py` | `CAP_PROP_FRAME_WIDTH/HEIGHT` (1280×720). |
| Recording format | `app.py` | FourCC `XVID`, 20 fps in `gen_frames()`. |
| Motor pins | `app.py` | `MOTOR_PINS = [23, 24, 25]`, PWM on 25. |
| Wi‑Fi interface | `app.py` | `analyze_wifi()` uses `wlan0mon`. |
| Analysis interval | `app.py` | `time.sleep(10)` in `analyze_frame()`. |
| Twilio | `index.js` | Account SID, Auth Token, Twilio phone number. |
| Dashboard cameras | `index.html` | `config.cameras` and video `src` (e.g. `/video_feed`, `/thermal_feed`). |

---

## API Reference

| Method | Endpoint | Body / Params | Description |
|--------|----------|----------------|-------------|
| GET | `/` | — | Serves dashboard (`index.html`). |
| GET | `/video_feed` | — | MJPEG stream (primary camera). |
| GET | `/thermal_feed` | — | MJPEG stream (thermal mock). |
| POST | `/toggle_recording` | — | Toggle recording; response `{ "recording": bool }`. |
| POST | `/toggle_motion` | `{ "motion": bool }` | Toggle motion state (no backend effect in current code). |
| POST | `/move_camera` | `{ "direction": "left"\|"right"\|"stop" }` | PTZ motor control. |
| GET | `/get_data` | — | JSON array of all `ai_data` rows. |
| GET | `/export_data` | — | CSV download of `ai_data`. |
| POST | `/login` | `{ "username", "password" }` | Placeholder auth; returns `{ "success": bool }`. |
| POST | `/sms-preferences` | `{ "phone", "preferences" }` | (Node) Store SMS preferences. |
| POST | `/send-sms-alert` | `{ "phone", "message" }` | (Node) Send SMS via Twilio. |

---

## Dashboard & UI

- **Primary dashboard**: `index.html` — full-featured (cameras, snapshots, system status, AI log, alerts, weekly/extended logs, filters, search, and exports).
- **Jetson-dashboard.html**: Simpler grid (feeds, system status, AI log, device controls).
- **New Text Document.html**: Alternate combined dashboard and weekly behavior log with category filters and export.

For Flask, use one of these as `templates/index.html`. To use live streams, set video sources to `/video_feed` and `/thermal_feed` (same origin as the Flask server).

---

## Security & Compliance

- **Credentials**: Do not hardcode Twilio or any secrets; use environment variables or a secrets manager.
- **Login**: Current `/login` is a stub; implement proper authentication (e.g. session/JWT) and password hashing before production.
- **Network**: Run Flask and Node behind HTTPS and a reverse proxy in production; restrict `host`/firewall as needed.
- **CSRF**: Dashboard uses a simulated CSRF token; replace with server-issued tokens for state-changing requests.
- **Input/output**: Dashboard sanitizes displayed text and validates video paths; keep server-side validation and encoding for all inputs and exports.
- **Privacy / compliance**: Video, biometric (emotion/pose), and device MAC data may be subject to GDPR, CCPA, or local laws; ensure retention, consent, and disclosure policies are in place.

---

## Deployment

1. **Edge (Pi/Jetson)**  
   - Run `app.py` under a process manager (systemd, supervisord) and optionally put Nginx in front for static files and reverse proxy to Flask.  
   - Ensure camera, GPIO, and (if used) monitor-mode Wi‑Fi are available and permissions set.

2. **SMS service**  
   - Run `index.js` on a server with Twilio credentials; call `/send-sms-alert` from the dashboard or from Flask (e.g. on alert rules).

3. **Scaling**  
   - For multiple cameras or sites, run one Flask instance per device or refactor to support multiple camera indices and per-stream recording/analytics.

---

## Maintenance & Operations

- **Database**: SQLite file `surveillance.db` in the app directory; back up regularly; consider vacuum/rotation for long-running use.
- **Recordings**: AVI files (`recording_*.avi`) are written to the app directory; add a retention or archival policy.
- **Logs**: Application logs are stdout/stderr; redirect to files or a logging service for production.
- **Thermal**: Replace mock thermal stream and `analyze_thermal()` with FLIR Lepton (or equivalent) SDK when hardware is available.
- **Updates**: Keep Ultralytics, OpenCV, and system libraries updated for security and model improvements.

---

## License & Disclaimer

- Use in compliance with local laws regarding surveillance, privacy, and data retention.
- No warranty; use at your own risk. For production, harden authentication, secrets, and deployment as described above.

---

**Summary**: This repository provides an end-to-end surveillance stack: Flask backend for capture, AI, storage, and PTZ; SQLite for analytics data; CSV and dashboard-driven exports; optional Node + Twilio SMS; and a multi-camera dashboard with filtering and export suitable for enterprise-style security operations documentation and control.
