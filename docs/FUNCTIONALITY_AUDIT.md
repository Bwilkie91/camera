# Vigil — Extensive Functionality Audit (1–100)

**Audit date**: February 2026  
**Scope**: End-to-end functionality, external setup requirements, and UX/UI supercharge opportunities for the Vigil Edge Video Security platform.

---

## Overall Functionality Score: **72 / 100**

| Category | Weight | Score | Notes |
|---------|--------|-------|--------|
| Core features (streams, recording, events, auth) | 25% | 88 | Solid: multi-camera, MJPEG, recording, RBAC, MFA, audit |
| AI & analytics (YOLO, zones, search, aggregates) | 20% | 82 | Present; zones/config not editable in UI |
| External integrations & setup | 15% | 45 | SMS, ONVIF, thermal, Redis need external config |
| UX/UI polish & responsiveness | 20% | 58 | Functional but gaps: skeletons, storage UI, config UI |
| Security & compliance readiness | 20% | 74 | Strong auth/audit; encryption at rest weak |

**Weighted**: (88×0.25 + 82×0.20 + 45×0.15 + 58×0.20 + 74×0.20) ≈ **72**

---

## 1. What’s Working Well (Implemented)

### Backend
- **Multi-camera**: `CAMERA_SOURCES` (indices or RTSP), auto-detect when `auto`/unset; `/video_feed/<id>`, `/streams`.
- **Recording**: `POST /toggle_recording`, AVI to disk; retention job when `RETENTION_DAYS` set.
- **Auth**: Session login, bcrypt, roles (viewer/operator/admin), lockout, session timeout, optional TOTP MFA, password policy/expiry/history, resource-level RBAC (user_site_roles).
- **Audit**: Login/logout/config/export/ack/toggle_recording/move_camera; per-row integrity_hash; `/audit_log`, `/audit_log/export`, `/audit_log/verify`.
- **Events**: CRUD, severity, acknowledge, WebSocket push; filters (camera, type, severity, acknowledged, date).
- **AI**: YOLO (configurable model/device/size), motion, loitering/line-crossing (config.json), LPR on vehicles, optional DeepFace/EmotiEffLib, MediaPipe pose; batch commits for ai_data.
- **APIs**: `/get_data`, `/events`, `/api/v1/analytics/aggregates`, `POST /api/v1/search`, `/api/v1/system_status`, `/api/v1/cameras/detect`, `/api/v1/audio/detect`, `/api/v1/devices`.
- **Export**: CSV with SHA-256; recordings with NISTIR 8161-style headers and manifest; optional MP4 when ffmpeg present.
- **Config**: `GET /config`, `PATCH /config` (admin, audited) for loiter_zones, loiter_seconds, crossing_lines.
- **Health**: `/health`, `/health/ready`; system_status with DB, uptime, per-camera status, AI “superpowers”.

### Frontend (React)
- **Views**: Dashboard, Live (stream grid, recording, PTZ), Events (filters, search, ack), Timeline (ranges, expandable rows), Map (sites, positions), Analytics (date range, aggregates), Export (CSV + recordings AVI/MP4), Settings (user, devices, password, MFA, audit log).
- **Auth**: Login, MFA step, session timeout redirect, auto-login when `AUTO_LOGIN=1`.
- **Real data**: No mock data; streams, events, status, recordings from API.
- **WebSocket**: New-event toast and query invalidation.
- **Accessibility**: `?` help, Esc to close, aria-live toasts.

---

## 2. What’s Missing or Incomplete

### Backend / Logic
- **Redis WebSocket broadcast**: In `app.py`, `_redis_pub` and `_redis_sub` are set to `None` after the Redis block (lines 153–155), so Redis pub/sub is **never used** even when `REDIS_URL` is set. Multi-instance WebSocket scaling is effectively disabled until this is fixed.
- **Analytics config UI**: Backend has `GET/PATCH /config` for zones/lines; **frontend has no screen** to view or edit loiter zones, loiter_seconds, or crossing lines. Operators must edit `config.json` by hand or call the API directly.
- **Storage/recording health**: No API for “recordings folder size” or “retention status”; dashboard cannot show storage usage or “low disk” warnings.
- **Camera health history**: No persistence of camera online/offline transitions; no “last offline” or “flapping” metrics for dashboard.
- **Event type filter in Events view**: Backend supports `event_type` on `/events`; frontend Events page filters by severity and acknowledged only, not by event_type (motion, loitering, line_cross, etc.).

### Frontend
- **Loading states**: Most views use plain “Loading…” text; no skeleton loaders for cards, tables, or lists (called out in FRONTEND_UI_AUDIT.md).
- **Empty states**: Some copy exists; no dedicated illustrations or stronger CTAs for “No events”, “No streams”, “No recordings”.
- **Config (zones/lines)**: No Settings or Admin section to GET/PATCH analytics config (zones, lines, loiter_seconds).
- **Audit log export**: Backend has `GET /audit_log/export`; frontend Audit log in Settings is table-only, no “Export audit log” button.
- **Login redirect**: After login, always `navigate('/', { replace: true })`; no redirect to originally requested URL (e.g. `/export`).

---

## 3. What Needs to Be Set Up Externally

| Item | Purpose | How |
|------|--------|-----|
| **Twilio + Node SMS** | Motion/loitering/line_cross alerts to phone | Set `TWILIO_*` in env; run `node index.js` on port 3000; set `ALERT_SMS_URL`, `ALERT_PHONE` in .env |
| **ONVIF PTZ** | Pan/tilt/zoom on IP cameras | Install `onvif-zeep`; set `ONVIF_HOST`, `ONVIF_PORT`, `ONVIF_USER`, `ONVIF_PASS` |
| **Thermal stream** | FLIR Lepton feed | Install `flirpy`; use hardware on Jetson; backend exposes `/thermal_feed` when available |
| **Redis** | Multi-instance WebSocket broadcast | Set `REDIS_URL`; **and fix** the override in app.py so Redis is actually used |
| **HTTPS / reverse proxy** | TLS, production | Nginx/Caddy; set `ENFORCE_HTTPS=1`, optional `STRICT_TRANSPORT_SECURITY`, `CONTENT_SECURITY_POLICY` |
| **React build for production** | Serve SPA from Flask | `cd frontend && npm run build`; set `USE_REACT_APP=1` |
| **Optional AI stacks** | Emotion, audio, Wi‑Fi | DeepFace or EmotiEffLib; PyAudio + SpeechRecognition; Scapy + monitor interface; set corresponding env vars |
| **Sites / map** | Map view with map image and positions | Populate `sites` (e.g. map_url) and `camera_positions` (e.g. via SQL or future admin UI) |

---

## 4. What Would Supercharge UX/UI

### High impact
1. **Analytics config UI (zones & lines)**  
   Add an admin-only “Analytics” or “Zones” section (or extend Settings): GET `/config`, display loiter zones and crossing lines (e.g. on a canvas or list), allow editing and PATCH `/config`. Makes the system usable without touching `config.json` or curl.

2. **Storage and retention in System Status**  
   Backend: add an endpoint (e.g. `/api/v1/storage` or extend `/api/v1/system_status`) that returns recordings directory size and retention status (e.g. “X GB used”, “Retention: 30 days”). Frontend: show in Dashboard System Status and optionally warn when low or over retention.

3. **Loading skeletons**  
   Replace “Loading…” with skeleton placeholders for Dashboard cards, Events list, Timeline, Analytics table, and Stream grid. Improves perceived performance and polish.

4. **Event type filter on Events page**  
   Add a dropdown or chips for event_type (motion, loitering, line_cross, etc.) and pass it to `fetchEvents` so users can filter by type as well as severity/ack.

5. **Audit log export in Settings**  
   Add “Export audit log” button that calls `GET /audit_log/export` and downloads the CSV (with SHA-256), so admins don’t need to use the API directly.

### Medium impact
6. **Post-login redirect to intended page**  
   Store the requested path (e.g. in sessionStorage or state) when unauthenticated user hits a protected route; after login, redirect there instead of always `/`.

7. **Richer empty states**  
   Dedicated short copy + optional illustration or icon for “No events”, “No streams”, “No recordings”, “No aggregate data” with clear next steps (e.g. “Start recording from Live”).

8. **Design tokens / visual hierarchy**  
   Introduce a small set of spacing and type tokens (e.g. 4/8/16px, font sizes) and use them consistently; improves consistency and “premium” feel (see FRONTEND_UI_AUDIT.md).

9. **Tooltips for status terms**  
   In System Status, add tooltips for “No signal”, “Offline”, “Degraded” (e.g. “No frame in last 30s”) so operators understand at a glance.

10. **Camera health history (backend + UI)**  
    Log camera online/offline transitions (e.g. in a small table or append-only log); expose “last offline” or “recent flapping” in system_status and show in Dashboard for operational awareness.

### Lower priority
11. **Customizable dashboard**  
    Let users choose which cards/sections to show or reorder (e.g. store in user prefs or localStorage).

12. **Focus management in help modal**  
    Trap focus inside the help modal and restore focus on close; improve keyboard accessibility.

13. **Responsive tweaks**  
    Ensure System Status table and camera list work well on small screens (stack or horizontal scroll).

14. **Event-to-clip link**  
    If events get a “recording clip” or timestamp link in the future, add “Open clip” from Events/Timeline to jump to that time in a recording or export.

---

## 5. Quick Wins (Code-Level)

- **Fix Redis**: Remove or conditionalize the two lines in `app.py` that set `_redis_pub = None` and `_redis_sub = None` so that when `REDIS_URL` is set and redis is importable, pub/sub is actually used.
- **Events event_type filter**: Add `event_type` state and query param in `Events.tsx` and pass it into `fetchEvents`.
- **Audit export button**: In Settings, add a button that fetches `GET /audit_log/export` and triggers a CSV download.
- **Login redirect**: In `AuthContext` or Login flow, persist `location.pathname` when redirecting to login and navigate back after successful login when possible.

---

## 6. Summary Table

| Area | Status | Action |
|------|--------|--------|
| Core VMS (streams, record, events, auth) | ✅ Strong | Keep; optional UX polish |
| AI (YOLO, zones, search) | ✅ Backend done | Expose zones/lines in UI; add event_type filter |
| Config (zones/lines) | ⚠️ API only | Add Config/Zones UI (GET/PATCH) |
| Storage / retention visibility | ❌ Missing | API + Dashboard display |
| SMS / ONVIF / thermal / Redis | ⚠️ External / broken | Document setup; fix Redis override |
| Loading / empty states | ⚠️ Basic | Skeletons; richer empty states |
| Audit export in UI | ❌ Missing | Button in Settings |
| Post-login redirect | ❌ Missing | Persist path; redirect after login |

---

## 7. Reference Docs

- **docs/FRONTEND_UI_AUDIT.md** — UI score 78/100; skeletons, storage, design tokens.
- **docs/SYSTEM_RATING.md** — Security 74/100; encryption at rest, TLS, CVE process.
- **docs/OPTIMIZATION_AUDIT.md** — DB indexes, YOLO/stream tuning, batch commits.
- **docs/GOVERNMENT_STANDARDS_AUDIT.md** — NIST/CJIS alignment, gaps.

---

**Conclusion**: Vigil scores **72/100** on functionality. Core features and security are in good shape. The largest gaps are: (1) **external setup** (SMS, ONVIF, thermal, Redis) and a **Redis bug**; (2) **no UI for analytics config** (zones/lines) and **no storage/retention visibility**; (3) **UX polish** (skeletons, empty states, audit export button, post-login redirect). Addressing these would raise the score toward the mid‑80s and significantly improve operator experience and deployability.
