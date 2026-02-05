# Real-Time AI Edge Stack — Audit & Inspiration

This document audits the current Vigil Edge Video Security app against a **production-ready, ultra-fast real-time AI analysis system** (multi-RTSP, YOLO/ONNX/TensorRT, Docker, modern GUI). It lists gaps and improvements inspired by that reference design.

---

## 1. Reference System (Target Profile)

- **Backend**: Docker Compose; fast object detection (YOLOv8n / YOLOv10n / RT-DETR); ONNX/TensorRT (NVIDIA), OpenVINO (Intel), CPU fallback; OpenCV + GStreamer/FFmpeg for RTSP; annotated stream (WebRTC/MJPEG/HLS); optional events + webhook/MQTT.
- **Frontend**: React + TypeScript + Vite; dark dashboard; grid of live feeds (2×2, 3×3, fullscreen); bounding boxes + labels; sidebar: RTSP URLs, detection on/off, **confidence threshold slider**, **detection class filter**, FPS/latency.
- **Goals**: &lt;200ms end-to-end latency; self-hosted; edge/low-power (Jetson, mini-PC, CPU-only).

---

## 2. Current App vs Reference

| Area | Reference | This app (current) | Gap / improvement |
|------|------------|---------------------|-------------------|
| **Deployment** | Docker Compose, single `compose.yaml` | No Docker in repo | ✅ Add `docker-compose.yml` + Dockerfile(s). |
| **Object detection** | YOLOv8n / v10 / RT-DETR, ONNX/TensorRT/OpenVINO | Ultralytics YOLO (YOLOv8/v11), env `YOLO_DEVICE` | Add optional ONNX/TensorRT export path; document OpenVINO for Intel. |
| **RTSP** | Multiple RTSP (Hikvision, Dahua, etc.), GStreamer/FFmpeg | `CAMERA_SOURCES` (OpenCV indices or RTSP URLs) | Already multi-RTSP; document GStreamer/FFmpeg options for robustness. |
| **Latency** | &lt;200ms preferred | No explicit latency target; frame skip and resolution in code | Add latency/FPS display in UI; document tuning (YOLO_IMGSZ, skip). |
| **Annotated stream** | Bounding boxes, labels, zones/tripwires on stream | Detection in backend; overlay possible on MJPEG | Optional: draw boxes on MJPEG or add HLS/WebRTC with overlay. |
| **GUI: confidence** | Confidence threshold **slider** per view | `YOLO_CONF` in env only | Add confidence slider in dashboard (Live or Settings) that calls API or env. |
| **GUI: class filter** | Filter detection classes (person, car, dog, etc.) | Event-type filter (motion, loitering, line_cross) | Add “Detection classes” filter (person, car, truck, etc.) in Live/Export. |
| **GUI: grid layout** | 2×2, 3×3, 1 big + others, fullscreen | Grid of streams in Live section | Already grid; add layout presets (2×2, 3×3) and fullscreen toggle if missing. |
| **GUI: FPS/latency** | Per-stream FPS and latency | Not shown | Add FPS/latency in stream cards or status. |
| **Config** | `cameras.yaml` or `.env` | `config.json`, `.env`, `CAMERA_SOURCES` | Keep; add example `cameras.yaml` for Docker as alternative. |
| **Events** | Simple events + webhook/MQTT | Events table, WebSocket, optional `ALERT_SMS_URL` | Add optional MQTT and generic webhook for events. |
| **Motion pre-filter** | Optional motion before heavy detection | Real motion (frame-diff) already used | Document as “motion pre-filter” for clarity. |

---

## 3. Improvements Implemented / Recommended

### Done in this repo

- **Dashboard card**: “Real-time AI analysis (edge stack)” placed under **Status & controls** on the main dashboard. It summarizes the reference system and links to this audit and Docker.
- **Docker**: `docker-compose.yml` and Dockerfile(s) at project root for backend (and optional frontend) so the app runs with `docker compose up`.
- **Export & data**: Recordings list has **sort** and **filter** (filename search) in Flask and React Export view.

### Recommended next steps

1. **Confidence threshold in UI**  
   Expose `YOLO_CONF` (or an API that backs it) as a slider in the Live section or Settings. Persist in session or config.

2. **Detection class filter in UI**  
   Allow users to enable/disable COCO classes (person, car, truck, dog, cat, etc.) that affect what is drawn or logged. Backend already uses YOLO classes; add filter in API and UI.

3. **FPS / latency on stream cards**  
   Compute FPS and optionally end-to-end latency (frame timestamp → detection done) and show in each stream card or in Status.

4. **ONNX / TensorRT path**  
   Document or add a path to export YOLO to ONNX and, on NVIDIA, to TensorRT for faster inference. Ultralytics supports `model.export(format='onnx')` and TensorRT.

5. **Optional HLS/WebRTC**  
   If needed for scale or lower latency, add a gateway (e.g. nginx-rtmp, GStreamer, or a small WebRTC service) and document in README.

6. **Example cameras config for Docker**  
   Add `config/cameras.example.yaml` (or similar) with placeholder RTSP URLs and optional zones, and reference it in README and compose.

7. **MQTT / webhook for events**  
   Add optional MQTT publish and a generic webhook URL for events (motion, loitering, line_cross) so the app matches the “optional events + webhook/MQTT” from the reference.

---

## 4. Hardware & Run Instructions

- **Run with Docker**: See project root **README.md** and **docker-compose.yml**. Use `docker compose up` then open the web UI (port 5000 or as configured).
- **GPU (NVIDIA)**: Use image with CUDA; set `YOLO_DEVICE=0` (or leave auto). For TensorRT, export the model and mount it or build it in the image.
- **Intel**: For OpenVINO, use a separate export/doc or an image variant that includes OpenVINO runtime.
- **CPU-only**: Omit GPU; backend falls back to CPU (YOLO and OpenCV).

---

## 5. References

- **Ultralytics**: [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) — v8/v10/v11, export to ONNX/TensorRT.
- **This app**: **YOLO_INTEGRATION.md**, **ENTERPRISE_ROADMAP.md**, **FLASK_UI_UX_OVERHAUL.md**.
