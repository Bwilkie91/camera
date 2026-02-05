# Optimization Audit

Focused audit of **performance, resource use, and scalability** for the Vigil backend and key flows. Recommendations are ordered by impact vs effort.

---

## Summary

| Area | Priority | Impact | Effort | Status |
|------|----------|--------|--------|--------|
| YOLO inference (resolution / device) | High | High | Low | Recommended |
| DB indexes for list/query endpoints | High | Medium | Low | Recommended |
| MJPEG stream (encode quality/size) | Medium | Medium | Low | Optional |
| analyze_frame batching / skip-frames | Medium | Medium | Medium | Optional |
| API response caching | Low | Low | Medium | Optional |

---

## 1. AI / Inference (analyze_frame)

### Current behavior

- **YOLO**: Full camera frame (1280×720) passed to `yolo_model(frame)` every 10s when recording. No explicit input size; Ultralytics may resize internally but full-resolution read is used.
- **MediaPipe**: Same full frame for pose.
- **DeepFace**: Same full frame for emotion (when available).
- **LPR**: PyTesseract on vehicle ROIs only (already scoped).

### Recommendations

1. **Downscale for YOLO**  
   Resize frame to 640px (or 416) before inference; YOLO is typically trained at 640. Reduces GPU/CPU time and memory with minimal accuracy loss. Example: `cv2.resize(frame, (640, 360))` or use Ultralytics’ built-in `imgsz=640` in the `predict()` call if the API supports it per-call.

2. **YOLO device and options**  
   - Set `YOLO_DEVICE=0` (or `cuda`) on GPU hosts.  
   - Use half-precision on GPU if supported (e.g. Ultralytics’ `half=True`) to reduce memory and latency.  
   - Ensure inference runs with `verbose=False` (or equivalent) to avoid log I/O.

3. **Optional: skip-frames or lower frequency**  
   If 10s is more than needed, consider 15–30s for analytics and keep motion/recording on full frame rate where appropriate.

4. **DeepFace / MediaPipe**  
   Both are optional. If enabled, consider running them on a downscaled crop (e.g. face/person ROI) or every N-th analysis cycle to limit cost.

---

## 2. Database

### Current behavior

- **WAL**: `PRAGMA journal_mode=WAL` is set per connection — good for concurrent read/write.
- **No indexes** on filter/sort columns: `ai_data` (date, time, camera_id), `events` (timestamp, site_id, event_type), `audit_log` (timestamp).  
- **Queries**: `get_data`, `list_events`, aggregates, and audit export use `ORDER BY date/time/timestamp DESC LIMIT ? OFFSET ?`. As tables grow, full scans will slow.

### Recommendations

1. **Add indexes** (run once, e.g. in a migration or `_init_schema`):
   - `ai_data`: `(date, time DESC)`, `(camera_id, date, time DESC)`.
   - `events`: `(timestamp DESC)`, `(site_id, timestamp DESC)`, optionally `(event_type, timestamp DESC)`.
   - `audit_log`: `(timestamp DESC)` for export/verify and retention.

2. **Cap default list sizes**  
   Ensure `limit` has a server-side max (e.g. 1000) on `/get_data`, `/events`, and aggregate endpoints to avoid huge result sets.

3. **Retention deletes**  
   Retention job deletes by `date < ?`. Indexes on `date` / `timestamp` will make these deletes and the preceding range scans faster.

---

## 3. Video Stream (gen_frames)

### Current behavior

- Full frame (1280×720) from `cap.read()` encoded to JPEG every loop with `cv2.imencode('.jpg', frame)` (default quality).
- No explicit quality or max resolution for the stream; bandwidth scales with resolution.

### Recommendations

1. **Stream size/quality**  
   For live view, consider encoding at lower resolution (e.g. 640×360) or with `cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])` to reduce bandwidth and CPU. Keep full resolution for recording if needed.

2. **Placeholder**  
   When no frame is available, the 0.5s sleep is reasonable; no change required unless tuning for responsiveness.

---

## 4. analyze_frame Loop and DB Writes

### Current behavior

- One `INSERT` into `ai_data` per analysis (every 10s); optional second `INSERT` into `events` on event; immediate `commit()` after each.
- Single thread; no batching across frames.

### Recommendations

1. **Batching** (optional)  
   Buffer 2–3 analysis rows and commit in one transaction to reduce commit overhead. Trade-off: up to ~30s delay before data is visible; usually acceptable for analytics.

2. **Keep per-frame commit for events**  
   So that alerts and WebSocket push stay timely; no change recommended for event inserts.

---

## 5. API and Frontend

### Current behavior

- No HTTP caching headers on JSON APIs; no in-memory response cache.
- List endpoints build result lists in memory; acceptable with capped `limit`.

### Recommendations

1. **Limit caps**  
   Enforce a maximum `limit` (e.g. 500 or 1000) on `/get_data`, `/events`, and aggregate/search endpoints.

2. **Caching** (optional)  
   Short-lived cache (e.g. 5–10s) for `/streams`, `/health`, or `/config` if they are hit very frequently; lower priority than DB and inference.

3. **Frontend**  
   Not audited in depth; consider lazy loading and pagination for large tables (Events, Timeline) if not already present.

---

## 6. Startup and Configuration

### Current behavior

- YOLO model loaded at import; optional `.env` via python-dotenv; camera auto-detect when `CAMERA_SOURCES=auto`.
- Single process; no multi-worker guidance in this audit.

### Recommendations

1. **Model load**  
   Already optional (graceful if YOLO missing or load fails). No change required.

2. **Documentation**  
   Add a short “Performance tuning” section in README or ops doc: set `YOLO_DEVICE`, optional `YOLO_MODEL` (e.g. `yolov8n.pt` for speed), and reference this audit for DB indexes and stream quality.

---

## Implemented (Current)

- **DB indexes**: `ai_data`, `events`, `audit_log` — see `_init_schema`.
- **Limit caps**: `_parse_filters()` default 100, max 1000 for list endpoints.
- **YOLO**: `imgsz=640` (configurable via `YOLO_IMGSZ`), `verbose=False` in `analyze_frame` for faster inference.
- **MJPEG**: `STREAM_JPEG_QUALITY` (default 82), `STREAM_MAX_WIDTH` (0 = no resize; e.g. 640) for lighter streams; recording stays full resolution.
- **AI status**: `GET /api/v1/system_status` includes `ai` (yolo, emotion, mediapipe_pose, lpr, stream_quality, stream_max_width) so dashboards can show “superpowers” and ops can verify which analytics are active.
- **Batch commit for ai_data**: Up to 3 analysis rows buffered, then committed in one transaction (`AI_DATA_BATCH_SIZE=3`). Reduces commit overhead; up to ~30s delay before latest rows are visible (events still commit immediately).
- **Performance tuning (README)**: Short subsection added: YOLO_DEVICE, YOLO_MODEL, YOLO_IMGSZ, stream vars, link to this audit.

## Next Steps

1. **Ongoing**: Run `pip-audit` (or `pip audit` on newer pip) and dependency updates (see SYSTEM_RATING.md).

## Research (collection optimization)

See **COLLECTION_OPTIMIZATION_RESEARCH.md** for literature on frame sampling, DB batching, conditional emotion/extended runs, and flush-on-stop. That doc proposes env-driven tuning: `ANALYZE_INTERVAL_SECONDS`, `AI_DATA_BATCH_SIZE`, `EMOTION_EVERY_N`, `EXTENDED_EVERY_N`, `YOLO_CONF`.

See **GOVERNMENT_STANDARDS_AUDIT.md** and **SYSTEM_RATING.md** for security and compliance; **YOLO_INTEGRATION.md** for model configuration.
