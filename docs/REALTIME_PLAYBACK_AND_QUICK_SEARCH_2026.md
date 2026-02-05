# Real-Time Video Playback & Quick Search — 2026 Standards

This document defines **highest-standards 2026** requirements and recommendations for **real-time video playback** and **quick search** in the Vigil SOC / security dashboard, aligned with enterprise, government, and UX best practices.

---

## 1. Real-Time Video Playback (2026 Standards)

### 1.1 Delivery & Latency

| Requirement | Standard / target | Notes |
|-------------|-------------------|--------|
| **End-to-end latency** | &lt; 500 ms preferred; &lt; 200 ms for critical ops | Display frame timestamp or "live" indicator; measure capture → encode → display. |
| **Stream protocols** | MJPEG (current), optional HLS/WebRTC for scale | MJPEG: simple, low server load. HLS/WebRTC: better for many viewers, lower latency. |
| **Frame rate** | Configurable; match camera or cap (e.g. 15–30 fps) | Avoid overloading browser; show actual FPS in UI. |
| **Resolution** | Adaptive or fixed (e.g. 720p) for playback | Backend already supports resolution; document in UI. |

### 1.2 Playback UX

- **Grid layouts**: Presets (1×1, 2×2, 3×3) and fullscreen per stream; keyboard shortcut (e.g. F).
- **Overlay**: Optional bounding boxes and labels on live stream (NISTIR 8161–style metadata in export; overlay for operator view).
- **Indicators**: "Live" badge, recording state, FPS/latency per tile; last frame time in tooltip or status bar.
- **Accessibility**: ARIA labels for video regions; optional captions/announcements for alerts (WCAG 2.2).

### 1.3 Reliability & Security

- **Auth**: All live endpoints require auth; streams scoped by user/site (RBAC).
- **Timeouts**: Configurable stream timeout; automatic reconnect with backoff.
- **Integrity**: Recording export with chain-of-custody (see ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md); live view does not alter chain.

### 1.4 Overlay (Bounding Boxes on Live)

- **Optional**: Draw detection bounding boxes and labels on the MJPEG stream for operator view (NISTIR 8161–style metadata applies to export; overlay is for situational awareness only).
- **Implementation options**: (1) Backend draws on the frame before MJPEG encode (same as recording overlay); (2) Frontend overlays canvas/divs from a separate detection feed (e.g. WebSocket or SSE with bbox coordinates). Prefer (1) for simplicity and consistency with recordings.
- **HLS/WebRTC**: For many viewers or sub-200 ms latency, add a gateway (e.g. nginx-rtmp, GStreamer, or WebRTC service) and document in README; see REALTIME_AI_EDGE_AUDIT.md.

### 1.5 Latency Tuning

- **Frame skip**: Backend analyzes every Nth frame (e.g. every 2–5) to reduce CPU and improve effective latency; configurable via env or config.
- **Resolution**: Lower MJPEG resolution (`STREAM_MAX_WIDTH`, `STREAM_JPEG_QUALITY`) reduces bandwidth and decode cost; recording can stay full res.
- **Target**: &lt; 500 ms end-to-end for typical deployments; &lt; 200 ms when using hardware encode and optional HLS/WebRTC.

### 1.6 Implementation References

- **Current**: MJPEG via `/stream/<id>`, Live page (React + Dash) with grid presets (1×1, 2×2, 3×3), FPS on tiles, fullscreen (F key), system status from `/api/v1/system_status`.
- **Hardening**: VideoWriter in backend uses fixed size (1280×720), contiguous frames, try/except to reduce SIGSEGV risk in OpenCV/FFmpeg.
- **Docs**: REALTIME_AI_EDGE_AUDIT.md, MACBOOK_LOW_LIGHT_VIDEO.md.

---

## 2. Quick Search (2026 Standards)

### 2.1 Scope

Quick search applies to **events, detections, persons, and exportable data** (recordings, audit log, AI data). Results should be scoped by **user role and site access**.

### 2.2 Functional Requirements

| Requirement | Description |
|-------------|-------------|
| **Full-text / keyword** | Search in event type, label, camera name, timestamp range, notes. |
| **Filters** | Date range, camera, event type, detection class (person, car, etc.), severity. |
| **Response time** | &lt; 2 s for typical queries; use indexes (SQLite FTS, or backend search API). |
| **Pagination** | Limit/offset or cursor; "Load more" or infinite scroll. |

### 2.3 UX (2026)

- **Single search box**: Global search with dropdown or modal for filters (date, camera, type).
- **Keyboard**: Focus search with Ctrl+K / Cmd+K; Enter to run; Escape to clear/close.
- **Recent searches**: Last 5–10 queries (stored in session or localStorage); click to re-run.
- **Saved searches** (optional): Name and save filter presets; list in sidebar or Settings.
- **Results**: Highlight matching terms; deep link to event/recording (e.g. Export, Timeline).

### 2.4 API & Backend

- **Endpoint**: e.g. `GET /api/v1/search?q=...&from=...&to=...&camera_id=...&type=...&limit=...`.
- **Response**: JSON list of events/detections/recordings with id, timestamp, camera, type, snippet.
- **RBAC**: Enforce site/camera access; return only allowed resources.

### 2.5 Compliance

- **Audit**: Log search queries (who, when, query params) for sensitive deployments (NIST AU-9).
- **Data minimization**: Return only fields needed for list/detail; no bulk export via search without explicit export action.

---

## 3. Priority Checklist

### Real-time playback

- [x] Show FPS/latency on Live stream tiles (React: ~fps from MJPEG refresh; Dash: LIVE badge).
- [x] Add grid presets (1×1, 2×2, 3×3) and fullscreen (F key per tile).
- [x] Document overlay (1.4) and HLS/WebRTC path; optional overlay implementation later.
- [x] Document latency tuning (frame skip, resolution) in this doc (1.5).

### Quick search

- [x] Global search box (Ctrl+K / Cmd+K) with filters (date_from, date_to, event_type).
- [x] Backend `GET /api/v1/search` and POST with `date_from`, `date_to`, `camera_id`, `event_type`.
- [x] Recent searches in localStorage (last 10); click to re-run.
- [ ] Optional: saved searches, search audit log (admin).

---

## 4. References

- **Enterprise/gov**: ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md, GOVERNMENT_STANDARDS_AUDIT.md, AI_DETECTION_LOGS_STANDARDS.md.
- **Real-time stack**: REALTIME_AI_EDGE_AUDIT.md, YOLO_INTEGRATION.md.
- **UI/UX**: FLASK_UI_UX_OVERHAUL.md, UNIFIED_ACTIVITY_UX.md.
