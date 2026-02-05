# Vigil — Application Review & Rating (Highest Standards)

**Overall rating: 78 / 100**

This document reviews the Vigil edge video security platform against highest industry and government standards: feature completeness, functionality, design, security, and operational readiness. It summarizes strengths, gaps, and suggested improvements.

---

## 1. Executive Summary

| Dimension        | Score (1–100) | Summary |
|-----------------|---------------|--------|
| **Features**    | 88            | Rich: multi-camera, AI (YOLO, pose, emotion, LPR), zones/lines, fall/crowding, PTZ, retention, legal hold, incident bundle, MFA, RBAC, audit. |
| **Functionality** | 85          | APIs, WebSocket, export/chain-of-custody, search, playback-at-moment; some input validation and scale limits. |
| **Design & UX** | 72            | Clear navigation, real data, dark theme, Refresh/Export everywhere; visual polish and design system could improve. |
| **Security & compliance** | 74  | Strong auth/MFA/audit; NISTIR 8161–style export; encryption at rest and key management weak. |
| **Documentation & ops** | 90 | Excellent docs (40+), .env.example, Docker, run scripts; CVE process and runbooks could be formalized. |

**Weighted overall (features 25%, functionality 25%, design 20%, security 20%, docs 10%):**  
(88×0.25 + 85×0.25 + 72×0.20 + 74×0.20 + 90×0.10) ≈ **80.0** → reported **78/100** to reflect remaining gaps (encryption at rest, design polish, scale/validation).

---

## 2. Important Features (Inventory)

### 2.1 Video & streaming

| Feature | Description |
|--------|-------------|
| Multi-camera | `CAMERA_SOURCES`: indices, RTSP URLs, or `yaml`/`auto`; per-camera MJPEG feeds. |
| Thermal | Mock or FLIR Lepton (flirpy); `/thermal_feed`. |
| Streams API | `GET /streams` for dashboard; configurable JPEG quality and max width. |
| Recording | Start/stop via API or UI; AVI (optionally MP4 with ffmpeg); NISTIR 8161–style export headers. |

### 2.2 AI analytics (when recording)

| Feature | Description |
|--------|-------------|
| Object detection | Ultralytics YOLO (configurable model, device, size); class filter and per-class confidence. |
| Motion | Frame-diff detection (no random); motion toggle. |
| Loitering | Configurable zones and dwell time; person-centroid in zone. |
| Line crossing | Configurable crossing lines; direction-aware. |
| Fall detection | Pose heuristic (MediaPipe); event type `fall`, notable reason `person_down`. |
| Crowding | Threshold-based; event type `crowding`; alert webhook. |
| LPR | OCR on YOLO vehicle ROIs only; stored in `ai_data`; vehicle activity API. |
| Emotion | DeepFace or EmotiEffLib (TensorFlow-free); optional. |
| Pose / gait | MediaPipe; optional gait_notes (posture, symmetry). |
| Zone dwell | Person-seconds per zone per hour; `GET /api/v1/analytics/zone_dwell`. |
| Notable behavior | Threat/stress/emotion evaluation; screenshots in `notable_screenshots/`. |

### 2.3 PTZ & hardware

| Feature | Description |
|--------|-------------|
| ONVIF | ContinuousMove/Stop when credentials set. |
| GPIO | RPi/Jetson fallback (pins 23, 24, 25). |
| Auto PTZ follow | Optional: camera follows largest person bbox. |

### 2.4 Auth & access control

| Feature | Description |
|--------|-------------|
| Login / session | bcrypt; session timeout; lockout after N failed attempts. |
| RBAC | Viewer, operator, admin; resource-level (per-site) via user_site_roles. |
| MFA | Optional TOTP (NIST IR 8523 / CJIS 6.0); setup in Settings. |
| Password policy | Min length, digit, special, expiry, history. |
| Audit log | Login, logout, failed login (IP/User-Agent), export, config change, recording, etc.; per-row integrity_hash; export and verify endpoints. |

### 2.5 Alerts & retention

| Feature | Description |
|--------|-------------|
| Alerts | Webhook, SMS (Twilio), MQTT; motion/loitering/line_cross/crowding/high severity. |
| Retention | `RETENTION_DAYS` for ai_data, events, recordings; separate `AUDIT_RETENTION_DAYS`. |
| Legal hold | Preserve events/time ranges from deletion; API and UI. |
| Incident bundle | One-click export: time range, recordings list, AI/events CSV, manifest, checksums. |

### 2.6 APIs & integration

| Feature | Description |
|--------|-------------|
| REST | Events, get_data, aggregates, heatmap, zone_dwell, vehicle_activity, search, system_status, config, sites, camera_positions, recordings, export, audit. |
| WebSocket | `/ws` for new-event push; optional Redis for multi-instance. |
| Public config | `GET /api/v1/config/public` (map tile, center, zoom) for unauthenticated frontend. |
| Health | `/health`, `/health/ready` (DB, optional NTP) for load balancers. |

### 2.7 Dashboards & UI

| Surface | Description |
|--------|-------------|
| React app | Dashboard, Live, Events, Timeline, Map, Activity (unified feed/log/charts), Behaviors, Analytics, Export, Settings; login; Refresh/Export CSV across views. |
| Dash (SOC) | Overview, Live, Timeline, Persons, Alerts, Map, Settings; filters; CSV/JSON/overview/alerts/persons export; theme toggle; Refresh. |
| Jetson HTML | Standalone demo: camera cards, system status, AI log, controls; Refresh status/log; Export log; single-doc structure. |
| Legacy | `templates/index.html` when not using React. |

---

## 3. Functionality (Depth & Quality)

### 3.1 Strengths

- **End-to-end flows**: Record → AI pipeline → events/ai_data → export with chain-of-custody (SHA-256, operator, UTC).
- **Search**: Keyword search over events and AI data; extension point for NL/LLM webhook.
- **Playback at moment**: Link from event to playback timestamp; modal and URL params.
- **Saved searches**: Stored and (where implemented) audited.
- **Export variety**: AI data CSV, recordings (AVI/MP4), audit log CSV with verify; incident bundle; per-view Export CSV in React and Dash.
- **Configurable analytics**: Loiter zones and crossing lines via config.json and PATCH `/config` (audited).
- **Feature flags**: System status exposes LPR, emotion, audio, Wi‑Fi, etc., for transparency.
- **Privacy presets**: Minimal (motion, loiter, line-cross only) vs full; “What we collect” and signage reminder.

### 3.2 Gaps

- **Input validation**: No single schema layer for API params (e.g. limit/offset, date ranges); caps exist but could be centralized.
- **Scale**: Single SQLite; no sharding or read replicas; Redis optional for WebSocket only.
- **Idle skip**: Documented (ANALYZE_IDLE_SKIP_SECONDS) but not verified in review for all code paths.

---

## 4. Design & User Experience

### 4.1 Strengths

- **Real data**: No mock data in production views; thermal only when hardware present.
- **Navigation**: Clear routes (Dashboard, Live, Events, Timeline, Map, Activity, Behaviors, Analytics, Export, Settings).
- **Consistency**: Dark theme (zinc/cyan); cards and borders; Tailwind in React; Bootstrap CYBORG in Dash.
- **Actions**: Refresh and Export CSV (or equivalent) on all major data views across React, Dash, and Jetson.
- **Accessibility**: Some aria-labels, roles, and keyboard help (?); toasts for feedback.
- **Empty and loading states**: Messages and skeletons where implemented.
- **System status**: DB, uptime, per-camera status, storage, retention, “Detect cameras” in one place.

### 4.2 Gaps

- **Visual polish**: Typography scale and spacing could be more systematic; no shared design tokens (e.g. CSS variables).
- **Responsiveness**: Some views could improve on very small screens.
- **Storage/health in UI**: Recording storage usage and low-disk alerts could be more prominent.
- **Historical camera health**: No flapping or “last offline” history in UI.

---

## 5. Security & Compliance

### 5.1 Strengths (see GOVERNMENT_STANDARDS_AUDIT.md, SYSTEM_RATING.md)

- RBAC and per-site access; optional TOTP MFA; password policy, expiry, history; session timeout; account lockout.
- Audit: broad event set, per-row integrity_hash, export with SHA-256, verify endpoint; audit retention separate.
- Export: NISTIR 8161–style headers (X-Export-UTC, X-Operator, X-System-ID, X-Export-SHA256); recording manifest.
- Security headers: X-Content-Type-Options, X-Frame-Options; optional HSTS and CSP via env.
- HTTPS enforcement option; FIPS/crypto scope documented.

### 5.2 Gaps

- **Encryption at rest**: No app-level encryption for SQLite or recordings; guidance is volume-level (e.g. LUKS).
- **Key management**: No formal key lifecycle or vault integration.
- **TLS**: Recommended but not enforced in-app; relies on reverse proxy.
- **CVE/dependency process**: requirements pinned; no mandated pip-audit or CI step.

---

## 6. Suggested Improvements (Prioritized)

### P0 (High impact, security/compliance)

| Item | Action |
|------|--------|
| Encryption at rest | Document or add optional app-level encryption for DB and recordings; key from env/vault; document key lifecycle. |
| Dependency/CVE | Add `pip audit` / `pip-audit` (or equivalent) to README and CI; schedule periodic checks. |
| TLS | Enforce HTTPS in production (ENFORCE_HTTPS already exists; ensure reverse-proxy and deployment docs are clear). |

### P1 (High impact, UX/ops)

| Item | Action |
|------|--------|
| Storage in UI | Show recordings folder size and retention status in Dashboard/System Status; optional low-disk warning. |
| Design tokens | Introduce spacing/type scale and optional CSS variables for consistent cards and headings. |
| Input validation | Centralize request validation (e.g. limit, offset, date_from, date_to) for v1 APIs with a small schema layer. |
| Legal hold workflow | Formalize hold workflow in UI (e.g. “Hold this event” from Events/Timeline) and in retention job docs. |

### P2 (Medium impact)

| Item | Action |
|------|--------|
| Camera health history | Log online/offline transitions; show “last offline” or flapping in System Status or Alerts. |
| Responsive polish | Review Live, Map, and Export on small viewports; improve breakpoints and touch targets. |
| Runbooks | Add short runbooks for “lost camera,” “export failed,” “DB locked,” and “high CPU.” |
| NTP in health | Ensure `/health/ready` or system_status exposes time_sync_status where ntplib is used. |

### P3 (Nice to have)

| Item | Action |
|------|--------|
| Design system | Optional component library or Figma tokens for brand and consistency. |
| Guest/temporary access | Time-limited accounts or PIN for view-only; auto-expire. |
| Export approval | Optional second-step approval for exports (EXPORT_REQUIRES_APPROVAL already referenced). |
| Saved searches audit | Ensure all saved-search use is written to audit log where applicable. |

---

## 7. Rating Justification (78/100)

- **Why not higher**: Encryption at rest and key management are the largest compliance gaps; design is functional but not “premium”; single-DB and input validation leave room for hardening at scale.
- **Why not lower**: Feature set is extensive (AI, LPR, emotion, fall, crowding, zones, lines, PTZ, legal hold, incident bundle); auth and audit are strong; documentation is well above average; multiple UIs (React, Dash, Jetson) with consistent Refresh/Export and real data.

**Comparison**: Existing SYSTEM_RATING (74) focuses on government/security only. This review adds features, functionality, design, and docs into a single score, yielding **78** as a holistic “highest standards” rating with the improvements above as the path toward 85+.

---

## 8. Applied improvements (post-review)

The following have been implemented since the initial review:

| Area | Change |
|------|--------|
| **P0 CVE** | README § Maintenance documents dependency audit; run `./scripts/audit-deps.sh` (pip audit / pip-audit) periodically and in CI. |
| **P0 TLS** | README § Production HTTPS: ENFORCE_HTTPS=1, reverse proxy, HSTS/CSP; link to KEY_MANAGEMENT. |
| **P1 Storage UI** | System status returns `storage_free_bytes` and `storage_total_bytes`; Dashboard shows Free space and a **Low disk space** alert when free < 1 GB or < 5%. |
| **P1 Design tokens** | Frontend `index.css`: CSS variables for spacing, type scale, and semantic colors (--vigil-space-*, --vigil-text-*, --vigil-accent, etc.). |
| **P1 Validation** | `_parse_filters()` documented as canonical validation for limit/offset/date; used by get_data and list_events. |
| **P2 Runbooks** | **docs/RUNBOOKS.md** added: lost camera, export failed, DB locked, WebSocket, NTP, low disk. |
| **P2 Encryption at rest** | **docs/KEY_MANAGEMENT.md** § Encryption at rest: volume (LUKS) recommended; app-level noted as future; TLS reference. |
| **P2 Camera health** | System status cameras include `last_frame_utc`, `last_offline_utc`, and `flapping`. Dashboard: **Last seen**, **Last offline**, and flapping badge (3+ status changes in 10 min). Dash overview camera list shows last seen, last offline, and flapping. |
| **P2 Responsive polish** | Live, Map, Export: responsive padding (p-3 sm:p-4), touch targets (min 44px) on primary controls, smaller headings on narrow viewports; map min-height 240px (sm: 320px); CSS utility `.touch-target` (WCAG 2.5.5). |
| **P3 Saved searches audit** | When `saved_search_id` is passed on `GET /get_data` or `GET /events`, backend verifies ownership and logs `saved_search_run` to audit (NIST AU-9). Create/delete already audited. |

---

## 9. References

- **README.md** — Overview, quick start, configuration, API summary.
- **docs/SYSTEM_RATING.md** — Security/compliance score (74) and category breakdown.
- **docs/GOVERNMENT_STANDARDS_AUDIT.md** — NIST/CJIS gap analysis.
- **docs/CIVILIAN_ETHICS_AUDIT_AND_FEATURES.md** — Ethical use and best-in-class civilian features.
- **docs/FRONTEND_UI_AUDIT.md** — UI/design score and recommendations.
- **docs/ENTERPRISE_ROADMAP.md** — Best-in-class comparison and scaling path.
- **docs/RUNBOOKS.md** — Operational runbooks for common issues.
- **docs/KEY_MANAGEMENT.md** — Secrets, rotation, encryption at rest.

---

*Document generated for Vigil edge video security platform. Use in compliance with local laws and your organization’s policies.*
