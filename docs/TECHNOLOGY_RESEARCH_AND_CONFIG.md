# Technology Research & Configuration Guide

High-grade research on **technologies to add** or **improve configuration** of existing ones in the Vigil edge surveillance stack. Includes citations, trade-offs, and a configuration matrix for deployment.

---

## 1. Object detection: inference optimization (add/improve)

### Current

- **Ultralytics YOLO** (YOLOv8/v9/v10/YOLO11/YOLO26) via Python API; `YOLO_MODEL`, `YOLO_DEVICE`, `YOLO_IMGSZ`, `YOLO_CONF` in env.
- Default PyTorch inference; GPU when `YOLO_DEVICE=0` (CUDA).

### Research summary

| Technology | Use case | Speed vs PyTorch | Config / integration |
|------------|---------|------------------|----------------------|
| **ONNX** | Cross-platform, CPU/GPU via ONNX Runtime | Up to ~3× CPU | `model.export(format='onnx')`; load with `onnxruntime`; same API surface. |
| **TensorRT** | NVIDIA GPU (Jetson, desktop) | Up to ~5× GPU | `model.export(format='engine')`; Ultralytics auto-detects Jetson; set `YOLO_MODEL` to `.engine` path. |
| **OpenVINO** | Intel CPU/GPU/NPU | Up to ~3× CPU, Intel GPU | `model.export(format='openvino')`; device `intel:cpu`, `intel:gpu`, `intel:npu`. |

**References**

- [Ultralytics Export](https://docs.ultralytics.com/modes/export/) — ONNX, TensorRT, OpenVINO.
- [Ultralytics TensorRT](https://docs.ultralytics.com/integrations/tensorrt) — FP16/INT8, workspace.
- [Ultralytics OpenVINO](https://docs.ultralytics.com/integrations/openvino) — Intel devices.
- [Ultralytics Jetson guide](https://docs.ultralytics.com/guides/nvidia-jetson/) — YOLO26 on JetPack 6/7.

### Recommended configuration (add)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `YOLO_EXPORT_FORMAT` | Prefer loaded format: `torch`, `onnx`, `engine`, `openvino` | (auto from file) | When set, app can prefer loading `.onnx`/`.engine`/`.openvino` if present. |
| `YOLO_OPENVINO_DEVICE` | OpenVINO device: `intel:cpu`, `intel:gpu`, `intel:npu` | `intel:cpu` | Only when using OpenVINO export. |
| `YOLO_TENSORRT_FP16` | Use FP16 when exporting/using TensorRT (1/0) | `1` | Jetson/Ampere+. |

**Implementation note:** Ultralytics already loads by path; use a `.onnx` or `.engine` path as `YOLO_MODEL` to get optimized inference. Optional: at startup, if `YOLO_EXPORT_FORMAT=onnx` and `YOLO_MODEL=yolov8n.pt`, look for `yolov8n.onnx` and use it when present.

---

## 2. Configuration management: validation and schema (improve)

### Current

- **.env** for secrets and tunables (Flask, YOLO, cameras, etc.); no schema.
- **config.json** for analytics (loiter zones, crossing lines); loaded with `json.load`, no validation.
- **config/cameras.example.yaml** is reference only; app reads cameras from `CAMERA_SOURCES` (comma-separated) only.

### Research summary

- **Pydantic Settings** (`pydantic-settings`): type-safe env with `BaseSettings`, `Field()`, `env_prefix`, `.env` support, validation. Used by FastAPI and many production Python apps.
- **YAML + Pydantic**: Define a Pydantic model for YAML structure; validate on load for clear errors and self-documenting config.
- **Best practice**: Single source of truth per concern (env for deployment/secrets, YAML/JSON for structured app config); validate at startup.

**References**

- [Pydantic Settings](https://docs.pydantic.dev/latest/api/pydantic_settings/) — env, secrets, validation.
- [Validating YAML with Pydantic](https://betterprogramming.pub/validating-yaml-configs-made-easy-with-pydantic-594522612db5).

### Recommended configuration (improve)

| Change | Purpose |
|--------|--------|
| **CONFIG_DIR** | Already used for `config.json` override; document and support `config/cameras.yaml` when present. |
| **Optional Pydantic** | Add optional `pydantic-settings` for a typed “app settings” subset (e.g. YOLO_IMGSZ, ANALYZE_INTERVAL_SECONDS) with bounds; fallback to current `os.environ.get` if not installed. |
| **config.json schema** | Document required shape (loiter_zones, loiter_seconds, crossing_lines); optionally validate with a small Pydantic model or JSON Schema. |

No new env vars strictly required; improvement is validation and optional cameras YAML.

---

## 3. Speech-to-text: offline and privacy (add/improve)

### Current

- **Google Speech Recognition** (cloud) via `SpeechRecognition` + `recognize_google()`; requires internet and sends audio to Google.
- Controlled by `ENABLE_AUDIO`; transcription written to `ai_data` only when recording is on and `capture_audio` is true.

### Research summary

| Technology | Offline | Latency | Accuracy | Resource use | Best for |
|------------|--------|---------|----------|--------------|----------|
| **Vosk** | Yes | Low (streaming) | Good | Light (~50 MB model) | Edge, Pi/Jetson, privacy. |
| **Whisper (local)** | Yes (after model download) | Higher (batch) | Very good | Heavier (e.g. base/small) | High accuracy, optional GPU. |
| **Google (current)** | No | Low | Very good | N/A (cloud) | When internet and cloud are acceptable. |

**References**

- [Vosk](https://alphacephei.com/vosk/) — offline, 20+ languages, streaming; `pip install vosk`.
- [OpenAI Whisper](https://github.com/openai/whisper) — local; cache model in `~/.cache/whisper/` for offline.
- [Vosk vs Whisper (comparison)](https://medium.com/@alexis.orthodox/two-paths-to-perfect-transcription-local-vosk-vs-cloud-whisper-ef0e83925e77).

### Recommended configuration (add)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `SPEECH_BACKEND` | `google` \| `vosk` \| `whisper` | `google` | When `vosk`/`whisper`, use local models; no API key. |
| `VOSK_MODEL_PATH` | Path to Vosk model dir (e.g. `models/vosk-model-en`) | (none) | Required if `SPEECH_BACKEND=vosk`. |
| `WHISPER_MODEL` | Whisper size: `tiny`, `base`, `small`, `medium`, `large` | `base` | Larger = better accuracy, more CPU/GPU. |

**Implementation note:** Keep current Google path as default; add a thin adapter: `get_audio_event()` calls either Google, Vosk, or Whisper based on `SPEECH_BACKEND`. Vosk fits the existing “continuous listener” pattern; Whisper can run on the last N seconds of audio each cycle.

---

## 4. RTSP and camera streams: robustness (improve)

### Current

- **OpenCV `VideoCapture`** with RTSP URLs in `CAMERA_SOURCES`; reconnection not explicit; OpenCV can hang on disconnect.

### Research summary

- **GStreamer**: Bus callbacks and pipeline state (NULL → reconnect → PLAY) give proper disconnect detection and recovery; recommended for production RTSP.
- **FFmpeg**: Alternative backend for `VideoCapture` (e.g. `cv2.CAP_FFMPEG`) or separate decode; can add timeout/reconnect in a wrapper.
- **OpenCV limitation**: [Known](https://forum.opencv.org/t/opencv-python-videocapture-read-does-not-return-false-when-rtsp-connection-is-interrupted/16952): `read()` may not return False on RTSP drop; use timeout + reconnect loop or GStreamer.

**References**

- [GStreamer RTSP reconnection](https://stackoverflow.com/questions/77264691/handling-connection-errors-and-resuming-streaming-in-gstreamer-rtsp-pipeline).
- [NVIDIA DeepStream RTSP](https://forums.developer.nvidia.com/t/how-to-turn-on-off-camera-when-the-internet-connection-or-rtsp-server-is-unstable-using-gstreamer-and-python/236756).

### Recommended configuration (improve)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `RTSP_CAP_BACKEND` | OpenCV backend: `opencv`, `ffmpeg`, `gstreamer` | (OpenCV default) | `cv2.CAP_FFMPEG` for FFmpeg; GStreamer needs pipeline string. |
| `RTSP_RECONNECT_SEC` | Seconds before treating stream as dead and reconnecting | `15` | Use with a watchdog thread or read timeout. |
| `RTSP_TIMEOUT_MS` | Timeout per frame read (ms); 0 = no change | `0` | Some backends support; avoids indefinite hang. |

**Implementation note:** Document in README that for unstable RTSP, consider GStreamer or a wrapper with timeout + reconnect. Optional: small helper that re-creates `VideoCapture` when no frame for `RTSP_RECONNECT_SEC` seconds.

---

## 5. NVIDIA Jetson and TensorRT (add/improve)

### Current

- `YOLO_DEVICE=0` uses CUDA when available; no TensorRT-specific path.

### Research summary

- **Jetson + TensorRT**: Export YOLO to `.engine` (or ONNX then build engine); 2–5× faster than PyTorch on same hardware.
- **JetPack 6/7**: Official Ultralytics guides for [Jetson](https://docs.ultralytics.com/guides/nvidia-jetson/) and [DeepStream](https://docs.ultralytics.com/guides/deepstream-nvidia-jetson/); YOLO26 supported.
- **FP16**: Default on Jetson; INT8 with calibration for further speed.

### Recommended configuration (add)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `YOLO_TENSORRT_WORKSPACE_MB` | TensorRT workspace size (MB) when building engine | `4` | Increase for large models. |
| `JETSON_MODE` | Set `1` on Jetson to auto-tune defaults (e.g. smaller imgsz, FP16) | `0` | Optional convenience. |

**Implementation note:** Best approach is to pre-export on Jetson: `yolo export model=yolov8n.pt format=engine device=0`, then set `YOLO_MODEL=yolov8n.engine`. Document in YOLO_INTEGRATION.md and README.

---

## 6. ONVIF discovery (add)

### Current

- ONVIF PTZ when `ONVIF_HOST`/credentials set; no discovery.

### Research summary

- **WS-Discovery**: ONVIF uses WS-Discovery for device discovery on the LAN.
- **Libraries**: `WSDiscovery` (PyPI), `python-ws-discovery`, or `pyonvif` for ONVIF-focused discovery.
- **Use case**: “Discover cameras” in UI or CLI to list ONVIF devices and optionally pre-fill RTSP URLs or ONVIF_HOST.

**References**

- [WSDiscovery (PyPI)](https://pypi.org/project/WSDiscovery/) — Python 3.9–3.13.
- [pyonvif](https://github.com/maxbelyanin/pyonvif) — ONVIF + discovery.

### Recommended configuration (add)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `ONVIF_DISCOVERY_TIMEOUT_SEC` | Timeout for ONVIF discovery when using “Detect cameras” (or API) | `5` | Used by discovery API only. |

**Implementation note:** Optional dependency; add `GET /api/v1/cameras/onvif_discover` that runs WS-Discovery and returns device list (and optionally RTSP/media URLs). Current `GET /api/v1/cameras/detect` can remain for OpenCV indices; ONVIF discover is an extra option.

---

## 7. Events and alerts: MQTT and webhooks (add)

### Current

- Events table + WebSocket push; optional `ALERT_SMS_URL` + `ALERT_PHONE` for SMS.

### Research summary

- **MQTT**: Common in IoT and NOC/SOC for event streaming; lightweight; brokers (Mosquitto, HiveMQ, cloud).
- **Generic webhook**: POST event payload to a configurable URL; enables Zapier, Slack, PagerDuty, custom handlers.

**References**

- REALTIME_AI_EDGE_AUDIT.md (this repo) — “MQTT / webhook for events”.

### Recommended configuration (add)

| Env var | Description | Default | Notes |
|---------|-------------|---------|--------|
| `ALERT_WEBHOOK_URL` | POST event JSON here on motion/loiter/line_cross (in addition to SMS if set) | (none) | Body: `{ "event_type", "camera_id", "timestamp_utc", "metadata", ... }`. |
| `ALERT_MQTT_BROKER` | MQTT broker URL (e.g. `tcp://localhost:1883`) | (none) | When set, publish events to a topic (e.g. `vms/events`). |
| `ALERT_MQTT_TOPIC` | MQTT topic for events | `vms/events` | |
| `ALERT_MQTT_CLIENT_ID` | MQTT client id | `vigil` | |

**Implementation note:** In `_trigger_alert()`, if `ALERT_WEBHOOK_URL` is set, `requests.post(url, json=payload, timeout=5)`. If `ALERT_MQTT_BROKER` is set, optional `paho-mqtt` publish (dependency optional).

---

## 8. Configuration matrix (quick reference)

| Area | Current config | Add / improve |
|------|----------------|----------------|
| **YOLO** | YOLO_MODEL, YOLO_DEVICE, YOLO_IMGSZ, YOLO_CONF | YOLO_EXPORT_FORMAT, YOLO_OPENVINO_DEVICE, YOLO_TENSORRT_FP16, YOLO_TENSORRT_WORKSPACE_MB, JETSON_MODE |
| **Config** | .env, config.json, CONFIG_DIR | Validate config.json; optional cameras.yaml; optional Pydantic |
| **Speech** | ENABLE_AUDIO | SPEECH_BACKEND, VOSK_MODEL_PATH, WHISPER_MODEL |
| **RTSP** | CAMERA_SOURCES | RTSP_RECONNECT_SEC, RTSP_TIMEOUT_MS, RTSP_CAP_BACKEND (doc) |
| **ONVIF** | ONVIF_HOST, ONVIF_USER, ONVIF_PASS | ONVIF_DISCOVERY_TIMEOUT_SEC; optional discovery API |
| **Alerts** | ALERT_SMS_URL, ALERT_PHONE | ALERT_WEBHOOK_URL, ALERT_MQTT_BROKER, ALERT_MQTT_TOPIC, ALERT_MQTT_CLIENT_ID |

---

## 9. Implementation priority

1. **High value, low effort**: Document existing env in one place; add `.env.example` entries for YOLO export (path to .onnx/.engine), SPEECH_BACKEND/VOSK_MODEL_PATH/WHISPER_MODEL, ALERT_WEBHOOK_URL, ALERT_MQTT_*; optional code for webhook and MQTT in `_trigger_alert()`.
2. **High value, medium effort**: Optional cameras from `config/cameras.yaml` when present (and CONFIG_DIR); schema/doc for config.json.
3. **Medium value**: Vosk/Whisper adapter behind `SPEECH_BACKEND`; RTSP reconnect watchdog; ONVIF discovery API.
4. **Later**: Pydantic Settings for a subset of env; GStreamer-based RTSP pipeline; TensorRT build script for Jetson.

This document should be updated as options are implemented or new research (e.g. new YOLO export formats or speech models) becomes relevant.
