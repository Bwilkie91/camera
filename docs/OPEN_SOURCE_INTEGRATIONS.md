# Open-Source Integrations & Upgrade Path

This document lists **integrated** open-source components and **recommended** enterprise-grade, easy-to-integrate upgrades (research-backed, best-in-class).

---

## Currently integrated

### Chart.js (real-time charting)
- **What:** Live activity chart (events + AI data over last 60 min in 5‑minute buckets).
- **Source:** [Chart.js](https://www.chart.js.org/) v4.4.1 via CDN (MIT).
- **Why:** Lightweight, tree-shakeable, supports real-time updates and decimation for large datasets; widely used in production dashboards.
- **Location:** `templates/index.html` — script from `cdn.jsdelivr.net`, init for `#liveActivityChart`.

### Web Audio API (audio visualization)
- **What:** Real-time microphone waveform on the Live activity panel.
- **Source:** Browser built-in (AnalyserNode, getUserMedia).
- **Why:** No extra dependency; standard for real-time audio viz.

### Speech-to-text pipeline (continuous)
- **What:** A long-running audio worker thread listens continuously and updates the last transcription; each analysis cycle merges it into `ai_data` (e.g. `audio_transcription`, sentiment, emotion). The Speech log tab shows rows with transcriptions.
- **Why:** Enables the “Speech log” tab to show entries as soon as the pipeline captures speech (start recording, Audio on, speak into the mic). Empty state explains how to enable it (ENABLE_AUDIO, microphone, recording).

### Flask + SQLite + YOLO/MediaPipe/DeepFace
- **What:** Backend stack for video, AI pipeline, and storage.
- **Docs:** See YOLO_INTEGRATION.md, EMOTION_INTEGRATION.md, ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md.

---

## Recommended upgrades (easy to integrate)

### 1. **ApexCharts** (alternative to Chart.js)
- **Use case:** More chart types (radar, heatmaps, radial bar) and built-in annotations.
- **Integration:** Add `<script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>`, create `new ApexCharts(el, options)`.
- **License:** MIT.

### 2. **Plotly.js** (scientific / 3D)
- **Use case:** 3D scene visualization, contour plots, geographic maps for multi-site dashboards.
- **Integration:** CDN or npm; `Plotly.newPlot(div, data, layout)`.
- **License:** MIT.

### 3. **Server-Sent Events (SSE)** for live pipeline — *integrated*
- **Use case:** Push feed updates (new events, activity, recording/audio toggles) without polling.
- **Integration:** `GET /api/stream` streams SSE; frontend `EventSource('/api/stream')` refreshes the current tab and chart on `new_event` or `activity_update`.
- **Why:** Feed and analytics data update in real time when new AI data or events are written.

### 4. **WebSocket (e.g. Flask-SocketIO)**
- **Use case:** True bidirectional live updates (alerts, PTZ, recording state).
- **Integration:** `flask-socketio`, `socket.io` on frontend; emit on `_broadcast_event` and recording/audio toggle.
- **Why:** Enterprise dashboards often use WebSockets for ops consoles.

### 5. **Papa Parse** (CSV export)
- **What:** Robust CSV parse/stringify for exports and bulk uploads.
- **Integration:** Already common in analytics UIs; use for client-side preview before download.
- **License:** MIT.

### 6. **Date-fns or Day.js** (time handling)
- **Use case:** Consistent timezone and 12‑hour formatting across the app.
- **Integration:** Replace ad-hoc `toDateAnd12hr` with `format(date, 'h:mm:ss a')` and `zonedTimeToUtc` for audit timestamps.
- **License:** MIT.

### 7. **Accessibility (a11y)**
- **Use case:** ARIA live regions, focus management, keyboard navigation for fullscreen and toggles.
- **Current:** Live activity and footer toggles have `aria-label` and roles; expand to all interactive sections for enterprise/508 alignment.

---

## Standards alignment

- **NISTIR 8161 / chain of custody:** Integrity hashes and manifest exports (see ENTERPRISE_GOV_STANDARDS_IMPROVEMENTS.md).
- **Chart.js / ApexCharts:** Used in many SOC and NOC dashboards; no known export or compliance blockers.
- **SSE/WebSocket:** Prefer TLS in production; document in security/ops runbooks.

---

## Summary

| Component        | Status   | Purpose                    |
|-----------------|----------|----------------------------|
| Chart.js        | Integrated | Live activity (60 min) chart |
| Web Audio API   | Integrated | Mic waveform               |
| API audio toggle| Integrated | Runtime audio on/off      |
| Fullscreen footer | Integrated | Record + Audio toggles   |
| Grid layout     | Integrated | Data sections spacing     |
| SSE             | Integrated  | Live feed + chart updates  |
| WebSocket       | Optional    | When flask-sock installed  |
| ApexCharts/Plotly | Optional | Richer visualizations   |
