# Configuration & Optimization Guide

Research-backed settings and presets for the Vigil stack. Each section cites sources and gives recommended values.

---

## 1. Flask & production serving

### Research

- **Workers**: Start with `(CPU cores × 2)`; scale to 2–4 workers per core for I/O-bound apps. Workers are capacity, not connection count.  
  [Gunicorn design](https://docs.gunicorn.org/en/stable/design.html), [Flask deploying](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/)
- **Worker type**: `gthread` (thread pool per worker) supports keep-alive and good concurrency with lower memory than more processes. Example: `gunicorn -w 4 -k gthread --threads 4 app:app`.  
  [Gunicorn worker types](https://docs.gunicorn.org/en/stable/design.html)
- **Async (gevent/eventlet)**: Use for long blocking calls, WebSockets, or streaming when not behind a buffering proxy.
- **Best practice**: Run behind a reverse proxy (nginx/Apache); enable gzip and caching; offload heavy work (e.g. Celery).

### Recommended

| Setting | Development | Production |
|--------|-------------|------------|
| Server | `python app.py` (Flask dev) | `gunicorn -w 4 -k gthread --threads 4 --bind 0.0.0.0:5000 "app:app"` |
| `FLASK_SECRET_KEY` | Any (dev) | Long random secret (e.g. 32+ bytes) |
| `SESSION_TIMEOUT_MINUTES` | 60 | 15–30 (NIST/CJIS style) |
| `ENABLE_CORS` | 1 if frontend on different port | 1 + `CORS_ORIGIN` set to frontend URL |
| `STRICT_TRANSPORT_SECURITY` | 0 | 1 when behind HTTPS |
| `ENFORCE_HTTPS` | 0 | 1 when behind reverse proxy with HTTPS |

---

## 2. YOLO object detection

### Research

- **Image size**: 640 = faster, good for real-time; 1280 = better for small objects, ~4× cost. Choose 640 for speed, 1280 for accuracy.  
  [Ultralytics model comparison](https://docs.ultralytics.com/compare/), [YOLO imgsz tradeoff](https://github.com/ultralytics/ultralytics/issues/18849)
- **Export**: ONNX ~3× CPU speedup; TensorRT 2–5× on NVIDIA GPU; OpenVINO on Intel. Use `.onnx`/`.engine` path as `YOLO_MODEL` when available.  
  [Ultralytics export](https://docs.ultralytics.com/modes/export/), [OpenVINO YOLO](https://docs.ultralytics.com/guides/optimizing-openvino-latency-vs-throughput-modes/)
- **Confidence**: 0.25 default; raise to 0.4–0.5 to cut false positives; lower to catch more (more noise).

### Recommended

| Env var | Default | Optimized (speed) | Optimized (accuracy) | Jetson |
|---------|--------|-------------------|------------------------|--------|
| `YOLO_MODEL` | yolov8n.pt | yolov8n.onnx (if exported) | yolov8s.pt or .onnx | yolov8n.engine |
| `YOLO_IMGSZ` | 640 | 640 | 1280 | 640 |
| `YOLO_CONF` | 0.25 | 0.35 | 0.25 | 0.3 |
| `YOLO_DEVICE` | (auto) | 0 (GPU) or leave empty (CPU) | 0 | 0 |
| `YOLO_TENSORRT_FP16` | — | — | — | 1 |
| `YOLO_TENSORRT_WORKSPACE_MB` | — | — | — | 4 |
| `JETSON_MODE` | 0 | 0 | 0 | 1 |

---

## 3. OpenCV & RTSP / camera capture

### Research

- **Buffer lag**: OpenCV buffers frames; if processing is slower than capture, latency grows (e.g. 7–10 s).  
  [OpenCV buffer lag](https://stackoverflow.com/questions/30032063/opencv-videocapture-lag-due-to-the-capture-buffer)
- **Buffer size**: `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` keeps one frame in buffer (reduces latency). Support varies by backend.  
  [CAP_PROP_BUFFERSIZE](https://stackoverflow.com/questions/54460797/how-to-disable-buffer-in-opencv-camera/54461284)
- **RTSP**: OpenCV `read()` may not return False on disconnect; use timeout + reconnect or GStreamer pipeline with `max-buffers=1 drop=true`.  
  [RTSP timeout](https://forum.opencv.org/t/opencv-rtsp-stream-timeout/20252), [GStreamer low latency](https://stackoverflow.com/questions/51722319/skip-frames-and-seek-to-end-of-rtsp-stream-in-opencv/51825534)
- **Backend**: FFmpeg (`cv2.CAP_FFMPEG`) is default for URLs; GStreamer allows fine control (reconnect, decode).

### Recommended

| Env var | Default | Optimized (low latency) | Unstable RTSP |
|---------|--------|-------------------------|----------------|
| `RTSP_RECONNECT_SEC` | (none) | 15 | 10 |
| `RTSP_TIMEOUT_MS` | 0 | 5000 | 3000 |
| (code) | — | Set `CAP_PROP_BUFFERSIZE=1` after open | Same + shorter reconnect |

- In code: after `VideoCapture` open, call `cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)` when supported.
- For very unstable RTSP, consider GStreamer pipeline or a watchdog that reopens the stream when no frame for `RTSP_RECONNECT_SEC` seconds.

---

## 4. MJPEG streaming

### Research

- MJPEG uses more bandwidth than H.264; each frame is a JPEG. Quality 80–85 is a common tradeoff; lower = less bandwidth, higher = better clarity.  
  [MJPEG vs H.264 bandwidth](https://smartipvideo.wordpress.com/2010/05/25/comparing-h-264-and-mjpeg-bandwidth-usage-over-security-networks/)
- Resizing (e.g. max width 640) greatly reduces bandwidth and CPU.

### Recommended

| Env var | Default | Low bandwidth | High quality (LAN) |
|---------|--------|----------------|--------------------|
| `STREAM_JPEG_QUALITY` | 82 | 70 | 88 |
| `STREAM_MAX_WIDTH` | 0 | 640 | 0 (no resize) |

---

## 5. SQLite

### Research

- **WAL**: Better concurrency and often faster; readers don’t block writers.  
  [SQLite WAL](https://www.sqlite.org/wal.html)
- **synchronous=NORMAL**: With WAL, reduces fsync cost while keeping consistency.  
  [SQLite pragmas](https://www.sqlite.org/pragma.html), [pragma cheatsheet](https://cj.rs/blog/sqlite-pragma-cheatsheet-for-performance-and-consistency/)
- **cache_size**: More pages in memory = fewer disk reads (e.g. -64000 for 64MB).
- **busy_timeout**: Avoids immediate “database is locked”; wait up to N ms.

### Recommended (app already uses WAL)

| PRAGMA | Value | Purpose |
|--------|--------|---------|
| `journal_mode` | WAL | Concurrency, performance |
| `synchronous` | NORMAL | Balance safety/speed with WAL |
| `cache_size` | -64000 | ~64 MB page cache |
| `busy_timeout` | 5000 | Wait up to 5 s on lock |
| `temp_store` | MEMORY | Temp tables in RAM (optional) |

---

## 6. AI analysis interval & batch

### Research

- Shorter interval = more responsive alerts, higher CPU. Longer = less load, more delay.
- Batch size: larger = fewer commits, better throughput; too large = delayed visibility and more memory.

### Recommended

| Env var | Default | Low latency | Low CPU |
|---------|--------|-------------|---------|
| `ANALYZE_INTERVAL_SECONDS` | 10 | 5 | 20–30 |
| `AI_DATA_BATCH_SIZE` | 10 | 5 | 20–30 |

Bounds in code: interval 5–60 s, batch 1–50.

---

## 7. Frontend (Vite / React)

### Research

- Vite uses Rollup for production; `build.rollupOptions.output.manualChunks` splits vendor vs app code for better caching.  
  [Vite build](https://vite.dev/guide/build), [code splitting](https://dev.to/markliu2013/vite-code-splitting-strategy-5a69)
- Modern targets (Chrome 87+, Safari 13+) keep bundles smaller.

### Recommended

- In `vite.config.ts`: add `build.rollupOptions.output.manualChunks` to split `react` / `react-dom` and router into a vendor chunk.
- Production: `npm run build`; serve built assets via Flask when `USE_REACT_APP=1`.

---

## 8. Dashboard (Plotly Dash)

### Research

- Polling interval drives API load vs freshness. 30 s is a reasonable default for a SOC view.

### Recommended (`dashboard/config.yaml`)

| Setting | Default | Optimized |
|---------|--------|-----------|
| `polling.interval_ms` | 30000 | 15000 (fresher) or 60000 (lighter) |
| `data.api_get_data_limit` | 5000 | 10000 if backend allows |
| `theme.default` | dark | dark (SOC) or light |

---

## 9. Proactive pipeline

### Research

- ReID threshold ~0.85 balances identity stability vs over-merging.
- Loiter duration and anomaly thresholds depend on site; 300 s (5 min) is a reasonable escalation point.

### Recommended (`proactive/config.yaml`)

| Setting | Default | Tighter (more alerts) | Looser |
|---------|--------|------------------------|--------|
| `reid.similarity_threshold` | 0.85 | 0.9 | 0.8 |
| `predictor.loiter_duration_sec` | 300 | 180 | 600 |
| `predictor.anomaly_high` | 0.5 | 0.4 | 0.6 |
| `camera.width` / `height` | 640×480 | 640×480 (keep for speed) | 1280×720 if GPU |

---

## 10. Analytics (config.json)

### Schema

- **loiter_zones**: List of polygons; each polygon is list of `[x,y]` (0–1 normalized).
- **loiter_seconds**: Seconds in zone before loitering event (e.g. 30).
- **crossing_lines**: List of lines; each line is `[x1,y1,x2,y2]` (0–1 normalized).

### Recommended

- **Indoor/small**: One zone covering area of interest; 20–30 s loiter; one crossing line at door.
- **Outdoor**: Multiple zones; 30–60 s; crossing lines at boundaries.

---

## 11. Security & hardening

| Env var | Recommendation |
|---------|----------------|
| `FLASK_SECRET_KEY` | 32+ random bytes in production |
| `ADMIN_PASSWORD` | Strong; change from default |
| `SESSION_TIMEOUT_MINUTES` | 15–30 for NIST/CJIS |
| `LOCKOUT_MAX_ATTEMPTS` | 5 |
| `LOCKOUT_DURATION_MINUTES` | 15 |
| `ENABLE_MFA` | 1 for operator/admin when required |
| `PASSWORD_MIN_LENGTH` | 8+ |
| `AUDIT_RETENTION_DAYS` | 365 |
| `CONTENT_SECURITY_POLICY` | Restrictive; allow only needed sources |

---

## 10. Data quality & evidence (90+ plan)

Env vars for PLAN_90_PLUS and BEST_PATH_FORWARD data-quality and evidence alignment. See **docs/PLAN_90_PLUS_DATA_POINTS.md** and **docs/STANDARDS_APPLIED.md**.

| Env var | Default | Purpose |
|---------|--------|---------|
| `EMOTION_CLAHE_THRESHOLD` | 80 | Mean intensity below which CLAHE is applied on L channel for emotion (0 = off). Phase 2.1. |
| `SCENE_VAR_MAX_INDOOR` | 5000 | Max lower-half variance for Indoor; Indoor only when mean < 100 and var < this. |
| `CENTROID_SMOOTHING_FRAMES` | 5 | Moving average of primary centroid over N frames for line-cross (0 = off). |
| `MOTION_MOG2_VAR_THRESHOLD` | 16 | MOG2 varThreshold (4–64) when `MOTION_BACKEND=mog2`. |
| `ENFORCE_HTTPS` | 0 | `1` = redirect HTTP→HTTPS; `reject` = return 403 for non-HTTPS (Phase 3.2). |

Also: `EMOTION_MIN_CROP_SIZE`, `POSE_MIN_CROP_SIZE`, `LINE_CROSS_DEBOUNCE_CYCLES`, `HEIGHT_REF_CM`, `HEIGHT_REF_PX`, `MOTION_BACKEND`, `MOTION_THRESHOLD`. Full list in **docs/DATA_COLLECTION_RESEARCH.md** §5.

---

## Quick reference: env presets

**Speed (real-time, low CPU)**  
`YOLO_IMGSZ=640` `YOLO_CONF=0.35` `ANALYZE_INTERVAL_SECONDS=10` `STREAM_MAX_WIDTH=640` `STREAM_JPEG_QUALITY=75`

**Accuracy (small objects, better quality)**  
`YOLO_IMGSZ=1280` `YOLO_CONF=0.25` `ANALYZE_INTERVAL_SECONDS=5` `STREAM_MAX_WIDTH=0` `STREAM_JPEG_QUALITY=88`

**Jetson**  
`JETSON_MODE=1` `YOLO_MODEL=yolov8n.engine` `YOLO_TENSORRT_FP16=1` `YOLO_IMGSZ=640`

**Production Flask**  
Use Gunicorn with `-w 4 -k gthread --threads 4`; set `FLASK_SECRET_KEY`, `SESSION_TIMEOUT_MINUTES`, `STRICT_TRANSPORT_SECURITY=1` when on HTTPS.

**Unstable RTSP**  
`RTSP_RECONNECT_SEC=10` `RTSP_TIMEOUT_MS=3000`; app sets `CAP_PROP_BUFFERSIZE=1` automatically after opening capture.

---

## 12. References

- [Flask / Gunicorn](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/)
- [Gunicorn design & workers](https://docs.gunicorn.org/en/stable/design.html)
- [Ultralytics export & Jetson](https://docs.ultralytics.com/modes/export/)
- [OpenVINO YOLO latency vs throughput](https://docs.ultralytics.com/guides/optimizing-openvino-latency-vs-throughput-modes/)
- [OpenCV VideoCapture buffer lag](https://stackoverflow.com/questions/30032063/opencv-videocapture-lag-due-to-the-capture-buffer)
- [SQLite WAL & pragmas](https://www.sqlite.org/wal.html), [pragma cheatsheet](https://cj.rs/blog/sqlite-pragma-cheatsheet-for-performance-and-consistency/)
- [Vite production build](https://vite.dev/guide/build)
