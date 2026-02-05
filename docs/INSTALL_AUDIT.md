# Install & dependency audit

Summary of what is installed and what is optional.

## Core (required)

From `requirements.txt`:

- **Flask** — web server, API, sessions
- **flask-sock** — WebSocket
- **python-dotenv** — .env loading
- **bcrypt** — password hashing
- **opencv-python** — video capture, MJPEG, recording
- **numpy**, **Pillow** — image handling
- **pandas** — exports, analysis
- **ultralytics** — YOLO object detection
- **pytesseract** — LPR (license plate)
- **mediapipe** — pose estimation

## Optional (install with `pip install -r requirements-optional.txt`)

| Package | Purpose | Env / config |
|--------|---------|---------------|
| **PyYAML** | Cameras from `config/cameras.yaml` | `CAMERA_SOURCES=yaml` |
| **PyAudio** | Microphone capture | `ENABLE_AUDIO=1` |
| **SpeechRecognition** | Google speech-to-text | `ENABLE_AUDIO=1` |
| **redis** | Multi-instance WebSocket | `REDIS_URL` |
| **pyotp** | TOTP MFA | `ENABLE_MFA=1` |
| **onvif-zeep** | ONVIF PTZ | `ONVIF_HOST`, etc. |
| **paho-mqtt** | MQTT alerts | `ALERT_MQTT_BROKER` |
| **pip-audit** | CVE check | Run `pip audit` |

## Not installed by default (device-specific or heavy)

| Package | Reason |
|--------|--------|
| **RPi.GPIO** | Raspberry Pi / Jetson only |
| **flirpy** | FLIR Lepton thermal (Jetson/hardware) |
| **scapy** | Wi‑Fi monitor (optional; may need libpcap) |
| **deepface** | TensorFlow; use **emotiefflib** for TF-free emotion |
| **emotiefflib** | Uncomment in requirements-optional if desired |

## Frontend

```bash
cd frontend && npm install
```

## Dashboard (Plotly Dash)

```bash
pip install -r dashboard/requirements.txt
```

## Proactive pipeline

```bash
pip install -r requirements-proactive.txt
```

## Security audit

```bash
python3 -m pip_audit
# or
./scripts/audit-deps.sh
```

(Pip’s built-in `pip audit` is not available in all pip versions; use the `pip-audit` package as above.)

## PyAudio (optional audio)

**PyAudio** needs the system PortAudio library. On macOS with Homebrew:

```bash
brew install portaudio
pip install PyAudio
```

Without this, `pip install -r requirements-optional.txt` will skip PyAudio; other optional packages install normally.

## UI: Clear data cache (audit)

The React UI exposes **Clear data cache** in the top bar and in the main nav. This clears **client-side cached data only** (React Query cache); charts, events, and lists refetch from the server. **Server data (recordings, ai_data, events) is not deleted.** For actual retention/deletion, use backend retention (e.g. `RETENTION_DAYS`) or admin tools. Label and confirmation dialog are audit-friendly; button uses `data-action="clear-data-cache"` and `aria-label` for accessibility.

## Configuration and optimization

After installing, apply recommended settings and presets: see **docs/CONFIG_AND_OPTIMIZATION.md**. Covers Flask/Gunicorn, YOLO, RTSP/MJPEG, SQLite, AI interval/batch, frontend build, dashboard polling, and security hardening.

## Quick “install all optional” (Mac/Linux)

```bash
pip install -r requirements.txt
pip install -r requirements-optional.txt   # PyAudio may fail without portaudio
pip install SpeechRecognition redis pyotp onvif-zeep paho-mqtt  # if PyAudio failed
cd frontend && npm install
npm install   # root, for SMS/Express)
```
